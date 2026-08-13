"""Report desk "Cấp phát theo khoa phòng" — US-E8.5 (UC-56).

Toàn bộ số học sống ở `miyano_portal.kho.reports.bao_cao_cap_phat_rows()`
(nhóm theo khoa, join sổ kho <-> phiếu xuất, loại trừ phiếu đảo) gọi lại qua
`miyano_portal.kho.desk_reports.cap_phat_theo_khoa_rows()` cho MỌI khách hàng
cùng lúc — không viết lại phép tính lần thứ hai.

Quyền hạn: `ref_doctype=Customer Stock Ledger Entry`, `roles=System Manager/
Sales Manager/Sales User` (xem setup/install_kho_desk_reports.py). Role
`Customer` KHÔNG có DocPerm nào trên doctype này — report liệt kê cấp phát
của MỌI khách hàng, cùng hạn chế VĐ-10 như các report desk khác trong module.
"""

import frappe

from miyano_portal.kho import desk_reports

COLUMNS = [
	{"label": "Khách hàng", "fieldname": "customer_name", "fieldtype": "Data", "width": 180},
	{"label": "Khoa phòng", "fieldname": "khoa_phong", "fieldtype": "Data", "width": 160},
	{"label": "Ngày", "fieldname": "ngay", "fieldtype": "Date", "width": 90},
	{"label": "Phiếu", "fieldname": "phieu", "fieldtype": "Data", "width": 120},
	{"label": "Vật tư", "fieldname": "vat_tu", "fieldtype": "Data", "width": 200},
	{"label": "ĐVT", "fieldname": "dvt", "fieldtype": "Data", "width": 70},
	{"label": "SL", "fieldname": "sl", "fieldtype": "Float", "precision": 2, "width": 90},
	{"label": "Giá trị", "fieldname": "gia_tri", "fieldtype": "Currency", "width": 130},
	{"label": "Người nhận", "fieldname": "nguoi_nhan", "fieldtype": "Data", "width": 150},
]


def execute(filters=None):
	filters = frappe._dict(filters or {})
	data = desk_reports.cap_phat_theo_khoa_rows(
		customer=filters.get("customer") or None,
		tu_ngay=filters.get("tu_ngay") or None,
		den_ngay=filters.get("den_ngay") or None,
	)
	return COLUMNS, data
