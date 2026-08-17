"""Report desk "Cấp phát theo tháng và khoa phòng" — yêu cầu chủ đầu tư
2026-08-17 ("báo cáo kho ghi nhận theo từng tháng đối với từng khoa phòng").

Toàn bộ số học sống ở `miyano_portal.kho.reports.cap_phat_thang_rows()` (một
lượt GỘP trên đầu ra của `bao_cao_cap_phat_rows` — thừa hưởng nguyên phép loại
phiếu đảo hai lớp và nhóm "Chưa gắn khoa"), gọi lại qua
`desk_reports.cap_phat_thang_theo_khoa_rows()` cho MỌI khách hàng cùng lúc.
Không phép cộng nào được viết lại ở đây.

KHÔNG có cột "Số lượng": ở mức (khoa phòng, tháng) số lượng cộng hộp với chai
với cái nên vô nghĩa — đọc docstring cap_phat_thang_theo_khoa_rows(). Cần số
lượng theo từng vật tư thì dùng report "Cấp phát theo khoa phòng" (mức dòng).

`add_total_row=1` an toàn cho cả ba cột số ở đây, và đó là một tính chất phải
kiểm chứ không phải mặc định: một phiếu xuất chỉ có ĐÚNG MỘT `khoa_phong` và
ĐÚNG MỘT `ngay` trên đầu phiếu, nên mỗi phiếu rơi vào đúng một cặp (khoa,
tháng) — các phép đếm phân biệt ở đây PHÂN HOẠCH tập phiếu, cộng lại ra đúng
tổng số phiếu, không đếm trùng. Cột thứ ba vì vậy phải mang nhãn "Số dòng vật
tư" chứ không phải "Số mặt hàng" (xem chú thích tại COLUMNS).

Mặc định khoảng ngày = 12 THÁNG gần nhất (không phải tháng hiện tại như báo
cáo N-X-T): một báo cáo "theo từng tháng" mà mặc định chỉ một tháng thì không
cho thấy điều nó tồn tại để cho thấy. Tính lại mỗi lần chạy, không hardcode
một mốc cố định (bài học "date rot" ghi trong test_kho_reports.py).

Quyền hạn: `ref_doctype=Customer Stock Ledger Entry`, `roles=System Manager/
Sales Manager/Sales User` (xem setup/install_kho_desk_reports.py). Role
`Customer` KHÔNG có DocPerm nào trên doctype này — report liệt kê cấp phát của
MỌI khách hàng, cùng hạn chế VĐ-10 như các report desk khác trong module.
"""

import frappe

from miyano_portal.kho import desk_reports

SO_THANG_MAC_DINH = 12

COLUMNS = [
	{"label": "Khách hàng", "fieldname": "customer_name", "fieldtype": "Data", "width": 180},
	{"label": "Kho", "fieldname": "ten_kho", "fieldtype": "Data", "width": 140},
	{"label": "Khoa phòng", "fieldname": "khoa_phong", "fieldtype": "Data", "width": 170},
	{"label": "Tháng", "fieldname": "nhan_thang", "fieldtype": "Data", "width": 90},
	{"label": "Số phiếu", "fieldname": "so_phieu", "fieldtype": "Int", "width": 90},
	# Nhãn "Số DÒNG vật tư", không phải "Số mặt hàng": `add_total_row` của
	# Frappe cộng MỌI cột số và không cho tắt riêng cột nào (xem
	# frappe/desk/query_report.py::add_total_row — chỉ xét fieldtype). Trong
	# một dòng thì hai cách đọc trùng nhau, nhưng ở dòng Total thì "số mặt
	# hàng" là SAI: một vật tư cấp cho hai khoa bị cộng hai lần. Số dòng thì
	# cộng được thật, nên nhãn phải là cái cộng được.
	{"label": "Số dòng vật tư", "fieldname": "so_mat_hang", "fieldtype": "Int", "width": 120},
	{"label": "Giá trị cấp phát", "fieldname": "gia_tri", "fieldtype": "Currency", "width": 150},
]


def execute(filters=None):
	filters = frappe._dict(filters or {})
	today = frappe.utils.getdate(frappe.utils.today())
	tu_ngay = filters.get("tu_ngay") or frappe.utils.get_first_day(
		frappe.utils.add_months(today, -(SO_THANG_MAC_DINH - 1))
	)
	den_ngay = filters.get("den_ngay") or frappe.utils.get_last_day(today)
	data = desk_reports.cap_phat_thang_theo_khoa_rows(
		customer=filters.get("customer") or None, tu_ngay=tu_ngay, den_ngay=den_ngay,
	)
	return COLUMNS, data
