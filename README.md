# TradeIT Crawler

Công cụ crawl API search của TradeIT (buyer-search) cho **một account tại một thời điểm**.
Cookie do bạn tự cung cấp. Tool không tạo account, không tự động thu thập cookie.

## Cài đặt

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate

pip install -r requirements.txt
```

Yêu cầu: Python 3.10+.

## Chuẩn bị cookie

Lấy từ DevTools → Application → Cookies:

```
_TaaS.auth.crm.token=xxx; _TaaS.auth.crm.rf_token=yyy
```

Đặt vào file `cookies.txt` (một dòng) hoặc truyền qua `--cookie-file`, hoặc để tool
prompt. Khi prompt, tool hỏi **từng cookie riêng** để tránh nhầm:

```
_TaaS.auth.crm.token = <dán giá trị token>
_TaaS.auth.crm.rf_token = <dán giá trị rf_token>
```

(Chỉ dán phần giá trị, không cần `name=`; nếu dán cả cặp `name=value` hoặc cả dòng
`a=..; b=..` thì tool vẫn tự nhận.) Tool **không** ghi cookie đầy đủ ra log.

## Chạy

```bash
# Test 2 trang đầu
python tradeit_crawler.py --end-page 2

# Chạy full với delay mặc định
python tradeit_crawler.py --per-page 50 --delay 1.5

# Resume-friendly: chạy lại sẽ tự bỏ qua data/<n>.json đã có
python tradeit_crawler.py

# Ghi đè file đã tồn tại
python tradeit_crawler.py --force
```

## Chạy giao diện web

Giao diện web cho phép upload Excel danh sách tài khoản, bắt đầu/dừng job crawl,
xem/sửa file đã crawl và tải CSV:

```bash
python -m pip install -r requirements.txt
python web_app.py
```

Mở `http://localhost:5000`. Khi triển khai Render/Railway, dùng lệnh
`gunicorn --bind 0.0.0.0:$PORT web_app:app` (đã có sẵn trong `Procfile`).
Có thể dùng `Dockerfile` để triển khai trên bất kỳ nền tảng container nào.

Trên Windows local, không chạy lệnh `gunicorn` trong PowerShell. Hãy dùng:

```powershell
python web_app.py
```

Sau đó mở `http://localhost:5000`. `gunicorn` chỉ dành cho môi trường Linux
trên hosting hoặc trong Docker.

### Upload danh sách tài khoản

Chuẩn bị một file Excel với sheet đầu tiên gồm 2 cột:

| token | refresh_token |
|---|---|
| ... | ... |

Nếu file có hàng tiêu đề, web sẽ tự nhận. Nên dùng nút **Tải template Excel** để
lấy mẫu sẵn.

### Chọn bộ dữ liệu đích

Mỗi lần crawl nên chọn hoặc tạo một **bộ dữ liệu** riêng ở ô **Chọn bộ dữ liệu đã có**
/ **Hoặc nhập tên mới**. Bộ dữ liệu này quyết định thư mục lưu record và file CSV
đầu ra, nên khi đổi `Importer` hoặc `HS Code` bạn chỉ cần tạo bộ mới để không
trộn record cũ vào CSV mới.

Web sẽ crawl tuần tự từng account, tự bỏ qua record đã có trong bộ dữ liệu đó và
gộp kết quả cuối cùng thành một CSV duy nhất.

Ứng dụng chỉ chạy một job tại một thời điểm. Cookie không được ghi ra file;
không nên bật debug hoặc chia sẻ URL dashboard công khai nếu chưa thêm lớp đăng nhập.
Các file `data/`, `state.json` và CSV trên hosting miễn phí có thể mất khi
container khởi động lại; hãy dùng persistent disk hoặc tải CSV sau mỗi phiên.

### Xem và chọn file trên web

Phần **File đã crawl** trên dashboard liệt kê từng `data/<trang>.json`. Có thể
bấm **Xem / sửa**, chỉnh JSON dạng mảng rồi bấm **Lưu thay đổi**. Khi tải CSV,
chỉ những file được tick mới được gộp; dùng **Chọn tất cả** nếu muốn gộp toàn bộ
file hiện có. Nếu không chọn file nào, hệ thống không tạo bản tải xuống để tránh
nhầm dữ liệu.

CSV xuất ra đang dùng dấu `;` để phân tách cột, phù hợp với thao tác **Text to
Columns** trong Excel. Các trường lồng nhau được đổi sang dạng `a__b` để không
bị tách nhầm khi dùng dấu `;`.

### Giao diện

