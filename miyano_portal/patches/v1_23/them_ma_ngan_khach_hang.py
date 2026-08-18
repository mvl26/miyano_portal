"""Thêm `Customer.custom_ma_ngan` — mã ngắn của bệnh viện.

Dùng làm phần đầu tên phiếu `Đề nghị mua` (spec §6.1). BẮT BUỘC với khách
dùng cổng, nhưng KHÔNG đặt `reqd=1` trên field: hàng trăm Customer nội bộ
không dùng cổng sẽ không lưu được nữa. Chốt bắt buộc nằm ở
`Portal Member.validate` (Task 4) — kiểm đúng lúc bật tính năng cho một
bệnh viện, không phải lúc nhân viên bấm gửi.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_field


def execute():
	create_custom_field("Customer", {
		"fieldname": "custom_ma_ngan",
		"label": "Mã ngắn (cổng khách)",
		"fieldtype": "Data",
		"length": 10,
		"unique": 1,
		"insert_after": "customer_name",
		"description": "Chữ hoa không dấu, ví dụ BM. Dùng làm phần đầu mã đề nghị mua.",
	})
