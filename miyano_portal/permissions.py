import frappe
from miyano_portal.portal_context import get_allowed_customers


def _is_restricted_user(user: str) -> bool:
    """Only Website Users are constrained by these portal-scoped hooks."""
    return frappe.get_cached_value("User", user, "user_type") == "Website User"


def _customer_condition(table: str, user: str | None) -> str:
    user = user or frappe.session.user
    if not _is_restricted_user(user):
        return ""
    customers = get_allowed_customers(user)
    if not customers:
        return "1=0"
    joined = ", ".join(frappe.db.escape(c) for c in customers)
    return f"`tab{table}`.`customer` in ({joined})"


def _has_customer_permission(doc, user=None):
    user = user or frappe.session.user
    if not _is_restricted_user(user):
        return True
    return doc.get("customer") in get_allowed_customers(user)


def sales_query(user=None):
    return _customer_condition("Sales Order", user)


def sales_has_permission(doc, ptype=None, user=None):
    return _has_customer_permission(doc, user)


def delivery_query(user=None):
    return _customer_condition("Delivery Note", user)


def invoice_query(user=None):
    return _customer_condition("Sales Invoice", user)


def blanket_query(user=None):
    return _customer_condition("Blanket Order", user)


def generic_has_permission(doc, ptype=None, user=None):
    return _has_customer_permission(doc, user)
