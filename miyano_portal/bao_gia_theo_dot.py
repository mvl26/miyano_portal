"""Báo giá theo đợt trên một yêu cầu báo giá (spec 2026-10-15).

Phiếu gốc là Quotation của cổng do `bao_gia.tao_bao_gia` dựng. Nhân viên tách
từng nhóm dòng ĐÃ CÓ GIÁ thành một Quotation con ("đợt", `custom_phieu_goc`)
đi nguyên workflow của `bao_gia`; phiếu gốc giữ phần chưa báo và không bao giờ
gửi khách nữa (D7). Mọi luật về đợt nằm ở module này; `bao_gia` chỉ gọi sang
ở `dong_y` (ghi bảng `don_hang`).
"""

import frappe
from frappe.utils import cint, flt

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


# Trường đầu phiếu chép từ phiếu gốc sang đợt (spec §3.1). Các `custom_*` là
# `no_copy` nên KHÔNG dùng `frappe.copy_doc`: dựng đợt tường minh.
TRUONG_DAU_PHIEU = (
	"quotation_to", "party_name", "company", "currency", "selling_price_list",
	"order_type", "customer_address", "shipping_address_name", "contact_person",
	"contact_email", "custom_nguon_don", "custom_de_xuat", "custom_khoa_phong",
	"custom_ten_don_hang",
)
# Trường của một dòng hàng khi đi từ phiếu gốc sang đợt và ngược lại.
TRUONG_DONG = (
	"item_code", "item_name", "description", "qty", "rate", "uom", "stock_uom",
	"conversion_factor", "warehouse", "custom_nguon_gia",
)


def _dong_moi(d) -> dict:
	kq = {t: d.get(t) for t in TRUONG_DONG}
	# BẪY ERPNext (xem `bao_gia.tao_bao_gia`): `price_list_rate` phải tường minh,
	# không thì `set_missing_item_details` tra bảng giá và thay đơn giá vừa báo.
	kq["price_list_rate"] = flt(d.get("rate"))
	return kq


def la_phieu_goc_cong(doc) -> bool:
	return doc.get("custom_nguon_don") == bao_gia.NGUON_CONG and not doc.get("custom_phieu_goc")


def co_dot(ten: str) -> bool:
	"""Phiếu `ten` đã tách ít nhất một đợt."""
	if not ten or not san_sang():
		return False
	return bool(frappe.db.exists("Quotation", {"custom_phieu_goc": ten}))


def _con_dong_chua_bao(goc) -> bool:
	"""Còn dòng hàng, hoặc còn dòng khách gõ tay chưa khớp mã (§4.1 bước 3, 5).

	Bỏ qua dòng giữ chỗ: phiếu gốc hết dòng hàng mà còn dòng gõ tay thì
	`portal_mua_le._dam_bao_con_dong_hang` (hook `before_validate`) tự chèn
	một dòng `ITEM_GIU_CHO` — dòng đó không phải mặt hàng chờ báo."""
	from miyano_portal.portal_mua_le import la_dong_giu_cho

	return any(not la_dong_giu_cho(d.item_code) for d in goc.get("items") or []) or any(
		not d.get("da_xu_ly") for d in goc.get("custom_dat_ngoai") or []
	)


def cho_phep_phieu_goc_rong(doc, method=None) -> None:
	"""Hook `before_validate` của Quotation. `items` là bắt buộc; phiếu gốc đã
	tách hết dòng sang các đợt thì rỗng là ĐÚNG — lưu nó (chuyển "Đã báo hết",
	nhận dòng trả về, huỷ phần còn lại) không được vấp chốt bắt buộc. Chạy ở
	`before_validate` vì Frappe kiểm bắt buộc ngay sau bước đó."""
	if doc.get("items") or doc.is_new() or not la_phieu_goc_cong(doc):
		return
	if co_dot(doc.name):
		doc.flags.ignore_mandatory = True


