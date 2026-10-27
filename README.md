# Jane Austen 无损压缩项目

根据 `project.pdf` 实现的纯 Python 压缩方案：5 阶 PPM 上下文模型、符号排除、更新排除、自适应逃逸概率估计和 32 位区间编码。原参考程序保存在 `reference/` 中。原文 `austen.txt` 未修改。

`compressed` 已生成，可直接使用。完整实测数据见 [验证记录](docs/validation.md) 和 [原始结果 JSON](docs/benchmark_results.json)。算法及二进制格式见 [技术说明](docs/technical_notes_zh.md)。

## 直接解压和比对

在项目目录运行，解码器会读取 `compressed` 并生成 `out.txt`：

```bash
python decompress.py
diff out.txt austen.txt
md5sum out.txt austen.txt
```

正确结果是 `diff` 无输出，两份文件的 MD5 均为 `967205af325fc85e5783b6847eaf8dba`。解码器仅导入 `struct`，无需安装第三方依赖，也不读取原文或项目中的其他 Python 文件。

## 重新压缩

```bash
python compress.py --verify
```

也支持输入、输出路径和上下文阶数：

```bash
python compress.py austen.txt compressed --order 5 --verify
```

`--verify` 会在写入前执行完整往返比对。`--order` 支持 1–8；实测 5 阶最适合本项目文本。新格式与参考程序的 6 位编码格式不同，必须配套使用新的压缩文件和解码器。

## 验证及评分

```bash
python -m unittest discover -s tests -v
python benchmark.py
```

`benchmark.py` 先核对 PDF 指定的原文 MD5，然后将**仅有** `compressed` 和 `decompress.py` 的副本放入临时目录独立解压；比较全部字节，测量用户 CPU 时间和 Linux 峰值内存，并统计 `compressed + decompress.pyc`。gzip、bzip2、xz 只用于开发阶段的比较，没有进入最终解码器。

复现参数比较：

```bash
python benchmark.py --orders 4 6 7 8
```

报告里的压缩大小应包含解码器字节码，而不只统计 `compressed`。`.pyc` 大小取决于解释器版本、编译选项及编译时保存的源文件名；脚本使用普通编译、源文件名 `decompress.py`。本地环境为 Python 3.12.14；PDF 指定的 ECE 环境是 3.12.4，本工作区没有该集群的访问配置。提交前在集群执行：

```bash
module load anaconda3
/usr/bin/time --format %U python decompress.py
diff out.txt austen.txt
python -m py_compile decompress.py
```

## 报告与提交

PDF 要求最终提交**恰好三个文件**：

1. 本项目根目录的 `compressed`。
2. 本项目根目录的 `decompress.py`。
3. **由你本人撰写**的 PDF 报告。

PDF 第 3 页明确允许 AI 编码，但要求报告由学生本人撰写，且包含标题为 **Acknowledgments** 的独立章节。因此这里提供的是报告写作材料，不是可直接提交的成品报告：

- [报告空白提纲（Markdown）](docs/report_template.md)
- [报告空白提纲（PDF）](docs/report_template.pdf)
- [算法及格式技术说明](docs/technical_notes_zh.md)
- [实测验证记录](docs/validation.md)
- [贡献与来源核对清单](docs/acknowledgments_checklist.md)

请根据自己的理解完成报告，并如实说明 AI 设计、编码、调参与测试的贡献，以及你自己实际完成的工作。不要把模板直接当作完成的报告提交。`compress.py`、测试、原文、原参考代码和开发工具均不属于上述三份提交文件。

## 开发文件

- `compress.py`：可复现编码器，默认输出 `compressed`。
- `decompress.py`：独立解码器；成功时只写 `out.txt`。
- `benchmark.py`：完整文本验收、评分口径和参数比较。
- `tests/test_codec.py`：边界输入、二进制字符、确定性、缩放、损坏及独立解码测试。
- `tools/build_docs.py`：从实测 JSON 生成验证说明和空白报告 PDF；仅此开发工具需要 `reportlab`。
- `reference/`：原始参考代码，保留用于对照。
