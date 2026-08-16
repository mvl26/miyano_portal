"""Kiểm hàng khi nhận & trả lại phần hàng hỏng.

Thiết kế: `docs/superpowers/specs/2026-08-16-kiem-hang-tra-hang-hong-design.md`.

File này giữ NGHIỆP VỤ; các endpoint khách hàng nằm ở `api/portal.py` (cùng
khuôn với `portal_mua_le.py`), còn ba thao tác vai NHÂN VIÊN được whitelist
NGAY TẠI ĐÂY vì chúng không phải "cổng khách hàng" — người gọi là Desk.
"""

import frappe

from miyano_portal.miyano_portal.doctype.portal_delivery_inspection.portal_delivery_inspection import (
	EPS,
	TT_CHO_XU_LY,
	TT_DA_DUYET_TRA,
	TT_DA_XAC_NHAN,
	TT_DA_THU_HOI,
	TT_DA_XU_LY,
	TT_TU_CHOI,
)

from miyano_portal.portal_mua_le import la_dong_giu_cho

DOCTYPE = "Portal Delivery Inspection"

# Role được phép quyết định trên biên bản. KHÔNG dùng `has_permission` của
# doctype làm cổng duy nhất: DocPerm cho `Sales User` là write=1 (để họ ghi
# chú, sửa dữ liệu), nhưng "duyệt trả hàng" là một quyết định thương mại —
# nó sinh chứng từ trả hàng và cam kết Miyano thu hồi hàng.
ROLE_DUYET = ("System Manager", "Sales Manager")

LY_DO_TOI_THIEU = 5


def _kiem_role_duyet() -> None:
	if not set(ROLE_DUYET) & set(frappe.get_roles()):
		raise frappe.PermissionError(
			"Chỉ Sales Manager hoặc System Manager được xử lý biên bản kiểm hàng."
		)


def dong_tu_delivery_note(dn_name: str) -> list[dict]:
	"""Dựng dòng biên bản từ một Delivery Note đã giao.

	Gộp theo `item_code`: một Delivery Note có thể có NHIỀU dòng cùng mã hàng
	(tách theo lô, theo kho xuất). Khách kiểm hàng theo MẶT HÀNG chứ không
	theo dòng chứng từ nội bộ của Miyano — bắt họ đối chiếu ba dòng "Găng tay
	S" chỉ vì Miyano xuất từ ba lô là đẩy chi tiết vận hành của mình sang cho
	khách.

	`sl_nhan` khởi tạo bằng ĐÚNG `sl_giao` (mặc định "nhận đủ") — cùng lựa
	chọn `delivery_hook` đã làm với `so_luong`/`sl_giao` của phiếu nhập kho:
	trường hợp phổ biến nhất không cần gõ gì.
	"""
	gop: dict[str, dict] = {}
	for row in frappe.get_all(
		"Delivery Note Item",
		filters={"parent": dn_name},
		fields=["item_code", "item_name", "uom", "qty"],
		order_by="idx asc",
	):
		# Dòng giữ chỗ `HANG-DAT-NGOAI` là chi tiết kỹ thuật nội bộ, khách
		# không được thấy ở BẤT KỲ lối nào. `kiem_khong_con_dong_giu_cho`
		# (before_submit của Sales Order) khiến một DN sinh từ đơn cổng không
		# thể mang nó — nhưng một Delivery Note lập TAY trên Desk thì không
		# đi qua chốt đó. Lọc ở đây là cái cửa vào, không phải cửa ra: bài
		# học C-1 (2026-08-15) là gác ba lối ra rồi quên lối vào.
		if la_dong_giu_cho(row.item_code):
			continue
		muc = gop.setdefault(row.item_code, {
			"item_code": row.item_code,
			"item_name": row.item_name,
			"uom": row.uom,
			"sl_giao": 0.0,
		})
		muc["sl_giao"] += float(row.qty or 0)

	dong = []
	for muc in gop.values():
		dong.append({**muc, "sl_nhan": muc["sl_giao"], "sl_tra": 0.0, "ly_do": ""})
	return dong


