# Bản đồ chức năng cổng khách hàng

> **Tài liệu SỐNG.** Bất kỳ task nào thêm/bỏ một màn hoặc một mục menu **phải sửa file này trong cùng commit**. Một màn không có dòng ở đây là một màn không ai biết nó tồn tại để làm gì.

Kiểm kê ngày 21/08/2026, sau khi chủ đầu tư chỉ ra: *"anh thấy vẫn còn mục đặt hàng xong lại còn lập phiếu đề xuất, hệ thống chúng ta đang rất không hợp lý"*.

---

> **Cập nhật 21/08/2026 — Task 10 ĐÃ THI CÔNG.** Ba cửa `#2 Đặt hàng`,
> `#3 Giỏ hàng`, `#5 Lập phiếu đề xuất` đã gộp thành **một** mục `Đặt hàng`
> (`/dat-hang`). Nav còn **9 mục** (quản lý: 10). Task 11 (gộp `#4 Đơn hàng
> của tôi` + `#6 Đề xuất mua` thành `Yêu cầu của tôi`) chưa thi công — khi
> nó xong, con số cuối cùng ở mục 3 mới đạt.
>
> Kiểm kê ở mục 1 dưới đây GIỮ NGUYÊN làm bản gốc "trước khi gộp": nó là
> bằng chứng của cái đã sai, và một tài liệu tự xoá bằng chứng của mình thì
> lần sau không ai kiểm chứng được điều gì đã thay đổi.

## 1. Nhân viên khoa nhìn thấy gì hôm nay (kiểm kê 21/08, TRƯỚC Task 10)

**11 mục menu** (quản lý: 12). Nhưng công việc thật của một nhân viên khoa chỉ có **ba**:

1. Xin mua đồ
2. Xem đồ mình xin đã tới đâu
3. Quản kho của khoa mình

| # | Mục menu | Đường dẫn | Làm gì | Phán quyết |
|---|---|---|---|---|
| 1 | Tổng quan | `/dashboard` | KPI, công nợ, **đơn hàng gần đây**, hợp đồng khung | Giữ |
| 2 | Đặt hàng | `/catalog` | Tìm hàng, hai chế độ HĐ/Mua lẻ | **TRÙNG với #5** |
| 3 | Giỏ hàng | `/cart` | Chốt đơn, ngày giao, địa chỉ | **KHÔNG PHẢI ĐÍCH ĐẾN** — là một bước |
| 4 | Đơn hàng của tôi | `/orders` | Danh sách Sales Order | **TRÙNG NỬA với #6** |
| 5 | Lập phiếu đề xuất | `/de-xuat/lap` | Tìm hàng ba tầng, lập phiếu | **TRÙNG với #2** |
| 6 | Đề xuất mua | `/de-xuat` | Danh sách phiếu đề xuất | **TRÙNG NỬA với #4** |
| 7 | Duyệt | `/duyet` | Hàng chờ của quản lý | Giữ — *quản lý mới thấy* |
| 8 | Kho của tôi | `/kho` | 9 màn con: nhập, xuất, tồn, NCC, nhật ký… | Giữ — module riêng |
| 9 | Hoá đơn & công nợ | `/invoices` | Hoá đơn điện tử, công nợ | Giữ |
| 10 | Thông báo | `/thong-bao` | Thông báo | Giữ |
| 11 | Hồ sơ đơn vị | `/profile` | Thông tin đơn vị | Giữ |

**26 route, 11 cửa, 3 việc.**

---

## 2. Bốn chỗ trùng lặp — theo thứ tự nghiêm trọng

### 2.1 Đặt hàng (#2) và Lập phiếu đề xuất (#5) — cùng một việc

Cả hai đều là *"tìm hàng, chọn số lượng, gửi đi"*. Người dùng không có quy tắc nào trong đầu để chọn cửa nào.

**Vì sao có:** `Đặt hàng` có từ trước khi cổng có luồng duyệt. `Lập phiếu` dựng sau, khi thêm luồng duyệt. Giữ cả hai là **để lộ lịch sử thi công ra mặt người dùng**.

**Chủ đầu tư đã chốt:** gộp làm một, giữ tên **"Đặt hàng"**.

**✅ ĐÃ THI CÔNG (Task 10, 21/08).** `/dat-hang` là cửa duy nhất, hai BƯỚC
trên cùng một màn: (1) danh sách hàng hoá, (2) giỏ hàng + thông tin giao
hàng + nút gửi.

### 2.2 Giỏ hàng (#3) là một BƯỚC, không phải một đích đến

Không ai mở cổng lên với ý định *"vào xem giỏ hàng"*. Giỏ là chặng giữa của việc đặt hàng. Nó chiếm một cửa ngang hàng với "Kho của tôi" — một module có 9 màn.

