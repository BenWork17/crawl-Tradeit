"""Small web dashboard for running the TradeIT crawler."""

from __future__ import annotations

import json
import re
import threading
import time
from pathlib import Path
from typing import Any

import requests
from flask import Flask, jsonify, redirect, render_template, request, send_file, url_for

import merge_data
import tradeit_crawler as crawler


app = Flask(__name__)
job_lock = threading.Lock()
job: dict[str, Any] = {
    "status": "idle",
    "message": "Sẵn sàng",
    "page": 0,
    "records": 0,
    "total": None,
    "account_index": 0,
    "account_total": 0,
    "account_label": "",
    "started_at": None,
}
stop_event = threading.Event()


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


def _parse_accounts(raw: str) -> list[dict[str, str]]:
    """Parse multiline accounts. Each line can be token|refresh or token,refresh."""
    accounts: list[dict[str, str]] = []
    for line in raw.splitlines():
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        token = ""
        refresh = ""
        if "rf_token=" in text or "_TaaS.auth.crm.rf_token=" in text:
            token_match = re.search(
                r"(?:_TaaS\.auth\.crm\.token|token)\s*=\s*([^;|,\t]+)", text, re.I
            )
            refresh_match = re.search(
                r"(?:_TaaS\.auth\.crm\.rf_token|rf_token)\s*=\s*([^;|,\t]+)",
                text,
                re.I,
            )
            if token_match and refresh_match:
                token = token_match.group(1).strip()
                refresh = refresh_match.group(1).strip()
        else:
            parts = [part.strip() for part in re.split(r"[\t,|]", text) if part.strip()]
            if len(parts) >= 2:
                token, refresh = parts[0], parts[1]
        if token and refresh:
            accounts.append({"token": token, "refresh_token": refresh})
    return accounts


def _update(**values: Any) -> None:
    with job_lock:
        job.update(values)


