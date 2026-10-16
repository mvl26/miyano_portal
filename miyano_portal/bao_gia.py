"""Yêu cầu báo giá bằng Quotation (spec 2026-10-12).

Một yêu cầu báo giá của khách là một Quotation đi workflow `WORKFLOW`. Sales
Order chỉ sinh ra khi khách đồng ý (`dong_y`). Tài khoản cổng KHÔNG có DocPerm
trên Quotation: mọi hàm ghi ở đây chạy bước chuyển trạng thái dưới
`nang_quyen.quyen_he_thong()`, và NGƯỜI GỌI (endpoint trong `api/portal.py`)
phải kiểm quyền của khách trên đúng báo giá đó trước khi gọi vào đây.
"""

import math

import frappe
from frappe.utils import add_days, flt, formatdate, getdate, now_datetime, nowdate

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
# Lối ra duy nhất của "Báo giá hết hạn" (Sales Manager). "Khách từ chối" và
# "Miyano từ chối" không có lối ra: đó là trạng thái kết thúc.
HD_MO_LAI = "Mở lại"

# Báo giá theo đợt (spec 2026-10-15). Phiếu gốc đã tách hết dòng → "Đã báo
# hết"; dòng của một đợt bị từ chối/hết hạn quay về thì phiếu mở lại. Hai bước
# đó do CODE áp (`bao_gia_theo_dot`), khai vai `Administrator` nên nhân viên
# không thấy thành nút; code áp chúng dưới `nang_quyen.quyen_he_thong()`.
TT_DA_BAO_HET = "Đã báo hết"
TT_HUY_CON_LAI = "Đã huỷ phần còn lại"
HD_HUY_CON_LAI = "Huỷ phần còn lại"
HD_BAO_HET = "Hệ thống: đã báo hết"
HD_CON_HANG = "Hệ thống: có hàng trả về"
# Giá trị `custom_nguoi_huy_con_lai` khi khách huỷ trên cổng.
NGUOI_KHACH = "Khách"

LY_DO_TOI_THIEU = 10


_san_sang_cache: bool | None = None


