"""HSD tối thiểu theo yêu cầu khách hàng: logic thuần (spec 2026-10-19).

Các hàm tính ngày (`hsd_yeu_cau_den`, `san_cho_phep`, `danh_gia_lo`,
`mo_ta_chenh_lech`) là logic thuần, để SO (cảnh báo) và Delivery Note (chốt lô,
chặn duyệt) dùng chung một cách tính; các hook/API bên dưới đọc DB qua chúng.
"""

import datetime
import math

import frappe
from dateutil.relativedelta import relativedelta
from frappe import _
from frappe.utils import add_months, cint, flt, formatdate, getdate, now_datetime

TOI_DA_THANG = 60


def ap_dung(item_code, so_thang):
	"""Có yêu cầu HSD (số tháng > 0) và mặt hàng quản lý theo lô."""
	if cint(so_thang) <= 0 or not item_code:
		return False
	return bool(frappe.db.get_value("Item", item_code, "has_batch_no"))


def kiem_so_thang(so_thang):
	"""Chuẩn hoá số tháng: nguyên 0-60 (rỗng = 0), sai thì ném ValidationError."""
	thong_bao = _("HSD tối thiểu phải là số tháng từ 0 đến 60.")
	if so_thang is None or so_thang == "":
		return 0
	try:
		gia_tri = float(so_thang)
	except (TypeError, ValueError):
		frappe.throw(thong_bao)
	if not math.isfinite(gia_tri) or gia_tri != int(gia_tri) or not 0 <= gia_tri <= TOI_DA_THANG:
		frappe.throw(thong_bao)
	return int(gia_tri)


def hsd_yeu_cau_den(ngay, so_thang):
	"""`ngay` + N tháng (cuối tháng được kẹp: 31/01 + 1 = 28/02); None khi không yêu cầu."""
	if cint(so_thang) <= 0 or not ngay:
		return None
	return getdate(add_months(getdate(ngay), cint(so_thang)))


def san_cho_phep(dong_so, ngay_moc):
	"""Ngày HSD tối thiểu một lô phải đạt; None khi dòng không yêu cầu.

	Có ngoại lệ → lấy ngày ngoại lệ; không thì ngày mốc + số tháng.
	"""
	if cint(dong_so.get("custom_hsd_toi_thieu_thang")) <= 0:
		return None
	if cint(dong_so.get("custom_ngoai_le_hsd")) and dong_so.get("custom_ngoai_le_hsd_den"):
		return getdate(dong_so.get("custom_ngoai_le_hsd_den"))
	return hsd_yeu_cau_den(ngay_moc, dong_so.get("custom_hsd_toi_thieu_thang"))


def danh_gia_lo(expiry_date, san):
	"""Lô đạt khi `expiry_date >= san`; lô không có HSD thì không đạt; `san` None = đạt."""
	if san is None:
		return True
	if not expiry_date:
		return False
	return getdate(expiry_date) >= getdate(san)


def mo_ta_chenh_lech(hsd_yeu_cau, hsd_thuc_te, tu_ngay):
	"""Mô tả HSD còn lại của lô tính từ `tu_ngay` và số ngày còn thiếu so với yêu cầu."""
	hsd_yeu_cau, hsd_thuc_te, tu_ngay = getdate(hsd_yeu_cau), getdate(hsd_thuc_te), getdate(tu_ngay)
	thieu_ngay = max(0, (hsd_yeu_cau - hsd_thuc_te).days)
	if hsd_thuc_te < tu_ngay:
		return {"con_lai": "đã hết hạn", "thieu_ngay": thieu_ngay}
	kc = relativedelta(hsd_thuc_te, tu_ngay)
	thang = kc.years * 12 + kc.months
	con_lai = f"{thang:02d} tháng"
	if kc.days:
		con_lai += f" {kc.days:02d} ngày"
	return {"con_lai": con_lai, "thieu_ngay": thieu_ngay}


