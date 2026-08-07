"""Miyano giao hàng → Phiếu Nhập Kho NHÁP trong kho của khách (thiết kế §4.3).

RÀNG BUỘC CAO NHẤT, TRÊN CẢ VIỆC TÍNH NĂNG NÀY CHẠY ĐÚNG: hook này không bao
giờ được làm Delivery Note của Miyano fail. Kho khách hàng là một sổ phụ trợ;
việc bán hàng của Miyano thì không. Mọi lối vào từ hooks.py đều đi qua
`_chay_an_toan()`, nơi mọi Exception bị nuốt và ghi vào Error Log.

Ba điều dễ làm sai mà đã được cố định ở đây:

1. **Nháp, không submit.** Thủ kho phải đối chiếu hàng thực nhận. Giao thiếu
   hoặc vỡ mà tự cộng tồn thì sổ sai ngay từ ngày đầu, và sổ là append-only
   nên không sửa lại được.
2. **Nuốt lỗi phải kèm rollback tới savepoint.** Nuốt suông sẽ để lại dữ liệu
   nửa vời (ví dụ đã tạo Customer Warehouse Item rồi mới hỏng ở bước tạo
   phiếu). Bản ghi Error Log thì KHÔNG bị rollback cuốn theo dù đặt trước hay
   sau — `tabError Log` khai `"engine": "MyISAM"`, tức là bảng phi giao dịch
   (đã đo: insert rồi `rollback to savepoint`, dòng log vẫn còn). Vẫn rollback
   trước rồi mới log, vì nếu chính lời gọi log hỏng thì dữ liệu nửa vời đã kịp
   biến mất.
3. **Đọc lô: bundle TRƯỚC, `batch_no` sau.** Build này bật cả hai cơ chế của
   ERPNext v15. Hơn nữa `StockController.make_bundle_using_old_serial_batch_fields()`
   chạy trong `DeliveryNote.on_submit`, tức là TRƯỚC hook này, nên một dòng chỉ
   gắn `batch_no` cũng đã có `serial_and_batch_bundle` lúc hook chạy. Đọc
   `batch_no` trước sẽ mất thông tin: một dòng DN tách nhiều lô chỉ có bundle
   mới kể được, còn `batch_no` khi đó rỗng.
"""

import frappe

from miyano_portal.kho.ledger import LOT_KHONG_CO

LOAI_NHAP = "Từ đơn hàng Miyano"

_SAVEPOINT = "kho_delivery_hook"

# Data field trên Customer Stock Receipt; cắt cho khớp giới hạn cột.
_MAX_DATA = 140


# ---------------------------------------------------------------- lối vào hook
def on_delivery_note_submit(doc, method=None):
	_chay_an_toan(doc, _tu_delivery_note, "Kho khách: lỗi khi tạo phiếu nhập từ Delivery Note")


def on_delivery_note_cancel(doc, method=None):
	_chay_an_toan(doc, _huy_theo_delivery_note, "Kho khách: lỗi khi huỷ phiếu nhập theo Delivery Note")


def _chay_an_toan(doc, fn, title: str) -> None:
	"""Chạy `fn(doc)` sao cho KHÔNG có đường nào ném lỗi ra Delivery Note.

	`frappe.local.message_log` cũng được cắt về đúng độ dài trước khi chạy:
	nếu không, một `frappe.throw()` bị nuốt ở bên trong (ví dụ
	`voucher.validate_ngay`) vẫn để lại một toast đỏ tiếng Việt trên màn hình
	của nhân viên Miyano sau khi giao hàng THÀNH CÔNG — trông y hệt như việc
	giao hàng vừa hỏng.
	"""
	so_message = len(getattr(frappe.local, "message_log", []) or [])
	frappe.db.savepoint(_SAVEPOINT)
	try:
		fn(doc)
	except Exception:
		# Rollback TRƯỚC, log SAU — để nếu chính lời gọi log hỏng thì dữ liệu
		# nửa vời đã kịp biến mất. (Bản thân dòng Error Log không phụ thuộc
		# thứ tự này: `tabError Log` là MyISAM nên rollback không đụng tới nó.)
		try:
			frappe.db.rollback(save_point=_SAVEPOINT)
		except Exception:
			pass
		try:
			del frappe.local.message_log[so_message:]
		except Exception:
			pass
		try:
			frappe.log_error(
				title=title,
				message=frappe.get_traceback(with_context=True),
				reference_doctype=doc.doctype,
				reference_name=doc.name,
			)
		except Exception:
			# Nếu ngay cả việc ghi log cũng hỏng (transaction đang hỏng, khoá
			# hết hạn...) thì vẫn tuyệt đối không được để lỗi thoát ra: đó
			# đúng là kiểu vỡ Delivery Note mà cả module này sinh ra để chặn.
			pass


