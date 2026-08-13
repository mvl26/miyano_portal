"""E5 (US-E5.5) — hai Report Desk mới: "Tiêu thụ và đề xuất dự trù" và
"Tỷ trọng nguồn cung". Gọi lại đúng `install_kho_desk_reports()` của
Phase 6 (idempotent — bỏ qua `report_name` đã tồn tại) sau khi hai đặc tả
mới được thêm vào `REPORTS`, thay vì viết một hàm cài đặt thứ hai.

Report thứ ba của US-E5.5 ("Chất lượng dữ liệu": mở rộng thêm hai khía
cạnh NL-9.3) KHÔNG cần patch riêng — nó SỬA file `.py` của report "Chất
lượng dữ liệu kho khách" đã cài từ v1_5, không tạo bản ghi `Report` mới.
"""

from miyano_portal.setup.install_kho_desk_reports import install_kho_desk_reports


def execute():
	install_kho_desk_reports()
