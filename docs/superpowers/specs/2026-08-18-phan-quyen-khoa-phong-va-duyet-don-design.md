# Phân quyền theo khoa phòng và luồng duyệt đơn trên cổng khách

**Ngày:** 18/08/2026
**Nguồn:** yêu cầu của chủ đầu tư sau góp ý của khách hàng Hi-medic.
**Trạng thái:** ĐỀ XUẤT ĐÃ CHỐT QUA ĐỐI THOẠI — chưa viết code, chưa tạo doctype,
chưa đụng schema. Cần chủ đầu tư đọc lại file này trước khi lập kế hoạch thi công.

Đánh số quyết định dùng tiền tố **QĐ-KP-**. Bộ tài liệu dự án đã có ba dãy "QĐ"
của ba văn bản khác nhau (hai dãy trong bộ BA, một dãy `QĐ-HM-` của tài liệu
Hi-medic ngày 17/08) — thêm một dãy trơn nữa là thêm một chỗ để hiểu sai.

---

## 1. Vấn đề

Hôm nay mỗi bệnh viện có **đúng một tài khoản** trên cổng. Mọi người trong bệnh
viện dùng chung tài khoản đó, nên:

- không biết ai đặt đơn nào;
- không có bước duyệt nội bộ của bệnh viện — người trực bấm là đơn đi thẳng
  sang Miyano;
- không chia được dữ liệu theo khoa phòng.

Yêu cầu: **nhiều tài khoản cho một bệnh viện**, chia theo khoa phòng, nhân viên
khoa lập đề nghị mua, quản lý bệnh viện xem và duyệt.

## 2. Hiện trạng đã đo trên `erptest.local`

Đo ngày 18/08, không suy từ ký ức:

| Việc | Số đo |
|---|---|
| Tài khoản cổng | **6 user / 6 khách hàng** — chưa khách nào có 2 user. Đường code hỗ trợ nhiều user/một khách nhưng **chưa từng chạy thật** |
| Danh tính cổng | User → `Contact` (field `user`) → `Dynamic Link` → `Customer`, cộng một `User Permission`. Role `Customer`, `user_type = Website User` |
| Khoa phòng | Doctype `Customer Department` (`KP-.#####`) **đã có**, nhưng khoá vào **`Customer Warehouse`** chứ không vào `Customer`. Toàn hệ thống mới **1 bản ghi**, `ma_khoa = "hs"` (chữ thường, không ràng buộc) |
| Endpoint cổng | **27 hàm `@frappe.whitelist()`** trong `api/portal.py` (khoảng **20** đụng tới đơn hàng hoặc thứ dẫn xuất) và **38 hàm** trong `api/kho.py` → **65 endpoint** phải rà. Con số kho lớn hơn ước lượng lúc bàn (~15) gấp hai lần rưỡi — xem §9 |
| Hàm đặt hàng | `portal_order_place` dài **139 dòng**, ôm cả dựng dòng hàng, kiểm hạn mức HĐNT và định giá |
| Workflow đang có | `Chờ xác nhận → Chờ Miyano xác nhận → Đã xác nhận / Từ chối`; **mọi** bước duyệt do `Sales User` của Miyano bấm. Chưa có bước nào cho người của bệnh viện |
| `Portal Item Request` | Là yêu cầu **một mặt hàng** để tìm nguồn, không phải phiếu đề nghị nhiều dòng → **không tái dụng được** |
| Collation CSDL | `utf8mb4_unicode_ci`. Thử thật: `LIKE '%gang tay%'` trả về đúng 5 mặt hàng "Găng tay"; `'%GĂNG%'` cũng trả về → **không dấu và không phân biệt hoa thường đã có sẵn**, không cần cột chuẩn hoá |
| Sổ cái kho | `Customer Stock Ledger Entry` và `Customer Stock Lot Balance` **không có** trường khoa phòng. `Customer Stock Issue` **có** `khoa_phong`; `Customer Stock Receipt` có `sales_order` (suy ra khoa được) |

## 3. Các quyết định đã chốt

| # | Câu hỏi | Đã chốt |
|---|---|---|
| **QĐ-KP-1** | Nhân viên khoa nhìn thấy đơn nào? | **Chỉ đơn của khoa mình.** Quản lý thấy tất cả |
| **QĐ-KP-2** | Đơn có phải luôn qua quản lý duyệt? | **Mọi đơn đều phải duyệt.** Chưa duyệt thì Miyano không thấy |
| **QĐ-KP-3** | Quản lý được làm gì khi duyệt? | **Sửa được cả mặt hàng lẫn số lượng** |
| **QĐ-KP-4** | Bao nhiêu người duyệt? | **Một quản lý chính + uỷ quyền tạm thời** |
| **QĐ-KP-5** | Mã đề nghị đặt theo gì? | **Theo khoa phòng**, kèm ô tìm theo mã/tên vật tư |
| **QĐ-KP-6** | Module kho có cách ly theo khoa không? | **Có** |
| **QĐ-KP-7** | Tồn kho — thứ không chia theo khoa được — thì sao? | **Ẩn các màn tồn kho khỏi nhân viên khoa, nhưng khi lập phiếu xuất vẫn hiện tồn của mặt hàng đang chọn** |
| **QĐ-KP-8** | Quản lý bệnh viện có tự tạo tài khoản không? | **Không.** Quản lý gán khoa, bật/tắt thành viên, lập uỷ quyền; **tạo tài khoản thì Miyano cấp**. *(Chủ đầu tư xác nhận 18/08: "nhân viên có tài khoản và được gán khoa bởi quản lý nhưng tài khoản sẽ được tạo ở phía Miyano")* |
| **QĐ-KP-9** | Phiếu đề nghị ghi những gì để truy vết? | **Tên người yêu cầu, ngày giờ, và LÝ DO yêu cầu** — lý do thành field riêng bắt buộc, không gộp vào ô ghi chú |
| **QĐ-KP-10** | Ai xoá được phiếu đề nghị? | Nhân viên xoá được **phiếu nháp của mình**; quản lý gỡ được phiếu đã gửi — nhưng **gỡ = chuyển trạng thái Đã huỷ, không xoá khỏi CSDL** (xem §5.4b) |