**✅ ĐÃ THI CÔNG (Task 10).** Giỏ là **bước 2** của `/dat-hang`, không còn
mục nav, không còn badge số dòng trên thanh nav/thanh dưới. Giỏ toàn cục
trong bộ nhớ trình duyệt (`store.cart`) đã bỏ hẳn: giỏ nay CHÍNH LÀ một
phiếu `Portal De Xuat Mua` trạng thái Nháp trên server — sống qua F5, qua
đổi máy, và mang sẵn tầng giá do server suy.

### 2.3 Đơn hàng của tôi (#4) và Đề xuất mua (#6) — hai danh sách của CÙNG MỘT THỨ

Đây là chỗ trùng lặp **khó thấy nhất và phiền nhất**.

Nhân viên khoa xin 10 hộp găng tay. Yêu cầu đó:
- nằm ở **#6** khi còn là phiếu đề xuất (nháp → chờ duyệt → đã duyệt)
- nhảy sang **#4** sau khi quản lý duyệt (thành đơn hàng → chờ báo giá → đã giao)

Nghĩa là **để tìm lại yêu cầu của mình, nhân viên phải biết trước nó đang ở giai đoạn nội bộ nào của hệ thống.** Đó là bắt người dùng học sơ đồ kiến trúc của chúng ta.

**Và chính chủ đầu tư đã gỡ bỏ rào cản kỹ thuật cuối cùng của việc gộp** khi chốt ngày 21/08 rằng đơn hàng **mang thẳng mã đề xuất** (`MD-HUYETHOC-260819-91`) thay vì `SAL-ORD-…`. Phiếu và đơn giờ **cùng một mã**. Không còn lý do gì để chúng nằm hai danh sách.

### 2.4 "Đơn hàng gần đây" trên Tổng quan (#1) — cái nhìn thứ ba

Không nghiêm trọng (dashboard tóm tắt là bình thường), nhưng đáng ghi: cùng dữ liệu đó hiện ở **ba** nơi.

---

## 3. ĐÃ CHỐT (chủ đầu tư duyệt 21/08): 11 cửa → 7

| Mục | Đường dẫn | Ghi chú |
|---|---|---|
| Tổng quan | `/dashboard` | giữ nguyên |
| **Đặt hàng** | `/dat-hang` | tìm → giỏ → gửi duyệt. Nuốt #2, #3, #5 |
| **Yêu cầu của tôi** | `/yeu-cau` | **một** dòng đời: nháp → chờ duyệt → đã duyệt → chờ báo giá → đã giao. Nuốt #4, #6 |
| Kho của tôi | `/kho` | giữ nguyên, module riêng |
| Hoá đơn & công nợ | `/invoices` | giữ nguyên |
| Thông báo | `/thong-bao` | giữ nguyên |
| Hồ sơ đơn vị | `/profile` | giữ nguyên |

**Trạng thái:** Task 10 (gộp đặt hàng) **đã thi công 21/08**. Task 11 (gộp
danh sách) chưa — cho tới khi xong, nav thật là:

| # | Mục | Đường dẫn | Ghi chú |
|---|---|---|---|
| 1 | Tổng quan | `/dashboard` | |
| 2 | **Đặt hàng** | `/dat-hang` | **MỚI** — nuốt `/catalog`, `/cart`, `/de-xuat/lap` |
| 3 | Đơn hàng của tôi | `/orders` | Task 11 sẽ gộp với #4 |
| 4 | Đề xuất mua | `/de-xuat` | Task 11 sẽ gộp với #3 |
| 5 | Duyệt | `/duyet` | *quản lý mới thấy* |
| 6 | Kho của tôi | `/kho` | |
| 7 | Hoá đơn & công nợ | `/invoices` | |
| 8 | Thông báo | `/thong-bao` | |
| 9 | Hồ sơ đơn vị | `/profile` | |

**11 cửa → 9** (quản lý: 12 → 10). Task 11 đưa nốt về 7 (+ Duyệt).

### Task 10 BỎ đi những gì (để không ai đi tìm chúng)

| Thứ đã bỏ | Vì sao |
|---|---|
| Bộ chuyển **"Theo hợp đồng khung ｜ Mua lẻ"** | Ruling P1 — khách không có quy tắc nào trong đầu để chọn ngăn. Tầng giá nay suy theo TỪNG DÒNG (`portal_catalog_gop.tang`), một giỏ trộn cả hai loại đi qua đúng một lời gọi (`dat_hang._xay_don`, Task 4). |
| Giỏ **hai ngăn** + hai nút xác nhận + hai `request_id` | Cùng gốc: không còn "chế độ" nào để tách đơn theo. |
| Nhãn **"Có trong HĐNT — đặt ở chế độ Theo HĐNT"** (`thuoc_hdnt`) | Nó tồn tại CHỈ để điều hướng giữa hai ngăn. Không còn hai ngăn thì không còn gì để điều hướng — mặt hàng thuộc hợp đồng nay hiện thẳng badge `Giá HĐ …` ngay tại dòng của nó. Cờ `thuoc_hdnt` vẫn còn ở `portal_catalog_ban_le` (endpoint cũ, chưa gỡ). |
| **Tổng tiền / tạm tính / VAT** ở giỏ | QĐ-G9 — chỉ còn đơn giá TỪNG DÒNG. Tránh việc khoa nhớ một con số rồi đem so với hoá đơn cuối; Miyano báo giá đầy đủ ở bước sau. |
| Badge **số dòng giỏ hàng** trên nav + nút giỏ ở header mobile | Không còn giỏ toàn cục để đếm. |

