import frappe
from frappe.model.document import Document

from miyano_portal.permissions import _is_restricted_user
from miyano_portal.portal_context import get_allowed_khos


class CustomerStockIssueItem(Document):
	def has_permission(self, permtype="read", *, debug=False, user=None):
		"""Ghi đè has_permission() ở mức CLASS — xem giải thích đầy đủ trong
		CustomerStockReceiptItem.has_permission() (cùng lý do, cùng cơ chế,
		chỉ khác doctype cha: Customer Stock Issue thay vì Customer Stock
		Receipt)."""
		if self.flags.ignore_permissions:
			return True
		user = user or frappe.session.user
		if not _is_restricted_user(user):
			return super().has_permission(permtype, debug=debug, user=user)
		parent = self.get("parent")
		if not parent:
			return False
		kho = frappe.db.get_value("Customer Stock Issue", parent, "kho")
		return bool(kho) and kho in get_allowed_khos(user)
