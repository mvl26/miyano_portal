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
from miyano_portal.portal_thong_bao_khach import bao_da_nhap_hang

LOAI_NHAP = "Từ đơn hàng Miyano"

_SAVEPOINT = "kho_delivery_hook"

# Data field trên Customer Stock Receipt; cắt cho khớp giới hạn cột.
_MAX_DATA = 140


# ---------------------------------------------------------------- lối vào hook
def on_delivery_note_submit(doc, method=None):
	_chay_an_toan(doc, _tu_delivery_note, "Kho khách: lỗi khi tạo phiếu nhập từ Delivery Note")
	# LỆNH GỌI RIÊNG, savepoint RIÊNG (brief 2026-08-15, QĐ nền 4) — không
	# gộp chung với lệnh trên. Nếu gộp, một lỗi ở BƯỚC GỬI THÔNG BÁO (chạy
	# SAU khi phiếu đã insert thành công trong CÙNG savepoint) sẽ rollback
	# LUÔN CẢ phiếu vừa tạo: mất dữ liệu thật (phiếu nhập) để đổi lấy một
	# thông báo phụ trợ. Tách savepoint nghĩa là hỏng ở đây chỉ mất thông
	# báo — đúng nguyên văn QĐ nền 4 ("hỏng thì mất thông báo, KHÔNG được
	# chặn phiếu giao hàng"), và phiếu đã tạo ở lệnh gọi trên không bị cuốn
	# theo.
	_chay_an_toan(doc, _bao_da_nhap_hang, "Kho khách: lỗi khi gửi thông báo đã nhập hàng")


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
				# BR-K16 (US-E3.2): mốc đối soát. `sl_giao` là SL Miyano GIAO
				# trên chính dòng này; `so_luong` (thực nhận) khởi tạo bằng
				# đúng giá trị đó — thủ kho sửa lại nếu lệch.
				"sl_giao": so_luong,
				# US-E3.6 (NL-3.7): lô rơi về LOT_KHONG_CO nghĩa là Item chưa
				# bật Has Batch No/Has Expiry Date phía Miyano. Cờ này chỉ
				# NÊU chứ không chặn giao.
				"thieu_lo_han": 1 if so_lo == LOT_KHONG_CO else 0,
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
	so_dot = _so_dot_cua(dn)
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
		"so_dot": so_dot,
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


# -------------------------------------------------------- thông báo đã nhập
def _bao_da_nhap_hang(dn) -> None:
	"""Thông báo khách "Miyano đã giao hàng, phiếu nhập chờ bạn kiểm".

	Tự tra lại phiếu qua `_phieu_dang_song(dn.name)` thay vì nhận tham số từ
	`_tu_delivery_note` — hai lệnh gọi `_chay_an_toan()` trong
	`on_delivery_note_submit` ĐỘC LẬP nhau (savepoint riêng, xem chú thích ở
	đó), nên hàm này không có cách nào biết trực tiếp _tu_delivery_note vừa
	trả về gì; tự truy vấn lại là cách duy nhất để hai lệnh gọi tách rời mà
	vẫn đồng bộ. Chi phí một truy vấn DB có index (`delivery_note`) không
	đáng kể so với việc gộp chung savepoint (xem rủi ro ở trên).

	KHÔNG gửi khi không có phiếu (hàng trả về Miyano, khách chưa mở kho, đã
	có phiếu từ trước) — cùng các nhánh im lặng của `_tu_delivery_note`.

	Task 8 (§5.8) — truyền thêm khoa phòng của SO ĐẦU TIÊN đứng sau DN
	(`_khoa_phong_dau_tien`) để `bao_da_nhap_hang` thu hẹp người nhận về
	đúng khoa, thay vì báo cho TOÀN BỘ tài khoản của khách hàng.
	"""
	if dn.get("is_return"):
		return
	kho = _kho_cua_khach(dn.customer)
	if not kho:
		return
	phieu = _phieu_dang_song(dn.name)
	if not phieu:
		return
	bao_da_nhap_hang(dn.customer, phieu, dn.name, khoa_phong=_khoa_phong_dau_tien(dn))


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


def _khoa_phong_dau_tien(dn) -> str | None:
	"""Khoa phòng của SO ĐẦU TIÊN mà DN này giao cho (Task 8, §5.8) — tái
	dùng ĐÚNG `_sales_order_dau_tien()` đã có cho `so_dot` ngay dưới, không
	dựng một cơ chế suy Sales Order thứ hai chỉ để phục vụ thông báo (spec
	§11 mục 5).

	Dùng để thu hẹp người nhận thông báo "đã nhập hàng" về đúng khoa, thay
	vì báo cho MỌI tài khoản của khách hàng (Task 8 fix — hôm nay, với một
	khách nhiều tài khoản, khoa Dược nhận thông báo về hàng của khoa Huyết
	học mỗi ngày).

	Trả `None` khi DN không qua Sales Order nào (bán lẻ) — nơi gọi
	(`bao_da_nhap_hang`) hiểu `None` là "không xác định được khoa" và tự rơi
	về hành vi CŨ (báo TOÀN BỘ tài khoản của khách), AN TOÀN HƠN so với thu
	hẹp nhầm về 0 người. Cùng lý do, một SO "Toàn viện" (không mang khoa)
	đứng sau DN cũng cho ra `None` ở đây — hai nguyên nhân khác nhau gộp
	chung MỘT giá trị `None`, chấp nhận được vì cả hai đều nên rơi về nhánh
	an toàn "báo thừa còn hơn báo thiếu", không phải nhánh "chỉ Quản lý"
	của `_portal_users_theo_khoa` (đó là ĐÚNG nghĩa CHO SỰ KIỆN "gửi đề
	xuất", KHÔNG phải nghĩa "không xác định được" của hàm này)."""
	so = _sales_order_dau_tien(dn)
	if not so:
		return None
	return frappe.db.get_value("Sales Order", so, "custom_khoa_phong")