---

## 4. Nền danh tính và phạm vi dữ liệu

### 4.1 `Portal Member` — bảng thành viên cổng

Doctype mới, thành **nguồn sự thật duy nhất** cho câu hỏi "user này là ai trên cổng":

| Trường | Kiểu | Ràng buộc |
|---|---|---|
| `user` | Link User | bắt buộc, **duy nhất** — một tài khoản thuộc đúng một bệnh viện |
| `customer` | Link Customer | bắt buộc |
| `vai_tro` | Select: `Quản lý` / `Nhân viên khoa` | bắt buộc |
| `khoa_phong` | Link Customer Department | bắt buộc khi `vai_tro = Nhân viên khoa`; **phải để trống** khi là Quản lý |
| `active` | Check | mặc định 1 |

Hai luật chặn lúc `validate`:

1. **Mỗi bệnh viện đúng một `Quản lý` đang hoạt động.** (QĐ-KP-4 chọn mô hình một
   quản lý chính; nhiều quản lý cùng lúc sẽ làm khái niệm uỷ quyền vô nghĩa.)
2. **`khoa_phong.customer` phải bằng `customer`.** Không chặn thì gán được khoa
   của bệnh viện khác — một lỗ phân quyền mở bằng một thao tác nhập liệu.

Tắt (`active = 0`) thay vì xoá: một thành viên đã nghỉ vẫn phải còn đó để lịch
sử duyệt và lịch sử đề nghị giải thích được.

### 4.2 `portal_context` viết lại

`get_allowed_customers()` đọc `Portal Member` thay vì `Contact`. **Không giữ
đường Contact song song** — hai nguồn sự thật cho cùng một câu hỏi "user này
thuộc bệnh viện nào" là đúng loại lỗi app này đã trả giá hai lần. `Contact` giữ
nguyên cho email/liên hệ, chỉ thôi làm căn cứ phân quyền.

Bổ sung bốn hàm, và **chỉ bốn hàm này** được quyết định phạm vi:

```
get_portal_member(user)   -> bản ghi thành viên; PermissionError nếu không có
la_quan_ly(user)          -> True nếu là Quản lý đang hoạt động HOẶC đang
                             có uỷ quyền còn hiệu lực HÔM NAY
pham_vi_don(user)         -> điều kiện lọc cho mọi endpoint LIỆT KÊ
dam_bao_xem_duoc(ct)      -> chặn ở mọi endpoint ĐỌC MỘT chứng từ
```

`pham_vi_don()` trả "toàn bộ đơn của bệnh viện" khi `la_quan_ly()` đúng, và
`{khoa_phong: <khoa của user>}` khi sai.

**Chiều ngược lại cũng phải chuyển, nếu không lời hứa "một nguồn sự thật" là giả.**
App hỏi cả câu ngược — "bệnh viện này có những user nào" — ở hai chỗ, và cả hai
đang đi qua `Contact`:

| Chỗ | Hôm nay | Phải đổi thành |
|---|---|---|
| `portal_thong_bao_khach._portal_users_cua_khach()` | Customer → Dynamic Link → Contact → User | đọc `Portal Member` |
| `portal_provision()` (`api/portal.py:1758`) | tạo Contact + `User Permission` | tạo **thêm** `Portal Member` |

Bỏ sót ô thứ nhất: user có `Portal Member` nhưng không có `Contact` sẽ **không
nhận được thông báo nào**, còn user có `Contact` cũ đã bỏ thì **nhận thông báo về
dữ liệu mà `pham_vi_don()` không cho mở** — đúng cái "hai câu trả lời cho một câu
hỏi" mà §11.6 loại trừ.

Bỏ sót ô thứ hai: patch bước 3 điền cho 6 tài khoản đang có, nhưng **mọi tài
khoản cấp sau đó đều vô hình** với tầng danh tính mới.

**Quy ước sau khi chuyển:** một `Contact` có `user` mà **không** có `Portal Member`
là **lỗi cấu hình**, không phải trường hợp hợp lệ — `portal_provision` không tạo
ra được tình huống đó nữa, và một kiểm tra chạy định kỳ ghi Error Log nếu nó xuất
hiện. Viết ra thành luật thì patch bước 3 mới kiểm chứng được là đã chạy đủ.

**Điểm dễ sai:** `pham_vi_don()` phải hỏi `la_quan_ly()`, **không** hỏi
`vai_tro`. Người được uỷ quyền thường là nhân viên một khoa; trong thời gian uỷ
quyền họ phải nhìn được đơn của mọi khoa, nếu không thì không duyệt được. Hết
hạn thì tầm nhìn tự thu lại. Đây là một hàm **phụ thuộc thời gian**.

### 4.3 Khoa phòng chuyển từ kho lên bệnh viện

`Customer Department` thêm `customer` (Link Customer, bắt buộc), hạ `kho` xuống
tuỳ chọn. Patch điền ngược `customer` từ `kho.customer` cho bản ghi đang có.

Vì sao bắt buộc: đặt hàng thì bệnh viện nào cũng làm, kho thì chỉ vài bệnh viện
có. Không chuyển thì Hi-medic (chưa mở kho) không có khoa phòng nào để mà phân
quyền. Sau khi chuyển, **một danh mục dùng chung** cho cả đặt hàng lẫn kho —
không có chuyện "Khoa Huyết học" bên đặt hàng khác "Khoa Huyết học" bên kho.

`ten_khoa_phong` là chữ tự do nên khai "Phòng khám 1", "Phòng Xét nghiệm",
"Phòng Cấp cứu" đều được — không ràng buộc phải là "khoa" của bệnh viện lớn.

