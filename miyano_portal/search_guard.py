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
`check_parent_permission(parent, doctype)` (`db_query.py:1305-1317`) cho MỌI
doctype con (`frappe.is_table(doctype)` đúng), hàm đó chỉ hỏi
`has_permission(parent_doctype)` KHÔNG kèm `doc` cụ thể — nên chỉ kiểm ở mức
doctype, bỏ qua hoàn toàn khách hàng của chứng từ, VÀ bỏ qua luôn việc
`parent=` do client gửi có thực sự khớp `parenttype` của dòng con hay không
(`parent=` chỉ là chìa khoá tra quyền, không phải điều kiện lọc hàng — một
doctype con dùng chung nhiều `parenttype`, ví dụ `Payment Schedule` gắn cả
`Sales Order` lẫn `Sales Invoice`, chỉ cần MỘT `parenttype` mà role có read
là đủ mở hết). PoC gốc chứng minh bằng ba doctype `Sales Order Item` /
`Delivery Note Item` / `Sales Invoice Item` — bản vá ĐẦU TIÊN (round 1) chỉ
chặn đúng ba tên đó theo kiểu allow-omission và **fail OPEN** với mọi doctype
con khác (Critical C1, review round 1, 2026-08-12): probe thật cho thấy
`client_get_list("Payment Schedule", parent="Sales Invoice", ...)` vẫn trả
`outstanding`/`payment_amount` của khách khác — đúng trường NG-37 tồn tại để
chặn. Còn lộ: `Payment Schedule`, `Sales Taxes and Charges`, `Sales Invoice
Payment`, `Sales Invoice Advance`, `Packed Item`, `Sales Team`, `Pricing Rule
Detail`, và bất kỳ doctype con nào khác của bốn doctype cha đã có
`permission_query_conditions` (`hooks.py:131-155`).

**Bản vá hiện tại (round 2) chặn theo TRỤC DOCTYPE bằng `frappe.is_table()`,
không liệt kê tên** — đúng nguyên tắc "deny-list role cổng, đừng allow-list
từng hàm/tên" mà brief NG-37b đã nêu ở Step 3, áp dụng luôn cho trục doctype
chứ không chỉ trục hàm (`get_list`/`get`). Không cần danh sách ba/tám/N tên —
MỌI doctype con (bảng con của bất kỳ doctype cha nào) đều bị chặn cho Website
User qua hai hàm này, không phụ thuộc `parent=` client gửi là gì.

ĐỪNG đăng ký `has_permission` cho các doctype con này — đó là một chốt chặn
giả: `frappe.permissions.has_child_permission()` (khi được gọi từ
`doc.check_permission()`/`frappe.has_permission(doctype, doc=<instance>)`)
rẽ nhánh sang kiểm quyền CHA trước khi bất kỳ hook `has_permission` đăng ký
riêng cho doctype con có cơ hội chạy — xem comment dài ở `hooks.py` (khối
`has_permission`) đã ghi lại phát hiện này cho tám doctype kho, cùng một cơ
chế áp dụng ở đây.

**Phạm vi ĐÃ đóng bởi NG-37b (chỉ đọc, xem `client_get_list`/`client_get`
bên dưới):** trên hai route `/api/method/frappe.client.get_list`,
`/api/method/frappe.client.get` (và tương đương `/api/v2/method/...`, mọi
request đi qua `frappe.override_whitelisted_method()` — `handler.py:67`,
`v2.py:36`), Website User bị chặn đọc **MỌI doctype con** (không riêng ba
doctype PoC gốc) — cả trục hàm (chỉ 2 hàm này) lẫn trục doctype (mọi
`is_table`) đều đã fail-closed.

**Phạm vi CHƯA đóng — hai trục khác, không thuộc NG-37b (đã duyệt thành
NG-37c, xem `docs/CHANGELOG-khac-phuc-BA-v2.md`), đã xác nhận bằng probe HTTP
thật:**
- **Trục ROUTE**: `/api/resource/<doctype>` (v1) và `/api/v2/document/
  <doctype>` (v2) gọi thẳng `frappe.call(frappe.client.get_list, doctype,
  **form_dict)` bằng THAM CHIẾU HÀM, không qua tra cứu chuỗi tên, nên
  `override_whitelisted_method()` không bao giờ được gọi tới — wrapper dưới
  đây KHÔNG chạy trên route này, bất kể doctype gì. Tương tự
  `/api/resource/<doctype>/<name>/` (v1) và `/api/v2/document/<doctype>/
  <name>/` (v2) không hề gọi `frappe.client.get`, mà gọi thẳng
  `frappe.get_doc()` rồi `doc.has_permission()`/`check_permission()`, cùng
  dính lỗi `getattr(child_doc, "parent_doc", child_doc.parent)` ở
  `permissions.py:841` (thuộc tính `parent_doc` LUÔN tồn tại trên mọi
  `Document`, nên `getattr` không bao giờ rơi về giá trị mặc định).
