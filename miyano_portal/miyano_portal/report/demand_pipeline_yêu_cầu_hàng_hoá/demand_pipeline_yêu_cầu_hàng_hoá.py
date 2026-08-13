"""Report desk "Demand pipeline yêu cầu hàng hoá" — US-E6.6/UC-53. Toàn bộ
số học sống ở `miyano_portal.demand_pipeline`; file này chỉ khai cột/filter
và ghép `report_summary` (bốn thẻ KPI, trong đó có tỷ lệ chuyển thành đơn và
nhóm Định kỳ tách riêng — NL-11.7).

Quyền hạn nằm ở Report doctype (roles=Sales Manager/Sales User/Purchase
User, KHÔNG Customer — xem setup/install_e6_desk_reports.py); xem docstring
đầu demand_pipeline.py.
"""

import frappe

from miyano_portal import demand_pipeline

COLUMNS = [
	{"label": "Mã yêu cầu", "fieldname": "name", "fieldtype": "Link", "options": "Portal Item Request", "width": 110},
	{"label": "Ngày gửi", "fieldname": "creation", "fieldtype": "Datetime", "width": 150},
	{"label": "Khách hàng", "fieldname": "customer_name", "fieldtype": "Data", "width": 200},
	{"label": "Loại yêu cầu", "fieldname": "loai", "fieldtype": "Data", "width": 150},
	{"label": "Tên hàng hoá", "fieldname": "ten_hang", "fieldtype": "Data", "width": 200},
	{"label": "Tần suất", "fieldname": "tan_suat", "fieldtype": "Data", "width": 90},
	{"label": "Trạng thái", "fieldname": "trang_thai", "fieldtype": "Data", "width": 150},
	{"label": "Thời gian xử lý (giờ)", "fieldname": "thoi_gian_xu_ly_gio", "fieldtype": "Float", "precision": 1, "width": 140},
	{"label": "Đã chuyển thành đơn", "fieldname": "da_chuyen_don", "fieldtype": "Check", "width": 130},
	{"label": "Đơn liên kết", "fieldname": "don_lien_ket", "fieldtype": "Link", "options": "Sales Order", "width": 140},
]


def execute(filters=None):
	filters = frappe._dict(filters or {})
	rows = demand_pipeline.yeu_cau_rows(
		customer=filters.get("customer") or None,
		loai=filters.get("loai") or None,
		tan_suat=filters.get("tan_suat") or None,
		trang_thai=filters.get("trang_thai") or None,
		tu_ngay=filters.get("tu_ngay") or None,
		den_ngay=filters.get("den_ngay") or None,
	)
	tt = demand_pipeline.tom_tat(rows)
	report_summary = [
		{"value": tt["tong"], "label": "Tổng yêu cầu", "datatype": "Int"},
		{
			"value": tt["ty_le_chuyen_don"] if tt["ty_le_chuyen_don"] is not None else 0,
			"label": "Tỷ lệ chuyển thành đơn (%)", "datatype": "Float",
		},
		{
			"value": (
				tt["thoi_gian_xu_ly_binh_quan_gio"]
				if tt["thoi_gian_xu_ly_binh_quan_gio"] is not None else 0
			),
			"label": "Thời gian xử lý bình quân (giờ)", "datatype": "Float",
		},
		{"value": tt["dinh_ky_tong"], "label": "Trong đó Định kỳ", "datatype": "Int"},
		{
			"value": (
				tt["dinh_ky_ty_le_chuyen_don"]
				if tt["dinh_ky_ty_le_chuyen_don"] is not None else 0
			),
			"label": "Định kỳ — tỷ lệ chuyển thành đơn (%)", "datatype": "Float",
		},
	]
	return COLUMNS, rows, None, None, report_summary
