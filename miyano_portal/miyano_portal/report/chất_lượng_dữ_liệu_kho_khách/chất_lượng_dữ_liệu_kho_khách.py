"""Report desk "Chất lượng dữ liệu kho khách" — US-E3.6, Phần B của E3.

(M5, E3 phần B review: đổi tên từ "Chất lượng dữ liệu" — tên Report
DOCNAME DUY NHẤT TOÀN SITE across mọi app, một tên chung chung như vậy dễ
đụng report của app khác trong tương lai.)

Liệt kê các Item của Miyano đang sinh ra dòng `thieu_lo_han=1` trên phiếu
nhập kho khách hàng (NL-3.7: lô rơi về `KHONG-LO` vì Item chưa bật `Has
Batch No`/`Has Expiry Date`) — số học sống ở
`miyano_portal.kho.desk_reports.chat_luong_du_lieu_rows()`.

Quyền hạn: cùng khuôn với `đối_soát_giao_nhận.py` — `ref_doctype=Customer
Stock Receipt`, `roles=System Manager/Sales Manager/Sales User`, KHÔNG có
role `Customer`.
"""

import frappe

from miyano_portal.kho import desk_reports

COLUMNS = [
	{"label": "Mã Item", "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 140},
	{"label": "Tên Item", "fieldname": "item_name", "fieldtype": "Data", "width": 240},
	{"label": "Đã bật Has Batch No", "fieldname": "has_batch_no", "fieldtype": "Check", "width": 130},
	{"label": "Đã bật Has Expiry Date", "fieldname": "has_expiry_date", "fieldtype": "Check", "width": 140},
	{"label": "Số dòng thiếu lô/hạn", "fieldname": "so_dong_thieu", "fieldtype": "Int", "width": 130},
	{"label": "Số khách bị ảnh hưởng", "fieldname": "so_khach_anh_huong", "fieldtype": "Int", "width": 130},
	{"label": "Lần gần nhất", "fieldname": "lan_gan_nhat", "fieldtype": "Date", "width": 110},
]


def execute(filters=None):
	filters = frappe._dict(filters or {})
	raw = filters.get("chi_chua_bat_co")
	# Mặc định BẬT khi field vắng mặt (None/"" — ô Check chưa từng đổi giá
	# trị trong URL deep-link); có mặt thì cint() trước khi dùng, KHÔNG so
	# truthy thô — một filter gửi "0" (chuỗi) là truthy trong Python, sẽ
	# BẬT nhầm bộ lọc dù người dùng đang để ô Check TẮT.
	chi_chua_bat_co = True if raw in (None, "") else bool(frappe.utils.cint(raw))
	data = desk_reports.chat_luong_du_lieu_rows(
		customer=filters.get("customer") or None,
		chi_chua_bat_co=chi_chua_bat_co,
	)
	return COLUMNS, data
