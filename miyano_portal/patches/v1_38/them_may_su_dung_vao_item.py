"""Thêm bảng `Item.custom_may_su_dung` — các DÒNG MÁY dùng được mặt hàng.

Chủ đầu tư 28/09/2026: *"thêm cho anh table máy sử dụng nữa, filter also"* —
cùng đợt với nhóm vật tư (v1_36) và nhà cung cấp (v1_37); màn `/portal/
dat-hang` lọc hàng theo máy.

Trỏ tới `Dong May` (danh mục dùng chung), KHÔNG tới `Customer Equipment` (máy
cụ thể của từng bệnh viện) — xem docstring `DongMay`.

Đặt thành một phần riêng ở cuối tab Details (sau bảng đơn vị tính), không
chen vào cột trên cùng cạnh `item_group`.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	# Patch nằm ở `post_model_sync` nên hai doctype đã đồng bộ sẵn; nạp lại
	# cho chắc khi patch bị chạy lẻ (`bench execute`).
	frappe.reload_doc("miyano_portal", "doctype", "dong_may")
	frappe.reload_doc("miyano_portal", "doctype", "item_may_su_dung")
	create_custom_fields({
		"Item": [
			{
				"fieldname": "custom_sec_may_su_dung",
				"label": "Máy sử dụng",
				"fieldtype": "Section Break",
				"insert_after": "uoms",
			},
			{
				"fieldname": "custom_may_su_dung",
				"label": "Máy sử dụng được mặt hàng này",
				"fieldtype": "Table",
				"options": "Item May Su Dung",
				"insert_after": "custom_sec_may_su_dung",
			},
		],
	}, ignore_validate=True)
