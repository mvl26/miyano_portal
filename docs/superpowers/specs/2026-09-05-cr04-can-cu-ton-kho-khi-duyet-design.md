# CR-04 — Căn cứ tồn kho ngay cạnh dòng hàng khi duyệt

**Ngày:** 05/09/2026 · **Chủ đầu tư chốt trong phiên**

## 1. Vấn đề

Quản lý duyệt đơn phải trả lời đúng một câu: *"số lượng nhân viên đề nghị có
hợp lý không?"*. Hôm nay họ không có căn cứ nào ngoài kinh nghiệm — màn duyệt
chỉ hiện tên hàng, ĐVT và số lượng đề xuất.

CR-04 đặt các con số cần thiết **ngay cạnh dòng hàng**, bên trái ô nhập
"SL duyệt", để quyết định duyệt là quyết định có căn cứ.

## 2. Bốn dữ kiện đã ĐO trên hệ thống thật

Đo trước khi thiết kế, và chúng cắt bản vẽ gốc đi khá nhiều:

| Dữ kiện | Số đo | Hệ quả |
|---|---|---|
| Vật tư kho đã khai Min/Max/điểm đặt lại/bội số | **0 / 22** | Bỏ cột Min/Max, bỏ cột "Đề xuất" |
| Vật tư kho nối được `item_code` sang Item | **17 / 22** | ~1/4 dòng hàng không tra được |
| Kho đang hoạt động / số khách | **5 / 6** | Một bệnh viện không có kho nào |
| Vật tư có lịch sử xuất trong 12 tuần | **5 / 22** | ADU trống với phần lớn dòng hôm nay |

**Hai khoảng trống KHÁC BẢN CHẤT nhau, và đó là lý do xử khác nhau:**

* Min/Max **không tự đầy** — phải có người ngồi khai từng vật tư. Chưa ai
  khai, và không có kế hoạch nào bắt khai. Cột dựa vào nó sẽ trống vĩnh viễn.
* ADU **tự đầy** theo thời gian, chỉ cần bệnh viện dùng kho. Trống hôm nay
  không có nghĩa trống mãi.

Nên: bỏ hẳn nhóm Min/Max, GIỮ nhóm ADU.

## 3. Sáu cột

`Vật tư · Tồn hiện có · Đang về · Dùng TB/ngày · Còn dùng được · NV đặt`
— rồi tới ô nhập **SL duyệt** đã có.

**Tồn hiện có** — tồn khả dụng tại kho khách. Lấy qua
`kho.reports.ton_hien_tai_rows()`, đúng hàm báo cáo tồn kho đang dùng; KHÔNG
viết phép cộng lô lần thứ hai.

**Đang về** — *đã đặt nhưng chưa nhập kho* (chủ đầu tư chốt nguyên văn).

    Đang về = Σ (số lượng đặt trên các đơn CÒN HIỆU LỰC)
            − Σ (số lượng đã nhập kho TỪ CHÍNH các đơn đó)

`Customer Stock Receipt` mang `sales_order`, nên quy được về đơn.

Công thức này CỐ Ý rộng hơn `qty − delivered_qty` mà bản vẽ gốc ghi. Chênh
lệch nằm ở khoảng **đã giao nhưng chưa vào sổ kho**: phiếu nhập tự sinh hỏng
(bị `_chay_an_toan` nuốt, chỉ để lại một dòng Error Log), phiếu giao lùi ngày
trước `ngay_bat_dau` của kho, hoặc kiểm hàng trả lại một phần. Trong mọi ca
đó hàng CHƯA nằm trên kệ của bệnh viện — đúng nghĩa "đang về".

Đơn của **chính lần duyệt này KHÔNG tính vào** — nếu tính, con số đó cộng
trùng với cột "NV đặt" ngay cạnh, và quản lý đọc ra "hàng sắp về rồi" cho
chính lô họ đang cân nhắc.

**Dùng TB/ngày (ADU)** — bình quân xuất kho mỗi ngày, kỳ trượt 12 tuần.
Chỉ tính dòng XUẤT (`so_luong < 0`) trong `Customer Stock Ledger Entry`.

