"""E3 phần B (US-E3.5, US-E3.6) — hai Report Desk mới: "Đối soát giao – nhận"
và "Chất lượng dữ liệu". Gọi lại đúng `install_kho_desk_reports()` của Phase
6 (idempotent — bỏ qua report_name đã tồn tại) sau khi hai đặc tả mới được
thêm vào `REPORTS`, thay vì viết một hàm cài đặt thứ hai.
"""

from miyano_portal.setup.install_kho_desk_reports import install_kho_desk_reports


def execute():
	install_kho_desk_reports()
