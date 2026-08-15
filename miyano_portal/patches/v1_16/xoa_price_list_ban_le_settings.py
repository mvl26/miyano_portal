"""Việc 2(b) (dọn lean) — xoá `Miyano Portal Settings.price_list_ban_le` +
hàm `portal_mua_le.price_list_ban_le()`.

BR-R3/VĐ-12 (bản đầu) đòi Price List bán lẻ phải cấu hình trước khi bật
mua lẻ. Thiết kế lại mua lẻ §4.5 bỏ hẳn việc TRA GIÁ ở nhánh mua lẻ (đơn
vào "Chờ xác nhận" với `rate=0`, sales điền giá sau — xem
`api/portal.py::_selling_price_list_mac_dinh`, dùng `Selling Settings`
thay vì field này) — từ đó hàm `price_list_ban_le()` hết caller ngoài
test, và giá trị đang lưu trong field (`'Bán lẻ E6 Test'`) là một fixture
test lọt vào cấu hình thật.

Field này khai TRỰC TIẾP trong DocType JSON (không phải Custom Field) và
`Miyano Portal Settings` là Single — không có cột `tabSingles` cố định để
DROP, giá trị nằm ở một HÀNG trong `tabSingles` (doctype='Miyano Portal
Settings', field='price_list_ban_le'). Bỏ field khỏi JSON (đã làm trong
cùng commit) đã đủ để không ai đọc/ghi được nó qua ORM; patch này CHỈ dọn
hàng dữ liệu mồ côi còn sót lại cho sạch, không phải yêu cầu bắt buộc về
mặt schema.

Idempotent: `frappe.db.delete` trên điều kiện không khớp bản ghi nào trả
về 0 hàng bị xoá, không lỗi — chạy lại vô hại.
"""

import frappe


def execute():
    frappe.db.delete(
        "Singles",
        {"doctype": "Miyano Portal Settings", "field": "price_list_ban_le"},
    )
