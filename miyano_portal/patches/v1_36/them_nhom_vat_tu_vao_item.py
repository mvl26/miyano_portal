"""Thêm `Item.custom_nhom_vat_tu` — NHÓM VẬT TƯ của từng mặt hàng.

Chủ đầu tư 28/09/2026: *"trong mỗi item em hãy thêm cho anh 1 trường chọn
nhóm vật tư ... hóa sinh, vi sinh, huyết học, test nhanh, sinh học phân tử,
vật tư"* và ở màn `/portal/dat-hang` có bộ lọc hiển thị hàng theo nhóm đó.

VÌ SAO KHÔNG dùng lại `item_group`: `Item Group` là cây phân loại kế toán/kho
của ERPNext, gắn với tài khoản và báo cáo tồn — đổi nó để phục vụ một bộ lọc
hiển thị ở cổng là kéo theo hạch toán. Nhóm vật tư là trục RIÊNG cho khách.

`Select` chứ không `Link`: sáu giá trị do chủ đầu tư chốt, không cần doctype
riêng. Danh sách tuỳ chọn là NGUỒN DUY NHẤT — `portal_catalog_gop` đọc lại nó
từ meta để kiểm tham số lọc và trả về cho cổng dựng nút lọc, nên thêm một
nhóm ở Customize Form là cổng thấy ngay, không phải sửa code.

Mặt hàng CŨ để trống — hợp lệ: chưa ai phân nhóm cho chúng. Không đoán nhóm
từ tên hàng (một nhóm đoán sai thì hàng biến mất khỏi đúng bộ lọc khách cần).
"""

from frappe.custom.doctype.custom_field.custom_field import create_custom_field


def execute():
	create_custom_field("Item", {
		"fieldname": "custom_nhom_vat_tu",
		"label": "Nhóm vật tư",
		"fieldtype": "Select",
		"options": "\nHóa sinh\nVi sinh\nHuyết học\nTest nhanh\nSinh học phân tử\nVật tư",
		"insert_after": "item_group",
		"in_list_view": 1,
		"in_standard_filter": 1,
		"description": "Dùng cho bộ lọc nhóm hàng ở màn Đặt hàng trên cổng khách.",
	})
