"""E3 phần B (US-E3.5, US-E3.6) — hai Report Desk mới: "Đối soát giao nhận"
và "Chất lượng dữ liệu kho khách". Gọi lại đúng `install_kho_desk_reports()`
của Phase 6 (idempotent — bỏ qua report_name đã tồn tại) sau khi hai đặc tả
mới được thêm vào `REPORTS`, thay vì viết một hàm cài đặt thứ hai.

(I4/M5, E3 phần B review) Hai report này ban đầu mang tên "Đối soát giao –
nhận" (có en-dash "–") và "Chất lượng dữ liệu" — đã đổi TRƯỚC KHI patch này
kịp merge lên nhánh chính, nhưng site dev đã chạy patch ở phiên bản cũ nên
vẫn có thể còn hai bản ghi Report tên cũ trong DB, trỏ tới thư mục trên đĩa
đã bị đổi tên/xoá. Xoá chúng nếu còn tồn tại TRƯỚC khi gọi
install_kho_desk_reports(), để lần chạy lại patch trên một site đã từng
chạy bản cũ hội tụ về đúng trạng thái mới — không để lại Report mồ côi."""

import frappe

from miyano_portal.setup.install_kho_desk_reports import install_kho_desk_reports

_TEN_CU = ("Đối soát giao – nhận", "Chất lượng dữ liệu")


def execute():
	for ten in _TEN_CU:
		# Chỉ xoá bản ghi ĐÚNG của module này — Report docname là duy nhất
		# toàn site, nhưng kiểm thêm module cho chắc, tránh xoá nhầm nếu một
		# app khác (ngoài kiểm soát) từng đặt trùng tên chung chung.
		if frappe.db.get_value("Report", ten, "module") == "Miyano Portal":
			frappe.delete_doc("Report", ten, ignore_permissions=True, force=True)
	install_kho_desk_reports()
