#!/usr/bin/env python3
"""TradeIT buyer-search API crawler (single-account, resume-friendly).

The tool uses one cookie at a time (provided by the user) to call:

    POST https://www.tradeit.global/api/crm/bl/search?perPage=50&curPage=N

It saves each page to ``data/<curPage>.json`` and logs progress to
``logs/crawler.log``. On a credit/token error it stops and asks the user to
paste a cookie they already have, then continues from the same page.

No account creation, no automated cookie harvesting.
"""

from __future__ import annotations

import argparse
import base64
import json
import logging
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import requests

BASE_URL = "https://www.tradeit.global/api/crm/bl/search"
DEFAULT_BODY: dict[str, Any] = {"importer": "netherland", "hsCode": "090411"}

DATA_DIR = Path("data")
LOG_DIR = Path("logs")
STATE_FILE = Path("state.json")
CRAWLER_LOG = LOG_DIR / "crawler.log"
COOKIES_USED_LOG = LOG_DIR / "cookies_used.log"

MAX_SERVER_RETRIES = 3
DEFAULT_DELAY = 1.5
DEFAULT_PER_PAGE = 50

CRM_TOKEN_NAME = "_TaaS.auth.crm.token"
CRM_RF_TOKEN_NAME = "_TaaS.auth.crm.rf_token"

logger = logging.getLogger("tradeit_crawler")


class CreditError(Exception):
    """Raised when the account has run out of credit (code CREDIT_NOT_ENOUGH)."""


class AuthError(Exception):
    """Raised when the token expired / is unauthorized (HTTP 401 or 403)."""


def _force_utf8() -> None:
    """Best-effort reconfigure of stdout/stderr to UTF-8 (needed on Windows)."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        except (AttributeError, ValueError):
            pass


def setup_logging() -> None:
    """Configure file + console logging. Never logs full cookie values."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    logger.setLevel(logging.INFO)
    if logger.handlers:
        return

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )

    file_handler = logging.FileHandler(CRAWLER_LOG, encoding="utf-8")
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(fmt)
    logger.addHandler(console_handler)


def _now_iso() -> str:
    """Return the current UTC timestamp in ISO-8601 format."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def parse_account_id(cookie: str) -> Optional[str]:
    """Best-effort extraction of an account id from a JWT inside the cookie.

    Decodes the JWT payload without verifying the signature (used only for the
    cookie audit log). Returns ``None`` if nothing usable is found.
    """
    for part in cookie.split(";"):
        part = part.strip()
        if not part or "=" not in part:
            continue
        name, _, value = part.partition("=")
        if "token" not in name.lower():
            continue
        token = value.strip()
        segments = token.split(".")
        if len(segments) != 3:
            continue
        payload = segments[1]
        padded = payload + "=" * (-len(payload) % 4)
        try:
            decoded = base64.urlsafe_b64decode(padded.encode("ascii"))
            claims = json.loads(decoded)
        except (ValueError, json.JSONDecodeError):
            continue
        if isinstance(claims, dict):
            for key in ("accountId", "account_id", "sub", "userId", "id"):
                if claims.get(key) is not None:
                    return str(claims[key])
    return None


def _clean_cookie_value(raw: str, name: str) -> str:
    """Strip a ``name=`` prefix and trailing ``;`` from a pasted cookie value."""
    value = raw.strip().rstrip(";").strip()
    if value.startswith(name + "="):
        value = value[len(name) + 1:]
    elif "=" in value:
        prefix = value.split("=", 1)[0].strip().lower()
        if prefix.endswith("token"):
            value = value.split("=", 1)[1]
    return value.strip()


def prompt_cookies() -> str:
    """Prompt for each cookie value separately and combine them.

    Asks for ``_TaaS.auth.crm.token`` and ``_TaaS.auth.crm.rf_token`` on their
    own lines to avoid mix-ups. If the user pastes a full ``name=value; ...``
    line into the first prompt, it is accepted as-is.
    """
    print("[INFO] Nhập cookie (mỗi giá trị dán riêng 1 dòng):")
    raw_token = input(f"  {CRM_TOKEN_NAME} = ").strip()

    if CRM_RF_TOKEN_NAME in raw_token or (";" in raw_token and "=" in raw_token):
        return raw_token.strip()

    token = _clean_cookie_value(raw_token, CRM_TOKEN_NAME)
    raw_rf = input(f"  {CRM_RF_TOKEN_NAME} = ").strip()
    rf_token = _clean_cookie_value(raw_rf, CRM_RF_TOKEN_NAME)

    parts = []
    if token:
        parts.append(f"{CRM_TOKEN_NAME}={token}")
    if rf_token:
        parts.append(f"{CRM_RF_TOKEN_NAME}={rf_token}")
    return "; ".join(parts)


def load_cookie(cookie_file: Optional[Path], prompt_if_missing: bool = True) -> str:
    """Load a cookie from ``cookie_file`` or prompt the user interactively.

    Args:
        cookie_file: Optional path to a file containing the raw cookie string.
        prompt_if_missing: When True, prompt the user if no file is available.

    Returns:
        The cookie string.

    Raises:
        SystemExit: If no cookie is available and prompting is disabled.
    """
    if cookie_file is not None:
        if cookie_file.is_file():
            cookie = cookie_file.read_text(encoding="utf-8").strip()
            if cookie:
                logger.info("Đã đọc cookie từ %s", cookie_file)
                return cookie
            logger.warning("File cookie rỗng: %s", cookie_file)
        else:
            logger.warning("Không tìm thấy file cookie: %s", cookie_file)

    if not prompt_if_missing:
        raise SystemExit("Không có cookie. Hãy cung cấp --cookie-file hoặc cookies.txt.")

    cookie = prompt_cookies()
    if not cookie:
        raise SystemExit("Cookie trống, dừng chương trình.")
    return cookie


def log_cookie_used(cookie: str) -> None:
    """Append timestamp + parsed account id to the cookie audit log."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    account_id = parse_account_id(cookie) or "unknown"
    with COOKIES_USED_LOG.open("a", encoding="utf-8") as fh:
        fh.write(f"{_now_iso()} account_id={account_id}\n")


