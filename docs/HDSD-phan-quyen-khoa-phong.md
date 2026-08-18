# Hướng dẫn thao tác — Phân quyền theo khoa phòng trên cổng khách hàng

App `miyano_portal` · Cập nhật **18/08/2026** · Áp dụng từ bản nền (bước 1–4)

**Tài liệu này dành cho nhân viên Miyano** làm việc trên Desk (`/app`). Khách hàng
chưa có màn hình mới nào — các màn của bệnh viện thuộc bước 5–9, chưa làm.

---

## 0. Điều quan trọng nhất: chưa làm gì thì chưa đổi gì

Sau khi cài bản này, **mọi bệnh viện đang dùng cổng vẫn hoạt động y như trước**.
Mọi tài khoản hiện có được hệ thống tự đánh là **Quản lý** không gắn khoa phòng,
nên họ vẫn thấy toàn bộ đơn hàng của bệnh viện mình.

Việc cách ly theo khoa **chỉ bắt đầu có tác dụng** khi bạn thật sự tạo một thành
viên có vai trò **Nhân viên khoa**. Nghĩa là bạn bật cho từng bệnh viện một, khi
họ sẵn sàng — không có ngày "cả hệ thống đổi cách hoạt động".

> **Hệ quả cần nhớ:** một bệnh viện chưa bật thì không cần làm gì cả. Đừng khai mã
> ngắn hay khoa phòng cho họ "cho đủ".

---

## 1. Ba khái niệm mới

| Khái niệm | Là gì | Ở đâu trên Desk |
|---|---|---|
| **Mã ngắn khách hàng** | Mã viết tắt của bệnh viện, ví dụ `BM`. Dùng làm phần đầu mã phiếu đề xuất mua sau này | `Customer` → ô **Mã ngắn (cổng khách)** |
| **Khoa phòng** | Khoa/phòng/đơn vị của bệnh viện. Trước đây thuộc về **kho**, nay thuộc về **bệnh viện** | Doctype `Customer Department` |
| **Thành viên cổng** | Một tài khoản cổng thuộc bệnh viện nào, vai trò gì, khoa nào | Doctype `Portal Member` |

**Hai vai trò, và chỉ hai:**

- **Quản lý** — nhìn thấy **toàn bộ** đơn của bệnh viện. **Mỗi bệnh viện đúng một
  quản lý đang hoạt động.** Không gắn vào khoa phòng nào.
- **Nhân viên khoa** — chỉ nhìn thấy đơn của **khoa mình**. Bắt buộc phải có khoa
  phòng khi được kích hoạt.

---

## 2. Bật phân quyền khoa phòng cho một bệnh viện

**Bốn bước, và thứ tự là bắt buộc** — hệ thống sẽ chặn nếu làm sai thứ tự.

### Bước 1 — Đặt Mã ngắn cho bệnh viện

`Customer` → mở bệnh viện → ô **Mã ngắn (cổng khách)** → điền, ví dụ `BM`.

- Chữ hoa không dấu, tối đa 10 ký tự.
- **Không được trùng** với bệnh viện khác.

> **Vì sao phải làm trước:** mã này đi vào tên phiếu đề xuất mua. Hệ thống **không
> cho** tạo Nhân viên khoa cho một bệnh viện chưa có mã ngắn — và nó chặn ngay lúc
> bạn cấp tài khoản, chứ không để tới lúc nhân viên bệnh viện bấm gửi mới báo lỗi.

### Bước 2 — Khai khoa phòng

`Customer Department` → **New** cho từng khoa:

| Ô | Điền gì |
|---|---|
| **Khách hàng** | bệnh viện — **bắt buộc** |
| **Tên khoa phòng** | tên đầy đủ, ví dụ `Khoa Huyết học`. Chữ tự do, nên khai được cả `Phòng khám 1`, `Phòng Xét nghiệm` |
| **Mã khoa** | viết tắt, ví dụ `HUYETHOC` |
| **Kho** | **để trống** nếu bệnh viện chưa dùng kho trên cổng |

Quy tắc **Mã khoa** — hệ thống tự viết hoa và kiểm:

- chỉ chữ cái không dấu và chữ số (`HUYETHOC` được, `HUYẾT HỌC` và `XN-01` bị chặn);
- **không trùng trong cùng một bệnh viện** (hai bệnh viện khác nhau được phép trùng);
- **`CHUNG` là mã dành riêng của hệ thống**, không đặt cho khoa phòng được.

**Tên khoa phòng** cũng không được trùng trong cùng bệnh viện, và hệ thống so
**không dấu** — `Khoa Hồi sức` và `Khoa Hoi suc` bị coi là một.

### Bước 3 — Cấp tài khoản

Dùng đúng chức năng cấp tài khoản cổng đang có. Hệ thống tự quyết vai trò:

| Tình huống | Kết quả |
|---|---|
| Bệnh viện **chưa có** tài khoản nào | Tài khoản đầu tiên thành **Quản lý**, **đang hoạt động** — dùng được ngay |
| Bệnh viện **đã có** quản lý | Tài khoản mới thành **Nhân viên khoa**, **chưa hoạt động**, **chưa gán khoa** |

