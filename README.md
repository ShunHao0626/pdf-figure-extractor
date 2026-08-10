# PDF 图表提取与元数据导出

该脚本根据 JSON 中记录的页面结构和归一化坐标，从 PDF 中自动裁剪图表，并为每张图片导出对应的元数据。

## 主要功能

- 使用 PyMuPDF 将 PDF 页面渲染为图片。
- 按既定层级读取 JSON 中的 `group`、`image`、`figuregroup` 和 `chart` 结构。
- 根据归一化 `bbox` 坐标裁剪图表区域。
- 区分子图与整图，避免重复提取父级容器。
- 将 caption 和 footnote 关联到对应图表。
- 根据面板编号和内容描述生成可读文件名。
- 为每张图片生成独立的 JSON 元数据。
- 生成 `extraction_index.json`，汇总全部提取结果。
- 自动过滤尺寸过小或裁剪结果为空的区域。

## 处理流程

```text
PDF + 页面结构 JSON
        │
        ▼
将每一页渲染为 PIL Image
        │
        ▼
遍历 JSON 并识别待提取节点
        │
        ▼
将归一化 bbox 转换为像素坐标
        │
        ▼
裁剪并保存 PNG
        │
        ▼
输出单图元数据和总索引
```

## 文件说明

```text
CODE.V2/
├── 5.extract_sources.py        # 主程序
├── *.pdf                       # 示例 PDF 输入
├── *.json                      # 示例页面结构数据
├── *_extracted_sources_v2/     # 示例输出目录
└── README.md
```

脚本实际使用两个输入：

- `PDF_PATH`：需要提取图表的 PDF。
- `JSON_PATH`：包含页面层级、元素类型、坐标、caption 和 footnote 的 JSON。

## 环境要求

- Python 3.9+
- PyMuPDF
- Pillow

安装依赖：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install PyMuPDF Pillow
```

## 配置

运行前需要在 `5.extract_sources.py` 顶部配置工作目录和输入文件：

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

提高 DPI 可以得到更清晰、尺寸更大的裁剪图，但会增加内存占用和运行时间。

如果需要自定义输出名称，请修改面板映射和表格信息：

```python
FIG1_ORDER_MAP = {...}
FIG2_LEGEND_MAP = {...}
FIG3_ORDER_MAP = {...}
TABLE_INFO = (...)
```

映射值的格式为：

```python
JSON中的顺序编号: ("面板编号", "内容描述")
```

例如：

```python
5: ("A", "performance_curve")
```

## 运行

```bash
python 5.extract_sources.py
```

程序会依次输出：

- PDF、JSON 和输出目录路径。
- JSON 与 PDF 页数。
- 识别到的目标数量。
- 每张已保存图片的文件名和关联文本。
- 最终保存的图片总数。

## 提取规则

脚本按照以下规则识别目标：

- `chart`：作为子图叶子节点提取。
- `image`：仅在内部不包含 `figuregroup` 时作为整图提取。
- `figuregroup`：作为子图容器，本身不直接导出。
- `group`：用于关联内部图片、caption 和 footnote，本身不导出。
- 没有 `bbox` 的节点不会提取。
- 归一化宽度或高度小于 `0.005` 的节点会被过滤。
- 超出页面范围的坐标会被限制在有效图像边界内。
- 空裁剪结果会被跳过。

## 输出文件

当面板编号和描述都存在时，图片采用以下名称：

```text
{panel_id}_{description}.png
```

对应的元数据文件为：

```text
{panel_id}_{description}_meta.json
```

如果没有配置面板编号，脚本会使用图号、页码、元素顺序和类型生成备用文件名。

输出目录中还会生成：

```text
extraction_index.json
```

该文件是所有单图元数据组成的 JSON 数组，可用于批量检索或后续数据处理。

## 元数据字段

| 字段 | 说明 |
|---|---|
| `page` | PDF 页码，从 1 开始 |
| `order` | 元素在 JSON 中的嵌套顺序标识 |
| `type` | 提取目标类型，如 `chart` 或 `image` |
| `panel_id` | 面板编号或表格编号 |
| `description` | 图表内容描述 |
| `figure_label` | 关联的图表标题 |
| `bbox_norm` | 归一化裁剪坐标 `x1`、`y1`、`x2`、`y2` |
| `caption` | 关联的 caption |
| `footnote` | 当前实现保存的 caption 与 footnote 组合文本 |
| `context` | 当前实现合并后的 footnote 文本 |
| `image_size_px` | 输出图片尺寸 `[宽, 高]` |
| `pdf_size` | JSON 中记录的页面尺寸 |

> 当前代码中 `build_text()` 的返回值接收顺序使 `footnote` 和 `context` 的实际内容与通常的字段含义不同。如需严格区分 caption、footnote 和完整上下文，应调整 `collect_targets()` 中的赋值顺序。

## 核心函数

### `sanitize_filename()`

移除文件名中的非法字符、合并重复下划线，并限制文件名长度。

### `render_pdf_to_images()`

按指定 DPI 渲染 PDF 的全部页面，并转换为 RGB 格式的 PIL Image。

### `crop_subimage()`

将 JSON 中的归一化坐标转换为像素坐标，执行边界检查后裁剪图片。

### `collect_targets()`

遍历单页 JSON 结构，关联 caption 与 footnote，并收集所有符合规则的图表节点。

### `main()`

检查输入、加载 JSON、渲染 PDF、收集目标、保存图片与元数据，并生成总索引。

## 使用限制

- 输入路径和输出路径目前通过代码变量配置，尚未提供命令行参数。
- 面板编号和描述依赖手工维护的映射表。
- 页码和元素 `order` 发生变化后，需要同步更新映射。
- 当前独立 `image` 使用统一的 `TABLE_INFO`，处理多个不同整图时需要扩展命名逻辑。
- 相同文件名会覆盖已有结果，旧的多余文件不会自动删除。
- OCR 或上游解析产生的文本错误会原样写入元数据。
