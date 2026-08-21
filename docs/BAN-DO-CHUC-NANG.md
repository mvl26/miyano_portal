# Bản đồ chức năng cổng khách hàng

> **Tài liệu SỐNG.** Bất kỳ task nào thêm/bỏ một màn hoặc một mục menu **phải sửa file này trong cùng commit**. Một màn không có dòng ở đây là một màn không ai biết nó tồn tại để làm gì.

Kiểm kê ngày 21/08/2026, sau khi chủ đầu tư chỉ ra: *"anh thấy vẫn còn mục đặt hàng xong lại còn lập phiếu đề xuất, hệ thống chúng ta đang rất không hợp lý"*.

---

## 1. Nhân viên khoa nhìn thấy gì hôm nay

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

### 2.2 Giỏ hàng (#3) là một BƯỚC, không phải một đích đến

Không ai mở cổng lên với ý định *"vào xem giỏ hàng"*. Giỏ là chặng giữa của việc đặt hàng. Nó chiếm một cửa ngang hàng với "Kho của tôi" — một module có 9 màn.

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

**Trạng thái:** Task 10 (gộp đặt hàng) và Task 11 (gộp danh sách) đã vào kế hoạch `docs/superpowers/plans/2026-08-19-gop-luong-dat-hang.md`.

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

Review hẹp không thấy được thứ **vắng mặt**, và cũng không thấy được thứ **trùng lặp**. Cả hai chỉ lộ ra khi có người nhìn *toàn sản phẩm*.

### Bốn thay đổi, áp dụng từ 21/08/2026

1. **File này là cổng bắt buộc.** Task nào thêm/bỏ màn hoặc mục menu phải sửa nó trong cùng commit. Review từ chối task không sửa.

2. **Ba câu hỏi trong MỌI brief dựng màn mới**, trả lời trước khi giao việc:
   - Cổng đã có màn nào làm việc này chưa?
   - Màn mới **thay thế** cái gì?
   - Cái cũ **nghỉ hay ở lại** — và nếu ở lại thì vì lý do gì?

3. **Cổng "đi một vòng như người dùng"** trước khi báo xong: mở cổng bằng tài khoản **nhân viên khoa** thật, **đếm số cửa**, và đi trọn một việc từ đầu tới cuối. Không thay bằng "suite xanh". Hai lần "1313 test xanh" đã che đúng loại lỗi này.

4. **Review toàn cục có thêm một lăng kính**: không chỉ soi diff, mà soi **menu như người dùng nhìn thấy**. Câu hỏi bắt buộc: *"hai mục nào ở đây có thể khiến người dùng phân vân nên bấm cái nào?"*
