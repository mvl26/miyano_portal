"""Một đơn hàng sinh từ phiếu đề xuất (spec 2026-10-15 §3.3).

Báo giá theo đợt cho một phiếu ra NHIỀU đơn; `Portal De Xuat Mua.sales_order`
chỉ giữ đơn đầu tiên. Không có DocPerm riêng: đọc qua phiếu cha như
`Portal De Xuat Mua Item`, và dùng CHUNG lớp phòng thủ thứ hai
(`has_permission` theo khách/khoa của phiếu cha) với bảng đó."""

from miyano_portal.miyano_portal.doctype.portal_de_xuat_mua_item.portal_de_xuat_mua_item import (
	DongConDeXuatMua,
)


class PortalDeXuatMuaDonHang(DongConDeXuatMua):
	pass
