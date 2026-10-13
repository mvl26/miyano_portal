"""Yêu cầu báo giá bằng Quotation (spec 2026-10-12).

Một yêu cầu báo giá của khách là một Quotation đi workflow `WORKFLOW`. Sales
Order chỉ sinh ra khi khách đồng ý (`dong_y`). Tài khoản cổng KHÔNG có DocPerm
trên Quotation: mọi hàm ghi ở đây chạy bước chuyển trạng thái dưới
`nang_quyen.quyen_he_thong()`, và NGƯỜI GỌI (endpoint trong `api/portal.py`)
phải kiểm quyền của khách trên đúng báo giá đó trước khi gọi vào đây.
"""

import frappe
from frappe.utils import add_days, flt, now_datetime, nowdate

WORKFLOW = "Quotation - Client Portal"
NGUON_CONG = "Client Portal"
LOAI_DON_THEO_BAO_GIA = "Theo báo giá"
HAU_TO_DON = ":don"

TT_CHO_MIYANO = "Chờ Miyano báo giá"
TT_CHO_KHACH = "Chờ khách đồng ý"
TT_DA_DONG_Y = "Khách đã đồng ý"
TT_KHACH_TU_CHOI = "Khách từ chối"
TT_MIYANO_TU_CHOI = "Miyano từ chối"
TT_HET_HAN = "Báo giá hết hạn"

HD_GUI_KHACH = "Gửi khách duyệt"
HD_TU_CHOI = "Từ chối"
HD_THU_HOI = "Thu hồi để sửa"
HD_KHACH_DONG_Y = "Khách đồng ý"
HD_KHACH_TU_CHOI = "Khách từ chối"
HD_KHACH_SUA_SL = "Khách sửa số lượng"
HD_HET_HAN = "Báo giá hết hạn"
HD_GHI_NHAN = "Ghi nhận khách đồng ý"

LY_DO_TOI_THIEU = 10


def _trang_thai_truoc(doc) -> str | None:
	truoc = doc.get_doc_before_save()
	return truoc.get("workflow_state") if truoc else None


def chan_dong_y_ngoai_cong(doc, method=None) -> None:
	"""Hook `before_submit` của Quotation.

	Báo giá của cổng chỉ được Submit bởi `dong_y()`, nơi sinh luôn Sales Order.
	Bước "Khách đồng ý" khai `System Manager`, nên một nhân viên có vai đó bấm
	được nó trên Desk; đi đường đó thì báo giá "đã đồng ý" mà không có đơn.
	"""
	if doc.get("custom_nguon_don") != NGUON_CONG:
		return
	if frappe.flags.get("bao_gia_dong_y_qua_cong") == doc.name:
		return
	frappe.throw(
		"Báo giá của cổng khách hàng chỉ được đồng ý bởi chính khách trên cổng.",
		frappe.ValidationError,
	)


def kiem_ly_do_tu_choi(doc, method=None) -> None:
	"""Hook `validate` — Miyano từ chối thì phải có lý do (spec §4.1)."""
	if doc.get("workflow_state") != TT_MIYANO_TU_CHOI:
		return
	if _trang_thai_truoc(doc) == TT_MIYANO_TU_CHOI:
		return
	if len((doc.get("custom_ly_do_tu_choi") or "").strip()) < LY_DO_TOI_THIEU:
		frappe.throw(
			f"Phải nhập lý do từ chối (tối thiểu {LY_DO_TOI_THIEU} ký tự) trước khi "
			"chuyển trạng thái.",
			frappe.ValidationError,
		)


# Trường của một dòng khách gõ tay được chép từ giỏ sang báo giá. Cùng danh
# sách trắng mà `dat_hang._xay_don` dùng; không chép `da_chuyen`/`dong_hang`.
TRUONG_DAT_NGOAI = (
	"ten_hang", "dvt", "so_luong", "ghi_chu", "model_ma", "hang_san_xuat",
	"nuoc_san_xuat", "quy_cach", "ncc_hien_tai", "gia_hien_tai", "anh",
	"khong_co_anh", "mo_ta_nhan_dang",
)


