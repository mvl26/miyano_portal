import frappe


def get_allowed_customers(user: str | None = None) -> list[str]:
    """Customers linked to the user's Contact (Dynamic Link -> Customer)."""
    user = user or frappe.session.user
    contacts = frappe.get_all(
        "Contact",
        filters={"user": user},
        pluck="name",
    )
    if not contacts:
        return []
    customers = frappe.get_all(
        "Dynamic Link",
        filters={
            "parenttype": "Contact",
            "parent": ["in", contacts],
            "link_doctype": "Customer",
        },
        pluck="link_name",
    )
    return list(dict.fromkeys(customers))


def get_portal_customer(user: str | None = None) -> str:
    customers = get_allowed_customers(user)
    if not customers:
        raise frappe.PermissionError("Tài khoản chưa gắn với khách hàng nào.")
    return customers[0]


def remaining_qty(blanket_order: str, item_code: str) -> float:
    row = frappe.get_all(
        "Blanket Order Item",
        filters={"parent": blanket_order, "item_code": item_code},
        fields=["qty", "ordered_qty"],
        limit=1,
    )
    if not row:
        return 0.0
    return float(row[0].qty or 0) - float(row[0].ordered_qty or 0)
