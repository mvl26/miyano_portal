import frappe

no_cache = 1


def get_context(context):
    if frappe.session.user != "Guest":
        frappe.local.flags.redirect_location = "/portal"
        raise frappe.Redirect
    context.no_header = True
    context.title = "Đăng nhập — Cổng khách hàng Miyano"
    return context
