# Example output

The tool was developed on *Measuring Aging Stability of Perovskite Solar Cells* (Joule, 2018). The article PDF, its page-structure JSON and the cropped figures belong to the publisher and are not redistributed here.

`metadata/` keeps the per-figure records that the extractor produced for that article, with the caption and footnote text removed: page number, panel ID, element type, figure label, normalized bounding box and image size. They show the output format.

To reproduce the full output, obtain the article PDF and a page-structure JSON for it, set `PDF_PATH` and `JSON_PATH` in `extract_sources.py`, and run the script. Captions, footnotes, cropped PNGs and `extraction_index.json` are then written locally.
