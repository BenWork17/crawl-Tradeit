"""Persistent TradeIT account list + per-run credit-exhaustion tracking.

The dashboard requires the user to upload a cookie Excel on *every* crawl
because the parsed accounts only ever lived in the request.  This module is the
missing memory: it stores the parsed account list as JSON on disk so a crawl
can reuse the accounts from the previous run, and it tracks which accounts ran
out of credit so the UI can say "2/3 accounts exhausted" instead of stopping
with a raw exception.

The module deliberately has **no hard third-party imports**: it imports on a
bare Python install, and only reaches for an HTTP client when the Supabase
backend is actually configured and used.

Two backends
------------
The public API (:func:`save`, :func:`load`, :func:`load_with_status`,
:func:`summary`, :func:`clear`, :func:`exists`) is backend-agnostic; callers do
not need to know which one is active.

* **file** (default) -- the local JSON file described below.  Zero network
  calls, no configuration.
* **supabase** -- a single row in a Supabase Postgres table, spoken to over the
  PostgREST HTTP API.  Selected automatically when ``SUPABASE_URL`` and
  ``SUPABASE_KEY`` are both set (override the table with ``SUPABASE_TABLE``).
  This is what makes accounts survive a Render redeploy: Render's free plan has
  no persistent disk and the container filesystem is wiped on every deploy and
  every idle spin-down.

If the Supabase backend is selected but the network, the key or the table fails,
the module logs a warning once and falls back to the local file provider so a
crawl never dies because of storage.  ``summary()["backend"]`` reports which
provider actually served the call: ``"file"``, ``"supabase"`` or
``"file-fallback"``.  Pass an explicit ``path=`` to force the file provider.

Secrets policy
--------------
Tokens are credentials.  They are written only to the store (file or Supabase
row); they are never written to a log, never included in an exception message
and never returned by :func:`summary`, :meth:`CreditTracker.summary` or any
other public function.  Functions here log counts, positions and file paths
only.  The same applies to the Supabase URL/key: they are read from the
environment, are never logged and never appear in a summary -- ``backend`` is a
bare label like ``"supabase"``.
The store file is a credential file: it is created with mode ``0o600`` where the
platform supports it.  **Windows limitation (accepted, documented risk):** on
Windows ``os.chmod`` cannot express an ACL -- it only toggles the read-only bit,
so ``0o600`` is *not* enforced and the file inherits the ACL of its containing
directory (typically readable by other local users or by anyone who can reach a
roaming profile).  :func:`save` therefore logs a one-time warning when the
``chmod`` cannot be enforced, so an operator is not left believing the file is
private.  Mitigations, in order of strength:

1. prefer the Supabase backend on Windows (no local credential file at all);
2. point ``TRADEIT_ACCOUNTS_FILE`` at a path inside your own user profile that
   is not a shared/roaming directory (``C:\\Users\\<you>\\...``), and do **not**
   keep the store under ``shared``/roaming-profile directories;
3. on a multi-user Windows host, restrict the file with an explicit DACL, e.g.
   ``icacls accounts.json /inheritance:r /grant:r "%USERNAME%:F"``.

The file is git-ignored in every default location, so it cannot be committed.

Where the file lives (file backend)
-----------------------------------
The location is resolved on every call, in this order:

1. an explicit ``path=`` argument (a file path, or a directory to put
   ``accounts.json`` in);
2. ``TRADEIT_ACCOUNTS_FILE`` -- an explicit file path;
3. ``TRADEIT_DATA_DIR`` + ``/accounts.json`` -- a directory mount point;
4. ``<project>/datasets/accounts.json`` -- the project default.  ``datasets/``
   is git-ignored, so credentials can never be committed by accident.

On Render (and any container host) the filesystem is **ephemeral**: it is wiped
on every redeploy and, on free instances, every time the service spins down
after being idle.  Accounts stored in the file backend are therefore *lost*
there; that is exactly why the Supabase backend exists.  Without either, the
app still works: :func:`load` simply returns an empty list and the user has to
upload the Excel again.

Typical use::

    import accounts_store

    summary = accounts_store.save(accounts)          # after parsing the Excel
    accounts = accounts_store.load()                 # next run
    tracker = accounts_store.CreditTracker(accounts) # 0-based account index
    tracker.mark_exhausted(index)
    print(tracker.summary()["message"])              # "2/3 tài khoản đã hết credit"
"""

from __future__ import annotations

import json
import hashlib
import logging
import os
import re
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

__all__ = [
    "ACCOUNTS_FILENAME",
    "BACKEND_FILE",
    "BACKEND_FILE_FALLBACK",
    "BACKEND_SUPABASE",
    "CREDITS_PER_SEARCH_REQUEST",
    "CREDIT_AVAILABLE",
    "CREDIT_EXHAUSTED",
    "CREDIT_FILENAME",
    "CREDIT_UNKNOWN",
    "DEFAULT_STORAGE_DIRNAME",
    "ENV_ACCOUNTS_FILE",
    "ENV_DATA_DIR",
    "ENV_SUPABASE_KEY",
    "ENV_SUPABASE_TABLE",
    "ENV_SUPABASE_URL",
    "EXHAUSTION_ALL",
    "EXHAUSTION_NONE",
    "EXHAUSTION_SOME",
    "EXHAUSTION_UNKNOWN",
    "MAX_CREDIT_RECORDS",
    "NEW_ACCOUNT_CREDITS",
    "PROBE_PER_PAGE",
    "RECORDS_PER_CREDIT",
    "SUPABASE_DEFAULT_TABLE",
    "SUPABASE_ROW_ID",
    "CreditTracker",
    "account_key",
    "active_accounts",
    "active_backend",
    "classify_exhaustion",
    "clear",
    "clear_credit",
    "credit_records",
    "credit_summary",
    "default_path",
    "default_storage_dir",
    "exhaustion_summary",
    "exists",
    "load",
    "load_with_status",
    "record_balance",
    "record_exhausted",
    "resolve_path",
    "save",
    "summary",
]

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent

ENV_DATA_DIR = "TRADEIT_DATA_DIR"
ENV_ACCOUNTS_FILE = "TRADEIT_ACCOUNTS_FILE"

