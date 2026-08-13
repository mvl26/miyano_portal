"""E8 (US-E8.5) — Report Desk mới: "Cấp phát theo khoa phòng". Gọi lại đúng
`install_kho_desk_reports()` của Phase 6 (idempotent — bỏ qua `report_name`
đã tồn tại) sau khi đặc tả mới được thêm vào `REPORTS`, thay vì viết một hàm
cài đặt thứ hai — cùng khuôn `v1_10/install_e5_desk_reports.py`.
"""

from miyano_portal.setup.install_kho_desk_reports import install_kho_desk_reports


def execute():
	install_kho_desk_reports()