def kiem_ton_cho_dong(item_code, warehouse, stock_qty, san):
	"""Tồn theo lô của mặt hàng ở kho có đủ lô đạt sàn cho `stock_qty` không.

	Trả `dat`, `hsd_tot_nhat` (HSD lớn nhất trong các lô còn tồn > 0), `ton_dat`
	(tổng tồn các lô đạt sàn).
	"""
	from erpnext.stock.doctype.batch.batch import get_batch_qty

	lo_ton = []
	if item_code and warehouse:
		lo_ton = [b for b in (get_batch_qty(item_code=item_code, warehouse=warehouse) or []) if flt(b.get("qty")) > 0]
	han = {}
	if lo_ton:
		han = dict(
			frappe.get_all(
				"Batch",
				filters={"name": ["in", [b.get("batch_no") for b in lo_ton]]},
				fields=["name", "expiry_date"],
				as_list=True,
			)
		)
	ton_dat = 0.0
	hsd_tot_nhat = None
	for b in lo_ton:
		expiry = han.get(b.get("batch_no"))
		if expiry:
			expiry = getdate(expiry)
			if hsd_tot_nhat is None or expiry > hsd_tot_nhat:
				hsd_tot_nhat = expiry
		if danh_gia_lo(expiry, san):
			ton_dat += flt(b.get("qty"))
	return {"dat": ton_dat >= flt(stock_qty), "hsd_tot_nhat": hsd_tot_nhat, "ton_dat": ton_dat}


def _ngay(d):
	return formatdate(d, "dd/mm/yyyy")


def cau_canh_bao(dong, kq_ton, tu_ngay):
	"""Câu cảnh báo một dòng không đáp ứng HSD khách yêu cầu (mẫu spec §4.2)."""
	so_thang = cint(dong.get("custom_hsd_toi_thieu_thang"))
	yeu_cau = dong.get("custom_hsd_yeu_cau_den")
	cau = (
		f"Dòng {dong.get('idx')} – {dong.get('item_code')}: Khách hàng yêu cầu hàng còn tối thiểu "
		f"{so_thang:02d} tháng HSD (đến {_ngay(yeu_cau)}). "
	)
	tot_nhat = kq_ton.get("hsd_tot_nhat")
	if tot_nhat:
		cl = mo_ta_chenh_lech(yeu_cau, tot_nhat, tu_ngay)
		cau += (
			f"Tồn kho tốt nhất HSD {_ngay(tot_nhat)}, chỉ còn {cl['con_lai']} "
			f"→ Không đáp ứng (thiếu {cl['thieu_ngay']} ngày)."
		)
	else:
		cau += "Không còn tồn kho lô nào."
	if cint(dong.get("custom_ngoai_le_hsd")) and dong.get("custom_ngoai_le_hsd_den"):
		cau += f" Đã ghi ngoại lệ: khách chấp nhận đến {_ngay(dong.get('custom_ngoai_le_hsd_den'))}."
	cau += " Vui lòng xác nhận với Khách hàng trước khi giao hàng."
	return cau


def _tinh_dong(doc, d, dau_phieu, ke_thua_khi_0=False):
	"""Kế thừa số tháng, tính yêu cầu/kết quả/tồn tốt nhất cho MỘT dòng SO.

	Trả câu cảnh báo khi dòng "Không đạt", không thì None. `ke_thua_khi_0`: dòng
	thêm sau duyệt (Update Items) không khai được số tháng nên 0 cũng kế thừa.
	"""
	so_thang = d.get("custom_hsd_toi_thieu_thang")
	if so_thang is None or so_thang == "" or (ke_thua_khi_0 and not cint(so_thang)):
		so_thang = dau_phieu
	d.custom_hsd_toi_thieu_thang = kiem_so_thang(so_thang)

	if doc.docstatus == 0 and cint(d.get("custom_ngoai_le_hsd")):
		if not d.get("custom_ngoai_le_hsd_den") or not (d.get("custom_ngoai_le_ly_do") or "").strip():
			frappe.throw(
				_("Dòng {0}: ngoại lệ HSD cần nhập đủ ngày khách chấp nhận và lý do.").format(d.idx)
			)
		if not d.get("custom_ngoai_le_boi"):
			d.custom_ngoai_le_boi = frappe.session.user
		if not d.get("custom_ngoai_le_luc"):
			d.custom_ngoai_le_luc = now_datetime()

	if not ap_dung(d.get("item_code"), d.custom_hsd_toi_thieu_thang):
		d.custom_ket_qua_hsd = "Không áp dụng"
		d.custom_hsd_yeu_cau_den = None
		d.custom_hsd_ton_tot_nhat = None
		return None

	ngay_giao = d.get("delivery_date") or doc.get("delivery_date")
	d.custom_hsd_yeu_cau_den = hsd_yeu_cau_den(ngay_giao, d.custom_hsd_toi_thieu_thang)
	kq = kiem_ton_cho_dong(
		d.item_code, d.get("warehouse"), flt(d.get("stock_qty")) or flt(d.get("qty")), san_cho_phep(d, ngay_giao)
	)
	d.custom_ket_qua_hsd = "Đạt" if kq["dat"] else "Không đạt"
	d.custom_hsd_ton_tot_nhat = kq["hsd_tot_nhat"]
	return None if kq["dat"] else cau_canh_bao(d, kq, ngay_giao)


