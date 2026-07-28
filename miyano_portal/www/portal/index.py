import frappe

no_cache = 1


def get_context(context):
    # Auth gate: khách vãng lai → chuyển sang trang đăng nhập; tài khoản không có
    # vai trò Customer → chặn truy cập cổng khách hàng.
    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/portal/login"
        raise frappe.Redirect
    if "Customer" not in frappe.get_roles():
        frappe.throw("Tài khoản không có quyền truy cập cổng khách hàng.", frappe.PermissionError)

    context.no_header = True
    context.no_breadcrumbs = True
    context.no_sidebar = True
    context.title = "Cổng khách hàng Miyano"

    # SPA Vue chạy trên trang website (không có desk `frappe.call`), nên mọi lời
    # gọi API whitelist phải dùng fetch() tới /api/method/<method> kèm CSRF token.
    # Bơm token vào <meta name="csrf-token"> để api.js đọc lại.
    try:
        context.csrf_token = frappe.sessions.get_csrf_token()
    except Exception:
        context.csrf_token = ""

    # Cache-busting cho index.js/index.css đã build: URL asset (index.js/index.css)
    # không đổi giữa các lần deploy nên trình duyệt/CDN sẽ giữ bản cũ. Dùng version
    # app (ổn định, chỉ đổi khi release); fallback timestamp nếu tra cứu lỗi.
    try:
        context.build_version = frappe.get_attr("miyano_portal.__version__")
    except Exception:
        context.build_version = frappe.utils.now()

    return context
