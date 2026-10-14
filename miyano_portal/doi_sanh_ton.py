"""Đối sánh tồn kho của MIYANO trên Sales Order, và Material Request cho
phần thiếu.

Spec: docs/superpowers/specs/2026-10-12-doi-sanh-ton-kho-khi-tao-so-design.md

KHÔNG nhầm với CR-04 (`kho/can_cu_duyet.py`): CR-04 là tồn tại kho của BỆNH
VIỆN, cho quản lý bệnh viện duyệt số lượng đặt. Ở đây là tồn tại kho của
Miyano (`Bin`, `Batch`), cho nhân viên Miyano xác nhận đơn.

Ba lớp, từ trong ra ngoài:

1. Hàm thuần — nhận số, trả số. Mọi quy tắc tính nằm ở đây.
2. Hàm đọc CSDL — mỗi hàm một nguồn.
3. Hai endpoint — chốt vai nội bộ rồi mới gọi hai lớp trên.
"""

import math

import frappe
from frappe.utils import cint, flt, getdate, today

# Tài khoản cổng khách hàng ĐỌC ĐƯỢC đơn của chính họ
# (`permissions.sales_has_permission`), nên "có quyền đọc Sales Order" không
# chặn được họ. Chốt bằng danh sách vai đặt tên rõ, theo tiền lệ
# `portal_hen_giao.ROLE_HEN_GIAO`.
ROLE_NOI_BO = (
	"System Manager",
	"Sales Manager",
	"Sales User",
	"Stock Manager",
	"Stock User",
	"Purchase Manager",
	"Purchase User",
)

# Số lượng tồn kho của ERPNext mặc định 3 chữ số thập phân.
DO_CHINH_XAC = 3

LY_DO_KHONG_TON = "Mặt hàng không quản lý tồn kho"
LY_DO_KHONG_KHO = "Dòng đơn chưa có kho"
LY_DO_GIAO_THANG = "Nhà cung cấp giao thẳng — không qua kho Miyano"
LY_DO_BO = "Bộ sản phẩm — tồn nằm ở các mặt hàng thành phần"

DX_DU = "du"
DX_CAN_MUA = "can_mua"
DX_MOT_PHAN = "mr_mot_phan"
DX_DA_CO_MR = "da_co_mr"


# ---------------------------------------------------------------- hàm thuần
def sl_con_giao(stock_qty, qty, delivered_qty) -> float:
	"""Phần CÒN PHẢI GIAO của một dòng đơn, theo đơn vị tồn kho.

	`stock_qty` là cả dòng theo đơn vị tồn kho; `qty` và `delivered_qty` theo
	đơn vị bán. Đơn đã giao một phần mà vẫn đòi đủ `stock_qty` thì luôn báo
	thiếu sai — hàng đã giao đã rời kho rồi.
	"""
	qty = flt(qty)
	if qty <= 0:
		return 0.0
	con = max(qty - flt(delivered_qty), 0)
	return flt(flt(stock_qty) * con / qty, DO_CHINH_XAC)


def ton_kha_dung(ton_hien_tai, ton_het_han, giu_don_khac) -> float:
	"""Tồn có thể sử dụng = tồn hiện tại − lô hết hạn − đã giữ cho đơn khác.

	`ton_het_han` là tổng tồn của các lô ĐÃ hết hạn — chỉ trừ thứ BIẾT CHẮC
	là hết hạn. Mặt hàng không theo lô thì truyền 0.
	"""
	dung_duoc = flt(ton_hien_tai) - max(flt(ton_het_han), 0)
	return flt(max(dung_duoc - flt(giu_don_khac), 0), DO_CHINH_XAC)


