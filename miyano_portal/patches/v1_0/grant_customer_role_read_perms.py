from frappe.permissions import add_permission


def execute():
    """Grant the standard "Customer" role base read access on the doctypes
    the client portal lists via ``frappe.get_list``.

    Without a base DocPerm, ``frappe.get_list`` raises ``PermissionError``
    before the ``permission_query_conditions``/``has_permission`` hooks in
    ``miyano_portal.permissions`` (Task 5) ever get a chance to scope the
    result set to the caller's own customer. Read-only, permlevel 0 — the
    Task 5 hooks are what actually restrict rows to the caller's customer.
    """
    for doctype in ("Sales Order", "Delivery Note", "Sales Invoice"):
        add_permission(doctype, "Customer", 0, "read")
