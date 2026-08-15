"""Việc 2(a) (dọn lean) — xoá `Item.custom_ban_le_portal`.

Cờ này được tạo ở `patches/v1_8/create_e6_mua_le_custom_fields.py` để lọc
danh mục mua lẻ (BR-R6 cũ). Thiết kế lại mua lẻ §4.1 đổi danh mục lẻ sang
trả TOÀN BỘ `Item` (`disabled=0` là điều kiện thành viên duy nhất còn lại)
— cờ này từ đó không còn lọc gì (spec §7 hoãn xoá lúc đó; giờ hết lý do
hoãn, không còn caller nào đọc field này ngoài fixture test đã dọn cùng
patch này).

Xoá bằng `frappe.delete_doc("Custom Field", ...)` (KHÔNG phải xoá cột
`tabItem` — `Custom Field.on_trash` không tự ALTER TABLE DROP COLUMN, xem
`frappe/custom/doctype/custom_field/custom_field.py`). 64 vật tư đang set
cờ này SẼ MẤT giá trị cột đó (chấp nhận được — cờ không còn ảnh hưởng hành
vi nào).

Idempotent: `frappe.db.exists` guard trước khi xoá — chạy lại khi field đã
xoá rồi là no-op, không lỗi.
"""

import frappe


def execute():
    name = "Item-custom_ban_le_portal"
    if frappe.db.exists("Custom Field", name):
        frappe.delete_doc("Custom Field", name, ignore_permissions=True, force=True)