# Supabase backend (optional).  Setting both URL and a key switches the backend.
ENV_SUPABASE_URL = "SUPABASE_URL"
# New Supabase projects expose ``sb_secret_...`` / ``sb_publishable_...`` keys
# instead of the legacy JWT pair, so accept either name.  Order matters: the
# secret key bypasses RLS and is the one this server-side store needs; a
# publishable key would be blocked by RLS unless a policy is added.
ENV_SUPABASE_KEY = "SUPABASE_KEY"
ENV_SUPABASE_KEY_NAMES: tuple[str, ...] = (
    "SUPABASE_KEY",
    "SUPABASE_SECRET_KEY",
    "SUPABASE_SERVICE_ROLE_KEY",
)
ENV_SUPABASE_TABLE = "SUPABASE_TABLE"
SUPABASE_DEFAULT_TABLE = "tradeit_accounts"
# Single-row table: the whole account list lives in one ``accounts`` jsonb cell.
SUPABASE_ROW_ID = "default"
SUPABASE_TIMEOUT = 8.0

BACKEND_FILE = "file"
BACKEND_SUPABASE = "supabase"
BACKEND_FILE_FALLBACK = "file-fallback"

# Table names/postgrest identifiers must stay boring; they are interpolated into
# a URL path, so anything else is rejected before a request is made.
_TABLE_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,62}$")

# ``datasets/`` is listed in .gitignore, so the default store can never be
# committed.  The file name itself is git-ignored as well.
DEFAULT_STORAGE_DIRNAME = "datasets"
ACCOUNTS_FILENAME = "accounts.json"
# The credit ledger lives beside the account store and is likewise git-ignored.
CREDIT_FILENAME = "credit_ledger.json"

FILE_VERSION = 1
_FILE_MODE = 0o600
_TEMP_PREFIX = ".accounts-"
_TEMP_SUFFIX = ".tmp"

# Store states reported by load_with_status()/summary().
STATE_OK = "ok"
STATE_EMPTY = "empty"
STATE_MISSING = "missing"
STATE_CORRUPT = "corrupt"
STATE_UNREADABLE = "unreadable"

# Credit-exhaustion classification.
EXHAUSTION_NONE = "none"
EXHAUSTION_SOME = "some"
EXHAUSTION_ALL = "all"
EXHAUSTION_UNKNOWN = "unknown"

_TOKEN_KEY = "token"
_REFRESH_KEYS = ("refresh_token", "refreshToken", "refresh")

# Windows can briefly refuse os.replace() while another handle is open.
_REPLACE_ATTEMPTS = 8
_REPLACE_BACKOFF = 0.02

# --- per-account credit knowledge -----------------------------------------
#
# The TradeIT search API reports ``credit.totalBalance`` in every search
# response, but has no read-only credit endpoint: the only way to learn an
# account's balance is to spend credit on a search.  The app therefore never
# *asks* for a balance on its own.  It records the balance the API volunteered
# during a crawl, which costs nothing extra, and remembers it here so the
# dashboard can show a running total instead of forgetting it between runs.
#
# Accounts are keyed by an opaque fingerprint of their token, never by a token,
# so the stored metadata can be summarised and shown without exposing a
# credential.
CREDIT_UNKNOWN = "unknown"       # never seen a balance (not used yet)
CREDIT_AVAILABLE = "available"   # last known balance is above zero
CREDIT_EXHAUSTED = "exhausted"   # the API said CREDIT_NOT_ENOUGH

# How many credit records are kept in the store file.  The list is bounded
# because accounts are long-lived but uploads rotate them.
MAX_CREDIT_RECORDS = 500

# A credit-check probe deliberately asks for a single record, which costs far
# less than a normal page.  The exact price is TradeIT's; this is only used to
# warn the user before a check runs, so an approximation is fine.
CREDITS_PER_SEARCH_REQUEST = 500
PROBE_PER_PAGE = 1
# Records a single credit buys, derived from the log in this repo (50 records
# per 500-credit request).  Used only for the "how many records can I still
# crawl" estimate, so it degrades gracefully if the real price changes.
RECORDS_PER_CREDIT = 0.1
# A brand-new TradeIT account is documented (by the user) to start at 3000
# credits.  This is the last-resort estimate for an account that has never been
# measured; it is clearly labelled as an estimate in the UI, never as a reading.
NEW_ACCOUNT_CREDITS = 3000


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------


def default_storage_dir() -> Path:
    """Return the directory that holds the account store by default.

    ``TRADEIT_DATA_DIR`` wins (point it at a Render persistent disk mount);
    otherwise the project's git-ignored ``datasets/`` folder is used.  The
    environment is read on every call so a redeploy can change it without code
    changes.
    """
    raw = os.environ.get(ENV_DATA_DIR, "").strip()
    if raw:
        return Path(raw).expanduser()
    return PROJECT_ROOT / DEFAULT_STORAGE_DIRNAME


def default_path() -> Path:
    """Return the account store file path, honouring the environment."""
    raw = os.environ.get(ENV_ACCOUNTS_FILE, "").strip()
    if raw:
        return Path(raw).expanduser()
    return default_storage_dir() / ACCOUNTS_FILENAME


def resolve_path(path: str | os.PathLike[str] | None = None) -> Path:
    """Resolve the caller-supplied *path* to the store file.

    ``None`` means "use the configured default".  A path that names an existing
    directory (or ends with a separator) is treated as the storage directory and
    ``accounts.json`` is appended, so ``TRADEIT_DATA_DIR``-style directory
    mounts can be passed through unchanged.  The one exception is a directory
    that is itself named ``accounts.json``: it is returned untouched so
    :func:`summary` can report it as unusable instead of silently nesting a
    second ``accounts.json`` inside it.

    Relative paths are anchored at the project root, not at whatever the process
    working directory happens to be.
    """
    if path is None:
        return default_path()

    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        candidate = PROJECT_ROOT / candidate

    looks_like_dir = candidate.is_dir() or str(path).endswith(("/", "\\"))
    if looks_like_dir and candidate.name != ACCOUNTS_FILENAME:
        return candidate / ACCOUNTS_FILENAME
    return candidate


def exists(path: str | os.PathLike[str] | None = None) -> bool:
    """True when accounts are stored (Supabase row, or the local file)."""
    if path is not None or _supabase_config() is None:
        target = resolve_path(path)
        try:
            return target.is_file()
        except OSError:
            return False
    return bool(load(None))


# ---------------------------------------------------------------------------
# Backend selection
# ---------------------------------------------------------------------------


class _SupabaseError(Exception):
    """Internal: a Supabase call failed. Message is safe to log/return."""


