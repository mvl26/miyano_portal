"""Endpoint cổng cho `Portal De Xuat Mua` (spec §5).

MỌI hàm ở đây suy `customer` và `khoa_phong` từ PHIÊN ĐĂNG NHẬP qua
`get_portal_member()`, KHÔNG nhận từ client — cùng luật C1 đã áp cho
`portal_order_place`. Một tham số `khoa_phong` nhận từ client sẽ cho nhân
viên khoa A lập phiếu mang tên khoa B.

Module này PHẢI có tên trong `tests/test_pham_vi_endpoint.py` — module mới
không tự động bị test đếm ngược soi tới.

BỐI CẢNH KIẾN TRÚC (Task 5, 19/08/2026) — role `Customer` có ZERO DocPerm
trên `Portal De Xuat Mua` (đã kiểm `tabDocPerm` thực nghiệm, xem
`test_de_xuat_cach_ly.py`), giống ba doctype cổng khác đang chạy thật. Hệ
quả: `frappe.get_list`/`doc.check_permission()` ném `PermissionError` cho
MỌI Website User TRƯỚC KHI hook `has_permission`/`permission_query_
conditions` (Task 4, `permissions.de_xuat_query_condition`/`de_xuat_co_
quyen`) kịp chạy. Hook đó vì thế là LỚP PHÒNG THỦ THỨ HAI, chết có điều
kiện — ĐƯỜNG SỐNG của cổng là các hàm whitelist DƯỚI ĐÂY, và chúng phải tự
hỏi ĐÚNG chốt phạm vi mà tầng hook hỏi (`pham_vi_don()`), không tự chế bộ
lọc riêng.
"""

import frappe

from miyano_portal.portal_context import get_portal_member, la_quan_ly, pham_vi_don

DOCTYPE = "Portal De Xuat Mua"


def _phieu_cua_toi(ten: str, *, cho_quan_ly=False):
	"""Lấy phiếu sau khi đã kiểm quyền. Trả `Document`.

	SỬA SAU TASK 4 — `doc.check_permission("read")` KHÔNG dùng được ở đây.
	Role `Customer` có ZERO DocPerm trên doctype này (đã kiểm `tabDocPerm`
	19/08: cả `Portal Item Request`, `Portal Delivery Inspection`,
	`Customer Department`, `Portal De Xuat Mua` đều vậy — quy ước của app,
	không phải thiếu sót). `check_permission` ném `PermissionError` cho MỌI
	Website User TRƯỚC KHI hook `has_permission` có cơ hội chạy.

	Nên đường sống của cổng là ĐÂY, và nó phải hỏi ĐÚNG chốt phạm vi mà
	tầng hook hỏi — `pham_vi_don()` — chứ không tự chế bộ lọc riêng.

	`cho_quan_ly=True` KHÔNG có nghĩa "chỉ quản lý gọi được" — nó nghĩa là
	BỎ vòng kiểm chủ sở hữu, chỉ còn vòng kiểm phạm vi (khách hàng + khoa
	phòng). Dùng cho `de_xuat_chi_tiet`: bất kỳ ai TRONG PHẠM VI (đúng
	khách hàng, đúng khoa — kể cả quản lý, vốn có `pham_vi_don()` rỗng nên
	luôn trong phạm vi) đều xem được chi tiết một phiếu, không riêng người
	tạo ra nó — đúng ý nghĩa "đồng nghiệp cùng khoa xem được phiếu của
	nhau", không phải một đặc quyền chỉ dành cho quản lý.
	"""
	doc = frappe.get_doc(DOCTYPE, ten)
	tv = get_portal_member()
	if doc.customer != tv.customer:
		# Không xác nhận cả sự tồn tại của phiếu thuộc khách khác.
		raise frappe.PermissionError("Phiếu này không thuộc đơn vị của bạn.")
	pv = pham_vi_don()
	khoa_gioi_han = pv.get("custom_khoa_phong")
	if khoa_gioi_han and doc.khoa_phong != khoa_gioi_han:
		raise frappe.PermissionError("Phiếu này không thuộc khoa phòng của bạn.")
	if not cho_quan_ly and doc.owner != frappe.session.user and not la_quan_ly():
		raise frappe.PermissionError("Phiếu này không phải của bạn.")
	return doc


@frappe.whitelist()
def de_xuat_tao_nhap(loai_don="HĐNT", hdnt=None, **_bo_qua) -> dict:
	"""`**_bo_qua` là CỐ Ý: client cũ/độc hại gửi thêm `customer` hay
	`khoa_phong` thì chúng rơi vào đây và bị vứt, không đi vào doc."""
	tv = get_portal_member()
	doc = frappe.get_doc({
		"doctype": DOCTYPE,
		"customer": tv.customer,
		"khoa_phong": tv.khoa_phong,
		"loai_don": loai_don,
		"hdnt": hdnt,
		"trang_thai": "Nháp",
	}).insert(ignore_permissions=True)
	return {"name": doc.name}