# --------------------------------------------------------------------- on_submit
def _tu_delivery_note(dn) -> str | None:
	if dn.get("is_return"):
		# Hàng đi NGƯỢC về Miyano. Cộng vào kho khách sẽ là nhân đôi hàng.
		return None

	kho = _kho_cua_khach(dn.customer)
	if not kho:
		# Khách chưa mở kho — bỏ qua im lặng, đúng thiết kế §4.3.
		return None

	if _phieu_dang_song(dn.name):
		return None

	dong = []
	co_canh_bao_dvt = False
	cache_vat_tu: dict[str, str] = {}
	for row in dn.items:
		vat_tu, canh_bao = _vat_tu_trong_kho(kho, row, cache_vat_tu)
		if canh_bao:
			co_canh_bao_dvt = True
		for so_lo, han_su_dung, so_luong in _lo_cua_dong(row):
			if so_luong <= 0:
				continue
			dong.append({
				"vat_tu": vat_tu,
				"so_lo": so_lo,
				"han_su_dung": han_su_dung,
				"so_luong": so_luong,
				"don_gia": float(row.rate or 0),
				"ghi_chu": (canh_bao or "")[:_MAX_DATA],
			})
	if not dong:
		return None

	return _tao_phieu(dn, kho, dong, co_canh_bao_dvt)


def _tao_phieu(dn, kho: str, dong: list[dict], co_canh_bao_dvt: bool = False) -> str:
	"""Tách riêng khỏi _tu_delivery_note() để test ép hỏng được ĐÚNG bước ghi
	phiếu, sau khi danh mục vật tư đã bị đụng vào — đó là kịch bản mà savepoint
	phải cuốn lại, và nó không kiểm được nếu chỉ ép hỏng ở bước đầu tiên."""
	ngay_phieu, ghi_chu_ngay = _ngay_phieu_khong_mat_hang(dn, kho)
	dien_giai = (
		f"Tự động tạo từ phiếu giao hàng {dn.name} của Miyano. "
		"Vui lòng đối chiếu hàng thực nhận rồi mới ghi sổ."
		+ ghi_chu_ngay
	)
	if co_canh_bao_dvt:
		# Đủ để thủ kho THẤY trước khi ghi sổ — không chặn: đúng khuôn nháp-
		# rồi-đối-chiếu của cả tính năng này (§4.3), không phải một chốt chặn
		# mới. Cảnh báo chi tiết theo từng dòng nằm ở `ghi_chu` của dòng đó.
		dien_giai += (
			" CẢNH BÁO: có dòng ĐVT trên Delivery Note khác ĐVT đang lưu trong "
			"danh mục kho khách — xem cột Ghi chú của từng dòng trước khi ghi sổ."
		)
	phieu = frappe.get_doc({
		"doctype": "Customer Stock Receipt",
		"kho": kho,
		"ngay": ngay_phieu,
		"loai_nhap": LOAI_NHAP,
		"nguoi_giao": (dn.company or "")[:_MAX_DATA],
		"chung_tu_kem": dn.name[:_MAX_DATA],
		"delivery_note": dn.name,
		"sales_order": _sales_order_cua(dn),
		"dien_giai": dien_giai,
		"items": dong,
	})
	phieu.insert(ignore_permissions=True)
	return phieu.name