def bien_ban_cua_dn(dn_name: str) -> dict | None:
	"""Biên bản MỚI NHẤT còn sống (docstatus < 2) của một phiếu giao.

	`order_by="creation desc"` chứ không lấy tuỳ ý: sau một lần bị từ chối,
	phiếu giao có HAI biên bản còn sống (bản bị từ chối giữ làm lịch sử + bản
	khách đang gửi lại). Khách phải thấy bản mới nhất.
	"""
	rows = frappe.get_all(
		DOCTYPE,
		filters={"delivery_note": dn_name, "docstatus": ["<", 2]},
		pluck="name",
		order_by="creation desc",
		limit_page_length=1,
	)
	if not rows:
		return None
	return _ra_dict(frappe.get_doc(DOCTYPE, rows[0]))


def _ra_dict(doc) -> dict:
	return {
		"name": doc.name,
		"delivery_note": doc.delivery_note,
		"sales_order": doc.sales_order,
		"ngay_kiem": doc.ngay_kiem,
		"trang_thai": doc.trang_thai,
		"co_hang_hong": bool(doc.co_hang_hong),
		"ly_do_tu_choi": doc.ly_do_tu_choi,
		"phieu_tra_hang": doc.phieu_tra_hang,
		"ghi_chu": doc.ghi_chu,
		"da_gui": doc.docstatus == 1,
		# Bị từ chối = đường lùi DUY NHẤT của khách (spec §4.3). Không có cờ
		# này, màn kiểm hàng khoá cứng ở "đã gửi" và khách hết đường: bản bị
		# từ chối vẫn là docstatus=1.
		"co_the_gui_lai": doc.trang_thai == TT_TU_CHOI,
		"items": [
			{
				"item_code": r.item_code,
				"item_name": r.item_name,
				"uom": r.uom,
				"sl_giao": float(r.sl_giao or 0),
				"sl_nhan": float(r.sl_nhan or 0),
				"sl_tra": float(r.sl_tra or 0),
				"sl_thieu": max(
					0.0,
					float(r.sl_giao or 0) - float(r.sl_nhan or 0) - float(r.sl_tra or 0),
				),
				"ly_do": r.ly_do,
			}
			for r in doc.items
		],
	}


# ------------------------------------------------------------- vai nhân viên
@frappe.whitelist()
def kiem_hang_duyet_tra(name: str) -> dict:
	"""Duyệt yêu cầu trả hàng → sinh Delivery Note trả hàng ở dạng NHÁP.

	KHÔNG submit hộ (spec §4.5): submit sẽ cộng lại tồn kho Miyano ngay lập
	tức, trong khi hàng hỏng vẫn còn nằm ở chỗ khách. Nhân viên kho submit
	khi hàng về thật — đó cũng là lúc `_dong_bo_trang_thai_thu_hoi()` đẩy
	biên bản sang "Đã thu hồi".
	"""
	_kiem_role_duyet()
	doc = frappe.get_doc(DOCTYPE, name)
	if doc.docstatus != 1:
		frappe.throw("Biên bản chưa được khách gửi.", frappe.ValidationError)
	if doc.trang_thai != TT_CHO_XU_LY:
		frappe.throw(
			f"Biên bản đang ở trạng thái «{doc.trang_thai}», không duyệt lại được.",
			frappe.ValidationError,
		)
	if not doc.co_hang_hong:
		frappe.throw(
			"Biên bản này không có dòng hàng hỏng nào cần trả. Dùng «Đã xử lý» "
			"cho trường hợp chỉ thiếu hàng.",
			frappe.ValidationError,
		)

	dn_tra = _tao_phieu_tra_hang(doc)
	doc.db_set("phieu_tra_hang", dn_tra)
	doc.db_set("trang_thai", TT_DA_DUYET_TRA)

	_bao_khach(
		doc,
		"Đã duyệt trả hàng",
		f"Miyano đã duyệt yêu cầu trả hàng của quý khách trên biên bản "
		f"<b>{doc.name}</b> (phiếu giao {doc.delivery_note}). Bộ phận giao nhận "
		"sẽ liên hệ để thu hồi phần hàng hỏng.",
	)
	return {"phieu_tra_hang": dn_tra, "trang_thai": TT_DA_DUYET_TRA}


