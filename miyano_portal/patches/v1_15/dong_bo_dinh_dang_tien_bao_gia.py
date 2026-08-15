"""review Minor — mẫu in "Miyano - Báo giá" (`HTML_BG` ở `setup/
install_print_formats.py`) đổi sang dấu CHẤM phân nhóm (`1.234.567 ₫`, đúng
quy ước dự án), thay cho dấu phẩy sai quy ước ("{:,.0f}" nguyên bản).

`install_portal_print_formats()` BỎ QUA (không ghi đè) mẫu in đã tồn tại —
sửa chuỗi `HTML_BG` trong mã nguồn không tự động cập nhật bản ghi `Print
Format` đã cài trên site. Patch NÀY đồng bộ lại field `html` cho ĐÚNG bản
ghi đó (`frappe.db.set_value`, không phải Link nên không cần lo
`_validate_links()`).

Idempotent: ghi cùng giá trị nhiều lần vô hại; bỏ qua nếu mẫu in chưa tồn
tại (site chưa chạy `v1_15.install_print_format_bao_gia`, patch đó tự dùng
`HTML_BG` hiện hành nên không cần đồng bộ thêm).
"""

import frappe

from miyano_portal.setup.install_print_formats import HTML_BG, NAME_BG


def execute():
    if frappe.db.exists("Print Format", NAME_BG):
        frappe.db.set_value("Print Format", NAME_BG, "html", HTML_BG)