Ở trường hợp thứ hai, hệ thống trả về cờ báo *"tài khoản còn chờ gán khoa phòng"*.
**Tài khoản đó chưa dùng được** — còn bước 4.

> **Vì sao không gán khoa luôn lúc cấp:** người biết nhân viên đó thuộc khoa nào là
> **quản lý bệnh viện**, không phải Miyano. Nên tài khoản được tạo trước, gán khoa
> sau. Đó cũng là lý do nó được tạo ở trạng thái chưa hoạt động thay vì hoạt động
> mà không thấy gì.

### Bước 4 — Gán khoa phòng rồi kích hoạt

`Portal Member` → mở bản ghi vừa tạo:

1. **Vai trò** = `Nhân viên khoa`
2. **Khoa phòng** = chọn khoa của người đó
3. Tích **Hoạt động**
4. **Lưu**

Xong bước này tài khoản mới dùng được.

> Hiện quản lý bệnh viện **chưa có màn hình** để tự làm bước này — màn "Thành viên
> & phân quyền" thuộc bước 9, chưa làm. Tạm thời Miyano làm hộ trên Desk.

---

## 3. Thao tác hằng ngày

### Nhân viên chuyển khoa

`Portal Member` → đổi ô **Khoa phòng** → Lưu. Có hiệu lực ngay.

Đơn **đã đặt** vẫn mang khoa cũ — đó là chủ đích: đơn ghi lại nơi đã yêu cầu hàng
tại thời điểm đặt, không phải nơi người đó đang làm việc hôm nay.

### Nhân viên nghỉ việc

**Bỏ tích Hoạt động**, đừng xoá bản ghi. Xoá đi là mất luôn dấu vết ai đã đặt
những đơn cũ.

Tài khoản bị tắt thì **không đăng nhập dùng được và không nhận thông báo nữa**.

### Đổi quản lý bệnh viện

Hệ thống chỉ cho **một quản lý đang hoạt động** cho mỗi bệnh viện, nên phải làm
**đúng thứ tự này**:

1. Mở bản ghi quản lý **cũ** → bỏ tích **Hoạt động** → Lưu.
2. Mở bản ghi người **mới** → Vai trò = `Quản lý` → **xoá trống ô Khoa phòng** →
   tích **Hoạt động** → Lưu.

Làm ngược lại sẽ bị chặn với thông báo *"Bệnh viện này đã có quản lý là …"*.

### Tắt một khoa phòng

`Customer Department` → bỏ tích **Hoạt động**. **Đừng xoá** — khoa phòng đã dùng
trên phiếu xuất kho thì hệ thống cũng không cho xoá.

---

## 4. Gặp lỗi thì tra ở đây

| Thông báo | Nghĩa là gì | Làm gì |
|---|---|---|
| *"Nhân viên khoa phải được gán một khoa phòng."* | Đang bật Hoạt động cho một Nhân viên khoa chưa chọn khoa | Chọn khoa phòng rồi lưu lại |
| *"Quản lý nhìn xuyên mọi khoa nên không gắn vào khoa phòng nào."* | Quản lý mà lại điền ô Khoa phòng | Xoá trống ô Khoa phòng |
| *"Khoa phòng được chọn không thuộc khách hàng này."* | Chọn nhầm khoa của bệnh viện khác | Chọn lại đúng khoa của bệnh viện đó |
| *"Bệnh viện này đã có quản lý là …"* | Đang tạo quản lý thứ hai | Tắt quản lý cũ trước — xem mục 3 |
| *"Khách hàng … chưa có Mã ngắn."* | Cấp Nhân viên khoa cho bệnh viện chưa khai mã ngắn | Làm bước 1 trước |
| *"Bệnh viện này đã có khoa phòng mang mã …"* | Mã khoa trùng trong cùng bệnh viện | Đổi mã khoa |
| *"Mã khoa chỉ được dùng chữ cái không dấu và chữ số"* | Mã khoa có dấu, khoảng trắng hoặc ký tự lạ | Ví dụ đúng: `HUYETHOC` |
| Khách báo **"không tìm thấy chứng từ"** khi mở một đơn | Đơn đó thuộc khoa khác | Đúng như thiết kế. Muốn xem hết thì phải là Quản lý |
| Khách báo **"Tài khoản chưa được kích hoạt"** | Tài khoản đã cấp nhưng chưa gán khoa và chưa bật | Làm **bước 4** — gán khoa phòng rồi tích Hoạt động |
| Khách báo **"Tài khoản chưa gắn với khách hàng nào"** | Tài khoản **không có** bản ghi Thành viên cổng nào — lỗi cấu hình | Tạo `Portal Member` cho tài khoản đó. Hai thông báo này khác nhau, đừng nhầm |

> **Vì sao "của khoa khác" và "không có thật" báo giống hệt nhau:** phân biệt hai
> cái đó chính là tiết lộ rằng chứng từ tồn tại. Trong bệnh viện, *"khoa Dược có
> đơn mã X"* đã là thông tin.

