#!/usr/bin/env python3
"""Generate a factual validation record and an unfilled report worksheet PDF.

Only this optional development tool needs reportlab; the codec has no dependency.
"""
import json
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]


def write_validation():
    r = json.loads((ROOT / "docs/benchmark_results.json").read_text())
    rows = [f"| 原文 | {r['source_bytes']:,} |",
            f"| compressed | {r['compressed_bytes']:,} |",
            f"| decompress.pyc | {r['decoder_pyc_bytes']:,} |",
            f"| **评分总大小** | **{r['scored_bytes']:,}** |"]
    baselines = [f"| 参考 6 位短语格式（计算值） | {r['reference_format']['data_bytes']:,} | — |"]
    for name, entry in r["baselines"].items():
        baselines.append(f"| {name} | {entry['data_bytes']:,} | "
                         f"{entry['scored_reduction_vs_data_only']:.2%} |")
    orders = {5: (r["compressed_bytes"], None)}
    for entry in r["order_experiments"]:
        orders[entry["order"]] = (entry["data_bytes"], entry["encode_wall_seconds"])
    order_rows = []
    for order, (size, seconds) in sorted(orders.items()):
        elapsed = f"{seconds:.3f}" if seconds is not None else "已生成并往返验证"
        order_rows.append(f"| {order} | {size:,} | {elapsed} |")
    text = f"""# 实测验证记录

这是由工具根据 `benchmark_results.json` 生成的工程实验记录，不是学生提交报告。

## 输入与输出

- 原文大小：{r['source_bytes']:,} 字节。
- PDF 指定 MD5 / 实测原文 MD5：`{r['source_md5']}`。
- 独立解压后 MD5：`{r['decoded_md5']}`。
- 原文和输出已逐字节比较，完全一致。
- 压缩文件 SHA-256：`{r['compressed_sha256']}`。

## PDF 评分口径

| 项目 | 字节 |
|---|---:|
{chr(10).join(rows)}

计入解码器后的比例是 **{r['scored_ratio']:.4%}**，即缩小 **{1-r['scored_ratio']:.4%}**；总位数/字符为 **{r['scored_bits_per_character']:.6f}**。
只计数据时为 {r['data_bits_per_character']:.6f} 位/字符。原文为 ASCII，每字节对应一个字符。

`.pyc` 使用当前 Python 的正常编译模式，保存的源文件名固定为 `decompress.py`，包含 .pyc 头。解释器版本或编译路径变化可能使数值略有变化。

## 独立解码性能

| 指标 | 本地实测 |
|---|---:|
| 用户 CPU 秒 | {r['decode_user_seconds']:.6f} |
| 系统 CPU 秒 | {r['decode_system_seconds']:.6f} |
| 墙钟秒 | {r['decode_wall_seconds']:.6f} |
| Linux 子进程峰值 RSS | {r['decode_peak_rss_kib_linux']:,} KiB（约 {r['decode_peak_rss_kib_linux']/1024:.2f} MiB） |

测试环境：`{r['python']}`，`{r['platform']}`。

测量在仅包含 `compressed` 与 `decompress.py` 的临时目录执行 `python -I -S -B decompress.py`，没有原文、编码器或其他项目模块。解码器源码静态检查显示仅导入 `struct`。它也没有执行外部程序。

本地 CPU 时间低于 PDF 的 1,200 秒限制。本工作区未连接 ECE 集群，因此**没有声称在集群 Python 3.12.4 上验证**；提交前请按 README 的集群命令复核时间、大小和输出。

## 通用压缩器比较

| 比较对象 | 仅压缩文件字节 | 本方案评分总大小比该文件更小 |
|---|---:|---:|
{chr(10).join(baselines)}

本方案在此表中使用 **{r['scored_bytes']:,} 字节（已计入解码器）**，比较对象只计压缩文件，没有计其解码器。gzip/bzip2/xz 的往返验证也已通过。表中数值不是对全局最优压缩率的证明。

参考格式大小通过相同的贪心短语选择和四编码一组规则计算，未用其原始脚本测量耗时；因此不报告原始脚本的加速倍数。参考分词共 {r['reference_format']['tokens']:,} 个编码，未写入的尾部为 {r['reference_format']['discarded_tail_bytes']} 字节，十六进制 `{r['reference_format']['discarded_tail_hex']}`。该输入恰好可以由参考解码器补换行恢复，但该规则不能保证其他输入无损。

## 最终算法参数比较

| 最大上下文阶数 | 压缩文件字节（含头与字符表） | 编码墙钟秒 |
|---:|---:|---:|
{chr(10).join(order_rows)}

以上使用同一套最终算法，只改变最大上下文阶数。5 阶在这些候选中大小最小。4/6/7/8 阶试验统计编码结果，最终提交的 5 阶流另外完成了往返和独立解码验证。

## 自动测试

`python -m unittest discover -s tests -v`：7 项测试全部通过，覆盖空输入、尾部长度、末尾换行、CRLF、Unicode 原始字节、全 256 字节字符表、随机输入、长重复串及计数缩放、编码确定性、损坏输入、允许导入检查和独立解码。测试还确认失败的解码不会覆盖既有输出。

## 复现

```bash
python compress.py --verify
python -m unittest discover -s tests -v
python benchmark.py --orders 4 6 7 8
python tools/build_docs.py
```

最后一条是可选文档生成命令，需要 `reportlab`；其余命令及最终解码器仅依赖 Python 标准库。
"""
    (ROOT / "docs/validation.md").write_text(text, encoding="utf-8")


