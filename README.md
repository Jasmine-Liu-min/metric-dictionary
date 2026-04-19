# 数据口径查询助手

基于指标字典的本地搜索工具，支持关键词模糊匹配，快速查询指标的业务口径和技术口径。

## 功能

- 关键词模糊搜索指标名称和口径定义
- 按业务线、指标类型筛选
- 展示业务口径、技术口径、SQL 片段、来源信息
- Markdown 渲染的搜索结果，支持 SQL 高亮

## 安装

```bash
pip install -r requirements.txt
```

## 使用

```bash
python app.py
```

浏览器打开 http://localhost:7860 即可使用。

命令行模式：

```bash
python metric_search.py
```

## 数据

将指标字典 Excel 文件放入 `data/` 目录下（已在 .gitignore 中排除，不会上传）。

## 技术方案

- 数据读取：pandas + openpyxl
- 中文分词：jieba
- 搜索匹配：scikit-learn TF-IDF + 余弦相似度
- 网页界面：Gradio

纯本地运行，不依赖任何外部 API。
