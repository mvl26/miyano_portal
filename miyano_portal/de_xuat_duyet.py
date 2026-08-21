"""Lõi duyệt đề xuất → Sales Order (spec §5.6).

Tách khỏi endpoint theo đúng khuôn `dat_hang.py`: hàm này nhận tên phiếu,
KHÔNG đọc `frappe.session.user` để quyết định quyền — việc xác định người
gọi có được duyệt hay không thuộc TRÁCH NHIỆM của endpoint gọi nó
(`api/de_xuat.py::de_xuat_duyet_phieu`). Nhờ vậy kế hoạch C (uỷ quyền) chỉ
phải sửa một chỗ ở tầng endpoint.

`duyet_va_tao_don()` KHÔNG tự viết trạng thái "Đã duyệt": nó lo hạn mức +
giá + tạo Sales Order rồi gọi `doc.duyet(...)` (Task 3) — nơi DUY NHẤT viết
trạng thái đã duyệt cùng cả khối truy vết. Đặt tên khác `duyet` (khớp tên
phương thức doctype) CỐ Ý — hai hàm cùng tên `duyet` ở hai tầng là mồi cho
lỗi gọi nhầm.

BẪY #2 §5.6 ("giá tính lại tại thời điểm duyệt, khác giá khoa đã thấy thì
báo cho quản lý TRƯỚC KHI họ bấm") — vòng sửa (19/08/2026, sau report Task
6 đầu tiên): VẾ MỘT (tính lại tại thời điểm duyệt) có SẴN nhờ kiến trúc:
`dat_hang.tao_sales_order` luôn tra `Item Price` MỚI NHẤT tại thời điểm gọi
(`_gia_hien_hanh`), không cache lại giá cũ. VẾ HAI (báo TRƯỚC KHI bấm) giờ
có DỮ LIỆU: `PortalDeXuatMua.gui_duyet()` đóng dấu `don_gia` = giá hiện
hành NGAY lúc gửi duyệt (cùng lúc `so_luong_de_xuat` bị khoá) — đó là "giá
khoa đã thấy". `_kiem_gia_doi()` dưới đây so `don_gia` với giá tính lại
NGAY LÚC DUYỆT và trả về `canh_bao_gia` trong kết quả — KHÔNG chặn việc
duyệt, chỉ mang dữ liệu lên cho tầng hiển thị (kế hoạch B, ngoài phạm vi
module này) tự quyết cách báo và có bắt xác nhận hay không.
"""

import frappe

from miyano_portal import dat_hang
from miyano_portal.miyano_portal.doctype.portal_de_xuat_mua.portal_de_xuat_mua import (
	nguon_gia_theo_ma_cho_khach,
)
from miyano_portal.portal_context import han_muc_con, ten_khoa_da_tieu