def _sales_order_dau_tien(dn) -> str | None:
	"""SO ĐẦU TIÊN mà DN này giao cho — dùng để tính `so_dot` (BR-K16).

	Tách riêng khỏi `_sales_order_cua()`: hàm đó GỘP nhiều SO thành một chuỗi
	truy vết (và có thể CẮT chuỗi nếu quá dài), không dùng được để tra một SO
	đơn lẻ. `so_dot` chỉ có ý nghĩa trên MỘT SO — DN giao chung cho nhiều SO
	là trường hợp hiếm, lấy SO đầu tiên theo đúng thứ tự dòng DN.
	"""
	for row in dn.items:
		so = row.get("against_sales_order")
		if so:
			return so
	return None


def _so_dot_cua(dn) -> int | None:
	"""US-E3.2 (BR-K16): thứ tự DN ĐÃ GHI SỔ của cùng Sales Order.

	`dn` ở đây đã docstatus=1 trong DB (hook chạy trong on_submit, sau
	db_update()), nên chính nó cũng được đếm. Vì vậy SỐ LƯỢNG DN docstatus=1
	của SO này TẠI THỜI ĐIỂM NÀY — bao gồm chính `dn` — CHÍNH LÀ thứ tự ghi
	sổ của nó: không có DN nào khác kịp submit sau nó trước khi hook này
	chạy (Python đơn luồng trong một request), nên `len(danh_sach)` không
	cần sắp theo cột nào cả.

	SỬA (I1, E3 phần B review — bản trước SAI, không chỉ lệch ý mà ĐỤNG SỐ):
	bản trước sắp theo `creation` (thời điểm SOẠN nháp) rồi lấy `index`, với
	lý do "DN được tạo rồi submit gần như ngay sau đó nên thứ tự trùng
	nhau". Sai khi DN-A soạn TRƯỚC nhưng ghi sổ SAU DN-B (soạn sau, ghi sổ
	trước): lúc DN-B submit, danh sách docstatus=1 = [DN-B] → so_dot=1. Lúc
	DN-A submit, danh sách sắp theo creation = [DN-A, DN-B] (DN-A vẫn đứng
	đầu vì soạn trước) → index(DN-A)+1 = 1. HAI phiếu cùng SO cùng mang
	so_dot=1, không phiếu nào mang 2 — không chỉ "lệch thứ tự hiển thị" mà
	MẤT một số đợt thật. `len(danh_sach)` không có lỗ này vì nó không quan
	tâm DN nào đứng đâu trong danh sách, chỉ đếm đã có bao nhiêu DN docstatus
	=1 tính đến thời điểm hook đang chạy.

	SỬA (18/08/2026): thêm vế `is_return = 0`. Bản trước đếm cả phiếu TRẢ
	HÀNG — `make_return_doc` chép nguyên `against_sales_order` sang phiếu trả
	nên nó lọt vào `danh_sach` và chiếm mất một số đợt. Đo được trên
	`erptest.local`: SAL-ORD-2026-00132 có phiếu nhập mang `so_dot` = 1, 2, 3,
	**5** (không có đợt 4); SAL-ORD-2026-00128 có 1, **3** (không có đợt 2).
	Nặng hơn một lỗi hiển thị vì con số này GHI XUỐNG DB, trên phiếu nhập kho
	khách in và ký — và theo đúng đoạn ngay dưới đây, nó không bao giờ được
	tính lại. Quy ước lấy nguyên từ `portal_hen_giao._da_giao_sau()`.

	CŨNG LƯU Ý: so_dot là ẢNH CHỤP tại thời điểm tạo phiếu, không tính lại
	khi một DN giữa chừng bị huỷ — huỷ DN2 của ba DN không kéo so_dot=3 của
	DN3 xuống 2. Đây là hạn chế đã biết, ngoài phạm vi phần A này.

	Không có SO (DN bán lẻ không qua Sales Order) → không tính đợt, hàm trả
	`None` (khác 1 — không được trông như "đợt đầu tiên"). Field `so_dot`
	trên doctype là Int nên KHÔNG NULLABLE: `None` bị Frappe ghi xuống DB
	thành `0`, không phải giữ NULL — 0 vẫn phân biệt được với 1/2/3 nên
	không gây nhầm "đợt đầu", nhưng Phần B (report/portal_order_track) phải
	biết coi `so_dot == 0` là "không có đợt", không phải "đợt 0".
	"""
	so = _sales_order_dau_tien(dn)
	if not so:
		return None
	ten_dn = frappe.db.sql(
		"""select dni.parent
		   from `tabDelivery Note Item` dni
		   join `tabDelivery Note` dn on dn.name = dni.parent
		   where dni.against_sales_order = %s
		     and dn.docstatus = 1
		     and ifnull(dn.is_return, 0) = 0
		   group by dni.parent""",
		so,
		as_dict=False,
	)
	danh_sach = [r[0] for r in ten_dn]
	if dn.name not in danh_sach:
		# Không nên xảy ra (dn đã docstatus=1 trong DB) — nhưng nếu có, không
		# đoán mò một con số sai, để trống còn hơn.
		return None
	return len(danh_sach)


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