`ma_khoa` siết lại: **bắt buộc, tự viết hoa, chỉ `A-Z0-9`, duy nhất trong một
bệnh viện** (dùng để sinh mã đề nghị — xem §6).

`Customer` thêm `custom_ma_ngan`: bắt buộc với khách dùng cổng, duy nhất. 6 giá
trị. Kiểm **lúc bật tính năng cho bệnh viện** (lúc tạo `Portal Member` đầu tiên
có `vai_tro = Nhân viên khoa`), **không** kiểm lúc nhân viên bấm gửi — không để
một người soạn xong đề nghị rồi mới nhận một lỗi khó hiểu.

### 4.4 Một chốt phạm vi, không phải 20 bộ lọc

Cổng có ~20 endpoint đụng tới đơn hàng. Nếu mỗi cái tự viết điều kiện lọc thì
việc *một* cái quên lọc là chắc chắn xảy ra — tuần 17–18/08 app đã dính đúng
kiểu đó hai lần (phiếu trả hàng lọt vào danh sách đợt giao; phiếu giao nháp lọt
ra cổng khách).

Thiết kế: mọi endpoint liệt kê gọi `pham_vi_don()`; mọi endpoint đọc một chứng
từ gọi `dam_bao_xem_duoc()`. Cộng **một test đếm ngược** (§8b).

`Sales Order` nhận thêm `custom_khoa_phong` (Link Customer Department, chỉ đọc,
ghi lúc tạo đơn từ phiếu đề nghị).

**Thứ dẫn xuất không có trường khoa phòng riêng** — phiếu giao, hoá đơn, biên
bản kiểm hàng đều lọc **qua đơn cha**. Một nguồn sự thật; không có chuyện phiếu
giao nói khoa A còn đơn nói khoa B.

### 4.5 Sáu tài khoản đang chạy không đổi hành vi

Patch cấp cho cả 6 tài khoản hiện có `vai_tro = Quản lý`, `khoa_phong` trống →
phạm vi của họ vẫn là toàn bộ đơn của bệnh viện, đúng như hôm nay.

**Ràng buộc tự đặt cho thiết kế: đề án này không được làm phiền khách đang dùng.**
Bệnh viện nào chưa muốn dùng khoa phòng thì không phải làm gì cả.

---

## 5. `Đề nghị mua`

### 5.1 Vì sao là một doctype riêng, không phải Sales Order nháp

Đã cân nhắc ba hướng; chọn doctype riêng vì:

- **"Miyano không thấy đơn chưa duyệt" thành tính chất của schema**, không phải
  một bộ lọc phải nhớ áp đúng ở nhiều chỗ. Miyano không được cấp quyền nào trên
  doctype này. Đây chính là bài học của hai lỗi tuần 17–18/08.
- **Số `SAL-ORD` chỉ sinh khi bệnh viện đã thật sự chốt** — không có đơn "ma"
  nằm trong danh sách, báo cáo, dashboard của Miyano.
- Đối chiếu "đề nghị gốc / đã duyệt" thành **hai chứng từ**, không phải một cái diff.

Giá phải trả: tách phần lõi của `portal_order_place` thành hàm dùng chung (§9).

### 5.2 Cấu trúc

**Đầu phiếu:** `customer`, `khoa_phong`, `loai_don` (HĐNT / Mua lẻ), `hdnt`,
`ngay_can`, `dia_chi_giao`, `ghi_chu`, `trang_thai`, `request_id` (chống trùng,
chuyển từ tầng đơn hàng xuống đây), `nguoi_duyet`, `thoi_diem_duyet`,
`duyet_voi_tu_cach`, `uy_quyen`, `ly_do_tu_choi`, `sales_order`.

**Khối truy vết (QĐ-KP-9)** — ba thứ hiện ngay đầu phiếu, không phải đi tìm
trong lịch sử:

| Trường | Nguồn | Ghi chú |
|---|---|---|
| `nguoi_yeu_cau` | `owner`, chỉ đọc | Hệ thống ghi, không nhập tay — đây là **user thao tác**, không phải một cái tên gõ vào |
| `thoi_diem_gui` | Datetime, chỉ đọc | Ghi lúc bấm **Gửi duyệt**, không phải lúc tạo nháp. Nháp soạn ba ngày rồi mới gửi thì mốc truy vết là lúc gửi |
| `ly_do_yeu_cau` | Small Text, **bắt buộc khi Gửi duyệt** | Vì sao khoa cần hàng này. Field RIÊNG, không gộp vào `ghi_chu`: một ô để trống được thì sẽ luôn trống, và đúng lúc cần truy vết thì không có gì để đọc |

`ly_do_yeu_cau` bắt buộc **ở bước Gửi duyệt**, không phải lúc lưu nháp — bắt điền
ngay từ dòng đầu tiên sẽ khiến người ta gõ "abc" cho xong.

`customer` và `khoa_phong` **chỉ đọc, hệ thống ghi từ phiên đăng nhập** — không
nhận từ client. Người của khoa Huyết học không lập được đề nghị mang tên khoa
khác kể cả khi sửa payload.

**Dòng hàng** (`Đề nghị mua Item`): `item_code`, `dvt`, `so_luong_de_nghi`,
`so_luong_duyet`, `don_gia`, `thanh_tien`, `nguon_dong`, `ghi_chu_quan_ly`.

Bảng "đặt ngoài" **dùng lại `Sales Order Dat Ngoai Item`** đã có — child doctype
gắn được vào nhiều cha, không tạo bảng mới.

### 5.3 Giữ nguyên đề nghị gốc: quản lý **không xoá dòng, chỉ hạ về 0**

QĐ-KP-3 cho quản lý sửa cả mặt hàng lẫn số lượng, nên phải trả lời được "khoa
xin gì / duyệt gì". Cách chắc nhất **không phải** là chụp một bản snapshot đặt
cạnh bản sống — hai bản dữ liệu song song thì sớm muộn cũng lệch.

