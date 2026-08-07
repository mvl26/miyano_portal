"""Report desk "Tồn kho khách hàng" — Phase 6. Toàn bộ số học sống ở
`miyano_portal.kho.desk_reports.ton_kho_khach_hang_rows()` (gọi lại
`reports.ton_hien_tai_rows()` cho từng kho); file này chỉ khai báo cột và
chuyển tiếp filter. Không tính toán gì ở đây.

Quyền hạn: hoàn toàn nằm ở Report doctype (`ref_doctype=Customer Stock Lot
Balance`, roles=System Manager/Sales Manager/Sales User) — xem
setup/install_kho_desk_reports.py. `frappe.desk.query_report.run()` kiểm
`frappe.has_permission(ref_doctype, "report")` TRƯỚC khi execute() này được
gọi, nên hàm dưới đây không tự kiểm quyền gì thêm.
"""

import frappe

from miyano_portal.kho import desk_reports

COLUMNS = [
	{"label": "Khách hàng", "fieldname": "customer_name", "fieldtype": "Data", "width": 200},
	{"label": "Kho", "fieldname": "ten_kho", "fieldtype": "Data", "width": 160},
	{"label": "Mã vật tư", "fieldname": "ma_vat_tu", "fieldtype": "Data", "width": 120},
	{"label": "Tên vật tư", "fieldname": "ten_vat_tu", "fieldtype": "Data", "width": 220},
	{"label": "ĐVT", "fieldname": "dvt", "fieldtype": "Data", "width": 80},
	{"label": "Số lượng tồn", "fieldname": "so_luong", "fieldtype": "Float", "precision": 2, "width": 120},
	{"label": "Giá trị", "fieldname": "gia_tri", "fieldtype": "Currency", "precision": 0, "width": 150},
	{"label": "Số lô", "fieldname": "so_lo_count", "fieldtype": "Int", "width": 80},
	{"label": "Hạn gần nhất", "fieldname": "han_gan_nhat", "fieldtype": "Date", "width": 110},
]


def execute(filters=None):
	filters = frappe._dict(filters or {})
	data = desk_reports.ton_kho_khach_hang_rows(
		customer=filters.get("customer") or None,
		item=filters.get("item") or None,
		sap_het_han_trong_ngay=filters.get("sap_het_han_trong_ngay") or None,
	)
	return COLUMNS, data