def chia_ton(yeu_cau, kha_dung) -> list:
	"""Chia tồn có thể sử dụng cho các dòng theo thứ tự dòng.

	`yeu_cau`: `[(khoa, so_luong), ...]`, `khoa = (item_code, kho)`.
	`kha_dung`: `{khoa: so_luong}`.
	Trả `[(ton_dong_nay_thay, so_thieu), ...]` cùng thứ tự.

	Hai dòng cùng mặt hàng, cùng kho dùng CHUNG một lượng tồn: dòng trước lấy
	trước, dòng sau chỉ thấy phần còn lại.
	"""
	con = {k: max(flt(v), 0) for k, v in kha_dung.items()}
	ket_qua = []
	for khoa, sl in yeu_cau:
		thay = flt(con.get(khoa), DO_CHINH_XAC)
		cap = min(flt(sl), thay)
		con[khoa] = thay - cap
		ket_qua.append((thay, flt(flt(sl) - cap, DO_CHINH_XAC)))
	return ket_qua


def de_xuat(sl_thieu, mr_da_phu) -> dict:
	"""Cột "Đề xuất" của một dòng (spec §5.4).

	`mr_da_phu` là phần MR CHƯA NHẬN VỀ KHO. Chỉ tính tới mức bằng số thiếu:
	MR 10 cho một dòng nay chỉ còn thiếu 6 thì phủ 6, không phải 10.
	"""
	thieu = max(flt(sl_thieu), 0)
	phu = min(max(flt(mr_da_phu), 0), thieu)
	can_mua = flt(thieu - phu, DO_CHINH_XAC)
	if thieu <= 0:
		ma = DX_DU
	elif phu <= 0:
		ma = DX_CAN_MUA
	elif can_mua > 0:
		ma = DX_MOT_PHAN
	else:
		ma = DX_DA_CO_MR
	return {"ma": ma, "mr_da_phu": flt(phu, DO_CHINH_XAC), "can_mua": can_mua}


def sl_mua(can_mua, don_vi_nguyen: bool) -> float:
	"""Số lượng ghi lên Material Request cho một dòng thiếu.

	Đơn vị chỉ nhận số nguyên thì làm tròn LÊN: ERPNext từ chối 2,3 Hộp, và
	thiếu 2,3 mà mua 2 là vẫn thiếu.
	"""
	sl = flt(can_mua, DO_CHINH_XAC)
	return float(math.ceil(sl)) if don_vi_nguyen else sl


def ly_do_khong_tra(row, thong_tin_item, la_bo: bool):
	"""Vì sao KHÔNG tra được tồn cho dòng này, hoặc `None` nếu tra được.

	Dòng có lý do thì các cột tồn hiện `—`, không hiện 0: "tồn 0" nghĩa là
	hết hàng, "không biết" là chuyện khác.
	"""
	# Bộ sản phẩm xét TRƯỚC: ERPNext buộc mã gộp của Product Bundle là mặt
	# hàng KHÔNG quản lý tồn, nên xét sau thì lý do này không bao giờ hiện.
	if la_bo:
		return LY_DO_BO
	if not thong_tin_item or not cint(thong_tin_item.get("is_stock_item")):
		return LY_DO_KHONG_TON
	if cint(row.get("delivered_by_supplier")):
		return LY_DO_GIAO_THANG
	if not row.get("warehouse"):
		return LY_DO_KHONG_KHO
	return None


# ------------------------------------------------------------- đọc CSDL
def _ton_hien_tai(item_code: str, warehouse: str) -> float:
	"""`Bin.actual_qty`. Không có dòng `Bin` = chưa từng có hàng = 0 THẬT."""
	return flt(
		frappe.db.get_value(
			"Bin", {"item_code": item_code, "warehouse": warehouse}, "actual_qty"
		),
		DO_CHINH_XAC,
	)


def _ton_het_han(item_code: str, warehouse: str) -> float:
	"""Tổng tồn của các lô ĐÃ hết hạn tại một kho.

	= (mọi lô, `for_stock_levels=True`) − (lô còn hạn và lô không khai hạn).
	Hỏi đúng hàm ERPNext dùng khi tự chọn lô để xuất, để "hết hạn" ở đây và
	"không xuất được" ở phiếu giao là cùng một định nghĩa.

	Tính phần HẾT HẠN rồi trừ, KHÔNG lấy thẳng "tổng lô còn hạn" làm tồn dùng
	được: đo trên site thử 12/10/2026 có mặt hàng theo lô mà tồn `Bin` không
	có sổ lô đi kèm (1/60). Lấy tổng lô còn hạn thì mặt hàng đó ra 0 và báo
	thiếu sai; cách này chỉ trừ thứ biết chắc là hết hạn.
	"""
	from erpnext.stock.doctype.batch.batch import get_batch_qty

	def tong(**kw):
		lo = get_batch_qty(item_code=item_code, warehouse=warehouse, **kw) or []
		return sum(flt(b.get("qty")) for b in lo)

	return flt(max(tong(for_stock_levels=True) - tong(), 0), DO_CHINH_XAC)