- Khi khoa bấm **Gửi duyệt**, cột `so_luong_de_nghi` **khoá vĩnh viễn**. Không
  ai sửa được nữa, kể cả quản lý, kể cả Miyano.
- Quản lý chỉ chạm `so_luong_duyet`. Bỏ một mặt hàng = **hạ về 0**, không xoá dòng.
- Quản lý thêm mặt hàng → dòng mới có `so_luong_de_nghi = 0`,
  `nguon_dong = "Quản lý thêm"`.
- Sales Order sinh ra **chỉ từ dòng có `so_luong_duyet > 0`**.

Kết quả: đề nghị gốc còn nguyên **theo cấu trúc**, không cần cơ chế nào giữ nó.

### 5.4 Vòng đời

```
Nháp ──Gửi duyệt──► Chờ duyệt ──Duyệt──► Đã duyệt ──► sinh Sales Order
 │                      │
 │                      └──Từ chối (bắt buộc lý do)──► Từ chối ──sửa──► Chờ duyệt
 └──Huỷ──► Đã huỷ
```

### 5.4b Xoá và huỷ — hai việc khác nhau (QĐ-KP-10)

Chủ đầu tư yêu cầu cả nhân viên lẫn quản lý **xoá được phiếu**. Nhưng yêu cầu đó
đụng thẳng vào QĐ-KP-9 (*"ghi tên ngày giờ lý do để sau này truy vết"*): một
phiếu xoá khỏi cơ sở dữ liệu thì không truy vết được gì cả. Phân đôi theo việc
phiếu **đã được ai khác nhìn thấy hay chưa**:

| Trạng thái | Ai làm được | Việc gì xảy ra |
|---|---|---|
| **Nháp** (chưa gửi) | Nhân viên lập phiếu, và quản lý | **XOÁ THẬT.** Chưa ai ngoài người lập nhìn thấy, chưa sinh mã, không có gì để truy vết |
| **Chờ duyệt** trở đi | Quản lý | **Chuyển sang `Đã huỷ`**, phiếu còn nguyên. Đã có mã, quản lý đã nhìn thấy, đã vào danh sách chờ duyệt |
| **Đã duyệt** | Quản lý | Đã thành Sales Order — theo luật huỷ đơn đang có |

Nút trên màn hình vẫn ghi **"Xoá"** ở trạng thái Nháp và **"Huỷ phiếu"** từ Chờ
duyệt trở đi, để người dùng thấy đúng việc mình đang làm.

Nhân viên **không** huỷ được phiếu đã gửi: một phiếu đang nằm trong danh sách chờ
của quản lý mà biến mất giữa chừng là thứ khó chịu nhất cho người duyệt. Muốn rút
thì nhờ quản lý, hoặc quản lý từ chối.

Sửa số lượng: nhân viên sửa thoải mái khi còn **Nháp**; từ **Chờ duyệt** trở đi
chỉ quản lý sửa (`so_luong_duyet`), và `so_luong_de_nghi` khoá vĩnh viễn (§5.3).

### 5.5 Quản lý đặt hàng trực tiếp — vẫn một đường giấy tờ

Quản lý bấm đặt trên giỏ hàng thì hệ thống vẫn lập một `Đề nghị mua`, **tự động
đánh Đã duyệt ngay** với `nguoi_duyet` là chính họ, rồi sinh Sales Order. Không
phải bấm thêm nút nào, mà **mọi đơn trên hệ thống đều có đúng một chứng từ đề
nghị đứng sau** — không có hai loại đơn với hai lịch sử khác nhau.

Nhân viên khoa gọi thẳng `portal_order_place` thì bị từ chối kèm thông báo rõ,
không phải lỗi 500 khó hiểu.

**Quản lý không thuộc khoa nào (§4.1), nên phải chọn khoa lúc đặt.** Nếu bỏ qua
điều này thì mã đề nghị của quản lý không có phần `[Mã khoa]` để mà sinh, và
`Sales Order.custom_khoa_phong` để trống khiến mọi thứ dẫn xuất từ đơn đó không
quy về được khoa nào. Quy ước:

* Giỏ hàng của quản lý có thêm ô chọn khoa phòng, mặc định **"Toàn viện"**.
* Chọn một khoa → đơn thuộc khoa đó, nhân viên khoa đó nhìn thấy đơn và mọi
  phiếu giao/hoá đơn của nó. Dùng khi quản lý đặt hộ một khoa.
* Chọn **"Toàn viện"** → `custom_khoa_phong` để trống, mã dùng mã khoa dành
  riêng **`CHUNG`** (`BM-CHUNG-260817-01`). Đơn này **chỉ quản lý thấy** — đúng
  theo `pham_vi_don()`, không cần luật riêng.
* `CHUNG` là mã dành riêng: `Customer Department.ma_khoa` **không được** nhận
  giá trị này, nếu không hai thứ khác nhau sẽ sinh ra cùng một mã.

Với đơn của quản lý, mã sinh **ngay lúc tạo** — vì lúc đó "gửi duyệt" và "duyệt"
xảy ra cùng một thời điểm (§5.5), nên quy tắc "sinh lúc Gửi duyệt" ở §6.2 vẫn
đúng nguyên văn, không phải một ngoại lệ.

### 5.6 Hai cái bẫy mà mô hình nhiều khoa mới sinh ra

**Hạn mức hợp đồng khung là tài nguyên chung giữa các khoa.** Trước đây một bệnh
viện một tài khoản nên không bao giờ có hai người cùng tiêu một hạn mức. Giờ hai
khoa có thể cùng soạn đề nghị trên cùng một dòng hợp đồng.