def _bao_canh_bao(canh_bao):
	"""Một msgprint gom các dòng — chỉ cho người dùng nội bộ.

	Khách cổng (Website User) đặt đơn/duyệt đề xuất cũng chạy `validate` của SO;
	câu tồn kho, HSD lô là thông tin nội bộ nên không được lọt vào
	`_server_messages` trả về cổng.
	"""
	if not canh_bao:
		return
	if frappe.get_cached_value("User", frappe.session.user, "user_type") == "Website User":
		return
	frappe.msgprint("<br>".join(canh_bao), indicator="orange", title=_("Không đáp ứng HSD khách yêu cầu"))


def tinh_tren_don(doc, method=None):
	"""Hook `validate` của Sales Order: kế thừa số tháng, tính kết quả từng dòng, cảnh báo.

	Cảnh báo không bao giờ chặn lưu/submit; chỉ số tháng sai hoặc ngoại lệ thiếu
	thông tin mới bị từ chối.
	"""
	dau_phieu = kiem_so_thang(doc.get("custom_hsd_toi_thieu_thang"))
	doc.custom_hsd_toi_thieu_thang = dau_phieu
	canh_bao = [c for d in doc.get("items") or [] if (c := _tinh_dong(doc, d, dau_phieu))]
	_bao_canh_bao(canh_bao)


def tinh_dong_them_sau_duyet(doc, method=None):
	"""`before_update_after_submit` của Sales Order: dòng thêm qua "Update Items".

	`update_child_qty_rate` của ERPNext ghi thẳng dòng mới rồi lưu đơn theo lối
	sửa-sau-duyệt — `validate` (và `tinh_tren_don`) không chạy, dòng mới mang số
	tháng 0 và lọt khỏi chốt phiếu giao. Dòng mới được nhận ra bằng TRẠNG THÁI:
	`custom_ket_qua_hsd` rỗng = chưa từng được tính (dòng nào đi qua
	`tinh_tren_don` cũng mang một trong ba giá trị). Dòng đã tính thì không đụng:
	các trường kết quả không `allow_on_submit`, đổi chúng trên lần lưu sửa-sau-
	duyệt bình thường (vd. hẹn lịch giao mới) sẽ bị Frappe chặn.

	Chỉ xử lý khi Frappe không kiểm sửa-sau-duyệt (cờ của Update Items) hoặc dòng
	thật sự mới — đơn cũ trước tính năng (kết quả rỗng) lưu kiểu khác thì để yên.
	"""
	dau_phieu = cint(doc.get("custom_hsd_toi_thieu_thang"))
	truoc = doc.get_doc_before_save()
	ten_cu = {d.name for d in (truoc.get("items") if truoc else None) or []}
	bo_kiem = bool(doc.flags.ignore_validate_update_after_submit)
	canh_bao = []
	for d in doc.get("items") or []:
		if d.get("custom_ket_qua_hsd"):
			continue
		if not bo_kiem and d.name in ten_cu:
			continue
		c = _tinh_dong(doc, d, dau_phieu, ke_thua_khi_0=True)
		if c:
			canh_bao.append(c)
	_bao_canh_bao(canh_bao)


