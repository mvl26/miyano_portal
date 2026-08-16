"""Cập nhật mẫu 02-VT: tiền bằng chữ tiếng Việt.

`install_bien_ban_print_formats()` idempotent theo kiểu "bỏ qua nếu đã có" —
site đã chạy patch cài mẫu sẽ KHÔNG bao giờ nhận được bản sửa. Ghi đè thẳng
HTML của đúng một mẫu, cùng khuôn `update_kho_print_formats_khoa_phong`.
"""

import frappe

from miyano_portal.setup.install_bien_ban_print_formats import (
    HTML_PHIEU_XUAT_02VT,
    NAME_PHIEU_XUAT_02VT,
)


def execute():
    if frappe.db.exists("Print Format", NAME_PHIEU_XUAT_02VT):
        frappe.db.set_value(
            "Print Format", NAME_PHIEU_XUAT_02VT, "html", HTML_PHIEU_XUAT_02VT,
            update_modified=False,
        )