def _ngay_phieu_khong_mat_hang(dn, kho: str) -> tuple[str, str]:
	"""Chọn `ngay` cho phiếu sao cho hàng giao trước `ngay_bat_dau` của kho
	KHÔNG BAO GIỜ biến mất.

	`CustomerStockReceipt.validate()` (qua `voucher.validate_ngay`) chặn cứng
	mọi phiếu có `ngay` trước `ngay_bat_dau` — đúng ràng buộc §7. Nếu cứ đặt
	`ngay = dn.posting_date` như trước, một DN backdated trước mốc đó khiến
	chính `phieu.insert()` NÉM LỖI ở bước validate; lỗi đó bị `_chay_an_toan()`
	nuốt (đúng thiết kế — DN không được phép fail), và hệ quả là KHÔNG CÓ
	PHIẾU NÀO được tạo: hàng đã giao vật lý biến mất khỏi kho khách hàng, chỉ
	để lại một dòng Error Log không ai đọc.

	Ba phương án đã cân nhắc:
	  1. Giữ nguyên hiện trạng (bỏ phiếu khi backdated) — LOẠI: mất hàng thật,
	     không gì hiển thị cho khách biết hàng đã tới.
	  2. Nới `validate_ngay()` để chấp nhận phiếu backdated — LOẠI: ràng buộc
	     đó áp dụng cho MỌI phiếu, kể cả phiếu thủ kho tự tay tạo (tồn đầu kỳ,
	     nhập khác); nới riêng cho đường DN sẽ mở lỗ cho các đường khác vì
	     `validate_ngay()` dùng chung.
	  3. **Ghim `ngay` vào đúng `ngay_bat_dau`** (ngày sớm nhất kho còn nhận),
	     và ghi ngày giao hàng THẬT vào `dien_giai` — ĐÃ CHỌN: hàng luôn được
	     ghi nhận (không mất), ràng buộc §7 không bị nới cho bất kỳ đường nào,
	     và sai khác giữa ngày giao thật và ngày ghi sổ hiện rõ trên chứng từ
	     thay vì bị giấu — thủ kho đọc phiếu là biết ngay có bất thường.

	Hàm này không được phép ném lỗi: chỉ đọc một giá trị DB và so ngày.
	"""
	ngay_bat_dau = frappe.db.get_value("Customer Warehouse", kho, "ngay_bat_dau")
	ngay_dn = dn.posting_date
	if ngay_bat_dau and frappe.utils.getdate(ngay_dn) < frappe.utils.getdate(ngay_bat_dau):
		ghi_chu = (
			f" CẢNH BÁO: Delivery Note giao ngày {frappe.utils.formatdate(ngay_dn)}, "
			f"TRƯỚC Ngày bắt đầu quản lý kho ({frappe.utils.formatdate(ngay_bat_dau)}). "
			"Phiếu được ghi vào đúng Ngày bắt đầu quản lý kho để không mất hàng; "
			"ngày giao hàng thực tế là ngày nêu ở trên."
		)
		return ngay_bat_dau, ghi_chu
	return ngay_dn, ""


# --------------------------------------------------------------------- on_cancel
def _huy_theo_delivery_note(dn) -> None:
	"""Huỷ DN → gỡ phiếu nháp, hoặc đảo phiếu đã ghi sổ.

	Việc đảo KHÔNG được viết lại ở đây. `CustomerStockReceipt.on_cancel` đã
	biết cách: nó sinh một phiếu đảo đã submit mang số lượng ngược dấu rồi bật
	`da_dao` trên các dòng sổ gốc — bút toán đối ứng trên một sổ append-only,
	đúng một cơ chế đảo duy nhất trong toàn app. Viết lại ở đây sẽ là cơ chế
	thứ hai, và hai cơ chế đảo cùng tồn tại chính là cách sinh ra lỗi đảo hai
	lần.

	Lặp qua TẤT CẢ phiếu docstatus < 2 chứ không chỉ phiếu đầu: chống trùng ở
	on_submit đã đảm bảo chỉ có một, nhưng nếu vì lý do nào đó có hai thì bỏ
	sót một cái sẽ để lại tồn ma trong kho khách sau khi DN đã huỷ.
	"""
	for name, docstatus in frappe.get_all(
		"Customer Stock Receipt",
		filters={"delivery_note": dn.name, "docstatus": ["<", 2]},
		fields=["name", "docstatus"],
		as_list=True,
	):
		if docstatus == 0:
			# Phiếu nháp chưa chạm sổ: xoá hẳn. Frappe không cho cancel một
			# tài liệu docstatus=0, và để lại phiếu nháp mồ côi trỏ tới một DN
			# đã huỷ sẽ khiến thủ kho ghi sổ hàng không hề tới.
			frappe.delete_doc(
				"Customer Stock Receipt", name,
				ignore_permissions=True, delete_permanently=True,
			)
		else:
			phieu = frappe.get_doc("Customer Stock Receipt", name)
			phieu.flags.ignore_permissions = True
			phieu.cancel()


# ------------------------------------------------------------------ tra cứu kho
def _kho_cua_khach(customer: str) -> str | None:
	"""Kho ĐANG HOẠT ĐỘNG của khách. Kho đã tắt không nhận phiếu tự động:
	`active = 0` là cách thủ công để ngừng tính năng cho một khách, và một kho
	đã tắt mà vẫn tự mọc phiếu nháp thì cái công tắc đó vô nghĩa."""
	return frappe.db.get_value(
		"Customer Warehouse", {"customer": customer, "active": 1}, "name"
	)


