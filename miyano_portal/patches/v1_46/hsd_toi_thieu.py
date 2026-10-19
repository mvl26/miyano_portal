"""HSD tối thiểu theo yêu cầu khách hàng (spec 2026-10-19).

Chạy lại được: `install.py::after_install` gọi lại mọi patch.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

NHOM_DONG = "custom_sec_hsd_khach"


def them_truong():
	frappe.reload_doc("miyano_portal", "doctype", "portal_de_xuat_mua_item", force=True)
	frappe.reload_doc("miyano_portal", "doctype", "portal_de_xuat_mua", force=True)

	# `no_copy=0` cho yêu cầu (bản sao đơn vẫn mang yêu cầu của khách); riêng
	# ngoại lệ là quyết định của người duyệt trên đúng dòng đó nên `no_copy=1`.
	ngoai_le = {"no_copy": 1, "allow_on_submit": 1}
	create_custom_fields({
		"Sales Order": [
			{
				"fieldname": "custom_hsd_toi_thieu_thang", "label": "HSD tối thiểu (tháng)",
				"fieldtype": "Int", "insert_after": "delivery_date", "no_copy": 0,
				"allow_on_submit": 0,
				"description": "Số tháng hạn sử dụng còn lại tối thiểu khách yêu cầu khi nhận hàng.",
			},
		],
		"Sales Order Item": [
			{
				"fieldname": NHOM_DONG, "label": "Hạn sử dụng khách yêu cầu",
				"fieldtype": "Section Break", "insert_after": "project", "collapsible": 1,
			},
			{
				"fieldname": "custom_hsd_toi_thieu_thang", "label": "HSD tối thiểu (tháng)",
				"fieldtype": "Int", "insert_after": NHOM_DONG, "no_copy": 0,
			},
			{
				"fieldname": "custom_hsd_yeu_cau_den", "label": "HSD yêu cầu đến ngày",
				"fieldtype": "Date", "insert_after": "custom_hsd_toi_thieu_thang",
				"read_only": 1, "no_copy": 0,
			},
			{
				"fieldname": "custom_ket_qua_hsd", "label": "Kết quả HSD", "fieldtype": "Select",
				"options": "\nĐạt\nKhông đạt\nKhông áp dụng",
				"insert_after": "custom_hsd_yeu_cau_den", "read_only": 1, "no_copy": 0,
			},
			{
				"fieldname": "custom_hsd_ton_tot_nhat", "label": "HSD tồn tốt nhất",
				"fieldtype": "Date", "insert_after": "custom_ket_qua_hsd",
				"read_only": 1, "no_copy": 0,
			},
			{
				"fieldname": "custom_ngoai_le_hsd", "label": "Ngoại lệ HSD", "fieldtype": "Check",
				"insert_after": "custom_hsd_ton_tot_nhat", **ngoai_le,
			},
			{
				"fieldname": "custom_ngoai_le_hsd_den", "label": "Ngoại lệ: chấp nhận HSD đến ngày",
				"fieldtype": "Date", "insert_after": "custom_ngoai_le_hsd", **ngoai_le,
			},
			{
				"fieldname": "custom_ngoai_le_ly_do", "label": "Ngoại lệ: lý do",
				"fieldtype": "Small Text", "insert_after": "custom_ngoai_le_hsd_den", **ngoai_le,
			},
			{
				"fieldname": "custom_ngoai_le_boi", "label": "Ngoại lệ: người ghi",
				"fieldtype": "Link", "options": "User", "insert_after": "custom_ngoai_le_ly_do",
				"read_only": 1, **ngoai_le,
			},
			{
				"fieldname": "custom_ngoai_le_luc", "label": "Ngoại lệ: thời điểm ghi",
				"fieldtype": "Datetime", "insert_after": "custom_ngoai_le_boi",
				"read_only": 1, **ngoai_le,
			},
		],
	}, ignore_validate=True)


def execute():
	them_truong()
