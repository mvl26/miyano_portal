"""Chắn các endpoint whitelist của framework trước Website User.

BA v2 §NG-37 + NG-37b (2026-08-12, ngoài BA v2 gốc — xem
`.superpowers/sdd/2026-08-12-dot-1-chan-mau-P0/task-1b-brief.md`).

**NG-37** — `frappe.desk.search.search_link` và `search_widget` đều là
`@frappe.whitelist()` trần: bất kỳ phiên đăng nhập nào không phải Guest đều gọi
được, và khi client tự truyền `ignore_user_permissions=1` thì `search_widget`
chuyển thẳng cờ đó xuống `frappe.get_list(ignore_permissions=...)`, bỏ qua toàn
bộ `permission_query_conditions` của `miyano_portal/permissions.py`. Kết quả:
một tài khoản cổng bất kỳ kéo về được sổ Sales Invoice / Sales Order /
Delivery Note của khách hàng khác, kèm tổng tiền và số còn phải trả.

Chắn CẢ HAI hàm, không chỉ `search_link`: `search_link` chỉ là lớp mỏng gọi
`search_widget`, nên bọc một mình nó để hở nguyên đường gọi thẳng.

**NG-37b** — `frappe.client.get_list`/`frappe.client.get` gọi
`check_parent_permission(parent, doctype)` (`db_query.py:1305-1317`) cho ba
doctype con `Sales Order Item` / `Delivery Note Item` / `Sales Invoice Item`,
hàm đó chỉ hỏi `has_permission(parent_doctype)` KHÔNG kèm `doc` cụ thể, nên chỉ
kiểm ở mức doctype và bỏ qua hoàn toàn khách hàng của đơn. Ba doctype con này
không có entry riêng trong `permission_query_conditions`
(`hooks.py:131-155`) — hook đó phân giải theo doctype ĐANG được truy vấn,
không đi ngược lên cha. Kết quả đã chứng minh bằng probe thật trên
`erptest.local`: một tài khoản cổng đọc được `rate`/`amount` của dòng hàng
thuộc NĂM khách hàng khác nhau qua `frappe.client.get_list("Sales Order
Item", parent="Sales Order")`, dù `frappe.get_list("Sales Order")` ở bảng cha
đã lọc đúng.

ĐỪNG đăng ký `has_permission` cho ba doctype con này — đó là một chốt chặn
giả: `frappe.permissions.has_child_permission()` (khi được gọi từ
`doc.check_permission()`/`frappe.has_permission(doctype, doc=<instance>)`)
rẽ nhánh sang kiểm quyền CHA trước khi bất kỳ hook `has_permission` đăng ký
riêng cho doctype con có cơ hội chạy — xem comment dài ở `hooks.py` (khối
`has_permission`) đã ghi lại phát hiện này cho tám doctype kho, cùng một cơ
chế áp dụng ở đây.

**Phạm vi ĐÃ đóng bởi NG-37b (chỉ đọc, xem `client_get_list`/`client_get`
bên dưới):** `/api/method/frappe.client.get_list`, `/api/method/
frappe.client.get`, và tương đương `/api/v2/method/...` — mọi request đi qua
`frappe.override_whitelisted_method()` (`handler.py:67`, `v2.py:36`), tức
CHỈ những request định danh hàm đích bằng CHUỖI tên đầy đủ.

**Phạm vi CHƯA đóng (đã xác nhận còn rò rỉ bằng probe HTTP thật, ghi trong
`docs/CHANGELOG-khac-phuc-BA-v2.md`, KHÔNG thuộc NG-37b):**
- `/api/resource/<doctype>` (v1) và `/api/v2/document/<doctype>` (v2) — cả
  hai gọi thẳng `frappe.call(frappe.client.get_list, doctype, **form_dict)`
  bằng THAM CHIẾU HÀM, không qua tra cứu chuỗi tên, nên
  `override_whitelisted_method()` không bao giờ được gọi tới.
- `/api/resource/<doctype>/<name>/` (v1) và `/api/v2/document/<doctype>/
  <name>/` (v2) — không hề gọi `frappe.client.get`, mà gọi thẳng
  `frappe.get_doc()` rồi `doc.has_permission()`/`check_permission()`, cùng
  dính lỗi `getattr(child_doc, "parent_doc", child_doc.parent)` ở
  `permissions.py:841` (thuộc tính `parent_doc` LUÔN tồn tại trên mọi
  `Document`, nên `getattr` không bao giờ rơi về giá trị mặc định).
- `frappe.client.get_value` — gọi hàm `get_list` NỘI BỘ của chính module
  `client.py` (tham chiếu Python trực tiếp trong cùng file), không phải bản
  đã override, nên bọc `frappe.client.get_list` không có tác dụng với nó.

Chỉ siết Website User. Nhân viên Miyano ngồi Desk đi thẳng qua bản gốc — đây là
casualty thường gặp nhất của loại sửa này và nó phải không xảy ra.
"""

