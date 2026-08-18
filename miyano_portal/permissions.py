import frappe
from miyano_portal.portal_context import dam_bao_xem_duoc, get_allowed_customers, pham_vi_don


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


def _and_conditions(*conds: str) -> str:
    """Nối nhiều điều kiện SQL bằng AND, bỏ qua chuỗi rỗng ("" = "không
    giới hạn thêm gì" — cùng quy ước `_customer_condition` đã dùng)."""
    parts = [c for c in conds if c]
    return " and ".join(f"({c})" for c in parts)


# VÒNG SỬA 2 (review độc lập, C3 — CRITICAL). Cache CẤP TIẾN TRÌNH — không
# phải `None` nghĩa là "chưa biết", `True`/`False` là kết quả đã kiểm. Nhớ
# Ở ĐÂY (không hỏi lại `information_schema`/Redis mỗi lần) vì hàm dùng biến
# này chạy trên MỌI truy vấn Sales Order/Delivery Note/Sales Invoice của
# MỌI Website User — không phải một lần mỗi request.
_cot_khoa_ton_tai: bool | None = None


def _cot_khoa_phong_ton_tai() -> bool:
    """Có cột `Sales Order.custom_khoa_phong` THẬT trong CSDL không.

    Vòng sửa 1 (C2) đưa `custom_khoa_phong` vào `permission_query_
    conditions`/`has_permission` — tức MỌI đường đọc Sales Order/Delivery
    Note/Sales Invoice của MỌI khách cổng, không còn giới hạn ở 21 hàm
    whitelist của `api/portal.py` như trước. Nếu patch `v1_23/them_khoa_
    phong_vao_don_hang` CHƯA THỰC SỰ chạy trên site đích, SQL sinh ra ở đây
    tham chiếu một cột không tồn tại → MariaDB ném lỗi 1054 (unknown
    column) cho MỌI truy vấn đó → CỔNG KHÁCH SẬP HOÀN TOÀN, không phải suy
    giảm êm.

    Đây KHÔNG phải rủi ro lý thuyết: `install_app` trên dự án này từng ghi
    nhận "hoàn thành giả" patch — ghi Patch Log mà không thực sự chạy DDL
    (xem memory `miyano-portal-install-patch-trap`). Một dòng trong
    `patches.txt` không phải bằng chứng cột đã tồn tại.

    Hàm này là LƯỚI AN TOÀN CHO LÚC TRIỂN KHAI, KHÔNG PHẢI giấy phép để
    deploy mà không chạy `bench migrate`: thiếu cột thì MỌI Website User bị
    fail-closed (`"1=0"` — không thấy gì, an toàn) thay vì gặp lỗi CSDL thô,
    nhưng cổng vẫn "câm" với đúng người lẽ ra phải thấy dữ liệu của mình —
    vá triệu chứng, không thay được `bench migrate`."""
    global _cot_khoa_ton_tai
    if _cot_khoa_ton_tai is None:
        _cot_khoa_ton_tai = bool(frappe.db.has_column("Sales Order", "custom_khoa_phong"))
        if not _cot_khoa_ton_tai:
            frappe.log_error(
                title="Thiếu cột Sales Order.custom_khoa_phong",
                message=(
                    "Hook phân quyền theo khoa phòng (miyano_portal.permissions) "
                    "đang chạy trên một site CHƯA có cột Sales Order.custom_"
                    "khoa_phong. Mọi Website User đang bị chặn fail-closed "
                    "(điều kiện 1=0) trên Sales Order/Delivery Note/Sales "
                    "Invoice thay vì gặp lỗi CSDL — cổng \"câm\" thay vì sập, "
                    "nhưng khách không thấy được đơn của chính họ. Chạy `bench "
                    "--site <site> migrate` để thêm cột (patch miyano_portal."
                    "patches.v1_23.them_khoa_phong_vao_don_hang)."
                ),
            )
    return _cot_khoa_ton_tai


def _dieu_kien_khoa_qua_don_cha(
    table: str, child_table: str, link_field: str, escaped_khoa: str
) -> str:
    """Điều kiện SQL: TOÀN BỘ `Sales Order` mà `table` (Delivery Note/Sales
    Invoice) nối tới (qua bảng dòng `child_table`) đều thuộc ĐÚNG khoa
    `escaped_khoa` — khớp CHÍNH XÁC ngữ nghĩa "mơ hồ nhiều khoa = ĐÓNG" của
    `dam_bao_xem_duoc` (một nguồn sự thật, không được lỏng hơn ở tầng hook
    này): có ÍT NHẤT MỘT dòng khớp khoa VÀ KHÔNG dòng nào khác khoa/chưa
    gắn khoa."""
    return (
        f"exists (select 1 from `tab{child_table}` cc "
        f"inner join `tabSales Order` so on so.name = cc.`{link_field}` "
        f"where cc.parent = `tab{table}`.name and so.custom_khoa_phong = {escaped_khoa}) "
        f"and not exists (select 1 from `tab{child_table}` cc2 "
        f"inner join `tabSales Order` so2 on so2.name = cc2.`{link_field}` "
        f"where cc2.parent = `tab{table}`.name and "
        f"(so2.custom_khoa_phong is null or so2.custom_khoa_phong != {escaped_khoa}))"
    )