def _run(options: dict[str, Any]) -> None:
    page = options["start_page"]
    total: int | None = None
    seen: set[str] = options["seen"]
    accounts: list[dict[str, str]] = options["accounts"]
    body = {"importer": options["importer"], "hsCode": options["hs_code"]}

    if not options["force"]:
        saved_state = crawler.load_state()
        if saved_state:
            total = saved_state.get("total")

    _update(
        status="running",
        message="Đang chuẩn bị crawl",
        page=page,
        records=len(seen),
        total=total,
        account_index=0,
        account_total=len(accounts),
        account_label="",
    )

    try:
        if not accounts:
            raise ValueError("Chưa có tài khoản hợp lệ")

        for account_index, account in enumerate(accounts, start=1):
            if stop_event.is_set():
                break

            cookie = (
                f"{crawler.CRM_TOKEN_NAME}={account['token']}; "
                f"{crawler.CRM_RF_TOKEN_NAME}={account['refresh_token']}"
            )
            crawler.log_cookie_used(cookie)

            _update(
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
                while not stop_event.is_set():
                    if options["end_page"] is not None and page > options["end_page"]:
                        break

                    if not options["force"] and crawler.page_file_path(page).exists():
                        _update(
                            page=page,
                            records=len(seen),
                            message=(
                                f"Bỏ qua trang {page} đã có dữ liệu; "
                                f"tiếp tục {account_index}/{len(accounts)}"
                            ),
                        )
                        page += 1
                        continue

                    payload = fetch_page(session, cookie, page, options["per_page"], body)
                    data = payload.get("data") or {}
                    items = data.get("items")
                    if not isinstance(items, list):
                        raise RuntimeError(f"API không trả về data.items ở trang {page}")

                    row_count = data.get("rowCount", len(items))
                    if isinstance(data.get("total"), int):
                        total = data["total"]

                    unique_items, _skipped = _dedupe_items(items, seen)
                    crawler.save_page(unique_items, page, options["force"])

                    _update(
                        page=page,
                        records=len(seen),
                        total=total,
                        message=(
                            f"Tài khoản {account_index}/{len(accounts)}: "
                            f"trang {page} đã lưu {len(unique_items)} bản ghi mới"
                        ),
                    )
                    crawler.save_state(page, total, len(seen))

                    if isinstance(row_count, int) and row_count < options["per_page"]:
                        page += 1
                        break
                    if total is not None and len(seen) >= total:
                        page += 1
                        break

                    page += 1
                    stop_event.wait(options["delay"])
            except (crawler.AuthError, crawler.CreditError) as exc:
                if account_index >= len(accounts):
                    raise
                _update(
                    message=(
                        f"Tài khoản {account_index}/{len(accounts)} dừng ở trang {page}: "
                        f"{exc}. Chuyển sang tài khoản kế tiếp."
                    ),
                    records=len(seen),
                    total=total,
                )
            finally:
                session.close()

        if stop_event.is_set():
            _update(status="stopped", message="Đã dừng theo yêu cầu", records=len(seen))
        else:
            _update(status="completed", message=f"Hoàn tất: {len(seen)} bản ghi", records=len(seen))
    except (crawler.AuthError, crawler.CreditError) as exc:
        _update(
            status="error",
            message=f"Không crawl được tài khoản cuối ở trang {page}: {exc}.",
            records=len(seen),
            total=total,
        )
    except (requests.RequestException, RuntimeError, OSError, ValueError) as exc:
        _update(status="error", message=str(exc))


@app.get("/")
def index():
    with job_lock:
        current = dict(job)
    return render_template("index.html", job=current)


@app.post("/api/jobs")
def start_job():
    with job_lock:
        if job["status"] == "running":
            return jsonify({"error": "Đang có một job chạy"}), 409

    raw_accounts = request.form.get("accounts", "")
    accounts = _parse_accounts(raw_accounts)
    if not accounts:
        return jsonify({"error": "Vui lòng nhập danh sách tài khoản hợp lệ"}), 400

    try:
        start_page = max(1, int(request.form.get("start_page", "1")))
        end_raw = request.form.get("end_page", "").strip()
        end_page = int(end_raw) if end_raw else None
        per_page = min(50, max(1, int(request.form.get("per_page", "50"))))
        delay = max(0.0, float(request.form.get("delay", "1.5")))
    except ValueError:
        return jsonify({"error": "Thông số trang, số bản ghi hoặc delay không hợp lệ"}), 400

    if end_page is not None and end_page < start_page:
        return jsonify({"error": "Trang kết thúc phải lớn hơn hoặc bằng trang bắt đầu"}), 400

    seen = _load_seen_fingerprints()
    options = {
        "start_page": start_page,
        "end_page": end_page,
        "per_page": per_page,
        "delay": delay,
        "force": request.form.get("force") == "on",
        "importer": request.form.get("importer", "netherland").strip() or "netherland",
        "hs_code": request.form.get("hs_code", "090411").strip() or "090411",
        "accounts": accounts,
        "seen": seen,
    }

    stop_event.clear()
    with job_lock:
        job.update(
            status="running",
            message="Đang khởi động",
            page=start_page,
            records=len(seen),
            total=None,
            account_index=0,
            account_total=len(accounts),
            account_label="",
            started_at=time.time(),
        )

    threading.Thread(target=_run, args=(options,), daemon=True).start()
    return redirect(url_for("index"))


@app.post("/api/jobs/stop")
def stop_job():
    stop_event.set()
    return redirect(url_for("index"))


@app.get("/api/status")
def status():
    with job_lock:
        return jsonify(dict(job))


@app.get("/api/files")
def list_files():
    files = []
    if crawler.DATA_DIR.is_dir():
        for path in sorted(crawler.DATA_DIR.glob("*.json"), key=merge_data.page_number):
            page = merge_data.page_number(path)
            if page >= 10**9:
                continue
            try:
                count = len(_read_page(page))
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


@app.get("/api/files/<page>")
def get_file(page: str):
    try:
        page_number = int(page)
        return jsonify({"page": page_number, "records": _read_page(page_number)})
    except (ValueError, FileNotFoundError, OSError, json.JSONDecodeError) as exc:
        return jsonify({"error": str(exc)}), 400


@app.put("/api/files/<page>")
def update_file(page: str):
    try:
        page_number = int(page)
        path = _page_path(page)
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
    if selected:
        try:
            pages = sorted({int(value) for value in selected})
            records = []
            for page in pages:
                records.extend((page, merge_data.flatten(item)) for item in _read_page(page))
        except (ValueError, FileNotFoundError, OSError, json.JSONDecodeError) as exc:
            return jsonify({"error": str(exc)}), 400
    else:
        records = merge_data.load_records(crawler.DATA_DIR)

    output = Path("data.csv")
    if not records:
        return jsonify({"error": "Chưa có dữ liệu để xuất"}), 400
    merge_data.write_csv(records, output, dedupe=True, encoding="utf-8-sig")
    return send_file(output, as_attachment=True, download_name="buyers.csv")


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