def _phieu_dang_song(dn_name: str) -> str | None:
	"""Đã có phiếu nào cho DN này chưa? `docstatus < 2` nên tính cả phiếu ĐÃ
	GHI SỔ, không chỉ phiếu nháp — nếu chỉ đếm nháp thì chạy lại hook sau khi
	thủ kho đã ghi sổ sẽ cộng tồn lần thứ hai."""
	return frappe.db.get_value(
		"Customer Stock Receipt",
		{"delivery_note": dn_name, "docstatus": ["<", 2]},
		"name",
	)


def _sales_order_cua(dn) -> str | None:
	"""Các Sales Order mà DN này giao cho, giữ nguyên thứ tự dòng, bỏ trùng.

	Chỉ để truy vết, nên khi vượt quá độ dài field thì cắt chứ không ném lỗi.
	"""
	ds: list[str] = []
	for row in dn.items:
		so = row.get("against_sales_order")
		if so and so not in ds:
			ds.append(so)
	if not ds:
		return None
	gop = ", ".join(ds)
	return gop if len(gop) <= _MAX_DATA else ds[0][:_MAX_DATA]


# ------------------------------------------------------------------ vật tư kho
def _vat_tu_trong_kho(kho: str, row, cache: dict[str, str]) -> tuple[str, str | None]:
	"""Customer Warehouse Item tương ứng dòng DN, tạo mới nếu chưa có.

	KHÔNG BAO GIỜ tạo `Item` của ERPNext ở đây: `row.item_code` đã là một Item
	thật của Miyano, ta chỉ trỏ tới nó. Tạo Item từ một hook giao hàng sẽ đẻ
	rác vào catalog bán hàng của Miyano.

	Trả về `(tên vật tư kho khách, cảnh báo lệch ĐVT hoặc None)`. `dvt` của
	một Vật Tư Kho Khách chỉ được CHỐT ở lần tạo đầu tiên và hook KHÔNG BAO
	GIỜ ghi đè lại sau đó: đổi ĐVT của cả danh mục là quyết định nghiệp vụ của
	thủ kho, không phải việc một dòng giao hàng tự động được phép làm âm thầm.
	Khi TÁI SỬ DỤNG một vật tư đã có (khớp theo `item_code` hoặc `ma_vat_tu`),
	hàm chỉ SO SÁNH ĐVT của dòng DN với `dvt` đang lưu — gộp thẳng một lô ĐVT
	khác vào cùng tồn sẽ ra một con số sai đơn vị không cách nào phát hiện lại
	được sau khi đã cộng (ví dụ 10 Hộp + 10 Cái thành "20"), nên việc phải làm
	là lộ ra cho thủ kho thấy TRƯỚC khi ghi sổ, không phải tự quy đổi (ngoài
	phạm vi — xem review §Item 2).
	"""
	item_code = row.item_code
	dvt_dn = (row.get("uom") or "").strip()

	if item_code in cache:
		name = cache[item_code]
		return name, _canh_bao_lech_dvt(name, dvt_dn)

	name = frappe.db.get_value(
		"Customer Warehouse Item", {"kho": kho, "item_code": item_code}, "name"
	)
	if not name:
		# Khách có thể đã tự khai mã này (import tồn đầu kỳ) mà chưa gắn
		# item_code. Khớp theo mã, không phân biệt hoa thường — cùng quy tắc
		# với kho.import_ton_dau._match_vat_tu, để hai đường không đẻ ra hai
		# bản ghi cho cùng một mặt hàng.
		khop = frappe.db.sql(
			"""select name from `tabCustomer Warehouse Item`
			   where kho=%s and lower(ma_vat_tu)=%s limit 1""",
			(kho, (item_code or "").strip().lower()),
		)
		name = khop[0][0] if khop else None

	if name:
		cache[item_code] = name
		return name, _canh_bao_lech_dvt(name, dvt_dn)

	item = frappe.db.get_value(
		"Item", item_code, ["item_name", "stock_uom"], as_dict=True
	) or frappe._dict()
	vt = frappe.get_doc({
		"doctype": "Customer Warehouse Item",
		"kho": kho,
		"ma_vat_tu": item_code,
		"ten_vat_tu": row.get("item_name") or item.item_name or item_code,
		"dvt": dvt_dn or item.stock_uom or "Cái",
		"item_code": item_code,
	})
	vt.insert(ignore_permissions=True)
	name = vt.name

	cache[item_code] = name
	# Vừa tạo mới: dvt CHÍNH LÀ dvt_dn (hoặc rơi về mặc định), nên không thể
	# lệch với chính nó — không gọi _canh_bao_lech_dvt() để khỏi tốn một
	# truy vấn DB vô nghĩa.
	return name, None


