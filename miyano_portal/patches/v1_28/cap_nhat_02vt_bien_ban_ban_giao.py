"""Cập nhật mẫu 02-VT sang bản TT 99/2025 — "Phiếu xuất kho kiêm biên bản bàn giao".

`install_bien_ban_print_formats()` idempotent theo kiểu "bỏ qua nếu đã có" —
site đã chạy patch cài mẫu sẽ KHÔNG bao giờ nhận được bản sửa. Ghi đè thẳng
HTML của đúng một mẫu, cùng khuôn `cap_nhat_02vt_tien_bang_chu` (v1_21) và
`update_kho_print_formats_khoa_phong`.

Không đụng `gan_mau_in_mac_dinh`: 02-VT ĐÃ là mẫu mặc định của `Delivery Note`
từ trước (`setup/gan_mau_in_mac_dinh.py`), nên nhân viên bấm In là ra bản mới
mà không phải chọn gì.
"""

import frappe

from miyano_portal.setup.install_bien_ban_print_formats import (
    HTML_PHIEU_XUAT_02VT,
    NAME_PHIEU_XUAT_02VT,
    install_bien_ban_print_formats,
)


def execute():
    if not frappe.db.exists("Print Format", NAME_PHIEU_XUAT_02VT):
        # Site chưa từng cài (bản cài mới) — để installer dựng luôn bản mới.
        install_bien_ban_print_formats()
        return
    frappe.db.set_value(
        "Print Format", NAME_PHIEU_XUAT_02VT, "html", HTML_PHIEU_XUAT_02VT,
        update_modified=False,
    )