### Đường cũ — chuyển hướng, không 404 (QĐ-G7)

| Đường cũ | Đi đâu |
|---|---|
| `/catalog` | → `/dat-hang` |
| `/cart` | → `/dat-hang` |
| `/de-xuat/lap/:ten?` | → `/dat-hang/:ten?` (giữ nguyên tham số) |

Nút **"Đặt lại"** ở màn chi tiết đơn (`/orders/:name`) trước đây nạp giỏ
toàn cục rồi đẩy sang `/cart`. Nay nó tạo thẳng một phiếu Nháp mang các
dòng đặt lại được và mở `/dat-hang/<mã phiếu>` — nếu chỉ để `/cart` chuyển
hướng suông thì khách nhận toast thành công và một giỏ TRỐNG, đúng loại
hỏng lặng lẽ mà tài liệu này tồn tại để bắt.

Quản lý thấy thêm: **Duyệt** (`/duyet`) — đây **không** phải danh sách trùng, nó là **hàng chờ việc**, khác về mục đích.

**Mọi đường cũ chuyển hướng, không xoá** — `/catalog`, `/cart`, `/orders`, `/de-xuat`, `/de-xuat/lap` đều có thể nằm trong bookmark của khách hoặc trong tài liệu đã gửi bệnh viện. Trả 404 cho một đường đang chạy là hồi quy, không phải dọn dẹp.

---

## 4. Vì sao lọt lưới — và đổi cách làm việc thế nào

**Nguyên nhân:** thi công theo kế hoạch task-by-task, mỗi task một vòng review **phạm vi hẹp theo task**. Kế hoạch ghi *"Task 8: Màn lập phiếu"* nên màn đó được dựng — không ai có nhiệm vụ hỏi *"cổng này đã có màn nào làm việc đó chưa?"*.

Đây là **lần thứ ba cùng một gốc** trong dự án:

| Lần | Thứ lọt lưới | Ai tìm ra |
|---|---|---|
| 1 | `de_xuat_xin_sua` dựng xong, **không có lối vào** | review toàn cục |
| 2 | `dieu_chinh` dựng xong, **không có lối vào** | review toàn cục |
| 3 | Màn lập phiếu **trùng** với màn đặt hàng | **chủ đầu tư** |
| 4 | `boi_so` được API trả về nhưng KHÔNG màn nào đọc | review Task 10 |

Lần thứ 4 là một biến thể khác của cùng một gốc: *"API đã trả về"* và
*"sản phẩm đã dùng"* là hai chuyện khác nhau. Một trường dữ liệu chỉ có
người sinh ra nó mà không có người tiêu thụ thì không tồn tại đối với
người dùng — và lỗi nó lẽ ra chặn được vẫn nổ, chỉ nổ muộn hơn và vào mặt
người khác (ở đây: bội số sai nổ vào màn DUYỆT của quản lý, cho một con số
quản lý không hề chọn).

Review hẹp không thấy được thứ **vắng mặt**, và cũng không thấy được thứ **trùng lặp**. Cả hai chỉ lộ ra khi có người nhìn *toàn sản phẩm*.

### Bốn thay đổi, áp dụng từ 21/08/2026

1. **File này là cổng bắt buộc.** Task nào thêm/bỏ màn hoặc mục menu phải sửa nó trong cùng commit. Review từ chối task không sửa.

2. **Ba câu hỏi trong MỌI brief dựng màn mới**, trả lời trước khi giao việc:
   - Cổng đã có màn nào làm việc này chưa?
   - Màn mới **thay thế** cái gì?
   - Cái cũ **nghỉ hay ở lại** — và nếu ở lại thì vì lý do gì?

3. **Cổng "đi một vòng như người dùng"** trước khi báo xong: mở cổng bằng tài khoản **nhân viên khoa** thật, **đếm số cửa**, và đi trọn một việc từ đầu tới cuối. Không thay bằng "suite xanh". Hai lần "1313 test xanh" đã che đúng loại lỗi này.

4. **Review toàn cục có thêm một lăng kính**: không chỉ soi diff, mà soi **menu như người dùng nhìn thấy**. Câu hỏi bắt buộc: *"hai mục nào ở đây có thể khiến người dùng phân vân nên bấm cái nào?"*
