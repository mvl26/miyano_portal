"""CR-03 (05/09/2026) — mẫu in "Miyano - Báo giá" (`HTML_BG` ở `setup/
install_print_formats.py`) thêm ba cột Model/Hãng SX/Quy cách vào bảng "Hàng
đang tìm nguồn" (thiết kế §8): tờ giấy đó chính là thứ purchasing cầm đi hỏi
nhà cung cấp, nên ba field khách vừa khai thêm ở màn Đặt hàng phải in ra
được ở đây, không dừng lại ở màn hình Desk.

Cùng bài học `v1_15.dong_bo_dinh_dang_tien_bao_gia` đã ghi: `install_portal_
print_formats()` BỎ QUA (không ghi đè) mẫu in đã tồn tại — sửa chuỗi
`HTML_BG` trong mã nguồn không tự cập nhật bản ghi `Print Format` đã cài
trên site. Patch NÀY đồng bộ lại field `html` cho ĐÚNG bản ghi đó.

Idempotent: ghi cùng giá trị nhiều lần vô hại; bỏ qua nếu mẫu in chưa tồn
tại (site chưa từng chạy `v1_15.install_print_format_bao_gia` thì lần cài
ĐẦU TIÊN sẽ tự dùng `HTML_BG` hiện hành, không cần đồng bộ thêm)."""

import frappe

from miyano_portal.setup.install_print_formats import HTML_BG, NAME_BG


def execute():
    if frappe.db.exists("Print Format", NAME_BG):
        frappe.db.set_value("Print Format", NAME_BG, "html", HTML_BG)