def build_headers(cookie: str) -> dict[str, str]:
    """Build the required HTTP headers including the cookie."""
    return {
        "Content-Type": "application/json",
        "Accept": "*/*",
        "Origin": "https://www.tradeit.global",
        "Referer": "https://www.tradeit.global/en/search-home/buyer-search",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36"
        ),
        "Cookie": cookie,
    }


def fetch_page(
    session: requests.Session,
    cookie: str,
    cur_page: int,
    per_page: int,
    body: dict[str, Any],
) -> dict[str, Any]:
    """Fetch a single search page and return the parsed JSON response.

    Handles 429 (rate limit) and 5xx (server error) with retries/backoff.

    Raises:
        CreditError: When the account ran out of credit.
        AuthError: When the token is expired / unauthorized.
    """
    params = {"perPage": per_page, "curPage": cur_page}
    headers = build_headers(cookie)

    for attempt in range(1, MAX_SERVER_RETRIES + 1):
        try:
            response = session.post(
                BASE_URL, params=params, headers=headers, json=body, timeout=30
            )
        except requests.RequestException as exc:
            if attempt >= MAX_SERVER_RETRIES:
                raise
            backoff = 2 ** (attempt - 1)
            logger.warning(
                "Lỗi mạng curPage=%s (%s), thử lại sau %ss...", cur_page, exc, backoff
            )
            time.sleep(backoff)
            continue

        status = response.status_code

        if status == 429:
            retry_after = response.headers.get("Retry-After")
            try:
                wait = float(retry_after) if retry_after else 2 ** attempt
            except ValueError:
                wait = 2 ** attempt
            logger.warning("429 rate limit curPage=%s, sleep %ss", cur_page, wait)
            time.sleep(wait)
            continue

        if 500 <= status < 600:
            if attempt >= MAX_SERVER_RETRIES:
                response.raise_for_status()
            backoff = 2 ** (attempt - 1)
            logger.warning(
                "HTTP %s curPage=%s, thử lại sau %ss...", status, cur_page, backoff
            )
            time.sleep(backoff)
            continue

        payload: dict[str, Any] = {}
        try:
            payload = response.json()
        except ValueError:
            payload = {}

        code = str(payload.get("code", ""))

        if status in (401, 403) or code in {"common.UNAUTHORIZED", "common.FORBIDDEN"}:
            raise AuthError(f"HTTP {status} code={code}")

        if code == "credit.CREDIT_NOT_ENOUGH":
            raise CreditError(f"HTTP {status} code={code}")

        if status == 400:
            logger.error("HTTP 400 curPage=%s code=%s", cur_page, code)
            raise requests.HTTPError(f"HTTP 400 code={code}", response=response)

        response.raise_for_status()
        return payload

    raise RuntimeError(f"Hết số lần thử cho curPage={cur_page}")


