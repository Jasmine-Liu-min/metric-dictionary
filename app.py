import gradio as gr
from metric_search import MetricSearchEngine

engine = MetricSearchEngine()


def search(query, biz_line, metric_type):
    if not query.strip():
        return "请输入搜索关键词"

    results = engine.search(query, biz_line, metric_type)
    if results.empty:
        return "未找到相关指标"

    cards = []
    for i, (_, row) in enumerate(results.iterrows(), 1):
        parts = [f"### {i}. {row['指标名称']}"]
        tags = []
        if row["业务线"]:
            tags.append(f"**业务线:** {row['业务线']}")
        if row["类型"]:
            tags.append(f"**类型:** {row['类型']}")
        if row["指标编码"]:
            tags.append(f"**编码:** {row['指标编码']}")
        if row["应用报表"]:
            tags.append(f"**报表:** {row['应用报表']}")
        parts.append(" | ".join(tags))

        if row["业务口径"]:
            parts.append(f"\n**业务口径**\n\n{row['业务口径']}")
        if row["技术口径"]:
            parts.append(f"\n**技术口径**\n\n{row['技术口径']}")
        if row["SQL"]:
            sql = row["SQL"]
            if len(sql) > 500:
                sql = sql[:500] + "\n-- ... SQL过长已截断"
            parts.append(f"\n**SQL**\n```sql\n{sql}\n```")
        parts.append(f"\n*来源: {row['来源']}*")

        cards.append("\n".join(parts))

    return "\n\n---\n\n".join(cards)


with gr.Blocks(title="数据口径查询助手", theme=gr.themes.Soft()) as app:
    gr.Markdown("# 数据口径查询助手")
    gr.Markdown(f"已加载 **{len(engine.df)}** 条指标记录，覆盖业务线: {', '.join(engine.get_biz_lines()[1:])}")

    with gr.Row():
        query_input = gr.Textbox(label="搜索关键词", placeholder="输入指标名称或关键词，如：有效播放、日活、留存率", scale=3)
        biz_line = gr.Dropdown(choices=engine.get_biz_lines(), value="全部", label="业务线", scale=1)
        metric_type = gr.Dropdown(choices=engine.get_metric_types(), value="全部", label="指标类型", scale=1)
        search_btn = gr.Button("搜索", variant="primary", scale=1)

    output = gr.Markdown(label="搜索结果")

    search_btn.click(fn=search, inputs=[query_input, biz_line, metric_type], outputs=output)
    query_input.submit(fn=search, inputs=[query_input, biz_line, metric_type], outputs=output)

if __name__ == "__main__":
    app.launch(server_name="127.0.0.1", server_port=7860)
