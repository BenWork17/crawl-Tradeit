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

### Điều kiện tìm kiếm (HS Code + quốc gia nhập hàng)

Form gửi lên TradeIT đúng body mà trang buyer-search thật sử dụng:

| Trường | Ý nghĩa |
|--------|---------|
| `searchBase` | Luôn `0` (giữ cho giống web gốc) |
| `hsCode` | Mã HS cần tìm (ít nhất 2 chữ số; dấu chấm/khoảng trắng được tự bỏ) |
| `productKeyword` | Từ khoá sản phẩm (mặc định rỗng) |
| `buyerName` / `supplierName` | Lọc theo tên công ty (mặc định rỗng) |
| `destiCountryCode` | **Quốc gia nhập hàng** — chuỗi ISO-2 phân tách bằng dấu phẩy, ví dụ `"US,VN"`. Đây chính là các nước bạn chọn trong danh sách. |
| `originclCountryCode` | Quốc gia xuất hàng (mặc định rỗng). Chú ý: tên trường có typo `origincl` đúng như web gốc. |
| `startDate` / `endDate` | Khoảng thời gian (mặc định rỗng) |

> **Quan trọng:** API **không** nhận trường `region_list`. Bản trước gửi
> `region_list` dạng mảng object nên server bỏ qua hoàn toàn, kết quả trả về mọi
> nước (US chiếm đa số) — đó là lý do bạn thấy dữ liệu "mặc định US".
> Hiện code gửi `destiCountryCode` đúng schema và lấy đúng từ lựa chọn của bạn.

Chọn quốc gia bằng danh sách có ô tìm kiếm, chọn nhanh theo nhóm (checkbox ở
tiêu đề nhóm), hoặc các nút **NL + VN**, **Toàn EU**, **ASEAN**. Khung
*Body gửi lên TradeIT* hiển thị chính xác JSON sẽ POST, nên bạn kiểm tra được
trước khi tốn credit.

### Danh sách quốc gia

Danh sách trong `regions.py` **khớp 1-1 với picker của web gốc**: đúng 195 quốc
gia, chia 5 nhóm theo đúng thứ tự và đúng nhãn tiếng Anh của site:

| Nhóm | Số quốc gia |
|------|-------------|
| America | 34 |
| Asia | 47 |
| Africa | 55 |
| Oceania | 14 |
| Europe | 45 |

Mỗi dòng có **cờ** (lấy từ `flagcdn.com`, có emoji dự phòng khi offline) và nhãn
tiếng Việt. Những vùng lãnh thổ **không** có trên web gốc (South Georgia, Macau,
Puerto Rico, Guernsey, Bắc Triều Tiên...) cũng không được đưa vào, để lựa chọn
không bao giờ tạo ra truy vấn mà site không hỗ trợ. Kosovo (`XK`) có trong danh
sách dù không thuộc ISO-3166.

Ô tìm kiếm lọc theo cả tên tiếng Anh, tiếng Việt và mã ISO. Gõ `Asia`,
`Châu Á` hoặc `all` để chọn cả nhóm.

Web sẽ crawl tuần tự từng account, tự bỏ qua trang đã có trong bộ dữ liệu đó và
gộp kết quả cuối cùng thành một file Excel duy nhất.

Ứng dụng chỉ chạy một job tại một thời điểm. Không nên bật debug hoặc chia sẻ URL
dashboard công khai nếu chưa thêm lớp đăng nhập.

