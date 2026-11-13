# PDF 图表提取工具

[English](README.md) · **简体中文**

一个基于页面结构 JSON 与归一化边界框坐标，从 PDF 文档中提取图片与图表的 Python 工具。每张提取出的图像都会附带对应的图注、脚注及结构化元数据。

## 功能

- 使用 PyMuPDF 将 PDF 页面渲染为图像。
- 从 JSON 中读取预定义的 `group`、`image`、`figuregroup` 与 `chart` 层级结构。
- 按归一化 `bbox` 坐标裁剪图像。
- 区分单个子图与完整图像，避免重复提取。
- 将图注与脚注关联到对应图像。
- 根据子图编号与描述生成可读的文件名。
- 为每张提取图像生成一个元数据 JSON 文件。
- 生成包含全部提取记录的 `extraction_index.json`。
- 跳过过小或裁剪结果为空的区域。

## 流程

```text
PDF + 页面结构 JSON
          |
          v
将每页渲染为 PIL 图像
          |
          v
遍历 JSON，收集目标元素
          |
          v
将归一化边界框换算为像素坐标
          |
          v
裁剪并将每个目标保存为 PNG
          |
          v
写出单图元数据与汇总索引
```

## 项目结构

```text
pdf-figure-extractor/
├── extract_sources.py          # 主提取脚本
├── examples/                   # 输出格式示例（见 examples/README.md）
└── README.md
```

脚本使用两个输入文件：

- `PDF_PATH`：待提取图表的 PDF 文档。
- `JSON_PATH`：页面结构 JSON，包含元素类型、坐标、图注与脚注。

## 环境要求

- Python 3.9 及以上
- [PyMuPDF](https://pymupdf.readthedocs.io/)
- [Pillow](https://pillow.readthedocs.io/)

创建虚拟环境并安装依赖：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install PyMuPDF Pillow
```

## 配置

运行前，在 `extract_sources.py` 顶部设置工作目录与输入路径：

```python
WORK_DIR = Path(__file__).resolve().parent
PDF_PATH = WORK_DIR / "input.pdf"
JSON_PATH = WORK_DIR / "connected-imagecaption.json"
OUT_DIR = WORK_DIR / "output"
```

渲染分辨率由以下参数控制：

```python
RENDER_DPI = 150
```

DPI 越高，图像越大越清晰，但内存占用与处理时间也随之增加。

如需自定义输出文件名，可修改子图映射表与表格信息：

```python
FIG1_ORDER_MAP = {...}
FIG2_LEGEND_MAP = {...}
FIG3_ORDER_MAP = {...}
TABLE_INFO = (...)
```

每条映射的格式如下：

```python
json_order: ("panel_id", "description")
```

示例：

```python
5: ("A", "performance_curve")
```

## 使用方法

在项目目录下运行：

```bash
python extract_sources.py
```

脚本会输出：

- PDF、JSON 与输出目录的路径。
- PDF 页数与 JSON 页数。
- 找到的提取目标数量。
- 每张已保存图像的文件名及其关联文本。
- 最终写出的图像数量。

## 提取规则

- `chart` 元素作为单个子图提取。
- `image` 元素仅在其不包含 `figuregroup` 时提取。
- `figuregroup` 作为子图容器，本身不直接导出。
- `group` 用于将图像与图注、脚注关联，本身不直接导出。
- 没有 `bbox` 的元素会被忽略。
- 归一化宽度或高度小于 `0.005` 的元素会被忽略。
- 超出页面范围的坐标会被截断到有效边界内。
- 裁剪结果为空时跳过。

## 输出文件

当子图编号与描述均可用时，图像文件名格式为：

```text
{panel_id}_{description}.png
```

对应的元数据文件名为：

```text
{panel_id}_{description}_meta.json
```

若未配置子图编号，脚本会根据图号、页码、元素序号与元素类型生成备用文件名。

输出目录中还包含：

```text
extraction_index.json
```

该文件为 JSON 数组，包含所有提取图像的元数据，便于批量处理与后续分析。

## 元数据字段

| 字段 | 说明 |
|---|---|
| `page` | PDF 页码（从 1 开始） |
| `order` | 源 JSON 中的嵌套元素序号 |
| `type` | 目标类型，如 `chart` 或 `image` |
| `panel_id` | 子图或表格编号 |
| `description` | 文件名中使用的简短描述 |
| `figure_label` | 关联的图或表标题 |
| `bbox_norm` | 归一化裁剪坐标 `x1`、`y1`、`x2`、`y2` |
| `caption` | 关联的图注文本 |
| `footnote` | 当前实现中为图注与脚注的合并文本 |
| `context` | 当前实现中为合并后的脚注文本 |
| `image_size_px` | 输出图像尺寸 `[宽, 高]` |
| `pdf_size` | 源 JSON 中记录的页面尺寸 |

> 在当前实现中，由于 `build_text()` 返回值的赋值顺序，`footnote` 与 `context` 并不完全符合其通常含义。若需严格区分，请修改 `collect_targets()` 中的赋值。

## 核心函数

### `sanitize_filename()`

去除文件名中的非法字符，合并连续下划线，并限制文件名长度。

### `render_pdf_to_images()`

按设定 DPI 渲染每一页 PDF，并转换为 RGB 格式的 PIL 图像。

### `crop_subimage()`

将归一化坐标换算为像素坐标，截断到有效范围后裁剪源图像。

### `collect_targets()`

遍历单页 JSON 结构，关联图注与脚注，收集所有符合条件的提取目标。

### `main()`

校验输入、加载 JSON、渲染 PDF、收集目标、保存图像与元数据，并写出汇总索引。

## 局限

- 输入与输出路径在源码中配置，目前不支持命令行参数。
- 子图编号与描述依赖人工维护的映射表。
- 若页码或 JSON 元素序号改变，需同步更新映射表。
- 独立的 `image` 元素目前共用同一个 `TABLE_INFO`，处理多张独立图像时需扩展命名逻辑。
- 同名文件会被覆盖，旧文件不会被自动删除。
- OCR 与上游解析错误会原样保留在导出的元数据中。