- Có nút đổi sáng/tối ngay trên dashboard.
- Phần xem file đã crawl hiển thị theo bảng, sửa từng ô rồi lưu lại.
- Có nút **Tạo bộ dữ liệu mới** riêng, không cần nhập tên dataset trong form crawl.
- Giao diện dùng typography `DM Sans` cho nội dung và `Space Grotesk` cho tiêu đề,
  tự responsive trên màn hình nhỏ.

### CLI

| Flag | Mặc định | Mô tả |
|------|----------|-------|
| `--start-page N` | 1 | Bắt đầu từ trang N |
| `--end-page N` | None | Dừng ở trang N (mặc định chạy đến hết) |
| `--per-page N` | 50 | Số records mỗi trang |
| `--delay N` | 1.5 | Giây nghỉ giữa các request |
| `--force` | off | Ghi đè file `data/<n>.json` đã tồn tại |
| `--cookie-file PATH` | None | Đọc cookie từ file |
| `--body JSON` | `{"importer":"netherland","hsCode":"090411"}` | Body request tùy chỉnh |

## Cấu trúc output

```
project/
├── tradeit_crawler.py   # crawl
├── merge_data.py        # gộp data/*.json -> CSV
├── cookies.txt
├── data/            # <curPage>.json
├── data.csv         # kết quả gộp (merge_data.py)
├── logs/
│   ├── crawler.log      # log chi tiết mỗi request
│   └── cookies_used.log # timestamp + account id (JWT), KHÔNG log cookie
└── state.json       # curPage để resume / sau Ctrl+C
```

## Gộp ra CSV

```bash
python merge_data.py                       # -> data.csv
python merge_data.py --output buyers.csv   # đổi tên file
python merge_data.py --dedupe              # bỏ dòng trùng hoàn toàn
```

`merge_data.py` chỉ dùng thư viện chuẩn (không cần pandas), đọc mọi `data/*.json`
theo thứ tự trang, làm phẳng record (key lồng nhau -> `a.b`), gộp tất cả cột và ghi
CSV. Cột đầu `_source_page` cho biết record đến từ trang nào. File mặc định mã hoá
`utf-8-sig` để mở bằng Excel không lỗi tiếng Việt.

| Flag | Mặc định | Mô tả |
|------|----------|-------|
| `--data-dir PATH` | `data` | Thư mục chứa `<n>.json` |
| `--output PATH` | `data.csv` | File CSV kết quả |
| `--dedupe` | off | Loại bỏ dòng trùng hoàn toàn |
| `--encoding NAME` | `utf-8-sig` | Encoding file CSV |

## Cách hoạt động

1. Đọc cookie (file hoặc prompt), ghi audit vào `logs/cookies_used.log`.
2. Lặp `curPage` từ `--start-page` (hoặc state): POST `perPage&curPage`, parse `data.items`.
3. Lưu `data/<curPage>.json`, log status/rowCount/credit/crawled-total.
4. Dừng khi `rowCount < perPage`, đạt `--end-page`, hoặc đủ `total`.
5. `sleep --delay` giữa các request.

## Resume (nhớ trang đã crawl)

Tool nhớ tiến độ theo **2 lớp**:

- `state.json`: lưu `curPage` (trang cuối đã crawl), `total` và `crawled`. Khi chạy lại,
  tool tiếp tục từ `curPage + 1` và **không gọi lại** các trang đã xong. Nếu đã đủ `total`,
  tool thoát ngay mà không request nào (không tốn credit).
- `data/<n>.json`: nếu `state.json` bị xóa, tool bỏ qua yêu cầu HTTP cho mọi trang đã có file
  (không ghi lại, không tốn credit). Gặp file có số records `< perPage` → coi là trang cuối và dừng.

`--force` bỏ qua cả state lẫn file đã có, crawl lại từ `--start-page`.

## Xử lý lỗi

- **400 `credit.CREDIT_NOT_ENOUGH`** / **401 / 403**: dừng, in thông báo `[STOP]`,
  chờ bạn paste cookie mới, rồi **tiếp tục từ curPage hiện tại** (không reset về 1).
- **429**: tôn trọng `Retry-After`, sleep rồi retry.
- **5xx**: retry với exponential backoff (tối đa 3 lần).
- Response thiếu `data.items`: log warning và skip trang.
- **Ctrl+C**: lưu `state.json` (curPage hiện tại) rồi thoát gọn gàng.

## Lưu ý

- Tool lưu kết quả theo từng trang và state nên chạy lại an toàn (resume-friendly, không tốn credit cho trang đã xong).
- Muốn crawl lại từ đầu: xóa `state.json` + thư mục `data/`, hoặc dùng `--force`.
- Nếu chỉ test 1 trang, hãy đặt `--start-page 1 --end-page 1` để job kết thúc ngay sau trang đó.
