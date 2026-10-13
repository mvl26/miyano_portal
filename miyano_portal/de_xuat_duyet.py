"""Lõi duyệt đề xuất → Sales Order (spec §5.6).

Tách khỏi endpoint theo đúng khuôn `dat_hang.py`: hàm này nhận tên phiếu,
KHÔNG đọc `frappe.session.user` để quyết định quyền — việc xác định người
gọi có được duyệt hay không thuộc TRÁCH NHIỆM của endpoint gọi nó
(`api/de_xuat.py::de_xuat_duyet_phieu`). Nhờ vậy kế hoạch C (uỷ quyền) chỉ
phải sửa một chỗ ở tầng endpoint.

`duyet_va_tao_don()` KHÔNG tự viết trạng thái "Đã duyệt": nó lo kiểm giá
+ tạo Sales Order rồi gọi `doc.duyet(...)` (Task 3) — nơi DUY NHẤT viết
trạng thái đã duyệt cùng cả khối truy vết. Đặt tên khác `duyet` (khớp tên
phương thức doctype) CỐ Ý — hai hàm cùng tên `duyet` ở hai tầng là mồi cho
lỗi gọi nhầm.

Spec 2026-10-09 (giá theo Price List) §4.3 — giá giữa lúc GỬI và lúc DUYỆT:
  * đơn luôn mang giá Price List TẠI THỜI ĐIỂM DUYỆT: `dat_hang.
    tao_sales_order` hỏi `bang_gia_khach` mỗi lần gọi, không cache giá cũ;
  * `PortalDeXuatMua.gui_duyet()` đóng dấu `don_gia` = giá lúc gửi ("giá
    khoa đã thấy"); `_kiem_gia_doi()` dưới đây so nó với giá hiện hành và
    trả `canh_bao_gia` — giá ĐỔI thì chỉ cảnh báo, tầng hiển thị tự quyết
    cách báo;
  * dòng "Bảng giá" MẤT giá thì CHẶN duyệt.
Module này KHÔNG còn hỏi hợp đồng khung hay hạn mức (spec §4.3: `_kiem_han_
muc` bị xoá).
"""

import frappe

from miyano_portal import bao_gia, dat_hang, nhat_ky
from miyano_portal.portal_context import cot_ten_don_hang_ton_tai


