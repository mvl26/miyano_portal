"""Quản lý thời gian giao hàng (chủ đầu tư 09/10/2026).

Hai việc trên site đang chạy:

1. Thêm `Delivery Note.custom_thoi_gian_giao` — thời điểm giao THẬT do Miyano
   nhập (`posting_date` chỉ là ngày ghi sổ). `allow_on_submit` để sửa được
   khi xe tới trễ so với lúc lập phiếu; `no_copy` để phiếu nhân bản/sửa đổi
   không thừa hưởng giờ giao của phiếu cũ.
2. Cập nhật nội dung hai thư "Portal - Đơn xác nhận" và "Portal - Xuất giao"
   — `install_portal_notifications()` BỎ QUA bản ghi đã tồn tại, nên DEFS
   mới chỉ tới được site cũ qua patch (cùng lý do `v1_19`).
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

from miyano_portal.portal_thoi_gian_giao import MO_TA_TRUONG
from miyano_portal.setup.install_notifications import DEFS, install_portal_notifications

THU_CAP_NHAT = ("Portal - Đơn xác nhận", "Portal - Xuất giao")


def execute():
	create_custom_fields({
		"Delivery Note": [
			{
				"fieldname": "custom_thoi_gian_giao",
				"label": "Thời gian giao hàng",
				"fieldtype": "Datetime",
				"insert_after": "posting_time",
				"allow_on_submit": 1,
				"no_copy": 1,
				"description": MO_TA_TRUONG,
			},
		],
	}, ignore_validate=True)

	install_portal_notifications()
	for d in DEFS:
		if d["name"] in THU_CAP_NHAT and frappe.db.exists("Notification", d["name"]):
			frappe.db.set_value("Notification", d["name"], "message", d["message"])
