"""Cách ly dữ liệu kho giữa các khách hàng.

Kho Khách Hàng lọc theo `customer`; năm doctype còn lại đều mang field `kho`
nên lọc theo danh sách kho mà user được phép thấy.

Chỉ Website User bị ràng buộc — nhân viên Miyano ngồi desk thấy toàn bộ, giống
cơ chế đã dùng cho Sales Order ở miyano_portal/permissions.py.
"""

import frappe

from miyano_portal.permissions import _is_restricted_user
from miyano_portal.portal_context import get_allowed_customers, get_allowed_khos


def _kho_condition(table: str, user: str | None) -> str:
	user = user or frappe.session.user
	if not _is_restricted_user(user):
		return ""
	khos = get_allowed_khos(user)
	if not khos:
		return "1=0"
	joined = ", ".join(frappe.db.escape(k) for k in khos)
	return f"`tab{table}`.`kho` in ({joined})"


def kho_query(user=None) -> str:
	user = user or frappe.session.user
	if not _is_restricted_user(user):
		return ""
	customers = get_allowed_customers(user)
	if not customers:
		return "1=0"
	joined = ", ".join(frappe.db.escape(c) for c in customers)
	return f"`tabCustomer Warehouse`.`customer` in ({joined})"


def vat_tu_query(user=None) -> str:
	return _kho_condition("Customer Warehouse Item", user)


def receipt_query(user=None) -> str:
	return _kho_condition("Customer Stock Receipt", user)


def issue_query(user=None) -> str:
	return _kho_condition("Customer Stock Issue", user)


def sle_query(user=None) -> str:
	return _kho_condition("Customer Stock Ledger Entry", user)


def lot_query(user=None) -> str:
	return _kho_condition("Customer Stock Lot Balance", user)


def kho_has_permission(doc, ptype=None, user=None) -> bool:
	user = user or frappe.session.user
	if not _is_restricted_user(user):
		return True
	return doc.get("customer") in get_allowed_customers(user)


def kho_child_has_permission(doc, ptype=None, user=None) -> bool:
	user = user or frappe.session.user
	if not _is_restricted_user(user):
		return True
	return doc.get("kho") in get_allowed_khos(user)