def _tao_phieu_tra_hang(doc) -> str:
	"""Dựng phiếu trả hàng bằng CHÍNH bộ khởi tạo của ERPNext.

	`make_return_doc` lo hết phần khó: đảo dấu, `is_return`/`return_against`,
	thuế, tiền tệ, kho xuất — chép tay lại những thứ đó là cách chắc chắn
	nhất để sai một chỗ nào đó không ai nhìn thấy cho tới lúc chốt sổ.

	Sau khi có phiếu, giữ lại ĐÚNG các mặt hàng khách báo hỏng và đặt `qty`
	về `-sl_tra` (ERPNext dùng SL ÂM trên phiếu trả).
	"""
	from erpnext.controllers.sales_and_purchase_return import make_return_doc

	can_tra = {r.item_code: float(r.sl_tra or 0) for r in doc.items if float(r.sl_tra or 0) > EPS}
	dn = make_return_doc("Delivery Note", doc.delivery_note)

	# PHÂN BỔ qua nhiều dòng, KHÔNG dồn hết vào dòng đầu tiên. Miyano xuất
	# hàng theo lô nên một mã thường nằm trên nhiều dòng Delivery Note (xem
	# `delivery_hook._lo_cua_dong`). Dồn 7 cái hỏng vào một dòng chỉ giao 4 sẽ
	# bị `validate_returned_qty` của ERPNext chặn — chính là loại lỗi chỉ nổ
	# ở dữ liệu thật, nơi hàng đi từ nhiều lô.
	#
	# `make_return_doc` đã đặt `row.qty` = SL còn trả được của dòng đó, mang
	# dấu ÂM. `abs()` để lấy trần phân bổ, rồi ghi lại phần thật sự trả.
	giu = []
	for row in dn.items:
		con = can_tra.get(row.item_code, 0.0)
		if con <= EPS:
			continue
		tran = abs(float(row.qty or 0))
		if tran <= EPS:
			continue
		lay = min(con, tran)
		row.qty = -lay
		# `stock_qty`/`received_qty` được controller tính lại trong validate();
		# chỉ đặt `qty` để không chốt cứng một giá trị sẽ lệch với hệ số quy
		# đổi đơn vị của chính dòng đó.
		can_tra[row.item_code] = con - lay
		giu.append(row)

	con_thua = {k: v for k, v in can_tra.items() if v > EPS}
	if con_thua:
		# Không thể xảy ra nếu `_kiem_dong()` đúng (sl_tra ≤ sl_giao) VÀ phiếu
		# giao chưa bị trả một phần trước đó. Nếu xảy ra thì đúng là trường
		# hợp thứ hai — báo rõ thay vì lặng lẽ lập một phiếu trả thiếu số.
		frappe.throw(
			"Không lập được phiếu trả hàng: phiếu giao này không còn đủ số "
			f"lượng để trả cho {', '.join(con_thua)} (có thể đã có phiếu trả "
			"hàng khác trước đó).",
			frappe.ValidationError,
		)

	dn.items = giu
	for i, row in enumerate(dn.items, start=1):
		row.idx = i
	dn.flags.ignore_permissions = True
	dn.insert()
	dn.add_comment(
		"Comment", f"[Portal] Lập từ biên bản kiểm hàng {doc.name} của khách."
	)
	return dn.name


