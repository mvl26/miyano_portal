"""Report desk "Tiêu thụ và đề xuất dự trù" — US-E5.5 (UC-49, UC-50).

(Cùng lưu ý I4 đã ghi ở đối_soát_giao_nhận.py: tên KHÔNG dùng en-dash "–".
Tên cũng KHÔNG dùng "&" — brief gốc viết "Tiêu thụ & đề xuất dự trù", nhưng
"&" trong docname/URL Desk report mang cùng lớp rủi ro gõ nhầm/encode như
en-dash đã từng gây lỗi thật ở report này (xem lịch sử "Đối soát giao –
nhận"), nên đổi sang "và" — chữ thường, không dấu câu đặc biệt nào.)

Toàn bộ số học sống ở `miyano_portal.kho.desk_reports.tieu_thu_de_xuat_rows()`,
gọi lại `kho.dutru` (ADU/ROP/SL đề xuất) cho từng (kho, vật tư) — không viết
lại phép tính lần thứ hai.

CỐ Ý KHÔNG áp BR-P3 (bộ lọc ẩn "chưa thiết lập + chưa đủ dữ liệu" của màn
cảnh báo phía khách hàng) — đây là báo cáo phân tích NỘI BỘ, sales cần thấy
đủ mọi vật tư để lên kế hoạch mua/tồn.

Quyền hạn: `ref_doctype=Customer Warehouse Item`, `roles=System Manager/
Sales Manager/Sales User` (xem setup/install_kho_desk_reports.py). Role
`Customer` KHÔNG có DocPerm nào trên doctype này — report liệt kê tiêu thụ
của MỌI khách hàng, VĐ-10: chỉ triển khai cho khách đã ký điều khoản chia
sẻ dữ liệu, quản lý bằng quy trình mở kho, không chặn bằng code.
"""

import frappe

from miyano_portal.kho import desk_reports

COLUMNS = [
	{"label": "Khách hàng", "fieldname": "customer_name", "fieldtype": "Data", "width": 200},
	{"label": "Vật tư", "fieldname": "ten_vat_tu", "fieldtype": "Data", "width": 200},
	{"label": "ĐVT", "fieldname": "dvt", "fieldtype": "Data", "width": 80},
	{"label": "Tồn", "fieldname": "ton", "fieldtype": "Float", "precision": 2, "width": 90},
	{"label": "ADU 30 ngày", "fieldname": "adu_30", "fieldtype": "Float", "precision": 2, "width": 100},
	{"label": "ADU (kỳ chuẩn)", "fieldname": "adu_90", "fieldtype": "Float", "precision": 2, "width": 110},
	{"label": "Ngày phủ tồn", "fieldname": "ngay_phu", "fieldtype": "Data", "width": 100},
	{"label": "Ngày dự kiến hết", "fieldname": "ngay_du_kien_het", "fieldtype": "Date", "width": 120},
	{"label": "Điểm đặt lại (ROP)", "fieldname": "rop", "fieldtype": "Float", "precision": 2, "width": 120},
	{"label": "Tồn tối đa (max)", "fieldname": "max", "fieldtype": "Float", "precision": 2, "width": 110},
	{"label": "SL đề xuất", "fieldname": "sl_de_xuat", "fieldtype": "Float", "precision": 2, "width": 100},
	{"label": "Vật tư (docname)", "fieldname": "vat_tu", "fieldtype": "Link", "options": "Customer Warehouse Item", "width": 110},
]


def execute(filters=None):
	filters = frappe._dict(filters or {})
	data = desk_reports.tieu_thu_de_xuat_rows(
		customer=filters.get("customer") or None,
		nhom=filters.get("nhom") or None,
	)
	return COLUMNS, data