---

## 5. Checklist triển khai — đọc trước khi lên bản

**Ba việc, thiếu một là hỏng:**

1. **`bench --site <site> migrate`** — bắt buộc. Bản này thêm cột mới vào bảng đơn
   hàng. Chưa migrate mà chạy mã mới thì cổng khách **từ chối mọi truy vấn**.
2. **Khởi động lại worker sau khi migrate.** Hệ thống nhớ kết quả kiểm "cột đã có
   chưa" trong bộ nhớ tiến trình để khỏi hỏi lại mỗi truy vấn. Worker cũ vẫn nhớ
   giá trị trước migrate cho tới khi được khởi động lại — và nó sẽ **từ chối mọi
   truy vấn** dù cơ sở dữ liệu đã đúng.
3. **Kiểm patch đã chạy THẬT.** Có một bẫy đã gặp trên dự án này: `install_app`
   **ghi nhật ký patch mà không thật sự chạy nó**. Nên dòng khai báo trong
   `patches.txt` không phải bằng chứng. Chạy trên chính site đích:

```sql
-- phải trả về 1 dòng
select 1 from information_schema.columns
 where table_name='tabSales Order' and column_name='custom_khoa_phong';

-- phải có dòng, và skipped = 0
select name, creation, skipped from `tabPatch Log`
 where patch like '%them_khoa_phong_vao_don_hang%';
```

**Nếu quên bước 2 hoặc 3:** cổng khách từ chối mọi thứ (an toàn, không rò rỉ), và
có một dòng trong `Error Log` nói rõ thiếu cột. Chạy migrate, restart, xong.

---

## 6. Hệ thống cố ý CHƯA làm

Nói rõ để không ai chờ nhầm:

1. **Kho vật tư chưa cách ly theo khoa.** Nhân viên khoa vẫn thấy toàn bộ màn Kho —
   thuộc bước 8 của thiết kế.

   **Điều này có hệ quả cần biết, không phải chi tiết kỹ thuật:** phiếu nhập kho có
   ghi số đơn hàng sinh ra nó. Nên tới khi bước 8 xong, một nhân viên khoa vẫn có
   thể mở màn Kho, xem phiếu nhập và **đọc được số đơn của khoa khác** kèm mặt hàng
   và tổng tiền của đợt giao đó. Họ không mở được chính đơn hàng, nhưng cách ly theo
   khoa **chưa trọn vẹn** chừng nào bước 8 chưa chạy. Nếu bệnh viện hỏi, đừng nói
   là đã cách ly xong.
2. **Chưa có phiếu Đề xuất mua và luồng duyệt.** Nhân viên khoa hiện đặt hàng
   thẳng như trước, chỉ khác là đơn được đóng dấu khoa. Bước 5–6.
3. **Chưa có uỷ quyền tạm thời.** Quản lý đi vắng thì chưa có ai duyệt thay. Bước 7.
4. **Quản lý bệnh viện chưa tự cấp tài khoản được** — và sẽ không bao giờ được.
   Tạo tài khoản là tạo tài khoản trên hệ thống Miyano. Quản lý sẽ chỉ được gán
   khoa và bật/tắt thành viên (bước 9).
5. **Con số thông báo chưa đọc chưa lọc theo khoa.** Nội dung thông báo thì đã lọc
   — chỉ riêng con số trên huy hiệu là đếm chung.

---

## Phụ lục — Bảng trường

**`Portal Member`** (`TVC-.#####`)

| Trường | Kiểu | Ghi chú |
|---|---|---|
| `user` | Link User | **duy nhất** — một tài khoản thuộc đúng một bệnh viện |
| `customer` | Link Customer | bắt buộc |
| `vai_tro` | Chọn | `Quản lý` / `Nhân viên khoa` |
| `khoa_phong` | Link Customer Department | bắt buộc khi Nhân viên khoa đang hoạt động; **phải trống** với Quản lý |
| `active` | Tích | tắt thay vì xoá |

**`Customer Department`** (`KP-.#####`)

| Trường | Kiểu | Ghi chú |
|---|---|---|
| `customer` | Link Customer | **bắt buộc** (trước đây khoá theo kho) |
| `kho` | Link Customer Warehouse | tuỳ chọn |
| `ten_khoa_phong` | Data | bắt buộc, không trùng trong một bệnh viện (so không dấu) |
| `ma_khoa` | Data | chữ hoa `A–Z0–9`, không trùng trong một bệnh viện, `CHUNG` là mã dành riêng |
| `active` | Tích | |

**`Customer`** — thêm một trường

| Trường | Kiểu | Ghi chú |
|---|---|---|
| `custom_ma_ngan` | Data(10) | **duy nhất toàn hệ thống**. Bắt buộc trước khi cấp Nhân viên khoa |

**`Sales Order`** — thêm một trường

| Trường | Kiểu | Ghi chú |
|---|---|---|
| `custom_khoa_phong` | Link Customer Department | **chỉ đọc**, hệ thống ghi lúc tạo đơn từ khoa phòng của người đặt. Đơn cũ để trống |
