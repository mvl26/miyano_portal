"""Một đơn hàng sinh từ phiếu đề xuất (spec 2026-10-15 §3.3).

Báo giá theo đợt cho một phiếu ra NHIỀU đơn; `Portal De Xuat Mua.sales_order`
chỉ giữ đơn đầu tiên. Không có DocPerm riêng: đọc qua phiếu cha như
`Portal De Xuat Mua Item`."""

from frappe.model.document import Document


class PortalDeXuatMuaDonHang(Document):
	pass
