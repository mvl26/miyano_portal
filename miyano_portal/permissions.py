import frappe
from miyano_portal.portal_context import (
    _cot_khoa_phong_ton_tai,
    dam_bao_xem_duoc,
    get_allowed_customers,
    pham_vi_don,
)


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


def de_xuat_query_condition(user=None) -> str:
    """`Portal De Xuat Mua` mang `customer` trực tiếp — cùng hình dạng
    `Portal Item Request`/`Portal Delivery Inspection` ngay trên, KHÔNG phải
    hình dạng kho (`kho/permissions.py`, lọc qua field `kho`).

    Vế TRỤC KHÁCH HÀNG này vốn thuộc Task 4 của kế hoạch nền phân quyền
    khoa phòng, nhưng bị kéo lên Task 1 (ruling coordinator 19/08/2026):
    lưới an toàn `test_kho_isolation.py::_nap_doctype_kho()` bắt MỌI
    doctype mang `customer` trong module này phải nằm trong
    `KHO_DOCTYPES_KHAC` kèm wiring thật — một doctype thiếu dây cách ly
    không được phép tồn tại trong repo, dù chỉ tạm thời giữa hai task.

    Vế KHOA PHÒNG do Task 4 thêm vào CHÍNH hàm này — chiều khoa đi VÀO tầng
    phân quyền đã có ở đây, không dựng tầng thứ hai. Trường trên doctype này
    tên là `khoa_phong` (KHÔNG phải `custom_khoa_phong` như Sales Order) —
    `pham_vi_don()` luôn trả khoá `custom_khoa_phong` bất kể doctype gọi nó,
    nên đọc GIÁ TRỊ từ khoá đó rồi áp lên ĐÚNG tên cột của doctype này.

    Fail-closed cùng nguyên tắc `_khoa_query_condition`: nếu `dk` đã là ""
    (không bị giới hạn — không phải Website User) hoặc "1=0" (đã fail-closed
    ở trục khách hàng, ca không có `Portal Member` active nào), thêm vế khoa
    vào đây vô nghĩa — VÀ `pham_vi_don()` có thể tự ném `PermissionError` vì
    cùng lý do không có `Portal Member` active (`get_portal_member` bên
    trong nó), nên phải chặn sớm trước khi gọi. Nếu `pham_vi_don()` ném
    `PermissionError` vì lý do khác (Nhân viên khoa `active=1` mà
    `khoa_phong` rỗng — xem docstring hàm đó) thì cũng fail-closed, không để
    lộ ra ngoài."""
    dk = _customer_condition("Portal De Xuat Mua", user)
    if dk in ("", "1=0"):
        return dk
    user = user or frappe.session.user
    try:
        pv = pham_vi_don(user)
    except frappe.PermissionError:
        return "1=0"
    khoa = pv.get("custom_khoa_phong")
    if khoa:
        dk += f" and `tabPortal De Xuat Mua`.khoa_phong = {frappe.db.escape(khoa)}"
    return dk


def de_xuat_co_quyen(doc, ptype=None, user=None):
    """Vỏ `has_permission` cho `Portal De Xuat Mua` — cùng khuôn
    `generic_has_permission`, chỉ lọc theo `customer`. Xem docstring
    `de_xuat_query_condition` cho lý do hàm này nằm trong Task 1 thay vì
    Task 4. Vế khoa phòng do Task 4 thêm vào CHÍNH hàm này — cùng logic với
    `de_xuat_query_condition` ngay trên, dạng kiểm MỘT bản ghi thay vì lọc
    danh sách; đọc field `khoa_phong` của `doc` (KHÔNG phải
    `custom_khoa_phong` — tên đó chỉ là khoá `pham_vi_don()` trả về, không
    phải tên cột trên doctype này)."""
    if not _has_customer_permission(doc, user):
        return False
    user = user or frappe.session.user
    if not _is_restricted_user(user):
        return True
    try:
        pv = pham_vi_don(user)
    except frappe.PermissionError:
        return False
    khoa = pv.get("custom_khoa_phong")
    return not khoa or doc.get("khoa_phong") == khoa


