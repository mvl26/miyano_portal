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

    # SPA chạy trên trang website (extends templates/web.html) nên
    # `frappe.call` (desk helper) không có sẵn — mọi lời gọi API whitelist
    # phải dùng fetch() tới /api/method/<method> kèm CSRF token. Bơm token
    # vào context để index.html render thành biến JS toàn cục.
    try:
        context.csrf_token = frappe.sessions.get_csrf_token()
    except Exception:
        context.csrf_token = ""

    # Cache-busting query string for the built portal.js/portal.css assets:
    # browsers/CDNs otherwise keep serving a stale cached copy after a
    # redeploy since the asset URL itself never changes. Prefer the app
    # version (stable across requests, only changes on release); fall back
    # to a timestamp if that lookup ever fails.
    try:
        context.build_version = frappe.get_attr("miyano_portal.__version__")
    except Exception:
        context.build_version = frappe.utils.now()

    return context