@frappe.whitelist()
def de_xuat_luu_nhap(ten, items=None, dat_ngoai=None, ngay_can=None,
                     dia_chi_giao=None, ghi_chu=None, ly_do_yeu_cau=None) -> dict:
	doc = _phieu_cua_toi(ten)
	if doc.trang_thai != "Nháp":
		frappe.throw("Chỉ sửa được phiếu đang ở trạng thái Nháp.",
		             frappe.ValidationError)
	if items is not None:
		doc.set("items", frappe.parse_json(items) if isinstance(items, str) else items)
	if dat_ngoai is not None:
		doc.set("dat_ngoai",
		        frappe.parse_json(dat_ngoai) if isinstance(dat_ngoai, str) else dat_ngoai)
	for f, v in (("ngay_can", ngay_can), ("dia_chi_giao", dia_chi_giao),
	             ("ghi_chu", ghi_chu), ("ly_do_yeu_cau", ly_do_yeu_cau)):
		if v is not None:
			doc.set(f, v)
	doc.save(ignore_permissions=True)
	return {"name": doc.name}


@frappe.whitelist()
def de_xuat_xoa_nhap(ten) -> dict:
	"""§5.4b — XOÁ THẬT, chỉ ở trạng thái Nháp. `on_trash` của doctype là
	chốt cuối; kiểm ở đây chỉ để báo lỗi dễ hiểu hơn. Owner HOẶC quản lý
	(`_phieu_cua_toi()` mặc định `cho_quan_ly=False` đã cho cả hai đi
	qua)."""
	doc = _phieu_cua_toi(ten)
	frappe.delete_doc(DOCTYPE, doc.name, ignore_permissions=True)
	return {"ok": True}


@frappe.whitelist()
def de_xuat_gui_duyet(ten) -> dict:
	"""Chỉ CHỦ PHIẾU (owner) được gửi duyệt — khác `de_xuat_xoa_nhap`/
	`de_xuat_luu_nhap` (owner HOẶC quản lý). Quản lý là người DUYỆT phiếu
	(`doc.duyet()`, Task 6/9), không phải người tự GỬI hộ phiếu của nhân
	viên khác — `_phieu_cua_toi()` một mình sẽ cho quản lý đi qua (nó cũng
	chấp nhận quản lý ở vòng kiểm chủ sở hữu chung), nên endpoint này phải
	tự thêm một chốt owner-only riêng SAU vòng kiểm phạm vi của
	`_phieu_cua_toi()`. Một quản lý tự tạo phiếu cho chính mình vẫn gửi
	được bình thường qua đúng nhánh owner này (họ CHÍNH LÀ owner) — không
	mất khả năng tự duyệt phiếu của mình (`tu_duyet`, xem `PortalDeXuatMua.
	duyet()`)."""
	doc = _phieu_cua_toi(ten)
	if doc.owner != frappe.session.user:
		raise frappe.PermissionError("Chỉ chủ phiếu (người tạo) mới gửi duyệt được.")
	doc.gui_duyet()
	return {"name": doc.name, "ma_de_xuat": doc.ma_de_xuat}


@frappe.whitelist()
def de_xuat_danh_sach(trang_thai=None, limit=50) -> list[dict]:
	"""SỬA SAU TASK 4 — KHÔNG dùng `frappe.get_list` tràn được.

	Role `Customer` có ZERO DocPerm trên doctype này, nên `get_list` ném
	`PermissionError` TRƯỚC khi `permission_query_conditions` kịp chạy.
	Hook của Task 4 là LỚP PHÒNG THỦ THỨ HAI — nó sẽ có hiệu lực nếu
	DocPerm bị cấp lại, và nó chặn `GET /api/resource/...`; nhưng hôm nay
	đường đó đã trả 403 cho mọi Website User, tức KÍN HƠN chứ không hở.

	Đường sống là đây. Phải áp CẢ HAI bộ lọc, và lấy đúng chốt mà tầng hook
	đúng hỏi — `get_portal_member()` cho khách, `pham_vi_don()` cho khoa.
	Tự chế bộ lọc riêng ở đây là đi ngược nguồn sự thật thứ hai."""
	tv = get_portal_member()
	loc = {"customer": tv.customer}
	pv = pham_vi_don()
	if pv.get("custom_khoa_phong"):
		loc["khoa_phong"] = pv["custom_khoa_phong"]
	if trang_thai:
		loc["trang_thai"] = trang_thai
	return frappe.get_all(
		DOCTYPE, filters=loc,
		fields=["name", "ma_de_xuat", "khoa_phong", "trang_thai",
		        "thoi_diem_gui", "owner"],
		order_by="modified desc", limit_page_length=int(limit),
	)


@frappe.whitelist()
def de_xuat_chi_tiet(ten) -> dict:
	doc = _phieu_cua_toi(ten, cho_quan_ly=True)
	return doc.as_dict()