def _supabase_key() -> str:
    """Return the first configured Supabase key, or ``""``.

    Accepts ``SUPABASE_KEY`` plus the newer project key names, so either the
    legacy JWT/service_role value or the new ``sb_secret_...`` key works
    without renaming anything in the Render dashboard.
    """
    for name in ENV_SUPABASE_KEY_NAMES:
        value = os.environ.get(name, "").strip()
        if value:
            if name != ENV_SUPABASE_KEY and not os.environ.get(ENV_SUPABASE_KEY):
                # Making the fallback visible saves a lot of confusion when
                # only SUPABASE_SECRET_KEY was set.
                logger.info("Dùng %s làm Supabase key", name)
            return value
    return ""


def _supabase_config() -> tuple[str, str, str] | None:
    """Return ``(url, key, table)`` when Supabase is configured, else ``None``.

    The URL and any of :data:`ENV_SUPABASE_KEY_NAMES` must be set; the table
    defaults to :data:`SUPABASE_DEFAULT_TABLE`.  Reading the environment on every
    call means a Render restart can switch backends without a code change.
    """
    url = os.environ.get(ENV_SUPABASE_URL, "").strip()
    key = _supabase_key()
    if not url or not key:
        return None

    table = os.environ.get(ENV_SUPABASE_TABLE, "").strip() or SUPABASE_DEFAULT_TABLE
    if not _TABLE_RE.match(table):
        # The table name is interpolated into a URL path; refuse anything odd
        # rather than sending a malformed request.
        logger.warning(
            "%s không hợp lệ, dùng bảng mặc định %s",
            ENV_SUPABASE_TABLE,
            SUPABASE_DEFAULT_TABLE,
        )
        table = SUPABASE_DEFAULT_TABLE
    return url.rstrip("/"), key, table


def active_backend() -> str:
    """Which backend would serve a call right now: ``file`` or ``supabase``.

    This is configuration only (no network) -- :func:`summary` reports the
    backend that *actually* served the last call, including ``file-fallback``.
    """
    return BACKEND_SUPABASE if _supabase_config() is not None else BACKEND_FILE


# A configured-but-broken Supabase must not add an HTTP round trip to every
# /api/accounts poll, so failures open a short local circuit breaker.
_SUPABASE_COOLDOWN = 60.0
_supabase_down_until = 0.0
_supabase_warned = False


def _supabase_healthy() -> bool:
    return time.monotonic() >= _supabase_down_until


def _mark_supabase_down(exc: "_SupabaseError") -> None:
    global _supabase_down_until, _supabase_warned
    _supabase_down_until = time.monotonic() + _SUPABASE_COOLDOWN
    if not _supabase_warned:
        _supabase_warned = True
        logger.warning(
            "Supabase không dùng được (%s). Tạm dùng file cục bộ trong %ds.",
            exc,
            int(_SUPABASE_COOLDOWN),
        )


def _reset_supabase_state() -> None:
    """Test hook: clear the breaker so the next call tries Supabase again."""
    global _supabase_down_until, _supabase_warned
    _supabase_down_until = 0.0
    _supabase_warned = False


def _http_request(
    method: str,
    url: str,
    *,
    headers: Mapping[str, str],
    body: Any = None,
    timeout: float = SUPABASE_TIMEOUT,
) -> Any:
    """Perform one PostgREST request, translating every failure to one error.

    ``requests`` is imported here, not at module import time, so
    ``import accounts_store`` keeps working with no HTTP client installed and no
    network access.  Messages never carry the URL or key.
    """
    try:
        import requests
    except ImportError:
        raise _SupabaseError("thiếu thư viện requests") from None

    try:
        response = requests.request(
            method, url, headers=dict(headers), json=body, timeout=timeout
        )
    except Exception as exc:  # requests.RequestException and transport errors
        # repr of a requests exception embeds the URL, so only the class name.
        raise _SupabaseError(f"lỗi mạng ({exc.__class__.__name__})") from None

    if response.status_code >= 400:
        raise _SupabaseError(_describe_http_error(response.status_code))

    if response.status_code == 204 or not (getattr(response, "content", b"") or b""):
        # PostgREST answers 201/204 with an empty body for writes, and
        # ``Prefer: return=minimal`` makes that the normal case.
        return None
    try:
        return response.json()
    except ValueError:
        raise _SupabaseError("Supabase trả về dữ liệu không phải JSON") from None


def _describe_http_error(status: int) -> str:
    if status in (401, 403):
        return f"SUPABASE_KEY sai hoặc thiếu quyền (HTTP {status})"
    if status == 404:
        return (
            "không thấy bảng trên Supabase (HTTP 404); "
            f"hãy tạo bảng {SUPABASE_DEFAULT_TABLE} hoặc đặt {ENV_SUPABASE_TABLE}"
        )
    if status == 400:
        return "Supabase từ chối truy vấn (HTTP 400)"
    if status == 429:
        return "Supabase giới hạn tần suất (HTTP 429)"
    return f"Supabase trả về HTTP {status}"