Danh sách tài khoản (token / refresh_token) sau khi upload sẽ được **ghi nhớ** để
lần crawl sau không phải upload lại — xem [Lưu tài khoản bằng Supabase](#lưu-tài-khoản-bằng-supabase)
để biết cách làm cho nó sống sót qua mỗi lần deploy. Cookie **không** bao giờ được
ghi ra `logs/` hay trả về qua API; chỉ có file lưu tài khoản (hoặc hàng Supabase)
chứa token.

Các file `data/`, `datasets/`, `state.json` và file Excel vẫn nằm trên filesystem
của container. Trên hosting miễn phí (kể cả Render free) filesystem đó là **tạm
thời**: mất khi redeploy và khi service ngủ đông. Hãy tải dữ liệu về sau mỗi phiên
nếu chưa có nơi lưu bền vững.

### Tải, xem và xóa bộ dữ liệu

Ngay dưới ô chọn **Bộ dữ liệu đang chọn** có ba nút thao tác trên đúng bộ đang chọn:

| Nút | Việc gì xảy ra |
|-----|----------------|
| **⬇ Tải bộ dữ liệu (.xlsx)** | Tải toàn bộ bộ dữ liệu đang chọn ra **một file Excel** — mỗi bản ghi một dòng, mỗi trường một cột (giống nút xuất Excel). Bộ rỗng trả về lỗi 404 thay vì tải file trống. Trong hộp thoại **Xem bộ dữ liệu** còn nút **ZIP (JSON gốc)** nếu bạn cần các file `data/<trang>.json` thô (tương ứng `?format=zip`). |
| **👁 Xem bộ dữ liệu** | Mở hộp thoại chi tiết: số file, tổng bản ghi, dung lượng, trang lớn nhất, điều kiện tìm kiếm đã lưu trong `state.json` và bảng từng trang (số bản ghi, số cột, dung lượng). Bấm **Xem / sửa** trên một dòng để mở bảng chỉnh sửa của trang đó. |
| **✕ Xóa bộ dữ liệu** | Xóa vĩnh viễn dữ liệu của bộ đang chọn. Phải gõ lại đúng tên bộ dữ liệu để nút **Xóa vĩnh viễn** bật lên; hộp thoại hiển thị trước số file và số bản ghi sẽ mất. |

Chi tiết cách xóa:

- Bộ thường: xóa cả thư mục `datasets/<tên>/`. Thư mục `datasets/` rỗng cũng được
  dọn luôn để danh sách bộ dữ liệu không còn dòng trống.
- Bộ **Mặc định (legacy)**: chỉ xóa `data/*.json` và `state.json`. `data.csv` là file
  bạn tự gộp (và đang được git theo dõi) nên **được giữ nguyên**.
- Không xóa được bộ đang được crawl: API trả về `409` kèm thông báo dừng job trước.
- Sau khi xóa, dashboard tự chuyển về bộ **Mặc định (legacy)** và tải lại danh sách file.

Các thao tác này tương ứng với ba endpoint: `GET /api/datasets/<tên>/download`,
`GET /api/datasets/<tên>/summary` và `POST /api/datasets/<tên>/delete`. Cả ba đều
kiểm tra tên bộ dữ liệu và không tạo thư mục mới chỉ vì bị gọi.

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
- Bộ dữ liệu đang chọn có thêm ba nút **Tải / Xem / Xóa** ngay dưới ô chọn.
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
| `--body JSON` | None | Ghi đè toàn bộ body (`hsCode` + `destiCountryCode`) |

`--region` nhận mã ISO2 (`VN`), ISO3 (`VNM`), tên tiếng Anh (`Vietnam`), tên
tiếng Việt (`Việt Nam`), tên châu lục (`Asia`, `Châu Á`) hoặc `all`.

```bash
# Tìm buyer nhập khẩu hạt tiêu (090411) tại Hà Lan và Việt Nam
python tradeit_crawler.py --hs-code 090411 --region NL --region VN

# Toàn bộ châu Á
python tradeit_crawler.py --hs-code 090411 --region Asia
```

## Lưu tài khoản bằng Supabase

### Vì sao cần

Render gói **free không có persistent disk** (disk chỉ có ở gói trả phí), và
filesystem của container bị **xoá sạch mỗi lần redeploy**, đồng thời service free
**ngủ đông sau một thời gian rảnh** rồi khởi động lại từ đầu. Nếu chỉ lưu bằng file,
mỗi lần deploy bạn lại phải upload lại Excel tài khoản.

Vì vậy danh sách tài khoản có thể được lưu ở **Supabase** (Postgres + REST API).
Khi bật, tài khoản nằm ngoài container nên **redeploy không làm mất**; dashboard vẫn
hiện đúng số tài khoản đã lưu.

> **Lưu ý:** Supabase chỉ giải quyết phần **tài khoản**. Các trang đã crawl
> (`datasets/`, `data/`, `state.json`) vẫn ghi lên filesystem tạm của container và
> **sẽ mất khi redeploy/ngủ đông** — hãy tải ZIP/Excel về sau mỗi phiên. Việc đưa
> datasets lên Supabase là thay đổi riêng, chưa làm ở đây.

Không cấu hình Supabase thì module dùng file JSON cục bộ như trước — chạy local
không đổi gì và **không phát sinh request mạng nào**.

### 1. Tạo project Supabase

1. Vào <https://supabase.com>, tạo project mới (gói free là đủ).
2. Vào **Project Settings → API**, lấy:
   - **Project URL** — dạng `https://<project-ref>.supabase.co`
   - **service_role key** (mục *Project API keys*). Đây là key **bắt buộc** cho
     cấu hình trong mục 2 bên dưới: bảng có bật RLS mà **không tạo policy**, nên
     chỉ `service_role` (bỏ qua RLS) mới đọc/ghi được. Key này chỉ dùng ở server,
     **không** đưa vào trình duyệt hay commit vào repo.

### 2. Tạo bảng

Mở **SQL Editor** và chạy đúng đoạn SQL này (một dòng duy nhất giữ cả danh sách
tài khoản trong một cột `jsonb`):

```sql
create table if not exists public.tradeit_accounts (
    id         text primary key,
    accounts   jsonb       not null,
    updated_at timestamptz not null default now()
);

-- Bắt buộc: bảng chứa token nên phải bật RLS.
-- Cố ý KHÔNG tạo policy nào: anon/public không đọc, không ghi được gì.
-- Chỉ service_role key (dùng ở server) bỏ qua RLS nên vẫn truy cập được.
alter table public.tradeit_accounts enable row level security;
```

> Nếu bạn **không** bật RLS thì app vẫn chạy với `service_role`, nhưng bảng sẽ
> hở: bất kỳ ai có `anon` key (key này công khai trong mọi app Supabase) cũng đọc
> được token. Vì vậy đừng bỏ dòng `enable row level security`.

> Dùng `anon` key thay cho `service_role` sẽ **hỏng** với cấu hình trên: RLS chặn
> mọi truy cập vì không có policy. Muốn dùng `anon` thì phải tự tạo policy cho
> đúng nhu cầu — đơn giản nhất là cứ dùng `service_role` ở server.

Toàn bộ danh sách nằm ở hàng `id = 'default'`, cột `accounts` có dạng:

```json
{"version": 1, "updated_at": "…", "count": 2,
 "accounts": [{"token": "…", "refresh_token": "…"}]}
```

### 3. Biến môi trường trên Render

**Render Dashboard → service → Environment → Add Environment Variable:**

| Biến | Bắt buộc | Ý nghĩa |
|------|----------|---------|
| `SUPABASE_URL` | có | Project URL, ví dụ `https://abcdefgh.supabase.co` |
| `SUPABASE_SECRET_KEY` | có | Secret key dạng mới `sb_secret_…` |
| `SUPABASE_KEY` | (thay thế) | Tên cũ, dùng cho key `service_role` kiểu JWT |
| `SUPABASE_TABLE` | không | Tên bảng, mặc định `tradeit_accounts` |

Code chấp nhận **một trong ba** tên key, theo thứ tự: `SUPABASE_KEY` →
`SUPABASE_SECRET_KEY` → `SUPABASE_SERVICE_ROLE_KEY`. Nghĩa là project mới (key
`sb_secret_…`) đặt `SUPABASE_SECRET_KEY`, project cũ (JWT `service_role`) đặt
`SUPABASE_KEY` — cả hai đều chạy, không cần đổi code.

Chỉ cần đặt `SUPABASE_URL` và **một** key là backend Supabase tự bật. Thiếu một
trong hai thì vẫn dùng file cục bộ.

> **Các key Supabase KHÔNG được dùng:**
> - `sb_publishable_…` / `anon` — RLS sẽ chặn (bảng không có policy), app rơi về
>   file tạm và báo `SUPABASE_KEY sai hoặc thiếu quyền (HTTP 401/403)`.
> - `SUPABASE_JWKS_URL` — chỉ dùng để xác thực JWT ở phía Auth, app này không cần.

> **Không bao giờ commit key** vào repo. `requirements.txt`, README và code chỉ
> đọc từ biến môi trường; key không được ghi ra log, không nằm trong
> `/api/accounts`, và không xuất hiện trong thông báo lỗi. Nếu key lộ, hãy
> **rotate** ngay trong Supabase.

### 4. Sao lưu bộ dữ liệu đã crawl lên Supabase Storage

Phần trên chỉ lưu **tài khoản**. Các trang đã crawl (`<trang>.json`), `state.json`
và file Excel vẫn nằm trên filesystem tạm của Render free, nên **mất khi
redeploy**. Để giữ luôn bộ dữ liệu, bật thêm Supabase **Storage**:

1. **Storage → New bucket**, đặt tên `tradeit-data`, để **Private** (không public
   — dữ liệu thương mại không nên hở). Nếu chưa tạo, app cũng tự tạo được bằng
   API khi bucket chưa tồn tại.
2. Thêm biến môi trường (cùng `SUPABASE_URL` + key ở trên):

| Biến | Bắt buộc | Ý nghĩa |
|------|----------|---------|
| `SUPABASE_STORAGE_BUCKET` | có | Tên bucket, ví dụ `tradeit-data` |

Cách hoạt động:

- Đĩa **vẫn là bản làm việc chính** — crawler ghi trang xuống đĩa như cũ, rồi
  **đẩy ngay từng trang** lên Storage sau khi lưu xong. Redeploy giữa lúc crawl
  chỉ mất tối đa trang đang chạy dở.
- Sau redeploy, khi bạn mở một bộ dữ liệu mà đĩa trống, app **tự khôi phục** các
  trang từ Storage (chỉ tải file còn thiếu, không ghi đè file đã có).
- Nút **Sao lưu** (`POST /api/datasets/<tên>/backup`) đẩy toàn bộ bộ dữ liệu hiện
  có lên Storage khi bạn muốn.
- `GET /api/storage` cho biết đang bật hay tắt và tên bucket.

Cấu trúc object trên Storage:

```
tradeit-data/
└── <tên-bộ-dữ-liệu>/
    ├── data/1.json, 2.json, …
    └── state.json
```

Đây là bản sao 1-1 của thư mục trên đĩa, nên khôi phục chỉ là copy file.

> **Dung lượng:** mỗi trang ~58 KB; một lần crawl đầy đủ (~786 trang) ~45 MB.
> Gói free của Supabase Storage cho 1 GB ⇒ khoảng **20 bộ dữ liệu đầy đủ**. Nên
> xoá bộ không dùng, hoặc tải ZIP về rồi xoá.

> Nếu Storage lỗi (mạng, sai bucket, hết dung lượng), crawl **vẫn chạy bình
> thường** trên đĩa và job ghi `backup_error` để dashboard hiện cảnh báo — dữ
> liệu không bị mất, chỉ là chưa được sao lưu.

### 5. Các biến môi trường khác (tuỳ chọn)

Thứ tự chọn nơi lưu của backend file (dùng khi **không** cấu hình Supabase, hoặc
khi truyền `path=`):

1. tham số `path=` (đường dẫn file, hoặc thư mục chứa `accounts.json`);
2. `TRADEIT_ACCOUNTS_FILE` — đường dẫn **file** đầy đủ;
3. `TRADEIT_DATA_DIR` + `/accounts.json` — **thư mục** chứa file;
4. mặc định `<project>/datasets/accounts.json` (đã nằm trong `.gitignore`).

`TRADEIT_DATA_DIR` và `TRADEIT_ACCOUNTS_FILE` chỉ có ý nghĩa với backend file. Trên
Render free chúng trỏ vào filesystem tạm nên **không** giúp dữ liệu sống sót qua
redeploy — đó là lý do dùng Supabase ở trên.

#### Quyền truy cập file tài khoản trên Windows (hạn chế đã biết)

Trên Linux/macOS, `accounts_store` đặt file tài khoản ở chế độ `0600` (chỉ chủ sở
hữu đọc được). Trên **Windows** điều này **không** được áp đặt: `os.chmod` ở đó chỉ
bật/tắt thuộc tính read-only, không diễn đạt được ACL, nên file **thừa hưởng quyền
của thư mục chứa nó** — người dùng khác trên cùng máy (hoặc ai đọc được roaming
profile) có thể mở được file. Đây là hạn chế đã biết, chấp nhận, và được ghi log
một lần khi lưu file.

Cách giảm thiểu, theo thứ tự ưu tiên:

1. Dùng **Supabase** trên Windows — không có file credential cục bộ nào cả;
2. Đặt `TRADEIT_ACCOUNTS_FILE` vào thư mục **riêng của bạn** (ví dụ
   `C:\Users\<tên-bạn>\...`) và **không** đặt trong thư mục `shared`/roaming;
3. Trên máy nhiều người dùng, giới hạn quyền bằng DACL tường minh:
   `icacls accounts.json /inheritance:r /grant:r "%USERNAME%:F"`.

File này luôn nằm trong `.gitignore` ở mọi vị trí mặc định, nên không thể bị commit.

### 5. Kiểm chứng đã hoạt động

1. Mở dashboard, upload Excel tài khoản như bình thường. Sau khi upload, khối tài
   khoản hiển thị **"Đã lưu N tài khoản"** kèm thời điểm cập nhật.
2. Kiểm tra trực tiếp Supabase: **Table Editor → `tradeit_accounts`** phải có đúng
   một hàng `id = default`. (Hoặc `GET /api/accounts` — chỉ trả về số lượng và
   trạng thái, không trả token.)
3. **Redeploy** service trên Render (Manual Deploy → Deploy latest commit), hoặc để
   service ngủ đông rồi truy cập lại.
4. Tải lại dashboard: khối tài khoản vẫn phải hiện **đúng số tài khoản đã lưu** và
   form crawl **không** đòi upload lại Excel. Đó là bằng chứng tài khoản đã nằm
   ngoài container.

Nếu vẫn thấy "Chưa có danh sách tài khoản nào được lưu", xem log Render: một dòng
cảnh báo `Supabase không dùng được (…)` cho biết lý do (sai key, thiếu bảng, mạng)
và app đã tạm quay về file cục bộ trong 60 giây trước khi thử lại.

`accounts_store.summary()` trả trường `backend` (`file`, `supabase` hoặc
`file-fallback`) để biết backend nào đang thực sự phục vụ. Endpoint `/api/accounts`
cũng trả `backend` (kèm `fallback_reason` khi đang ở `file-fallback`), **không**
trả đường dẫn file. Nhờ vậy dashboard hiện được nhãn "Lưu trữ: Supabase" /
"Lưu trữ: file tạm" và cảnh báo mất dữ liệu khi phải fallback về file tạm.

## Cấu trúc output

```
project/
├── tradeit_crawler.py   # crawl
├── regions.py           # danh mục quốc gia/vùng + dựng destiCountryCode
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

> **Cảnh báo `--force` một phần khoảng trang:** `--force` chỉ ghi đè những trang
> nó thực sự crawl. Nếu `data/` còn trang của **điều kiện tìm kiếm khác** nằm
> ngoài khoảng `--start-page..--end-page`, các trang đó vẫn ở lại và sẽ bị gộp
> vào file export. CLI có in `[WARNING]` nêu rõ điều kiện cũ và các trang đó,
> nhưng không tự xoá dữ liệu của bạn. Muốn sạch hoàn toàn: xoá `data/` +
> `state.json` trước khi chạy.
>
> Ngoài `--force`, CLI **từ chối** (exit 3) khi thấy `data/` hoặc `state.json`
> thuộc điều kiện tìm kiếm khác, thay vì lặng lẽ bỏ qua trang và báo "xong".

## Xử lý lỗi

- **400 `credit.CREDIT_NOT_ENOUGH`** / **401 / 403**: dừng, in thông báo `[STOP]`,
  chờ bạn paste cookie mới, rồi **tiếp tục từ curPage hiện tại** (không reset về 1).
- **429**: tôn trọng `Retry-After`, sleep rồi retry.
- **5xx**: retry với exponential backoff (tối đa 3 lần).
- **Hết credit giữa lúc crawl (không báo lỗi):** đây là bẫy quan trọng. Khi tài
  khoản cạn credit, API có thể vẫn trả **HTTP 200 kèm `items: []`** thay vì mã lỗi.
  Nếu chỉ nhìn `items` rỗng thì rất dễ tưởng "đã hết dữ liệu" và **bỏ sót bản ghi**.
  Crawler đọc `credit.totalBalance` ở mỗi trang:
  - `totalBalance` về `0` → job kết thúc với status **`no_credit`**, không ghi trang rỗng.
  - Hết trang nhưng `totalBalance` còn → **không ghi trang rỗng** và **không** báo "hoàn tất".
- **Crawl ngắn hơn `total` mà API báo:** job kết thúc với status **`incomplete`**,
  kèm `short_by` (số bản ghi còn thiếu) và banner đỏ trên dashboard. Đây là điểm
  khác biệt giữa "không còn dữ liệu" và "dừng sớm" — luôn kiểm tra banner này
  trước khi tin rằng đã lấy đủ.
- Response thiếu `data.items`: log warning và skip trang.
- **Ctrl+C**: lưu `state.json` (curPage hiện tại) rồi thoát gọn gàng.

> Nếu thấy `incomplete`/`no_credit`: nạp thêm credit hoặc file tài khoản mới, rồi
> chạy lại với **"Crawl lại và ghi đè"** để lấy tiếp phần còn thiếu.

## Lưu ý

- Tool lưu kết quả theo từng trang và state nên chạy lại an toàn (resume-friendly, không tốn credit cho trang đã xong).
- Muốn crawl lại từ đầu: xóa `state.json` + thư mục `data/`, hoặc dùng `--force`.
- Nếu chỉ test 1 trang, hãy đặt `--start-page 1 --end-page 1` để job kết thúc ngay sau trang đó.