def de_xuat_item_query(user=None) -> str:
    """Bảng con `Portal De Xuat Mua Item` — không mang `customer` riêng, lọc
    qua parent. Cùng khuôn `kiem_hang_item_query` ngay trên cho trục KHÁCH
    HÀNG.

    VÒNG VÁ (mang từ Task 4 sang Task 5, review phát hiện) — bản trước CHỈ
    lọc theo `customer`, thiếu vế KHOA mà doctype cha (`de_xuat_query_
    condition`) đã có: một nhân viên khoa Huyết học gọi thẳng kênh
    `frappe.client.*`/reportview trên bảng con vẫn thấy dòng hàng của khoa
    Dược cùng bệnh viện. Vá theo ĐÚNG khuôn hàm cha — dùng lại
    `pham_vi_don()` (không viết lại logic khoa ở tầng này), `frappe.db.
    escape` giá trị, rồi AND thêm điều kiện qua chứng từ cha (không có
    field khoa riêng trên bảng con để so trực tiếp)."""
    user = user or frappe.session.user
    if not _is_restricted_user(user):
        return ""
    customers = get_allowed_customers(user)
    if not customers:
        return "1=0"
    joined = ", ".join(frappe.db.escape(c) for c in customers)
    dieu_kien_cha = f"`customer` in ({joined})"
    try:
        pv = pham_vi_don(user)
    except frappe.PermissionError:
        # Fail-closed — cùng nguyên tắc de_xuat_query_condition/_khoa_query_
        # condition: không xác định được phạm vi thì không được coi là
        # "không giới hạn".
        return "1=0"
    khoa = pv.get("custom_khoa_phong")
    if khoa:
        dieu_kien_cha += f" and `khoa_phong` = {frappe.db.escape(khoa)}"
    return (
        "`tabPortal De Xuat Mua Item`.`parent` in "
        f"(select name from `tabPortal De Xuat Mua` where {dieu_kien_cha})"
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


# Ba doctype DUY NHẤT mang khái niệm khoa phòng (`custom_khoa_phong` trực
# tiếp hoặc quy về đơn cha) — SONG SINH với `api/portal.py::_THONG_BAO_
# DOCTYPE_LOC_KHOA` (không import chéo được, hai module không có quan hệ
# phụ thuộc: `permissions.py` phục vụ tầng hook, `api/portal.py` phục vụ
# tầng endpoint). Đổi một bên PHẢI soát bên còn lại — cùng khuôn "hai nơi
# định nghĩa một khái niệm PHẢI khớp nhau" đã ghi ở nhiều chỗ khác trong đề
# án (vd. `_TRANG_THAI_GHI_DE_WORKFLOW`/`_so_status_vi_full`).
_THONG_BAO_DOCTYPE_LOC_KHOA = ("Sales Order", "Delivery Note", "Sales Invoice")


def notification_khoa_query(user=None) -> str:
    """VÒNG VÁ FIX-WAVE (V1, review tổng toàn nhánh — CRITICAL).

    `Notification Log` (core) cấp `read/report/export` cho role `All`
    (JSON gốc `frappe/desk/doctype/notification_log/notification_log.json`),
    mà `ALL_USER_ROLE` được framework gán cho MỌI user kể cả Website User
    (`frappe/permissions.py`). `get_permission_query_conditions` của core
    (`notification_log.py`) chỉ lọc `for_user = session.user` — KHÔNG có vế
    khoa. Doctype này KHÔNG phải bảng con (`frappe.is_table`) nên
    `rest_guard.chan_rest_doctype_con`/`search_guard.client_get_list` (hai
    lưới chặn `frappe.client.*`/REST cho MỌI doctype "con" — xem hooks.py)
    không áp dụng ở đây: `frappe.client.get_list`/`get_value`/
    `frappe.get_list` đi THẲNG cho MỌI Website User.

    `bao_hen_giao_lai`/`bao_kiem_hang_ket_qua` (`portal_thong_bao_khach.py`)
    fan-out MỘT bản ghi `Notification Log` cho MỖI thành viên ĐANG ACTIVE
    của KHÁCH HÀNG (chưa lọc theo khoa lúc TẠO — docstring `_portal_users_
    cua_khach` tự nhận, để dành việc lọc khoa cho phần mở rộng này).
    `for_user` vì thế đúng NGAY TỪ ĐẦU cho một nhân viên khoa B dù chứng từ
    thuộc khoa A — điều kiện `for_user` của core không chặn được ca này, vì
    nó không phải một quyền bị chiếm đoạt mà là một bản ghi ĐÚNG CHỦ nhưng
    SAI PHẠM VI.

    Hàm này thêm ĐÚNG vế khoa còn thiếu, dùng LẠI `_dieu_kien_khoa_qua_don_
    cha` — KHÔNG viết lại logic quy-về-đơn-cha (cùng nguyên tắc
    `_khoa_query_condition` ngay trên). CHỈ áp cho ba doctype có khái niệm
    khoa phòng (`_THONG_BAO_DOCTYPE_LOC_KHOA`, cùng bộ ba với `api/
    portal.py::_THONG_BAO_DOCTYPE_LOC_KHOA`) — thông báo KHÁC (`Customer
    Stock Receipt`/kho, `Portal Delivery Inspection`/kiểm hàng, thông báo
    hệ thống nội bộ Miyano...) giữ NGUYÊN hành vi cũ, không âm thầm mở rộng
    phạm vi vá (đúng docstring `_THONG_BAO_DOCTYPE_LOC_KHOA` ở `api/
    portal.py` đã giải thích: kho là tài sản CẤP BỆNH VIỆN, lọc theo khoa
    ở đó là lỗi, không phải một chỗ quên).

    Frappe AND mọi `permission_query_conditions` của MỌI app lại với nhau
    (`frappe/model/db_query.py::get_permission_query_conditions`) — hook
    của core (`for_user = ...`) và hook này CÙNG áp dụng, không hook nào
    ghi đè hook kia; hàm này chỉ THU HẸP thêm, không bao giờ mở rộng."""
    user = user or frappe.session.user
    if not _is_restricted_user(user):
        return ""
    if not _cot_khoa_phong_ton_tai():
        # Cùng lưới an toàn triển khai với _khoa_query_condition ngay trên
        # — thiếu cột thì fail-closed, không để MariaDB 1054 lộ ra.
        return "1=0"
    try:
        pham_vi = pham_vi_don(user)
    except frappe.PermissionError:
        # Fail-closed — cùng nguyên tắc _khoa_query_condition.
        return "1=0"
    if not pham_vi:
        return ""
    khoa = pham_vi["custom_khoa_phong"]
    escaped = frappe.db.escape(khoa)
    dtype_col = "`tabNotification Log`.`document_type`"
    dname_col = "`tabNotification Log`.`document_name`"
    dieu_kien_theo_loai = {
        "Sales Order": (
            f"exists (select 1 from `tabSales Order` where "
            f"`tabSales Order`.name = {dname_col} and "
            f"`tabSales Order`.custom_khoa_phong = {escaped})"
        ),
        "Delivery Note": (
            f"exists (select 1 from `tabDelivery Note` where "
            f"`tabDelivery Note`.name = {dname_col} and ("
            + _dieu_kien_khoa_qua_don_cha(
                "Delivery Note", "Delivery Note Item", "against_sales_order", escaped
            )
            + "))"
        ),
        "Sales Invoice": (
            f"exists (select 1 from `tabSales Invoice` where "
            f"`tabSales Invoice`.name = {dname_col} and ("
            + _dieu_kien_khoa_qua_don_cha(
                "Sales Invoice", "Sales Invoice Item", "sales_order", escaped
            )
            + "))"
        ),
    }
    ve_theo_loai = " or ".join(
        f"({dtype_col} = {frappe.db.escape(dt)} and {cond})"
        for dt, cond in dieu_kien_theo_loai.items()
    )
    scoped = ", ".join(frappe.db.escape(t) for t in _THONG_BAO_DOCTYPE_LOC_KHOA)
    return f"({dtype_col} not in ({scoped}) or {ve_theo_loai})"