def _ton_lo_vo_hieu(item_code: str, warehouse: str) -> float:
	"""Tổng tồn của các lô bị VÔ HIỆU HOÁ (`Batch.disabled`) tại một kho.

	Lô cách ly / thu hồi: hàng vẫn nằm trong `Bin` nhưng ERPNext không cho
	chọn lô đó để xuất. `get_batch_qty` bỏ lô vô hiệu ở CẢ HAI lời gọi của
	`_ton_het_han`, nên chúng không lọt vào phần "hết hạn" — phải đếm riêng,
	và vì thế cũng không bị trừ hai lần khi lô vừa hết hạn vừa vô hiệu.
	"""
	kq = frappe.db.sql(
		"""
		select sum(sbe.qty)
		from `tabSerial and Batch Entry` sbe
		join `tabSerial and Batch Bundle` sbb on sbb.name = sbe.parent
		join `tabBatch` b on b.name = sbe.batch_no
		where sbb.item_code = %(item)s and sbe.warehouse = %(kho)s
			and sbb.docstatus = 1 and sbb.is_cancelled = 0 and b.disabled = 1
		""",
		{"item": item_code, "kho": warehouse},
	)
	return flt(max(flt(kq[0][0] if kq else 0), 0), DO_CHINH_XAC)


def _bo_trong_don(so) -> dict:
	"""Thành phần Product Bundle của CHÍNH đơn này còn phải giao, theo
	`(item_code, kho)`.

	Đơn vừa có một bộ chứa mặt hàng X vừa có một dòng lẻ X: cả hai rút từ
	cùng một lượng tồn. Dòng bộ hiện "—" (không tra tồn mã gộp), nhưng phần X
	nó cần vẫn phải trừ khỏi tồn mà dòng lẻ thấy.
	"""
	con_giao = {
		r.name: (max(flt(r.qty) - flt(r.delivered_qty), 0) / flt(r.qty)) if flt(r.qty) else 0
		for r in so.get("items") or []
	}
	kq = {}
	for p in so.get("packed_items") or []:
		if not p.item_code or not p.warehouse or p.item_code == p.parent_item:
			continue
		khoa = (p.item_code, p.warehouse)
		kq[khoa] = flt(
			kq.get(khoa, 0) + flt(p.qty) * con_giao.get(p.parent_detail_docname, 1),
			DO_CHINH_XAC,
		)
	return kq