def duyet_va_tao_don(ten_phieu: str, nguoi_duyet: str,
                      tu_cach="Quản lý chính", uy_quyen=None) -> dict:
	doc = frappe.get_doc("Portal De Xuat Mua", ten_phieu)
	doc._kiem_chuyen("Đã duyệt")

	# §5.3 — CHỈ dòng có so_luong_duyet > 0 đi vào đơn. Dòng hạ về 0 VẪN
	# CÒN trên phiếu: đó là cách giữ "khoa xin gì / duyệt gì" mà không cần
	# một bản snapshot song song sớm muộn cũng lệch.
	#
	# Ruling P28 (vòng sửa 1) — `dong` CHỈ mang `item_code`/`qty`. Bản đầu
	# của Task 5 kèm theo `nguon_gia`/`blanket_order` đã đóng băng để
	# `_kiem_han_muc` dùng; nhưng hợp đồng dùng để QUYẾT ĐỊNH phải là bản
	# suy lại tại thời điểm duyệt, và cả hai tầng giờ tự hỏi cùng một hàm
	# (`nguon_gia_theo_ma_cho_khach`). Không truyền hợp đồng xuống nữa =
	# không có đường nào để hai tầng lệch nhau.
	dong = [
		{"item_code": d.item_code, "qty": float(d.so_luong_duyet or 0)}
		for d in doc.items if float(d.so_luong_duyet or 0) > 0
	]
	if not dong and not doc.dat_ngoai:
		frappe.throw(
			"Không còn dòng nào có số lượng duyệt lớn hơn 0.",
			frappe.ValidationError,
		)

	# Task 5 — kiểm hạn mức cho MỌI phiếu, lọc theo DÒNG bên trong
	# `_kiem_han_muc`. Gate cũ (`if not doc.co_dong_cho_bao_gia() and
	# doc.hdnt:`) sai theo HAI hướng cùng lúc:
	#   * phiếu TRỘN thoát hoàn toàn phép kiểm, dù dòng hợp đồng của nó
	#     tiêu đúng hạn mức chung của bệnh viện;
	#   * `doc.hdnt` LUÔN rỗng với mọi phiếu tạo qua UI thật
	#     (`de_xuat_tao_nhap()` tạo phiếu Nháp TRƯỚC khi người dùng chọn
	#     mặt hàng, `de_xuat_luu_nhap()` không có tham số `hdnt`), nên
	#     ngay cả phiếu THUẦN hợp đồng cũng chưa từng được kiểm ở đây.
	# Chỗ đúng để lọc là bên trong vòng lặp, theo hợp đồng của từng dòng
	# — không phải một cái cổng ở ngoài đóng/mở cho cả phiếu.
	_kiem_han_muc(doc, dong)

	# §5.6 bẫy #2 — thu thập TRƯỚC khi tạo đơn: nếu `tao_sales_order` bên
	# dưới ném lỗi (hạn mức/giá/kho...) thì không có đơn nào được duyệt, và
	# không có gì đáng để cảnh báo cho một lần duyệt chưa từng xảy ra.
	canh_bao_gia = _kiem_gia_doi(doc)

	kq = dat_hang.tao_sales_order(
		doc.customer,
		# Task 4 — KHÔNG còn `mode=`. Hàm dựng đơn đã gộp làm một và quyết
		# định theo TỪNG DÒNG, nên không còn "chế độ" nào để chọn cho cả
		# đơn. Cầu tạm Ruling P2 (`mode="ban_le" if doc.co_dong_cho_bao_
		# gia() else "hdnt"`) chính là chỗ phiếu THUẦN hợp đồng lập từ giao
		# diện thật chết vì `contract=None`, và phiếu TRỘN chết vì BR-R7.
		#
		# `contract=doc.hdnt` GIỮ LẠI: `hdnt` là field LEGACY, rỗng với mọi
		# phiếu tạo qua UI thật nhưng CÒN giá trị với phiếu cũ và với phiếu
		# tự duyệt của đường giỏ hàng quản lý (`_dam_bao_phieu_tu_duyet`
		# vẫn ghi nó). `tao_sales_order` chỉ dùng nó làm đường lui cho
		# `custom_hdnt` khi không suy được từ dòng, và vẫn kiểm nó thuộc
		# đúng khách hàng.
		contract=doc.hdnt, items=dong,
		dat_ngoai=[d.as_dict() for d in doc.dat_ngoai],
		delivery_date=doc.ngay_can, address=doc.dia_chi_giao,
		note=doc.ghi_chu, request_id=doc.request_id or doc.name,
		khoa_phong=doc.khoa_phong,
		# Task 9 — đơn MANG THẲNG mã phiếu. DÙNG LẠI `doc.ma_de_xuat` đã
		# cấp lúc `gui_duyet()`, KHÔNG gọi `sinh_ma()` lần nữa (nó cấp số
		# mới qua `getseries`, đơn sẽ mang mã không khớp phiếu nào).
		# `None` (phiếu chưa có mã, VD khách chưa có Mã ngắn) → đơn rơi về
		# `SAL-ORD-...` như cũ.
		ma=doc.ma_de_xuat,
	)

	# I1 (review tổng 19/08) — `tao_sales_order` trả ĐƠN CŨ kèm cờ
	# `da_ton_tai=True` khi `custom_request_id` đã tồn tại (BR-O12, chống
	# tạo đơn trùng — CỐ Ý ở tầng đó, nơi nó đúng: người dùng bấm lại nút
	# Xác nhận). Ở TẦNG NÀY thì không: nếu bỏ qua cờ đó, phiếu này gắn lấy
	# một đơn nó KHÔNG sinh ra rồi `doc.duyet()` như thường. Hai phiếu cùng
	# nhận MỘT đơn: dòng vừa duyệt không có đơn nào đứng sau, hạn mức HĐNT
	# không bị trừ, và khoa tưởng đã đặt hàng. Đường tới đây có thật —
	# `request_id` mặc định là `doc.name`, và Frappe LÙI bộ đếm đặt tên khi
	# bản ghi mới nhất của chuỗi bị xoá (`revert_series_if_last`), nên hai
	# phiếu khác nhau CÓ THỂ mang cùng một tên/`request_id`. THẤT BẠI ỒN ÀO
	# là cách hỏng duy nhất chấp nhận được ở đây.
	if kq.get("da_ton_tai"):
		frappe.throw(
			f'Đơn hàng {kq["sales_order"]} đã được tạo trước đó cho mã yêu '
			f'cầu "{doc.request_id or doc.name}" — phiếu này có thể đã được '
			"duyệt rồi, hoặc mã yêu cầu bị trùng. Tải lại trang để xem "
			"trạng thái mới nhất; nếu phiếu vẫn đang chờ duyệt thì liên hệ "
			"Miyano, KHÔNG bấm duyệt lại.",
			frappe.ValidationError,
		)

	# Ruling preflight C2 — KHÔNG tự viết trạng thái ở đây. `doc.duyet()`
	# (Task 3) là nơi duy nhất viết trạng thái đã duyệt + khối truy vết;
	# hai chỗ cùng viết một sự thật thì sớm muộn cũng lệch.
	doc.sales_order = kq["sales_order"]
	doc.duyet(nguoi_duyet, tu_cach=tu_cach, uy_quyen=uy_quyen)

	frappe.db.set_value("Sales Order", kq["sales_order"], {
		"custom_de_xuat": doc.name,
		"custom_ma_tra_cuu": doc.ma_de_xuat,
	})
	return {
		"sales_order": kq["sales_order"], "de_xuat": doc.name,
		"canh_bao_gia": canh_bao_gia,
	}


