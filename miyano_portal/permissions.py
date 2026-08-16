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


def yeu_cau_query(user=None):
    """E6 — `Portal Item Request` mang `customer` trực tiếp (không phải
    `kho`), đúng hình dạng Sales Order/Delivery Note/... ở file này, KHÔNG
    phải hình dạng `kho/permissions.py` (nơi phần lớn doctype lọc theo
    `kho`). Dùng chung `_customer_condition`/`generic_has_permission` thay vì
    viết một bản lọc theo customer thứ hai."""
    return _customer_condition("Portal Item Request", user)


def kiem_hang_query(user=None):
    """Biên bản kiểm hàng mang `customer` trực tiếp — cùng hình dạng
    `Portal Item Request` ngay trên, KHÔNG phải hình dạng kho (`kho/
    permissions.py`, lọc qua field `kho`). Doctype này CỐ Ý không gắn với
    kho: nó phải chạy cho cả khách chưa mở kho (spec kiểm hàng §4.4)."""
    return _customer_condition("Portal Delivery Inspection", user)


def kiem_hang_item_query(user=None) -> str:
    """Bảng con của biên bản kiểm hàng — không mang `customer` riêng, lọc qua
    parent. Cùng khuôn `kho/permissions._child_condition()` nhưng nối theo
    `customer` (không phải `kho`), vì cha ở đây mang `customer` trực tiếp."""
    user = user or frappe.session.user
    if not _is_restricted_user(user):
        return ""
    customers = get_allowed_customers(user)
    if not customers:
        return "1=0"
    joined = ", ".join(frappe.db.escape(c) for c in customers)
    return (
        "`tabPortal Delivery Inspection Item`.`parent` in "
        f"(select name from `tabPortal Delivery Inspection` where `customer` in ({joined}))"
    )


def einvoice_query(user=None):
    """E7 — `Fast EInvoice Document` là doctype của MODULE KHÁC (team Dev,
    `apps/erpnext/erpnext/einvoice/`), mảng `permissions` của nó chỉ còn
    `System Manager` (đã kiểm JSON + thực nghiệm
    `frappe.has_permission(..., user=<khách>)` trả `False`) — role `Customer`
    KHÔNG có DocPerm nào trên đây, y hệt tám doctype kho ở
    `kho/permissions.py`. Entry này vì thế "chết có điều kiện" NGAY KHI viết
    (không Website User nào qua nổi vòng kiểm role cơ bản để hook này được
    gọi tới) — giữ lại làm lớp phòng thủ thứ hai, sống lại nếu sau này ai đó
    lỡ cấp DocPerm cho `Customer` trên doctype này. Cổng THẬT đi qua
    `miyano_portal/einvoice.py::resolve()`, luôn bắt đầu từ `Sales Invoice`
    (nơi khách có quyền qua `check_permission`), không bao giờ nhận tên
    `Fast EInvoice Document` trực tiếp từ client."""
    return _customer_condition("Fast EInvoice Document", user)