→ **Đề nghị chỉ cảnh báo; hạn mức chỉ trừ lúc DUYỆT** (đúng như ERPNext trừ
`ordered_qty` lúc tạo đơn). Tới lúc duyệt mà hạn mức đã hết thì việc duyệt
**thất bại kèm tên khoa đã tiêu mất** — không im lặng cắt số lượng xuống.

**Giá có thể đổi giữa lúc đề nghị và lúc duyệt.** App đã có cơ chế đồng bộ giá HĐNT.

→ **Giá tính lại tại thời điểm duyệt** (đó là lúc Sales Order ra đời và là giá
ràng buộc với Miyano), nhưng nếu khác giá khoa đã nhìn thấy thì **báo cho quản
lý trước khi họ bấm**, không đổi lặng lẽ.

### 5.7 Uỷ quyền tạm thời

Doctype `Portal Delegation`: `customer`, `nguoi_uy_quyen` (phải là Quản lý),
`nguoi_nhan`, `tu_ngay`, `den_ngay`, `ly_do`, `active`.

Ràng buộc: `den_ngay >= tu_ngay`; không chồng lấn hai uỷ quyền còn hiệu lực của
cùng một quản lý; `nguoi_nhan != nguoi_uy_quyen`; `nguoi_nhan` phải là
`Portal Member` đang hoạt động của cùng bệnh viện.

Ba chi tiết không được bỏ:

1. **Tầm nhìn nở ra rồi thu lại theo thời gian** — xem §4.2.
2. **Mỗi lần duyệt ghi rõ tư cách** (`Quản lý chính` / `Được uỷ quyền` + trỏ về
   phiếu uỷ quyền). Không ghi thì ba tháng sau không ai giải thích được vì sao
   một người không phải quản lý lại duyệt được đơn đó.
3. **Không tự duyệt đề nghị của chính mình.** Người được uỷ quyền vẫn là nhân
   viên một khoa và vẫn lập đề nghị cho khoa mình; để họ tự duyệt là mất hẳn ý
   nghĩa của bước duyệt. Trường hợp này đẩy về quản lý chính.

### 5.8 Thông báo

Dùng lại đúng khuôn `Notification Log` đang chạy (`portal_thong_bao_khach.py`),
thêm một hàm chọn người nhận theo khoa:

| Việc | Ai nhận |
|---|---|
| Khoa gửi đề nghị | Quản lý + người đang được uỷ quyền |
| Quản lý duyệt / từ chối | Người lập đề nghị + thành viên khác của khoa đó |
| Miyano xác nhận, hẹn giao, giao hàng | Quản lý + thành viên của khoa đứng tên đơn |

Điều này cũng sửa một chỗ hôm nay đang thô: thông báo giao hàng gửi cho **mọi**
tài khoản của bệnh viện. Với một tài khoản thì đúng; với mười lăm tài khoản thì
khoa Dược nhận thông báo về hàng của khoa Huyết học mỗi ngày.

---

## 6. Mã đề nghị và tìm kiếm theo vật tư

### 6.1 Cấu trúc mã

```
BM-HUYETHOC-260817-01
│   │        │      └─ số thứ tự trong ngày của chính khoa đó
│   │        └─ ngày gửi duyệt, YYMMDD
│   └─ mã khoa phòng (Customer Department.ma_khoa)
└─ mã bệnh viện (Customer.custom_ma_ngan)
```

**Vì sao theo khoa chứ không theo nhóm sản phẩm** (tài liệu Hi-medic 17/08 đề
xuất `[Nhóm]-[Tên ngắn]-[YYMMDD]-[NN]`):

1. **Khoa phòng biết chắc lúc tạo và không bao giờ đổi.** Nhóm sản phẩm đổi khi
   quản lý sửa dòng hàng (QĐ-KP-3), nên mã suy từ mặt hàng sẽ nói sai về chính
   đơn nó đặt tên.
2. **Cởi được nút thắt dữ liệu.** Mã theo nhóm buộc phải dọn xong `Item Group`
   (nhóm `Sản phẩm` đang ôm 35/164 = 21% mặt hàng; `Hóa chất sinh phẩm` và
   `Hoá chất xét nghiệm` là hai nhóm khác nhau chỉ vì một dấu tiếng Việt) và
   nhập "tên viết ngắn" cho 164 mặt hàng. Mã theo khoa cần **6 mã bệnh viện +
   mã của từng khoa**. Việc dọn `Item Group` vẫn cần cho báo cáo phân loại nhà
   cung cấp (YC-3 của tài liệu Hi-medic), nhưng **thôi chắn đường** tính năng này.
3. Cái mất — nhìn mã không đoán được đơn về hàng gì — do **ô tìm kiếm** (§6.3)
   gánh, và gánh tốt hơn: mã chỉ chứa được *một* mặt hàng, ô tìm kiếm tra được
   *mọi* mặt hàng trong *mọi* phiếu.

**Vì sao có mã bệnh viện ở đầu:** tên chứng từ trong Frappe phải duy nhất toàn
cục. Nhiều bệnh viện sẽ đặt mã khoa giống nhau (`HS`, `HH`, `XN` là những chữ
viết tắt hiển nhiên) — không có tiền tố bệnh viện thì hoặc lưu không được, hoặc
phải đếm chung khiến số của một bệnh viện nhảy cách. Có tiền tố thì **mỗi khoa
của mỗi bệnh viện có dãy số liền mạch của riêng mình**.

Vượt 99 đề nghị cùng tiền tố trong ngày thì **tràn sang 3 chữ số**, không quay
vòng — mã trùng tệ hơn mã dài.

### 6.2 Sinh mã lúc **Gửi duyệt**

Không sớm hơn, không muộn hơn:

- Lúc còn **Nháp** giỏ hàng vẫn đang thay đổi → sinh mã lúc đó là sinh một cái sẽ sai.
- Lúc **Duyệt** thì đã muộn — quản lý cần mã để gọi tên đơn khi trao đổi với khoa.
- Sinh tại **Gửi duyệt** thì mã suy từ dữ liệu đã đóng băng (cùng thời điểm
  `so_luong_de_nghi` khoá lại).