def write_worksheet_pdf():
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, PageBreak,
                                   Table, TableStyle)

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="WorksheetTitle", parent=styles["Title"],
                              fontSize=20, leading=24, alignment=TA_CENTER))
    styles["BodyText"].leading = 15
    target = ROOT / "docs/report_template.pdf"
    doc = SimpleDocTemplate(str(target), title="Report worksheet - student authoring required",
                            author="AI-generated blank worksheet", pagesize=(612, 792),
                            rightMargin=54, leftMargin=54, topMargin=54, bottomMargin=54)
    story = []

    def para(text, style="BodyText"):
        story.append(Paragraph(escape(text), styles[style]))
        story.append(Spacer(1, 8))

    def blank(lines):
        table = Table([[""] for _ in range(lines)], colWidths=[504], rowHeights=24)
        table.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.4, colors.lightgrey)]))
        story.extend([table, Spacer(1, 12)])

    para("Lossless Compression Project", "WorksheetTitle")
    para("REPORT WRITING WORKSHEET", "Heading1")
    para("NOT A COMPLETED SUBMISSION REPORT. The course PDF requires the report "
         "to be written by the student. Write your own report and include a separate "
         "section titled Acknowledgments. Do not submit this worksheet unchanged.")
    para("Student(s): ____________________    Course: ____________________")
    para("1. Objective and constraints", "Heading2")
    para("Explain exact reconstruction, permitted imports, the CPU limit, and the "
         "compressed-data-plus-decoder-bytecode scoring metric in your own words.")
    blank(4)
    para("2. Modeling approach", "Heading2")
    para("Explain the reference scheme's limits, context initialization, dictionary "
         "ordering, backoff and symbol exclusion. Describe why this models English.")
    blank(6)
    story.append(PageBreak())
    para("3. Algorithm and file format", "Heading1")
    para("Explain the shared escape-estimation buckets, their initial counts and "
         "rescaling. Describe update exclusion and model count rescaling. Explain "
         "the integer range coder, carry handling and termination. Include enough "
         "detail for another student to implement a similar scheme.")
    blank(10)
    para("Describe the header fields, alphabet, payload, output length and checksum. "
         "Explain how the decoder rebuilds all models without the original file.")
    blank(7)
    story.append(PageBreak())
    para("4. Experiments and discussion", "Heading1")
    para("Use docs/benchmark_results.json and docs/validation.md as factual inputs. "
         "Record any measurements you personally repeat. Distinguish local tests "
         "from tests performed on the required ECE cluster.")
    rows = [["Measurement", "Your verified result"],
            ["Original bytes and MD5", ""], ["Compressed data bytes", ""],
            ["Decoder bytecode bytes", ""], ["Scored total bytes", ""],
            ["Scored bits per character", ""], ["Decoder user CPU seconds", ""],
            ["Python version and machine", ""]]
    table = Table(rows, colWidths=[240, 264], rowHeights=28)
    table.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                              ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
                              ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold")]))
    story.extend([table, Spacer(1, 12)])
    para("Discuss context-order comparisons, memory, tradeoffs, limitations and "
         "what you learned. Do not claim global optimality or cluster validation "
         "without evidence.")
    blank(9)
    story.append(PageBreak())
    para("Acknowledgments", "Heading1")
    para("REQUIRED SECTION TITLE. Attribute the main algorithmic ideas, all AI "
         "assistance, and external material actually used. State what the AI "
         "designed, implemented and tested, and what you personally did. Use "
         "docs/acknowledgments_checklist.md to check the facts.")
    blank(8)
    para("References", "Heading2")
    para("List the supplied material and other sources you actually read. Verify "
         "the bibliographic details of suggested literature before citing it.")
    blank(5)
    para("Final submission check", "Heading2")
    para("Submit exactly three separate files: compressed, decompress.py, and "
         "your own PDF report. Confirm exact reconstruction, CPU time below "
         "1,200 seconds, bytecode-inclusive size, and a separate Acknowledgments "
         "section. The report must be written by you.")

    def footer(canvas, document):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.drawString(54, 30, "Blank worksheet - student authoring required")
        canvas.drawRightString(558, 30, str(document.page))
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)


if __name__ == "__main__":
    write_validation()
    write_worksheet_pdf()
    print("Generated docs/validation.md and docs/report_template.pdf")