VAI_TRO_NGOAI_LE = {"Sales User", "Sales Manager", "System Manager"}


def _kiem_quyen_va_dong(so, dong, ly_do, go=False):
	"""Kiểm vai trò → đơn đã duyệt còn mở → dòng thuộc đơn và áp dụng → lý do. Trả thông tin dòng."""
	if not VAI_TRO_NGOAI_LE & set(frappe.get_roles()):
		frappe.throw(_("Bạn không có quyền ghi/gỡ ngoại lệ HSD."), frappe.PermissionError)
	# Vai trò chưa đủ: User Permission (vd. giới hạn theo khách) vẫn phải được tôn trọng.
	frappe.has_permission("Sales Order", "write", so, throw=True)

	don = frappe.db.get_value("Sales Order", so, ["docstatus", "status"], as_dict=True)
	if not don:
		frappe.throw(_("Không tìm thấy đơn bán hàng {0}.").format(so))
	if don.docstatus != 1 or don.status in ("Closed", "Completed"):
		frappe.throw(_("Chỉ ghi/gỡ ngoại lệ HSD trên đơn đã duyệt và chưa đóng/hoàn tất."))

	d = frappe.db.get_value(
		"Sales Order Item",
		dong,
		["parent", "idx", "item_code", "custom_hsd_toi_thieu_thang", "custom_ngoai_le_hsd"],
		as_dict=True,
	)
	if not d or d.parent != so:
		frappe.throw(_("Dòng {0} không thuộc đơn {1}.").format(dong, so))
	if not ap_dung(d.item_code, d.custom_hsd_toi_thieu_thang):
		frappe.throw(_("Dòng {0} không yêu cầu HSD tối thiểu nên không cần ngoại lệ.").format(d.idx))
	if not str(ly_do or "").strip():
		frappe.throw(_("Vui lòng nhập lý do."))
	if go and not cint(d.custom_ngoai_le_hsd):
		frappe.throw(_("Dòng {0} chưa có ngoại lệ HSD để gỡ.").format(d.idx))
	return d


@frappe.whitelist()
def ghi_ngoai_le(so, dong, chap_nhan_den, ly_do):
	"""Ghi ngoại lệ HSD cho một dòng của Sales Order đã duyệt: khách chấp nhận hàng đến ngày `chap_nhan_den`."""
	d = _kiem_quyen_va_dong(so, dong, ly_do)
	if not chap_nhan_den or not isinstance(chap_nhan_den, (str, datetime.date)):
		frappe.throw(_("Vui lòng nhập ngày khách chấp nhận."))
	den = getdate(chap_nhan_den)
	ly_do = str(ly_do).strip()
	frappe.db.set_value(
		"Sales Order Item",
		dong,
		{
			"custom_ngoai_le_hsd": 1,
			"custom_ngoai_le_hsd_den": den,
			"custom_ngoai_le_ly_do": ly_do,
			"custom_ngoai_le_boi": frappe.session.user,
			"custom_ngoai_le_luc": now_datetime(),
		},
	)
	frappe.get_doc("Sales Order", so).add_comment(
		"Comment",
		f"Ghi ngoại lệ HSD dòng {d.idx} ({d.item_code}): khách chấp nhận đến {_ngay(den)} — {ly_do}",
	)
	return {"dong": dong, "custom_ngoai_le_hsd_den": str(den), "custom_ngoai_le_boi": frappe.session.user}


@frappe.whitelist()
def go_ngoai_le(so, dong, ly_do):
	"""Gỡ ngoại lệ HSD của một dòng; lý do gỡ được lưu vào `custom_ngoai_le_ly_do`."""
	d = _kiem_quyen_va_dong(so, dong, ly_do, go=True)
	ly_do = str(ly_do).strip()
	frappe.db.set_value(
		"Sales Order Item",
		dong,
		{
			"custom_ngoai_le_hsd": 0,
			"custom_ngoai_le_hsd_den": None,
			"custom_ngoai_le_ly_do": ly_do,
			"custom_ngoai_le_boi": frappe.session.user,
			"custom_ngoai_le_luc": now_datetime(),
		},
	)
	frappe.get_doc("Sales Order", so).add_comment(
		"Comment", f"Gỡ ngoại lệ HSD dòng {d.idx} ({d.item_code}) — {ly_do}"
	)
	return {"dong": dong}


