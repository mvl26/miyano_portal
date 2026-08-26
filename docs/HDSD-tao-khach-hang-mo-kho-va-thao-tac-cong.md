# Hướng dẫn vận hành: tạo khách hàng · mở kho · thao tác trên cổng

Áp dụng cho app `miyano_portal` (supplycore v2) trên site **erptest.local**.
Cập nhật: 26/08/2026.

Tài liệu này có ba phần cho ba việc khác nhau, làm bởi hai loại người khác nhau:

| Phần | Ai làm | Làm ở đâu |
|---|---|---|
| [A. Tạo khách hàng + cấp tài khoản cổng](#a-tạo-khách-hàng-và-cấp-tài-khoản-cổng) | Nhân viên Miyano | Desk ERPNext (`/app`) |
| [B. Mở kho khách hàng](#b-mở-kho-khách-hàng) | Nhân viên Miyano | Desk ERPNext (`/app`) |
| [C. Thao tác trên cổng](#c-thao-tác-trên-cổng-dành-cho-khách-hàng) | Khách hàng | Cổng khách hàng (`/portal`) |

Kèm theo:
[D. Dữ liệu demo dựng sẵn](#d-dữ-liệu-demo-đã-dựng-sẵn) ·
[E. Sự cố thường gặp](#e-sự-cố-thường-gặp) ·
[F. Hạn chế đã biết](#f-hạn-chế-đã-biết)

**Địa chỉ truy cập môi trường thử nghiệm**

- Desk (nhân viên Miyano): <http://192.168.61.129:8003/app>
- Cổng khách hàng: <http://192.168.61.129:8003/portal/login>

> ⚠️ Toàn bộ tài liệu này nói về **erptest.local**. Site `supplycore-miyano.local`
> (cổng :8002) là site bệnh viện đang chạy thật của app `supplycore` cũ — không
> thao tác gì trên đó theo tài liệu này.

---

## A. Tạo khách hàng và cấp tài khoản cổng

Một khách hàng dùng được cổng cần **6 thứ**. Thiếu bất kỳ thứ nào thì khách đăng
nhập được nhưng màn hình sẽ trống hoặc báo lỗi — mục A7 nói rõ thiếu cái nào ra
lỗi gì.

| # | Bản ghi | Bắt buộc để | Doctype |
|---|---|---|---|
| 1 | Khách hàng | mọi thứ | `Customer` |
| 2 | Địa chỉ giao hàng | chọn nơi giao khi đặt hàng | `Address` |
| 3 | Bảng giá + giá từng mặt hàng | đặt hàng (thiếu giá → chặn đặt) | `Price List` + `Item Price` |
| 4 | Hợp đồng nguyên tắc | giá đã ký + hạn mức cho những mặt hàng trong hợp đồng | `Blanket Order` (Selling) |
| 5 | Tài khoản đăng nhập | đăng nhập cổng | `User` (Website User) |
| 6 | Liên kết tài khoản ↔ khách hàng | cổng biết "tôi là ai" | `Contact` + `User Permission` |

### A1. Tạo khách hàng

`/app/customer/new` — hoặc **Bán hàng › Khách hàng › Thêm mới**.

| Trường | Giá trị |
|---|---|
| Tên khách hàng | Tên đầy đủ của bệnh viện/đơn vị. Đây là tên khách nhìn thấy trên cổng. |
| Loại khách hàng | `Company` |
| Nhóm khách hàng / Khu vực | `All Customer Groups` / `All Territories` (nếu chưa có phân nhóm riêng) |
| Mã số thuế (`tax_id`) | Nhập nếu có — cổng hiển thị ở màn **Hồ sơ đơn vị** |
| **Bảng giá bán mặc định** | Bảng giá của chính khách này (mục A3). **Bắt buộc**: cổng lấy giá theo trường này. |

### A2. Địa chỉ giao hàng

`/app/address/new`, hoặc nút **Thêm địa chỉ** ngay trên form khách hàng.

- **Loại địa chỉ**: `Shipping`, tick **Là địa chỉ giao hàng**.
- Trong bảng **Liên kết**: `Link Document Type` = `Customer`, `Link Name` = khách vừa tạo.

Khách chọn địa chỉ này khi đặt hàng. Có thể tạo nhiều địa chỉ (nhiều khoa, nhiều
cơ sở) — cổng liệt kê hết và chỉ nhận địa chỉ thuộc chính khách đó.

### A3. Bảng giá riêng và giá từng mặt hàng

1. `/app/price-list/new`: tên theo quy ước `HĐNT-<Tên khách>-<Năm>`,
   tick **Bán (Selling)**, tiền tệ `VND`.
2. Với mỗi mặt hàng bán cho khách này, tạo `/app/item-price/new`:
   mã hàng · bảng giá vừa tạo · tick **Bán** · đơn giá · `VND`.
3. Quay lại `Customer`, đặt **Bảng giá bán mặc định** = bảng giá này.

> Mặt hàng có trong hợp đồng nhưng **không có `Item Price`** trong bảng giá của
> khách sẽ làm khách bấm "Đặt hàng" bị chặn với thông báo
> *"Không tìm thấy giá bán cho mặt hàng …"*.

### A4. Hợp đồng nguyên tắc (HĐNT)

Trên cổng, **hợp đồng quyết định mặt hàng nào có sẵn giá và tối đa bao nhiêu**.

Không có hợp đồng thì màn Đặt hàng của khách **không trống**: khách vẫn tìm được
toàn bộ danh mục của Miyano, chỉ là mọi dòng đều mang nhãn *Chờ báo giá* và mỗi
đơn phải đi một vòng báo giá trước khi giao. Có hợp đồng thì hàng thuộc hợp đồng
đứng đầu danh sách, hiện đơn giá đã ký kèm mã hợp đồng và hạn mức còn lại.

`/app/blanket-order/new`:

| Trường | Giá trị |
|---|---|
| Loại | `Selling` |
| Khách hàng | khách vừa tạo |
| Công ty | `Miyano Việt Nam` |
| Từ ngày / Đến ngày | **Đến ngày phải ≥ hôm nay**, nếu không cổng sẽ không thấy hợp đồng |
| Bảng chi tiết | mỗi dòng: mã hàng · số lượng hạn mức cả năm · đơn giá |

**Bấm Submit.** Hợp đồng còn ở trạng thái nháp thì cổng không đọc.

Số lượng đã đặt được cộng dồn vào cột `ordered_qty` của từng dòng hợp đồng; cổng
hiển thị "còn lại" = hạn mức − đã đặt, và **chặn cứng** đơn vượt hạn mức.

### A5. Cấp tài khoản đăng nhập cổng

Dùng màn Desk **Nhập nhân sự bệnh viện** — workspace **Kho khách hàng** → shortcut
cùng tên. Một lần nhập tạo đủ cho cả bệnh viện: tài khoản đăng nhập, khoa phòng
còn thiếu, vai trò và phân quyền.

Chỉ nhân viên Miyano (**System Manager**, **Sales Manager** hoặc **Sales User**)
mở được màn này.

**Bốn bước trên màn hình:**

**Bước 1 — Chọn bệnh viện** ở ô trên đầu màn. Bệnh viện **cố ý không có cột trong
tệp Excel**: một cột "tên bệnh viện" gõ tay là đường để nhập nhầm người của viện
này sang viện khác.

**Bước 2 — Tải bảng mẫu Excel** rồi gửi cho bệnh viện điền. Đúng năm cột:

| Cột | Điền gì |
|---|---|
| **Họ tên** | tên người dùng tài khoản |
| **Email** | email đăng nhập — mỗi người một email, không trùng trong tệp |
| **Khoa** | tên khoa, ví dụ `Huyết học`. Để trống với Quản lý |
| **Mã khoa** | viết tắt không dấu, ví dụ `HUYETHOC`. Để trống với Quản lý |
| **Vai trò** | đúng hai giá trị: `Quản lý` (nhìn toàn viện) hoặc `Nhân viên khoa` (bắt buộc có Khoa) |

**Không có cột mật khẩu, và đừng thêm cột đó.** Mật khẩu do hệ thống sinh ở bước 4.

**Bước 3 — Tải tệp đã điền lên và xem trước.** Bước này **không ghi gì**, nó chỉ
nói từng dòng sẽ ra sao:

| Nhãn | Nghĩa |
|---|---|
| **Sẽ tạo mới** | Dòng hợp lệ, sẽ tạo tài khoản |
| **Đã có — bỏ qua** | Người này đã là thành viên của chính bệnh viện đó |
| **Cần Miyano quyết** | Ví dụ email đã thuộc bệnh viện khác. Không tạo lại, không đổi mật khẩu của họ — bạn tự xét là gõ nhầm hay đúng là một người làm hai nơi. **Cảnh báo không chặn các dòng khác** |
| **Bị từ chối** | Có lỗi phải sửa. **Còn một dòng bị từ chối là không ghi gì cả** — hoặc ghi hết tệp, hoặc không ghi gì |

Bản xem trước cũng nói rõ **những khoa nào sẽ được tạo mới**, và cảnh báo nếu tệp
không có ai làm Quản lý mà bệnh viện cũng chưa có quản lý đang hoạt động — khi đó
sẽ không ai duyệt được yêu cầu của các khoa.

**Bước 4 — Bấm Ghi.** Xong, màn hình hiện **bảng email kèm mật khẩu**.

> ### ⚠️ Mật khẩu chỉ hiện MỘT LẦN
>
> Chép ngay để bàn giao — rời khỏi màn này là không xem lại được. Mật khẩu
> **không nằm trong tệp Excel**, **không gửi qua email**, không ghi vào bất kỳ
> nhật ký nào. Nhắc người nhận đổi mật khẩu ngay lần đăng nhập đầu.
>
> Có nút **Chép danh sách** để lấy cả bảng một lần.

Ba điều nữa cần biết:

- **Tài khoản đã tồn tại từ trước** (người đó đã có tài khoản nhưng chưa thuộc
  bệnh viện nào) chỉ được **gắn vào bệnh viện này**, hệ thống **không đặt lại mật
  khẩu** của họ. Bảng kết quả ghi rõ dòng nào rơi vào trường hợp đó.
- **Email nội bộ của Miyano bị từ chối.** Gắn một tài khoản nội bộ vào một khách
  hàng sẽ làm người đó mất tầm nhìn ở khắp hệ thống — hỏng theo kiểu rất khó lần
  ra nguyên nhân, nên chặn ngay ở bước xem trước.
- **Tệp nhân sự bị xoá khỏi hệ thống sau khi ghi xong.** Nó mang họ tên và email
  của nhân viên bệnh viện, không có lý do gì để nằm lại trên đĩa. Tệp phải ở chế
  độ riêng tư; tải lên bằng đúng nút trên màn này thì đã đúng sẵn.

**Cấp lẻ một tài khoản** (không qua bảng nhân sự) vẫn làm được bằng chức năng cấp
tài khoản cổng đang có, nhưng tài khoản sinh ra ở trạng thái **chưa hoạt động,
chưa gán khoa** và phải mở `Portal Member` gán khoa rồi bật thủ công. Chi tiết ở
tài liệu *phân quyền theo khoa phòng*, mục 2 bước 4.

**Tài khoản được cấp gồm ba mảnh khớp nhau**, hệ thống tạo đủ và đúng thứ tự:

1. `User` — kiểu **Website User**, có role **Customer**.
2. `Contact` — có `user = <email>` và một dòng liên kết tới `Customer`.
   **Đây là thứ cổng dùng để biết người đăng nhập thuộc khách hàng nào**, và cũng
   là thứ lọc danh sách đơn hàng / giao hàng / hoá đơn của tài khoản.
3. `User Permission` — `allow = Customer`, `for_value = <khách hàng>`. Đây là
   lớp chặn **bổ sung** của framework (áp cho ô tìm kiếm liên kết và các truy vấn
   phía desk). Nó không phải thứ quyết định khách thấy gì trên cổng — thứ đó là
   `Contact` ở trên — nhưng vẫn phải có, đừng bỏ.

### A6. Kiểm tra nhanh (làm trước khi bàn giao cho khách)

1. Mở cửa sổ ẩn danh → <http://192.168.61.129:8003/portal/login> → đăng nhập bằng
   tài khoản vừa cấp.
2. Màn **Tổng quan** phải hiện đúng tên đơn vị.
3. Màn **Đặt hàng** phải liệt kê các mặt hàng của hợp đồng **ở đầu danh sách**,
   kèm đơn giá hợp đồng và hạn mức còn lại.
4. Màn **Hồ sơ đơn vị** phải hiện đúng địa chỉ giao hàng.

### A7. Thiếu thứ gì thì lỗi ra sao

| Hiện tượng trên cổng | Nguyên nhân |
|---|---|
| *"Tài khoản chưa gắn với khách hàng nào."* | Thiếu `Contact`, hoặc `Contact` không có dòng liên kết tới `Customer`, hoặc `Contact.user` để trống |
| Màn Đặt hàng chỉ hiện *Chờ báo giá*, không mặt hàng nào có giá hợp đồng | Chưa có `Blanket Order`, hoặc còn nháp, hoặc `Đến ngày` đã qua |
| *"Không tìm thấy giá bán cho mặt hàng …"* | Thiếu `Item Price` trong bảng giá mặc định của khách |
| Màn Đặt hàng cảnh báo *"Vượt hạn mức HĐ — còn …"* | Số lượng đặt > hạn mức còn lại của dòng hợp đồng. Lúc soạn giỏ đây **chỉ là cảnh báo**; nhân viên khoa vẫn gửi duyệt được và người duyệt sẽ hạ số thật. Nhưng **lúc thật sự sinh đơn** — quản lý bấm Đặt hàng, hoặc quản lý duyệt một yêu cầu — thì hạn mức là **chốt cứng**, hệ thống báo còn bao nhiêu và không tạo đơn |
| Đăng nhập được nhưng danh sách đơn hàng trống dù đã có đơn | Đơn không thuộc đúng `Customer` mà `Contact` của tài khoản trỏ tới — danh sách được lọc theo `Contact`, không theo `User Permission` |

---

## B. Mở kho khách hàng

"Kho khách hàng" là **sổ kho riêng của bệnh viện** chạy trên cổng: bệnh viện tự
nhập, tự xuất, tự làm báo cáo nhập–xuất–tồn cho hàng đã mua của Miyano và cả hàng
mua ngoài.

> **Sổ này hoàn toàn độc lập với kho của ERPNext.** Nó không tạo `Warehouse`,
> không ghi `Stock Ledger Entry`, không sinh bút toán nào lên sổ sách của Miyano.
> Đừng tìm tồn kho của khách trong báo cáo Stock Balance của ERPNext — không có ở
> đó.

### B1. Ai được mở kho

| Role | Kho & danh mục | Phiếu nhập / phiếu xuất |
|---|---|---|
| System Manager | tạo, sửa, xoá | tạo, ghi sổ, huỷ, xoá |
| Sales Manager | tạo, sửa | tạo, ghi sổ, huỷ |
| Sales User | chỉ đọc | chỉ đọc, in |

**Khách hàng không tự mở kho được.** Đây là việc của nhân viên Miyano.

### B2. Tạo kho

`/app/customer-warehouse/new` — hoặc vào workspace **Kho khách hàng** trên desk,
mục *Danh mục* → **Kho Khách Hàng**.

| Trường | Ý nghĩa |
|---|---|
| **Khách hàng** | mỗi khách **một kho**. Cổng tự suy ra kho từ tài khoản đăng nhập. |
| **Tên kho** | ví dụ "Kho Khoa Dược" |
| **Mã kho** | 2–4 ký tự, **in vào số phiếu**: mã `MD` → `PN-MD-2026-00001`. Đặt rồi thì đừng đổi, vì số phiếu cũ vẫn mang mã cũ. |
| **Đang hoạt động** | công tắc bật/tắt tính năng kho cho khách này (mục B5) |
| Thủ kho | tên người phụ trách, in lên phiếu |
| Địa chỉ kho | in lên phiếu |
| **Ngày bắt đầu quản lý** | **không sửa được về sau một cách an toàn**: mọi phiếu có ngày trước mốc này đều bị chặn. Thường đặt là ngày kiểm kê bàn giao. |
| Tên đơn vị in / Bộ phận | hiển thị ở đầu phiếu in |
| Mẫu phiếu nhập / xuất | mục B4 |

### B3. Danh mục vật tư của kho

Mỗi dòng trong `Customer Warehouse Item` là một vật tư kho của khách. Có **hai
loại mã**, khác nhau ở chỗ có nối về hàng của Miyano hay không:

| Loại | `Mã hàng Miyano` (`item_code`) | Khi nào dùng |
|---|---|---|
| Mã Miyano | trỏ tới `Item` thật | hàng khách mua của Miyano — nhờ trường này, hàng giao đến mới tự chảy vào kho khách (mục C7) |
| **Mã riêng của bệnh viện** | **để trống** | hàng bệnh viện tự mua ngoài. **Không tạo `Item` trong ERPNext** cho những mã này. |

Không cần khai trước toàn bộ danh mục:

- Khách tự tạo hàng loạt bằng **file nhập tồn đầu kỳ** (mục C6).
- Hàng Miyano giao đến mà chưa có trong danh mục thì hệ thống **tự tạo dòng danh
  mục**, lấy ĐVT theo đúng dòng phiếu giao hàng.

**ĐVT chỉ được chốt một lần** — lần đầu vật tư xuất hiện. Nếu về sau có phiếu
giao hàng cùng mã nhưng ĐVT khác, hệ thống **không tự quy đổi**: nó vẫn tạo phiếu
nhập nháp, đồng thời ghi cảnh báo vào dòng phiếu và vào diễn giải phiếu để thủ
kho tự quyết. Gặp cảnh báo này thì xử lý bằng tay, đừng ghi sổ cho xong.

### B4. Mẫu phiếu in

Có sẵn 4 mẫu (`Print Format`): phiếu nhập / phiếu xuất, mỗi loại 2 kiểu —
**TT107** (mặc định) và **TT200**. Chọn trên form kho ở hai trường *Mẫu phiếu
nhập* / *Mẫu phiếu xuất*. Để trống thì dùng TT107.

Bệnh viện dùng mẫu riêng thì tạo thêm `Print Format` với `doc_type` đúng là
`Customer Stock Receipt` / `Customer Stock Issue` rồi chọn vào đây — mẫu gắn sai
loại chứng từ sẽ bị bỏ qua (rơi về TT107) chứ không làm hỏng nút in.

### B5. Tạm ngừng tính năng kho cho một khách

Bỏ tick **Đang hoạt động**. Kể từ đó:

- Khách vào mục Kho trên cổng sẽ nhận thông báo chưa được mở kho;
- Hàng Miyano giao đến **không** sinh phiếu nhập nháp nữa;
- Dữ liệu cũ vẫn còn nguyên, bật lại là dùng tiếp.

Đây là cách đúng để ngừng dịch vụ kho cho một khách vẫn đang mua hàng bình thường.
**Không xoá kho** — xoá là mất sổ.

> ### ⚠️ Tuyệt đối không cấp quyền doctype cho role `Customer`
>
> Role `Customer` **cố ý không có bất kỳ DocPerm nào** trên 8 doctype kho. Đó là
> chốt cách ly dữ liệu giữa các khách hàng: cổng chỉ chạm được vào dữ liệu kho
> qua nhóm API `miyano_portal.api.kho.*`, vốn tự suy kho từ phiên đăng nhập.
>
> Cấp lại quyền đọc (kể cả qua Role Permission Manager, kể cả role `All`) sẽ mở
> ngay đường cho một khách đọc dữ liệu kho của khách khác qua REST/danh sách —
> các hook phân quyền **không** bịt được lỗ đó.
>
> Hệ quả cần biết: tài khoản khách **không in được bằng `/printview` của desk**.
> Nút in trên cổng đi đường riêng (`kho_phieu_pdf`) và vẫn hoạt động bình thường.

### B6. Nhân viên Miyano xem kho của khách ở đâu

Workspace desk **Kho khách hàng** (tìm trong danh sách workspace bên trái của
`/app`) gồm:

- **Báo cáo**: *Tồn kho khách hàng* · *Nhập-Xuất-Tồn khách hàng* ·
  *Cảnh báo hạn dùng khách hàng* — xem được nhiều khách cùng lúc, lọc theo khách.
- **Danh mục**: 6 doctype kho (Kho Khách Hàng, Vật Tư Kho Khách, Phiếu Nhập Kho,
  Phiếu Xuất Kho, Sổ Kho Khách, Tồn Theo Lô).

---

## C. Thao tác trên cổng (dành cho khách hàng)

### C1. Đăng nhập

<http://192.168.61.129:8003/portal/login> — email và mật khẩu do Miyano cấp.
Sau khi đăng nhập, thanh điều hướng gồm **8 mục**: **Tổng quan · Đặt hàng · Yêu
cầu của tôi · Duyệt · Kho của tôi · Hoá đơn & công nợ · Thông báo · Hồ sơ đơn
vị**. Nhân viên khoa thấy **7** — họ không có mục **Duyệt**.

### C2. Đặt hàng

Một màn, hai bước.

**Bước 1 · Chọn hàng**

1. Vào **Đặt hàng** → gõ mã hoặc tên mặt hàng vào ô tìm.
2. Danh sách hiện 10 dòng mỗi trang, **hàng thuộc hợp đồng của đơn vị đứng
   trước**. Mỗi dòng có tình trạng hàng (**Còn hàng** / **Liên hệ**) và tầng giá
   (**Giá HĐ** kèm số tiền và mã hợp đồng, hoặc **Chờ báo giá**).
3. Nhập số lượng → **+ Giỏ**.
4. Hàng Miyano chưa có trong hệ thống: bấm **“+ Thêm dòng — hàng chưa có trong hệ
   thống”** rồi tự gõ tên hàng, ĐVT, số lượng, ghi chú.

**Bước 2 · Giỏ hàng**

5. Bấm **2 · Giỏ hàng**. Một giỏ duy nhất, mọi mặt hàng chung một bảng. Điền:
   - **Lý do yêu cầu** (bắt buộc, người duyệt của đơn vị sẽ đọc);
   - **Ngày giao mong muốn**;
   - **Địa chỉ giao hàng**;
   - **Ghi chú / Yêu cầu** (ví dụ: hàng cần giữ lạnh 2–8 °C).
6. Bấm nút cuối màn: **Gửi duyệt** (nhân viên khoa) hoặc **Đặt hàng** (quản lý
   đơn vị — đơn sang Miyano ngay). Có **Lưu nháp** nếu muốn soạn dở.

**Giỏ có hàng chờ báo giá thì cả đơn chờ Miyano báo giá rồi mới giao**, kể cả phần
hàng hợp đồng vốn giao được ngay — màn hình báo rõ điều này ngay trên nút gửi. Cần
hàng hợp đồng gấp thì đặt riêng một yêu cầu chỉ gồm hàng có giá hợp đồng.

Số lượng vượt hạn mức hợp đồng chỉ là **cảnh báo** lúc soạn giỏ, nhưng **chặn cứng**
lúc đơn thật sự sinh ra, kèm thông báo còn bao nhiêu.

### C3. Theo dõi

**Yêu cầu của tôi** — một danh sách cho cả vòng đời, lọc bằng dải chip:
`Nháp · Chờ duyệt · Đã duyệt · Chờ quý vị đồng ý · Đã giao · Từ chối · Đã huỷ`.

> Yêu cầu **đang chờ Miyano ra giá** nằm ở **Đã duyệt**. **Chờ quý vị đồng ý** là
> bước sau đó: **giá đã về, đang chờ đơn vị trả lời.**
>
> *(Giai đoạn này trước đây tên "Chờ báo giá" — đọc như đang chờ Miyano, ngược
> chiều việc. Đổi tên 26/08/2026; link cũ mang tên cũ vẫn mở đúng chip.)*

Bấm vào một dòng để xem tiến trình:
`Chờ xác nhận → Đang xử lý → Đang giao → Hoàn thành`

Trong màn chi tiết đơn:

- Danh sách các lần giao hàng và hoá đơn đã phát sinh của đơn đó.
- **PDF** xác nhận đơn hàng / hoá đơn (mẫu song ngữ), và **phiếu giao hàng** —
  phiếu giao là tờ *Phiếu xuất kho kiêm biên bản bàn giao* hai bên ký, mở ngay
  trong trình duyệt. Miyano đã đính bản quét có chữ ký thì cổng phát đúng bản đó.
- **Yêu cầu huỷ** — chỉ hiện khi đơn còn **Chờ xác nhận**. Bấm vào và nhập lý do;
  yêu cầu được ghi lại và chuyển tới nhân viên Miyano, đơn **không tự huỷ**.
- **Đặt lại đơn này** — dựng sẵn một yêu cầu **Nháp** mang đúng các mặt hàng của
  đơn cũ rồi mở màn Đặt hàng để sửa tiếp.

### C4. Hoá đơn & công nợ

Liệt kê hoá đơn: ngày, hạn thanh toán, tổng tiền, **còn phải trả**, trạng thái
(*Chưa TT · TT một phần · Đã TT · Quá hạn*). Tổng công nợ hiển thị ở màn Tổng quan.

### C5. Kho của tôi

**Kho của tôi** hiện tồn hiện tại, mỗi vật tư một dòng: mã · tên · ĐVT · SL tồn ·
giá trị · số lô · hạn gần nhất. Bấm vào một dòng để **bung xuống từng lô** (số
lô, hạn dùng, số lượng, đơn giá). Lô không có hạn dùng hiện là **"Không thời hạn"**.

Năm nút ở đầu màn hình: **Phiếu nhập · Phiếu xuất · Nhập tồn đầu kỳ · Danh mục
vật tư · Báo cáo**.

### C5b. Danh mục vật tư

**Kho của tôi › Danh mục vật tư** liệt kê mọi vật tư của kho: mã · tên · ĐVT ·
mã hàng Miyano · quy cách · nhóm · đang dùng. Ô tìm kiếm lọc theo mã/tên; tick
**Hiện cả vật tư đã tắt** để xem cả vật tư đã ngừng dùng.

- **+ Thêm vật tư** — mã trùng một mặt hàng của Miyano thì hệ thống tự nối
  (cột *Mã hàng Miyano* có giá trị); mã lạ thì thành mã riêng của bệnh viện.
- **Sửa** — mở lại đúng modal của "+ Thêm vật tư". Tên, quy cách, nhóm, ghi chú
  sửa lúc nào cũng được; tick **Đang dùng** cũng nằm trong màn này (bỏ tick để
  ngừng dùng — không tắt được vật tư còn tồn, phải xuất hết trước). **Mã vật
  tư và ĐVT bị khoá 🔒 khi vật tư đã có phát sinh trong sổ**: số liệu cũ đã
  tính theo giá trị hiện tại và hệ thống không quy đổi.
- **⬇ Xuất danh mục / ⬆ Nhập danh mục** — tệp xuất ra sửa rồi nạp lại được. Mã
  đã có thì **cập nhật**, mã chưa có thì **tạo mới**; bản xem trước báo rõ
  từng dòng là *Tạo mới* hay *Cập nhật* trước khi xác nhận, và **hoặc ghi hết
  tệp hoặc không ghi gì** nếu còn dòng lỗi. Hai điều cần nhớ khi điền tệp:
  - **Mã trùng nhau trong cùng một tệp là lỗi**, chặn nạp cả tệp — bản xem
    trước nêu rõ trùng với dòng nào, không tự gộp âm thầm.
  - Cột *Mã hàng Miyano* trong tệp chỉ để đối chiếu, nạp vào sẽ bị bỏ qua (hệ
    thống tự suy từ mã) — cột này cũng không xuất hiện lại ở bảng xem trước.
  - Cột **Đang dùng** để trống (kể cả ô chỉ có khoảng trắng) được hiểu là
    **đang dùng**; phải ghi rõ 0 / "không" / "tắt" mới thành ngừng dùng.

### C6. Nhập tồn đầu kỳ (làm một lần, khi mới mở kho)

1. **Kho của tôi › Nhập tồn đầu kỳ › Bước 1 · Tải tệp mẫu › ⬇ Tải mẫu Excel** —
   file `.xlsx` với đúng các cột: `Mã vật tư · Tên vật tư · ĐVT · Số lô ·
   Hạn sử dụng · Số lượng · Đơn giá · Quy cách · Nhóm`.
2. Điền dữ liệu kiểm kê thực tế vào file (giữ nguyên thứ tự cột).
3. **Bước 2 · Chọn tệp đã điền và xem trước** → hệ thống đọc và hiện
   **bản xem trước, chưa ghi gì**:
   - bao nhiêu dòng khớp mã Miyano,
   - bao nhiêu dòng là mã riêng sẽ được tạo mới,
   - bao nhiêu dòng trùng vật tư đã có,
   - danh sách dòng lỗi kèm **số dòng và lý do**.
4. Còn dòng lỗi thì sửa file rồi tải lại (bản xem trước chỉ ra **số dòng** trong
   file Excel). Bước ghi chỉ chạy khi toàn bộ file hợp lệ: **hoặc ghi hết, hoặc
   không ghi gì**, không có chuyện ghi được nửa file.
5. Kết quả: các vật tư còn thiếu được tạo, và **một phiếu nhập loại "Tồn đầu kỳ"**
   được ghi sổ.

Quy ước điền file:

- **Bắt buộc có giá trị** ở mọi dòng: `Mã vật tư`, `Tên vật tư`, `ĐVT`,
  `Số lượng`, `Đơn giá`.
- **Số lô** để trống được — dòng đó vào lô `KHONG-LO`.
- **Hạn sử dụng** nhận `dd/mm/yyyy` hoặc `yyyy-mm-dd`; để trống nghĩa là lô không
  có hạn.
- Thứ tự cột có thể đảo và hoa/thường không quan trọng — hệ thống nhận cột theo
  tên tiêu đề. Nhưng file **xuất ra từ báo cáo nạp lại được**, nên giữ nguyên thứ
  tự gốc là an toàn nhất.

### C7. Hàng Miyano giao đến — phiếu nhập tự sinh

Khi Miyano ghi sổ phiếu giao hàng, hệ thống **tự tạo một phiếu nhập ở trạng thái
NHÁP** trong kho của bệnh viện (loại *Từ đơn hàng Miyano*, có ghi số phiếu giao
hàng và số đơn).

**Phiếu là nháp chứ không tự ghi sổ, và đó là chủ ý**: thủ kho phải đối chiếu hàng
thực nhận trước. Giao thiếu, vỡ, sai lô mà cứ tự cộng vào tồn thì sổ sai ngay từ
ngày đầu.

Thao tác của thủ kho: **Kho của tôi › Phiếu nhập** → mở phiếu **Nháp** →

- sửa số lượng cho khớp thực nhận (sửa được mọi dòng khi còn nháp);
- điền số lô / hạn dùng nếu hàng có lô mà phiếu chưa ghi;
- đọc kỹ nếu phiếu có **dòng cảnh báo lệch ĐVT** (mục B3);
- bấm **Ghi sổ**. Từ lúc này tồn mới tăng, và phiếu **không sửa được nữa**.

Miyano huỷ phiếu giao hàng thì: phiếu nhập còn nháp sẽ bị huỷ theo; phiếu đã ghi
sổ sẽ được **đảo** bằng một phiếu ngược dấu (mục C10).

### C8. Nhập hàng mua ngoài (phiếu nhập tay)

**Kho của tôi › Phiếu nhập › + Tạo phiếu nhập** → loại nhập **"Nhập khác"** →
chọn vật tư, nhập số lô, hạn dùng, số lượng, đơn giá → **Lưu nháp** rồi **Ghi sổ**.

Ngày phiếu không được trước *Ngày bắt đầu quản lý* của kho.

### C8b. Nhập bảng dòng từ Excel

Trong màn lập phiếu nhập hoặc phiếu xuất: **Tải file mẫu** → điền → **⬆ Nhập từ
Excel**. Các dòng đọc được **nối vào cuối bảng**, không xoá dòng đã gõ tay.

| Màu dòng | Nghĩa | Việc cần làm |
|---|---|---|
| bình thường | mã đã có trong kho | không phải làm gì |
| nền vàng | mã chưa có trong kho | bấm **Tạo vật tư mới** — điền sẵn từ chính dòng đó |
| nền đỏ | sai dữ liệu | sửa tại ô; lý do và số dòng trong tệp hiện ngay dưới |

Dòng đỏ: sửa các ô ngay trên bảng rồi **chọn vật tư trong ô** là **Lưu nháp được**.
**Nền đỏ và danh sách lý do vẫn ở lại** cho tới khi bạn sửa tệp và nạp lại — đó là
chủ ý: hệ thống chỉ kiểm lại được một phần lỗi trên màn hình (số lượng, số lô, vật
tư), còn những lỗi như **hạn dùng sai định dạng** thì không, nên nó giữ nguyên lý
do đọc được từ tệp để bạn còn đối chiếu. Đặc biệt lưu ý dòng báo *"Hạn sử dụng
không hợp lệ"*: nếu lưu và ghi sổ luôn, lô đó vào sổ **không có hạn dùng** và sẽ
không bao giờ được cảnh báo hết hạn ở các phiếu xuất sau; hãy điền lại hạn dùng
trên bảng trước khi ghi sổ.

Còn dòng đỏ **chưa chọn được vật tư** thì **Lưu nháp bị chặn** — hệ thống báo còn
bao nhiêu dòng khi bấm. Dòng nền vàng và dòng gõ tay còn trống cũng bị chặn, báo
theo từng dòng ("Dòng 3: chưa chọn vật tư."). Các lỗi còn lại (số lượng phải lớn
hơn 0, chưa nhập số lô) cũng báo theo từng dòng khi bấm **Lưu nháp**.

Bấm **Tạo vật tư mới** một lần là mọi dòng khác đọc được cùng mã cũng tự khớp
theo, không phải lặp lại cho từng dòng.

**⬇ Xuất Excel** chỉ hiện khi phiếu đã lưu (đã có số phiếu) — tệp xuất ra nạp
lại được.

Riêng phiếu xuất: tệp **không có** cột Đơn giá và Hạn dùng (hệ thống luôn lấy
theo lô đã chọn khi ghi sổ), và vật tư vừa tạo nhanh từ dòng import sẽ hiện
*"Vật tư này chưa còn tồn lô nào"* — lưu nháp được nhưng phải nhập kho trước
khi ghi sổ phiếu xuất đó.

Cột **Số lô** của tệp được giữ nguyên như bạn điền, hệ thống không tự đổi sang lô
khác. Nếu số lô đó không còn tồn trong kho, dòng hiện cảnh báo *"Lô … không còn
tồn trong kho"* và ô chọn lô có thêm mục *"… · không còn tồn"*: vẫn **lưu nháp
được**, nhưng **ghi sổ sẽ bị chặn** cho tới khi bạn chọn lô khác hoặc nhập kho lô
đó. Để trống ô Số lô thì hệ thống mới tự chọn lô sắp hết hạn nhất (FEFO).

### C9. Xuất kho

**Kho của tôi › Phiếu xuất › + Tạo phiếu xuất**:

1. Chọn **loại xuất**: *Xuất sử dụng · Xuất huỷ - hết hạn · Xuất trả lại ·
   Điều chỉnh kiểm kê*.
2. Điền **Nơi nhận** và **Người nhận**.
3. Chọn vật tư và số lượng → hệ thống **gợi ý lô theo FEFO**: lô hạn dùng gần
   nhất trước, lô không có hạn xếp cuối, và tự phân bổ số lượng qua các lô.
4. Sửa lại phân bổ nếu thực tế lấy khác.
5. **Ghi sổ**.

Ba điều cần biết:

- **Xuất quá tồn của lô bị chặn cứng**, kèm thông báo lô đó còn bao nhiêu.
- **Lô đã quá hạn không bị cấm xuất** (thực tế có nghiệp vụ xuất huỷ), nhưng phải
  tick **Xác nhận xuất lô hết hạn** trên dòng đó.
- **Đơn giá xuất không nhập tay** — hệ thống luôn lấy đơn giá hiện hành của lô,
  nên giá trị xuất trên báo cáo luôn khớp sổ.

### C10. Huỷ phiếu đã ghi sổ

Phiếu đã ghi sổ **không sửa được**, chỉ **huỷ**. Khi huỷ:

- Hệ thống **không xoá dòng sổ nào**. Nó sinh một **phiếu đảo** cùng loại, số
  lượng ngược dấu, có trỏ về phiếu gốc; phiếu gốc chuyển trạng thái *Đã huỷ*.
- Vì vậy lịch sử luôn đọc lại được: ai nhập gì, huỷ lúc nào, đảo bằng phiếu nào.
- **Phiếu đảo không huỷ được** (huỷ phiếu đảo là làm hỏng cặp bù trừ).

Huỷ phiếu **nhập** sẽ bị **chặn** nếu hàng của lô đó đã được xuất đi mất — đảo lại
sẽ làm tồn âm. Thông báo chỉ rõ lô nào còn bao nhiêu; muốn huỷ thì **huỷ phiếu
xuất tương ứng trước**.

### C11. Báo cáo

**Kho của tôi › Báo cáo** — ba thẻ **Nhập - Xuất - Tồn · Thẻ kho · Cảnh báo**,
mỗi thẻ đều có nút **Xuất Excel** với đúng bộ cột đang xem:

| Thẻ | Nội dung |
|---|---|
| **Nhập - Xuất - Tồn** | theo khoảng ngày, mỗi vật tư một dòng, 8 cột (tồn đầu SL+TT, nhập SL+TT, xuất SL+TT, tồn cuối SL+TT). Bấm vào một vật tư để **bung xuống mức lô**. |
| **Thẻ kho** | một vật tư, liệt kê từng chứng từ theo thời gian kèm cột tồn luỹ kế |
| **Cảnh báo** | lô đã hết hạn còn tồn + lô sắp hết hạn trong N ngày tới (mặc định 90, sửa được) |

### C12. In phiếu

Mở phiếu nhập/phiếu xuất → bấm **In phiếu** → tải về PDF theo mẫu đã cấu hình cho
kho (TT107 hoặc TT200).

Nút **In phiếu** chỉ hiện khi phiếu **đã ghi sổ** hoặc **đã huỷ** — phiếu còn nháp
chưa phải chứng từ nên chỉ có **Lưu nháp** và **Ghi sổ**. Phiếu đảo chỉ có nút In,
không có nút Huỷ (mục C10).

---

## D. Dữ liệu demo đã dựng sẵn

Toàn bộ dữ liệu dưới đây được dựng bằng một lệnh, chạy **đúng các bước nghiệp vụ
thật** (đơn hàng đặt qua API của cổng dưới phiên đăng nhập của khách, phiếu kho
ghi sổ qua đúng endpoint mà nút bấm trên cổng gọi):

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct
bench --site erptest.local execute miyano_portal.setup.demo_kho_flow.chay_tat_ca
```

Script **idempotent**: chạy lại bao nhiêu lần cũng không đẻ thêm chứng từ, và
chạy tiếp được từ chỗ dở nếu lần trước bị đứt. Mã nguồn:
`miyano_portal/setup/demo_kho_flow.py`.

### Tài khoản demo

| | |
|---|---|
| Khách hàng | **Bệnh viện Đa khoa Minh Đức (DEMO)** |
| Đăng nhập cổng | `bvminhduc@demo.miyano` / `Portal@123` |
| Hợp đồng nguyên tắc | `MFG-BLR-2026-00020` (500 mỗi mặt hàng, hiệu lực 12 tháng) |
| Kho | `KKH-00007` — "Kho Khoa Dược", mã **MD**, thủ kho Trần Thị Bích Ngọc |
| Bảng giá | `HĐNT-BVMinhDuc-2026` |

### Danh mục vật tư trong kho

| Mã | Tên | ĐVT | Mã hàng Miyano |
|---|---|---|---|
| MYN-GLOVE-M | Găng tay khám nitrile size M – hộp 100 cái | Hộp | có |
| MYN-SYR-10 | Bơm tiêm 10ml G21 – hộp 100 cái | Hộp | có |
| MYN-ALT | Hoá chất sinh hoá ALT (GPT) – hộp 4×50ml | Hộp | có |
| **MD-BONG-01** | Bông y tế cuộn 500g (bệnh viện tự mua) | Cuộn | **không — mã riêng** |

### Chứng từ đã sinh

| Chứng từ | Số | Trạng thái / ý nghĩa demo |
|---|---|---|
| Phiếu nhập tồn đầu kỳ | `PN-MD-2026-00001` | Đã ghi sổ — 8 lô trải 3 mốc hạn dùng (đã hết hạn / sắp hết hạn / còn hạn dài) |
| Đơn hàng hoàn chỉnh | `SAL-ORD-2026-00011` | đã xác nhận → giao đủ → xuất hoá đơn → thu 60% |
| — phiếu giao hàng | `MAT-DN-2026-00007` | |
| — phiếu nhập kho khách | `PN-MD-2026-00002` | **Đã ghi sổ** (thủ kho đã đối chiếu) |
| — hoá đơn | `ACC-SINV-2026-00005` | TT một phần, còn nợ 1.288.000 ₫ |
| Đơn giao thiếu | `SAL-ORD-2026-00012` | đặt 6 ALT + 10 găng, Miyano mới giao 4 ALT |
| — phiếu giao hàng | `MAT-DN-2026-00008` | |
| — phiếu nhập kho khách | `PN-MD-2026-00003` | **Còn NHÁP** — để demo bước đối chiếu trước khi ghi sổ |
| Đơn chờ xác nhận | `SAL-ORD-2026-00013` | để demo màn theo dõi và nút **Yêu cầu huỷ** |
| Phiếu xuất sử dụng | `PX-MD-2026-00001` | 12 Hộp bơm tiêm cho Khoa Xét nghiệm, lô do FEFO chọn |
| Phiếu xuất huỷ | `PX-MD-2026-00002` | 2 Hộp ALT **đã quá hạn**, có tick xác nhận |
| Phiếu nhập tay + phiếu đảo | `PN-MD-2026-00004` (Đã huỷ) → `PN-MD-2026-00005` (Phiếu đảo) | để demo cơ chế huỷ ở mục C10 |

### Tồn hiện tại (thời điểm dựng dữ liệu)

| Vật tư | SL tồn | Giá trị | Số lô |
|---|---|---|---|
| Găng tay khám nitrile size M | 218 Hộp | 15.964.000 ₫ | 4 |
| Bơm tiêm 10ml G21 | 133 Hộp | 9.052.000 ₫ | 3 |
| Hoá chất ALT (GPT) | 13 Hộp | 12.340.000 ₫ | 2 |
| Bông y tế cuộn 500g | 50 Cuộn | 2.250.000 ₫ | 1 |

Báo cáo **Cảnh báo hạn dùng** (90 ngày) trả 7 dòng, trong đó 2 lô đã quá hạn còn tồn.

### Dựng thêm một khách hàng demo khác

Sửa khối hằng số ở đầu `demo_kho_flow.py` (`CUSTOMER`, `PORTAL_EMAIL`,
`PRICE_LIST`, `MA_KHO`, `PO_DON_*`) rồi chạy lại — **phải đổi cả `PO_DON_*`**, vì
số PO chính là khoá chống trùng của từng đơn hàng.

---

## E. Sự cố thường gặp

| Thông báo | Nguyên nhân | Xử lý |
|---|---|---|
| *"Tài khoản chưa gắn với khách hàng nào."* | `Contact` thiếu, hoặc thiếu liên kết tới `Customer` | Cấp lại tài khoản đó bằng màn **Nhập nhân sự bệnh viện** (mục A5) |
| *"Đơn vị của bạn chưa được mở kho trên cổng…"* | Chưa có `Customer Warehouse`, hoặc kho đã bỏ tick **Đang hoạt động** | Mục B2 / B5 |
| *"Ngày phiếu … không được trước Ngày bắt đầu quản lý của kho …"* | Ngày phiếu quá sớm | Sửa ngày phiếu, hoặc cân nhắc lại mốc *Ngày bắt đầu quản lý* |
| *"Lô … chỉ còn n …"* khi ghi sổ phiếu xuất | Xuất quá tồn của lô | Giảm số lượng hoặc chọn lô khác |
| *"Không thể huỷ phiếu: lô … chỉ còn …"* | Hàng của lô đã xuất đi rồi | Huỷ phiếu xuất tương ứng trước |
| *"Không thể tạo phiếu đảo bằng tay."* | Có người chọn loại **"Phiếu đảo"** trên form | Phiếu đảo chỉ do hệ thống sinh khi huỷ phiếu — chọn loại khác |
| *"Phiếu đã được ghi sổ hoặc đã huỷ, không thể sửa."* | Sửa phiếu đã ghi sổ | Huỷ rồi lập phiếu mới (mục C10) |
| Hàng Miyano đã giao nhưng kho khách **không có phiếu nhập nháp** | Kho chưa mở hoặc đã tắt **Đang hoạt động** — đây là trạng thái bình thường, hệ thống cố ý không báo lỗi | Mở/bật kho rồi lập phiếu nhập tay cho lần giao đó |
| Phiếu nhập nháp có **cảnh báo lệch ĐVT** | Cùng một mã hàng nhưng ĐVT của phiếu giao hàng khác ĐVT đã chốt trong danh mục kho | Xử lý bằng tay: quy đổi rồi sửa số lượng trên phiếu nháp trước khi ghi sổ |
| Khách bấm in trên **desk** báo lỗi quyền | Tài khoản khách không dùng được `/printview` (đúng thiết kế) | Dùng nút **In phiếu** trên cổng |

---

## F. Hạn chế đã biết

1. **Lô không có hạn dùng bị xếp vào "Sắp hết hạn".** Hàng nhập từ phiếu giao
   hàng của Miyano hiện không mang số lô (mặt hàng chưa bật quản lý lô ở ERPNext)
   nên rơi vào lô `KHONG-LO` và **không có hạn dùng**. Báo cáo *Cảnh báo hạn
   dùng* — **cả trên cổng lẫn báo cáo desk của nhân viên Miyano** — đang liệt kê
   các lô này với hạn dùng = ngày hôm nay, trạng thái *Sắp hết hạn*, trong khi
   đúng ra chúng không nên xuất hiện. Màn **Kho của tôi** thì hiển thị đúng
   ("Không thời hạn"). Chưa sửa; cần quyết định của chủ sản phẩm (loại hẳn khỏi
   báo cáo, hay tách thành một nhóm "không có hạn dùng").

2. **Một khách chỉ có một kho.** Cổng suy kho từ tài khoản đăng nhập và lấy kho
   đang hoạt động đầu tiên. Bệnh viện cần nhiều kho con (Khoa Dược, Khoa Xét
   nghiệm…) thì hiện chưa đáp ứng được.

3. **Chưa có mẫu phiếu nhập/xuất riêng của từng bệnh viện.** Đang dùng TT107
   (mặc định) và TT200. Bệnh viện nào có biểu mẫu riêng thì phải tạo thêm
   `Print Format` (mục B4).

4. **Ô tìm kiếm liên kết trên desk chưa được siết cho tài khoản Website User.**
   Vấn đề có sẵn từ trước phần kho, ảnh hưởng tới `Sales Order` / `Delivery Note`
   / `Sales Invoice`, đã ghi nhận và chờ xử lý riêng. Không liên quan tới các
   doctype kho.
