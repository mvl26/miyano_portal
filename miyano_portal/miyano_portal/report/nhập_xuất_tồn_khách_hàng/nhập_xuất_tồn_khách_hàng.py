"""Report desk "Nhập-Xuất-Tồn khách hàng" — Phase 6, bản nhiều-khách-hàng của
báo cáo N-X-T đã có trên portal. Toàn bộ tám con số vẫn tính bởi đúng một hàm
`reports.nxt_item_rows()` — `desk_reports.nxt_khach_hang_rows()` chỉ LẶP qua
từng kho rồi gắn thêm khách hàng, không viết lại phép cộng nào (xem docstring
đầu `kho/desk_reports.py`).

Mặc định khoảng ngày = THÁNG HIỆN TẠI khi người dùng chưa chọn filter —
tính lại mỗi lần chạy, không hardcode một tháng cố định (bài học "date rot"
đã ghi trong test_kho_reports.py).
"""

import frappe

from miyano_portal.kho import desk_reports, reports

# Năm cột đầu cố định + tám cột số DÙNG LẠI nhãn từ reports.NXT_COLUMNS (bỏ ba
# cột Mã/Tên/ĐVT đầu của mảng đó — desk report đặt chúng ngay sau Khách hàng/
# Kho, còn tám cột số giữ nguyên nhãn+field để không lệch khỏi portal.
_FIGURE_COLUMNS = reports.NXT_COLUMNS[3:]

COLUMNS = [
	{"label": "Khách hàng", "fieldname": "customer_name", "fieldtype": "Data", "width": 200},
	{"label": "Kho", "fieldname": "ten_kho", "fieldtype": "Data", "width": 160},
	{"label": "Mã vật tư", "fieldname": "ma_vat_tu", "fieldtype": "Data", "width": 120},
	{"label": "Tên vật tư", "fieldname": "ten_vat_tu", "fieldtype": "Data", "width": 220},
	{"label": "ĐVT", "fieldname": "dvt", "fieldtype": "Data", "width": 80},
] + [
	{
		"label": label, "fieldname": field, "width": 130,
		"fieldtype": "Currency" if field.endswith("_tt") else "Float",
		"precision": 0 if field.endswith("_tt") else 2,
	}
	for label, field in _FIGURE_COLUMNS
]


def execute(filters=None):
	filters = frappe._dict(filters or {})
	today = frappe.utils.getdate(frappe.utils.today())
	tu_ngay = filters.get("tu_ngay") or frappe.utils.get_first_day(today)
	den_ngay = filters.get("den_ngay") or frappe.utils.get_last_day(today)
	data = desk_reports.nxt_khach_hang_rows(
		customer=filters.get("customer") or None, tu_ngay=tu_ngay, den_ngay=den_ngay,
	)
	return COLUMNS, data
