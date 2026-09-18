"""Dựng lại mẫu "Miyano - Xác nhận đơn hàng" theo bản mẫu PHIẾU ĐẶT HÀNG
`docs/03_MVL_Phieu-dat-hang(SO).doc` — mẫu nút "⬇ PDF đơn hàng" trên cổng.

`install_portal_print_formats()` idempotent kiểu "bỏ qua nếu đã có" — site đã
cài mẫu sẽ KHÔNG bao giờ nhận HTML mới. Ghi đè thẳng HTML của đúng một mẫu,
cùng khuôn `v1_21/cap_nhat_02vt_tien_bang_chu`.
"""

import frappe

from miyano_portal.setup.install_print_formats import HTML, NAME


def execute():
	if frappe.db.exists("Print Format", NAME):
		frappe.db.set_value("Print Format", NAME, "html", HTML, update_modified=False)
