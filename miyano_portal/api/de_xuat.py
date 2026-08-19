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


def _ap_dieu_chinh(doc, dieu_chinh):
	"""Quản lý chỉ chạm `so_luong_duyet` và `ghi_chu_quan_ly`. Bỏ một mặt
	hàng = HẠ VỀ 0, không xoá dòng (§5.3). Thêm mặt hàng → dòng mới có
	`so_luong_de_xuat = 0`, `nguon_dong = "Quản lý thêm"`.

	CHỈ đọc `item_code` (để KHỚP dòng ĐÃ CÓ) và `so_luong_duyet` — mọi field
	khác trong payload bị bỏ qua, cùng khuôn `portal_order_sua_so_luong`.
	"""
	dc = frappe.parse_json(dieu_chinh) if isinstance(dieu_chinh, str) else dieu_chinh
	theo_ma = {d.item_code: d for d in doc.items}
	for row in dc.get("items", []):
		ma = row.get("item_code")
		if ma in theo_ma:
			theo_ma[ma].so_luong_duyet = float(row.get("so_luong_duyet") or 0)
			if row.get("ghi_chu_quan_ly") is not None:
				theo_ma[ma].ghi_chu_quan_ly = row["ghi_chu_quan_ly"]
		else:
			doc.append("items", {
				"item_code": ma, "so_luong_de_xuat": 0,
				"so_luong_duyet": float(row.get("so_luong_duyet") or 0),
				"nguon_dong": "Quản lý thêm",
			})
	doc.save(ignore_permissions=True)


@frappe.whitelist()
def de_xuat_duyet_phieu(ten, dieu_chinh=None) -> dict:
	"""Chốt quyền DUY NHẤT của đường duyệt. Kế hoạch C (uỷ quyền) sửa ĐÚNG
	dòng `la_quan_ly()` này, không đụng `de_xuat_duyet.duyet_va_tao_don`."""
	if not la_quan_ly():
		raise frappe.PermissionError("Chỉ quản lý mới duyệt được đề xuất.")
	doc = _phieu_cua_toi(ten, cho_quan_ly=True)
	if dieu_chinh:
		_ap_dieu_chinh(doc, dieu_chinh)
	from miyano_portal import de_xuat_duyet
	return de_xuat_duyet.duyet_va_tao_don(doc.name, frappe.session.user)


@frappe.whitelist()
def de_xuat_tu_choi(ten, ly_do) -> dict:
	if not la_quan_ly():
		raise frappe.PermissionError("Chỉ quản lý mới từ chối được đề xuất.")
	doc = _phieu_cua_toi(ten, cho_quan_ly=True)
	doc.tu_choi(ly_do)
	return {"name": doc.name}


@frappe.whitelist()
def de_xuat_xin_sua(ten, dong) -> dict:
	"""Task 9 (§12 Q4) — nhân viên khoa xin sửa số lượng một đơn ĐÃ được
	quản lý duyệt. `_phieu_cua_toi(..., cho_quan_ly=True)`: KHÔNG chỉ chủ
	phiếu — bất kỳ đồng nghiệp nào CÙNG KHOA (trong phạm vi khách hàng +
	khoa của `pham_vi_don()`) đều xin sửa được, không riêng owner. Đơn Sales
	Order KHÔNG bị chạm ở đây — `PortalDeXuatMua.xin_sua()` chỉ ghi lên
	phiếu, đúng thiết kế §12 Q4 (nhân viên vẫn sửa được, nhưng phải quay lại
	quản lý duyệt lần nữa TRƯỚC KHI đơn thật sự đổi).

	`dong` — JSON (hoặc dict) `{"items": [{"item_code": str, "qty": float}]}`,
	cùng hình dạng `dong` của `portal.portal_order_sua_so_luong`."""
	doc = _phieu_cua_toi(ten, cho_quan_ly=True)
	if isinstance(dong, str):
		dong = frappe.parse_json(dong)
	items = (dong or {}).get("items") or []
	doc.xin_sua(items)
	# Task 8 — tái dùng ĐÚNG hàm "báo quản lý có phiếu chờ xử lý" đã có
	# (chỉ Quản lý cần biết, không báo lại cho khoa vừa gửi — cùng khuôn
	# `gui_duyet()`), không dựng thêm một mẫu thông báo riêng cho nhánh này.
	from miyano_portal.portal_thong_bao_khach import bao_de_xuat_gui_duyet
	bao_de_xuat_gui_duyet(doc)
	return {"name": doc.name}


@frappe.whitelist()
def de_xuat_duyet_sua(ten) -> dict:
	"""Chỉ quản lý — ĐỒNG Ý yêu cầu xin sửa: gọi lõi `portal.portal_order_
	sua_so_luong` DƯỚI QUYỀN QUẢN LÝ đang gọi (guard `dam_bao_duoc_sua_don_
	da_duyet` cho qua vì `la_quan_ly()` đúng) để sửa THẬT Sales Order, rồi
	mới gọi `doc.duyet_sua()` dọn phần còn lại trên phiếu. Thứ tự này CỐ Ý:
	nếu sửa đơn thất bại (hết hiệu lực báo giá, đơn không còn ở đúng
	trạng thái...), phiếu KHÔNG được chuyển "Đã duyệt" sớm hơn thật.

	I2 (review Task 9) — lọc `d.so_luong_xin_sua >= 0`, KHÔNG lọc truthy:
	`0` là một yêu cầu THẬT ("xin bỏ dòng này", đúng quy ước của
	`portal_order_sua_so_luong`), không phải "chưa có gì để duyệt". Lọc
	truthy (bản đầu của Task 9) làm rớt LẶNG LẼ đúng yêu cầu nguy hiểm nhất."""
	if not la_quan_ly():
		raise frappe.PermissionError("Chỉ quản lý mới duyệt yêu cầu xin sửa được.")
	doc = _phieu_cua_toi(ten, cho_quan_ly=True)
	dong = {
		"items": [
			{"item_code": d.item_code, "qty": float(d.so_luong_xin_sua)}
			for d in doc.items if d.so_luong_xin_sua >= 0
		]
	}
	from miyano_portal.api import portal
	portal.portal_order_sua_so_luong(doc.sales_order, dong)
	doc.reload()
	doc.duyet_sua()
	return {"name": doc.name}


@frappe.whitelist()
def de_xuat_tu_choi_sua(ten, ly_do) -> dict:
	"""Chỉ quản lý — TỪ CHỐI yêu cầu xin sửa: đơn giữ NGUYÊN, không gọi lõi
	`portal_order_sua_so_luong` chút nào — chỉ dọn phiếu."""
	if not la_quan_ly():
		raise frappe.PermissionError("Chỉ quản lý mới từ chối yêu cầu xin sửa được.")
	doc = _phieu_cua_toi(ten, cho_quan_ly=True)
	doc.tu_choi_sua(ly_do)
	return {"name": doc.name}


@frappe.whitelist()
def de_xuat_huy(ten) -> dict:
	"""§5.4b — từ Chờ duyệt trở đi CHỈ quản lý huỷ được. Nhân viên không
	huỷ phiếu đã gửi: một phiếu đang nằm trong danh sách chờ của quản lý mà
	biến mất giữa chừng là thứ khó chịu nhất cho người duyệt."""
	if not la_quan_ly():
		raise frappe.PermissionError("Chỉ quản lý mới huỷ được phiếu đã gửi.")
	doc = _phieu_cua_toi(ten, cho_quan_ly=True)
	doc.huy()
	return {"name": doc.name}
