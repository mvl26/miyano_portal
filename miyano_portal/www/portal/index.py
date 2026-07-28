import frappe

no_cache = 1


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/portal/login"
        raise frappe.Redirect
    if "Customer" not in frappe.get_roles():
        frappe.throw("Tài khoản không có quyền truy cập cổng khách hàng.", frappe.PermissionError)
    context.no_header = True
    context.title = "Cổng khách hàng Miyano"
    return context
