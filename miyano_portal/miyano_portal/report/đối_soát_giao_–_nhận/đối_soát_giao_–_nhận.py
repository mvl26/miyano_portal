"""Report desk "Đối soát giao – nhận" — US-E3.5 (UC-48), Phần B của E3.

Toàn bộ số học sống ở `miyano_portal.kho.desk_reports.doi_soat_giao_nhan_rows()`;
file này chỉ khai báo cột và chuyển tiếp filter — cùng khuôn với ba report
Phase 6 (`tồn_kho_khách_hàng.py`...).

Quyền hạn: `ref_doctype=Customer Stock Receipt`, `roles=System Manager/Sales
Manager/Sales User` (xem setup/install_kho_desk_reports.py). Role `Customer`
KHÔNG có DocPerm nào trên doctype này — report này liệt kê dữ liệu của MỌI
khách hàng, để lọt role Customer vào là rò rỉ chéo khách hàng.
`frappe.desk.query_report.run()` kiểm `frappe.has_permission(ref_doctype,
"report")` TRƯỚC khi `execute()` này được gọi, nên hàm dưới đây không tự
kiểm quyền gì thêm.
"""

import frappe

from miyano_portal.kho import desk_reports

COLUMNS = [
	{"label": "Phiếu giao (DN)", "fieldname": "delivery_note", "fieldtype": "Link", "options": "Delivery Note", "width": 150},
	{"label": "Đơn hàng (SO)", "fieldname": "sales_order", "fieldtype": "Link", "options": "Sales Order", "width": 150},
	{"label": "Khách hàng", "fieldname": "customer_name", "fieldtype": "Data", "width": 200},
	{"label": "Đợt", "fieldname": "so_dot", "fieldtype": "Int", "width": 60},
	{"label": "Vật tư", "fieldname": "ten_vat_tu", "fieldtype": "Data", "width": 200},
	{"label": "SL giao", "fieldname": "sl_giao", "fieldtype": "Float", "precision": 2, "width": 100},
	{"label": "SL thực nhận", "fieldname": "so_luong", "fieldtype": "Float", "precision": 2, "width": 100},
	{"label": "Chênh", "fieldname": "chenh", "fieldtype": "Float", "precision": 2, "width": 90},
	{"label": "Lý do chênh lệch", "fieldname": "ly_do_chenh_lech", "fieldtype": "Data", "width": 220},
	{"label": "Phiếu nhập", "fieldname": "phieu_nhap", "fieldtype": "Link", "options": "Customer Stock Receipt", "width": 130},
	{"label": "Trạng thái phiếu", "fieldname": "trang_thai_phieu", "fieldtype": "Data", "width": 130},
]


def execute(filters=None):
	filters = frappe._dict(filters or {})
	data = desk_reports.doi_soat_giao_nhan_rows(
		customer=filters.get("customer") or None,
		# cint(), không truthy thô: một filter URL deep-link gửi "0" (chuỗi)
		# là truthy trong Python — sẽ bật nhầm bộ lọc khi ô Check đang TẮT.
		chi_chenh_lech=frappe.utils.cint(filters.get("chi_chenh_lech")),
		qua_han_ngay=filters.get("qua_han_ngay") or None,
	)
	return COLUMNS, data
