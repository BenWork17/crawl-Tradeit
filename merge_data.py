#!/usr/bin/env python3
"""Merge crawled JSON pages (``data/<n>.json``) into a single CSV file.

Reads every ``*.json`` in the data directory, flattens (possibly nested) records,
unions all columns and writes one CSV. Uses only the standard library.

Examples:
    python merge_data.py
    python merge_data.py --output buyers.csv --dedupe
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import re
import sys
from pathlib import Path
from typing import Any, Optional

DATA_DIR = Path("data")
DEFAULT_OUTPUT = Path("data.csv")

logger = logging.getLogger("merge_data")


def setup_logging() -> None:
    """Configure console logging with UTF-8 output (Windows-friendly)."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        except (AttributeError, ValueError):
            pass
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
    )


def page_number(path: Path) -> int:
    """Return the numeric page of a file like ``12.json`` (large number if none)."""
    match = re.match(r"^(\d+)\.json$", path.name)
    return int(match.group(1)) if match else 10**9


def flatten(obj: Any, parent: str = "", out: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    """Flatten a nested dict into safe keys; join scalar lists with `` | ``."""
    if out is None:
        out = {}
    if isinstance(obj, dict):
        for key, value in obj.items():
            name = f"{parent}__{key}" if parent else str(key)
            flatten(value, name, out)
    elif isinstance(obj, (list, tuple)):
        if all(not isinstance(x, (dict, list, tuple)) for x in obj):
            out[parent] = " | ".join("" if x is None else str(x) for x in obj)
        else:
            out[parent] = json.dumps(obj, ensure_ascii=False)
    else:
        out[parent] = obj
    return out


def load_records(data_dir: Path) -> list[tuple[int, dict[str, Any]]]:
    """Load and flatten records from all ``<page>.json`` files, sorted by page."""
    if not data_dir.is_dir():
        raise SystemExit(f"Không tìm thấy thư mục: {data_dir}")

    files = sorted(data_dir.glob("*.json"), key=page_number)
    if not files:
        raise SystemExit(f"Không có file .json trong: {data_dir}")

    records: list[tuple[int, dict[str, Any]]] = []
    for path in files:
        page = page_number(path)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Bỏ qua %s (%s)", path.name, exc)
            continue
        if not isinstance(payload, list):
            logger.warning("Bỏ qua %s (không phải mảng records).", path.name)
            continue
        for item in payload:
            if isinstance(item, dict):
                records.append((page, flatten(item)))
            else:
                records.append((page, {"value": item}))
        logger.info("Đọc %s: %s records", path.name, len(payload))
    return records


def write_csv(
    records: list[tuple[int, dict[str, Any]]],
    output: Path,
    dedupe: bool,
    encoding: str,
) -> tuple[int, int]:
    """Write ``records`` to CSV. Returns (written, skipped_duplicates)."""
    columns: dict[str, None] = {"_source_page": None}
    for _, record in records:
        for key in record:
            columns.setdefault(key, None)
    fieldnames = list(columns)

    seen: set[str] = set()
    written = 0
    skipped = 0

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding=encoding, newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, restval="", delimiter=".")
        writer.writeheader()
        for page, record in records:
            row = dict(record)
            row["_source_page"] = page
            if dedupe:
                fingerprint = json.dumps(row, ensure_ascii=False, sort_keys=True)
                if fingerprint in seen:
                    skipped += 1
                    continue
                seen.add(fingerprint)
            writer.writerow(row)
            written += 1
    return written, skipped


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Gộp data/<n>.json thành 1 file CSV")
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--dedupe", action="store_true", help="Loại bỏ dòng trùng hoàn toàn")
    parser.add_argument("--encoding", default="utf-8-sig", help="Encoding file CSV")
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    """Entry point: load all pages, flatten, and export a single CSV."""
    setup_logging()
    args = parse_args(argv)

    records = load_records(args.data_dir)
    if not records:
        logger.warning("Không có records nào để ghi.")
        return 1

    written, skipped = write_csv(records, args.output, args.dedupe, args.encoding)
    logger.info(
        "Đã ghi %s records vào %s (bỏ qua %s dòng trùng).",
        written,
        args.output,
        skipped,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