def _canh_bao_lech_dvt(vat_tu: str, dvt_dn: str) -> str | None:
	"""So ĐVT trên dòng DN với `dvt` đang chốt của một Vật Tư Kho Khách đã có.

	Không phân biệt hoa/thường và khoảng trắng thừa — cùng độ khoan dung với
	quy tắc khớp mã ở `_vat_tu_trong_kho`, để "Hộp" và " hộp " không bị báo
	nhầm là lệch.

	KHÔNG BAO GIỜ ném lỗi: hàm này chạy trong đường tạo phiếu tự động của
	Delivery Note, phải giữ đúng bất biến "không bao giờ chặn Delivery Note"
	của cả module — chỉ ghi Error Log (đã đo: `tabError Log` là MyISAM, dòng
	log không mất khi savepoint bị rollback ở nhánh lỗi khác) và trả một chuỗi
	cảnh báo ngắn để gắn lên `ghi_chu` của dòng phiếu.
	"""
	dvt_dn = (dvt_dn or "").strip()
	if not dvt_dn:
		return None
	dvt_kho = frappe.db.get_value("Customer Warehouse Item", vat_tu, "dvt")
	if not dvt_kho or dvt_kho.strip().lower() == dvt_dn.lower():
		return None
	canh_bao = (
		f'CẢNH BÁO ĐVT: DN ghi "{dvt_dn}", danh mục kho đang lưu "{dvt_kho}". '
		"KHÔNG tự cộng gộp — kiểm tra lại trước khi ghi sổ."
	)
	try:
		frappe.log_error(
			title="Kho khách: lệch đơn vị tính khi nhận hàng từ Delivery Note",
			message=canh_bao,
			reference_doctype="Customer Warehouse Item",
			reference_name=vat_tu,
		)
	except Exception:
		# Ghi log hỏng không được phép lan thành lỗi chặn DN — cùng nguyên
		# tắc với _chay_an_toan(), áp cho riêng nhánh phụ này.
		pass
	return canh_bao


# ----------------------------------------------------------------- lô và hạn
def _entry_cua_bundle(bundle: str) -> list:
	return frappe.get_all(
		"Serial and Batch Entry",
		filters={"parent": bundle, "parenttype": "Serial and Batch Bundle"},
		fields=["batch_no", "qty"],
		order_by="idx asc",
	)


def _han_su_dung(so_lo: str) -> str | None:
	if not so_lo or so_lo == LOT_KHONG_CO:
		return None
	han = frappe.db.get_value("Batch", so_lo, "expiry_date")
	return str(han) if han else None


def _lo_cua_dong(row) -> list[tuple[str, str | None, float]]:
	"""Một dòng Delivery Note → danh sách (số lô, hạn dùng, số lượng).

	Thứ tự đọc: `serial_and_batch_bundle` TRƯỚC, `batch_no` sau, cuối cùng mới
	đến LOT_KHONG_CO. Xem docstring đầu module về lý do thứ tự này không đảo
	được.

	Gộp theo số lô TRƯỚC khi trả về. Hàng theo serial cho ra N entry qty 1;
	không gộp thì một dòng DN 50 cái thành 50 dòng phiếu nhập. Trường hợp này
	KHÔNG trùng với "một dòng tách nhiều lô" và không được test đó bắt.

	Số lượng trong bundle tính theo ĐVT tồn kho, còn `rate` của dòng DN tính
	theo ĐVT bán. Chia lại cho `conversion_factor` để số lượng và đơn giá trên
	phiếu cùng một hệ; nếu không, thành tiền của phiếu sẽ lệch đúng bằng hệ số
	quy đổi với mọi mặt hàng bán theo thùng/lốc.
	"""
	he_so = float(row.get("conversion_factor") or 1) or 1.0
	qty = abs(float(row.get("qty") or 0))

	bundle = row.get("serial_and_batch_bundle")
	if bundle:
		gop: dict[str, float] = {}
		for e in _entry_cua_bundle(bundle):
			so_lo = e.get("batch_no") or LOT_KHONG_CO
			gop[so_lo] = gop.get(so_lo, 0.0) + abs(float(e.get("qty") or 0)) / he_so
		ket_qua = [
			(so_lo, _han_su_dung(so_lo), sl) for so_lo, sl in gop.items() if sl > 0
		]
		if ket_qua:
			return ket_qua
		# Bundle rỗng (chưa submit, hoặc đã bị xoá entry): rơi xuống nhánh dưới
		# thay vì trả về danh sách rỗng, để dòng hàng không biến mất khỏi phiếu.

	if row.get("batch_no"):
		return [(row.batch_no, _han_su_dung(row.batch_no), qty)]

	return [(LOT_KHONG_CO, None, qty)]