def _supabase_headers(key: str, *, prefer: str | None = None) -> dict[str, str]:
    headers = {
        # Supabase's gateway wants the apikey header; PostgREST wants the bearer
        # token. They are the same value; neither is ever logged.
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    if prefer:
        headers["Prefer"] = prefer
    return headers


def _supabase_load(config: tuple[str, str, str]) -> tuple[list[dict[str, str]], dict[str, Any]]:
    url, key, table = config
    endpoint = f"{url}/rest/v1/{table}"
    query = f"?id=eq.{SUPABASE_ROW_ID}&select=accounts,updated_at"
    rows = _http_request(
        "GET", endpoint + query, headers=_supabase_headers(key, prefer=None)
    )

    if not isinstance(rows, list):
        raise _SupabaseError("Supabase trả về dữ liệu không đúng định dạng")
    if not rows:
        return [], _remote_status(
            STATE_MISSING, table, None, 0, _MESSAGES[STATE_MISSING]
        )

    row = rows[0] if isinstance(rows[0], Mapping) else {}
    updated_at = _as_text(row.get("updated_at"))
    payload = row.get("accounts")
    accounts = _extract_accounts(payload)
    if accounts is None:
        logger.warning("Dữ liệu tài khoản trên Supabase không đúng cấu trúc")
        return [], _remote_status(
            STATE_CORRUPT, table, updated_at, 0, _MESSAGES[STATE_CORRUPT]
        )
    if not accounts:
        return [], _remote_status(
            STATE_EMPTY, table, updated_at, 0, _MESSAGES[STATE_EMPTY]
        )
    return accounts, _remote_status(
        STATE_OK, table, updated_at, len(accounts), _MESSAGES[STATE_OK]
    )


def _supabase_save(config: tuple[str, str, str], accounts: list[dict[str, str]]) -> str:
    url, key, table = config
    endpoint = f"{url}/rest/v1/{table}"
    payload: dict[str, Any] = {
        "version": FILE_VERSION,
        "updated_at": _now_iso(),
        "count": len(accounts),
        "accounts": accounts,
    }
    body = {
        "id": SUPABASE_ROW_ID,
        "accounts": payload,
        "updated_at": payload["updated_at"],
    }
    # merge-duplicates turns the POST into an upsert on the primary key.
    _http_request(
        "POST",
        endpoint,
        headers=_supabase_headers(
            key, prefer="resolution=merge-duplicates,return=minimal"
        ),
        body=body,
    )
    return str(payload["updated_at"])


def _supabase_clear(config: tuple[str, str, str]) -> bool:
    url, key, table = config
    endpoint = f"{url}/rest/v1/{table}"
    headers = _supabase_headers(key, prefer="return=minimal")

    # PostgREST does not report how many rows a DELETE touched, so check first
    # rather than always claiming something was removed.
    existing = _http_request(
        "GET",
        f"{endpoint}?id=eq.{SUPABASE_ROW_ID}&select=id",
        headers=_supabase_headers(key),
    )
    if not isinstance(existing, list):
        raise _SupabaseError("Supabase trả về dữ liệu không đúng định dạng")
    _http_request("DELETE", f"{endpoint}?id=eq.{SUPABASE_ROW_ID}", headers=headers)
    return bool(existing)


# ---------------------------------------------------------------------------
# Save / load / summary / clear (backend-agnostic public API)
# ---------------------------------------------------------------------------


def save(
    accounts: Iterable[Mapping[str, Any]] | None,
    path: str | os.PathLike[str] | None = None,
) -> dict[str, Any]:
    """Replace the stored account list with *accounts* (atomically).

    Saves to Supabase when it is configured (and no explicit *path* is given),
    otherwise to the local JSON file.  A Supabase failure logs a warning and
    still writes the local file, so a crawl never dies because of storage.

    Args:
        accounts: Iterable of mappings with ``token`` and ``refresh_token``
            (``refreshToken``/``refresh`` are accepted as aliases).  Extra keys
            are ignored, so an account dict from the crawler can be passed as
            is.
        path: Store file or storage directory; forces the *file* backend.
            Defaults to the configured backend.

    Returns:
        The same secret-free summary :func:`summary` returns after the write.

    Raises:
        ValueError: The input is not a sequence of usable account mappings.
            The message names the 1-based position only; it never contains a
            token value.
        OSError: The file backend could not write the file.
    """
    # Validate first, so a bad payload is rejected identically for both backends
    # and nothing is written anywhere.
    normalized = _normalize_accounts(accounts)

    if path is None:
        config = _supabase_config()
        if config is not None:
            if not _supabase_healthy():
                info = _file_save(normalized)
                return _annotate_fallback(info, "Supabase đang tạm dừng")
            try:
                updated_at = _supabase_save(config, normalized)
            except _SupabaseError as exc:
                _mark_supabase_down(exc)
                info = _file_save(normalized)
                return _annotate_fallback(info, str(exc))
            _write_local_cache(normalized)
            logger.info(
                "Đã lưu %d tài khoản vào Supabase (bảng %s)",
                len(normalized),
                config[2],
            )
            info = _remote_status(
                STATE_OK, config[2], updated_at, len(normalized), _MESSAGES[STATE_OK]
            )
            info["backend"] = BACKEND_SUPABASE
            return info

    return _file_save(normalized, path)


def load(path: str | os.PathLike[str] | None = None) -> list[dict[str, str]]:
    """Return the stored account list, or ``[]`` when it cannot be used.

    A missing, unreadable, corrupt or unreachable store never raises: the caller
    gets an empty list and :func:`summary`/``load_with_status`` explains why.
    """
    accounts, _ = load_with_status(path)
    return accounts


def load_with_status(
    path: str | os.PathLike[str] | None = None,
) -> tuple[list[dict[str, str]], dict[str, Any]]:
    """Like :func:`load`, but also return a secret-free status summary.

    The summary has ``state`` set to ``ok`` (accounts were read), ``empty``
    (readable store without usable accounts), ``missing`` (nothing stored, the
    normal first-run/Render-redeploy case), ``corrupt`` (bad data or wrong
    shape) or ``unreadable`` (permissions/IO error, or the path is a directory).
    ``backend`` says who served the call: ``file``, ``supabase`` or
    ``file-fallback`` (Supabase was configured but failed).
    """
    if path is None:
        config = _supabase_config()
        if config is not None:
            if _supabase_healthy():
                try:
                    return _supabase_load(config)
                except _SupabaseError as exc:
                    _mark_supabase_down(exc)
                    return _file_load_fallback(str(exc))
            return _file_load_fallback("Supabase đang tạm dừng sau lỗi trước đó")

    accounts, info = _file_load(path)
    info["backend"] = BACKEND_FILE
    return accounts, info


def summary(path: str | os.PathLike[str] | None = None) -> dict[str, Any]:
    """Return a summary of the store: count, timestamp, state -- never tokens.

    Keys: ``count``, ``updated_at`` (ISO-8601 UTC, or ``None``), ``exists``,
    ``state``, ``message``, ``backend``, ``path``, ``size_bytes``, ``mode``
    (e.g. ``"0o600"``), ``has_accounts``, ``needs_upload`` and -- only after a
    fallback -- ``fallback_reason``.  ``state`` separates "no accounts stored"
    (``missing``) from "stored but unusable" (``corrupt``/``unreadable``).
    """
    accounts, info = load_with_status(path)
    info["count"] = len(accounts)
    info["has_accounts"] = bool(accounts)
    info["needs_upload"] = not accounts
    return info


def clear(path: str | os.PathLike[str] | None = None) -> bool:
    """Delete the stored accounts.  Returns True when something was removed.

    Clears Supabase when it is the active backend, and always also removes the
    local cache file so "forget my accounts" really forgets them on this host.

    Raises:
        OSError: The file backend could not delete the file.
    """
    if path is None:
        config = _supabase_config()
        if config is not None and _supabase_healthy():
            try:
                removed_remote = _supabase_clear(config)
            except _SupabaseError as exc:
                _mark_supabase_down(exc)
                logger.warning("Không xóa được tài khoản trên Supabase: %s", exc)
            else:
                _file_clear(None)
                logger.info("Đã xóa danh sách tài khoản trên Supabase")
                return removed_remote
    return _file_clear(path)


def clear_credit() -> bool:
    """Forget every recorded credit balance.  True when a ledger was removed.

    Called when the account list is cleared: balances belong to specific
    accounts, so keeping them after "forget my accounts" would leak how much
    credit those (now removed) accounts had.
    """
    target = _credit_path()
    try:
        target.unlink()
    except FileNotFoundError:
        return False
    except OSError as exc:
        raise OSError(_safe_error("Không xóa được sổ credit", exc)) from None
    logger.info("Đã xóa sổ credit đã lưu")
    return True


# ---------------------------------------------------------------------------
# Credit exhaustion tracking
# ---------------------------------------------------------------------------


def classify_exhaustion(total: int, exhausted: int) -> str:
    """Classify a run as ``none``/``some``/``all`` exhausted (or ``unknown``)."""
    if total <= 0:
        return EXHAUSTION_UNKNOWN
    if exhausted <= 0:
        return EXHAUSTION_NONE
    if exhausted >= total:
        return EXHAUSTION_ALL
    return EXHAUSTION_SOME


class CreditTracker:
    """Track which accounts ran out of credit during one crawl run.

    Accounts are identified by their **0-based position** in the list the run
    iterates -- never by token -- so tracking can never leak a credential.
    ``mark_exhausted(1)`` therefore means "the second account is out of credit".

    Exhaustion is per account and can be reversed with :meth:`mark_available`
    (useful when an account is retried with a refreshed token).
    """

    def __init__(self, accounts: int | Iterable[Any] | None = None) -> None:
        if accounts is None:
            total = 0
        elif isinstance(accounts, int):
            total = accounts
        else:
            total = len(list(accounts))
        if total < 0:
            raise ValueError("Số tài khoản không hợp lệ")
        self._total = total
        self._exhausted: set[int] = set()

    # -- state ---------------------------------------------------------
    @property
    def total(self) -> int:
        return self._total

    @property
    def exhausted_count(self) -> int:
        return len(self._exhausted)

    @property
    def available_count(self) -> int:
        return self._total - len(self._exhausted)

    @property
    def exhausted_indices(self) -> list[int]:
        """0-based positions marked exhausted, ascending."""
        return sorted(self._exhausted)

    @property
    def exhausted_positions(self) -> list[int]:
        """1-based positions marked exhausted (what the UI shows)."""
        return [index + 1 for index in sorted(self._exhausted)]

    def is_exhausted(self, index: int) -> bool:
        return self._check(index) in self._exhausted

    def account_status(self, index: int) -> str:
        """Return ``"exhausted"`` or ``"available"`` for one account."""
        return "exhausted" if self.is_exhausted(index) else "available"

    # -- mutation ------------------------------------------------------
    def mark_exhausted(self, index: int) -> None:
        """Mark the 0-based account *index* as out of credit.

        Only the position is remembered -- never the token or the raw API error,
        so :meth:`summary` can be published in the UI without leaking anything.
        """
        self._exhausted.add(self._check(index))

    def mark_available(self, index: int) -> None:
        """Clear the exhausted flag for the 0-based account *index*."""
        self._exhausted.discard(self._check(index))

    def reset(self) -> None:
        """Forget every exhaustion flag (e.g. before reusing the tracker)."""
        self._exhausted.clear()

    # -- reporting -----------------------------------------------------
    def summary(self) -> dict[str, Any]:
        """Secret-free exhaustion report for the run.

        Keys: ``total``, ``exhausted``, ``available``, ``status``
        (``none``/``some``/``all``/``unknown``), ``label`` (``"2/3"``),
        ``message`` (ready to show in the UI), ``all_exhausted``,
        ``any_exhausted`` and ``per_account`` (positions + flags only).
        """
        total = self._total
        exhausted = len(self._exhausted)
        available = total - exhausted
        status = classify_exhaustion(total, exhausted)

        if status == EXHAUSTION_NONE:
            message = f"Chưa có tài khoản nào hết credit ({total}/{total} còn dùng được)"
        elif status == EXHAUSTION_SOME:
            message = (
                f"{exhausted}/{total} tài khoản đã hết credit, "
                f"còn {available} tài khoản dùng được"
            )
        elif status == EXHAUSTION_ALL:
            message = f"Tất cả {total}/{total} tài khoản đã hết credit"
        else:
            message = "Chưa có tài khoản nào để crawl"

        return {
            "total": total,
            "exhausted": exhausted,
            "available": available,
            "status": status,
            "label": f"{exhausted}/{total}",
            "message": message,
            "all_exhausted": status == EXHAUSTION_ALL,
            "any_exhausted": exhausted > 0,
            "per_account": [
                {"position": position, "exhausted": position in self.exhausted_positions}
                for position in range(1, total + 1)
            ],
        }

    def _check(self, index: int) -> int:
        if isinstance(index, bool) or not isinstance(index, int):
            raise ValueError(f"Chỉ số tài khoản phải là số nguyên, nhận {type(index).__name__}")
        if not 0 <= index < self._total:
            raise ValueError(
                f"Chỉ số tài khoản {index} nằm ngoài danh sách ({self._total} tài khoản)"
            )
        return index


def exhaustion_summary(
    accounts: int | Iterable[Any] | None,
    exhausted_indices: Iterable[int] = (),
) -> dict[str, Any]:
    """Build a :class:`CreditTracker` from 0-based indices and summarise it."""
    tracker = CreditTracker(accounts)
    for index in exhausted_indices:
        tracker.mark_exhausted(index)
    return tracker.summary()


# ---------------------------------------------------------------------------
# Per-account credit ledger
# ---------------------------------------------------------------------------


def account_key(account: Mapping[str, Any] | str) -> str:
    """Return a stable, non-reversible identifier for one account.

    The ledger must survive a re-upload (the same token in a new Excel file is
    still the same account), so accounts are keyed by a hash of the token rather
    than by position.  The digest is truncated: it only has to separate the few
    dozen accounts in one store, never resist a determined attacker, and keeping
    it short keeps the stored JSON readable.  A token is never written here.
    """
    if isinstance(account, str):
        token = account.strip()
    else:
        token = _clean_text(account.get(_TOKEN_KEY))
    if not token:
        return ""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()[:16]


def _credit_path() -> Path:
    """Path of the credit ledger, next to the account store."""
    return resolve_path(None).with_name(CREDIT_FILENAME)


def _read_credit_ledger() -> dict[str, dict[str, Any]]:
    """Read the ledger; a missing/corrupt file is simply an empty ledger."""
    target = _credit_path()
    try:
        raw = target.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}
    except (OSError, UnicodeDecodeError):
        return {}
    try:
        payload = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return {}
    rows = payload.get("accounts") if isinstance(payload, Mapping) else None
    if not isinstance(rows, Mapping):
        return {}
    ledger: dict[str, dict[str, Any]] = {}
    for key, value in rows.items():
        if not isinstance(key, str) or not isinstance(value, Mapping):
            continue
        ledger[key] = _normalize_credit_record(value)
    return ledger