@frappe.whitelist()
def canh_bao_hsd(so):
	"""Câu cảnh báo (cùng mẫu `cau_canh_bao`) cho các dòng 'Không đạt' đã lưu của đơn, cho banner Desk."""
	if not VAI_TRO_NGOAI_LE & set(frappe.get_roles()):
		frappe.throw(_("Bạn không có quyền xem cảnh báo HSD."), frappe.PermissionError)
	doc = frappe.get_doc("Sales Order", so)
	doc.check_permission("read")
	cau = []
	for d in doc.items:
		if d.get("custom_ket_qua_hsd") != "Không đạt":
			continue
		tu_ngay = d.get("delivery_date") or doc.get("delivery_date")
		kq = {"hsd_tot_nhat": d.get("custom_hsd_ton_tot_nhat")}
		cau.append(cau_canh_bao(d, kq, tu_ngay))
	return cau


# ---- Phiếu giao (spec §4.4, §4.5) ----

TIEU_DE_CHAN = "Không đáp ứng HSD khách yêu cầu"


def _yeu_cau_dong_giao(doc, d, ngay_ghi_so=None):
	"""Yêu cầu HSD của dòng phiếu giao, đọc TƯƠI dòng SO; None khi không áp dụng.

	Đọc DB chứ không dùng `custom_hsd_yeu_cau_den` đã lưu: ngày giao trên SO có
	thể đổi và ngoại lệ có thể được ghi/gỡ sau khi phiếu giao đã lập nháp.
	"""
	if cint(doc.get("is_return")) or not d.get("so_detail"):
		return None
	dong = frappe.db.get_value(
		"Sales Order Item",
		d.so_detail,
		["parent", "delivery_date", "custom_hsd_toi_thieu_thang", "custom_ngoai_le_hsd", "custom_ngoai_le_hsd_den"],
		as_dict=True,
	)
	if not dong or not ap_dung(d.get("item_code"), dong.custom_hsd_toi_thieu_thang):
		return None
	ngay_ghi_so = getdate(ngay_ghi_so or doc.get("posting_date") or frappe.utils.nowdate())
	ngay_moc = max(getdate(dong.delivery_date or ngay_ghi_so), ngay_ghi_so)
	san = san_cho_phep(dong, ngay_moc)
	if san is None:
		return None
	return frappe._dict(
		san=san,
		ngay_moc=ngay_moc,
		so=d.get("against_sales_order") or dong.parent,
		so_thang=cint(dong.custom_hsd_toi_thieu_thang),
		ngoai_le=bool(cint(dong.custom_ngoai_le_hsd) and dong.custom_ngoai_le_hsd_den),
	)


def _ngay_ghi_so_se_dung(doc):
	"""Ngày ghi sổ ERPNext SẼ dùng khi lưu/duyệt phiếu giao.

	Không tick "Edit Posting Date and Time": `validate` của ERPNext đặt lại ngày
	ghi sổ về hôm nay — sàn phải tính theo ngày đó, không theo ngày cũ đang lưu
	trên phiếu nháp. Có tick thì None (= dùng `posting_date` của phiếu).
	"""
	return None if cint(doc.get("set_posting_time")) else frappe.utils.nowdate()


def han_toi_thieu_lo_xuat(doc, d):
	"""Sàn HSD (date) một lô phải đạt để xuất cho dòng `d` của phiếu giao `doc`; None khi không áp dụng.

	Cùng ngày mốc với `chot_lo_truoc_validate`/`kiem_phieu_giao`: trang lấy hàng
	PDA mở một phiếu nháp cũ vẫn tính sàn theo ngày ERPNext sẽ ghi sổ.
	"""
	yc = _yeu_cau_dong_giao(doc, d, _ngay_ghi_so_se_dung(doc))
	return yc.san if yc else None


def _sl_dong(d):
	return flt(d.get("stock_qty")) or flt(d.get("qty")) * (flt(d.get("conversion_factor")) or 1)