def duyet_va_tao_don(ten_phieu: str, nguoi_duyet: str,
                      tu_cach="Quản lý chính", uy_quyen=None) -> dict:
	doc = frappe.get_doc("Portal De Xuat Mua", ten_phieu)
	doc._kiem_chuyen("Đã duyệt")

	# §5.3 — CHỈ dòng có so_luong_duyet > 0 đi vào đơn. Dòng hạ về 0 VẪN
	# CÒN trên phiếu: đó là cách giữ "khoa xin gì / duyệt gì" mà không cần
	# một bản snapshot song song sớm muộn cũng lệch.
	#
	# `dong` CHỈ mang `item_code`/`qty`: `nguon_gia`/`blanket_order` đã đóng
	# băng trên dòng phiếu là bằng chứng của lúc GỬI, không phải dữ liệu để
	# dựng đơn — `dat_hang._xay_don` tự hỏi Price List cho từng dòng tại
	# thời điểm duyệt (kể cả dòng cũ còn mang "Hợp đồng").
	dong = [
		{"item_code": d.item_code, "qty": float(d.so_luong_duyet or 0)}
		for d in doc.items if float(d.so_luong_duyet or 0) > 0
	]
	if not dong and not doc.dat_ngoai:
		frappe.throw(
			"Không còn dòng nào có số lượng duyệt lớn hơn 0.",
			frappe.ValidationError,
		)

	# Spec 2026-10-09 §4.3 — chạy TRƯỚC khi tạo đơn: dòng "Bảng giá" mất giá
	# phải chặn việc duyệt khi CHƯA có đơn nào sinh ra; và nếu
	# `tao_sales_order` bên dưới ném lỗi thì cũng không có gì đáng để cảnh
	# báo cho một lần duyệt chưa từng xảy ra.
	canh_bao_gia = _kiem_gia_doi(doc)

	# Spec 2026-10-12 §5 — phiếu còn dòng chưa có giá hoặc dòng gõ tay sinh
	# một Quotation, không sinh Sales Order "Mua lẻ" nữa. Hỏi lại Price List
	# LÚC DUYỆT: phiếu chờ báo giá mà mọi dòng vừa có giá thì đi thẳng đơn.
	dat_ngoai = [d.as_dict() for d in doc.dat_ngoai]
	if bao_gia.can_bao_gia(doc.customer, dong, dat_ngoai):
		return _duyet_va_tao_bao_gia(
			doc, dong, dat_ngoai, nguoi_duyet, tu_cach, uy_quyen, canh_bao_gia
		)

	kq = dat_hang.tao_sales_order(
		doc.customer,
		# Task 4 — KHÔNG còn `mode=`. Hàm dựng đơn đã gộp làm một và quyết
		# định theo TỪNG DÒNG, nên không còn "chế độ" nào để chọn cho cả
		# đơn.
		#
		# KHÔNG truyền `contract` (spec 2026-10-09): `doc.hdnt` chỉ còn là
		# field LEGACY trên phiếu cũ, đơn không còn gắn hợp đồng khung nào.
		items=dong,
		dat_ngoai=dat_ngoai,
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
	# nhận MỘT đơn: dòng vừa duyệt không có đơn nào đứng sau, và khoa tưởng
	# đã đặt hàng. Đường tới đây có thật —
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

	gia_tri_don = {
		"custom_de_xuat": doc.name,
		"custom_ma_tra_cuu": doc.ma_de_xuat,
	}
	if cot_ten_don_hang_ton_tai():
		# Tên do nhân viên gõ ở giỏ hàng (08/09/2026). CHÉP LÊN ĐƠN, không
		# để mỗi trên phiếu: danh sách yêu cầu ở cổng là UNION hai nhánh và
		# nhánh thứ hai đọc THẲNG `Sales Order` — thiếu chỗ này thì đúng
		# nhánh đó không bao giờ hiện được tên. Đây cũng là cây cầu đã đánh
		# rơi chín trường CR-03 một lần trong phiên (`999b39d`).
		#
		# Rào theo cột THẬT: ghi vào một cột không tồn tại (site quên `bench
		# migrate`) thì MariaDB ném, và lời ném đó rơi giữa `duyet_va_tao_don`
		# — tức không bệnh viện nào duyệt được đơn nào. Một trường hiển thị
		# không được phép chặn việc mua hàng.
		gia_tri_don["custom_ten_don_hang"] = doc.get("ten_don_hang") or ""
	frappe.db.set_value("Sales Order", kq["sales_order"], gia_tri_don)

	# Task 4 — ghi SAU khi `doc.duyet()` (Task 3) đã thật sự chuyển trạng
	# thái và Sales Order đã tồn tại với tên thật (`kq["sales_order"]` được
	# cấp bên trong `dat_hang.tao_sales_order`, TRƯỚC lời gọi này) — ghi
	# trước điểm này sẽ ăn may nếu `doc.duyet()` ném lỗi phía trên. `vai=
	# VAI_HE_THONG` (brief): việc DUYỆT đã có dòng riêng của nó
	# (`SK_QUAN_LY_DUYET`, ghi bên trong `doc.duyet()`) mang tên người
	# duyệt; dòng này chỉ kể lại HỆ QUẢ "đơn đã sinh ra", không phải một
	# hành động của ai đó.
	nhat_ky.ghi(
		nhat_ky.SK_DON_TAO, customer=doc.customer, khoa_phong=doc.khoa_phong,
		de_xuat=doc.name, sales_order=kq["sales_order"], vai=nhat_ky.VAI_HE_THONG,
	)
	return {
		"sales_order": kq["sales_order"], "bao_gia": None, "de_xuat": doc.name,
		"canh_bao_gia": canh_bao_gia,
	}


def _duyet_va_tao_bao_gia(doc, dong, dat_ngoai, nguoi_duyet, tu_cach, uy_quyen,
                          canh_bao_gia) -> dict:
	"""Nhánh Quotation của `duyet_va_tao_don`. Cùng thứ tự với nhánh đơn: tạo
	chứng từ, gắn vào phiếu, rồi mới `duyet()`."""
	kq = bao_gia.tao_bao_gia(
		doc.customer, items=dong, dat_ngoai=dat_ngoai,
		delivery_date=doc.ngay_can, address=doc.dia_chi_giao, note=doc.ghi_chu,
		request_id=doc.request_id or doc.name, khoa_phong=doc.khoa_phong,
	)
	if kq.get("da_ton_tai"):
		frappe.throw(
			f'Yêu cầu báo giá {kq["bao_gia"]} đã được tạo trước đó cho mã yêu cầu '
			f'"{doc.request_id or doc.name}" — phiếu này có thể đã được duyệt rồi. '
			"Tải lại trang để xem trạng thái mới nhất; nếu phiếu vẫn đang chờ "
			"duyệt thì liên hệ Miyano, KHÔNG bấm duyệt lại.",
			frappe.ValidationError,
		)
	doc.bao_gia = kq["bao_gia"]
	doc.duyet(nguoi_duyet, tu_cach=tu_cach, uy_quyen=uy_quyen)
	frappe.db.set_value("Quotation", kq["bao_gia"], {
		"custom_de_xuat": doc.name,
		"custom_ten_don_hang": doc.get("ten_don_hang") or "",
	})
	nhat_ky.ghi(
		nhat_ky.SK_BAO_GIA_TAO, customer=doc.customer, khoa_phong=doc.khoa_phong,
		de_xuat=doc.name, vai=nhat_ky.VAI_HE_THONG,
	)
	bao_gia.bao_nhan_vien(
		frappe.get_doc("Quotation", kq["bao_gia"]), "Portal - Yêu cầu báo giá mới",
		f"Khách hàng <b>{doc.customer}</b> vừa gửi yêu cầu báo giá "
		f"<b>{kq['bao_gia']}</b> ({doc.ma_de_xuat or doc.name}).",
	)
	return {
		"sales_order": None, "bao_gia": kq["bao_gia"], "de_xuat": doc.name,
		"canh_bao_gia": canh_bao_gia,
	}


def _kiem_gia_doi(doc) -> list[dict]:
	"""Spec 2026-10-09 §4.3. So giá đã đóng dấu lúc gửi duyệt với giá Price
	List hiện hành. Dòng "Bảng giá" MẤT giá → chặn duyệt (không tự chuyển
	sang vòng báo giá: phiếu đã được tách theo loại lúc gửi). Giá ĐỔI → cảnh
	báo, đơn mang giá mới.

	Lối thoát của lời chặn (Ruling R5): quản lý từ chối, khoa gửi lại —
	`PortalDeXuatMua._dong_dau_gia()` chuyển dòng mất giá sang "Chờ báo giá"
	ngay ở lần gửi đó, nên phiếu gửi lại duyệt được thành đơn báo giá. Câu
	chữ trong lời chặn dưới đây phải khớp đúng điều đó.

	Chỉ xét dòng đóng dấu "Bảng giá" SẼ VÀO ĐƠN (`so_luong_duyet` > 0):
	  * dòng "Chờ báo giá" không có giá đóng dấu nào để so — nếu nó vừa có
	    giá thì đơn cứ nhận giá đó (§4.3), không có gì để báo;
	  * dòng CŨ còn mang "Hợp đồng" (đóng băng trước spec này) cũng bỏ qua:
	    `don_gia` của nó là giá hợp đồng, không phải giá Price List, và nó
	    không được phép chặn việc duyệt một phiếu cũ đang chờ;
	  * dòng quản lý đã hạ về 0 không vào đơn — đó cũng là lối thoát của
	    quản lý khi một dòng mất giá mà các dòng còn lại vẫn cần duyệt.

	Mỗi mục trả về: `item_code`, `gia_cu`, `gia_moi`, `ly_do` (luôn là
	`"gia_doi"` — các loại "đổi hợp đồng" đã bị gỡ cùng phần hợp đồng).
	"""
	from miyano_portal import bang_gia_khach
	from miyano_portal.miyano_portal.doctype.portal_de_xuat_mua.portal_de_xuat_mua import (
		NGUON_GIA_BANG_GIA,
	)

	gia = bang_gia_khach.gia_bang_gia_nhieu(
		doc.customer, [r.item_code for r in doc.items]
	)
	mat_gia, canh_bao = [], []
	for row in doc.items:
		if row.nguon_gia != NGUON_GIA_BANG_GIA or not float(row.so_luong_duyet or 0):
			continue
		gia_moi = gia.get(row.item_code)
		if gia_moi is None:
			mat_gia.append(row.item_code)
			continue
		gia_cu = float(row.don_gia or 0)
		if gia_cu and gia_cu != float(gia_moi):
			canh_bao.append({
				"item_code": row.item_code, "gia_cu": gia_cu,
				"gia_moi": float(gia_moi), "ly_do": "gia_doi",
			})
	if mat_gia:
		# Mỗi mặt hàng nêu MỘT lần, giữ thứ tự dòng (dữ liệu cũ có thể có
		# hai dòng cùng mã).
		mat_gia = list(dict.fromkeys(mat_gia))
		frappe.throw(
			"Không duyệt được: " + ", ".join(mat_gia) + " không còn giá trong "
			"bảng giá. Từ chối phiếu để khoa gửi lại — các mặt hàng này sẽ "
			"chuyển sang chờ báo giá.",
			frappe.ValidationError,
		)
	return canh_bao