def _normalize_credit_record(record: Mapping[str, Any]) -> dict[str, Any]:
    """Keep only the known, secret-free fields of one ledger entry."""
    balance = record.get("balance")
    status = record.get("status")
    if status not in (CREDIT_AVAILABLE, CREDIT_EXHAUSTED, CREDIT_UNKNOWN):
        status = CREDIT_UNKNOWN
    return {
        "status": status,
        "balance": balance if isinstance(balance, int) and balance >= 0 else None,
        "checked_at": _as_text(record.get("checked_at")),
        "source": _as_text(record.get("source")),
    }


def _write_credit_ledger(ledger: Mapping[str, Mapping[str, Any]]) -> None:
    """Persist the ledger atomically (best effort -- never fatal)."""
    # Bound the file: keep the most recently checked entries.
    ordered = sorted(
        ledger.items(),
        key=lambda item: str(item[1].get("checked_at") or ""),
        reverse=True,
    )[:MAX_CREDIT_RECORDS]
    payload = {
        "version": 1,
        "updated_at": _now_iso(),
        "accounts": {key: dict(value) for key, value in ordered},
    }
    try:
        _write_atomic(_credit_path(), payload)
    except OSError as exc:
        logger.warning("Không lưu được sổ credit: %s", _safe_error("", exc))


