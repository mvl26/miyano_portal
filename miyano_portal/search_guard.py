"""Chắn hai endpoint tìm kiếm của framework trước Website User.

BA v2 §NG-37. `frappe.desk.search.search_link` và `search_widget` đều là
`@frappe.whitelist()` trần: bất kỳ phiên đăng nhập nào không phải Guest đều gọi
được, và khi client tự truyền `ignore_user_permissions=1` thì `search_widget`
chuyển thẳng cờ đó xuống `frappe.get_list(ignore_permissions=...)`, bỏ qua toàn
bộ `permission_query_conditions` của `miyano_portal/permissions.py`. Kết quả:
một tài khoản cổng bất kỳ kéo về được sổ Sales Invoice / Sales Order /
Delivery Note của khách hàng khác, kèm tổng tiền và số còn phải trả.

Chắn CẢ HAI hàm, không chỉ `search_link`: `search_link` chỉ là lớp mỏng gọi
`search_widget`, nên bọc một mình nó để hở nguyên đường gọi thẳng.

Chỉ siết Website User. Nhân viên Miyano ngồi Desk đi thẳng qua bản gốc — đây là
casualty thường gặp nhất của loại sửa này và nó phải không xảy ra.
"""

import frappe
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
