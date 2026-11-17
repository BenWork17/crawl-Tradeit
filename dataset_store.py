"""Mirror crawled dataset files to Supabase Storage so a redeploy keeps them.

Render's free plan has no persistent disk: the container filesystem is wiped on
every redeploy and every spin-down, which used to lose every crawled dataset.
Account credentials are already kept in Supabase by :mod:`accounts_store`; this
module does the same for the crawl output.

Design
------
The local filesystem stays the working copy — the crawler keeps writing pages to
disk exactly as before, so nothing about a run becomes slower or more fragile.
Each finished page is then *also* pushed to a Supabase Storage bucket, and the
dashboard can pull a dataset back from the bucket after a redeploy.

Objects are laid out as::

    <dataset>/data/<page>.json
    <dataset>/state.json

which mirrors the on-disk layout, so a restore is a plain file copy.

Everything degrades gracefully: with no bucket configured, or on any network or
auth error, every call returns a failure result instead of raising, and the app
keeps working from disk alone. Tokens are never involved here; dataset pages
contain trade records, not credentials.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping, Optional
from urllib.parse import quote

logger = logging.getLogger(__name__)

__all__ = [
    "ENV_BUCKET",
    "ENV_SUPABASE_URL",
    "ENV_KEY_NAMES",
    "StorageResult",
    "active",
    "bucket",
    "configured",
    "download_dataset",
    "list_datasets",
    "object_key",
    "page_key",
    "state_key",
    "upload_dataset",
    "upload_file",
]

ENV_BUCKET = "SUPABASE_STORAGE_BUCKET"
ENV_SUPABASE_URL = "SUPABASE_URL"
ENV_SUPABASE_TABLE = "SUPABASE_STORAGE_BUCKET"  # kept for symmetry/documentation

# Same key names accounts_store accepts; first one set wins.
ENV_KEY_NAMES: tuple[str, ...] = (
    "SUPABASE_KEY",
    "SUPABASE_SECRET_KEY",
    "SUPABASE_SERVICE_ROLE_KEY",
)

DEFAULT_BUCKET = "tradeit-data"
TIMEOUT = 20.0
PAGE_RE = re.compile(r"^(\d+)\.json$")

# A dataset name is interpolated into an object key; keep it boring.
_NAME_RE = re.compile(r"^[A-Za-z0-9_-]{1,80}$")


@dataclass(frozen=True)
class StorageResult:
    """Outcome of a storage call. Never contains file contents or secrets."""

    ok: bool
    detail: str = ""
    count: int = 0

    def __bool__(self) -> bool:  # allow ``if result:``
        return self.ok


def _env_key() -> str:
    for name in ENV_KEY_NAMES:
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return ""


def bucket() -> str:
    """Return the configured bucket name, or ``""`` when storage is off."""
    raw = os.environ.get(ENV_BUCKET, "").strip()
    if raw:
        return raw
    # A bucket is only implied when Supabase itself is configured; otherwise
    # leaving this unset keeps the feature off, which is what local dev wants.
    if os.environ.get(ENV_SUPABASE_URL, "").strip() and _env_key():
        return DEFAULT_BUCKET
    return ""


def configured() -> bool:
    """True when dataset mirroring to Supabase Storage is possible."""
    return bool(bucket() and os.environ.get(ENV_SUPABASE_URL, "").strip() and _env_key())


def active() -> str:
    """``"supabase-storage"`` when enabled, else ``"off"``."""
    return "supabase-storage" if configured() else "off"


def _base() -> str:
    url = os.environ.get(ENV_SUPABASE_URL, "").strip().rstrip("/")
    return f"{url}/storage/v1"


def _headers(content_type: str | None = None) -> dict[str, str]:
    key = _env_key()
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
    }
    if content_type:
        headers["Content-Type"] = content_type
        headers["x-upsert"] = "true"
    return headers


def _safe_name(name: str) -> str:
    if not _NAME_RE.match(name or ""):
        raise ValueError(f"Tên bộ dữ liệu không hợp lệ cho Storage: {name!r}")
    return name


def page_key(dataset: str, page: int) -> str:
    """Object key for one crawled page."""
    return f"{_safe_name(dataset)}/data/{int(page)}.json"


def state_key(dataset: str) -> str:
    """Object key for a dataset's ``state.json``."""
    return f"{_safe_name(dataset)}/state.json"


def object_key(dataset: str, relative: str) -> str:
    return f"{_safe_name(dataset)}/{quote(relative.lstrip('/'), safe='/')}"


def _request(method: str, url: str, **kwargs: Any):
    import requests  # imported lazily: the module must import without it

    return requests.request(method, url, timeout=TIMEOUT, **kwargs)


def _upload_object(key: str, data: bytes, content_type: str) -> StorageResult:
    if not configured():
        return StorageResult(False, "Supabase Storage chưa được cấu hình")
    url = f"{_base()}/object/{bucket()}/{quote(key, safe='/')}"
    try:
        response = _request(
            "POST", url, headers=_headers(content_type), data=data
        )
    except Exception as exc:  # noqa: BLE001 - network faults must not break a crawl
        logger.warning("Không đẩy được %s lên Supabase Storage: %s", key, exc)
        return StorageResult(False, f"lỗi mạng ({type(exc).__name__})")

    if response.status_code in (200, 201):
        return StorageResult(True)
    if response.status_code == 409:
        # Bucket missing is the common cause; surface it plainly.
        return StorageResult(False, "bucket chưa tồn tại (HTTP 409)")
    logger.warning(
        "Supabase Storage từ chối %s: HTTP %s", key, response.status_code
    )
    return StorageResult(False, f"HTTP {response.status_code}")