def _kiem_gia_doi(doc) -> list[dict]:
	"""§5.6 bẫy #2 — so giá tính lại NGAY LÚC DUYỆT với `don_gia` đã đóng
	dấu lúc GỬI DUYỆT (`PortalDeXuatMua.gui_duyet`/`_dong_dau_gia`, "giá
	khoa đã thấy"). KHÔNG chặn duyệt — chỉ trả DANH SÁCH các dòng lệch giá
	để tầng hiển thị (kế hoạch B, ngoài phạm vi module này) tự quyết cách
	báo và có bắt quản lý xác nhận hay không.

	Dòng nào `don_gia` RỖNG thì BỎ QUA — không có gì để so (mua lẻ không
	bao giờ có `don_gia`, §4.5; hoặc mặt hàng chưa có giá lúc gửi duyệt).
	Đi qua TOÀN BỘ `doc.items`, không chỉ những dòng vào đơn (`dong`
	tham số của `_kiem_han_muc`) — một dòng bị quản lý hạ về 0 lúc điều
	chỉnh vẫn đáng để họ biết giá đã đổi, dù nó không còn vào đơn lần này.

	Task 2 (gộp luồng đặt hàng) — HÀNH VI ĐỔI so với trước: gate CHỈ còn
	`not doc.hdnt`, KHÔNG còn đòi "phiếu THUẦN hợp đồng" (`co_dong_cho_
	bao_gia()`) như gate hạn mức bên trên. Đây là NỬA THỨ HAI của cùng
	tính năng §5.6 bẫy #2 mà `PortalDeXuatMua._dong_dau_gia()` vừa sửa
	thành đóng dấu THEO TỪNG DÒNG (chỉ dòng Hợp đồng, kể cả trong phiếu
	trộn) — nếu gate ở đây vẫn chặn cả phiếu trộn, `don_gia` đã đóng dấu
	đúng cho dòng Hợp đồng của một phiếu trộn sẽ không bao giờ được so
	sánh lại, và cảnh báo giá đổi coi như CHẾT LẶNG LẼ cho đúng loại phiếu
	task này sinh ra. An toàn vì vòng lặp dưới đã tự lọc `if not row.
	don_gia: continue` — dòng "Chờ báo giá" (kể cả trong phiếu trộn) không
	bao giờ có `don_gia` (xem `_dong_dau_gia()`), nên tự động không tham
	gia so sánh mà không cần gate ở đây gác thêm lần nữa.

	Ruling P14 — bỏ hẳn gate `not doc.hdnt` (vòng sửa sau review màn lập
	phiếu): `self.hdnt` ở đầu phiếu giờ chỉ còn LEGACY, không còn quyết
	định phiếu có dòng Hợp đồng hay không (suy nguồn giá giờ customer-wide,
	xem `PortalDeXuatMua._nguon_gia_theo_ma()`) — giữ gate đó sẽ chặn NHẦM
	cảnh báo giá cho mọi phiếu tạo qua `de_xuat_tao_nhap()` (luôn `hdnt =
	None`, xem docstring `_nguon_gia_theo_ma()`), dù dòng của nó có thể
	vẫn có `don_gia` đã đóng dấu đàng hoàng. Gate `price_list` một mình đã
	đủ — không có bảng giá thì không tính được `gia_moi` cho bất kỳ dòng
	nào, dù dòng đó có `don_gia` hay không.

	RULING P28 (vòng sửa 1, review độc lập) — hàm này giờ báo CẢ việc ĐỔI
	HỢP ĐỒNG, không chỉ đổi giá. Hợp đồng dùng để quyết định là bản SUY
	LẠI lúc duyệt (xem `_kiem_han_muc`), còn `row.blanket_order` đóng băng
	là BẰNG CHỨNG khoa đã nhìn thấy hợp đồng nào lúc gửi. Hai bản lệch
	nhau là một sự thật quản lý cần biết TRƯỚC khi bấm duyệt — hợp đồng
	đóng băng vừa hết hạn, hoặc một hợp đồng mới ký đã chen lên trước theo
	luật "hết hạn sớm nhất thắng". Nuốt lặng lẽ tín hiệu đó thì việc đơn
	được tính theo một hợp đồng khác hợp đồng khoa đã xem chỉ lộ ra khi ai
	đó đối chiếu sổ.

	Vì lý do đó gate `if not price_list: return []` cũng bỏ: không có bảng
	giá thì không so được GIÁ, nhưng vẫn so được HỢP ĐỒNG.

	Mỗi mục trả về mang thêm `hop_dong_cu`/`hop_dong_moi` (có thể `None`)
	và `ly_do` để tầng hiển thị phân biệt được ba tình huống. Ba khoá cũ
	(`item_code`/`gia_cu`/`gia_moi`) GIỮ NGUYÊN tên và kiểu — chúng là
	hợp đồng dữ liệu với người gọi.
	"""
	price_list = frappe.db.get_value("Customer", doc.customer, "default_price_list")
	thang_cuoc = nguon_gia_theo_ma_cho_khach(doc.customer)
	canh_bao = []
	for row in doc.items:
		bo_moi = thang_cuoc.get(row.item_code)
		bo_cu = row.blanket_order or None
		hop_dong_doi = bo_moi != bo_cu
		# Chỉ dòng thuộc hợp đồng mới có giá để so — dòng "Chờ báo giá"
		# không bao giờ có `don_gia` (xem `_dong_dau_gia()`).
		gia_moi = (
			dat_hang._gia_hien_hanh(row.item_code, price_list)
			if price_list and bo_moi else None
		)
		gia_cu = float(row.don_gia) if row.don_gia else None
		gia_doi = (
			gia_cu is not None and gia_moi is not None
			and float(gia_moi) != gia_cu
		)
		if not hop_dong_doi and not gia_doi:
			continue
		canh_bao.append({
			"item_code": row.item_code,
			"gia_cu": gia_cu,
			"gia_moi": float(gia_moi) if gia_moi is not None else None,
			"hop_dong_cu": bo_cu,
			"hop_dong_moi": bo_moi,
			"ly_do": (
				"gia_va_hop_dong_doi" if (gia_doi and hop_dong_doi)
				else "hop_dong_doi" if hop_dong_doi else "gia_doi"
			),
		})
	return canh_bao


