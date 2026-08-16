"""Gán mẫu in MẶC ĐỊNH cho từng doctype.

Yêu cầu chủ đầu tư 2026-08-16: không lấy mẫu in sẵn có của ERPNext.

Trước bản này app cài đủ mẫu theo thông tư nhưng **không doctype nào được gán
mặc định**, nên nút "In" trên Desk rơi thẳng vào mẫu Standard của ERPNext —
đúng thứ phải tránh. Cài mẫu mà không gán mặc định thì mẫu chỉ nằm đó chờ ai
đó nhớ chọn trong dropdown.

Cơ chế: `Property Setter` trên `default_print_format`, đúng cách Frappe lưu
lựa chọn này khi người dùng đặt tay trên Customize Form.

CHỈ gán khi mẫu đích TỒN TẠI — một `default_print_format` trỏ vào mẫu không có
thật khiến Frappe im lặng quay lại mẫu Standard, tức tệ hơn hiện trạng vì
người sửa tưởng đã xong.
"""

import frappe

# (doctype, tên mẫu mặc định, vì sao)
MAC_DINH = [
	# Chứng từ theo chế độ kế toán
	("Portal Delivery Inspection", "Miyano - Biên bản kiểm nghiệm (TT107)",
	 "Mẫu 03-VT. TT107 vì khách phần lớn là bệnh viện công"),
	("Customer Stock Receipt", "Miyano - Phiếu nhập kho (TT107)", "Mẫu 01-VT"),
	("Customer Stock Issue", "Miyano - Phiếu xuất kho (TT107)", "Mẫu 02-VT"),
	("Delivery Note", "Miyano - Phiếu xuất kho (02-VT)",
	 "Mẫu 02-VT của Miyano (doanh nghiệp → TT200)"),
	# Chứng từ thương mại — thông tư KHÔNG quy định mẫu, nhưng vẫn phải là mẫu
	# của Miyano chứ không phải mẫu Standard của ERPNext.
	("Sales Order", "Miyano - Xác nhận đơn hàng", "Không có mẫu thông tư"),
	("Sales Invoice", "Miyano - Hoá đơn", "Bản in nội bộ; hoá đơn hợp pháp do HĐĐT phát hành"),
]


def gan_mau_in_mac_dinh() -> dict:
	da_gan, bo_qua = [], []
	for doctype, mau, _ly_do in MAC_DINH:
		if not frappe.db.exists("Print Format", mau):
			bo_qua.append((doctype, mau, "mẫu chưa tồn tại"))
			continue
		frappe.make_property_setter({
			"doctype": doctype,
			"doctype_or_field": "DocType",
			"property": "default_print_format",
			"value": mau,
			"property_type": "Data",
		}, is_system_generated=True)
		da_gan.append((doctype, mau))
	return {"da_gan": da_gan, "bo_qua": bo_qua}