def upload_file(dataset: str, path: Path, *, content_type: str | None = None) -> StorageResult:
    """Mirror one local file to Storage; the object key keeps the file name."""
    if not configured():
        return StorageResult(False, "Supabase Storage chưa được cấu hình")
    try:
        key = object_key(dataset, f"data/{path.name}")
        data = path.read_bytes()
    except (OSError, ValueError) as exc:
        return StorageResult(False, f"không đọc được file cục bộ: {exc}")

    if content_type is None:
        content_type = "application/json" if path.suffix == ".json" else "application/octet-stream"
    return _upload_object(key, data, content_type)


def upload_dataset(dataset: str, data_dir: Path, state_file: Optional[Path] = None) -> StorageResult:
    """Upload every page file of a dataset plus its state file.

    Used by the "back up this dataset" action and at the end of a crawl.
    """
    if not configured():
        return StorageResult(False, "Supabase Storage chưa được cấu hình")

    uploaded = 0
    failures: list[str] = []
    pages = sorted(
        (p for p in data_dir.glob("*.json") if PAGE_RE.match(p.name)),
        key=lambda p: int(PAGE_RE.match(p.name).group(1)),  # type: ignore[union-attr]
    )
    for path in pages:
        result = upload_file(dataset, path)
        if result.ok:
            uploaded += 1
        else:
            failures.append(f"{path.name}: {result.detail}")

    if state_file is not None and state_file.is_file():
        try:
            key = state_key(dataset)
            result = _upload_object(key, state_file.read_bytes(), "application/json")
            if not result.ok:
                failures.append(f"state.json: {result.detail}")
        except (OSError, ValueError) as exc:
            failures.append(f"state.json: {exc}")

    if failures:
        return StorageResult(
            False,
            f"{uploaded}/{len(pages)} trang đã đẩy; lỗi: {failures[0]}",
            uploaded,
        )
    return StorageResult(True, f"đã đẩy {uploaded} trang", uploaded)


def _list_prefix(prefix: str) -> list[dict[str, Any]]:
    """List objects under ``prefix`` (one level, paginated)."""
    url = f"{_base()}/object/list/{bucket()}"
    objects: list[dict[str, Any]] = []
    offset = 0
    limit = 1000
    while True:
        body = {
            "prefix": prefix,
            "limit": limit,
            "offset": offset,
            "sortBy": {"column": "name", "order": "asc"},
        }
        response = _request("POST", url, headers=_headers("application/json"), json=body)
        if response.status_code >= 400:
            raise StorageError(f"HTTP {response.status_code}")
        rows = response.json()
        if not isinstance(rows, list) or not rows:
            break
        objects.extend(r for r in rows if isinstance(r, Mapping))
        if len(rows) < limit:
            break
        offset += limit
    return objects


class StorageError(RuntimeError):
    """Raised internally for a Storage failure the caller wants to report."""


def list_datasets() -> list[str]:
    """Names of datasets that have at least something mirrored in Storage."""
    if not configured():
        return []
    try:
        rows = _list_prefix("")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Không liệt kê được dataset trên Storage: %s", exc)
        return []
    names = {
        str(row.get("name"))
        for row in rows
        if row.get("name") and not str(row.get("name")).endswith(".json")
    }
    return sorted(names)


def _download_object(key: str) -> bytes | None:
    url = f"{_base()}/object/{bucket()}/{quote(key, safe='/')}"
    response = _request("GET", url, headers=_headers())
    if response.status_code == 404:
        return None
    if response.status_code >= 400:
        raise StorageError(f"HTTP {response.status_code}")
    return response.content


def download_dataset(dataset: str, data_dir: Path, state_file: Optional[Path] = None) -> StorageResult:
    """Pull a dataset from Storage onto disk, skipping files already present.

    Returns the number of files written, so a caller can report "restored N".
    """
    if not configured():
        return StorageResult(False, "Supabase Storage chưa được cấu hình")
    try:
        rows = _list_prefix(f"{_safe_name(dataset)}/data")
    except Exception as exc:  # noqa: BLE001
        return StorageResult(False, f"không liệt kê được: {exc}")

    written = 0
    failures: list[str] = []
    data_dir.mkdir(parents=True, exist_ok=True)
    for row in rows:
        name = str(row.get("name") or "")
        if not PAGE_RE.match(name):
            continue
        target = data_dir / name
        if target.exists():
            continue
        try:
            blob = _download_object(f"{dataset}/data/{name}")
        except Exception as exc:  # noqa: BLE001
            failures.append(f"{name}: {exc}")
            continue
        if blob is None:
            continue
        target.write_bytes(blob)
        written += 1

    if state_file is not None and not state_file.exists():
        try:
            blob = _download_object(state_key(dataset))
        except Exception as exc:  # noqa: BLE001
            blob = None
            failures.append(f"state.json: {exc}")
        if blob:
            state_file.parent.mkdir(parents=True, exist_ok=True)
            state_file.write_bytes(blob)

    if failures:
        return StorageResult(False, f"{written} file đã tải; lỗi: {failures[0]}", written)
    return StorageResult(True, f"đã khôi phục {written} file", written)