def record_balance(
    account: Mapping[str, Any] | str,
    balance: Any,
    source: str = "crawl",
) -> None:
    """Record the balance the API just reported for *account*.

    Called with the ``credit.totalBalance`` of a normal search response, so it
    adds no request and no cost.  A balance of ``0`` also flips the account to
    exhausted, which is how the dashboard hides a spent account without ever
    probing it.
    """
    key = account_key(account)
    if not key or isinstance(balance, bool) or not isinstance(balance, int):
        return
    if balance < 0:
        return
    ledger = _read_credit_ledger()
    ledger[key] = {
        "status": CREDIT_AVAILABLE if balance > 0 else CREDIT_EXHAUSTED,
        "balance": balance,
        "checked_at": _now_iso(),
        "source": source,
    }
    _write_credit_ledger(ledger)


def record_exhausted(account: Mapping[str, Any] | str, source: str = "crawl") -> None:
    """Mark *account* as out of credit (the API said CREDIT_NOT_ENOUGH).

    The exact balance is unknown at that point -- the request was refused -- so
    it is recorded as ``0``: the account has nothing left to spend, which is what
    every consumer of this ledger actually needs to know.
    """
    key = account_key(account)
    if not key:
        return
    ledger = _read_credit_ledger()
    ledger[key] = {
        "status": CREDIT_EXHAUSTED,
        "balance": 0,
        "checked_at": _now_iso(),
        "source": source,
    }
    _write_credit_ledger(ledger)


