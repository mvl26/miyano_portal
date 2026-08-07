import os

import frappe

no_cache = 1


def _build_token() -> str:
    """Mốc cache-busting cho bundle SPA, lấy từ mtime của chính file bundle.

    KHÔNG dùng `miyano_portal.__version__`: đó là hằng số trong code, chỉ đổi khi
    ai đó nhớ bump lúc release. Deploy một bản build mới mà quên bump thì người
    dùng vẫn chạy JS cũ, và triệu chứng nhìn thấy là "đã deploy rồi mà giao diện
    không đổi" — rất khó truy ra nguyên nhân. mtime tự đổi mỗi lần vite build.
    """
    bundle = frappe.get_app_path("miyano_portal", "public", "frontend", "index.js")
    try:
        return str(int(os.path.getmtime(bundle)))
    except OSError:
        # Chưa build bao giờ, hoặc đường dẫn đổi. Thà cache sai còn hơn ném lỗi
        # làm trắng cả trang cổng.
        try:
            return str(frappe.get_attr("miyano_portal.__version__"))
        except Exception:
            return "0"


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

    # Cache-busting: tên file asset không đổi giữa các lần deploy nên trình duyệt
    # và CDN sẽ giữ bản cũ nếu không có tham số này. Xem _build_token().
    context.build_version = _build_token()

    return context