def kiem_chuyen_theo_dot(doc, method=None) -> None:
	"""Hook `validate` của Quotation — các chốt chuyển trạng thái của báo giá
	theo đợt (spec §3.2, §4.1, §4.3). Frappe v15 không có `before_transition`:
	so trạng thái trước/sau như `bao_gia.kiem_ly_do_tu_choi`."""
	if doc.is_new() or doc.get("custom_nguon_don") != bao_gia.NGUON_CONG or not san_sang():
		return
	truoc, nay = bao_gia._trang_thai_truoc(doc), doc.get("workflow_state")
	if truoc == nay:
		return
	if doc.get("custom_da_tra_ve"):
		frappe.throw(
			f"Đợt {doc.name} đã trả các mặt hàng về phiếu gốc {doc.custom_phieu_goc} — "
			"không mở lại được. Muốn báo lại thì tách đợt mới từ phiếu gốc.",
			frappe.ValidationError,
		)
	if nay == bao_gia.TT_HUY_CON_LAI:
		_kiem_huy_con_lai(doc)
		return
	if doc.get("custom_phieu_goc") or not co_dot(doc.name):
		return
	if nay in (bao_gia.TT_CHO_KHACH, bao_gia.TT_MIYANO_TU_CHOI):
		frappe.throw(
			"Phiếu đã báo theo đợt — dùng nút «Báo giá đợt này» để gửi khách các mặt "
			"hàng còn lại, hoặc «Huỷ phần còn lại» nếu không báo nữa.",
			frappe.ValidationError,
		)


def _dung_dot(goc, dong: list, so_dot: int):
	d = frappe.new_doc("Quotation")
	for t in TRUONG_DAU_PHIEU:
		if goc.get(t) is not None:
			d.set(t, goc.get(t))
	d.transaction_date = frappe.utils.today()
	d.ignore_pricing_rule = 1
	d.custom_phieu_goc = goc.name
	d.custom_so_dot = so_dot
	d.custom_request_id = f"{goc.custom_request_id}:dot{so_dot}"
	for hang in dong:
		d.append("items", _dong_moi(hang))
	d.insert()
	return d


@frappe.whitelist()
def tach_dot(phieu_goc, dong) -> dict:
	"""Desk — «Báo giá đợt này» (spec §4.1). Tạo đợt từ các dòng `dong` (tên
	dòng `Quotation Item` của phiếu gốc), xoá chúng khỏi phiếu gốc và gửi khách
	đợt đó: MỘT đơn vị, hỏng bước nào lùi cả ba."""
	from frappe.model.workflow import apply_workflow

	from miyano_portal.nang_quyen import quyen_he_thong

	if isinstance(dong, str):
		try:
			dong = frappe.parse_json(dong)
		except ValueError:
			dong = None
	if (
		not isinstance(phieu_goc, str) or not isinstance(dong, list) or not dong
		or not all(isinstance(x, str) for x in dong)
	):
		frappe.throw("Chọn ít nhất một mặt hàng để báo giá đợt này.", frappe.ValidationError)

	# `for_update=True` khoá dòng cha VÀ đọc mọi bảng con bằng FOR UPDATE (đọc mới
	# nhất dưới REPEATABLE READ): việc kiểm dòng được chọn bên dưới thấy bản đã commit.
	goc = frappe.get_doc("Quotation", phieu_goc, for_update=True)
	goc.check_permission("write")
	if not la_phieu_goc_cong(goc) or not goc.get("custom_request_id"):
		frappe.throw(
			"Chỉ tách đợt được trên yêu cầu báo giá của cổng khách hàng (không tách từ một đợt).",
			frappe.ValidationError,
		)
	if goc.docstatus != 0 or goc.get("workflow_state") != bao_gia.TT_CHO_MIYANO:
		frappe.throw(
			f"Phiếu phải ở «{bao_gia.TT_CHO_MIYANO}» mới tách đợt được.", frappe.ValidationError
		)

	chon = list(dict.fromkeys(dong))
	theo_ten = {d.name: d for d in goc.items}
	if any(t not in theo_ten for t in chon):
		frappe.throw(
			"Có mặt hàng đã được báo ở đợt khác hoặc không còn trên phiếu — tải lại "
			"phiếu rồi chọn lại.",
			frappe.ValidationError,
		)
	thieu_gia = [theo_ten[t].item_code for t in chon if flt(theo_ten[t].rate) <= 0]
	if thieu_gia:
		frappe.throw("Chưa có đơn giá: " + ", ".join(thieu_gia) + ".", frappe.ValidationError)

	# Trên phiếu gốc `custom_so_dot` = số đợt ĐÃ phát hành (bộ đếm trên dòng đã
	# khoá, tránh khoá khoảng của truy vấn max()); trên đợt = số thứ tự của nó.
	so_dot = cint(goc.get("custom_so_dot")) + 1
	nguoi_bam = frappe.session.user
	frappe.db.savepoint("tach_dot")
	try:
		d = _dung_dot(goc, [theo_ten[t] for t in chon], so_dot)
		bo = set(chon)
		goc.set("items", [h for h in goc.items if h.name not in bo])
		for i, h in enumerate(goc.items, 1):
			h.idx = i
		goc.custom_so_dot = so_dot
		goc.save()
		d = apply_workflow(d, bao_gia.HD_GUI_KHACH)
		if not _con_dong_chua_bao(goc):
			with quyen_he_thong():
				goc = apply_workflow(goc, bao_gia.HD_BAO_HET)
		goc.add_comment(
			"Comment",
			f"Tách đợt {so_dot} ({len(chon)} mặt hàng) → {d.name}, gửi khách bởi {nguoi_bam}",
		)
	except Exception:
		frappe.db.rollback(save_point="tach_dot")
		raise
	return {"dot": d.name, "so_dot": so_dot, "trang_thai_goc": goc.get("workflow_state")}