def can_bao_gia(customer: str, items: list, dat_ngoai: list) -> bool:
	"""Giỏ này phải đi báo giá: có dòng gõ tay, hoặc có mã chưa có giá trong
	Price List của khách. Cùng phép chia mà `tach_phieu` dùng để tách phiếu."""
	from miyano_portal import tach_phieu

	if dat_ngoai:
		return True
	_co_gia, cho_bao_gia = tach_phieu.chia_dong(customer, items or [])
	return bool(cho_bao_gia)


def tao_bao_gia(
	customer: str, *, items=None, dat_ngoai=None, delivery_date=None, note=None,
	address=None, request_id=None, khoa_phong=None,
) -> dict:
	"""Dựng một Quotation ở "Chờ Miyano báo giá". Trả
	`{"bao_gia": str, "da_ton_tai": bool, "total": float}`.

	Mọi phép kiểm của giỏ hàng (bội số, hàng ngừng bán, dòng gõ tay thiếu tên,
	ngày giao, công ty, kho, dòng giữ chỗ) là của `dat_hang._xay_don`: hàm đó
	dựng một Sales Order CHƯA lưu, ở đây chỉ chép nó sang Quotation. Viết lại
	các phép kiểm ấy lần hai là để hai đường đặt hàng nói khác nhau về cùng
	một giỏ.
	"""
	from miyano_portal import dat_hang
	from miyano_portal.portal_dat_hang import ngay_giao_mac_dinh

	if not request_id:
		frappe.throw(
			"Thiếu mã yêu cầu đặt hàng. Tải lại trang rồi thử lại.",
			frappe.ValidationError,
		)
	da_co = frappe.db.get_value(
		"Quotation", {"custom_request_id": request_id},
		["name", "party_name", "grand_total"], as_dict=True,
	)
	if da_co:
		if da_co.party_name != customer:
			# Mã yêu cầu của khách khác: không xác nhận cả sự tồn tại của nó.
			raise frappe.PermissionError("Mã yêu cầu không hợp lệ.")
		return {
			"bao_gia": da_co.name, "da_ton_tai": True,
			"total": float(da_co.grand_total or 0),
		}

	if address:
		hop_le = {a["name"] for a in dat_hang._customer_addresses(customer)}
		if address not in hop_le:
			raise frappe.PermissionError("Địa chỉ giao hàng không thuộc đơn vị của bạn.")
	if isinstance(items, str):
		items = frappe.parse_json(items)
	if isinstance(dat_ngoai, str):
		dat_ngoai = frappe.parse_json(dat_ngoai)
	items, dat_ngoai = items or [], dat_ngoai or []
	if not items and not dat_ngoai:
		frappe.throw("Giỏ hàng trống.")

	gop: dict[str, float] = {}
	for dong in items:
		ma_tho = (dong.get("item_code") or "").strip()
		ma = frappe.db.get_value("Item", ma_tho, "name") if ma_tho else None
		if not ma:
			frappe.throw(
				f"Không tìm thấy mặt hàng '{ma_tho or '(trống)'}'.", frappe.ValidationError
			)
		gop[ma] = gop.get(ma, 0) + float(dong.get("qty") or 0)

	so = dat_hang._xay_don(
		customer, gop, dat_ngoai, delivery_date or ngay_giao_mac_dinh(),
		address, None, note, request_id,
	)

	bg = frappe.new_doc("Quotation")
	bg.quotation_to = "Customer"
	bg.party_name = customer
	bg.order_type = "Sales"
	bg.company = so.company
	bg.transaction_date = frappe.utils.today()
	bg.selling_price_list = so.selling_price_list
	# Một nguồn giá duy nhất: Price List của khách, không Pricing Rule.
	bg.ignore_pricing_rule = 1
	bg.custom_nguon_don = NGUON_CONG
	bg.custom_request_id = request_id
	for truong in ("customer_address", "shipping_address_name", "contact_person", "contact_email"):
		if so.get(truong):
			bg.set(truong, so.get(truong))
	for d in so.items:
		bg.append("items", {
			"item_code": d.item_code, "qty": d.qty, "rate": d.rate,
			# BẪY ERPNext: `price_list_rate` phải là số TƯỜNG MINH, kể cả 0. Để
			# None thì `set_missing_item_details` tự tra bảng giá rồi thay rate.
			"price_list_rate": d.rate,
			"uom": d.uom, "stock_uom": d.stock_uom, "conversion_factor": 1,
			"warehouse": d.warehouse, "custom_nguon_gia": d.get("custom_nguon_gia"),
		})
	for d in so.get("custom_dat_ngoai") or []:
		bg.append("custom_dat_ngoai", {t: d.get(t) for t in TRUONG_DAT_NGOAI})

	if khoa_phong:
		kp = frappe.db.get_value(
			"Customer Department", khoa_phong, ["customer", "active"], as_dict=True
		)
		if not kp or kp.customer != customer or not kp.active:
			raise frappe.PermissionError("Khoa phòng không thuộc đơn vị của bạn.")
		bg.custom_khoa_phong = khoa_phong

	return _chen_khong_trung(bg, request_id)


