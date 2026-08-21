"""Task 1 (2026-08-19, gộp luồng đặt hàng) — xoá `Customer.custom_cho_phep_
mua_le`.

BR-R1/NL-10.1 (chốt "khách phải được bật cờ này mới mua được hàng ngoài
HĐNT") đã bỏ hẳn — chủ đầu tư chốt 19/08: "nghiệp vụ đó áp dụng cho toàn bộ
khách hàng", không còn gì để field này gác nữa. `dam_bao_duoc_mua_le()`
(portal_mua_le.py) và mọi lời gọi tới nó đã xoá trong cùng task.

Giữ lại field trông như một chốt kiểm soát mà không còn gác gì là phiên
bản schema của "bình luận nói sai về code" — người sau nhìn
`custom_cho_phep_mua_le = 0` trên một khách sẽ tưởng khách đó đang bị chặn
mua ngoài hợp đồng, trong khi thực ra không còn chốt nào đọc field này.

Xoá bằng `frappe.delete_doc("Custom Field", ...)` — theo đúng khuôn
`patches/v1_16/xoa_custom_field_ban_le_portal.py`. `Custom Field.on_trash`
KHÔNG tự ALTER TABLE DROP COLUMN (xem
`frappe/custom/doctype/custom_field/custom_field.py`), nên cột vật lý
`tabCustomer.custom_cho_phep_mua_le` còn tồn tại mồ côi sau patch này —
chấp nhận được, không còn ORM/API nào đọc/ghi được nó qua Custom Field đã
xoá.

Không đụng `patches/v1_8/create_e6_mua_le_custom_fields.py` (tạo field này)
lẫn `patches/v1_15/bat_mua_le_mac_dinh.py` (đổi default + backfill) — cả
hai đã chạy trên site đã migrate, không bao giờ tới lại. `v1_15.execute()`
tự no-op an toàn sau patch này (kiểm `frappe.db.get_value("Custom Field",
FIELD, "name")` rỗng thì return sớm — xem chính file đó).

Idempotent: `frappe.db.exists` guard trước khi xoá — chạy lại khi field đã
xoá rồi là no-op, không lỗi.
"""

import frappe


def execute():
    name = "Customer-custom_cho_phep_mua_le"
    if frappe.db.exists("Custom Field", name):
        frappe.delete_doc("Custom Field", name, ignore_permissions=True, force=True)
