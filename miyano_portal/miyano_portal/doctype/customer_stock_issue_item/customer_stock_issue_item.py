from frappe.model.document import Document

from miyano_portal.kho.permissions import voucher_item_readable


class CustomerStockIssueItem(Document):
	def has_permission(self, permtype="read", *, debug=False, user=None):
		"""Ghi đè has_permission() ở mức CLASS — xem giải thích đầy đủ trong
		CustomerStockReceiptItem.has_permission() (cùng lý do, cùng cơ chế,
		chỉ khác doctype cha: Customer Stock Issue thay vì Customer Stock
		Receipt). Bao gồm cả vá FINDING 4 (chỉ thu hẹp permtype="read", mọi
		permtype khác giao lại cho Frappe mặc định) và guard
		ignore_permissions kiểm trước tiên, tách biệt khỏi nhánh permtype.
		"""
		if self.flags.ignore_permissions:
			return True
		if permtype != "read":
			return super().has_permission(permtype, debug=debug, user=user)
		if not super().has_permission(permtype, debug=debug, user=user):
			return False
		return voucher_item_readable(self, permtype, user=user)