@frappe.whitelist()
def kiem_hang_tu_choi(name: str, ly_do: str) -> dict:
	_kiem_role_duyet()
	ly_do = (ly_do or "").strip()
	if len(ly_do) < LY_DO_TOI_THIEU:
		frappe.throw(
			f"Nêu lý do từ chối (tối thiểu {LY_DO_TOI_THIEU} ký tự) — khách sẽ "
			"đọc đúng dòng này.",
			frappe.ValidationError,
		)
	doc = frappe.get_doc(DOCTYPE, name)
	if doc.trang_thai != TT_CHO_XU_LY:
		frappe.throw(
			f"Biên bản đang ở trạng thái «{doc.trang_thai}».", frappe.ValidationError
		)
	doc.db_set("ly_do_tu_choi", ly_do)
	doc.db_set("trang_thai", TT_TU_CHOI)
	_bao_khach(
		doc,
		"Từ chối",
		f"Miyano chưa chấp nhận đề nghị trên biên bản <b>{doc.name}</b> "
		f"(phiếu giao {doc.delivery_note}). Lý do: {frappe.utils.escape_html(ly_do)}",
	)
	return {"trang_thai": TT_TU_CHOI}


@frappe.whitelist()
def kiem_hang_da_xu_ly(name: str, ghi_chu: str | None = None) -> dict:
	"""Đóng biên bản chỉ THIẾU hàng (không có hàng hỏng để trả).

	Cách xử lý thật (giao bù, giảm trừ công nợ) nằm ngoài phạm vi cổng — cái
	biên bản cần là một cái đóng tường minh để khách thôi thấy "Chờ xử lý".
	"""
	_kiem_role_duyet()
	doc = frappe.get_doc(DOCTYPE, name)
	if doc.trang_thai != TT_CHO_XU_LY:
		frappe.throw(
			f"Biên bản đang ở trạng thái «{doc.trang_thai}».", frappe.ValidationError
		)
	doc.db_set("trang_thai", TT_DA_XU_LY)
	them = f" Ghi chú: {frappe.utils.escape_html(ghi_chu)}" if (ghi_chu or "").strip() else ""
	_bao_khach(
		doc,
		"Đã xử lý",
		f"Miyano đã xử lý biên bản kiểm hàng <b>{doc.name}</b> "
		f"(phiếu giao {doc.delivery_note}).{them}",
	)
	return {"trang_thai": TT_DA_XU_LY}


def _bao_khach(doc, tieu_de: str, noi_dung: str) -> None:
	try:
		from miyano_portal.portal_thong_bao_khach import bao_kiem_hang_ket_qua

		bao_kiem_hang_ket_qua(doc, tieu_de, noi_dung)
	except Exception:
		frappe.log_error(
			title="Kiểm hàng: lỗi khi báo khách",
			reference_doctype=DOCTYPE,
			reference_name=doc.name,
		)


# ------------------------------------------------- hook Delivery Note (trả hàng)
def dong_bo_trang_thai_thu_hoi(dn, method=None) -> None:
	"""`on_submit` của Delivery Note: phiếu trả hàng được ghi sổ → biên bản
	sang "Đã thu hồi".

	KHÔNG BAO GIỜ ném lỗi (Quyết định nền #4 của dự án — hook trên Delivery
	Note không được phép làm vỡ một lần submit chứng từ của Miyano). Một biên
	bản kẹt ở "Đã duyệt trả" là phiền; một Delivery Note không submit được là
	dừng việc giao hàng.
	"""
	try:
		if not dn.get("is_return"):
			return
		ten = frappe.db.get_value(DOCTYPE, {"phieu_tra_hang": dn.name}, "name")
		if not ten:
			return
		doc = frappe.get_doc(DOCTYPE, ten)
		if doc.trang_thai != TT_DA_DUYET_TRA:
			return
		doc.db_set("trang_thai", TT_DA_THU_HOI)
		_bao_khach(
			doc,
			"Đã thu hồi",
			f"Miyano đã thu hồi phần hàng hỏng theo biên bản <b>{doc.name}</b> "
			f"(phiếu trả hàng {dn.name}).",
		)
	except Exception:
		try:
			frappe.log_error(
				title="Kiểm hàng: lỗi khi đồng bộ trạng thái thu hồi",
				message=frappe.get_traceback(with_context=True),
				reference_doctype="Delivery Note",
				reference_name=dn.get("name"),
			)
		except Exception:
			pass
