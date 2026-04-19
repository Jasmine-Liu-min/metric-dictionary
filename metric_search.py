import os
import yaml
import pandas as pd
import jieba
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sources.yaml")

SYSTEM_FIELDS = ["业务线", "指标编码", "指标名称", "类型", "业务口径", "技术口径", "SQL", "应用报表", "来源"]


def _safe_str(val):
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return ""
    return str(val).strip()


def _load_source(src):
    """根据一条 sources.yaml 配置加载数据，返回 DataFrame 和错误信息列表。"""
    errors = []
    path = os.path.join(DATA_DIR, src["file"])
    if not os.path.exists(path):
        errors.append(f"文件不存在: {src['file']}")
        return pd.DataFrame(), errors

    try:
        skip = src.get("skip_rows", 0)
        if skip > 0:
            df = pd.read_excel(path, sheet_name=src["sheet"], header=None)
            header = df.iloc[0].tolist()
            df = df.iloc[skip:].reset_index(drop=True)
            df.columns = (header + [f"col_{i}" for i in range(len(df.columns) - len(header))])[:len(df.columns)]
        else:
            df = pd.read_excel(path, sheet_name=src["sheet"])
    except Exception as e:
        errors.append(f"{src['file']} / {src['sheet']}: 读取失败 - {e}")
        return pd.DataFrame(), errors

    # 构建列名模糊匹配：去掉空白字符后比较，解决 Excel 列名含换行符的问题
    def _normalize(s):
        return "".join(str(s).replace("\\n", "").split())

    col_norm_map = {_normalize(c): c for c in df.columns}

    def _find_col(name):
        if name in df.columns:
            return name
        return col_norm_map.get(_normalize(name))

    col_map = src.get("columns", {})
    name_col_cfg = col_map.get("指标名称")
    name_col = _find_col(name_col_cfg) if name_col_cfg else None
    if not name_col:
        errors.append(f"{src['file']} / {src['sheet']}: 找不到指标名称列「{name_col}」")
        return pd.DataFrame(), errors

    skip_values = set(src.get("skip_values", []))

    records = []
    for _, row in df.iterrows():
        name = _safe_str(row.get(name_col, ""))
        if not name or name in skip_values:
            continue

        record = {"业务线": src.get("biz_line", ""), "来源": src.get("source_tag", src["file"])}
        for sys_field, excel_col in col_map.items():
            if sys_field.endswith("_fallback"):
                continue
            if sys_field == "指标名称":
                record["指标名称"] = name
            elif excel_col.startswith("_literal:"):
                record[sys_field] = excel_col[len("_literal:"):]
            else:
                real_col = _find_col(excel_col)
                val = _safe_str(row.get(real_col, "")) if real_col else ""
                # 支持 fallback 列
                if not val:
                    fallback_col_cfg = col_map.get(f"{sys_field}_fallback")
                    if fallback_col_cfg:
                        fallback_col = _find_col(fallback_col_cfg)
                        if fallback_col:
                            val = _safe_str(row.get(fallback_col, ""))
                record[sys_field] = val

        # 补齐缺失字段
        for f in SYSTEM_FIELDS:
            record.setdefault(f, "")
        records.append(record)

    return pd.DataFrame(records, columns=SYSTEM_FIELDS), errors


def load_all():
    """加载所有数据源，返回 (DataFrame, errors)。"""
    if not os.path.exists(CONFIG_PATH):
        return pd.DataFrame(columns=SYSTEM_FIELDS), ["未找到 sources.yaml 配置文件"]

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    sources = config.get("sources", [])
    if not sources:
        return pd.DataFrame(columns=SYSTEM_FIELDS), ["sources.yaml 中没有配置任何数据源"]

    all_dfs = []
    all_errors = []
    for src in sources:
        df, errs = _load_source(src)
        all_errors.extend(errs)
        if not df.empty:
            all_dfs.append(df)

    if not all_dfs:
        return pd.DataFrame(columns=SYSTEM_FIELDS), all_errors

    return pd.concat(all_dfs, ignore_index=True), all_errors


class MetricSearchEngine:
    def __init__(self):
        self.df, self.load_errors = load_all()
        self.vectorizer = None
        self.tfidf_matrix = None

        if self.df.empty:
            return

        corpus = (
            self.df["指标名称"].fillna("") + " " +
            self.df["业务口径"].fillna("") + " " +
            self.df["技术口径"].fillna("")
        ).apply(lambda x: " ".join(jieba.cut(x)))

        self.vectorizer = TfidfVectorizer()
        self.tfidf_matrix = self.vectorizer.fit_transform(corpus)

    def search(self, query, biz_line="全部", metric_type="全部", top_k=10):
        if self.vectorizer is None or not query.strip():
            return pd.DataFrame()

        query_cut = " ".join(jieba.cut(query))
        query_vec = self.vectorizer.transform([query_cut])
        scores = cosine_similarity(query_vec, self.tfidf_matrix).flatten()

        df = self.df.copy()
        df["相关度"] = scores

        # 精确匹配加权：指标名称包含搜索词的，相关度 +1（保证排在前面）
        df.loc[df["指标名称"].str.contains(query, na=False), "相关度"] += 1.0

        if biz_line != "全部":
            df = df[df["业务线"] == biz_line]
        if metric_type != "全部":
            df = df[df["类型"] == metric_type]

        df = df[df["相关度"] > 0].sort_values("相关度", ascending=False).head(top_k)
        return df.drop(columns=["相关度"])

    def get_biz_lines(self):
        if self.df.empty:
            return ["全部"]
        return ["全部"] + sorted(self.df["业务线"].unique().tolist())

    def get_metric_types(self):
        if self.df.empty:
            return ["全部"]
        return ["全部"] + sorted(self.df["类型"].unique().tolist())


if __name__ == "__main__":
    engine = MetricSearchEngine()

    if engine.load_errors:
        print("⚠️  数据加载警告:")
        for err in engine.load_errors:
            print(f"   - {err}")
        print()

    print(f"已加载 {len(engine.df)} 条指标记录")
    print(f"业务线: {engine.get_biz_lines()}")
    print(f"类型: {engine.get_metric_types()}")
    print()

    while True:
        query = input("请输入要查询的指标（输入 q 退出）: ").strip()
        if query.lower() == "q":
            break
        results = engine.search(query)
        if results.empty:
            print("未找到相关指标\n")
            continue
        for i, (_, row) in enumerate(results.iterrows(), 1):
            print(f"\n--- 结果 {i} ---")
            print(f"指标名称: {row['指标名称']}")
            print(f"业务线:   {row['业务线']}")
            print(f"类型:     {row['类型']}")
            print(f"业务口径: {row['业务口径']}")
            if row["技术口径"]:
                print(f"技术口径: {row['技术口径']}")
            if row["SQL"]:
                print(f"SQL:      {row['SQL'][:200]}...")
            print(f"来源:     {row['来源']}")
        print()
