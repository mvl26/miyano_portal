"""Tra tên hợp đồng khung (Blanket Order) cho các bộ test cũ.

Endpoint `portal_contracts` đã gỡ (spec 2026-10-09 §7): cổng không còn màn nào
hiện hợp đồng. Nhiều bộ test vẫn cần TÊN hợp đồng demo của khách đang đăng nhập
— để sửa dòng `Blanket Order Item` làm fixture, hoặc để truyền vào tham số
`contract` (đã hết tác dụng) của `portal_order_place`. Hàm dưới giữ đúng bộ lọc
và thứ tự mà endpoint cũ dùng, để các bộ test đó lấy đúng hợp đồng như trước.
"""

import frappe

from miyano_portal.portal_context import get_portal_customer


def hop_dong_hieu_luc_dau_tien() -> str:
	"""Tên hợp đồng bán còn hiệu lực hết hạn sớm nhất của khách đang đăng nhập."""
	hom_nay = frappe.utils.today()
	ten = frappe.get_all(
		"Blanket Order",
		filters={
			"customer": get_portal_customer(),
			"blanket_order_type": "Selling",
			"docstatus": 1,
			"from_date": ["<=", hom_nay],
			"to_date": [">=", hom_nay],
		},
		order_by="to_date asc",
		pluck="name",
		limit=1,
	)
	if not ten:
		raise AssertionError("Fixture thiếu hợp đồng khung còn hiệu lực cho khách đang đăng nhập.")
	return ten[0]
