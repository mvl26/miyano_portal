"""Endpoint tên mặt hàng của cổng khách hàng — xem `miyano_portal/ten_hang.py`."""

import frappe

from miyano_portal import ten_hang
from miyano_portal.portal_context import get_portal_customer


@frappe.whitelist()
def portal_ten_hang(item_codes=None) -> dict:
	"""Tên xuất hoá đơn và tên thường gọi của các mã hàng đang hiện trên màn.

	Khách suy từ phiên đăng nhập, không nhận từ tham số — tên thường gọi của
	bệnh viện khác không bao giờ đi qua cửa này. Trả
	`{item_code: {item_name, ten_thuong_goi: [...]}}`.
	"""
	customer = get_portal_customer()
	ma = frappe.parse_json(item_codes) if isinstance(item_codes, str) else (item_codes or [])
	if not isinstance(ma, (list, tuple)):
		frappe.throw("Danh sách mã hàng không hợp lệ.", frappe.ValidationError)
	if len(ma) > ten_hang.SO_MA_TOI_DA:
		frappe.throw(
			f"Chỉ tra được tối đa {ten_hang.SO_MA_TOI_DA} mã hàng một lần.",
			frappe.ValidationError,
		)
	return ten_hang.thong_tin_ten_hang(customer, [str(m) for m in ma if m])