def san_sang() -> bool:
	"""Có cột `Quotation.custom_request_id` THẬT trong CSDL không (patch v1_42).

	Lưới an toàn lúc triển khai, cùng khuôn `portal_context.
	cot_ten_don_hang_ton_tai()` (cache cấp tiến trình): mã mới chạy trên site
	CHƯA `bench migrate` mà hỏi cột này là MariaDB ném 1054, và hai đường đặt
	hàng hỏi nó cho MỌI giỏ — kể cả giỏ toàn hàng có giá. Chưa sẵn sàng thì
	hai đường đó đi đường cũ (`dat_hang.tao_sales_order`, đơn "Mua lẻ") và
	không đụng tới bảng Quotation. Không `log_error`: thiếu cột chỉ làm cổng
	chạy theo luồng cũ, không che lỗ quyền nào."""
	global _san_sang_cache
	if _san_sang_cache is None:
		_san_sang_cache = bool(frappe.db.has_column("Quotation", "custom_request_id"))
	return _san_sang_cache


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
			"chuyển trạng thái. Nhập ở mục «Cổng khách hàng» → ô «Lý do từ chối» rồi "
			"lưu, sau đó bấm lại «Từ chối».",
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
	for d in so.flags.dong_dat_ngoai or []:
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

	Vào "Chờ khách đồng ý": chặn khi còn dòng gõ tay chưa khớp mã, dòng hàng
	sinh từ phép khớp đã bị xoá/đổi mã, còn dòng giữ chỗ, hoặc còn dòng chưa có
	đơn giá; qua chốt thì đóng mốc gửi và hạn hiệu
	lực. Quay về "Chờ Miyano báo giá" (thu hồi, khách sửa số lượng, hoặc mở
	lại một báo giá hết hạn): xoá mốc và hạn, vì báo giá cũ không còn là thứ
	khách đang xem — lần gửi lại đóng hạn mới. Đơn giá giữ nguyên làm gợi ý.
	"""
	from miyano_portal.portal_mua_le import (
		ITEM_GIU_CHO,
		hieu_luc_bao_gia_ngay,
		kiem_dong_chuyen_con_tren_don,
		la_dong_giu_cho,
	)

	if doc.is_new() or doc.get("custom_nguon_don") != NGUON_CONG:
		return
	truoc, nay = _trang_thai_truoc(doc), doc.get("workflow_state")
	if truoc == nay:
		return
	if nay == TT_CHO_MIYANO and truoc in (TT_CHO_KHACH, TT_HET_HAN):
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
	mat_dong = kiem_dong_chuyen_con_tren_don(doc)
	if mat_dong:
		loi.append(
			"dòng hàng sinh từ hàng khách gõ tay đã bị xoá hoặc đổi mã ("
			+ ", ".join(mat_dong) + ") — thêm lại dòng hàng, hoặc bỏ mã khớp rồi khớp lại"
		)
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


def qua_han(bg, hom_nay=None) -> bool:
	"""Báo giá đã quá `valid_till`. Không có hạn thì không bao giờ quá hạn."""
	if not bg.get("valid_till"):
		return False
	return getdate(bg.valid_till) < getdate(hom_nay or nowdate())


def don_cua_bao_gia(bg, khoa: bool = False) -> str | None:
	"""Sales Order đã sinh từ báo giá này, tra theo mã yêu cầu `<rid>:don`.

	`khoa=True` đọc bằng `for update`. Dưới REPEATABLE READ một phép đọc thường
	nhìn ảnh chụp lấy từ ĐẦU request: request thứ hai của một cú bấm đôi được
	đánh thức sau khi request đầu commit vẫn KHÔNG thấy đơn vừa sinh, và trả
	`sales_order = None` cho khách. Đọc có khoá là đọc dữ liệu hiện tại."""
	rid = bg.get("custom_request_id")
	if not rid:
		return None
	return frappe.db.get_value(
		"Sales Order", {"custom_request_id": rid + HAU_TO_DON}, "name", for_update=khoa
	)


def bao_gia_cua_don(so) -> str | None:
	"""Chiều ngược của `don_cua_bao_gia`: Quotation của cổng đã sinh ra đơn
	"Theo báo giá" này, tra theo cùng mã yêu cầu (đơn mang `<rid>:don`).

	Báo giá phải cùng khách với đơn: mã yêu cầu là dữ liệu trên chứng từ,
	không phải bằng chứng sở hữu. NGƯỜI GỌI đã kiểm quyền trên đơn."""
	rid = so.get("custom_request_id") or ""
	if so.get("custom_loai_don") != LOAI_DON_THEO_BAO_GIA or not rid.endswith(HAU_TO_DON):
		return None
	return frappe.db.get_value(
		"Quotation",
		{
			"custom_request_id": rid[: -len(HAU_TO_DON)], "custom_nguon_don": NGUON_CONG,
			"party_name": so.get("customer"),
		},
		"name",
	)


def dong_go_tay_da_khop_cua_don(so) -> list:
	"""Các dòng khách gõ tay ĐÃ KHỚP MÃ trên báo giá nguồn của một đơn "Theo
	báo giá", chỉ những dòng mà mã khớp còn nằm trên đơn.

	`Quotation.custom_dat_ngoai` là `no_copy` nên đơn sinh ra không mang dòng
	gõ tay nào; không có hàm này thì cổng không biết mặt hàng nào trên đơn ứng
	với thứ khách đã mô tả. Trả dòng bảng con; người gọi tự chọn trường để lộ."""
	ten = bao_gia_cua_don(so)
	if not ten:
		return []
	tren_don = {d.item_code for d in so.get("items") or []}
	return [
		d for d in frappe.get_doc("Quotation", ten).get("custom_dat_ngoai") or []
		if d.da_xu_ly and d.item_khop in tren_don
	]


def _don_con_song(ten: str) -> bool:
	"""Đơn còn đi tiếp được: chưa huỷ (docstatus 2) và không nằm ở trạng thái
	KẾT THÚC «Từ chối» của workflow đơn hàng — trạng thái đó vẫn ở docstatus
	0, nên chỉ nhìn docstatus là coi một đơn đã chết là còn sống. (Đơn «Khách
	huỷ» cũ đã được patch v1_44 chuyển sang «Từ chối».)"""
	# Nhập muộn: `api.portal` nhập module này ở đầu file.
	from miyano_portal.api.portal import WF_TU_CHOI

	don = frappe.db.get_value("Sales Order", ten, ["docstatus", "workflow_state"], as_dict=True)
	if not don or don.docstatus == 2:
		return False
	return don.workflow_state != WF_TU_CHOI


def chan_huy_khi_con_don(doc, method=None) -> None:
	"""Hook `before_cancel` của Quotation — chỉ báo giá của cổng.

	Đơn sinh từ báo giá còn nháp thì ERPNext không coi là ràng buộc (nó chỉ
	nhìn chứng từ đã Submit): huỷ báo giá lúc đó để lại một đơn đang chạy và
	phiếu gốc trỏ vào một báo giá đã huỷ. Đơn đã chết (`_don_con_song`) thì
	không còn gì để giữ. Lời nhắc KHÔNG bảo xoá đơn nháp: phiếu gốc trỏ vào
	đơn nên Frappe không cho xoá."""
	if doc.get("custom_nguon_don") != NGUON_CONG:
		return
	don = don_cua_bao_gia(doc)
	if don and _don_con_song(don):
		frappe.throw(
			f"Báo giá {doc.name} của cổng khách hàng đã sinh đơn hàng {don} và đơn "
			f"đó còn hiệu lực. Trước khi huỷ báo giá, phải huỷ đơn hàng {don} (nếu "
			"đã xác nhận) hoặc bấm «Từ chối» trên đơn (nếu còn chờ xác nhận).",
			frappe.ValidationError,
		)


def _la_ban_sua_doi_cua(doc, rid_don: str) -> bool:
	"""`doc` là bản «Amend» (trực tiếp hoặc qua nhiều đời) của đơn mang mã yêu
	cầu `rid_don`. Mã yêu cầu của đơn là `unique` + `no_copy`, nên không dựa
	vào việc bản sửa đổi còn mang nó; lần ngược `amended_from` tới đơn gốc."""
	ten = doc.get("amended_from")
	for _ in range(20):
		if not ten:
			return False
		goc = frappe.db.get_value(
			"Sales Order", ten, ["custom_request_id", "amended_from"], as_dict=True
		)
		if not goc:
			return False
		if goc.custom_request_id == rid_don:
			return True
		ten = goc.amended_from
	return False


def chan_don_thu_hai_tu_bao_gia_cong(doc, method=None) -> None:
	"""Hook `validate` của Sales Order.

	Báo giá của cổng chỉ sinh đơn qua `dong_y` → `_sinh_don`, nơi đơn nhận mã
	yêu cầu `<rid của báo giá>:don`. Dòng mang `prevdoc_docname` trỏ về một báo
	giá của cổng vì thế chỉ được nằm trên ĐÚNG đơn đó, hoặc trên bản «Amend»
	của nó. Hai lối khác trên Desk đi cùng mapper mà không có mã đó: «Tạo →
	Đơn bán hàng» trên báo giá (đơn mới) và «Lấy mặt hàng từ → Báo giá» trên
	một đơn nháp ĐÃ LƯU — nên chốt ở `validate`, không ở `before_insert`.
	ERPNext chỉ trừ số "đã đặt" theo đơn ĐÃ Submit, nên khi đơn đầu còn nháp
	cả hai lối đều cho ra đủ mọi dòng lần nữa.

	Không đụng: báo giá nội bộ, đơn không trỏ về báo giá nào."""
	nguon = {d.get("prevdoc_docname") for d in doc.get("items") or []} - {None, ""}
	if not nguon:
		return
	for bg in frappe.get_all(
		"Quotation", filters={"name": ["in", list(nguon)], "custom_nguon_don": NGUON_CONG},
		fields=["name", "custom_request_id"],
	):
		rid_don = (bg.custom_request_id or "") + HAU_TO_DON
		if bg.custom_request_id and (
			doc.get("custom_request_id") == rid_don or _la_ban_sua_doi_cua(doc, rid_don)
		):
			continue
		don = don_cua_bao_gia(bg)
		if don:
			frappe.throw(
				f"Báo giá của cổng đã có đơn hàng {don} — không tạo đơn thứ hai.",
				frappe.ValidationError,
			)
		frappe.throw(
			f"Đơn hàng của báo giá {bg.name} chỉ sinh ra khi khách đồng ý trên cổng "
			"— không tạo tay từ báo giá của cổng.",
			frappe.ValidationError,
		)


def _dam_bao_cua_cong(bg) -> None:
	"""Báo giá nhân viên tự lập trên Desk không có mã yêu cầu để tra đơn và
	không đi vòng khách đồng ý/từ chối/sửa của cổng: từ chối trước mọi nhánh."""
	if bg.get("custom_nguon_don") != NGUON_CONG or not bg.get("custom_request_id"):
		frappe.throw("Báo giá này không phải của cổng khách hàng.", frappe.ValidationError)


def _dam_bao_cho_khach(bg) -> None:
	if bg.get("workflow_state") != TT_CHO_KHACH:
		frappe.throw(
			"Báo giá này không ở trạng thái chờ quý khách đồng ý.", frappe.ValidationError
		)


def _dam_bao_con_han(bg) -> None:
	if qua_han(bg):
		frappe.local.response["ly_do"] = "qua_han_hieu_luc"
		frappe.throw(
			f"Báo giá {bg.name} đã hết hiệu lực ngày "
			f"{formatdate(bg.valid_till, 'dd/mm/yyyy')}. Gửi yêu cầu báo giá mới nếu "
			"vẫn cần hàng.",
			frappe.ValidationError,
		)


def _ngay_giao(phieu) -> str:
	"""Ngày cần hàng của phiếu gốc nếu chưa trôi qua, không thì ngày mặc định.
	Báo giá có thể nằm chờ nhiều ngày; chặn khách đồng ý chỉ vì ngày họ chọn
	lúc gửi yêu cầu đã qua là chặn nhầm chỗ."""
	from miyano_portal.portal_dat_hang import ngay_giao_mac_dinh

	ngay = phieu.get("ngay_can") if phieu else None
	if ngay and getdate(ngay) >= getdate(nowdate()):
		return ngay
	return ngay_giao_mac_dinh()


def _sinh_don(bg):
	"""Sinh Sales Order "Theo báo giá" từ một Quotation ĐÃ Submit, đưa nó tới
	"Chờ Miyano xác nhận". Gọi trong khối `quyen_he_thong()`.

	Dùng bản nội bộ `_make_sales_order`: bản whitelist kiểm quyền người gọi,
	mà khách không có quyền nào trên Quotation.
	"""
	from erpnext.selling.doctype.quotation.quotation import _make_sales_order
	from frappe.model.naming import validate_name
	from frappe.model.workflow import apply_workflow

	from miyano_portal.bang_gia_khach import NGUON_BAO_GIA
	from miyano_portal.dat_hang import _resolve_item_warehouse
	from miyano_portal.portal_mua_le import xoa_chenh_lech_gia

	phieu = None
	if bg.get("custom_de_xuat"):
		phieu = frappe.db.get_value(
			"Portal De Xuat Mua", bg.custom_de_xuat,
			["ngay_can", "ghi_chu", "ma_de_xuat"], as_dict=True,
		)
	ngay = _ngay_giao(phieu)

	so = _make_sales_order(bg.name, ignore_permissions=True)
	so.delivery_date = ngay
	so.custom_nguon_don = NGUON_CONG
	so.custom_loai_don = LOAI_DON_THEO_BAO_GIA
	so.custom_request_id = bg.custom_request_id + HAU_TO_DON
	so.custom_hdnt = None
	so.ignore_pricing_rule = 1
	# BẪY ERPNext: mapper chép lịch thanh toán của báo giá, mà hạn của nó là
	# NGÀY LẬP báo giá. Đơn lập hôm nay: đồng ý khác ngày là bị chặn "Due Date
	# ... cannot be before Posting Date". Xoá để `set_payment_schedule` dựng lại.
	so.payment_schedule = []
	# Gán tường minh, không dựa vào việc mapper chép trường cùng tên.
	so.custom_khoa_phong = bg.get("custom_khoa_phong")
	so.custom_de_xuat = bg.get("custom_de_xuat")
	so.custom_ten_don_hang = bg.get("custom_ten_don_hang") or ""
	if phieu:
		so.custom_ma_tra_cuu = phieu.ma_de_xuat
		so.custom_yeu_cau_khach = phieu.ghi_chu
	for d in so.items:
		d.delivery_date = ngay
		d.warehouse = d.warehouse or _resolve_item_warehouse(d.item_code, so.company)
		# Đơn giá khách đã đồng ý là đơn giá của đơn. Đặt `price_list_rate`
		# bằng nó và xoá margin/chiết khấu, nếu không ERPNext tính lại `rate`
		# từ giá bảng khi lưu.
		d.price_list_rate = d.rate
		xoa_chenh_lech_gia(d)
		d.custom_nguon_gia = NGUON_BAO_GIA
		d.custom_gia_khach_dong_y = flt(d.rate)
	# Mã đơn = mã của khách trên phiếu, như đơn sinh từ `duyet_va_tao_don`.
	if phieu and phieu.ma_de_xuat and not frappe.db.exists("Sales Order", phieu.ma_de_xuat):
		so.name = validate_name("Sales Order", phieu.ma_de_xuat)
		so.flags.name_set = True
	so.flags.ignore_permissions = True
	so.insert(ignore_permissions=True)
	# Đơn mới sinh ở trạng thái đầu của workflow. Vòng báo giá đã xong trên
	# Quotation nên đưa thẳng sang "Chờ Miyano xác nhận" bằng bước chuyển thật.
	return apply_workflow(so, "Gửi duyệt")


def dong_y(ten: str) -> dict:
	"""Khách đồng ý báo giá (spec §4.4). NGƯỜI GỌI đã kiểm quyền của khách.

	Submit Quotation, sinh Sales Order và gắn đơn vào phiếu gốc là MỘT đơn vị:
	hỏng bước nào thì lùi cả ba. Ghi giá vào Price List đứng ngoài đơn vị đó —
	lỗi ở đấy chỉ được ghi Error Log và báo nhân viên.
	"""
	from frappe.model.workflow import apply_workflow

	from miyano_portal import bang_gia_khach, nhat_ky
	from miyano_portal.nang_quyen import quyen_he_thong
	from miyano_portal.portal_thong_bao import bao_loi_ghi_gia

	# Khoá dòng: hai người cùng bấm thì người sau chờ, rồi thấy "đã đồng ý".
	bg = frappe.get_doc("Quotation", ten, for_update=True)
	_dam_bao_cua_cong(bg)
	if bg.get("workflow_state") == TT_DA_DONG_Y:
		return {
			"bao_gia": bg.name, "sales_order": don_cua_bao_gia(bg, khoa=True),
			"da_ton_tai": True, "trang_thai_moi": TT_DA_DONG_Y,
		}
	_dam_bao_cho_khach(bg)
	_dam_bao_con_han(bg)

	nguoi_bam = frappe.session.user
	khach = bg.party_name
	frappe.db.savepoint("bao_gia_dong_y")
	try:
		with quyen_he_thong():
			frappe.flags.bao_gia_dong_y_qua_cong = bg.name
			try:
				bg = apply_workflow(bg, HD_KHACH_DONG_Y)
			finally:
				frappe.flags.bao_gia_dong_y_qua_cong = None
			bg.add_comment("Comment", f"{HD_KHACH_DONG_Y} bởi {nguoi_bam}")
			so = _sinh_don(bg)
		if bg.get("custom_de_xuat"):
			# Báo giá theo đợt: một phiếu ra nhiều đơn. Ghi một dòng
			# `don_hang`; `sales_order` của phiếu chỉ đặt khi còn trống.
			from miyano_portal.bao_gia_theo_dot import them_don_hang

			them_don_hang(
				bg.custom_de_xuat, so.name, bg.name, int(bg.get("custom_so_dot") or 0)
			)
	except Exception:
		frappe.db.rollback(save_point="bao_gia_dong_y")
		raise

	try:
		frappe.db.savepoint("bao_gia_ghi_gia")
		so.reload()
		bang_gia_khach.ghi_gia_da_dong_y(so, nguoi_dong_y=nguoi_bam)
	except Exception:
		loi = frappe.get_traceback(with_context=True)
		# Lùi savepoint mà hỏng là máy chủ đã lùi CẢ giao dịch (deadlock...):
		# đơn vừa sinh không còn nữa. Để lỗi nổi lên, không báo thành công.
		frappe.db.rollback(save_point="bao_gia_ghi_gia")
		frappe.log_error(
			title=f"Không ghi được giá đã đồng ý của đơn {so.name} vào Price List",
			message=loi, reference_doctype="Sales Order", reference_name=so.name,
		)
		bao_loi_ghi_gia(khach, so.name)

	nhat_ky.ghi(
		nhat_ky.SK_KHACH_DONG_Y, customer=khach,
		khoa_phong=bg.get("custom_khoa_phong"), de_xuat=bg.get("custom_de_xuat"),
		sales_order=so.name, vai=nhat_ky.VAI_QUAN_LY,
	)
	return {
		"bao_gia": bg.name, "sales_order": so.name,
		"da_ton_tai": False, "trang_thai_moi": bg.get("workflow_state"),
	}


def bao_nhan_vien(bg, tieu_de: str, noi_dung: str) -> int:
	"""Notification Log cho nhân viên phụ trách khách (đường lui: Sales
	Manager), trỏ tới Quotation. Không bao giờ ném lỗi: chạy sau một việc ĐÃ
	thành công. Trả số thông báo vừa tạo."""
	try:
		from miyano_portal.portal_thong_bao import _nguoi_nhan_kiem_hang

		dem = 0
		for nguoi in _nguoi_nhan_kiem_hang(bg.party_name):
			frappe.get_doc({
				"doctype": "Notification Log", "subject": f"{tieu_de}: {bg.name}",
				"for_user": nguoi, "type": "Alert",
				"document_type": "Quotation", "document_name": bg.name,
				"email_content": noi_dung,
			}).insert(ignore_permissions=True)
			dem += 1
		return dem
	except Exception:
		frappe.log_error(
			title=f"bao_gia: không báo được nhân viên về {bg.name}",
			message=frappe.get_traceback(),
		)
		return 0


def tu_choi(ten: str, ly_do: str | None = None) -> dict:
	"""Khách từ chối báo giá. Lý do tuỳ chọn. NGƯỜI GỌI đã kiểm quyền."""
	from frappe.model.workflow import apply_workflow

	from miyano_portal import nhat_ky
	from miyano_portal.nang_quyen import quyen_he_thong

	bg = frappe.get_doc("Quotation", ten, for_update=True)
	_dam_bao_cua_cong(bg)
	_dam_bao_cho_khach(bg)
	ly_do = (ly_do or "").strip()
	nguoi_bam = frappe.session.user
	if ly_do:
		# Ghi thẳng: `apply_workflow` nạp lại chứng từ từ CSDL trước khi lưu.
		frappe.db.set_value(
			"Quotation", bg.name, "custom_ly_do_tu_choi", ly_do, update_modified=False
		)
	with quyen_he_thong():
		bg = apply_workflow(bg, HD_KHACH_TU_CHOI)
		bg.add_comment(
			"Comment",
			f"{HD_KHACH_TU_CHOI} bởi {nguoi_bam}" + (f" — lý do: {ly_do}" if ly_do else ""),
		)
	bao_nhan_vien(
		bg, "Portal - Khách từ chối báo giá",
		f"Khách hàng <b>{bg.party_name}</b> đã từ chối báo giá <b>{bg.name}</b>."
		+ (f"<br>Lý do: {frappe.utils.escape_html(ly_do)}" if ly_do else ""),
	)
	nhat_ky.ghi(
		nhat_ky.SK_KHACH_KHONG_DONG_Y, customer=bg.party_name,
		khoa_phong=bg.get("custom_khoa_phong"), de_xuat=bg.get("custom_de_xuat"),
		vai=nhat_ky.VAI_QUAN_LY, ghi_chu=ly_do or None,
	)
	return {"trang_thai_moi": bg.get("workflow_state")}


def sua_so_luong(ten: str, dong: list) -> dict:
	"""Khách sửa số lượng các dòng ĐÃ CÓ trên báo giá (spec §4.3). Không thêm,
	không xoá, không đặt về 0. Đơn giá giữ nguyên làm gợi ý; báo giá quay về
	"Chờ Miyano báo giá" và hook `chot_gui_khach` xoá hạn hiệu lực.
	NGƯỜI GỌI đã kiểm quyền."""
	from frappe.model.workflow import apply_workflow

	from miyano_portal import nhat_ky
	from miyano_portal.nang_quyen import quyen_he_thong
	from miyano_portal.portal_dat_hang import kiem_boi_so
	from miyano_portal.portal_mua_le import la_dong_giu_cho

	bg = frappe.get_doc("Quotation", ten, for_update=True)
	_dam_bao_cua_cong(bg)
	_dam_bao_cho_khach(bg)
	_dam_bao_con_han(bg)
	if isinstance(dong, str):
		try:
			dong = frappe.parse_json(dong)
		except ValueError:
			dong = None
	# Thân request là của client: sai hình dạng phải ra một lời từ chối rõ,
	# không phải AttributeError (lỗi 500) từ `.get` trên thứ không phải dict.
	if not isinstance(dong, list) or not all(isinstance(yc, dict) for yc in dong):
		frappe.throw("Danh sách dòng sửa số lượng không hợp lệ.", frappe.ValidationError)

	theo_ten = {d.name: d for d in bg.items if not la_dong_giu_cho(d.item_code)}
	thay_doi: list[str] = []
	ap_dung: dict[str, float] = {}
	for yc in dong:
		hang = theo_ten.get(yc.get("name"))
		if not hang:
			frappe.throw(
				"Không tìm thấy dòng hàng trong báo giá — không thêm được dòng mới "
				"qua sửa số lượng.",
				frappe.ValidationError,
			)
		try:
			moi = float(yc.get("qty"))
		except (TypeError, ValueError):
			moi = math.nan
		# `float("nan")` / `float("inf")` đổi được thành số nhưng không phải số
		# lượng: nan lọt mọi phép so sánh bên dưới.
		if not math.isfinite(moi):
			frappe.throw(f"{hang.item_code}: số lượng không hợp lệ.", frappe.ValidationError)
		if moi <= 0:
			frappe.throw(
				f"{hang.item_code}: số lượng phải lớn hơn 0. Không cần mặt hàng "
				"nào nữa thì từ chối báo giá.",
				frappe.ValidationError,
			)
		loi = kiem_boi_so(hang.item_code, moi)
		if loi:
			frappe.throw(loi["thong_diep"], frappe.ValidationError)
		if flt(hang.qty) == moi:
			continue
		thay_doi.append(f"{hang.item_code}: {flt(hang.qty):g} → {moi:g}")
		hang.qty = moi
		ap_dung[hang.item_code] = moi
	if not thay_doi:
		frappe.throw("Không có thay đổi số lượng nào để gửi.", frappe.ValidationError)

	nguoi_bam = frappe.session.user
	with quyen_he_thong():
		# Lưu TRƯỚC: `apply_workflow` nạp lại chứng từ từ CSDL ngay đầu hàm.
		bg.save()
		bg = apply_workflow(bg, HD_KHACH_SUA_SL)
		bg.add_comment(
			"Comment",
			f"[Portal] {HD_KHACH_SUA_SL} bởi {nguoi_bam}:<br>" + "<br>".join(thay_doi),
		)
	bao_nhan_vien(
		bg, "Portal - Khách sửa số lượng báo giá",
		f"Khách hàng <b>{bg.party_name}</b> vừa sửa số lượng trên báo giá "
		f"<b>{bg.name}</b>; báo giá đã về \"{TT_CHO_MIYANO}\" để xem lại giá:<br>"
		+ "<br>".join(thay_doi),
	)
	nhat_ky.ghi(
		nhat_ky.SK_KHACH_GUI_LAI_BAO_GIA, customer=bg.party_name,
		khoa_phong=bg.get("custom_khoa_phong"), de_xuat=bg.get("custom_de_xuat"),
		vai=nhat_ky.VAI_QUAN_LY, ghi_chu=f"{len(thay_doi)} dòng thay đổi",
	)
	return {
		"trang_thai_moi": bg.get("workflow_state"), "thay_doi": thay_doi, "ap_dung": ap_dung,
	}


# Trạng thái MỚI của báo giá → sự kiện nhật ký. Bước phía khách (đồng ý, từ
# chối, sửa số lượng) tự ghi ở hàm của nó, kèm người bấm.
_SU_KIEN_THEO_TRANG_THAI = {
	TT_CHO_KHACH: "SK_MIYANO_BAO_GIA",
	TT_MIYANO_TU_CHOI: "SK_MIYANO_TU_CHOI",
	TT_HET_HAN: "SK_BAO_GIA_HET_HAN",
}


def ghi_nhat_ky_chuyen_trang_thai(doc, method=None) -> None:
	"""Hook `on_update` — một dòng nhật ký khi báo giá của cổng CHUYỂN tới một
	trạng thái trong bảng trên. Chỉ khi trạng thái thật sự đổi."""
	from miyano_portal import nhat_ky

	if doc.get("custom_nguon_don") != NGUON_CONG:
		return
	truoc, nay = _trang_thai_truoc(doc), doc.get("workflow_state")
	if not truoc or truoc == nay or nay not in _SU_KIEN_THEO_TRANG_THAI:
		return
	nhat_ky.ghi(
		getattr(nhat_ky, _SU_KIEN_THEO_TRANG_THAI[nay]), customer=doc.party_name,
		khoa_phong=doc.get("custom_khoa_phong"), de_xuat=doc.get("custom_de_xuat"),
		vai=nhat_ky.VAI_HE_THONG if nay == TT_HET_HAN else nhat_ky.VAI_MIYANO,
		ghi_chu=(doc.get("custom_ly_do_tu_choi") or None) if nay == TT_MIYANO_TU_CHOI else None,
	)


def _gui_email_het_han(bg, han) -> None:
	"""Email hai phía. Lỗi gửi mail không được chặn việc đóng báo giá."""
	from miyano_portal.portal_bao_gia import _email_sales_phu_trach

	han_str = formatdate(han, "dd/mm/yyyy")
	noi_dung = (
		f"<p>Báo giá <b>{bg.name}</b> (khách hàng {bg.party_name}) đã hết hiệu lực "
		f"ngày <b>{han_str}</b> mà chưa được đồng ý trên cổng khách hàng.</p>"
		"<p>Nếu vẫn cần hàng, vui lòng gửi yêu cầu báo giá mới.</p>"
	)
	for nguoi_nhan in {bg.get("contact_email"), _email_sales_phu_trach(bg.party_name)}:
		if not nguoi_nhan:
			continue
		try:
			frappe.sendmail(
				recipients=[nguoi_nhan], subject=f"Báo giá {bg.name} đã hết hiệu lực",
				message=noi_dung, reference_doctype="Quotation", reference_name=bg.name,
				now=False,
			)
		except Exception:
			frappe.log_error(
				title="bao_gia: gửi email hết hạn thất bại", message=frappe.get_traceback()
			)


def quet_het_han(moc=None) -> int:
	"""Spec §4.6 — đóng mọi báo giá CỦA CỔNG ở "Chờ khách đồng ý" có `valid_till` trước
	`moc` (mặc định hôm nay). Job hằng ngày (`hooks.scheduler_events`), chạy
	dưới Administrator nên không cần nâng quyền.
	Job gốc `set_expired_status` của ERPNext chỉ đụng Quotation đã Submit.

	Mỗi báo giá một savepoint: một báo giá lưu hỏng được lùi riêng, ghi Error
	Log rồi bỏ qua — không làm dừng cả đợt quét. Trả số báo giá ĐÃ đóng."""
	from frappe.model.workflow import apply_workflow

	hom_nay = getdate(moc) if moc else getdate(nowdate())
	dem = 0
	for ten in frappe.get_all(
		"Quotation",
		# CHỈ báo giá của cổng. Form Quotation của ERPNext tự điền `valid_till`
		# (+1 tháng) cho báo giá nhân viên tự lập; quét cả chúng là tự đóng
		# những báo giá không ai coi là "hết hạn theo cổng".
		filters={
			"workflow_state": TT_CHO_KHACH, "docstatus": 0,
			"custom_nguon_don": NGUON_CONG, "valid_till": ("<", hom_nay),
		},
		pluck="name",
	):
		frappe.db.savepoint("bao_gia_het_han")
		try:
			bg = frappe.get_doc("Quotation", ten)
			han = bg.valid_till
			bg = apply_workflow(bg, HD_HET_HAN)
			bg.add_comment(
				"Comment",
				f"[Hệ thống] Báo giá hết hiệu lực ngày {formatdate(han, 'dd/mm/yyyy')} — tự đóng.",
			)
		except Exception:
			loi = frappe.get_traceback(with_context=True)
			frappe.db.rollback(save_point="bao_gia_het_han")
			frappe.log_error(
				title=f"bao_gia: không đóng được báo giá hết hạn {ten}", message=loi,
				reference_doctype="Quotation", reference_name=ten,
			)
			continue
		_gui_email_het_han(bg, han)
		dem += 1
	return dem