def _lo_cua_bundle(bundle):
	"""{lô: số lượng (dương)} trong một Serial and Batch Bundle."""
	kq = {}
	for e in frappe.get_all(
		"Serial and Batch Entry", filters={"parent": bundle}, fields=["batch_no", "qty"], order_by="idx asc"
	):
		if e.batch_no:
			kq[e.batch_no] = kq.get(e.batch_no, 0.0) + abs(flt(e.qty))
	return kq


def _lo_cua_dong(d):
	"""Các lô thực xuất của dòng: từ bundle nếu có, cộng `batch_no`."""
	lo = {}
	if d.get("serial_and_batch_bundle"):
		lo.update(_lo_cua_bundle(d.serial_and_batch_bundle))
	if d.get("batch_no") and d.batch_no not in lo:
		lo[d.batch_no] = _sl_dong(d)
	return lo


def _lo_dat_con_lai(doc, d, san):
	"""Lô đạt sàn của mặt hàng ở kho của dòng, kèm tồn còn lại sau khi trừ phần MỌI dòng
	khác trên cùng phiếu đang giữ (cùng mặt hàng, kho, lô). Sắp HSD tăng dần, rồi mã lô.
	"""
	from erpnext.stock.doctype.batch.batch import get_batch_qty

	if not d.get("item_code") or not d.get("warehouse"):
		return []
	ton = {}
	for b in get_batch_qty(item_code=d.item_code, warehouse=d.warehouse) or []:
		if b.get("batch_no"):
			ton[b.get("batch_no")] = ton.get(b.get("batch_no"), 0.0) + flt(b.get("qty"))
	if not ton:
		return []
	da_giu = {}
	for khac in doc.get("items") or []:
		if khac is d or khac.get("item_code") != d.item_code or khac.get("warehouse") != d.warehouse:
			continue
		for lo, sl in _lo_cua_dong(khac).items():
			da_giu[lo] = da_giu.get(lo, 0.0) + sl
	han = dict(
		frappe.get_all(
			# Lô bị khoá (disabled) không bao giờ được chốt — như bộ chọn lô của ERPNext.
			"Batch",
			filters={"name": ["in", list(ton)], "disabled": 0},
			fields=["name", "expiry_date"],
			as_list=True,
		)
	)
	kq = [
		frappe._dict(batch_no=lo, expiry_date=getdate(han[lo]), con=sl - da_giu.get(lo, 0.0))
		for lo, sl in ton.items()
		if han.get(lo) and danh_gia_lo(han[lo], san)
	]
	kq.sort(key=lambda x: (x.expiry_date, x.batch_no))
	return kq


def _chon_lo_dat(doc, d, san):
	"""Lô đạt HSD sớm nhất đủ một mình cho dòng; trả (lô hoặc None, danh sách lô đạt)."""
	ds = _lo_dat_con_lai(doc, d, san)
	can = _sl_dong(d)
	for x in ds:
		if x.con >= can:
			return x.batch_no, ds
	return None, ds


def _dong_can_chot(d):
	return not d.get("batch_no") and not d.get("serial_and_batch_bundle")


def _gan_lo(d, lo):
	d.batch_no = lo
	d.use_serial_batch_fields = 1


def chot_lo_truoc_validate(doc, method=None):
	"""`before_validate` của Delivery Note: dòng có yêu cầu HSD mà chưa có lô → chốt lô đạt.

	Chạy TRƯỚC `validate` của ERPNext, nơi `update_stock` tự điền lô hết hạn sớm
	nhất vào dòng trống (Stock Settings dùng trường lô cũ). Lô đã có sẵn — người
	hoặc PDA chọn — không bao giờ bị đổi. Không lô đạt nào đủ thì để trống, không
	ném lỗi: phiếu nháp vẫn lưu được, chốt `kiem_phieu_giao` lúc duyệt quyết.
	"""
	if cint(doc.get("is_return")):
		return
	ngay_ghi_so = _ngay_ghi_so_se_dung(doc)
	for d in doc.get("items") or []:
		if not _dong_can_chot(d):
			continue
		yc = _yeu_cau_dong_giao(doc, d, ngay_ghi_so)
		if yc is None:
			continue
		lo, _ds = _chon_lo_dat(doc, d, yc.san)
		if lo:
			_gan_lo(d, lo)