Mã hiện trên màn xác nhận **trước** khi khoa bấm gửi. Không cho sửa tay.

### 6.3 Ô tìm theo mã / tên vật tư

Endpoint `de_nghi_mua_tim(tu_khoa, khoa_phong=None, gom_da_xu_ly=False)`:

- **Phạm vi lấy từ phiên đăng nhập**, qua đúng `pham_vi_don()` (§4.2). Quản lý và
  người đang được uỷ quyền tìm khắp các khoa; nhân viên khoa chỉ trong khoa mình.
  **Không nhận phạm vi từ client.**
- Khớp trên `item_code`, `item_name`, **và cả dòng "đặt ngoài"**. Bỏ sót dòng đặt
  ngoài thì một phiếu toàn hàng chưa có mã sẽ **vô hình** trước ô tìm kiếm —
  đúng loại phiếu quản lý cần xem kỹ nhất.
- Không cần chuẩn hoá dấu: collation `utf8mb4_unicode_ci` đã lo (đã thử, §2).
- Mặc định chỉ tìm phiếu **Chờ duyệt**; công tắc "tìm cả phiếu đã xử lý" để quản
  lý tra lại *"tháng này đã duyệt găng tay chưa"*.
- Trả về **kèm chính dòng khớp** để gợi ý đọc được ngay.
- Tối thiểu 2 ký tự, chờ ngừng gõ rồi mới gọi, giới hạn số dòng.

**Hạn chế nói trước:** `LIKE '%...%'` không dùng được index. Ở quy mô hiện tại
không đáng kể; khi cần thì cách chữa là dùng tìm kiếm toàn cục của Frappe, không
phải viết lại.

---

## 7. Cách ly module kho (QĐ-KP-6, QĐ-KP-7)

### 7.1 Chia được tới đâu

| Đối tượng | Chiều khoa phòng | Cách ly |
|---|---|---|
| **Phiếu xuất** (`Customer Stock Issue`) | `khoa_phong` **có sẵn** trên đầu phiếu | Sạch sẽ |
| **Báo cáo cấp phát** (kể cả bản theo tháng, 17/08) | Đã nhóm theo khoa | Sạch sẽ |
| **Nhật ký vật tư** | Suy được cho dòng xuất | Được, phần dòng xuất |
| **Phiếu nhập** (`Customer Stock Receipt`) | Có `sales_order` → suy ra khoa | Được, **trừ** phiếu nhập tay và nhập tồn đầu kỳ (không có đơn) → **không thuộc khoa nào, chỉ quản lý thấy** |
| **Tồn kho, thẻ kho, N-X-T, cảnh báo hạn dùng, tồn theo lô** | **Không có, và không thể có** | **Không cách ly được** |

Dòng cuối không phải thiếu sót của schema: một hộp găng nằm trong kho là **của
bệnh viện**, nó chưa thuộc khoa nào cho tới lúc được cấp phát. "Tồn kho của khoa
Huyết học" là một con số không tồn tại. Muốn nó tồn tại thì phải đổi mô hình kho
— mỗi khoa một tồn riêng, cấp phát thành chuyển kho — lớn hơn cả phần đặt hàng
cộng lại. **Không làm.**

### 7.1b Chiều khoa đi VÀO tầng phân quyền kho đã có, không dựng tầng thứ hai

`kho/permissions.py` **đã có sẵn** `permission_query_conditions` cho tám doctype
kho (`_kho_condition`, `_child_condition`, `kho_child_has_permission`,
`voucher_item_readable`, `_is_restricted_user`). Đọc chú thích trong `hooks.py`
thì rõ vai trò của nó: với role `Customer` hiện tại **các hook này không bao giờ
được gọi tới** (không có DocPerm nền thì framework chặn trước) — chúng là **lớp
phòng thủ thứ hai**, còn **cổng thật là `api/kho.py`**.

Nên chiều khoa phòng đi vào **cả hai**, không dựng cái thứ ba:

* **Tầng chính** — `api/kho.py` gọi `pham_vi_don()` / `dam_bao_xem_duoc()`, cùng
  đúng hai hàm mà phần đơn hàng dùng (§4.2).
* **Tầng phòng thủ** — `_kho_condition` nhận thêm vế khoa phòng, để nếu ai đó cấp
  lại DocPerm cho một role Website User trong tương lai thì lớp thứ hai vẫn trả
  lời **giống** lớp thứ nhất. Hai lớp trả lời khác nhau còn tệ hơn một lớp.

### 7.1c Số endpoint kho thật sự phải sửa

`api/kho.py` có **38** hàm whitelist, nhưng không phải cái nào cũng đọc dữ liệu
quy được về khoa. Phân loại:

| Nhóm | Số | Việc |
|---|---|---|
| Đọc/ghi dữ liệu **có khoa** — phiếu xuất, báo cáo cấp phát (2 cái), nhật ký, đợt, xuất Excel, PDF, gợi ý người nhận, danh mục khoa | ~13 | Áp `pham_vi_don()` |
| **Tồn kho** — tồn, lô, N-X-T, thẻ kho, cảnh báo hạn, cảnh báo tồn, min/max, gợi ý lô | ~8 | Ẩn khỏi nhân viên khoa, **trừ** chế độ tra một mặt hàng (§7.2) |
| **Chỉ quản lý** hoặc trung tính — danh mục vật tư, NCC, nhập tồn đầu kỳ, phiếu nhập, `kho_me` | ~17 | Chặn theo vai trò, không cần lọc theo khoa |

Con số này thay cho ước lượng "~15" lúc bàn thiết kế **và** cho con số thô 38:
việc thật là **13 endpoint phải lọc + 8 phải thu hẹp**, phần còn lại chỉ chặn theo
vai trò. Bước 8 vẫn nặng, nhưng nặng vì **8 endpoint tồn kho cần chế độ thu hẹp**
chứ không phải vì 38 bộ lọc.