def _kiem_han_muc(doc, dong):
	"""§5.6 — hạn mức HĐNT là tài nguyên CHUNG giữa các khoa.

	Trừ ở lúc DUYỆT, không phải lúc đề xuất. Hết hạn mức thì THẤT BẠI kèm
	tên khoa đã tiêu mất — KHÔNG im lặng cắt số lượng xuống, vì người duyệt
	sẽ không biết mình vừa duyệt một số khác số họ nhìn thấy.

	Task 5 (gộp luồng đặt hàng, 21/08/2026) — kiểm THEO TỪNG DÒNG, trên
	ĐÚNG hợp đồng của riêng dòng đó, thay vì giả định cả phiếu nằm trên
	một `doc.hdnt` duy nhất. Dòng KHÔNG thuộc hợp đồng nào thì bỏ qua:
	`han_muc_con()` trả `(0.0, 0.0)` — "hạn mức 0" — cho MỌI mã hàng không
	có dòng trong hợp đồng được hỏi, nên đưa nó vào phép kiểm là chặn một
	dòng chưa từng bị hạn mức ràng buộc, kèm một thông điệp vô nghĩa với
	khoa phòng.

	RULING P28 (vòng sửa 1, review độc lập) — MỘT NGUỒN DUY NHẤT, và đó là
	bản SUY LẠI tại thời điểm duyệt: hàm này gọi ĐÚNG
	`nguon_gia_theo_ma_cho_khach()` mà `dat_hang._xay_don` gọi. Bản đầu
	của Task 5 đọc `row.blanket_order` ĐÃ ĐÓNG BĂNG lúc gửi duyệt, còn
	`_xay_don` suy lại — hai nguồn cho một sự thật, đúng loại lỗi cả kế
	hoạch này sinh ra để dẹp. Hai trạng thái hỏng, cả hai đều tới được:

	  * hợp đồng đóng băng HẾT HẠN trong lúc chờ duyệt, trong khi một hợp
	    đồng khác còn hiệu lực phủ đúng mặt hàng đó → hàm này viện dẫn hạn
	    mức của một hợp đồng ĐÃ CHẾT để chặn thẳng việc duyệt, còn
	    `_xay_don` thì lẽ ra định giá dòng ấy theo hợp đồng còn sống. Quản
	    lý bị từ chối oan, thông điệp không cho họ đường nào để gỡ;
	  * ngược lại, hàm này thấy đủ nên cho qua rồi `_xay_don` mới chặn —
	    và trước vòng sửa nhánh đó KHÔNG nêu tên khoa, hỏng đúng vế §5.6
	    trong chính ca nhiều hợp đồng mà Task 5 được viết ra để phục vụ.

	Còn một ca thứ ba cùng gốc: phiếu CŨ được patch `them_nguon_gia_dong_
	phieu.py` backfill mang `nguon_gia = "Hợp đồng"` nhưng `blanket_order
	= NULL` (patch chép từ `hdnt`, vốn NULL với mọi phiếu lập từ giao diện
	thật), và `_suy_nguon_gia` đóng băng dòng sau Nháp nên chúng KHÔNG tự
	lành. Đọc bản suy lại thì chúng được canh đúng, không cần dữ liệu quá
	khứ phải sạch trước.

	`row.blanket_order` đóng băng GIỮ NGUYÊN vai trò BẰNG CHỨNG — nó ghi
	lại khoa đã nhìn thấy hợp đồng nào lúc gửi; không xoá, không đổi ý
	nghĩa. Khi bản suy lại KHÁC bản đóng băng, tín hiệu đó đi vào
	`_kiem_gia_doi()` (cảnh báo trước khi quản lý bấm duyệt), không bị nuốt.

	Tên khoa đã tiêu tra theo hợp đồng CỦA DÒNG ĐÓ, qua `portal_context.
	ten_khoa_da_tieu()` — dùng CHUNG với nhánh của `dat_hang`.
	"""
	thang_cuoc = nguon_gia_theo_ma_cho_khach(doc.customer)
	for d in dong:
		bo = thang_cuoc.get(d["item_code"])
		if not bo:
			continue
		han, _da_dung = han_muc_con(bo, d["item_code"])
		if han is None:
			# BR-O15 — hạn mức khai 0 = KHÔNG GIỚI HẠN.
			continue
		if d["qty"] > han:
			frappe.throw(
				f'Hạn mức hợp đồng cho "{d["item_code"]}" chỉ còn {han}, '
				f"phiếu này duyệt {d['qty']}. "
				f"Đã dùng bởi: {ten_khoa_da_tieu(bo)}.",
				frappe.ValidationError,
			)