def _cau_san(yc):
	if yc.ngoai_le:
		return f"(khách chấp nhận đến {_ngay(yc.san)})"
	return f"(đến {_ngay(yc.san)})"


def _sl(x):
	# Không dùng `:g` — 1234567.5 sẽ thành "1.23457e+06".
	return f"{flt(x, 6):.6f}".rstrip("0").rstrip(".")


def _cau_khong_lo_du(d, yc, ds):
	con = [x for x in ds if x.con > 0]
	if con:
		hien_co = "Lô đạt hiện có: " + ", ".join(f"{x.batch_no} ({_sl(x.con)})" for x in con)
	else:
		hien_co = "Không còn lô nào đạt."
	return (
		f"Dòng {d.idx} – {d.item_code}: không có lô nào đạt HSD yêu cầu (đến {_ngay(yc.san)}) "
		f"đủ {_sl(_sl_dong(d))} {d.get('stock_uom') or d.get('uom') or ''}. {hien_co} — "
		f"tách dòng theo lô, hoặc ghi ngoại lệ trên SO {yc.so}."
	)


def _cau_lo_khong_dat(d, yc, lo, expiry):
	cau = (
		f"Dòng {d.idx} – {d.item_code}, lô {lo}: Khách hàng yêu cầu hàng còn tối thiểu "
		f"{yc.so_thang:02d} tháng HSD {_cau_san(yc)}. "
	)
	if expiry:
		cl = mo_ta_chenh_lech(yc.san, expiry, yc.ngay_moc)
		cau += (
			f"Lô này HSD {_ngay(expiry)}, chỉ còn {cl['con_lai']} "
			f"→ Không đáp ứng (thiếu {cl['thieu_ngay']} ngày). "
		)
	else:
		cau += "Lô này không có HSD → Không đáp ứng. "
	cau += f"Vui lòng xác nhận với Khách hàng và ghi ngoại lệ trên SO {yc.so} trước khi giao."
	return cau


def kiem_phieu_giao(doc, method=None):
	"""`before_submit` của Delivery Note: chốt lô đạt cho dòng còn trống, rồi chặn duyệt khi
	có lô thực xuất không đạt HSD khách yêu cầu (spec §4.5). Gom lỗi, ném MỘT lần.

	Lỗi lô không đạt kèm câu "không có lô nào đạt …" khi cũng không lô đạt nào đủ
	cho dòng — trường hợp ERPNext đã tự điền lô không đạt vì thiếu lô đạt.
	Không có cờ bỏ qua nào ngoài ngoại lệ trên dòng SO.
	"""
	if cint(doc.get("is_return")):
		return
	loi = []
	# Lúc `before_submit`, `validate` đã đặt lại ngày ghi sổ nên giá trị này trùng
	# `posting_date`; gọi chung một hàm để ba chỗ không bao giờ lệch nhau.
	ngay_ghi_so = _ngay_ghi_so_se_dung(doc)
	for d in doc.get("items") or []:
		yc = _yeu_cau_dong_giao(doc, d, ngay_ghi_so)
		if yc is None:
			continue
		if _dong_can_chot(d):
			lo, ds = _chon_lo_dat(doc, d, yc.san)
			if lo:
				_gan_lo(d, lo)
			else:
				loi.append(_cau_khong_lo_du(d, yc, ds))
				continue

		lo_xuat = list(_lo_cua_dong(d))
		han = dict(
			frappe.get_all(
				"Batch", filters={"name": ["in", lo_xuat]}, fields=["name", "expiry_date"], as_list=True
			)
		)
		loi_dong = [
			_cau_lo_khong_dat(d, yc, lo, han.get(lo)) for lo in lo_xuat if not danh_gia_lo(han.get(lo), yc.san)
		]
		if loi_dong:
			loi.extend(loi_dong)
			lo_thay, ds = _chon_lo_dat(doc, d, yc.san)
			if not lo_thay:
				loi.append(_cau_khong_lo_du(d, yc, ds))

	if loi:
		frappe.throw("<br>".join(loi), title=_(TIEU_DE_CHAN))