### 7.2 Xử lý nhóm không chia được (QĐ-KP-7)

Nhân viên khoa **không có** các mục "Báo cáo N-X-T", "Thẻ kho", "Cảnh báo" trên
menu. Nhưng **trong form phiếu xuất, chọn một vật tư thì vẫn thấy tồn của đúng
mặt hàng đó** ("tồn: 3 hộp").

Lý do: ẩn sạch thì nhân viên khoa xuất mù — điền 20 hộp trong khi kho còn 3, tới
lúc lưu mới báo lỗi. Thấy đủ để làm việc, không thấy được toàn cảnh kho.

**Danh mục vật tư vẫn hiện** với nhân viên khoa — đó là catalogue, không phải dữ
liệu của khoa nào, và không có nó thì không lập được phiếu xuất (nhưng **sửa**
danh mục là việc của quản lý).

**Cách làm cụ thể — "chế độ thu hẹp", không phải chặn/mở nhị phân.** Hai endpoint
`kho_ton` và `kho_lo_goi_y` là thứ form phiếu xuất cần: với nhân viên khoa, chúng
**bắt buộc phải có tham số `vat_tu` cụ thể** và chỉ trả về đúng mặt hàng đó. Duyệt
cả kho thì không, tra một mặt hàng đang chọn thì có. Sáu endpoint tồn kho còn lại
(N-X-T, thẻ kho, cảnh báo hạn, cảnh báo tồn, min/max, danh sách lô toàn kho) chặn
hẳn với nhân viên khoa.

---

## 8. Kiểm thử

### 8a. Cách ly

Với **mỗi họ endpoint** (đơn hàng, phiếu giao, hoá đơn, biên bản kiểm, thông báo,
đề nghị mua, phiếu xuất kho, báo cáo cấp phát): nhân viên khoa A gọi trên chứng
từ của khoa B → **`PermissionError`**, và **không lộ cả sự tồn tại** của nó —
thông báo lỗi giống hệt trường hợp chứng từ không có thật.

### 8b. Test đếm ngược cho endpoint

Liệt kê mọi hàm `@frappe.whitelist()` trong `api/portal.py` và `api/kho.py`; bắt
lỗi nếu có cái nào không nằm trong `DA_AP_PHAM_VI` hoặc `MIEN_PHAM_VI` (kèm lý do
viết ra chữ). Đây là cái chặn lỗi *sẽ* xảy ra sáu tháng nữa, khi ai đó thêm
endpoint thứ 28.

### 8c. Nghiệp vụ

| Test | Chốt điều gì |
|---|---|
| Gửi duyệt xong sửa `so_luong_de_nghi` → bị chặn | đề nghị gốc bất biến |
| Quản lý hạ về 0 → dòng **còn nguyên**, Sales Order **không có** dòng đó | không xoá, chỉ hạ |
| Hai khoa cùng tiêu một dòng hợp đồng; duyệt cái thứ hai → thất bại **kèm tên khoa đã tiêu** | hạn mức là tài nguyên chung |
| Giá đổi giữa đề nghị và duyệt → báo quản lý, không đổi lặng lẽ | giá chốt lúc duyệt |
| Uỷ quyền ở **ba mốc** (trước / trong / sau) → tầm nhìn nở ra rồi thu lại | phạm vi phụ thuộc thời gian |
| Người được uỷ quyền duyệt phiếu do chính mình lập → bị chặn | không tự duyệt |
| Sinh mã: liền mạch trong một khoa; hai bệnh viện không đụng nhau; vượt 99 tràn 3 chữ số | mã duy nhất |
| Tìm `gang tay` ra `Găng tay`; phiếu **toàn dòng đặt ngoài** vẫn tìm ra | không bỏ sót |
| Nhân viên khoa lập phiếu xuất: thấy tồn của mặt hàng đang chọn, **không** gọi được endpoint báo cáo N-X-T | QĐ-KP-7 |
| 6 tài khoản hiện có: mọi endpoint trả **đúng kết quả như trước** khi chưa gán khoa | không làm phiền khách đang dùng |

Test uỷ quyền phải **đóng băng ngày**. Một hàm phụ thuộc thời gian mà test chạy
theo đồng hồ thật thì sẽ hỏng vào một ngày không ai đoán được.

Fixture phải **tự dọn trong `setUp`**: `FrappeTestCase` rollback một lần cho cả
CLASS, không phải từng test.

---

## 9. Thứ tự triển khai

**Tính chất quan trọng nhất: đề án này nằm im cho tới khi Miyano bật.** Sau khi
cài xong, mọi tài khoản hiện có đều là `Quản lý` không gắn khoa → `pham_vi_don()`
trả "toàn bộ đơn của bệnh viện" → hành vi y hệt hôm nay. Cách ly chỉ bắt đầu có
tác dụng khi Miyano thật sự tạo một `Portal Member` có `vai_tro = Nhân viên khoa`.

Nghĩa là các bước nền lên site thật và chạy song song mà không ai thấy khác gì,
rồi **bật cho từng bệnh viện một** — Hi-medic trước. Không có ngày "cả hệ thống
đổi cách hoạt động".

