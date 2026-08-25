"""Task 12 (2026-08-21, gộp luồng đặt hàng) — backfill `Item Price` từ MỌI
hợp đồng khung bán ĐÃ TRÌNH KÝ còn hiệu lực.

`gia_hdnt.tu_hdnt` là hook `Blanket Order.on_submit`: nó chạy ĐÚNG MỘT LẦN,
lúc trình ký. Mọi hợp đồng ký TRƯỚC khi hook đó ra đời, và mọi hợp đồng nạp
bằng `migration/import_erpnext.py`, chưa bao giờ đi qua nó — nên `tabItem
Price` trống trong khi hợp đồng khai giá đầy đủ. Cơ chế đúng, phủ không kín,
và cái không kín thì im lặng.

VÌ SAO CẦN PATCH THỨ HAI khi `patches/v1_13/dong_bo_gia_hdnt.py` đã làm đúng
việc này: một patch chạy ĐÚNG MỘT LẦN MỖI SITE. `tabPatch Log` trên
`erptest.local` ghi v1_13 chạy 2026-08-14; các hợp đồng của Bệnh viện Đa khoa
Minh Đức (`MFG-BLR-2026-00020`) và Hùng Vương vào site SAU mốc đó, nên chúng
nằm ngoài tầm với của v1_13 vĩnh viễn. Đây là một lần CHẠY LẠI cho dữ liệu
đến sau, không phải một cơ chế mới — cố ý KHÔNG gọi `v1_13.execute()`: patch
là bản ghi lịch sử, không phải thư viện để module khác gọi vào.

Patch này KHÔNG thay QĐ-G12 (`gia_hdnt.gia_dong_hop_dong`, cổng tự đọc thẳng
`Blanket Order Item.rate`). Hai việc khác nhau, cần cả hai:

  * QĐ-G12 làm CỔNG đúng ngay — khách đặt được hàng kể cả khi bảng giá trống;
  * patch này làm DỮ LIỆU nhất quán cho phía ERPNext — báo cáo, hoá đơn, và
    giá mà Desk tự điền khi nhân viên Miyano dựng chứng từ bằng tay. Không có
    nó, hai phía nhìn hai con số khác nhau cho cùng một hợp đồng.

Quét theo KHÁCH HÀNG rồi gọi `dong_bo_khach()`, KHÔNG lặp thẳng danh sách
hợp đồng: làm vậy được miễn phí hai thứ đã chốt ở `gia_hdnt.py` và không
nhân bản ra đây — LUẬT PHÂN ĐỊNH của cổng và ĐỊNH NGHĨA "còn hiệu lực"
(`dong_bo()` tự loại hợp đồng đã hết hạn). Tự lọc `to_date` trong truy vấn
của patch là dựng nơi thứ hai định nghĩa cùng một khái niệm — đúng thứ
docstring `dong_bo_khach()` đã cảnh báo.

SỬA 25/08 — câu trên trước đây ghi luật phân định là `creation asc` ("hợp
đồng KÝ SAU ghi sau cùng nên thắng"). **Ruling P30 đã ĐẢO luật đó** và câu
cũ nằm lại thành một mô tả sai về chính đoạn mã nó giới thiệu: người thắng
giờ do `nguon_gia_theo_ma_cho_khach()` quyết (`THU_TU_PHAN_DINH` — hết hạn
SỚM NHẤT thắng, trùng `to_date` thì `name` nhỏ hơn thắng), và
`dong_bo_khach()` truyền người thắng đó xuống để hợp đồng THUA không ghi giá
cho mã đó. `creation asc` vẫn còn trong `dong_bo_khach()` nhưng chỉ còn là
thứ tự TẤT ĐỊNH cho những mã không có người thắng nào.

IDEMPOTENT theo thiết kế, không nhờ một cờ riêng: `dong_bo()` tra `Item
Price` theo `(item_code, price_list, selling)` — có rồi thì `set_value`
(hoặc bỏ qua nếu đã đúng giá), chưa có mới `insert`. Chạy lần thứ hai không
sinh thêm dòng nào. `rate <= 0` (CHƯA KHAI GIÁ) vẫn bị bỏ qua, không dựng
một dòng giá 0 che mất việc sales cần làm.

Không ném lỗi cho cả `migrate` vì MỘT khách hỏng: khách chưa có
`default_price_list` là tình huống dữ liệu bình thường (`dong_bo` trả `ly_do`
và không đồng bộ gì), còn lỗi thật thì ghi Error Log kèm tên khách rồi đi
tiếp — một patch dữ liệu dừng giữa chừng để lại trạng thái nửa vời khó lần
hơn nhiều so với một dòng log.
"""

import frappe

from miyano_portal import gia_hdnt


def execute():
	khach = frappe.get_all(
		"Blanket Order",
		filters={"blanket_order_type": "Selling", "docstatus": 1},
		pluck="customer",
		distinct=True,
	)
	tao = cap_nhat = 0
	for ten in sorted({k for k in khach if k}):
		try:
			kq = gia_hdnt.dong_bo_khach(ten)
		except Exception:
			frappe.log_error(
				title=f"Backfill giá HĐNT: khách {ten} không đồng bộ được"
			)
			continue
		tao += kq["tao"]
		cap_nhat += kq["cap_nhat"]
	print(
		f"Đồng bộ giá HĐNT đã ký: {tao} đơn giá mới, {cap_nhat} đơn giá cập nhật, "
		f"trên {len(set(khach))} khách hàng."
	)