**Còn dùng được** = `(Tồn + Đang về) ÷ ADU`, đơn vị ngày. ADU = 0 thì
KHÔNG chia — trả `None`, hiện `—`.

**NV đặt** — số nhân viên đề nghị, đã có sẵn trên màn (`so_luong_de_xuat`).

## 4. Không có dữ liệu thì hiện GẠCH NGANG, không hiện 0

Quyết định quan trọng nhất của CR này.

**"Tồn 0" nghĩa là HẾT HÀNG. "Không biết" là chuyện khác hẳn.** Cho quản lý
đọc nhầm hai thứ đó là làm hỏng đúng cái mà CR-04 sinh ra để sửa — họ sẽ
duyệt một đơn vì tưởng kho trống, trong khi thật ra hệ thống không tra được.

Ba ca hiện `—`, kèm một dòng giải thích ngắn trên bảng:

1. Bệnh viện chưa mở kho trên cổng (1/6 khách hiện tại)
2. Vật tư kho chưa nối `item_code` (5/22 vật tư)
3. Hàng trên đơn không có trong danh mục kho của bệnh viện

## 5. Cờ ⚠ và màu chấm — tính theo TỒN TRỮ, không theo Min

Bản vẽ gốc: chấm đỏ khi `tồn ≤ Min`, ⚠ khi *"NV đặt lệch đáng kể so với đề
xuất"*. Cả hai đều cần Min/Max, mà 0/22 vật tư có.

Thay bằng **"Còn dùng được"**, và điều đáng nói: **chính dữ liệu trong bản vẽ
của chủ đầu tư đã khớp cách này** — hai dòng ⚠ là hai dòng còn dùng lâu nhất
(40 ngày, 100 ngày), hai dòng ✓ là hai dòng sắp hết (5 ngày, 9 ngày).

| Dấu | Điều kiện | Nghĩa cho quản lý |
|---|---|---|
| 🔴 | Còn dùng được ≤ 7 ngày | Sắp hết, đơn này cần |
| 🟡 | ≤ 14 ngày | Đang cạn |
| 🟢 | > 14 ngày | Đủ tồn |
| ⚠ | Còn dùng được ≥ 30 ngày **và** NV vẫn đặt | Xem kỹ: đặt khi chưa cần |

Ngưỡng đặt ở MỘT chỗ trong mã, có tên, để đổi được mà không phải đi tìm số
rải rác. ADU trống thì KHÔNG chấm màu, KHÔNG cờ — không biết thì đừng đoán.

## 6. Sổ kho xổ ngay tại dòng

Bấm vào một dòng thì thẻ kho (nhập/xuất/tồn luỹ kế) của vật tư đó mở ra ngay
dưới, **không rời màn duyệt**: quản lý đang cân nhắc cả đơn, rời màn là mất
mạch và quay lại phải dò lại dòng đang xem.

Dùng lại `kho.reports.the_kho_rows()` đã có. Endpoint đọc riêng, đi qua đúng
chốt hai trục như mọi endpoint cổng.

## 7. Quyền và fail-safe

Endpoint **KHÔNG được gọi thẳng `get_portal_kho()`** — hàm đó NÉM
`PermissionError` khi khách chưa mở kho, và như vậy màn chi tiết đơn của
bệnh viện không có kho sẽ chết. Dùng `frappe.db.get_value("Customer
Warehouse", {customer, active:1})` rồi rơi về `—`, đúng tiền lệ đã có trong
`portal_order_track`.

Module kho hỏng KHÔNG được làm chết màn duyệt: bọc như
`dn_co_hoa_don_nhap` — hỏng thì mất các con số, không mất cả trang.

## 8. Ngoài phạm vi

Không làm cột "Đề xuất" (cần Max). Không làm màn khai Min/Max. Không đụng
báo cáo kho hiện có. Không đổi luồng duyệt — CR này chỉ THÊM căn cứ, không
đổi ai được duyệt hay duyệt thế nào.
