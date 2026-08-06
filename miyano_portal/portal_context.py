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


def get_portal_kho(user: str | None = None) -> str:
    """Tên Customer Warehouse của khách đang đăng nhập.

    Mỗi khách đúng một kho, nên hàm này trả về một chuỗi chứ không phải danh
    sách. Mọi endpoint kho đều phải đi qua đây thay vì nhận tên kho từ client.
    """
    customers = get_allowed_customers(user)
    if not customers:
        raise frappe.PermissionError("Tài khoản chưa gắn với khách hàng nào.")
    kho = frappe.db.get_value(
        "Customer Warehouse",
        {"customer": ["in", customers], "active": 1},
        "name",
    )
    if not kho:
        raise frappe.PermissionError(
            "Đơn vị của bạn chưa được mở kho trên cổng. Vui lòng liên hệ "
            "nhân viên kinh doanh Miyano."
        )
    return kho


def get_allowed_khos(user: str | None = None) -> list[str]:
    """Mọi kho mà user được phép thấy. Dùng cho các hook phân quyền."""
    customers = get_allowed_customers(user)
    if not customers:
        return []
    return frappe.get_all(
        "Customer Warehouse", filters={"customer": ["in", customers]}, pluck="name"
    )


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
