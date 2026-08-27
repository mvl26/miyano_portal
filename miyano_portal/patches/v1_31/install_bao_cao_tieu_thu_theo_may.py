"""Task 10 (2026-08-27) — đăng ký Report Desk "Tiêu thụ theo máy".

`install_kho_desk_reports()` (setup/install_kho_desk_reports.py) đã được
gọi MỘT LẦN qua patch `v1_2.install_kho_desk_reports`, và Patch Log đánh dấu
patch đó đã hoàn tất trên mọi site đã migrate trước Task 10 — thêm một mục
mới vào danh sách `REPORTS` của module đó KHÔNG tự động cài lại trên các
site cũ, vì `bench migrate` không chạy lại một patch đã ghi nhận hoàn tất
(xem memory "miyano-portal-install-patch-trap": install_app/migrate fake-
hoàn-tất patch, Patch Log.creation mới lộ ra). Hàm `install_kho_desk_reports()`
tự nó IDEMPOTENT (bỏ qua report đã tồn tại — `if frappe.db.exists(...):
continue`), nên gọi lại an toàn ở đây chỉ thêm ĐÚNG report còn thiếu
("Tiêu thụ theo máy"), không đụng tám report đã cài từ trước.
"""

from miyano_portal.setup.install_kho_desk_reports import install_kho_desk_reports


def execute():
	install_kho_desk_reports()
