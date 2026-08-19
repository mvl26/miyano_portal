"""Thêm `Sales Order.custom_de_xuat` + `custom_ma_tra_cuu` (Task 6, spec §5.6).

`custom_de_xuat` (Link `Portal De Xuat Mua`) — trỏ ngược từ đơn hàng về
đúng phiếu đề xuất đã sinh ra nó, qua `de_xuat_duyet.duyet_va_tao_don()`.
Đơn CŨ (trước Task 6, hoặc đặt trực tiếp không qua đề xuất) để trống — hợp
lệ, KHÔNG phải lỗi (xem `test_don_cu_khong_co_ma_tra_cuu_thi_khong_vo`).

`custom_ma_tra_cuu` (Data) — CHÉP LẠI `ma_de_xuat` của phiếu gốc lên đơn
(không phải Link ngược đọc qua `custom_de_xuat` mỗi lần): khách cần đọc
được MÃ CỦA HỌ (`DXA-HUYETHOC-260819-01`) ngay trên đơn hàng mà không cần
quyền đọc doctype `Portal De Xuat Mua` (zero DocPerm cho Customer, §5.1) —
chép giá trị tránh phải mở một đường đọc chéo doctype mới chỉ để hiển thị
một chuỗi.
"""

from frappe.custom.doctype.custom_field.custom_field import create_custom_field


def execute():
	create_custom_field("Sales Order", {
		"fieldname": "custom_de_xuat",
		"label": "Đề xuất mua",
		"fieldtype": "Link",
		"options": "Portal De Xuat Mua",
		"read_only": 1,
		"search_index": 1,
		"insert_after": "custom_khoa_phong",
	})
	create_custom_field("Sales Order", {
		"fieldname": "custom_ma_tra_cuu",
		"label": "Mã tra cứu (đề xuất)",
		"fieldtype": "Data",
		"read_only": 1,
		"insert_after": "custom_de_xuat",
	})