def credit_records(
    accounts: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Return one credit record per supplied account, in the same order.

    Accounts the ledger has never seen come back as ``unknown`` with no balance
    -- never as a guess -- so the caller can distinguish "we know it is empty"
    from "we have no idea".
    """
    ledger = _read_credit_ledger()
    rows: list[dict[str, Any]] = []
    for account in accounts:
        key = account_key(account)
        record = ledger.get(key)
        rows.append(
            {
                "key": key,
                "status": (record or {}).get("status", CREDIT_UNKNOWN),
                "balance": (record or {}).get("balance"),
                "checked_at": (record or {}).get("checked_at"),
                "source": (record or {}).get("source"),
            }
        )
    return rows


def credit_summary(
    accounts: Iterable[Mapping[str, Any]],
    *,
    estimate_unmeasured: bool = True,
) -> dict[str, Any]:
    """Summarise the credit position of an account list.

    Returns counts and totals only -- never a token:

    * ``total_known``: sum of measured balances (exhausted accounts count 0).
    * ``total_estimated``: ``total_known`` plus a documented starting balance for
      accounts that were never measured, so a fresh upload can show a useful
      number immediately.  ``estimated_count`` says how many were guessed.
    * ``active`` / ``exhausted`` / ``unknown``: account counts by state.
    * ``records_estimate``: how many records the measured credit can still buy,
      using :data:`RECORDS_PER_CREDIT`.

    The two totals are reported separately on purpose: a guessed 3000 must never
    be indistinguishable from a balance the API actually returned.
    """
    account_list = list(accounts)
    rows = credit_records(account_list)
    active = exhausted = unknown = 0
    total_known = 0
    total_estimated = 0
    for row in rows:
        status = row["status"]
        balance = row["balance"]
        if status == CREDIT_EXHAUSTED:
            exhausted += 1
        elif status == CREDIT_AVAILABLE:
            active += 1
            total_known += int(balance or 0)
            total_estimated += int(balance or 0)
        else:
            unknown += 1
            if estimate_unmeasured:
                total_estimated += NEW_ACCOUNT_CREDITS

    usable = total_estimated if estimate_unmeasured else total_known
    # An account with no recorded balance is *not* excluded from the total: the
    # user's expectation is "how much can I still crawl", and an unused account
    # certainly can be crawled.  Its starting balance is flagged separately so
    # the number is never mistaken for a measurement.
    return {
        "count": len(account_list),
        "active": active,
        "exhausted": exhausted,
        "unknown": unknown,
        "usable": active + (unknown if estimate_unmeasured else 0),
        "total_known": total_known,
        "total_estimated": total_estimated,
        "estimated_count": unknown if estimate_unmeasured else 0,
        "records_estimate": int(usable * RECORDS_PER_CREDIT),
        "accounts": [
            {
                "position": index + 1,
                "status": row["status"],
                "balance": row["balance"],
                "checked_at": row["checked_at"],
            }
            for index, row in enumerate(rows)
        ],
    }


def active_accounts(
    accounts: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Return the accounts still worth trying, in their original order.

    An account is skipped only when the ledger *knows* it is empty
    (``exhausted``).  Accounts with an unknown balance are kept: refusing them
    would mean a first crawl could never start, since nothing is known yet.

    This is what makes a spent account disappear from the list the crawler
    iterates without ever deleting the user's stored credentials.
    """
    account_list = list(accounts)
    rows = credit_records(account_list)
    keep: list[dict[str, Any]] = []
    for account, row in zip(account_list, rows):
        if row["status"] == CREDIT_EXHAUSTED:
            continue
        keep.append(account)
    return keep


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


_MESSAGES = {
    STATE_OK: "Đã có danh sách tài khoản đã lưu",
    STATE_EMPTY: "File tài khoản không chứa tài khoản nào",
    STATE_MISSING: "Chưa có tài khoản nào được lưu",
    STATE_CORRUPT: "File tài khoản bị lỗi định dạng, cần upload lại",
    STATE_UNREADABLE: "Không đọc được file tài khoản, cần upload lại",
}


def _now_iso() -> str:
    """Current UTC time as ISO-8601 (same format the crawler uses)."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# -- file provider (the original behaviour, unchanged) ----------------------


def _file_save(
    normalized: list[dict[str, str]],
    path: str | os.PathLike[str] | None = None,
) -> dict[str, Any]:
    """Write the account list to the local JSON file (atomic replace)."""
    target = resolve_path(path)
    payload: dict[str, Any] = {
        "version": FILE_VERSION,
        "updated_at": _now_iso(),
        "count": len(normalized),
        "accounts": normalized,
    }
    _write_atomic(target, payload)
    logger.info("Đã lưu %d tài khoản vào %s", len(normalized), target)
    info = _file_load(target)[1]
    info["count"] = len(normalized)
    info["has_accounts"] = bool(normalized)
    info["needs_upload"] = not normalized
    info["backend"] = BACKEND_FILE
    return info


def _file_load(
    path: str | os.PathLike[str] | None = None,
) -> tuple[list[dict[str, str]], dict[str, Any]]:
    """Read the local JSON file; never raises."""
    target = resolve_path(path)
    mtime = _file_mtime(target)

    try:
        stat = target.stat()
    except FileNotFoundError:
        return [], _status(STATE_MISSING, target, None, None, _MESSAGES[STATE_MISSING])
    except OSError:
        return [], _status(
            STATE_UNREADABLE, target, None, mtime, _MESSAGES[STATE_UNREADABLE]
        )

    if not stat.st_size and target.is_file():
        # An empty file is as useless as a missing one, but it *was* created.
        return [], _status(STATE_EMPTY, target, None, mtime, _MESSAGES[STATE_EMPTY])

    try:
        raw = target.read_text(encoding="utf-8")
    except FileNotFoundError:
        return [], _status(STATE_MISSING, target, None, None, _MESSAGES[STATE_MISSING])
    except (OSError, UnicodeDecodeError):
        return [], _status(
            STATE_UNREADABLE, target, None, mtime, _MESSAGES[STATE_UNREADABLE]
        )

    try:
        payload = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        logger.warning("File tài khoản bị lỗi định dạng: %s", target)
        return [], _status(STATE_CORRUPT, target, None, mtime, _MESSAGES[STATE_CORRUPT])

    updated_at = _stored_timestamp(payload) or mtime
    accounts = _extract_accounts(payload)
    if accounts is None:
        logger.warning("File tài khoản không đúng cấu trúc: %s", target)
        return [], _status(STATE_CORRUPT, target, None, updated_at, _MESSAGES[STATE_CORRUPT])

    if not accounts:
        return [], _status(
            STATE_EMPTY, target, updated_at, updated_at, _MESSAGES[STATE_EMPTY]
        )

    return accounts, _status(STATE_OK, target, updated_at, updated_at, _MESSAGES[STATE_OK])


def _file_clear(path: str | os.PathLike[str] | None = None) -> bool:
    """Delete the local JSON file; True when a file was actually removed."""
    target = resolve_path(path)
    try:
        target.unlink()
    except FileNotFoundError:
        return False
    except OSError as exc:
        raise OSError(_safe_error("Không xóa được file tài khoản", exc)) from None
    logger.info("Đã xóa danh sách tài khoản đã lưu: %s", target)
    return True


def _write_local_cache(accounts: list[dict[str, str]]) -> None:
    """Best-effort local mirror of a successful Supabase save.

    It is not the source of truth (Supabase is); it keeps a cold start useful if
    the network is briefly unavailable.  Failures are ignored on purpose.
    """
    try:
        _file_save(accounts)
    except (OSError, ValueError):
        pass


def _file_load_fallback(reason: str) -> tuple[list[dict[str, str]], dict[str, Any]]:
    """Serve reads from the file backend, flagged as ``file-fallback``."""
    accounts, info = _file_load(None)
    return accounts, _annotate_fallback(info, reason)


def _annotate_fallback(info: dict[str, Any], reason: str) -> dict[str, Any]:
    """Mark a file-backed summary as a Supabase fallback (no secrets added)."""
    info["backend"] = BACKEND_FILE_FALLBACK
    # The reason is our own fixed wording / an HTTP status phrase; it never
    # contains the URL, the key or a token.
    info["fallback_reason"] = reason
    return info


# -- remote (Supabase) summary shape ----------------------------------------


def _remote_status(
    state: str,
    table: str,
    updated_at: str | None,
    count: int,
    message: str,
) -> dict[str, Any]:
    """Summary for the Supabase backend: no local path/size/mode to report."""
    return {
        "count": count,
        "updated_at": updated_at,
        "exists": state != STATE_MISSING,
        "state": state,
        "message": message,
        # The table name is not a secret and helps debugging; URL/key never.
        "path": f"supabase:{table}",
        "size_bytes": None,
        "mode": None,
        "has_accounts": count > 0,
        "needs_upload": count == 0,
        "backend": BACKEND_SUPABASE,
    }


def _as_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _file_mtime(target: Path) -> str | None:
    try:
        return datetime.fromtimestamp(target.stat().st_mtime, timezone.utc).isoformat(
            timespec="seconds"
        )
    except OSError:
        return None


def _status(
    state: str,
    target: Path,
    updated_at: str | None,
    fallback_updated_at: str | None,
    message: str,
) -> dict[str, Any]:
    try:
        stat = target.stat()
        size = stat.st_size
        mode = f"0o{stat.st_mode & 0o777:03o}"
        exists_flag = target.is_file()
    except OSError:
        size = None
        mode = None
        exists_flag = False
    return {
        "count": 0,
        "updated_at": updated_at or fallback_updated_at,
        "exists": exists_flag,
        "state": state,
        "message": message,
        "path": str(target),
        "size_bytes": size,
        "mode": mode,
        "has_accounts": False,
        "needs_upload": True,
    }


def _stored_timestamp(payload: Any) -> str | None:
    if not isinstance(payload, Mapping):
        return None
    for key in ("updated_at", "updatedAt", "saved_at"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _extract_accounts(payload: Any) -> list[dict[str, str]] | None:
    """Pull usable account pairs out of a decoded store file.

    Returns ``None`` when the shape is wrong (a corrupt file), or a list
    (possibly empty) of accounts.  Individual malformed rows are skipped so one
    bad hand-edited line does not discard every other account.
    """
    if isinstance(payload, Mapping):
        rows = payload.get("accounts")
        if rows is None:
            rows = payload.get("data")
        if not isinstance(rows, list):
            return None
    elif isinstance(payload, list):
        rows = payload
    else:
        return None

    accounts: list[dict[str, str]] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        token = _clean_text(row.get(_TOKEN_KEY))
        refresh = ""
        for key in _REFRESH_KEYS:
            refresh = _clean_text(row.get(key))
            if refresh:
                break
        if token and refresh:
            accounts.append({"token": token, "refresh_token": refresh})
    return accounts


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _normalize_accounts(
    accounts: Iterable[Mapping[str, Any]] | None,
) -> list[dict[str, str]]:
    """Validate/clean the caller's accounts without ever echoing a value."""
    if accounts is None:
        return []
    if isinstance(accounts, (str, bytes, Mapping)):
        raise ValueError("Danh sách tài khoản phải là một danh sách các object")

    normalized: list[dict[str, str]] = []
    for position, item in enumerate(accounts, start=1):
        if not isinstance(item, Mapping):
            raise ValueError(f"Mục tài khoản thứ {position} không phải object")
        token = _clean_text(item.get(_TOKEN_KEY))
        refresh = ""
        for key in _REFRESH_KEYS:
            refresh = _clean_text(item.get(key))
            if refresh:
                break
        if not token or not refresh:
            raise ValueError(
                f"Tài khoản thứ {position} thiếu token hoặc refresh_token"
            )
        normalized.append({"token": token, "refresh_token": refresh})
    return normalized


def _write_atomic(target: Path, payload: Mapping[str, Any]) -> None:
    """Write *payload* as JSON via a temp file + ``os.replace``.

    A crash mid-write leaves either the old file or the new file, never a
    half-written credential file.

    On Windows ``os.replace`` fails with ``PermissionError`` when another thread
    or process has the destination open for a moment (antivirus scanners and
    concurrent saves do this), so the swap is retried briefly.  No lock is held
    between processes: the last writer wins, which is fine for a credential
    cache.
    """
    directory = target.parent
    try:
        directory.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise OSError(_safe_error("Không tạo được thư mục lưu tài khoản", exc)) from None

    text = json.dumps(payload, ensure_ascii=False, indent=2)
    temp_path: Path | None = None
    try:
        handle = tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=str(directory),
            prefix=_TEMP_PREFIX,
            suffix=_TEMP_SUFFIX,
            delete=False,
        )
        temp_path = Path(handle.name)
        try:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        finally:
            handle.close()
        _chmod_private(temp_path)
        _replace_with_retry(temp_path, target)
        temp_path = None
    except OSError as exc:
        raise OSError(_safe_error("Không ghi được file tài khoản", exc)) from None
    finally:
        if temp_path is not None:
            try:
                temp_path.unlink()
            except OSError:
                pass

    # os.replace copies the temp file's permissions on POSIX, but be explicit:
    # on Windows this is a no-op beyond the read-only bit, which is fine.
    _chmod_private(target)


