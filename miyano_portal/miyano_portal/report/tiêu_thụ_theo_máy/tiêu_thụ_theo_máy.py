"""Report desk "Tiêu thụ theo máy" (Task 10) — xoay chiều của "Vật tư · Máy ·
Khoa phòng" (Task 9): ở đó trục ngoài là VẬT TƯ, ở đây trục ngoài là MÁY.

Toàn bộ số học sống ở `miyano_portal.kho.reports.tieu_thu_theo_may_rows()`
(một kho, hai lớp lọc cấp phát) gọi lại qua
`miyano_portal.kho.desk_reports.tieu_thu_theo_thiet_bi_rows()` cho MỌI khách
hàng cùng lúc rồi BẺ PHẲNG xuống mức dòng (một dòng = một máy × một vật tư)
— không viết lại phép tính lần thứ hai, đúng khuôn "Cấp phát theo khoa
phòng" ngay cạnh report này.

Quyền hạn: `ref_doctype=Customer Stock Ledger Entry`, `roles=System Manager/
Sales Manager/Sales User` (xem setup/install_kho_desk_reports.py). Role
`Customer` KHÔNG có DocPerm nào trên doctype này — report liệt kê tiêu thụ
theo máy của MỌI khách hàng, cùng hạn chế VĐ-10 như các report desk khác.
"""

import frappe

from miyano_portal.kho import desk_reports

COLUMNS = [
	{"label": "Khách hàng", "fieldname": "customer_name", "fieldtype": "Data", "width": 180},
	{"label": "Kho", "fieldname": "ten_kho", "fieldtype": "Data", "width": 140},
	{
		"label": "Máy", "fieldname": "thiet_bi", "fieldtype": "Link",
		"options": "Customer Equipment", "width": 160,
	},
	{"label": "Tên máy", "fieldname": "ten_may", "fieldtype": "Data", "width": 180},
	{"label": "Mã máy", "fieldname": "ma_may", "fieldtype": "Data", "width": 110},
	{"label": "Khoa phòng đặt máy", "fieldname": "ten_khoa", "fieldtype": "Data", "width": 150},
	{
		"label": "Vật tư", "fieldname": "vat_tu_id", "fieldtype": "Link",
		"options": "Customer Warehouse Item", "width": 160,
	},
	{"label": "Tên vật tư", "fieldname": "ten_vat_tu", "fieldtype": "Data", "width": 200},
	{"label": "ĐVT", "fieldname": "dvt", "fieldtype": "Data", "width": 70},
	{"label": "SL cấp phát", "fieldname": "sl", "fieldtype": "Float", "precision": 2, "width": 100},
	{"label": "Giá trị", "fieldname": "gia_tri", "fieldtype": "Currency", "width": 130},
]


def execute(filters=None):
	filters = frappe._dict(filters or {})
	data = desk_reports.tieu_thu_theo_thiet_bi_rows(
		customer=filters.get("customer") or None,
		tu_ngay=filters.get("tu_ngay") or None,
		den_ngay=filters.get("den_ngay") or None,
	)
	return COLUMNS, data
