from frappe.model.document import Document


class SalesOrderDatNgoaiItem(Document):
	"""Dòng "chưa có trong kho, cần đặt ngoài" trên `Sales Order` (thiết kế
	§4.3) — khách gõ thẳng tên hàng/ĐVT/số lượng khi không tìm thấy mã hàng
	trong danh mục; nhân viên Miyano khớp `item_khop` khi báo giá.

	CỐ Ý không override `validate()` ở đây: Frappe KHÔNG gọi `validate()` của
	controller bảng con khi document cha lưu — chỉ các kiểm tra tầng khung
	(mandatory/link/options) chạy tự động cho bảng con, phần "why" đầy đủ nằm
	ở `miyano_portal.portal_mua_le.dong_bo_da_xu_ly_dat_ngoai` (đăng ký ở
	`hooks.py::doc_events["Sales Order"]["validate"]`) — nơi DUY NHẤT đồng bộ
	`da_xu_ly` theo `item_khop` và kiểm `so_luong > 0`. Một `validate()` ở
	đây sẽ không bao giờ chạy, và một agent sau đọc thấy nó tưởng chốt đã có
	trong khi thật ra chốt sống ở nơi khác — im lặng vô hiệu, đúng lớp lỗi
	"chốt chưa từng được viết" mà dự án này đã trả giá nhiều lần.
	"""
