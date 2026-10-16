"""Báo giá theo đợt trên một yêu cầu báo giá (spec 2026-10-15).

Phiếu gốc là Quotation của cổng do `bao_gia.tao_bao_gia` dựng. Nhân viên tách
từng nhóm dòng ĐÃ CÓ GIÁ thành một Quotation con ("đợt", `custom_phieu_goc`)
đi nguyên workflow của `bao_gia`; phiếu gốc giữ phần chưa báo và không bao giờ
gửi khách nữa (D7). Mọi luật về đợt nằm ở module này; `bao_gia` chỉ gọi sang
ở `dong_y` (ghi bảng `don_hang`).
"""

import frappe

from miyano_portal import bao_gia

BANG_DON_HANG = "Portal De Xuat Mua Don Hang"

_san_sang_cache: bool | None = None


def san_sang() -> bool:
	"""Có cột `Quotation.custom_phieu_goc` THẬT chưa (patch v1_45). Cùng khuôn
	`bao_gia.san_sang()`: mã mới trên site chưa `bench migrate` không được ném
	1054 ở các hook chạy cho MỌI báo giá của cổng."""
	global _san_sang_cache
	if _san_sang_cache is None:
		_san_sang_cache = bool(frappe.db.has_column("Quotation", "custom_phieu_goc"))
	return _san_sang_cache


def them_don_hang(phieu: str, sales_order: str, bao_gia: str | None, so_dot: int) -> None:
	"""Ghi một dòng `don_hang` lên phiếu đề xuất; `sales_order` của phiếu chỉ
	đặt khi đang trống (luôn trỏ ĐƠN ĐẦU TIÊN — màn và báo cáo cũ đọc nó).

	Chèn thẳng dòng con, không lưu lại phiếu: lưu phiếu đi qua các chốt sửa
	phiếu (`_chan_sua_so_luong_de_xuat`…) không liên quan tới việc này. Chạy
	lại được: đơn đã có dòng thì thôi."""
	if frappe.db.table_exists(BANG_DON_HANG):
		if not frappe.db.exists(BANG_DON_HANG, {"parent": phieu, "sales_order": sales_order}):
			idx = frappe.db.sql(
				f"select coalesce(max(idx), 0) from `tab{BANG_DON_HANG}` where parent = %s", phieu
			)[0][0]
			frappe.get_doc({
				"doctype": BANG_DON_HANG, "parent": phieu, "parenttype": "Portal De Xuat Mua",
				"parentfield": "don_hang", "idx": int(idx) + 1, "sales_order": sales_order,
				"bao_gia": bao_gia, "so_dot": so_dot or 0,
			}).db_insert()
	if not frappe.db.get_value("Portal De Xuat Mua", phieu, "sales_order"):
		frappe.db.set_value("Portal De Xuat Mua", phieu, "sales_order", sales_order)