def _giu_cho_don_khac(item_code: str, warehouse: str, tru_don: str) -> float:
	"""Phần còn phải giao của các Sales Order KHÁC đã Submit.

	Là BẢN SAO truy vấn của `erpnext.stock.stock_balance.get_reserved_qty`
	(nguồn của `Bin.reserved_qty`), thêm đúng một điều kiện `parent != tru_don`
	ở mỗi nhánh. Không lấy `Bin.reserved_qty` rồi tự trừ phần của đơn đang
	xem: phép trừ viết tay phải khớp từng nhánh (hàng trả lại, Product Bundle)
	mới không lệch. Bài test `…khop_dung_ham_goc…` ghim hai truy vấn vào nhau.
	"""
	khong_giu_khi_tra = cint(
		frappe.db.get_single_value(
			"Selling Settings", "dont_reserve_sales_order_qty_on_sales_return"
		)
	)
	kq = frappe.db.sql(
		f"""
		select
			sum(dnpi_qty * ((so_item_qty - so_item_delivered_qty
				- if({khong_giu_khi_tra}, so_item_returned_qty, 0)) / so_item_qty))
		from
			(
				(select
					dnpi.qty as dnpi_qty,
					(
						select qty from `tabSales Order Item`
						where name = dnpi.parent_detail_docname
						and (delivered_by_supplier is null or delivered_by_supplier = 0)
					) as so_item_qty,
					(
						select delivered_qty from `tabSales Order Item`
						where name = dnpi.parent_detail_docname
						and delivered_by_supplier = 0
					) as so_item_delivered_qty,
					(
						select returned_qty from `tabSales Order Item`
						where name = dnpi.parent_detail_docname
						and delivered_by_supplier = 0
					) as so_item_returned_qty,
					dnpi.parent, dnpi.name
				from `tabPacked Item` dnpi
				where dnpi.item_code = %(item)s and dnpi.warehouse = %(kho)s
					and dnpi.parenttype = 'Sales Order'
					and dnpi.item_code != dnpi.parent_item
					and dnpi.parent != %(tru)s
					and exists (select 1 from `tabSales Order` so
						where so.name = dnpi.parent and so.docstatus = 1
						and so.status not in ('On Hold', 'Closed')))
			union
				(select
					so_item.stock_qty as dnpi_qty,
					so_item.qty as so_item_qty,
					so_item.delivered_qty as so_item_delivered_qty,
					so_item.returned_qty as so_item_returned_qty,
					so_item.parent, so_item.name
				from `tabSales Order Item` so_item
				where so_item.item_code = %(item)s and so_item.warehouse = %(kho)s
					and (so_item.delivered_by_supplier is null
						or so_item.delivered_by_supplier = 0)
					and so_item.parent != %(tru)s
					and exists (select 1 from `tabSales Order` so
						where so.name = so_item.parent and so.docstatus = 1
						and so.status not in ('On Hold', 'Closed')))
			) tab
		where so_item_qty >= so_item_delivered_qty
		""",
		{"item": item_code, "kho": warehouse, "tru": tru_don or ""},
	)
	return flt(kq[0][0] if kq else 0, DO_CHINH_XAC)


def _don_nhap_khac(item_code: str, warehouse: str, tru_don: str):
	"""Các đơn NHÁP khác cùng mặt hàng, cùng kho — chỉ để ghi chú (spec §5.3)."""
	sl, so_don = frappe.db.sql(
		"""
		select coalesce(sum(i.stock_qty), 0), count(distinct i.parent)
		from `tabSales Order Item` i
		join `tabSales Order` s on s.name = i.parent
		where s.docstatus = 0 and i.item_code = %(item)s
			and i.warehouse = %(kho)s and i.parent != %(tru)s
		""",
		{"item": item_code, "kho": warehouse, "tru": tru_don or ""},
	)[0]
	if not so_don:
		return None
	return {"sl": flt(sl, DO_CHINH_XAC), "so_don": cint(so_don)}


def _mr_theo_dong(so_details: list, khoa: bool = False) -> dict:
	"""Phần Material Request CHƯA NHẬN VỀ KHO, gom theo dòng đơn.

	`stock_qty − received_qty`, không phải `stock_qty`: hàng đã nhận thì đã
	nằm trong tồn hiện tại, đếm cả số MR gốc là đếm hai lần. Tính cả MR nháp
	lẫn MR đã Submit; bỏ MR đã huỷ và MR Stopped.

	`khoa=True` biến truy vấn thành ĐỌC CÓ KHOÁ (`for update`) — chỉ đường
	tạo MR dùng. CSDL chạy REPEATABLE READ: một SELECT thường đọc theo ảnh
	chụp mở từ đầu yêu cầu, nên không thấy MR nháp mà người khác vừa commit
	trong lúc mình chờ khoá dòng đơn. Đọc có khoá thì thấy.
	"""
	so_details = [n for n in so_details if n]
	if not so_details:
		return {}
	rows = frappe.db.sql(
		f"""
		select mri.sales_order_item, mri.parent,
			greatest(mri.stock_qty - mri.received_qty, 0) as con
		from `tabMaterial Request Item` mri
		join `tabMaterial Request` mr on mr.name = mri.parent
		where mri.sales_order_item in %(ds)s
			and mr.material_request_type = 'Purchase'
			and mr.docstatus in (0, 1)
			and mr.status not in ('Stopped', 'Cancelled')
		order by mr.creation
		{"for update" if khoa else ""}
		""",
		{"ds": tuple(so_details)},
		as_dict=True,
	)
	kq = {}
	for r in rows:
		if flt(r.con) <= 0:
			continue
		d = kq.setdefault(r.sales_order_item, {"sl": 0.0, "mr": []})
		d["sl"] = flt(d["sl"] + flt(r.con), DO_CHINH_XAC)
		if r.parent not in d["mr"]:
			d["mr"].append(r.parent)
	return kq


