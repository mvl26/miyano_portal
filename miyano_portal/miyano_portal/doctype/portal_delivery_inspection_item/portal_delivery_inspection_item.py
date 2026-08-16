# Copyright (c) 2026, Miyano and contributors
# For license information, please see license.txt
"""Dòng của biên bản kiểm hàng.

CỐ Ý **không** kế thừa `kho.voucher_item.VoucherItemBase`: lớp đó thu hẹp
quyền theo field `kho` (`kho.permissions.voucher_item_readable`), còn bảng này
không có `kho` và không được có — biên bản kiểm hàng phải chạy cho cả khách
chưa mở kho (spec 2026-08-16 §4.4). Thay vào đó là một override CÙNG HÌNH DẠNG
nhưng soi theo `customer` của chứng từ cha.

Đọc docstring `VoucherItemBase` trước khi tin lớp này đang bảo vệ cái gì: cũng
như ở đó, cơ chế cách ly CHÍNH là role `Customer` không có DocPerm nào trên
doctype cha (`Portal Delivery Inspection`, xem JSON). Override này là LỚP PHÒNG
THỦ THỨ HAI, chỉ sống lại nếu ai đó cấp lại grant nền đó.
"""

import frappe
from frappe.model.document import Document

from miyano_portal.permissions import _is_restricted_user
from miyano_portal.portal_context import get_allowed_customers


class PortalDeliveryInspectionItem(Document):
	def has_permission(self, permtype="read", *, debug=False, user=None):
		# Kiểm cờ TRƯỚC và tách khỏi nhánh permtype — cùng lý do đã ghi ở
		# VoucherItemBase: để `super()` xử lý cờ rồi mới lọc tiếp sẽ làm
		# `insert(ignore_permissions=True)` của seed/test mất tác dụng.
		if self.flags.ignore_permissions:
			return True
		# CHỈ thu hẹp "read"/"print". Mọi permtype khác giao lại cho Frappe —
		# thu hẹp rộng hơn là đúng lỗi FINDING 4 mà VoucherItemBase đã dính.
		if permtype not in ("read", "print"):
			return super().has_permission(permtype, debug=debug, user=user)
		if not super().has_permission(permtype, debug=debug, user=user):
			return False

		user = user or frappe.session.user
		if not _is_restricted_user(user):
			return True
		customer = frappe.db.get_value(
			"Portal Delivery Inspection", self.parent, "customer"
		) if self.parent else None
		return bool(customer) and customer in get_allowed_customers(user)
