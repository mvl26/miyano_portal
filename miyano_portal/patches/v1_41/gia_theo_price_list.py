"""Giá theo Price List của khách (spec 2026-10-09 §6).

Phần CẤU TRÚC ở `them_truong()`. Phần DỮ LIỆU (bảng giá riêng, chép giá hợp
đồng, đóng dấu đơn đang dở) ở `chuyen_du_lieu()`.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def them_truong():
	# Hai doctype có thêm lựa chọn / trường mới trong .json: site cũ chỉ thấy
	# sau khi nạp lại, nên reload ở đây thay vì chờ `bench migrate`.
	frappe.reload_doc("miyano_portal", "doctype", "portal_de_xuat_mua_item")
	frappe.reload_doc("miyano_portal", "doctype", "portal_de_xuat_mua")
	create_custom_fields({
		"Sales Order Item": [
			{
				"fieldname": "custom_nguon_gia", "label": "Nguồn giá",
				"fieldtype": "Select", "options": "\nBảng giá\nBáo giá",
				"insert_after": "rate", "read_only": 1, "no_copy": 1,
				"in_list_view": 1, "columns": 1,
				"description": "Bảng giá: đơn giá lấy từ Price List của khách. Báo giá: Miyano điền, ghi vào Price List khi khách đồng ý.",
			},
			{
				"fieldname": "custom_gia_khach_dong_y", "label": "Giá khách đã đồng ý",
				"fieldtype": "Currency", "insert_after": "custom_nguon_gia",
				"read_only": 1, "no_copy": 1,
			},
		],
	}, ignore_validate=True)

	# `custom_loai_don` là Custom Field (không có Property Setter), nên lựa chọn
	# nằm ở `options` của chính nó. Giữ "Theo HĐNT" cho đơn cũ.
	ten = frappe.db.get_value(
		"Custom Field", {"dt": "Sales Order", "fieldname": "custom_loai_don"}, "name"
	)
	if ten:
		lua_chon = (frappe.db.get_value("Custom Field", ten, "options") or "").split("\n")
		if "Theo bảng giá" not in lua_chon:
			lua_chon.append("Theo bảng giá")
			frappe.db.set_value("Custom Field", ten, "options", "\n".join(lua_chon))
			frappe.clear_cache(doctype="Sales Order")


def chuyen_du_lieu():
	pass


def execute():
	them_truong()
	chuyen_du_lieu()
