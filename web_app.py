"""Small web dashboard for running the TradeIT crawler.

The cookie is kept in memory for the lifetime of a job and is never rendered
back to the browser or written to disk by this module.
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, redirect, render_template, request, send_file, url_for
import requests

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
    "started_at": None,
}
stop_event = threading.Event()


def _page_path(raw_page: str) -> Path:
    """Resolve a page number to a data file without allowing path traversal."""
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


def _cookie_from_form() -> str:
    token = request.form.get("token", "").strip()
    refresh = request.form.get("refresh_token", "").strip()
    parts = []
    if token:
        parts.append(f"{crawler.CRM_TOKEN_NAME}={token}")
    if refresh:
        parts.append(f"{crawler.CRM_RF_TOKEN_NAME}={refresh}")
    return "; ".join(parts)


def _update(**values: Any) -> None:
    with job_lock:
        job.update(values)


def _run(options: dict[str, Any]) -> None:
    cookie = options["cookie"]
    page = options["start_page"]
    records = 0
    total: int | None = None
    session = requests.Session()
    body = {"importer": options["importer"], "hsCode": options["hs_code"]}
    try:
        if not options["force"]:
            saved_state = crawler.load_state()
            if saved_state:
                total = saved_state.get("total")
            if crawler.DATA_DIR.is_dir():
                for page_file in crawler.DATA_DIR.glob("*.json"):
                    try:
                        existing_page = int(page_file.stem)
                    except ValueError:
                        continue
                    records += crawler.count_records_in_file(existing_page)
        crawler.log_cookie_used(cookie)
        _update(
            status="running",
            message=f"Đang tìm trang tiếp theo từ trang {page}",
            page=page,
            records=records,
            total=total,
        )
        while not stop_event.is_set():
            if options["end_page"] is not None and page > options["end_page"]:
                break
            if not options["force"] and crawler.page_file_path(page).exists():
                existing = crawler.count_records_in_file(page)
                _update(
                    page=page,
                    records=records,
                    message=f"Bỏ qua trang {page} đã có dữ liệu; đang tìm trang tiếp theo",
                )
                if existing < options["per_page"]:
                    break
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
            crawler.save_page(items, page, options["force"])
            records += len(items)
            crawler.save_state(page, total, records)
            _update(
                page=page,
                records=records,
                total=total,
                message=f"Đã lưu trang {page} ({len(items)} bản ghi)",
            )
            if isinstance(row_count, int) and row_count < options["per_page"]:
                break
            if total is not None and records >= total:
                break
            page += 1
            stop_event.wait(options["delay"])
        if stop_event.is_set():
            _update(status="stopped", message="Đã dừng theo yêu cầu")
        else:
            _update(status="completed", message=f"Hoàn tất: {records} bản ghi")
    except (crawler.AuthError, crawler.CreditError) as exc:
        _update(
            status="error",
            message=f"Cookie hoặc credit không hợp lệ ở trang {page}: {exc}. "
            f"Dữ liệu cũ vẫn được giữ nguyên.",
            records=records,
            total=total,
        )
    except (requests.RequestException, RuntimeError, OSError, ValueError) as exc:
        _update(status="error", message=str(exc))
    finally:
        session.close()


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
    cookie = _cookie_from_form()
    if not cookie:
        return jsonify({"error": "Vui lòng nhập cookie"}), 400
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

    options = {
        "cookie": cookie,
        "start_page": start_page,
        "end_page": end_page,
        "per_page": per_page,
        "delay": delay,
        "force": request.form.get("force") == "on",
        "importer": request.form.get("importer", "netherland").strip() or "netherland",
        "hs_code": request.form.get("hs_code", "090411").strip() or "090411",
    }
    stop_event.clear()
    with job_lock:
        job.update(
            status="running",
            message="Đang khởi động",
            page=start_page,
            records=0,
            total=None,
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
        temporary.write_text(
            json.dumps(records, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
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