def save_page(items: list[Any], page: int, force: bool) -> bool:
    """Write ``items`` to ``data/<page>.json``.

    Returns True if written, False if skipped because the file already exists.
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    target = page_file_path(page)
    if target.exists() and not force:
        logger.info("Bỏ qua data/%s.json (đã tồn tại).", page)
        return False
    with target.open("w", encoding="utf-8") as fh:
        json.dump(items, fh, ensure_ascii=False, indent=2)
    logger.info("Saved data/%s.json", page)
    return True


def handle_credit_error(cur_page: int) -> str:
    """Print a stop notice and return a freshly pasted cookie."""
    print()
    print("[STOP] Account hết credit hoặc token hết hạn.")
    print(f"Đã crawl đến curPage = {cur_page}.")
    print("Vui lòng nhập cookie mới:")
    cookie = prompt_cookies()
    if not cookie:
        raise SystemExit("Cookie trống, dừng chương trình.")
    log_cookie_used(cookie)
    return cookie


def load_state() -> Optional[dict[str, Any]]:
    """Return saved state (curPage + known total/crawled) from state.json."""
    if not STATE_FILE.is_file():
        return None
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        cur_page = int(data["curPage"])
    except (ValueError, KeyError, json.JSONDecodeError):
        logger.warning("state.json không hợp lệ, bỏ qua.")
        return None

    def _as_int(key: str) -> Optional[int]:
        value = data.get(key)
        return value if isinstance(value, int) else None

    return {"curPage": cur_page, "total": _as_int("total"), "crawled": _as_int("crawled")}


def save_state(
    cur_page: int, total: Optional[int] = None, crawled: Optional[int] = None
) -> None:
    """Persist curPage (last completed page) + total/crawled counts to state.json."""
    payload: dict[str, Any] = {"curPage": cur_page, "updatedAt": _now_iso()}
    if total is not None:
        payload["total"] = total
    if crawled is not None:
        payload["crawled"] = crawled
    STATE_FILE.write_text(json.dumps(payload), encoding="utf-8")


def page_file_path(page: int) -> Path:
    """Return the output path for a given page."""
    return DATA_DIR / f"{page}.json"


def count_records_in_file(page: int) -> int:
    """Return the number of records stored in data/<page>.json (0 if unreadable)."""
    try:
        existing = json.loads(page_file_path(page).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return 0
    return len(existing) if isinstance(existing, list) else 0


def count_existing_files() -> int:
    """Return the number of page files already present in data/."""
    if not DATA_DIR.is_dir():
        return 0
    return len(list(DATA_DIR.glob("*.json")))


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="TradeIT buyer-search crawler")
    parser.add_argument("--start-page", type=int, default=1)
    parser.add_argument("--end-page", type=int, default=None)
    parser.add_argument("--per-page", type=int, default=DEFAULT_PER_PAGE)
    parser.add_argument("--delay", type=float, default=DEFAULT_DELAY)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--cookie-file", type=Path, default=None)
    parser.add_argument(
        "--body",
        type=str,
        default=None,
        help="Body JSON tùy chỉnh (mặc định: %s)" % json.dumps(DEFAULT_BODY),
    )
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    """Entry point: run the crawl loop until finished or interrupted."""
    _force_utf8()
    setup_logging()
    args = parse_args(argv)

    body = DEFAULT_BODY
    if args.body:
        try:
            body = json.loads(args.body)
        except json.JSONDecodeError:
            logger.error("--body không phải JSON hợp lệ, dùng body mặc định.")

    cookie_file = args.cookie_file
    if cookie_file is None and Path("cookies.txt").is_file():
        cookie_file = Path("cookies.txt")

    cookie = load_cookie(cookie_file)
    log_cookie_used(cookie)

    session = requests.Session()

    total_records: Optional[int] = None
    records_crawled = 0
    start_page = args.start_page

    state = None if args.force else load_state()
    if state is not None:
        resume_page = state["curPage"] + 1
        if resume_page > start_page:
            start_page = resume_page
            total_records = state.get("total")
            records_crawled = state.get("crawled") or 0
            logger.info(
                "Resume từ state.json: đã crawl %s records, tiếp tục curPage=%s",
                records_crawled,
                start_page,
            )

    cur_page = start_page
    logger.info("Bắt đầu crawl từ curPage=%s", cur_page)

    if total_records is not None and records_crawled >= total_records:
        logger.info("Đã crawl đủ %s records, không cần chạy tiếp.", total_records)
        return 0

    pages_saved = 0

    def on_sigint(signum: int, frame: Any) -> None:
        save_state(cur_page, total_records, records_crawled)
        logger.info("Đã nhận Ctrl+C. Lưu state curPage=%s.", cur_page)
        raise KeyboardInterrupt

    previous_handler = signal.getsignal(signal.SIGINT)
    signal.signal(signal.SIGINT, on_sigint)

    try:
        while True:
            if args.end_page is not None and cur_page > args.end_page:
                logger.info("Đã đạt --end-page=%s, dừng.", args.end_page)
                break

            if not args.force and page_file_path(cur_page).exists():
                skipped = count_records_in_file(cur_page)
                records_crawled += skipped
                logger.info(
                    "Bỏ qua curPage=%s (data/%s.json đã tồn tại, %s records).",
                    cur_page,
                    cur_page,
                    skipped,
                )
                if skipped < args.per_page:
                    logger.info(
                        "Trang %s có %s records (< %s) -> trang cuối, dừng.",
                        cur_page,
                        skipped,
                        args.per_page,
                    )
                    break
                cur_page += 1
                if total_records is not None and records_crawled >= total_records:
                    logger.info("Đã crawl đủ %s records.", total_records)
                    break
                continue

            try:
                payload = fetch_page(session, cookie, cur_page, args.per_page, body)
            except (CreditError, AuthError) as exc:
                logger.warning("Dừng do lỗi xác thực/credit: %s", exc)
                cookie = handle_credit_error(cur_page)
                logger.info("Tiếp tục từ curPage=%s", cur_page)
                continue

            data = payload.get("data") or {}
            items = data.get("items")
            if not isinstance(items, list):
                logger.warning(
                    "curPage=%s không có data.items, bỏ qua.", cur_page
                )
                cur_page += 1
                time.sleep(args.delay)
                continue

            row_count = data.get("rowCount", len(items))
            total = data.get("total")
            credit = (payload.get("credit") or {}).get("totalBalance")

            if isinstance(total, int):
                total_records = total

            if save_page(items, cur_page, args.force):
                pages_saved += 1
            records_crawled += len(items)

            logger.info(
                "GET curPage=%s ... 200 OK, rowCount=%s, credit=%s, crawled=%s/%s",
                cur_page,
                row_count,
                credit,
                records_crawled,
                total_records if total_records is not None else "?",
            )

            save_state(cur_page, total_records, records_crawled)

            if isinstance(row_count, int) and row_count < args.per_page:
                logger.info("Trang cuối (rowCount=%s).", row_count)
                break

            if total_records is not None and records_crawled >= total_records:
                logger.info("Đã crawl đủ %s records.", total_records)
                break

            cur_page += 1
            time.sleep(args.delay)
    except KeyboardInterrupt:
        logger.info("Dừng bởi người dùng tại curPage=%s.", cur_page)
    finally:
        signal.signal(signal.SIGINT, previous_handler)
        total_files = count_existing_files()
        logger.info(
            "Đã crawl xong. Tổng: %s files, %s records (phiên này: %s files).",
            total_files,
            records_crawled,
            pages_saved,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
