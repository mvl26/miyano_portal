import frappe

from miyano_portal.www.portal.index import _build_token

no_cache = 1


def get_context(context):
    if frappe.session.user != "Guest":
        frappe.local.flags.redirect_location = "/portal"
        raise frappe.Redirect
    context.no_header = True
    context.title = "Đăng nhập — Cổng khách hàng Miyano"
    # Trang đăng nhập nạp index.css của cổng (phông tự host) — cùng mốc
    # cache-busting với trang shell, để deploy bản build mới không bị CSS cũ.
    context.build_version = _build_token()
    return context
