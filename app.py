import gradio as gr
from metric_search import MetricSearchEngine

engine = MetricSearchEngine()

# 缓存当前搜索结果
_last_results = {}


def search(query, biz_line, metric_type):
    _last_results.clear()

    if not query.strip():
        return "请输入搜索关键词", gr.update(choices=[], value=None, visible=False), gr.update(value="", visible=False)

    results = engine.search(query, biz_line, metric_type)
    if results.empty:
        return "未找到相关指标", gr.update(choices=[], value=None, visible=False), gr.update(value="", visible=False)

    cards = []
    sql_choices = []
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
            label = f"{i}. {row['指标名称']}"
            _last_results[label] = sql
            sql_choices.append(label)
            if len(sql) > 300:
                parts.append(f"\n**SQL**（预览，完整内容请在下方选择查看）\n```sql\n{sql[:300]}\n-- ...\n```")
            else:
                parts.append(f"\n**SQL**\n```sql\n{sql}\n```")

        parts.append(f"\n*来源: {row['来源']}*")
        cards.append("\n".join(parts))

    md = "\n\n---\n\n".join(cards)
    has_sql = len(sql_choices) > 0
    return md, gr.update(choices=sql_choices, value=None, visible=has_sql), gr.update(value="", visible=False)


def show_full_sql(choice):
    if not choice or choice not in _last_results:
        return gr.update(value="", visible=False)
    sql = _last_results[choice]
    return gr.update(value=f"```sql\n{sql}\n```", visible=True)


# 构建加载状态提示
status_parts = [f"已加载 **{len(engine.df)}** 条指标记录"]
if engine.df.empty and engine.load_errors:
    status_parts = ["⚠️ 未加载到任何数据"]
if not engine.df.empty:
    status_parts.append(f"覆盖业务线: {', '.join(engine.get_biz_lines()[1:])}")
if engine.load_errors:
    status_parts.append("\n\n**加载警告:**\n" + "\n".join(f"- {e}" for e in engine.load_errors))
status_text = "　".join(status_parts) if not engine.load_errors else "\n".join(status_parts)

with gr.Blocks(title="数据口径查询助手") as app:
    gr.Markdown("# 数据口径查询助手")
    gr.Markdown(status_text)

    with gr.Row():
        query_input = gr.Textbox(label="搜索关键词", placeholder="输入指标名称或关键词，如：有效播放、日活、留存率", scale=3)
        biz_line = gr.Dropdown(choices=engine.get_biz_lines(), value="全部", label="业务线", scale=1)
        metric_type = gr.Dropdown(choices=engine.get_metric_types(), value="全部", label="指标类型", scale=1)
        search_btn = gr.Button("搜索", variant="primary", scale=1)

    output = gr.Markdown(label="搜索结果")

    sql_selector = gr.Dropdown(label="查看完整 SQL", choices=[], visible=False)
    sql_display = gr.Markdown(visible=False)

    search_btn.click(fn=search, inputs=[query_input, biz_line, metric_type], outputs=[output, sql_selector, sql_display])
    query_input.submit(fn=search, inputs=[query_input, biz_line, metric_type], outputs=[output, sql_selector, sql_display])
    sql_selector.change(fn=show_full_sql, inputs=[sql_selector], outputs=[sql_display])

if __name__ == "__main__":
    app.launch(server_name="127.0.0.1", server_port=7860, theme=gr.themes.Soft())
