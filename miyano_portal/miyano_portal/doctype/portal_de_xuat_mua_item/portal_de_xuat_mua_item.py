"""Dòng hàng của `Portal De Xuat Mua`.

CỐ Ý **không** kế thừa `kho.voucher_item.VoucherItemBase`: lớp đó thu hẹp
quyền theo field `kho`, còn bảng này không có `kho` — cha (`Portal De Xuat
Mua`) mang `customer` trực tiếp. Override dưới đây CÙNG HÌNH DẠNG với
`portal_delivery_inspection_item.py::PortalDeliveryInspectionItem`, chỉ đổi
tên doctype cha.

Đọc docstring `VoucherItemBase` trước khi tin lớp này đang bảo vệ cái gì:
cơ chế cách ly CHÍNH là `Portal De Xuat Mua` không có DocPerm nào (§5.1, xem
JSON — mảng `permissions` rỗng). Override này là LỚP PHÒNG THỦ THỨ HAI, chỉ
sống lại nếu ai đó cấp DocPerm cho doctype cha.
"""

import frappe
from frappe.model.document import Document

from miyano_portal.permissions import _is_restricted_user
from miyano_portal.portal_context import get_allowed_customers


class PortalDeXuatMuaItem(Document):
	def has_permission(self, permtype="read", *, debug=False, user=None):
		# Kiểm cờ TRƯỚC và tách khỏi nhánh permtype — để `super()` xử lý cờ
		# rồi mới lọc tiếp sẽ làm `insert(ignore_permissions=True)` của
		# seed/test mất tác dụng (cùng lý do đã ghi ở VoucherItemBase).
		if self.flags.ignore_permissions:
			return True
		# CHỈ thu hẹp "read"/"print". Mọi permtype khác giao lại cho Frappe.
		if permtype not in ("read", "print"):
			return super().has_permission(permtype, debug=debug, user=user)
		if not super().has_permission(permtype, debug=debug, user=user):
			return False

		user = user or frappe.session.user
		if not _is_restricted_user(user):
			return True
		customer = frappe.db.get_value(
			"Portal De Xuat Mua", self.parent, "customer"
		) if self.parent else None
		return bool(customer) and customer in get_allowed_customers(user)