# ------------------------------------------------------------ dựng bảng
def _dong_trong(**kw) -> dict:
	d = {
		"so_detail": None, "idx": 0, "item_code": None, "item_name": "",
		"kho": None, "dvt": None, "ly_do": None, "sl_yeu_cau": None,
		"ton_hien_tai": None, "ton_kha_dung": None, "sl_thieu": None,
		"mr_da_phu": None, "can_mua": None, "de_xuat": None, "mr": [],
		"don_nhap_khac": None, "giu_don_khac": None, "bo_trong_don": None,
	}
	d.update(kw)
	return d


def bang_cho_don(so, khoa_mr: bool = False) -> dict:
	"""Bảng đối sánh tồn kho cho một Sales Order (spec §5).

	`so` là document Sales Order (đã lưu hay đang dựng trong bộ nhớ đều được).
	Chỉ ĐỌC; không ghi gì vào đơn hay vào CSDL. `khoa_mr=True` chỉ dành cho
	đường tạo MR (xem `_mr_theo_dong`).
	"""
	dong_don = list(so.get("items") or [])
	ma_hang = sorted({r.item_code for r in dong_don if r.item_code})
	thong_tin = {}
	bo = set()
	if ma_hang:
		thong_tin = {
			i.name: i
			for i in frappe.get_all(
				"Item",
				filters={"name": ["in", ma_hang]},
				fields=["name", "is_stock_item", "has_batch_no"],
			)
		}
		bo = set(
			frappe.get_all(
				"Product Bundle",
				filters={"name": ["in", ma_hang], "disabled": 0},
				pluck="name",
			)
		)
	mr = _mr_theo_dong([r.name for r in dong_don], khoa=khoa_mr)
	bo_cua_don = _bo_trong_don(so)

	nguon = {}
	bang = []
	for r in dong_don:
		item = thong_tin.get(r.item_code)
		d = _dong_trong(
			so_detail=r.name, idx=r.idx, item_code=r.item_code,
			item_name=r.item_name or r.item_code or "", kho=r.warehouse,
			dvt=r.stock_uom,
			ly_do=ly_do_khong_tra(r, item, r.item_code in bo),
		)
		bang.append(d)
		if d["ly_do"]:
			continue
		khoa = (r.item_code, r.warehouse)
		if khoa not in nguon:
			ton = _ton_hien_tai(r.item_code, r.warehouse)
			# Hết hạn + vô hiệu hoá: hai tập lô rời nhau (xem `_ton_lo_vo_hieu`).
			het_han = (
				_ton_het_han(r.item_code, r.warehouse)
				+ _ton_lo_vo_hieu(r.item_code, r.warehouse)
				if cint(item.has_batch_no) else 0
			)
			giu = _giu_cho_don_khac(r.item_code, r.warehouse, so.name)
			bo_dung = flt(bo_cua_don.get(khoa))
			nguon[khoa] = {
				"ton_hien_tai": ton,
				"kha_dung": ton_kha_dung(ton, het_han, giu + bo_dung),
				"bo_trong_don": bo_dung if bo_dung > 0 else None,
				# Chỉ để GHI CHÚ: hai đơn đã Submit tranh cùng một lượng tồn
				# thì mỗi đơn trừ trọn phần của đơn kia và CẢ HAI đều báo
				# thiếu. Hiện con số này ra để nhân viên thấy vì sao, trước
				# khi lập hai MR cho cùng một chỗ thiếu.
				"giu_don_khac": giu if giu > 0 else None,
				"don_nhap_khac": _don_nhap_khac(r.item_code, r.warehouse, so.name),
			}
		d["sl_yeu_cau"] = sl_con_giao(r.stock_qty, r.qty, r.delivered_qty)
		d["ton_hien_tai"] = nguon[khoa]["ton_hien_tai"]
		d["don_nhap_khac"] = nguon[khoa]["don_nhap_khac"]
		d["giu_don_khac"] = nguon[khoa]["giu_don_khac"]
		d["bo_trong_don"] = nguon[khoa]["bo_trong_don"]

	tra_duoc = [d for d in bang if not d["ly_do"]]
	chia = chia_ton(
		[((d["item_code"], d["kho"]), d["sl_yeu_cau"]) for d in tra_duoc],
		{k: v["kha_dung"] for k, v in nguon.items()},
	)
	for d, (thay, thieu) in zip(tra_duoc, chia):
		phu = mr.get(d["so_detail"]) or {}
		dx = de_xuat(thieu, phu.get("sl"))
		d.update(
			ton_kha_dung=thay, sl_thieu=thieu, de_xuat=dx["ma"],
			mr_da_phu=dx["mr_da_phu"], can_mua=dx["can_mua"],
			mr=list(phu.get("mr") or []),
		)

	con_mua = any(flt(d["can_mua"]) > 0 for d in tra_duoc)
	return {
		"dong": bang,
		"tong": {
			"so_dong": len(tra_duoc),
			"so_thieu": sum(1 for d in tra_duoc if flt(d["sl_thieu"]) > 0),
		},
		# ERPNext chỉ cho sinh Material Request từ Sales Order đã Submit.
		"co_the_tao_mr": bool(
			cint(so.docstatus) == 1
			and so.get("status") not in ("On Hold", "Closed")
			and con_mua
		),
	}


