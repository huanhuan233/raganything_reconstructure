"""
Subprocess entrypoint for DeepSeek OCR2 parsing.

Run inside the DeepSeek-OCR2 conda environment, while RAGAnything stays in raga:

  DEEPSEEK_OCR2_PYTHON=/path/to/ocr2/bin/python PARSER=deepseek_ocr2 ...

Parent sets RAGANYTHING_DEEPSEEK_WORKER=1 and unsets DEEPSEEK_OCR2_PYTHON in the child env
so this worker always runs in-process inference.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="DeepSeek OCR2 worker (subprocess)")
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--pdf", type=str, help="Path to PDF")
    g.add_argument("--image", type=str, help="Path to image")
    parser.add_argument("--out-json", type=str, required=True, help="Output JSON path")
    args = parser.parse_args()

    from third_party.raganything.parser import DeepseekOCR2Parser

    p = DeepseekOCR2Parser()
    if args.pdf:
        content_list = p.parse_pdf(Path(args.pdf))
    else:
        content_list = p.parse_image(Path(args.image))

    out_path = Path(args.out_json)
    out_path.write_text(
        json.dumps(content_list, ensure_ascii=False, indent=0),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
