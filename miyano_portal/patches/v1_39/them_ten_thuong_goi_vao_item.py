"""Thêm bảng `Item.custom_ten_thuong_goi` — tên thường gọi theo từng khách hàng.

Chủ đầu tư 02/10/2026: ở màn `/portal/dat-hang`, ô tìm vật tư đổi thành tìm
theo TÊN XUẤT HOÁ ĐƠN (`item_name` — đúng tên hoá đơn điện tử in ra, xem
`erpnext/einvoice/builder.py`), và thêm ô tìm theo TÊN THƯỜNG GỌI; trên Item có
bảng hai cột: tên thường gọi (chữ) + khách hàng (Link `Customer`).

Theo từng khách hàng vì cùng một mặt hàng mỗi bệnh viện gọi một kiểu, và tên
một bệnh viện tự đặt không được lộ sang bệnh viện khác.

Đặt thành phần riêng ngay sau phần "Máy sử dụng" (v1_38).
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	frappe.reload_doc("miyano_portal", "doctype", "item_ten_thuong_goi")
	create_custom_fields({
		"Item": [
			{
				"fieldname": "custom_sec_ten_thuong_goi",
				"label": "Tên thường gọi theo khách hàng",
				"fieldtype": "Section Break",
				"insert_after": "custom_may_su_dung",
			},
			{
				"fieldname": "custom_ten_thuong_goi",
				"label": "Tên thường gọi",
				"fieldtype": "Table",
				"options": "Item Ten Thuong Goi",
				"insert_after": "custom_sec_ten_thuong_goi",
				"description": "Tên mà từng bệnh viện quen gọi mặt hàng này. Bệnh viện chỉ thấy và tìm được tên của chính mình trên cổng.",
			},
		],
	}, ignore_validate=True)