# ------------------------------------------------------------- endpoint
def _don_duoc_doc(order: str):
	"""Sales Order mà người gọi được xem bảng tồn, hoặc ném PermissionError.

	Ba chốt, theo thứ tự: không phải tài khoản cổng, có vai nội bộ, đọc được
	đơn. Hai chốt đầu là chốt thật — tài khoản cổng khách hàng qua được chốt
	thứ ba với đơn của chính họ. Chốt đầu dùng đúng định nghĩa "tài khoản
	cổng" của cả app (`permissions._is_restricted_user`), để một tài khoản
	khách lỡ được gán thêm vai nội bộ vẫn không thấy tồn của Miyano.
	"""
	from miyano_portal.permissions import _is_restricted_user

	if _is_restricted_user(frappe.session.user):
		raise frappe.PermissionError("Bạn không có quyền xem đối sánh tồn kho.")
	if not set(ROLE_NOI_BO) & set(frappe.get_roles()):
		raise frappe.PermissionError("Bạn không có quyền xem đối sánh tồn kho.")
	so = frappe.get_doc("Sales Order", order)
	so.check_permission("read")
	return so


@frappe.whitelist()
def doi_sanh_ton(order: str) -> dict:
	"""Bảng đối sánh tồn kho của một Sales Order, cho form trên Desk.

	Phép tính hỏng thì trả `{"loi": …}` thay vì ném: bảng là thông tin phụ,
	nó hỏng không được kéo theo cả form Sales Order. Lỗi QUYỀN thì vẫn ném —
	`_don_duoc_doc` nằm NGOÀI khối try.
	"""
	so = _don_duoc_doc(order)
	try:
		bang = bang_cho_don(so)
	except Exception:
		frappe.log_error(
			title="Đối sánh tồn kho: không tính được bảng",
			message=frappe.get_traceback(with_context=True),
		)
		return {"loi": "Không tính được bảng đối sánh tồn kho. Lỗi đã được ghi lại."}
	bang["co_the_tao_mr"] = bool(
		bang["co_the_tao_mr"] and frappe.has_permission("Material Request", "create")
	)
	return bang


