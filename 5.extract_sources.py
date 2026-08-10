"""
从 PDF 文献中根据 JSON 位置信息提取子图

功能：
1. 加载 PDF 并用 PyMuPDF 将每页渲染为 PIL Image
2. 遍历 JSON 中的嵌套 items，收集叶子节点（chart / image）
3. 根据原文中的子图代号（A/B/C...）和曲线说明命名输出文件
4. caption/footnote 关联正确
5. 输出到新文件夹

提取规则：
- chart:        始终提取（叶子节点）
- image:        仅当内部没有 chart 子项时提取（整图，如 Table）
- figuregroup: 不提取（父级容器）
"""

import json
import re
import sys
import fitz
from pathlib import Path
from PIL import Image


# ========== 配置路径 ==========
WORK_DIR = Path("/Users/shunhao/Downloads/231（紧急程度）/2.改脚本功能")
PDF_PATH = WORK_DIR / "2.2018-joule-Measuring Aging Stability of Perovskite Solar Cells.pdf"
JSON_PATH = WORK_DIR / "4.connected-imagecaption.json"

pdf_stem = PDF_PATH.stem
OUT_DIR = WORK_DIR / f"{pdf_stem}_extracted_sources_v2"
OUT_DIR.mkdir(exist_ok=True)

# PyMuPDF 渲染 DPI
RENDER_DPI = 150


# ============================================================
# 子图名称映射：基于原文footnote和legend label
# 格式：(图号, 子图代号, 描述)
# ============================================================

# --- Figure 1 (PDF第2页) ---
# JSON figuregroup order → (代号, 描述)
# 通过 legend label + 空间位置确定
FIG1_ORDER_MAP = {
    # JSON order=5,  top-left, 无legend → 原文代号A
    5:  ("A", "JV_scan_forward_reverse"),
    # JSON order=11, legend='c' (OCR误读), 中右
    11: ("C", "JV_scan_forward_reverse"),
    # JSON order=14, 无legend, top-right
    14: ("B", "JV_scan_forward_reverse"),
    # JSON order=2,  legend='D',  左中
    2:  ("D", "stabilized_PCE"),
    # JSON order=8,  legend='E',  中
    8:  ("E", "stabilized_PCE"),
    # JSON order=18, legend='F',  右中
    18: ("F", "stabilized_PCE"),
    # JSON order=21, legend='G',  底部大图
    21: ("G", "MPP_tracking_PCE"),
}

# --- Figure 2 (PDF第3页) ---
# legend='A' → 原文A; legend='B' → 原文B
FIG2_LEGEND_MAP = {
    2: ("A", "aging_regular_mesoporous"),
    5: ("B", "aging_planar_inverted"),
}

# --- Figure 3 (PDF第4页) ---
# 按左到右顺序
FIG3_ORDER_MAP = {
    2: ("A", "schematic_regular_inverted"),
    4: ("B", "schematic_regular_inverted"),
}

# --- Table 1 (PDF第5页) ---
TABLE_INFO = ("Table1", "estimated_Tsso_MPP_traces")


def sanitize_filename(s: str, max_len: int = 50) -> str:
    """移除文件名中的非法字符并限制长度"""
    s = re.sub(r'[<>:"/\\|?*\n\r\t]', "_", s)
    s = re.sub(r"_{2,}", "_", s).strip(" _")
    if len(s) > max_len:
        s = s[:max_len]
    return s


def render_pdf_to_images(pdf_path: Path, dpi: int) -> list:
    """使用 PyMuPDF 将 PDF 每页渲染为 PIL RGB Image"""
    doc = fitz.open(str(pdf_path))
    images = []
    for page_num in range(len(doc)):
        page = doc[page_num]
        zoom = dpi / 72.0
        mat = fitz.Matrix(zoom, zoom)
        pixmap = page.get_pixmap(matrix=mat)
        img = Image.frombytes("RGB", [pixmap.width, pixmap.height], pixmap.samples)
        images.append((img, pixmap.width, pixmap.height))
    doc.close()
    return images


def crop_subimage(pil_img: Image.Image, bbox: dict,
                  pdf_w: int, pdf_h: int) -> Image.Image:
    """根据归一化 bbox 从渲染图上裁剪子图"""
    img_w, img_h = pil_img.size
    x1 = int(bbox["x1"] * img_w)
    y1 = int(bbox["y1"] * img_h)
    x2 = int(bbox["x2"] * img_w)
    y2 = int(bbox["y2"] * img_h)
    x1 = max(0, min(x1, img_w - 1))
    y1 = max(0, min(y1, img_h - 1))
    x2 = max(x1 + 1, min(x2, img_w))
    y2 = max(y1 + 1, min(y2, img_h))
    return pil_img.crop((x1, y1, x2, y2))


