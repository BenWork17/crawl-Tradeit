"""Small web dashboard for running the TradeIT crawler."""

from __future__ import annotations

import json
import os
import re
import shutil
import traceback
import threading
import time
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Any

import requests
from flask import Flask, jsonify, redirect, render_template, request, send_file, url_for
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill

import accounts_store
import dataset_store
import merge_data
import regions
import tradeit_crawler as crawler


app = Flask(__name__)
# Reentrant on purpose: several helpers read or update ``job`` while holding
# this lock, and a caller that already holds it must not deadlock the request.
# The rule is still "hold it briefly, never around rendering or I/O", but making
# the lock reentrant means a future nested call degrades in cost, not in a hang.
job_lock = threading.RLock()
# Held for the whole "claim the crawl slot" sequence in /api/jobs, which the
# short-lived job_lock cannot cover (the check and the status assignment are
# separated by Excel parsing and dataset setup). Non-blocking: a second
# simultaneous submit gets the 409 page immediately instead of queueing.
start_lock = threading.Lock()
# Every stored path is anchored to this file's directory. Using bare relative
# paths broke `send_file`, which resolves against the Flask root while
# `Path.open` resolves against the process CWD (so exports 500'd whenever the
# app was started from another working directory).
BASE_DIR = Path(__file__).resolve().parent

# ``TRADEIT_DATA_DIR`` is shared with accounts_store (which uses it for
# accounts.json), so one mount point can hold both the account list and the
# crawl output. They occupy different paths under it, so the two never collide.
DATA_DIR_ENV = "TRADEIT_DATA_DIR"


def _resolve_data_root() -> Path:
    """Where crawl output lives: ``TRADEIT_DATA_DIR`` if set, else the project.

    Render (and any container host) wipes the container filesystem on every
    redeploy and, on free instances, every time the service spins down. Crawled
    pages, per-dataset ``state.json`` and the .xlsx export are written to
    ``DATA_ROOT``, so pointing ``TRADEIT_DATA_DIR`` at a persistent disk mount
    (e.g. ``/var/data``) is what keeps them alive. Unset -- the local default --
    resolves to the project directory, so behaviour is byte-for-byte unchanged.

    A relative value is anchored at the project root rather than the process
    CWD, for the same reason as ``BASE_DIR`` above.
    """
    raw = os.environ.get(DATA_DIR_ENV, "").strip()
    if not raw:
        return BASE_DIR
    root = Path(raw).expanduser()
    if not root.is_absolute():
        root = BASE_DIR / root
    return root


# ``TRADEIT_DATA_DIR`` is shared with accounts_store (which uses it for
# accounts.json), so one mount point can hold both the account list and the
# crawl output. They occupy different paths under it, so the two never collide.
DATA_DIR_ENV = "TRADEIT_DATA_DIR"
DATA_ROOT = _resolve_data_root()
LEGACY_DATA_DIR = DATA_ROOT / "data"
LEGACY_STATE_FILE = DATA_ROOT / "state.json"
DATASETS_ROOT = DATA_ROOT / "datasets"
LEGACY_DATASET_NAME = "legacy"
ACTIVE_THEME_KEY = "tradeit-theme"
job: dict[str, Any] = {
    "run_id": 0,
    "status": "idle",
    "message": "Sẵn sàng",
    "page": 0,
    "records": 0,
    "total": None,
    "account_index": 0,
    "account_total": 0,
    "account_label": "",
    "dataset_name": LEGACY_DATASET_NAME,
    "query_label": "",
    "started_at": None,
    # Credit-exhaustion counters. Secret-free by construction: they are counts
    # and positions only (never a token), taken from accounts_store.CreditTracker
    # so /api/status can tell the UI "2/3 accounts out of credit" without
    # exposing a single credential.
    "credit_total": 0,
    "credit_exhausted": 0,
    "credit_label": "",
    "credit_status": accounts_store.EXHAUSTION_UNKNOWN,
    "credit_message": "",
    # Where this run's accounts came from: "upload", "stored", or "" (no run).
    "accounts_source": "",
}
stop_event = threading.Event()
ALLOWED_ACCOUNT_EXTENSIONS = {".xlsx", ".xlsm", ".xltx", ".xltm"}


def _page_path(raw_page: str) -> Path:
    try:
        page = int(raw_page)
    except (TypeError, ValueError) as exc:
        raise ValueError("Số trang không hợp lệ") from exc
    if page < 1:
        raise ValueError("Số trang phải lớn hơn 0")
    return crawler.page_file_path(page)


