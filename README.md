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

Mỗi lần crawl nên chọn hoặc tạo một **bộ dữ liệu** riêng. Bộ dữ liệu quyết định
thư mục lưu record và file Excel đầu ra.

Nếu để trống tên bộ dữ liệu, hệ thống **tự đặt tên theo điều kiện tìm kiếm**:
quốc gia/vùng + HS Code, ví dụ `nl-vn_090411`. Nhờ vậy hai điều kiện khác nhau
không bao giờ ghi chung một thư mục.

Nếu bạn cố ghi một điều kiện mới vào bộ dữ liệu đã crawl bằng điều kiện khác,
ứng dụng sẽ **từ chối** và yêu cầu tạo bộ mới (hoặc tick *Crawl lại và ghi đè*).

### Điều kiện tìm kiếm (HS Code + region_list)

Form gửi lên TradeIT đúng hai trường của trang buyer-search:

| Trường | Ý nghĩa |
|--------|---------|
| `hsCode` | Mã HS cần tìm (2–10 chữ số; dấu chấm/khoảng trắng được tự bỏ) |
| `region_list` | Mảng quốc gia/vùng **nhập hàng**; mỗi phần tử có `type`, `code`, `isoCode`, `isoAlpha2`, `name`, `nameEn`, `upCode`, `countryCode` |

Chọn quốc gia bằng danh sách có ô tìm kiếm, chọn nhanh theo châu lục (checkbox ở
tiêu đề nhóm), hoặc các nút **NL + VN**, **Toàn EU**, **ASEAN**. Khung
*Body gửi lên TradeIT* hiển thị chính xác JSON sẽ POST, nên bạn kiểm tra được
trước khi tốn credit.

> **Lưu ý quan trọng:** bản cũ hardcode `{"importer": "netherland", "hsCode": "090411"}`
> và bỏ qua lựa chọn của người dùng, nên mọi lần crawl đều tìm cho Hà Lan. Hiện
> trường `importer` đã bị loại bỏ hoàn toàn; chỉ `hsCode` + `region_list` được gửi,
> và chúng lấy đúng từ form.

Web sẽ crawl tuần tự từng account, tự bỏ qua trang đã có trong bộ dữ liệu đó và
gộp kết quả cuối cùng thành một file Excel duy nhất.

Ứng dụng chỉ chạy một job tại một thời điểm. Cookie không được ghi ra file;
không nên bật debug hoặc chia sẻ URL dashboard công khai nếu chưa thêm lớp đăng nhập.
Các file `data/`, `state.json` và file Excel trên hosting miễn phí có thể mất khi
container khởi động lại; hãy dùng persistent disk hoặc tải file sau mỗi phiên.

### Xem và chọn file trên web

Phần **File đã crawl** trên dashboard liệt kê từng `data/<trang>.json`. Có thể
bấm **Xem / sửa**, chỉnh JSON dạng mảng rồi bấm **Lưu thay đổi**. Khi tải CSV,
chỉ những file được tick mới được gộp; dùng **Chọn tất cả** nếu muốn gộp toàn bộ
file hiện có. Nếu không chọn file nào, hệ thống không tạo bản tải xuống để tránh
nhầm dữ liệu.

Web xuất trực tiếp file Excel `.xlsx`, không cần dùng **Text to Columns**. Mỗi
trường là một cột riêng, có bộ lọc và cố định hàng tiêu đề. Các giá trị được ghi
dạng text để hạn chế Excel tự đổi mã HS, số 0 đầu hoặc ngày tháng.

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
| `--hs-code CODE` | `090411` | HS Code cần tìm |
| `--region NAME` | `NL` | Quốc gia/vùng nhập hàng; lặp lại được (`--region NL --region VN`) |
| `--region-list "NL,VN"` | None | Nhiều quốc gia, phân tách bằng dấu phẩy |
| `--body JSON` | None | Ghi đè toàn bộ body (`hsCode` + `region_list`) |

`--region` nhận mã ISO2 (`VN`), ISO3 (`VNM`), tên tiếng Anh (`Vietnam`), tên
tiếng Việt (`Việt Nam`), tên châu lục (`Asia`, `Châu Á`) hoặc `all`.

```bash
# Tìm buyer nhập khẩu hạt tiêu (090411) tại Hà Lan và Việt Nam
python tradeit_crawler.py --hs-code 090411 --region NL --region VN

# Toàn bộ châu Á
python tradeit_crawler.py --hs-code 090411 --region Asia
```

## Cấu trúc output

```
project/
├── tradeit_crawler.py   # crawl
├── regions.py           # danh mục quốc gia/vùng + dựng region_list
├── merge_data.py        # gộp data/*.json -> CSV
├── cookies.txt
├── data/            # <curPage>.json
├── data.csv         # kết quả gộp (merge_data.py)
├── datasets/        # mỗi điều kiện tìm kiếm một thư mục riêng
├── logs/
│   ├── crawler.log      # log chi tiết mỗi request
│   └── cookies_used.log # timestamp + account id (JWT), KHÔNG log cookie
└── state.json       # curPage + query để resume / sau Ctrl+C
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