def _khoa_query_condition(doctype: str, table: str, user: str | None) -> str:
    """Điều kiện SQL bổ sung THEO KHOA cho `permission_query_conditions`,
    dùng LẠI `pham_vi_don()` — KHÔNG viết lại logic khoa ở tầng này (Vòng
    sửa 1, review độc lập, C2 — CRITICAL).

    CHỈ áp cho ba doctype role `Customer` có DocPerm read TRỰC TIẾP (patch
    `v1_0/grant_customer_role_read_perms.py` — Sales Order/Delivery Note/
    Sales Invoice): các hook này vì thế là TẦNG PHÒNG THỦ ĐẦU TIÊN cho mọi
    đường đọc KHÔNG qua 21 hàm whitelist của `api/portal.py`
    (`frappe.client.get_list`/`get_value`, `frappe.desk.reportview`,
    `/printview`, REST v1/v2, `search_guard.client_get_list`/`client_get`
    khi doctype không phải bảng con) — KHÁC HẲN vai trò "lớp phòng thủ thứ
    hai, chết có điều kiện" mà khối comment `has_permission` trong
    `hooks.py` mô tả cho tám doctype kho (những doctype đó KHÔNG có DocPerm
    nào cho `Customer` nên hook tương ứng không bao giờ được framework gọi
    tới — Sales Order/Delivery Note/Sales Invoice thì NGƯỢC LẠI, luôn được
    gọi cho mọi Website User).

    Trước bản vá này, ba hàm dùng hàm này chỉ lọc theo `customer`
    (`_customer_condition`) — một nhân viên khoa gọi thẳng kênh trên vẫn
    thấy TOÀN BỘ đơn của MỌI khoa trong bệnh viện, kèm tổng tiền."""
    user = user or frappe.session.user
    if not _is_restricted_user(user):
        return ""
    if not _cot_khoa_phong_ton_tai():
        # Vòng sửa 2 (C3) — lưới an toàn triển khai, xem docstring hàm đó.
        return "1=0"
    try:
        pham_vi = pham_vi_don(user)
    except frappe.PermissionError:
        # Fail-closed — cùng nguyên tắc `pham_vi_don()` đã lập (Nhân viên
        # khoa `active=1` nhưng chưa gán khoa): không xác định được phạm vi
        # thì KHÔNG được coi là "không giới hạn".
        return "1=0"
    if not pham_vi:
        return ""
    khoa = pham_vi["custom_khoa_phong"]
    escaped = frappe.db.escape(khoa)
    if doctype == "Sales Order":
        return f"`tab{table}`.`custom_khoa_phong` = {escaped}"
    if doctype == "Delivery Note":
        return _dieu_kien_khoa_qua_don_cha(table, "Delivery Note Item", "against_sales_order", escaped)
    if doctype == "Sales Invoice":
        return _dieu_kien_khoa_qua_don_cha(table, "Sales Invoice Item", "sales_order", escaped)
    return ""


def _khoa_ok_doc(doctype: str, name: str, user: str | None = None) -> bool:
    """`True` = KHÔNG bị chặn theo khoa. Vỏ bọc exception->bool quanh
    `dam_bao_xem_duoc` (Vòng sửa 1, C2) — `has_permission` hook PHẢI trả
    bool, không được ném; logic derive-đơn-cha vẫn sống DUY NHẤT trong
    `dam_bao_xem_duoc`, không viết lại ở đây."""
    user = user or frappe.session.user
    if not _is_restricted_user(user):
        return True
    if not _cot_khoa_phong_ton_tai():
        # Vòng sửa 2 (C3) — cùng lưới an toàn với `_khoa_query_condition`,
        # xem docstring `_cot_khoa_phong_ton_tai`. `dam_bao_xem_duoc` bên
        # dưới tự đọc thẳng cột này qua `frappe.db.get_value`/`sql` — không
        # chặn Ở ĐÂY thì lỗi CSDL thô sẽ lộ ra đúng chỗ hàm này định che.
        return False
    try:
        dam_bao_xem_duoc(doctype, name, user=user)
        return True
    except frappe.PermissionError:
        return False


def sales_query(user=None):
    return _and_conditions(
        _customer_condition("Sales Order", user),
        _khoa_query_condition("Sales Order", "Sales Order", user),
    )


def sales_has_permission(doc, ptype=None, user=None):
    if not _has_customer_permission(doc, user):
        return False
    return _khoa_ok_doc("Sales Order", doc.get("name"), user)


def delivery_query(user=None):
    return _and_conditions(
        _customer_condition("Delivery Note", user),
        _khoa_query_condition("Delivery Note", "Delivery Note", user),
    )


def invoice_query(user=None):
    return _and_conditions(
        _customer_condition("Sales Invoice", user),
        _khoa_query_condition("Sales Invoice", "Sales Invoice", user),
    )


def blanket_query(user=None):
    return _customer_condition("Blanket Order", user)


def generic_has_permission(doc, ptype=None, user=None):
    if not _has_customer_permission(doc, user):
        return False
    # Vòng sửa 1 (C2) — CHỈ Delivery Note/Sales Invoice có khoa (quy về đơn
    # cha). Blanket Order/Portal Item Request/Portal Delivery Inspection/
    # Fast EInvoice Document dùng CHUNG hàm này nhưng KHÔNG có khái niệm
    # khoa phòng ở tầng này (hợp đồng khung cấp bệnh viện; ba doctype còn
    # lại ngoài phạm vi review vòng sửa 1 — xem "mối lo còn lại" trong
    # task-7-8-report.md) — giữ NGUYÊN hành vi cũ (chỉ lọc customer) cho
    # chúng, không âm thầm mở rộng phạm vi thay đổi.
    if doc.doctype in ("Delivery Note", "Sales Invoice"):
        return _khoa_ok_doc(doc.doctype, doc.get("name"), user)
    return True


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