# Đợt rơi vào một trong các trạng thái này thì các dòng của nó quay về phiếu
# gốc (D3). "Khách đã đồng ý" không có ở đây: đơn đã sinh.
TT_TRA_VE = (bao_gia.TT_KHACH_TU_CHOI, bao_gia.TT_MIYANO_TU_CHOI, bao_gia.TT_HET_HAN)


def tra_dong_ve_khi_dot_dong(doc, method=None) -> None:
	"""Hook `on_update` của Quotation (spec §4.3). Chạy cho MỌI lối vào trạng
	thái kết thúc — nút trên Desk, `bao_gia.tu_choi` của khách, job
	`quet_het_han` — trong CÙNG giao dịch với bước chuyển. Cờ
	`custom_da_tra_ve` chặn trả hai lần; `kiem_chuyen_theo_dot` chặn mở lại.

	Phiếu gốc không còn nhận dòng (đã «Huỷ phần còn lại») thì đợt kết thúc,
	không trả gì. Dòng trả về giữ giá vừa báo và KHÔNG gộp với dòng trùng mã."""
	from frappe.model.workflow import apply_workflow

	from miyano_portal.nang_quyen import quyen_he_thong

	if not doc.get("custom_phieu_goc") or doc.get("custom_da_tra_ve"):
		return
	truoc, nay = bao_gia._trang_thai_truoc(doc), doc.get("workflow_state")
	if truoc == nay or nay not in TT_TRA_VE:
		return
	goc = frappe.get_doc("Quotation", doc.custom_phieu_goc, for_update=True)
	if goc.get("workflow_state") not in (bao_gia.TT_CHO_MIYANO, bao_gia.TT_DA_BAO_HET):
		goc.add_comment(
			"Comment",
			f"Đợt {doc.custom_so_dot} ({doc.name}) chuyển «{nay}» — phiếu đã "
			f"«{goc.workflow_state}», không trả mặt hàng về.",
		)
		return
	# Nâng quyền: khách (qua `bao_gia.tu_choi`) và job không có quyền ghi
	# phiếu gốc; bước «Hệ thống: có hàng trả về» khai vai Administrator.
	with quyen_he_thong():
		for hang in doc.items:
			goc.append("items", _dong_moi(hang))
		goc.save()
		if goc.get("workflow_state") == bao_gia.TT_DA_BAO_HET:
			goc = apply_workflow(goc, bao_gia.HD_CON_HANG)
		goc.add_comment(
			"Comment",
			f"Đợt {doc.custom_so_dot} ({doc.name}) «{nay}» — đã trả về {len(doc.items)} dòng.",
		)
	frappe.db.set_value("Quotation", doc.name, "custom_da_tra_ve", 1, update_modified=False)
	doc.custom_da_tra_ve = 1


def _kiem_huy_con_lai(doc) -> None:
	"""Miyano phải ghi lý do (≥ `LY_DO_TOI_THIEU`); khách thì tuỳ (D4). Ghi
	người huỷ ở đây — nơi duy nhất biết bước chuyển đến từ đâu."""
	if frappe.flags.get("huy_con_lai_boi_khach") == doc.name:
		doc.custom_nguoi_huy_con_lai = bao_gia.NGUOI_KHACH
		return
	if len((doc.get("custom_ly_do_huy_con_lai") or "").strip()) < bao_gia.LY_DO_TOI_THIEU:
		frappe.throw(
			f"Phải nhập lý do huỷ phần còn lại (tối thiểu {bao_gia.LY_DO_TOI_THIEU} ký tự) "
			"trước khi chuyển trạng thái. Nhập ở mục «Cổng khách hàng» → ô «Lý do huỷ "
			"phần còn lại» rồi lưu, sau đó bấm lại «Huỷ phần còn lại».",
			frappe.ValidationError,
		)
	doc.custom_nguoi_huy_con_lai = frappe.session.user