def _read_page(page: int) -> list[Any]:
    path = _page_path(str(page))
    if not path.is_file():
        raise FileNotFoundError(f"Không tìm thấy file trang {page}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"File trang {page} không chứa một mảng dữ liệu")
    return payload


def _dataset_page_path(dataset: str, page: int) -> Path:
    if page < 1:
        raise ValueError("Số trang phải lớn hơn 0")
    return _dataset_data_dir(dataset) / f"{page}.json"


def _read_page_in_dataset(dataset: str, page: int) -> list[Any]:
    path = _dataset_page_path(dataset, page)
    if not path.is_file():
        raise FileNotFoundError(f"Không tìm thấy file trang {page}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"File trang {page} không chứa một mảng dữ liệu")
    return payload


def _write_xlsx(
    records: list[tuple[int, dict[str, Any]]],
    output: Path,
) -> tuple[int, int]:
    """Write flattened records to an Excel file on disk."""
    buffer = _xlsx_buffer(records)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(buffer.getvalue())
    return buffer.written, buffer.skipped


class _XlsxBuffer(BytesIO):
    """A BytesIO that carries the written/skipped counters of one workbook."""

    def __init__(self) -> None:
        super().__init__()
        self.written = 0
        self.skipped = 0


def _xlsx_buffer(records: list[tuple[int, dict[str, Any]]]) -> _XlsxBuffer:
    """Build an .xlsx workbook in memory, preserving text values.

    Used by both the on-disk export and the "download dataset" button, so the
    two produce byte-identical workbooks.
    """
    columns: dict[str, None] = {"_source_page": None}
    for _, record in records:
        for key in record:
            columns.setdefault(key, None)
    fieldnames = list(columns)

    seen: set[str] = set()
    written = 0
    skipped = 0
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "buyers"

    header_fill = PatternFill("solid", fgColor="0F766E")
    header_font = Font(color="FFFFFF", bold=True)
    for column_index, fieldname in enumerate(fieldnames, start=1):
        cell = sheet.cell(row=1, column=column_index, value=fieldname)
        cell.fill = header_fill
        cell.font = header_font

    for page, record in records:
        row = dict(record)
        row["_source_page"] = page
        fingerprint = json.dumps(row, ensure_ascii=False, sort_keys=True, default=str)
        if fingerprint in seen:
            skipped += 1
            continue
        seen.add(fingerprint)
        for column_index, fieldname in enumerate(fieldnames, start=1):
            value = row.get(fieldname, "")
            if value is None:
                value = ""
            elif not isinstance(value, str):
                value = str(value)
            cell = sheet.cell(row=written + 2, column=column_index, value=value)
            cell.number_format = "@"
        written += 1

    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions
    for column_cells in sheet.columns:
        max_length = max(len(str(cell.value or "")) for cell in column_cells)
        sheet.column_dimensions[column_cells[0].column_letter].width = min(
            max(max_length + 2, 12), 42
        )

    buffer = _XlsxBuffer()
    workbook.save(buffer)
    workbook.close()
    buffer.seek(0)
    buffer.written = written
    buffer.skipped = skipped
    return buffer


def _clean_name(name: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_-]+", "_", name.strip()).strip("_-")
    if not slug:
        raise ValueError("Tên bộ dữ liệu không hợp lệ")
    return slug.lower()


def _dataset_dir(name: str) -> Path:
    if name == LEGACY_DATASET_NAME:
        return DATA_ROOT
    return DATASETS_ROOT / _clean_name(name)


def _dataset_data_dir(name: str) -> Path:
    if name == LEGACY_DATASET_NAME:
        return LEGACY_DATA_DIR
    return _dataset_dir(name) / "data"


def _dataset_state_file(name: str) -> Path:
    if name == LEGACY_DATASET_NAME:
        return LEGACY_STATE_FILE
    return _dataset_dir(name) / "state.json"


def _dataset_csv_file(name: str) -> Path:
    if name == LEGACY_DATASET_NAME:
        return DATA_ROOT / "data.csv"
    return _dataset_dir(name) / "data.csv"


def _dataset_display_name(name: str) -> str:
    if name == LEGACY_DATASET_NAME:
        return "Mặc định (legacy)"
    return name


def _dataset_exists(name: str) -> bool:
    data_dir = _dataset_data_dir(name)
    return data_dir.is_dir() and any(data_dir.glob("*.json"))


def _list_datasets() -> list[dict[str, Any]]:
    names = [LEGACY_DATASET_NAME]
    if DATASETS_ROOT.is_dir():
        for path in DATASETS_ROOT.iterdir():
            if path.is_dir():
                names.append(path.name)
    unique = []
    seen = set()
    for name in names:
        if name in seen:
            continue
        seen.add(name)
        data_dir = _dataset_data_dir(name)
        unique.append(
            {
                "name": name,
                "label": _dataset_display_name(name),
                "files": len(list(data_dir.glob("*.json"))) if data_dir.is_dir() else 0,
            }
        )
    return unique


def _default_dataset_name(region_codes: list[str], hs_code: str) -> str:
    """Build a dataset name from the actual query, e.g. ``nl-vn_090411``."""
    region_part = "-".join(code.lower() for code in region_codes) or "world"
    return _clean_name(f"{region_part}_{hs_code}")


def _clean_dataset_name(name: str) -> str:
    """Validate a dataset name without touching the filesystem."""
    return LEGACY_DATASET_NAME if name == LEGACY_DATASET_NAME else _clean_name(name)


def _require_dataset(name: str) -> str:
    """Validate a dataset name and fail when that dataset does not exist.

    Read-only routes must not call ``_ensure_dataset``: it creates folders, so a
    mistyped name would silently produce an empty dataset instead of an error.
    """
    dataset = _clean_dataset_name(name)
    if dataset == LEGACY_DATASET_NAME or _dataset_dir(dataset).is_dir():
        return dataset
    raise FileNotFoundError(f"Không tìm thấy bộ dữ liệu '{dataset}'")


def _ensure_dataset(name: str) -> str:
    dataset = _clean_dataset_name(name)
    if dataset != LEGACY_DATASET_NAME:
        _dataset_data_dir(dataset).mkdir(parents=True, exist_ok=True)
    return dataset


def _dataset_page_files(name: str) -> list[Path]:
    """Return the ``<page>.json`` files of a dataset, ordered by page number."""
    data_dir = _dataset_data_dir(name)
    if not data_dir.is_dir():
        return []
    pages = [path for path in data_dir.glob("*.json") if merge_data.page_number(path) < 10**9]
    return sorted(pages, key=merge_data.page_number)


def _restore_dataset_if_empty(name: str) -> None:
    """Pull a dataset back from Supabase Storage when the disk has none of it.

    On Render's free plan the container filesystem is wiped on every redeploy,
    so a dataset the dashboard lists can have no local files at all. This is
    best-effort: a Storage failure leaves the empty local state alone and the
    caller reports it, rather than raising into a page render.
    """
    if not dataset_store.configured():
        return
    if _dataset_page_files(name):
        return
    try:
        dataset_store.download_dataset(
            name, _dataset_data_dir(name), _dataset_state_file(name)
        )
    except Exception as exc:  # noqa: BLE001 - never break a read path
        print(f"[WARN] Không khôi phục được '{name}' từ Supabase Storage: {exc}")


def _dataset_summary(name: str) -> dict[str, Any]:
    """Build the record/files/size summary shown in the dataset dialog."""
    files: list[dict[str, Any]] = []
    total_records = 0
    total_bytes = 0
    for path in _dataset_page_files(name):
        page = merge_data.page_number(path)
        try:
            payload = _read_page_in_dataset(name, page)
            count = len(payload)
            columns: set[str] = set()
            for item in payload:
                if isinstance(item, dict):
                    columns.update(merge_data.flatten(item))
        except (OSError, ValueError, json.JSONDecodeError):
            count = 0
            columns = set()
        size = path.stat().st_size
        total_records += count
        total_bytes += size
        files.append(
            {
                "page": page,
                "name": path.name,
                "records": count,
                "size": size,
                "columns": len(columns),
                "updated_at": path.stat().st_mtime,
            }
        )

    state = {}
    query = _dataset_query(name)
    if query is not None:
        state["query"] = query
    state_file = _dataset_state_file(name)
    if state_file.is_file():
        try:
            saved = json.loads(state_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            saved = {}
        if isinstance(saved, dict):
            for key in ("curPage", "total", "crawled", "updatedAt"):
                if key in saved:
                    state[key] = saved[key]

    return {
        "name": name,
        "label": _dataset_display_name(name),
        "legacy": name == LEGACY_DATASET_NAME,
        "files": files,
        "file_count": len(files),
        "records": total_records,
        "size": total_bytes,
        "state": state,
    }


def _dataset_matches(dataset: str, name: str) -> bool:
    """True when two user-supplied dataset names point at the same folder."""
    try:
        return _clean_name(dataset) == _clean_name(name)
    except ValueError:
        return dataset == name


def _assert_dataset_idle(name: str) -> None:
    """Refuse to delete a dataset that the running crawl is still writing to."""
    with job_lock:
        running = job.get("status") == "running"
        current = str(job.get("dataset_name", ""))
    if running and _dataset_matches(current, name):
        raise ValueError(
            "Bộ dữ liệu này đang được crawl. Hãy dừng job rồi mới xóa."
        )


def _delete_dataset(name: str) -> dict[str, Any]:
    """Delete the crawled pages (and state) of one dataset.

    ``legacy`` maps to the repository's ``data/`` folder and ``state.json``, so
    only those files are removed; every other dataset loses its whole folder.
    """
    _assert_dataset_idle(name)
    summary = _dataset_summary(name)

    if name == LEGACY_DATASET_NAME:
        removed_files = 0
        for path in _dataset_page_files(name):
            path.unlink()
            removed_files += 1
        # ``data.csv`` is a user export (and tracked by git), not crawl output:
        # deleting the dataset must not throw that merge away.
        if LEGACY_STATE_FILE.is_file():
            LEGACY_STATE_FILE.unlink()
    else:
        removed_files = summary["file_count"]
        target = _dataset_dir(name)
        if target.is_dir():
            shutil.rmtree(target)
        # Keep the dataset list honest: an empty folder is not a dataset.
        if DATASETS_ROOT.is_dir() and not any(DATASETS_ROOT.iterdir()):
            DATASETS_ROOT.rmdir()

    # The job panel would otherwise keep pointing at a folder that no longer
    # exists, so falls back to the always-present default dataset.
    with job_lock:
        if _dataset_matches(str(job.get("dataset_name", "")), name):
            job["dataset_name"] = LEGACY_DATASET_NAME

    return {
        "name": name,
        "label": _dataset_display_name(name),
        "removed_files": removed_files,
        "removed_records": summary["records"],
        "message": (
            f"Đã xóa bộ dữ liệu '{_dataset_display_name(name)}' "
            f"({removed_files} file, {summary['records']} bản ghi)."
        ),
    }


def _zip_dataset(name: str) -> BytesIO:
    """Pack every page file of a dataset (plus ``data.csv``) into a ZIP buffer."""
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in _dataset_page_files(name):
            archive.write(path, arcname=f"data/{path.name}")
        csv_file = _dataset_csv_file(name)
        if csv_file.is_file():
            archive.write(csv_file, arcname=csv_file.name)
        state_file = _dataset_state_file(name)
        if state_file.is_file() and name != LEGACY_DATASET_NAME:
            archive.write(state_file, arcname="state.json")
    buffer.seek(0)
    return buffer


def _set_crawler_paths(name: str) -> str:
    dataset = _ensure_dataset(name)
    crawler.DATA_DIR = _dataset_data_dir(dataset)
    crawler.STATE_FILE = _dataset_state_file(dataset)
    return dataset


def _parse_region_selection(form: Any) -> list[str]:
    """Read the importing countries the user picked in the region list.

    The UI posts ``region_codes`` (possibly several values). These become the
    ``destiCountryCode`` request field. When the user picked nothing we refuse
    instead of falling back to a hardcoded country.
    """
    raw: list[str] = [str(value) for value in form.getlist("region_codes")]

    free_text = str(form.get("region_text", "") or "").strip()
    if free_text:
        raw.append(free_text)

    legacy = str(form.get("importer", "") or "").strip()
    if legacy:
        # Backwards compatibility with the old ``Importer`` field, but it is now
        # honoured instead of being ignored.
        raw.append(legacy)

    cleaned = [value for value in raw if str(value).strip()]
    if not cleaned:
        raise regions.RegionError(
            "Vui lòng chọn ít nhất một quốc gia/vùng nhập hàng."
        )

    codes, unknown = regions.resolve_region_codes(cleaned)
    if unknown:
        raise regions.RegionError(
            "Không nhận diện được quốc gia/vùng: " + ", ".join(unknown[:5])
        )
    return codes


def _resolve_dataset_from_request(form: Any, body: dict[str, Any]) -> str:
    """Pick the dataset to write into.

    Only an explicitly chosen dataset (the ``__explicit__`` flag set by the
    picker) is used as-is. Otherwise the name is derived from the real query
    (countries + HS code), so a new search never lands in an old folder by
    accident -- which previously made the dashboard show stale results.
    """
    explicit = str(form.get("dataset_explicit", "") or "").strip() == "1"
    dataset_name = str(form.get("dataset_name", "") or "").strip()

    if explicit and dataset_name and dataset_name != "__custom__":
        return dataset_name

    codes = regions.parse_destination_codes(body.get("destiCountryCode", ""))
    hs_code = str(body.get("hsCode") or "")
    return _default_dataset_name(codes, hs_code)


def _fingerprint(item: Any) -> str:
    if isinstance(item, dict):
        normalized = merge_data.flatten(item)
    else:
        normalized = {"value": item}
    return json.dumps(normalized, ensure_ascii=False, sort_keys=True)


def _load_seen_fingerprints() -> set[str]:
    seen: set[str] = set()
    if not crawler.DATA_DIR.is_dir():
        return seen
    for path in crawler.DATA_DIR.glob("*.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, list):
            continue
        for item in payload:
            seen.add(_fingerprint(item))
    return seen


def _dataset_query(dataset: str) -> str | None:
    """Return the query fingerprint previously saved for a dataset."""
    state_file = _dataset_state_file(dataset)
    if not state_file.is_file():
        return None
    try:
        data = json.loads(state_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    query = data.get("query")
    return query if isinstance(query, str) else None


def _assert_dataset_matches_query(dataset: str, query: str, force: bool) -> None:
    """Refuse to mix pages crawled with a different query into one dataset.

    Without this check, crawling VN into a folder that already holds US pages
    would skip those pages as "already done" and silently show the old data.

    A folder that already contains pages but has no recorded query is treated as
    *unknown*, not as a match: older crawls (before the query was stored) must
    not be silently reused, otherwise a new search returns stale results.
    """
    if force:
        return
    if not _dataset_page_files(dataset):
        return

    previous = _dataset_query(dataset)
    if previous is None:
        raise ValueError(
            f"Bộ dữ liệu '{dataset}' đã có dữ liệu nhưng không rõ điều kiện tìm kiếm "
            f"(bản crawl cũ). Hãy chọn/tạo bộ dữ liệu mới, hoặc tick "
            f"'Crawl lại và ghi đè' để ghi đè lên dữ liệu cũ."
        )
    if previous != query:
        raise ValueError(
            f"Bộ dữ liệu '{dataset}' đã crawl với điều kiện khác ({previous}). "
            f"Hãy tạo bộ dữ liệu mới, hoặc tick 'Crawl lại và ghi đè' để dùng lại."
        )


def _dedupe_items(items: list[Any], seen: set[str]) -> tuple[list[Any], int]:
    unique: list[Any] = []
    skipped = 0
    for item in items:
        key = _fingerprint(item)
        if key in seen:
            skipped += 1
            continue
        seen.add(key)
        unique.append(item)
    return unique, skipped


def _cell_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _parse_accounts_excel(upload: Any) -> list[dict[str, str]]:
    """Parse an uploaded Excel file into token pairs.

    Expects the first sheet and two columns:
    - column A: token
    - column B: refresh token
    Header row is optional.
    """
    if upload is None or not getattr(upload, "filename", ""):
        raise ValueError("Vui lòng upload file Excel danh sách tài khoản")

    ext = Path(upload.filename).suffix.lower()
    if ext not in ALLOWED_ACCOUNT_EXTENSIONS:
        raise ValueError("Chỉ hỗ trợ file Excel .xlsx/.xlsm/.xltx/.xltm")

    workbook = load_workbook(upload.stream, read_only=True, data_only=True)
    sheet = workbook.worksheets[0]
    rows = sheet.iter_rows(values_only=True)

    try:
        first_row = next(rows)
    except StopIteration:
        workbook.close()
        raise ValueError("File Excel rỗng")

    header = [_cell_text(value).lower() for value in first_row[:4]]
    has_header = any("token" in value for value in header) and any(
        "refresh" in value or "rf" in value for value in header
    )

    if has_header:
        token_index = 0
        refresh_index = 1
        for idx, value in enumerate(header):
            if "token" in value and "refresh" not in value and "rf" not in value:
                token_index = idx
            if "refresh" in value or "rf" in value:
                refresh_index = idx
        data_rows = rows
    else:
        token_index = 0
        refresh_index = 1
        data_rows = iter([first_row, *rows])

    accounts: list[dict[str, str]] = []
    for row in data_rows:
        token = _cell_text(row[token_index] if len(row) > token_index else "")
        refresh = _cell_text(row[refresh_index] if len(row) > refresh_index else "")
        if token and refresh:
            accounts.append({"token": token, "refresh_token": refresh})

    workbook.close()
    return accounts


def _client_prefers_json() -> bool:
    """True only when the caller explicitly negotiated a JSON response.

    A browser submitting the crawl form advertises ``text/html`` first (with
    ``*/*;q=0.8`` as a fallback), so it always gets the dashboard back. API
    clients that ask for ``Accept: application/json`` keep the JSON error body.
    """
    accept = request.accept_mimetypes
    if accept["application/json"] <= 0:
        return False
    return accept.best == "application/json"


def _form_snapshot(form: Any) -> dict[str, Any]:
    """Copy the submitted crawl form so an error page keeps the user's input.

    Values are plain strings (plus the repeated ``region_codes`` list) so the
    template can echo them back without a second request. Nothing is filled in
    here: an empty field stays empty, because guessing a country or an HS code
    is exactly the bug this guards against.
    """

    def _text(name: str) -> str:
        return str(form.get(name, "") or "").strip()

    return {
        "hs_code": _text("hs_code"),
        "region_codes": [
            str(value).strip()
            for value in form.getlist("region_codes")
            if str(value).strip()
        ],
        "region_text": _text("region_text"),
        "importer": _text("importer"),
        "dataset_name": _text("dataset_name"),
        "dataset_explicit": _text("dataset_explicit"),
        "start_page": _text("start_page"),
        "end_page": _text("end_page"),
        "per_page": _text("per_page"),
        "delay": _text("delay"),
        "force": form.get("force") == "on",
    }


def _submitted_query_label(
    form_values: dict[str, Any], body: dict[str, Any] | None = None
) -> str:
    """Describe the query the user just submitted (never a defaulted one)."""
    if body is not None:
        return crawler.describe_body(body)

    raw_hs = str(form_values.get("hs_code") or "").strip() or "(chưa nhập)"
    raw_regions = list(form_values.get("region_codes") or [])
    for key in ("region_text", "importer"):
        value = str(form_values.get(key) or "").strip()
        if value:
            raw_regions.append(value)

    codes: list[str] = []
    for value in raw_regions:
        for piece in str(value).replace(";", ",").split(","):
            code = regions.normalize_country_code(piece)
            if code is not None and code not in codes:
                codes.append(code)
    if not codes:
        return f"HS {raw_hs} · chưa chọn quốc gia/vùng"
    # Same ordering as the request body so the label matches what was sent.
    ordered = [code for code in regions.all_country_codes() if code in codes]
    ordered += [code for code in codes if code not in ordered]
    labels = ", ".join(regions.country_label(code) for code in ordered)
    return f"HS {raw_hs} · {len(ordered)} nước nhập: {labels}"


def _render_dashboard_error(
    message: str,
    *,
    form_values: dict[str, Any] | None = None,
    status_code: int = 400,
    body: dict[str, Any] | None = None,
    dataset_name: str | None = None,
    mark_error: bool = True,
):
    """Re-render the dashboard for a rejected ``POST /api/jobs``.

    The crawl form is a normal browser navigation, so answering with raw JSON
    replaced the whole dashboard with ``{"error": ...}`` and read as "the crawl
    returned no result". The page is rendered again instead, carrying a visible
    error message and the values the user had just submitted so they can retry
    without retyping. JSON is only produced when the caller asked for it.

    ``mark_error`` also records the failure as the job's current state, so the
    dashboard's 2-second ``/api/status`` poll cannot blank the message a moment
    after it appeared. It is skipped when a crawl is actually in flight, because
    that job's status belongs to the running worker.
    """
    if _client_prefers_json():
        return jsonify({"error": message}), status_code

    query_label = None
    if form_values is not None:
        query_label = _submitted_query_label(form_values, body)

    with job_lock:
        persist = mark_error and job.get("status") not in {"running", "stopped"}
        if persist:
            job["status"] = "error"
            job["message"] = message
            if query_label is not None:
                job["query_label"] = query_label
            if dataset_name:
                job["dataset_name"] = dataset_name
        current = {key: value for key, value in job.items() if key != "stop_token"}
        current = dict(current)
    if not persist:
        # The rendered page still explains this attempt, it just does not
        # rewrite the state of a crawl that is running (or was stopped).
        current["message"] = message
        if query_label is not None:
            current["query_label"] = query_label
        if dataset_name:
            current["dataset_name"] = dataset_name
    return (
        render_template(
            "index.html",
            job=current,
            error=message,
            form_values=form_values or {},
        ),
        status_code,
    )


def _accounts_public_summary() -> dict[str, Any]:
    """Secret-free description of the stored account list.

    Built from ``accounts_store.summary()``, which reports count/timestamp/state
    and never a token, so this is safe to hand to the dashboard and to
    ``/api/status``. The on-disk ``path`` is deliberately dropped: the UI only
    needs to know *whether* accounts are stored, and a filesystem path is noise
    (it would also leak the deploy layout into a browser response).

    ``backend`` (``file`` / ``supabase`` / ``file-fallback``) is included because
    the dashboard shows where the accounts are kept and warns when a Supabase
    failure means the local file is only a temporary cache. ``fallback_reason``
    is included only when present; it is a fixed phrase or an HTTP status word
    from accounts_store, never a URL or key.
    """
    info = accounts_store.summary()
    summary: dict[str, Any] = {
        "count": int(info.get("count") or 0),
        "updated_at": info.get("updated_at"),
        "state": info.get("state"),
        "message": info.get("message"),
        "has_accounts": bool(info.get("has_accounts")),
        "needs_upload": bool(info.get("needs_upload")),
        "backend": info.get("backend"),
    }
    if info.get("fallback_reason"):
        summary["fallback_reason"] = info.get("fallback_reason")
    return summary


def _accounts_from_upload(upload: Any) -> list[dict[str, str]]:
    """Parse the uploaded Excel and remember it, replacing the stored set.

    Returns the accounts so the caller can start the run immediately. The
    stored copy is what makes the next crawl work without re-uploading, so the
    save happens here rather than only on a successful crawl.

    Raises:
        ValueError: The upload is missing/empty/unreadable. The message is safe
            to show in the dashboard (no token, no path, no traceback), so every
            rejection takes the normal 400 + re-render path instead of a 500.
    """
    try:
        accounts = _parse_accounts_excel(upload)
    except ValueError:
        raise
    except zipfile.BadZipFile as exc:
        # A renamed .txt/.csv, a truncated download or an .xls (old binary
        # format) all surface as this from openpyxl's zip layer.
        raise ValueError(
            "File tải lên không phải file Excel .xlsx hợp lệ "
            "(không đọc được cấu trúc zip). Hãy xuất lại file từ Excel."
        ) from exc
    except KeyError as exc:
        # openpyxl raises KeyError for a zip that lacks the expected xlsx parts.
        raise ValueError(
            "File Excel bị thiếu thành phần bên trong (có thể đã hỏng). "
            "Hãy xuất lại file và thử lại."
        ) from exc
    except (OSError, EOFError) as exc:
        raise ValueError(
            f"Không đọc được file Excel đã tải lên: {type(exc).__name__}"
        ) from exc
    except Exception as exc:  # noqa: BLE001 - openpyxl raises many shapes
        # Defence in depth: an unreadable upload must never become a 500 page.
        raise ValueError(
            f"Không đọc được file Excel đã tải lên ({type(exc).__name__}). "
            "Hãy kiểm tra lại file và thử lại."
        ) from exc
    if not accounts:
        raise ValueError("Không đọc được tài khoản nào từ file Excel")
    try:
        accounts_store.save(accounts)
    except (OSError, ValueError) as exc:
        # The crawl itself can still run with the in-memory accounts; only the
        # "remember this for next time" part failed. Say so without pretending
        # the run failed (and without echoing any token).
        print(f"[WARN] Không lưu được danh sách tài khoản: {exc}")
    return accounts


def _accounts_from_store() -> list[dict[str, str]]:
    """Load the accounts saved by an earlier run ([] when none usable)."""
    return accounts_store.load()


def _resolve_accounts(
    upload: Any,
) -> tuple[list[dict[str, str]] | None, str, str | None]:
    """Pick the account list for this run: a fresh upload wins over the store.

    Returns ``(accounts, source, error)``:
    - ``accounts`` is None only when nothing usable is available, and then
      ``error`` explains what to do next.
    - ``source`` is ``"upload"``, ``"stored"`` or ``""``.
    """
    has_upload = upload is not None and bool(getattr(upload, "filename", ""))
    if has_upload:
        try:
            return _accounts_from_upload(upload), "upload", None
        except ValueError as exc:
            return None, "", str(exc)

    stored = _accounts_from_store()
    if stored:
        return stored, "stored", None

    info = accounts_store.summary()
    state = str(info.get("state") or "")
    if state == accounts_store.STATE_CORRUPT:
        message = (
            "Danh sách tài khoản đã lưu bị lỗi định dạng. "
            "Hãy upload lại file Excel tài khoản."
        )
    elif state == accounts_store.STATE_UNREADABLE:
        message = (
            "Không đọc được danh sách tài khoản đã lưu. "
            "Hãy upload lại file Excel tài khoản."
        )
    else:
        message = (
            "Chưa có danh sách tài khoản nào được lưu. "
            "Hãy upload file Excel tài khoản (cột token / refresh_token) để bắt đầu."
        )
    return None, "", message


def _credit_update(
    run_id: int, tracker: "accounts_store.CreditTracker", **extra: Any
) -> None:
    """Publish the tracker's secret-free summary into ``job`` for the UI."""
    info = tracker.summary()
    _update(
        run_id,
        credit_total=int(info.get("total") or 0),
        credit_exhausted=int(info.get("exhausted") or 0),
        credit_label=str(info.get("label") or ""),
        credit_status=str(info.get("status") or ""),
        credit_message=str(info.get("message") or ""),
        **extra,
    )


def _update(run_id: int | None = None, **values: Any) -> None:
    with job_lock:
        if run_id is not None and job.get("run_id") != run_id:
            return
        if job.get("status") == "stopped" and values.get("status") != "stopped":
            return
        job.update(values)


def _run(options: dict[str, Any]) -> None:
    run_id = int(options["run_id"])
    page = options["start_page"]
    total: int | None = None
    seen: set[str] = options["seen"]
    accounts: list[dict[str, str]] = options["accounts"]
    dataset_name: str = options["dataset_name"]
    accounts_source: str = options.get("accounts_source", "")
    # Resolve this run's paths once. The crawler's module globals are shared by
    # every thread, so a stopped run that wakes up late could otherwise write
    # its pages into whatever dataset the *next* job selected.
    data_dir = _dataset_data_dir(dataset_name)
    state_file = _dataset_state_file(dataset_name)
    stop_token = options["stop_token"]
    body = options["body"]
    query = crawler.query_fingerprint(body)
    query_label = crawler.describe_body(body)
    # Accounts are tracked by 0-based position, never by token, so every
    # exhaustion figure published below is safe to show in the UI.
    tracker = accounts_store.CreditTracker(accounts)

    def cancelled() -> bool:
        return stop_token.is_set() or stop_event.is_set()

    if not options["force"]:
        # Only trust the saved total when the state belongs to *this* query. A
        # state from another query (or an old one with no recorded query) is
        # unknown, so its total must not be shown or used: it would display a
        # count from a different search. The API's own data.total replaces it as
        # soon as the first page arrives, so this is about not reporting a
        # foreign number and not trusting a foreign resume point.
        saved_state = crawler.load_state(state_file)
        if saved_state and saved_state.get("query") == query:
            total = saved_state.get("total")

    _update(
        run_id,
        status="running",
        message="Đang chuẩn bị crawl",
        page=page,
        records=len(seen),
        total=total,
        account_index=0,
        account_total=len(accounts),
        account_label="",
        dataset_name=dataset_name,
        query_label=query_label,
        accounts_source=accounts_source,
    )
    _credit_update(run_id, tracker)

    try:
        if not accounts:
            raise ValueError("Chưa có tài khoản hợp lệ")

        for account_index, account in enumerate(accounts, start=1):
            if cancelled():
                break

            cookie = (
                f"{crawler.CRM_TOKEN_NAME}={account['token']}; "
                f"{crawler.CRM_RF_TOKEN_NAME}={account['refresh_token']}"
            )
            crawler.log_cookie_used(cookie)

            _update(
                run_id,
                account_index=account_index,
                account_total=len(accounts),
                account_label=f"Acc {account_index}/{len(accounts)}",
                page=page,
                records=len(seen),
                total=total,
                message=f"Đang crawl {account_index}/{len(accounts)} từ trang {page}",
            )

            session = requests.Session()
            try:
                while not cancelled():
                    if options["end_page"] is not None and page > options["end_page"]:
                        break

                    if not options["force"] and (data_dir / f"{page}.json").exists():
                        _update(
                            run_id,
                            page=page,
                            records=len(seen),
                            message=(
                                f"Bỏ qua trang {page} đã có dữ liệu; "
                                f"tiếp tục {account_index}/{len(accounts)}"
                            ),
                        )
                        page += 1
                        continue

                    payload = crawler.fetch_page(session, cookie, page, options["per_page"], body)
                    data = payload.get("data") or {}
                    items = data.get("items")
                    if not isinstance(items, list):
                        raise RuntimeError(f"API không trả về data.items ở trang {page}")

                    row_count = data.get("rowCount", len(items))
                    if isinstance(data.get("total"), int):
                        total = data["total"]

                    if cancelled():
                        break

                    # Keep every record the API returned for this page. Filtering
                    # ``items`` against fingerprints of *already saved* rows and
                    # then overwriting the page file destroyed data whenever a
                    # page overlapped a previous one. De-duplication now happens
                    # only at export time, where it belongs.
                    crawler.save_page(items, page, True, data_dir)
                    for item in items:
                        seen.add(_fingerprint(item))

                    # Mirror the page to Supabase Storage immediately, so a
                    # redeploy mid-crawl loses at most the page in flight.
                    # A Storage failure must never abort the crawl: the local
                    # file is the working copy and disk still has it.
                    backup_note = ""
                    if dataset_store.configured():
                        result = dataset_store.upload_file(
                            dataset_name, data_dir / f"{page}.json"
                        )
                        if not result.ok:
                            backup_note = f" (chưa sao lưu: {result.detail})"
                            _update(run_id, backup_error=result.detail)
                        else:
                            _update(run_id, backup_error="")

                    _update(
                        run_id,
                        page=page,
                        records=len(seen),
                        total=total,
                        message=(
                            f"Tài khoản {account_index}/{len(accounts)}: "
                            f"trang {page} đã lưu {len(items)} bản ghi"
                            f"{backup_note}"
                        ),
                    )
                    crawler.save_state(page, total, len(seen), query, state_file)

                    if options["end_page"] is not None and page >= options["end_page"]:
                        break

                    if isinstance(row_count, int) and row_count < options["per_page"]:
                        page += 1
                        break
                    if total is not None and len(seen) >= total:
                        page += 1
                        break

                    page += 1
                    options["stop_token"].wait(options["delay"])
            except (crawler.AuthError, crawler.CreditError) as exc:
                # Record which account failed *and why*, by position only. The
                # loop falls through to the next account; if there is none, the
                # final handler below turns this into the no-credit state.
                position = account_index - 1
                tracker.mark_exhausted(position)
                if account_index >= len(accounts):
                    raise
                _credit_update(
                    run_id,
                    tracker,
                    message=(
                        f"Tài khoản {account_index}/{len(accounts)} dừng ở trang {page}: "
                        f"{exc}. Chuyển sang tài khoản kế tiếp."
                    ),
                    records=len(seen),
                    total=total,
                )
            finally:
                session.close()

        credit = tracker.summary()
        if cancelled():
            _credit_update(
                run_id, tracker, status="stopped", message="Đã dừng theo yêu cầu", records=len(seen)
            )
        elif credit["all_exhausted"]:
            # Every account ran out of credit (or its token was rejected), so the
            # crawl stops with a status the UI can branch on -- never a plain
            # "completed" that reads like success.
            _credit_update(
                run_id,
                tracker,
                status="no_credit",
                message=(
                    f"Tất cả {credit['total']} tài khoản đã hết credit hoặc token hết hạn "
                    f"({credit['exhausted']}/{credit['total']}). "
                    "Hãy upload file Excel tài khoản mới để tiếp tục crawl."
                ),
                records=len(seen),
                total=total,
            )
        elif credit["any_exhausted"]:
            # Some accounts died but others carried on: report the count so the
            # user knows to replace them before the next run.
            _credit_update(
                run_id,
                tracker,
                status="completed",
                message=(
                    f"Hoàn tất: {len(seen)} bản ghi. "
                    f"{credit['message']}."
                ),
                records=len(seen),
                total=total,
            )
        else:
            _credit_update(
                run_id,
                tracker,
                status="completed",
                message=f"Hoàn tất: {len(seen)} bản ghi",
                records=len(seen),
            )
    except (crawler.AuthError, crawler.CreditError) as exc:
        # The last account failed. With >= 1 account that always means every
        # account is out of credit, so end in the distinguishable no_credit
        # state and tell the user what to do rather than reporting a generic
        # error that looks like a network problem. The counters must be
        # published here too: the loop's own last update happened *before* this
        # account was marked, so without this the UI would show a stale count.
        credit = tracker.summary()
        if credit["all_exhausted"]:
            _credit_update(
                run_id,
                tracker,
                status="no_credit",
                message=(
                    f"Tất cả {credit['total']} tài khoản đã hết credit hoặc token hết hạn "
                    f"({credit['exhausted']}/{credit['total']}). "
                    "Hãy upload file Excel tài khoản mới để tiếp tục crawl."
                ),
                records=len(seen),
                total=total,
            )
        else:
            _update(
                run_id,
                status="error",
                message=f"Không crawl được tài khoản cuối ở trang {page}: {exc}.",
                records=len(seen),
                total=total,
            )
    except (requests.RequestException, RuntimeError, OSError, ValueError) as exc:
        _update(run_id, status="error", message=str(exc))
    except Exception as exc:
        _update(
            run_id,
            status="error",
            message=f"Lỗi không xác định: {exc.__class__.__name__}: {exc}",
        )
        print(traceback.format_exc())


@app.get("/")
def index():
    with job_lock:
        current = {key: value for key, value in job.items() if key != "stop_token"}
    # ``error`` and ``form_values`` are always present so the template can rely
    # on them: a normal page load has no error and no submitted values, and the
    # error path (_render_dashboard_error) fills both in.
    return render_template("index.html", job=current, error=None, form_values={})


@app.post("/api/jobs")
def start_job():
    """Claim the single crawl slot, then start it.

    ``job_lock`` alone cannot make this atomic: the "is a job running?" check and
    the ``status="running"`` assignment are separated by the Excel parse and the
    dataset setup, both of which do I/O. With one sync worker that gap was
    unreachable, but the gthread worker runs requests concurrently, so two
    near-simultaneous submits could both pass the check and start two crawls
    writing into the same folder. This non-blocking lock serialises the whole
    claim sequence without touching the short-lived ``job_lock`` used by
    ``/api/status``.
    """
    if not start_lock.acquire(blocking=False):
        return _render_dashboard_error(
            "Đang có một job chạy. Hãy dừng job hiện tại trước khi bắt đầu job mới.",
            form_values=_form_snapshot(request.form),
            status_code=409,
        )
    try:
        return _start_job()
    finally:
        start_lock.release()


def _start_job():
    # Snapshot before any validation: every rejection below re-renders the
    # dashboard with exactly what the user typed, never a defaulted value.
    form_values = _form_snapshot(request.form)

    with job_lock:
        already_running = job["status"] == "running"
    if already_running:
        # The renderer reads/updates ``job`` under the same lock, so it must be
        # called OUTSIDE this block: acquiring job_lock twice on one thread
        # deadlocked the request (and, for a dead client, pinned a worker).
        return _render_dashboard_error(
            "Đang có một job chạy. Hãy dừng job hiện tại trước khi bắt đầu job mới.",
            form_values=form_values,
            status_code=409,
        )

    accounts_file = request.files.get("accounts_file")
    accounts, accounts_source, accounts_error = _resolve_accounts(accounts_file)
    if not accounts:
        return _render_dashboard_error(
            accounts_error or "Chưa có danh sách tài khoản nào được lưu.",
            form_values=form_values,
        )

    try:
        start_page = max(1, int(request.form.get("start_page", "1")))
        end_raw = request.form.get("end_page", "").strip()
        end_page = int(end_raw) if end_raw else None
        per_page = min(50, max(1, int(request.form.get("per_page", "50"))))
        delay = max(0.0, float(request.form.get("delay", "1.5")))
    except ValueError:
        return _render_dashboard_error(
            "Thông số trang, số bản ghi hoặc delay không hợp lệ",
            form_values=form_values,
        )

    if end_page is not None and end_page < start_page:
        return _render_dashboard_error(
            "Trang kết thúc phải lớn hơn hoặc bằng trang bắt đầu",
            form_values=form_values,
        )

    try:
        region_codes = _parse_region_selection(request.form)
        body = crawler.build_search_body(
            str(request.form.get("hs_code", "") or ""),
            region_codes,
        )
    except regions.RegionError as exc:
        return _render_dashboard_error(str(exc), form_values=form_values)

    dataset_raw = _resolve_dataset_from_request(request.form, body)
    force = request.form.get("force") == "on"
    try:
        dataset_name = _set_crawler_paths(dataset_raw)
        _assert_dataset_matches_query(
            dataset_name, crawler.query_fingerprint(body), force
        )
    except (ValueError, regions.RegionError) as exc:
        # The per-dataset query fingerprint guard rejects a folder that already
        # holds pages from a different query. The reason must be readable on the
        # dashboard, so render it there instead of handing back a JSON blob.
        # ``_clean_dataset_name`` can itself raise for an unusable name (that is
        # one of the failures caught here), so it must not break the render.
        try:
            shown_dataset = _clean_dataset_name(dataset_raw)
        except ValueError:
            shown_dataset = None
        # ``_set_crawler_paths`` already pointed the crawler's module globals at
        # the rejected folder. Nothing started, so put them back on the dataset
        # the dashboard is actually showing. Resolved without ``_ensure_dataset``
        # so a rejection never creates a folder as a side effect.
        with job_lock:
            active_dataset = str(job.get("dataset_name", LEGACY_DATASET_NAME))
        try:
            active_dataset = _clean_dataset_name(active_dataset)
        except ValueError:
            active_dataset = LEGACY_DATASET_NAME
        crawler.DATA_DIR = _dataset_data_dir(active_dataset)
        crawler.STATE_FILE = _dataset_state_file(active_dataset)
        return _render_dashboard_error(
            str(exc),
            form_values=form_values,
            body=body,
            dataset_name=shown_dataset,
        )
    seen = _load_seen_fingerprints()
    run_stop = threading.Event()
    options = {
        "start_page": start_page,
        "end_page": end_page,
        "per_page": per_page,
        "delay": delay,
        "force": force,
        "body": body,
        "accounts": accounts,
        "accounts_source": accounts_source,
        "seen": seen,
        "dataset_name": dataset_name,
        "stop_token": run_stop,
    }

    stop_event.clear()
    with job_lock:
        next_run_id = int(job.get("run_id", 0)) + 1
        job.update(
            run_id=next_run_id,
            status="running",
            message="Đang khởi động",
            page=start_page,
            records=len(seen),
            total=None,
            account_index=0,
            account_total=len(accounts),
            account_label="",
            dataset_name=dataset_name,
            query_label=crawler.describe_body(body),
            started_at=time.time(),
            accounts_source=accounts_source,
            credit_total=len(accounts),
            credit_exhausted=0,
            credit_label=f"0/{len(accounts)}",
            credit_status=accounts_store.classify_exhaustion(len(accounts), 0),
            credit_message="",
        )
        # Remembered so /api/jobs/stop can signal exactly this run.
        job["stop_token"] = run_stop

    options["run_id"] = next_run_id
    threading.Thread(target=_run, args=(options,), daemon=True).start()
    return redirect(url_for("index"))


@app.post("/api/jobs/stop")
def stop_job():
    stop_event.set()
    with job_lock:
        token = job.get("stop_token")
        job["status"] = "stopped"
        job["message"] = "Đã dừng theo yêu cầu"
    if token is not None:
        token.set()
    return redirect(url_for("index"))


@app.get("/api/status")
def status():
    with job_lock:
        return jsonify({key: value for key, value in job.items() if key != "stop_token"})


@app.get("/api/accounts")
def accounts_status():
    """Report the remembered account list without revealing any credential.

    The dashboard uses this to show "3 tài khoản, cập nhật lúc ..." and to decide
    whether the file input is still mandatory. Only the count, timestamp, state
    and safe message are returned -- never a token, and not the filesystem path.
    """
    return jsonify(_accounts_public_summary())


@app.post("/api/accounts/clear")
def accounts_clear():
    """Forget the stored account list (the user must upload a new one)."""
    with job_lock:
        running = job.get("status") == "running"
    if running:
        # Deleting the credentials out from under a live crawl would make the
        # in-flight account impossible to replace, so refuse instead.
        return (
            jsonify(
                {
                    "error": "Đang có job chạy. Hãy dừng job rồi mới xóa danh sách tài khoản."
                }
            ),
            409,
        )
    try:
        removed = accounts_store.clear()
    except OSError as exc:
        return jsonify({"error": f"Không xóa được danh sách tài khoản: {exc}"}), 500
    return jsonify(
        {
            **_accounts_public_summary(),
            "removed": bool(removed),
            "message": (
                "Đã xóa danh sách tài khoản đã lưu."
                if removed
                else "Không có danh sách tài khoản nào để xóa."
            ),
        }
    )


@app.get("/api/regions")
def list_regions():
    """Country catalog for the region picker.

    Mirrors the TradeIT buyer-search picker: five groups in the site's order,
    195 countries, the site's English labels and a flag for each.

    Deliberately no ``default`` / ``default_hs_code``: the picker starts empty so
    a page load can never preselect a country or an HS code the user did not
    choose. The form is re-filled from the user's own last submission instead.
    """
    return jsonify(
        {
            "groups": [
                {
                    "code": group_code,
                    "name": name,
                    "name_vi": name_vi,
                    "countries": regions.countries_in_group(group_code),
                }
                for group_code, name, name_vi, _members in regions.GROUPS
            ],
            "countries": [
                {
                    "code": code,
                    "name": name_en,
                    "name_vi": name_vi,
                    "group": group_code,
                    "flag": regions.flag_url(code),
                    "emoji": regions.flag_emoji(code),
                }
                for code, name_en, name_vi, group_code in regions.COUNTRIES
            ],
        }
    )


@app.post("/api/search-preview")
def search_preview():
    """Build and return the exact request body that will be sent to TradeIT."""
    payload = request.get_json(silent=True) or {}
    raw_regions = payload.get("region_codes")
    if raw_regions is None:
        raw_regions = payload.get("regions") or []
    if isinstance(raw_regions, str):
        raw_regions = [raw_regions]
    try:
        body = crawler.build_search_body(
            str(payload.get("hs_code", "") or ""),
            [str(value) for value in raw_regions],
        )
    except regions.RegionError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(
        {
            "body": body,
            "label": crawler.describe_body(body),
            "desti_country_code": body["destiCountryCode"],
        }
    )


@app.get("/api/datasets")
def datasets():
    with job_lock:
        current = job.get("dataset_name", LEGACY_DATASET_NAME)
    return jsonify({"current": current, "datasets": _list_datasets()})


@app.post("/api/datasets")
def create_dataset():
    payload = request.get_json(silent=True) or {}
    raw_name = str(payload.get("name", "")).strip()
    try:
        dataset_name = _ensure_dataset(raw_name)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(
        {
            "name": dataset_name,
            "label": _dataset_display_name(dataset_name),
            "message": "Đã tạo bộ dữ liệu",
        }
    ), 201


@app.get("/api/datasets/<dataset>/summary")
def dataset_summary(dataset: str):
    """Detail view for one dataset: pages, records, size and saved state."""
    try:
        name = _require_dataset(dataset)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except FileNotFoundError as exc:
        return jsonify({"error": str(exc)}), 404
    return jsonify(_dataset_summary(name))


@app.get("/api/storage")
def storage_status():
    """Report whether datasets are being mirrored to Supabase Storage."""
    return jsonify(
        {
            "active": dataset_store.active(),
            "configured": dataset_store.configured(),
            "bucket": dataset_store.bucket(),
            "env_var": dataset_store.ENV_BUCKET,
        }
    )


@app.post("/api/datasets/<dataset>/backup")
def backup_dataset(dataset: str):
    """Push an existing dataset's pages to Supabase Storage on demand."""
    if not dataset_store.configured():
        return jsonify(
            {
                "error": "Chưa cấu hình Supabase Storage. Đặt biến "
                f"{dataset_store.ENV_BUCKET} (và SUPABASE_URL + key) rồi thử lại."
            }
        ), 400
    try:
        name = _require_dataset(dataset)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except FileNotFoundError as exc:
        return jsonify({"error": str(exc)}), 404

    result = dataset_store.upload_dataset(
        name, _dataset_data_dir(name), _dataset_state_file(name)
    )
    payload = {
        "message": result.detail or ("Đã sao lưu" if result.ok else "Chưa sao lưu được"),
        "count": result.count,
        "bucket": dataset_store.bucket(),
    }
    return jsonify(payload), (200 if result.ok else 502)


@app.get("/api/datasets/<dataset>/download")
def download_dataset(dataset: str):
    """Download a whole dataset as one Excel workbook.

    This used to return a ZIP of the raw JSON pages, which meant opening a
    dozen files to read the data. It now returns the same .xlsx the export
    button produces (one row per record, one column per field, text-formatted
    so HS codes keep their leading zeros). ``?format=zip`` still serves the
    raw JSON for anyone who wants the pages themselves.
    """
    try:
        name = _require_dataset(dataset)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except FileNotFoundError as exc:
        return jsonify({"error": str(exc)}), 404

    pages = _dataset_page_files(name)
    if not pages:
        return jsonify({"error": "Bộ dữ liệu này chưa có file nào để tải"}), 404

    if request.args.get("format", "").strip().lower() == "zip":
        return send_file(
            _zip_dataset(name),
            as_attachment=True,
            download_name=f"{name}-json.zip",
            mimetype="application/zip",
        )

    records: list[tuple[int, dict[str, Any]]] = []
    for path in pages:
        page = merge_data.page_number(path)
        try:
            payload = _read_page_in_dataset(name, page)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            return jsonify({"error": f"Trang {page}: {exc}"}), 400
        records.extend((page, merge_data.flatten(item)) for item in payload)

    if not records:
        return jsonify({"error": "Bộ dữ liệu này chưa có bản ghi nào"}), 404

    buffer = _xlsx_buffer(records)
    return send_file(
        buffer,
        as_attachment=True,
        download_name=f"{name}-buyers.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@app.post("/api/datasets/<dataset>/delete")
def delete_dataset(dataset: str):
    """Delete one dataset (irreversible)."""
    # Deliberately resolved without ``_ensure_dataset``: validating the name must
    # not create the folder that is about to be removed.
    try:
        name = _require_dataset(dataset)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except FileNotFoundError as exc:
        return jsonify({"error": str(exc)}), 404
    try:
        result = _delete_dataset(name)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 409
    except OSError as exc:
        return jsonify({"error": f"Không xóa được bộ dữ liệu: {exc}"}), 500
    return jsonify(result)


@app.get("/api/files")
def list_files():
    dataset_name = request.args.get("dataset", "").strip()
    if not dataset_name:
        with job_lock:
            dataset_name = str(job.get("dataset_name", LEGACY_DATASET_NAME))
    dataset_name = _ensure_dataset(dataset_name)
    # After a redeploy the disk is empty but Storage still has the pages.
    _restore_dataset_if_empty(dataset_name)
    files = []
    for path in _dataset_page_files(dataset_name):
        page = merge_data.page_number(path)
        try:
            count = len(_read_page_in_dataset(dataset_name, page))
            size = path.stat().st_size
            updated_at = path.stat().st_mtime
        except (OSError, ValueError, json.JSONDecodeError):
            count, size, updated_at = 0, path.stat().st_size, None
        files.append(
            {
                "page": page,
                "name": path.name,
                "records": count,
                "size": size,
                "updated_at": updated_at,
            }
        )
    return jsonify(files)


@app.get("/api/files/<dataset>/<page>")
def get_file(dataset: str, page: str):
    try:
        dataset = _ensure_dataset(dataset)
        page_number = int(page)
        return jsonify({"page": page_number, "records": _read_page_in_dataset(dataset, page_number)})
    except (ValueError, FileNotFoundError, OSError, json.JSONDecodeError) as exc:
        return jsonify({"error": str(exc)}), 400


@app.put("/api/files/<dataset>/<page>")
def update_file(dataset: str, page: str):
    try:
        dataset = _ensure_dataset(dataset)
        page_number = int(page)
        path = _dataset_page_path(dataset, page_number)
        payload = request.get_json(silent=True)
        records = payload.get("records") if isinstance(payload, dict) else None
        if not isinstance(records, list):
            raise ValueError("Nội dung file phải là JSON array")
        json.dumps(records, ensure_ascii=False)
        temporary = path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(path)
        return jsonify({"page": page_number, "records": len(records), "message": "Đã lưu file"})
    except (ValueError, OSError, TypeError) as exc:
        return jsonify({"error": str(exc)}), 400


@app.post("/api/export")
def export_csv():
    selected = request.form.getlist("files")
    dataset_name = request.form.get("dataset", "").strip()
    if not dataset_name:
        with job_lock:
            dataset_name = str(job.get("dataset_name", LEGACY_DATASET_NAME))
    dataset_name = _ensure_dataset(dataset_name)
    data_dir = _dataset_data_dir(dataset_name)
    if selected:
        try:
            pages = sorted({int(value) for value in selected})
            records = []
            for page in pages:
                records.extend((page, merge_data.flatten(item)) for item in _read_page_in_dataset(dataset_name, page))
        except (ValueError, FileNotFoundError, OSError, json.JSONDecodeError) as exc:
            return jsonify({"error": str(exc)}), 400
    else:
        records = merge_data.load_records(data_dir)

    output = _dataset_dir(dataset_name) / f"{dataset_name}-buyers.xlsx"
    if not records:
        return jsonify({"error": "Chưa có dữ liệu để xuất"}), 400
    _write_xlsx(records, output)
    return send_file(
        output,
        as_attachment=True,
        download_name=f"{dataset_name}-buyers.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


@app.get("/download-template")
def download_template():
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "accounts"
    sheet.append(["token", "refresh_token"])
    sheet.append(["token_1", "refresh_token_1"])
    sheet.append(["token_2", "refresh_token_2"])

    buffer = BytesIO()
    workbook.save(buffer)
    workbook.close()
    buffer.seek(0)
    return send_file(
        buffer,
        as_attachment=True,
        download_name="tradeit-accounts-template.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