import frappe
from frappe import _
from frappe.desk import search as _frappe_search

# Tám doctype kho: role `Customer` vốn KHÔNG có DocPerm nào trên chúng, nên
# `get_list` sẽ ném PermissionError chứ không trả rỗng. Trả [] tường minh để
# khách không nhận một lỗi tiếng Anh thô từ một ô tìm kiếm.
_TU_CHOI = {
    "Customer Warehouse",
    "Customer Warehouse Item",
    "Customer Stock Receipt",
    "Customer Stock Receipt Item",
    "Customer Stock Issue",
    "Customer Stock Issue Item",
    "Customer Stock Ledger Entry",
    "Customer Stock Lot Balance",
}

# NG-37b — ba doctype con của bốn doctype cha đã có permission_query_conditions
# (`hooks.py:131-155`). Đúng bằng phạm vi đã chứng minh có lỗ trên site (xem
# docstring module) và đúng bằng phạm vi brief giao — CỐ Ý không thêm
# "Blanket Order Item" dù nó cùng họ (cha `Blanket Order` cũng có
# `blanket_query`/`generic_has_permission`, nên cùng cơ chế lỗ về lý thuyết):
# thêm vào đây là mở rộng phạm vi task một cách âm thầm, việc bị cấm rõ trong
# brief. Đã mở dòng riêng ở sổ theo dõi cho "Blanket Order Item" thay vì lặng
# lẽ vá thêm ở đây.
#
# KHÔNG dùng chung với `_TU_CHOI` ở trên (8 doctype kho) — hai deny-set này
# bảo vệ hai thứ khác nhau và KHÔNG được gộp. `_TU_CHOI` tồn tại vì
# `search_link`/`search_widget` gốc có thể ném `PermissionError` tiếng Anh
# thô cho khách khi role `Customer` không còn DocPerm nào trên 8 doctype kho
# (vòng 4 kho khách hàng) — `client_get_list`/`client_get` KHÔNG cần thêm
# entry cho 8 doctype đó: nếu ai gọi `frappe.client.get_list("Customer
# Warehouse Item", ...)` qua đường này, role check nền tảng (không có DocPerm
# nào cấp read) đã tự chặn ở `check_doctype_permission`/`check_parent_permission`
# TRƯỚC khi tới logic của wrapper, và lỗi `PermissionError` đó là hành vi
# đúng — không cần dịch sang tiếng Việt ở đây vì `frappe.client.*` không phải
# một ô tìm kiếm UI mà `search_guard.py`'s `_TU_CHOI` phục vụ.
_TU_CHOI_DONG_HANG = {
    "Sales Order Item",
    "Delivery Note Item",
    "Sales Invoice Item",
}


def _la_khach_cong(user: str | None = None) -> bool:
    user = user or frappe.session.user
    if user in ("Administrator", "Guest"):
        return False
    return frappe.get_cached_value("User", user, "user_type") == "Website User"


@frappe.whitelist()
def search_link(
    doctype: str,
    txt: str,
    query: str | None = None,
    filters: str | dict | list | None = None,
    page_length: int = 10,
    searchfield: str | None = None,
    reference_doctype: str | None = None,
    ignore_user_permissions: bool = False,
):
    if _la_khach_cong():
        if doctype in _TU_CHOI:
            return []
        try:
            return _frappe_search.search_link(
                doctype,
                txt,
                # `query` cho phép chỉ định một hàm truy vấn tuỳ ý; với khách
                # cổng thì không có nhu cầu nào chính đáng, và mỗi hàm như vậy
                # là một bộ lọc riêng nằm ngoài permission_query_conditions.
                # LƯU Ý: ép về None ở đây KHÔNG hẳn là "bỏ hoàn toàn" tham số
                # này — search.py:86-89 tự nạp lại `query` từ registry
                # `standard_queries` cho MỘT vài doctype cố định (hiện chỉ có
                # "User"). Với "User" thì nhánh đó rơi vào user_query() ->
                # frappe.get_list -> PermissionError cho khách cổng -> bắt ở
                # `except` bên dưới -> []; nên đường vòng này không khai thác
                # được, nhưng lý do là hành vi của user_query(), không phải vì
                # `query=None` đã triệt tiêu registry.
                query=None,
                filters=filters,
                page_length=page_length,
                searchfield=searchfield,
                reference_doctype=reference_doctype,
                # ĐÂY là dòng bịt lỗ.
                ignore_user_permissions=False,
            )
        except frappe.PermissionError:
            return []
    return _frappe_search.search_link(
        doctype, txt, query, filters, page_length,
        searchfield, reference_doctype, ignore_user_permissions,
    )


