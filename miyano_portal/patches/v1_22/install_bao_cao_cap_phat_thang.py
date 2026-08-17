"""Cài report desk "Cấp phát theo tháng và khoa phòng" + shortcut workspace.

Yêu cầu chủ đầu tư 2026-08-17. Cần MỘT PATCH MỚI, không sửa được patch cũ:
`v1_2`/`v1_11` (install_kho_desk_reports) và `v1_21`
(them_cong_khach_vao_workspace) đã nằm trong Patch Log của site đã migrate nên
không bao giờ chạy lại — thêm một dòng vào `REPORTS`/`_REPORT_SHORTCUTS` mà
không có patch mới thì site cũ không thấy gì. Đúng cái bẫy đã ghi trong
[[miyano-portal-install-patch-trap]] và đã cắn hai lần ở v1_20/v1_21.

Cả hai hàm đều idempotent: `install_kho_desk_reports()` bỏ qua từng report đã
tồn tại (nên nó CHỈ tạo cái mới), `install_kho_workspace()` ghi đè content +
shortcuts của workspace đã có.
"""

from miyano_portal.setup.install_kho_desk_reports import install_kho_desk_reports
from miyano_portal.setup.install_kho_workspace import install_kho_workspace


def execute():
	install_kho_desk_reports()
	install_kho_workspace()