@frappe.whitelist(methods=["POST"])
def tao_mr_phan_thieu(order: str) -> dict:
	"""Tạo MỘT Material Request NHÁP cho phần thiếu của đơn (spec §6).

	Không gọi `sales_order.make_material_request` của ERPNext: hàm đó lấy toàn
	bộ số lượng đơn (không trừ tồn) và chỉ đếm MR đã Submit khi chống trùng.

	Không bao giờ Submit — bộ phận mua kiểm tra rồi tự Submit.
	"""
	so = _don_duoc_doc(order)
	if not frappe.has_permission("Material Request", "create"):
		raise frappe.PermissionError(
			"Bạn không có quyền tạo yêu cầu mua hàng (Material Request)."
		)
	# Khoá dòng đơn rồi MỚI đọc trạng thái và tính lại: hai người bấm sát
	# nhau xếp hàng ở đây. Mọi thứ quyết định "có tạo không, tạo bao nhiêu"
	# đều đọc SAU khoá và bằng đọc có khoá — `so` nạp ở trên là bản trước
	# khoá, đơn có thể đã bị đóng hay huỷ trong lúc chờ.
	trang_thai = frappe.db.get_value(
		"Sales Order", so.name, ["docstatus", "status"], as_dict=True, for_update=True
	)
	if cint(trang_thai.docstatus) != 1:
		frappe.throw(
			"Chỉ tạo được yêu cầu mua hàng cho đơn đã xác nhận.",
			frappe.ValidationError,
		)
	if trang_thai.status in ("On Hold", "Closed"):
		frappe.throw(
			"Đơn đang tạm giữ hoặc đã đóng — không tạo yêu cầu mua hàng.",
			frappe.ValidationError,
		)

	# Số thiếu tính lại tại máy chủ, không nhận từ trình duyệt — tồn có thể
	# đã đổi từ lúc bảng hiện.
	thieu = [
		d for d in bang_cho_don(so, khoa_mr=True)["dong"] if flt(d["can_mua"]) > 0
	]
	if not thieu:
		frappe.throw(
			"Đơn không còn phần thiếu nào cần mua thêm.", frappe.ValidationError
		)

	# Mỗi dòng đơn thiếu là MỘT dòng MR (để phần phủ tính được theo từng dòng
	# đơn), nên hai dòng đơn cùng mặt hàng sinh hai dòng MR cùng mặt hàng.
	# ERPNext chỉ nhận thế khi Buying Settings cho phép; báo trước bằng tiếng
	# Việt thay vì để nó ném "Same item cannot be entered multiple times".
	ma = [d["item_code"] for d in thieu]
	if len(set(ma)) < len(ma) and not cint(
		frappe.db.get_single_value("Buying Settings", "allow_multiple_items")
	):
		frappe.throw(
			"Đơn có nhiều dòng thiếu của cùng một mặt hàng. Bật «Allow Item To Be "
			"Added Multiple Times in a Transaction» trong Buying Settings rồi "
			"tạo lại yêu cầu mua hàng.",
			frappe.ValidationError,
		)

	hom_nay = getdate(today())
	ngay_giao = {r.name: r.delivery_date for r in so.items}

	mr = frappe.new_doc("Material Request")
	mr.material_request_type = "Purchase"
	mr.company = so.company
	mr.transaction_date = hom_nay
	dvt_nguyen = {
		u.name: cint(u.must_be_whole_number)
		for u in frappe.get_all(
			"UOM",
			filters={"name": ["in", sorted({d["dvt"] for d in thieu if d["dvt"]})]},
			fields=["name", "must_be_whole_number"],
		)
	}
	for d in thieu:
		ngay = getdate(ngay_giao.get(d["so_detail"]) or so.delivery_date or hom_nay)
		sl = sl_mua(d["can_mua"], bool(dvt_nguyen.get(d["dvt"])))
		mr.append("items", {
			"item_code": d["item_code"],
			"item_name": d["item_name"],
			"qty": sl,
			"uom": d["dvt"],
			"stock_uom": d["dvt"],
			"conversion_factor": 1,
			"stock_qty": sl,
			"warehouse": d["kho"],
			"schedule_date": max(ngay, hom_nay),
			"sales_order": so.name,
			"sales_order_item": d["so_detail"],
		})
	mr.schedule_date = min(getdate(r.schedule_date) for r in mr.items)
	mr.insert()
	return {"name": mr.name, "so_dong": len(mr.items)}