def huy_con_lai_boi_khach(ten: str, ly_do: str | None = None) -> dict:
	"""Khách huỷ các mặt hàng chưa báo của phiếu gốc (spec §4.4). NGƯỜI GỌI đã
	kiểm quyền của khách. Đợt đang chờ khách vẫn còn hiệu lực."""
	from frappe.model.workflow import apply_workflow

	from miyano_portal.nang_quyen import quyen_he_thong

	goc = frappe.get_doc("Quotation", ten, for_update=True)
	bao_gia._dam_bao_cua_cong(goc)
	if (
		goc.get("custom_phieu_goc") or not co_dot(goc.name)
		or goc.get("workflow_state") != bao_gia.TT_CHO_MIYANO
	):
		frappe.throw(
			"Yêu cầu báo giá này không còn mặt hàng chờ báo giá nào để huỷ.",
			frappe.ValidationError,
		)
	ly_do = (ly_do or "").strip()
	nguoi_bam = frappe.session.user
	if ly_do:
		# Ghi thẳng: `apply_workflow` nạp lại chứng từ từ CSDL trước khi lưu.
		frappe.db.set_value(
			"Quotation", goc.name, "custom_ly_do_huy_con_lai", ly_do, update_modified=False
		)
	with quyen_he_thong():
		frappe.flags.huy_con_lai_boi_khach = goc.name
		try:
			goc = apply_workflow(goc, bao_gia.HD_HUY_CON_LAI)
		finally:
			frappe.flags.huy_con_lai_boi_khach = None
		goc.add_comment(
			"Comment",
			f"{bao_gia.HD_HUY_CON_LAI} bởi {nguoi_bam}" + (f" — lý do: {ly_do}" if ly_do else ""),
		)
	return {"trang_thai_moi": goc.get("workflow_state")}


def bao_khi_huy_con_lai(doc, method=None) -> None:
	"""Hook `on_update` — báo bên kia khi phiếu gốc vào «Đã huỷ phần còn lại»
	(spec §6): khách huỷ → nhân viên phụ trách (Notification Log + email); Miyano
	huỷ → email khách. Lỗi gửi không được làm hỏng việc huỷ."""
	from miyano_portal.portal_bao_gia import _email_sales_phu_trach

	if doc.get("custom_nguon_don") != bao_gia.NGUON_CONG:
		return
	truoc, nay = bao_gia._trang_thai_truoc(doc), doc.get("workflow_state")
	if truoc == nay or nay != bao_gia.TT_HUY_CON_LAI:
		return
	ly_do = (doc.get("custom_ly_do_huy_con_lai") or "").strip()
	dong_ly_do = f"<p>Lý do: {frappe.utils.escape_html(ly_do)}</p>" if ly_do else ""
	if doc.get("custom_nguoi_huy_con_lai") == bao_gia.NGUOI_KHACH:
		noi_dung = (
			f"<p>Khách hàng <b>{doc.party_name}</b> đã huỷ các mặt hàng chưa báo giá "
			f"của yêu cầu <b>{doc.name}</b>.</p>{dong_ly_do}"
		)
		bao_gia.bao_nhan_vien(doc, "Portal - Khách huỷ phần còn lại của yêu cầu báo giá", noi_dung)
		nguoi_nhan = _email_sales_phu_trach(doc.party_name)
		tieu_de = f"Khách huỷ phần còn lại của yêu cầu báo giá {doc.name}"
	else:
		noi_dung = (
			f"<p>Miyano không tiếp tục báo giá các mặt hàng còn lại của yêu cầu "
			f"<b>{doc.name}</b>. Các đợt đã gửi trước đó vẫn giữ nguyên.</p>{dong_ly_do}"
		)
		nguoi_nhan = doc.get("contact_email")
		tieu_de = f"Yêu cầu báo giá {doc.name}: Miyano dừng báo giá phần còn lại"
	if not nguoi_nhan:
		return
	try:
		frappe.sendmail(
			recipients=[nguoi_nhan], subject=tieu_de, message=noi_dung,
			reference_doctype="Quotation", reference_name=doc.name, now=False,
		)
	except Exception:
		frappe.log_error(
			title="bao_gia_theo_dot: gửi email huỷ phần còn lại thất bại",
			message=frappe.get_traceback(),
		)