def _replace_with_retry(
    source: Path, target: Path, attempts: int = _REPLACE_ATTEMPTS
) -> None:
    """``os.replace`` with a short retry for Windows sharing violations."""
    for attempt in range(1, attempts + 1):
        try:
            os.replace(source, target)
            return
        except PermissionError:
            if attempt >= attempts:
                raise
            time.sleep(_REPLACE_BACKOFF * attempt)


_chmod_warned = False


def _chmod_private(path: Path) -> bool:
    """Best-effort ``chmod 0600``.  Returns True when the OS accepted it.

    On Windows ``os.chmod`` reports success while only toggling the read-only
    bit, so a True return does **not** mean the file is private there. When the
    call fails outright, or when running on a platform whose ``chmod`` cannot
    express an ACL, a single warning is logged so an operator knows the file
    inherits its directory's permissions (see the module docstring for the
    mitigations). The warning is emitted at most once per process: it describes a
    property of the platform, not of each save.
    """
    global _chmod_warned
    try:
        os.chmod(path, _FILE_MODE)
        enforced = os.name != "nt"
    except (OSError, NotImplementedError):
        enforced = False

    if not enforced and not _chmod_warned:
        _chmod_warned = True
        if os.name == "nt":
            logger.warning(
                "Windows không áp đặt được quyền 0600 cho file tài khoản; file thừa "
                "hưởng quyền của thư mục chứa nó. Hãy dùng Supabase, hoặc đặt "
                "TRADEIT_ACCOUNTS_FILE trong thư mục riêng của bạn (không dùng thư "
                "mục shared/roaming), hoặc giới hạn bằng icacls. File: %s",
                path,
            )
        else:
            logger.warning(
                "Không đặt được quyền 0600 cho file tài khoản (file có thể đọc được "
                "bởi người dùng khác). File: %s",
                path,
            )
    return enforced


def _safe_error(prefix: str, exc: OSError) -> str:
    """Build an error message without leaking file contents or secrets."""
    detail = exc.strerror or exc.__class__.__name__
    return f"{prefix}: {detail}"