def _chen_khong_trung(bg, request_id) -> dict:
	"""Cùng luật với `dat_hang._insert_so_idempotent`: hai lần bấm đua nhau thì
	lần thua nhận lại báo giá của lần thắng."""
	bg.flags.ignore_permissions = True
	try:
		bg.insert(ignore_permissions=True)
	except frappe.UniqueValidationError:
		cu = frappe.db.get_value(
			"Quotation", {"custom_request_id": request_id},
			["name", "grand_total"], as_dict=True, for_update=True,
		)
		if not cu:
			raise
		return {"bao_gia": cu.name, "da_ton_tai": True, "total": float(cu.grand_total or 0)}
	return {"bao_gia": bg.name, "da_ton_tai": False, "total": float(bg.grand_total or 0)}


def chot_gui_khach(doc, method=None) -> None:
	"""Hook `validate` — spec §4.2. Chỉ báo giá của cổng; báo giá nhân viên tự
	lập do họ tự chịu trách nhiệm về giá và hạn hiệu lực.

	Vào "Chờ khách đồng ý": chặn khi còn dòng gõ tay chưa khớp mã, còn dòng giữ
	chỗ, hoặc còn dòng chưa có đơn giá; qua chốt thì đóng mốc gửi và hạn hiệu
	lực. Quay về "Chờ Miyano báo giá" (thu hồi, khách sửa số lượng): xoá mốc và
	hạn, vì báo giá cũ không còn là thứ khách đang xem.
	"""
	from miyano_portal.portal_mua_le import (
		ITEM_GIU_CHO,
		hieu_luc_bao_gia_ngay,
		la_dong_giu_cho,
	)

	if doc.is_new() or doc.get("custom_nguon_don") != NGUON_CONG:
		return
	truoc, nay = _trang_thai_truoc(doc), doc.get("workflow_state")
	if truoc == nay:
		return
	if nay == TT_CHO_MIYANO and truoc == TT_CHO_KHACH:
		doc.valid_till = None
		doc.custom_ngay_gui_khach_duyet = None
		return
	if nay != TT_CHO_KHACH:
		return

	loi = []
	chua_khop = [
		d.get("ten_hang") or "?" for d in doc.get("custom_dat_ngoai") or []
		if not d.get("da_xu_ly")
	]
	if chua_khop:
		loi.append("còn hàng khách gõ tay chưa khớp mã: " + ", ".join(chua_khop))
	if any(la_dong_giu_cho(d.item_code) for d in doc.items):
		loi.append(f"còn dòng giữ chỗ kỹ thuật {ITEM_GIU_CHO}")
	thieu_gia = [
		d.item_code for d in doc.items
		if not la_dong_giu_cho(d.item_code) and flt(d.rate) <= 0
	]
	if thieu_gia:
		loi.append("còn mặt hàng chưa có đơn giá: " + ", ".join(thieu_gia))
	if loi:
		frappe.throw(
			"Chưa gửi khách được — " + "; ".join(loi) + ".", frappe.ValidationError
		)

	doc.custom_ngay_gui_khach_duyet = now_datetime()
	doc.valid_till = add_days(nowdate(), hieu_luc_bao_gia_ngay())
