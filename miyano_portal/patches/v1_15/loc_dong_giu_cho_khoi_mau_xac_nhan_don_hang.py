"""Việc thêm (controller, ngoài Task 9) — lớp phòng thủ THỨ HAI: lọc dòng
giữ chỗ `HANG-DAT-NGOAI` khỏi mẫu in "Miyano - Xác nhận đơn hàng" bằng
`la_dong_giu_cho` (xem `setup/install_print_formats.py`).

Chốt `before_submit` (`portal_mua_le.kiem_khong_con_dong_giu_cho`) đã chặn
dòng giữ chỗ tới được một đơn ĐÃ SUBMIT — nhưng nếu chốt đó có lỗ hổng nào
trong tương lai, mẫu in vẫn phải tự lọc, không tin tưởng riêng vào chốt ghi.

`install_portal_print_formats()` BỎ QUA bản ghi đã tồn tại (cùng khuôn
"exists → continue" như patch `install_print_format_bao_gia`), nên bản ghi
Print Format "Miyano - Xác nhận đơn hàng" đã cài từ v1_0 sẽ KHÔNG tự nhận
HTML mới — phải ghi đè thẳng `html` ở đây.

Idempotent: `frappe.db.set_value` ghi cùng giá trị nhiều lần là vô hại.
"""

import frappe

from miyano_portal.setup.install_print_formats import HTML, NAME


def execute():
    if frappe.db.exists("Print Format", NAME):
        frappe.db.set_value("Print Format", NAME, "html", HTML)
