"""Report desk "Cảnh báo hạn dùng khách hàng" — Phase 6, bản nhiều-khách-hàng
của cảnh báo hạn dùng đã có trên portal. Phép lọc/sắp xếp vẫn chỉ sống trong
`reports.canh_bao_han_rows()`; `desk_reports.canh_bao_han_khach_hang_rows()`
lặp qua từng kho rồi sắp lại TOÀN CỤC theo hạn sử dụng (nearest-first xuyên
khách hàng) — không viết lại phép lọc "đã hết hạn / sắp hết hạn" ở đây.
"""

import frappe

from miyano_portal.kho import desk_reports, reports

_TAIL_COLUMNS = reports.CANH_BAO_COLUMNS[3:]  # Số lô .. Trạng thái

COLUMNS = [
	{"label": "Khách hàng", "fieldname": "customer_name", "fieldtype": "Data", "width": 200},
	{"label": "Kho", "fieldname": "ten_kho", "fieldtype": "Data", "width": 160},
	{"label": "Mã vật tư", "fieldname": "ma_vat_tu", "fieldtype": "Data", "width": 120},
	{"label": "Tên vật tư", "fieldname": "ten_vat_tu", "fieldtype": "Data", "width": 220},
	{"label": "ĐVT", "fieldname": "dvt", "fieldtype": "Data", "width": 80},
] + [
	{
		"label": label, "fieldname": field, "width": 120,
		"fieldtype": {
			"han_su_dung": "Date",
			"so_ngay_con_lai": "Int",
			"so_luong": "Float",
		}.get(field, "Data"),
	}
	for label, field in _TAIL_COLUMNS
]

DEFAULT_SO_NGAY = 90


def execute(filters=None):
	filters = frappe._dict(filters or {})
	so_ngay = filters.get("so_ngay")
	so_ngay = frappe.utils.cint(so_ngay) if so_ngay not in (None, "") else DEFAULT_SO_NGAY
	data = desk_reports.canh_bao_han_khach_hang_rows(
		customer=filters.get("customer") or None, so_ngay=so_ngay,
	)
	return COLUMNS, data