- **Trục HÀM**: `frappe.client.get_value` — gọi hàm `get_list` NỘI BỘ của
  chính module `client.py` (tham chiếu Python trực tiếp trong cùng file,
  không phải bản đã override), nên bọc `frappe.client.get_list` không có tác
  dụng với nó, DÙ doctype có `is_table` hay không.

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

# NG-37b round 1 (2026-08-12) từng dùng một deny-set liệt kê tên
# ("Sales Order Item"/"Delivery Note Item"/"Sales Invoice Item") ở đây,
# giống hệt hình dạng `_TU_CHOI` ở trên. Review round 1 tìm ra Critical C1:
# đó là allow-by-omission trên TRỤC DOCTYPE — mọi doctype con KHÁC ba tên đó
# (`Payment Schedule`, `Sales Taxes and Charges`, `Sales Invoice Payment`,
# `Sales Invoice Advance`, `Packed Item`, `Sales Team`, `Pricing Rule
# Detail`, ...) vẫn lọt qua nguyên trạng, dù cùng một lỗ `check_parent_
# permission()` y hệt (xem docstring module). `_TU_CHOI` phía trên KHÔNG mắc
# lỗi này vì nó liệt kê ĐỦ toàn bộ 8 doctype kho hiện có — nhưng "doctype con
# của một chứng từ bán hàng" là một tập KHÔNG đóng (ERPNext có thể thêm bảng
# con mới bất kỳ lúc nào qua Custom Field), nên liệt kê tên không bao giờ an
# toàn cho trục này. Đã bỏ hẳn deny-set liệt kê tên, thay bằng
# `frappe.is_table(doctype)` ngay trong `client_get_list`/`client_get` bên
# dưới — deny-list ĐÚNG NGHĨA là "mọi Website User bị chặn trên MỌI doctype
# con", không phải "chặn những tên tôi nhớ ra".


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
# Nguyên tắc CHẶN THẲNG, không lọc: cổng không có màn nào cần đọc dòng con
# qua hai hàm framework này (đã grep `www/portal`/`frontend/src` — SPA dùng
# riêng `miyano_portal/api/portal.py`/`api/kho.py`, không gọi
# `frappe.client.*`).
#
# CHẶN THEO TRỤC DOCTYPE, KHÔNG LIỆT KÊ TÊN (đã sửa sau Critical C1, review
# round 1): `check_parent_permission()` (`db_query.py:1305-1317`) chỉ kiểm
# `has_permission(parent)` ở mức doctype cho BẤT KỲ doctype con nào, không
# riêng ba tên PoC gốc — nên gate đúng là `frappe.is_table(doctype)`, đúng
# hệt cách framework tự hỏi "đây có phải bảng con không" ở chính
# `frappe/client.py:50,99` (`if frappe.is_table(doctype): check_parent_
# permission(...)`). Với Website User: `get_list` trả `[]` (đúng kiểu dữ
# liệu client mong đợi) cho MỌI doctype con; `get` ném `frappe.PermissionError`
# tiếng Việt (khớp hành vi `check_parent_permission` gốc vẫn ném
# `PermissionError` khi thiếu quyền cha, chỉ đổi thông điệp). Với mọi người
# khác — hoặc Website User gọi doctype KHÔNG PHẢI bảng con — uỷ quyền nguyên
# trạng cho bản gốc `frappe.client.*`, không đổi hành vi.
#
# `parent=` do client gửi KHÔNG được tin để quyết định block hay không — nó
# chỉ là chìa khoá tra quyền phía framework (và có thể sai/giả, xem
# `check_parent_permission()`), không phải điều kiện lọc theo hàng. Gate chỉ
# nhìn `doctype`, không nhìn `parent`.
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
    if _la_khach_cong() and frappe.is_table(doctype):
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
    if _la_khach_cong() and frappe.is_table(doctype):
        frappe.throw(
            _("Không có quyền truy cập dữ liệu này"), frappe.PermissionError
        )

    from frappe.client import get as _frappe_client_get

    return _frappe_client_get(doctype, name, filters, parent)