def collect_targets(page_items: list, page_idx: int) -> list:
    """
    处理一页，收集所有目标。

    返回 list of dict:
      - page_idx, type, bbox, page_size, legend, panel_id,
        description, figure_label, context, caption, footnote
    """
    results = []

    # 辅助函数：从 item 列表中收集 caption / footnote
    def collect_cf(items: list):
        cap, foots = "", []
        for it in items:
            t = it.get("type", "")
            if t == "imagecaption":
                cap = it.get("text", "")
            elif t == "imagefootnote":
                foots.append(it.get("text", ""))
        return cap, foots

    # 辅助函数：构建 context 和 footnote_text
    def build_text(cap: str, foots: list):
        ft = " ".join(foots)
        ctx = cap
        if ft:
            ctx = (ctx + " " + ft).strip()
        return ctx, ft

    # 遍历 page 顶层 items（可能是 group 或独立元素）
    for item in page_items:
        item_type = item.get("type", "")

        # ---- 处理 group ----
        if item_type == "group":
            group_items = item.get("items", [])
            # 先收集 group 内的 caption/footnote（Table 页的 caption 在这里）
            caption, footnotes = collect_cf(group_items)
            footnote_text, context = build_text(caption, footnotes)

            for sub in group_items:
                sub_type = sub.get("type", "")
                sub_order = str(sub.get("order", ""))
                sub_items = sub.get("items", [])

                # ---- image: 可能含 figuregroup，也可能是独立整图 ----
                if sub_type == "image":
                    has_fg = any(
                        child.get("type") == "figuregroup"
                        for child in sub_items
                    )

                    if has_fg:
                        # 含 figuregroup → 处理每个子图
                        for fg in sub_items:
                            if fg.get("type") != "figuregroup":
                                continue
                            fg_order = fg.get("order", "")
                            page_size = fg.get("page_size", [1206, 1566])

                            for child in fg.get("items", []):
                                if child.get("type") != "chart":
                                    continue
                                bbox = child.get("bbox")
                                if not bbox:
                                    continue

                                panel_id, desc = "", ""
                                if page_idx == 1:
                                    info = FIG1_ORDER_MAP.get(int(fg_order), None)
                                    if info:
                                        panel_id, desc = info
                                elif page_idx == 2:
                                    info = FIG2_LEGEND_MAP.get(int(fg_order), None)
                                    if info:
                                        panel_id, desc = info
                                elif page_idx == 3:
                                    info = FIG3_ORDER_MAP.get(int(fg_order), None)
                                    if info:
                                        panel_id, desc = info

                                results.append({
                                    "page_idx": page_idx,
                                    "type": "chart",
                                    "order": f"{sub_order}_{fg_order}",
                                    "bbox": bbox,
                                    "page_size": page_size,
                                    "panel_id": panel_id,
                                    "description": desc,
                                    "figure_label": caption,
                                    "context": context,
                                    "caption": caption,
                                    "footnote": footnote_text,
                                })

                    else:
                        # 无 figuregroup 的独立 image → Table 等整图
                        bbox = sub.get("bbox")
                        if bbox:
                            results.append({
                                "page_idx": page_idx,
                                "type": "image",
                                "order": sub_order,
                                "bbox": bbox,
                                "page_size": sub.get("page_size", [1206, 1566]),
                                "panel_id": TABLE_INFO[0],
                                "description": TABLE_INFO[1],
                                "figure_label": caption,
                                "context": context,
                                "caption": caption,
                                "footnote": footnote_text,
                            })

                # ---- 独立 imagecaption / imagefootnote ----
                # （已在 group 层级统一处理，无需额外操作）

    return results


