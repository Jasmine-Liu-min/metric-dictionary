import os
import pandas as pd
import jieba
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


def _safe_str(val):
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return ""
    return str(val).strip()


def _load_biz_a():
    """加载业务线A的指标字典"""
    path = os.path.join(DATA_DIR, "业务线A数据方案.xlsx")
    if not os.path.exists(path):
        return pd.DataFrame()

    df = pd.read_excel(path, sheet_name="指标字典", header=None)
    header = df.iloc[0].tolist()
    df = df.iloc[1:].reset_index(drop=True)
    df.columns = header + [f"col_{i}" for i in range(len(df.columns) - len(header))] if len(df.columns) > len(header) else header[:len(df.columns)]

    records = []
    for _, row in df.iterrows():
        name = _safe_str(row.get("指标名", ""))
        if not name or name in ("原子指标", "派生指标", "衍生指标", "名词定义"):
            continue
        records.append({
            "业务线": "业务线A",
            "指标编码": _safe_str(row.get("指标编码", "")),
            "指标名称": name,
            "类型": _safe_str(row.get("字典类型", "")),
            "业务口径": _safe_str(row.get("业务口径", "")),
            "技术口径": _safe_str(row.get("技术口径", "")),
            "SQL": "",
            "应用报表": _safe_str(row.get("报表依赖", "")),
            "来源": "业务线A数据方案.xlsx / 指标字典",
        })
    return pd.DataFrame(records)


def _load_biz_b():
    """加载业务线B的指标字典"""
    path = os.path.join(DATA_DIR, "业务线B指标字典.xlsx")
    if not os.path.exists(path):
        return pd.DataFrame()

    frames = []

    try:
        df = pd.read_excel(path, sheet_name="指标（汇总）")
        for _, row in df.iterrows():
            name = _safe_str(row.get("指标名称", ""))
            if not name:
                continue
            frames.append({
                "业务线": "业务线B",
                "指标编码": _safe_str(row.get("指标编码", "")),
                "指标名称": name,
                "类型": "指标",
                "业务口径": _safe_str(row.get("业务口径", "")),
                "技术口径": _safe_str(row.get("技术口径", "")),
                "SQL": _safe_str(row.get("开发逻辑\n（填线上版本的逻辑）", row.get("开发逻辑", ""))),
                "应用报表": _safe_str(row.get("应用报表", "")),
                "来源": "业务线B指标字典.xlsx / 指标（汇总）",
            })
    except Exception:
        pass

    try:
        df = pd.read_excel(path, sheet_name="概念定义")
        for _, row in df.iterrows():
            name = _safe_str(row.get("概念名", ""))
            if not name:
                continue
            frames.append({
                "业务线": "业务线B",
                "指标编码": "",
                "指标名称": name,
                "类型": "概念定义",
                "业务口径": _safe_str(row.get("定义", "")),
                "技术口径": _safe_str(row.get("技术口径", "")),
                "SQL": "",
                "应用报表": "",
                "来源": "业务线B指标字典.xlsx / 概念定义",
            })
    except Exception:
        pass

    return pd.DataFrame(frames) if frames else pd.DataFrame()


def load_all():
    dfs = [_load_biz_a(), _load_biz_b()]
    dfs = [d for d in dfs if not d.empty]
    if not dfs:
        return pd.DataFrame(columns=["业务线", "指标编码", "指标名称", "类型", "业务口径", "技术口径", "SQL", "应用报表", "来源"])
    return pd.concat(dfs, ignore_index=True)


class MetricSearchEngine:
    def __init__(self):
        self.df = load_all()
        if self.df.empty:
            self.vectorizer = None
            self.tfidf_matrix = None
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