@frappe.whitelist()
def search_widget(
    doctype: str,
    txt: str,
    query: str | None = None,
    searchfield: str | None = None,
    start: int = 0,
    page_length: int = 10,
    filters: str | None | dict | list = None,
    filter_fields=None,
    as_dict: bool = False,
    reference_doctype: str | None = None,
    ignore_user_permissions: bool = False,
):
    if _la_khach_cong():
        if doctype in _TU_CHOI:
            return []
        try:
            return _frappe_search.search_widget(
                doctype,
                txt,
                query=None,
                searchfield=searchfield,
                start=start,
                page_length=page_length,
                filters=filters,
                # `filter_fields` là đường client tự chọn cột trả về — đúng chỗ
                # `grand_total` và `outstanding_amount` lọt ra ngoài trong BA v2.
                # LƯU Ý: nulling filter_fields KHÔNG PHẢI cái chặn rò rỉ CHÉO
                # KHÁCH HÀNG — `searchfield` (tham số client cũng kiểm soát
                # được) là một đường chiếu cột y hệt: search.py's
                # get_std_fields_list() nối `searchfield` thẳng vào danh sách
                # cột SELECT, nên search_widget("Sales Order", <đơn của
                # CHÍNH khách>, searchfield="grand_total") vẫn trả cột đó cho
                # ĐƠN CỦA CHÍNH HỌ — đó không phải rò rỉ, chỉ là khách tự xem
                # số của mình qua một cổng vào khác thường. Cái thật sự chặn
                # rò rỉ CHÉO KHÁCH HÀNG là dòng lọc theo hàng được khôi phục
                # (ignore_user_permissions=False bên dưới, giữ
                # permission_query_conditions sống lại). Null filter_fields ở
                # đây chỉ là phòng thủ theo chiều sâu (giảm bề mặt cột trả
                # về), không phải cơ chế chặn chính.
                filter_fields=None,
                as_dict=as_dict,
                reference_doctype=reference_doctype,
                ignore_user_permissions=False,
            )
        except frappe.PermissionError:
            return []
    return _frappe_search.search_widget(
        doctype, txt, query, searchfield, start, page_length,
        filters, filter_fields, as_dict, reference_doctype,
        ignore_user_permissions,
    )


# ---------------------------------------------------------------------------
# NG-37b — bọc frappe.client.get_list / frappe.client.get
# ---------------------------------------------------------------------------
# Nguyên tắc CHẶN THẲNG, không lọc: cổng không có màn nào cần đọc dòng hàng
# qua hai hàm framework này (đã grep `www/portal` — SPA dùng riêng
# `miyano_portal/api/portal.py`/`api/kho.py`, không gọi `frappe.client.*`).
# Nên với Website User, mọi lời gọi trên ba doctype con
# (`_TU_CHOI_DONG_HANG`) bị chặn hẳn — trả `[]` cho `get_list` (đúng kiểu dữ
# liệu client mong đợi), ném `frappe.PermissionError` tiếng Việt cho `get`
# (khớp hành vi `check_parent_permission` gốc vẫn ném `PermissionError` khi
# thiếu quyền cha, chỉ đổi thông điệp sang tiếng Việt). Với mọi người khác —
# hoặc Website User gọi doctype KHÁC ba doctype trên — uỷ quyền nguyên trạng
# cho bản gốc `frappe.client.*`, không đổi hành vi.
#
# `@frappe.whitelist()` là bắt buộc, không phải trang trí: `execute_cmd()`
# (`handler.py:65-86`) resolve chuỗi tên qua `override_whitelisted_method()`
# RỒI MỚI gọi `is_whitelisted(method)` trên hàm ĐÍCH đã resolve — thiếu
# decorator này thì request thật (không phải test gọi thẳng hàm Python) sẽ
# bị handler chặn với lỗi "not whitelisted", che luôn nhánh chặn rò rỉ bên
# dưới không bao giờ chạy tới.
@frappe.whitelist()
def client_get_list(
    doctype,
    fields=None,
    filters=None,
    group_by=None,
    order_by=None,
    limit_start=None,
    limit_page_length=20,
    parent=None,
    debug: bool = False,
    as_dict: bool = True,
    or_filters=None,
    expand=None,
):
    if _la_khach_cong() and doctype in _TU_CHOI_DONG_HANG:
        return []

    from frappe.client import get_list as _frappe_client_get_list

    return _frappe_client_get_list(
        doctype,
        fields=fields,
        filters=filters,
        group_by=group_by,
        order_by=order_by,
        limit_start=limit_start,
        limit_page_length=limit_page_length,
        parent=parent,
        debug=debug,
        as_dict=as_dict,
        or_filters=or_filters,
        expand=expand,
    )


@frappe.whitelist()
def client_get(doctype, name=None, filters=None, parent=None):
    if _la_khach_cong() and doctype in _TU_CHOI_DONG_HANG:
        frappe.throw(
            _("Không có quyền truy cập dữ liệu này"), frappe.PermissionError
        )

    from frappe.client import get as _frappe_client_get

    return _frappe_client_get(doctype, name, filters, parent)