| Bước | Nội dung | Người dùng thấy gì |
|---|---|---|
| **0** | ~~Sửa 3 lỗi đã phát hiện 18/08~~ — **XONG** (commit `678775e`, TDD, suite xanh) | Hết đợt giao âm phần trăm |
| **1** | Tách lõi đặt hàng ra `dat_hang.py` | **Không gì cả** — suite phải xanh, **không sửa một test nào** |
| **2** | Khoa phòng chuyển từ kho lên bệnh viện; siết `ma_khoa`; thêm `Customer.custom_ma_ngan` | Màn khoa phòng ra khỏi mục Kho |
| **3** | `Portal Member` + viết lại `portal_context` + **chuyển `_portal_users_cua_khach()` và `portal_provision()` sang `Portal Member`** (§4.2) + patch 6 tài khoản + test đếm ngược | **Không gì cả** |
| **4** | Áp phạm vi lên ~20 endpoint đơn hàng; `Sales Order.custom_khoa_phong` | **Không gì cả** (chưa ai được gán khoa) |
| **5** | `Đề nghị mua`: doctype, luồng duyệt, sinh mã, màn của khoa phòng | Bật được cho Hi-medic |
| **6** | Màn duyệt của quản lý + ô tìm theo vật tư | |
| **7** | Uỷ quyền tạm thời | |
| **8** | Cách ly module kho (§7): 13 endpoint áp phạm vi, 8 endpoint chuyển sang chế độ thu hẹp, thêm vế khoa vào `_kho_condition` | |
| **9** | Màn thành viên & phân quyền cho quản lý | |

Bước 1–4 không đổi gì với người dùng — **cố ý**. Bốn bước nền lên site trước,
chạy thật một thời gian, rồi mới bật tính năng. Nếu có gì hỏng ở tầng phân quyền
thì nó lộ ra khi chưa có ai phụ thuộc vào nó.

### Rủi ro lớn nhất

Bước 4 và bước 8 phải **rà** cả **65 endpoint** (27 ở `api/portal.py` + 38 ở
`api/kho.py`) để không sót cái nào, dù số phải **sửa** ít hơn nhiều — xem §7.1c
cho phân loại phía kho. Con số 38 là thứ đo lại sau khi viết bản nháp; lúc bàn
thiết kế ước ~15.

Sót một chỗ nghĩa là khoa này đọc được dữ liệu khoa kia — trong bệnh viện đó là
chuyện nghiêm trọng, không phải phiền toái.

**Ba lớp chắn:** (a) chỉ có **một** hàm quyết định phạm vi cho cả đơn hàng lẫn
kho, không phải mấy chục điều kiện lọc chép tay; (b) test đếm ngược bắt buộc mọi endpoint phải khai báo; (c)
đến hết bước 4 vẫn **chưa ai được gán khoa**, nên kể cả sót thì cũng chưa lộ gì —
có thời gian phát hiện trước khi bật.

Trước khi bật cho Hi-medic: **chứng minh RED** cho ít nhất một test cách ly —
cố tình bỏ điều kiện lọc, xem test đỏ đúng chỗ, rồi trả lại. Một test cách ly
không bao giờ đỏ là một test không kiểm gì cả.

---

## 10. Màn hình

**Mới:**

| Màn | Ai dùng | Nội dung |
|---|---|---|
| `/de-nghi` | Nhân viên khoa | Danh sách phiếu của khoa mình, theo trạng thái |
| `/de-nghi/:ma` | Cả hai | Hai cột **SL đề nghị / SL duyệt**; dòng bị cắt về 0 gạch ngang; dòng quản lý thêm có nhãn |
| `/duyet` | Quản lý + người được uỷ quyền | Lọc theo khoa, ô tìm theo vật tư, badge số phiếu chờ |
| `/thanh-vien` | Quản lý | Gán khoa, bật/tắt thành viên, lập uỷ quyền. **Không tạo được tài khoản** (QĐ-KP-8) |

**Phải sửa:**

- `Cart.vue` — nút cuối theo vai trò: nhân viên khoa thấy **"Gửi duyệt"**, quản
  lý thấy **"Đặt hàng"** như cũ. Hiện sẵn mã sẽ sinh trước khi bấm.
- `Orders.vue` / `OrderDetail.vue` — thêm cột **Khoa phòng** và dòng
  **"Từ đề nghị …"** trỏ ngược về phiếu gốc.
- `KhoaPhongList.vue` — chuyển từ `/kho/khoa-phong` sang `/khoa-phong`, giữ
  chuyển hướng cho đường cũ. Bệnh viện chưa mở kho vẫn phải khai được khoa phòng.
- Menu bên — hiện theo vai trò; nhân viên khoa không thấy mục Duyệt, mục Thành
  viên, và các mục tồn kho (§7.2).

---

## 11. Đề án này cố ý **không** làm

1. **Không duyệt hai cấp** (trưởng khoa rồi phòng vật tư) — QĐ-KP-4 chốt một cấp.
2. **Không cho quản lý bệnh viện tạo tài khoản** (QĐ-KP-8). Tạo `User` là tạo
   tài khoản trên hệ thống Miyano.
3. **Không dựng kho riêng cho từng khoa.** Sổ cái không có chiều khoa phòng và
   sẽ không thêm — xem §7.1.
4. **Không đổi tên 102 đơn `SAL-ORD-*` cũ.** Mã dễ đọc nằm trên phiếu đề nghị;
   đơn hàng chỉ chép lại vào `custom_ma_tra_cuu`.
5. **Không dựng cơ chế thông báo thứ hai.** Dùng lại khuôn `Notification Log`.
6. **Không giữ `Contact` làm căn cứ phân quyền song song với `Portal Member`.**

---

## 12. Câu hỏi còn mở

| # | Câu hỏi | Chặn bước nào |
|---|---|---|
| 1 | QĐ-KP-8 (quản lý không tự tạo tài khoản) — chủ đầu tư xác nhận? | 9 |
| 2 | Mã bệnh viện (`BM`, `HM`…) do ai đặt và đặt theo quy tắc gì? | 2 |
| 3 | Nhân viên khoa có được xem **hoá đơn và công nợ** của khoa mình không, hay công nợ là việc của quản lý? | 4 |
| 4 | Đơn đã duyệt mà khoa muốn đổi số lượng (đã có `portal_order_sua_so_luong`) — khoa tự sửa được hay phải qua quản lý lần nữa? | 4 |
| 5 | Người của khoa nghỉ việc: đề nghị và đơn của họ chuyển cho ai đứng tên? | 3 |