def main():
    # ---------- 1. 检查文件 ----------
    if not PDF_PATH.exists():
        print(f"错误：找不到 PDF 文件\n  {PDF_PATH}")
        sys.exit(1)
    if not JSON_PATH.exists():
        print(f"错误：找不到 JSON 文件\n  {JSON_PATH}")
        sys.exit(1)

    # ---------- 2. 加载 JSON ----------
    with open(JSON_PATH, "r", encoding="utf-8") as f:
        pages = json.load(f)

    print(f"PDF 路径: {PDF_PATH}")
    print(f"JSON 路径: {JSON_PATH}")
    print(f"输出目录: {OUT_DIR}")
    print(f"JSON 共 {len(pages)} 页\n")

    # ---------- 3. 渲染 PDF ----------
    print(f"正在渲染 PDF @ {RENDER_DPI} DPI（可能需要几秒）...")
    pdf_images = render_pdf_to_images(PDF_PATH, RENDER_DPI)
    print(f"PDF 共 {len(pdf_images)} 页，已渲染为图像\n")

    # ---------- 4. 遍历所有页面，收集目标 ----------
    all_targets = []
    for page_idx, page_items in enumerate(pages):
        if page_idx >= len(pdf_images):
            break
        targets = collect_targets(page_items, page_idx)
        all_targets.extend(targets)

    print(f"共找到 {len(all_targets)} 个目标\n")

    # ---------- 5. 逐个裁剪并保存 ----------
    saved_count = 0
    metadata_list = []

    for target in all_targets:
        page_idx = target["page_idx"]
        item_type = target["type"]
        order_str = target["order"]
        bbox = target["bbox"]
        page_size = target["page_size"]
        panel_id = target["panel_id"]
        desc = target["description"]
        figure_label = target["figure_label"]
        context = target["context"]

        pdf_h, pdf_w = page_size[0], page_size[1]

        # 跳过面积过小的区域
        w_norm = bbox["x2"] - bbox["x1"]
        h_norm = bbox["y2"] - bbox["y1"]
        if w_norm < 0.005 or h_norm < 0.005:
            continue

        img_pil, _, _ = pdf_images[page_idx]
        sub_img = crop_subimage(img_pil, bbox, pdf_w, pdf_h)

        if sub_img.size[0] == 0 or sub_img.size[1] == 0:
            print(f"  ⚠ [p{page_idx + 1}] order={order_str} 裁剪结果为空，跳过")
            continue

        # 提取图号（从 figure_label 中提取 "Figure X" 或 "Table X"）
        fig_num = ""
        fl = figure_label.strip()
        if fl.startswith("Figure") or fl.startswith("Table"):
            # 取 "Figure 1" 或 "Table 1" 部分
            m = re.match(r"(Figure\s*\d+|Table\s*\d+)", fl)
            if m:
                fig_num = m.group(1).replace(" ", "")

        # 生成文件名：Fig1A_JV_scan_forward_reverse.png
        # panel_id 可能是 "A","B",... 或 "Table1"
        if panel_id and desc:
            filename_img = f"{panel_id}_{desc}.png"
        elif panel_id:
            filename_img = f"{panel_id}.png"
        elif fig_num:
            filename_img = f"{fig_num}_p{page_idx + 1}_{order_str}.png"
        else:
            filename_img = f"p{page_idx + 1}_{order_str}_{item_type}.png"

        filename_meta = filename_img.replace(".png", "_meta.json")

        save_path_img = OUT_DIR / filename_img
        save_path_meta = OUT_DIR / filename_meta

        sub_img.save(save_path_img, "PNG")

        meta = {
            "page": page_idx + 1,
            "order": order_str,
            "type": item_type,
            "panel_id": panel_id,
            "description": desc,
            "figure_label": figure_label,
            "bbox_norm": {
                "x1": round(bbox["x1"], 6),
                "y1": round(bbox["y1"], 6),
                "x2": round(bbox["x2"], 6),
                "y2": round(bbox["y2"], 6),
            },
            "caption": target["caption"],
            "footnote": target["footnote"],
            "context": context,
            "image_size_px": list(sub_img.size),
            "pdf_size": [pdf_h, pdf_w],
        }
        with open(save_path_meta, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)

        print(f"  [p{page_idx + 1}] {filename_img}")
        if figure_label:
            print(f"           {figure_label[:80]}{'...' if len(figure_label) > 80 else ''}")
        if context:
            print(f"           context: {context[:80]}{'...' if len(context) > 80 else ''}")

        saved_count += 1
        metadata_list.append(meta)

    # ---------- 6. 保存总体索引 ----------
    index_path = OUT_DIR / "extraction_index.json"
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(metadata_list, f, ensure_ascii=False, indent=2)

    print(f"\n完成！共保存 {saved_count} 张子图到：\n  {OUT_DIR}")


if __name__ == "__main__":
    main()
