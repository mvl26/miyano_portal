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
from miyano_portal.portal_context import han_muc_con


def duyet_va_tao_don(ten_phieu: str, nguoi_duyet: str,
                      tu_cach="Quản lý chính", uy_quyen=None) -> dict:
	doc = frappe.get_doc("Portal De Xuat Mua", ten_phieu)
	doc._kiem_chuyen("Đã duyệt")

	# §5.3 — CHỈ dòng có so_luong_duyet > 0 đi vào đơn. Dòng hạ về 0 VẪN
	# CÒN trên phiếu: đó là cách giữ "khoa xin gì / duyệt gì" mà không cần
	# một bản snapshot song song sớm muộn cũng lệch.
	dong = [
		{"item_code": d.item_code, "qty": float(d.so_luong_duyet or 0)}
		for d in doc.items if float(d.so_luong_duyet or 0) > 0
	]
	if not dong and not doc.dat_ngoai:
		frappe.throw(
			"Không còn dòng nào có số lượng duyệt lớn hơn 0.",
			frappe.ValidationError,
		)

	if doc.loai_don == "HĐNT" and doc.hdnt:
		_kiem_han_muc(doc, dong)

	# §5.6 bẫy #2 — thu thập TRƯỚC khi tạo đơn: nếu `tao_sales_order` bên
	# dưới ném lỗi (hạn mức/giá/kho...) thì không có đơn nào được duyệt, và
	# không có gì đáng để cảnh báo cho một lần duyệt chưa từng xảy ra.
	canh_bao_gia = _kiem_gia_doi(doc)

	kq = dat_hang.tao_sales_order(
		doc.customer,
		mode="hdnt" if doc.loai_don == "HĐNT" else "ban_le",
		contract=doc.hdnt, items=dong,
		dat_ngoai=[d.as_dict() for d in doc.dat_ngoai],
		delivery_date=doc.ngay_can, address=doc.dia_chi_giao,
		note=doc.ghi_chu, request_id=doc.request_id or doc.name,
		khoa_phong=doc.khoa_phong,
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
	"""
	if doc.loai_don != "HĐNT" or not doc.hdnt:
		return []
	price_list = frappe.db.get_value("Customer", doc.customer, "default_price_list")
	if not price_list:
		return []
	canh_bao = []
	for row in doc.items:
		if not row.don_gia:
			continue
		gia_moi = dat_hang._gia_hien_hanh(row.item_code, price_list)
		if gia_moi and float(gia_moi) != float(row.don_gia):
			canh_bao.append({
				"item_code": row.item_code,
				"gia_cu": float(row.don_gia),
				"gia_moi": float(gia_moi),
			})
	return canh_bao


def _kiem_han_muc(doc, dong):
	"""§5.6 — hạn mức HĐNT là tài nguyên CHUNG giữa các khoa.

	Trừ ở lúc DUYỆT, không phải lúc đề xuất. Hết hạn mức thì THẤT BẠI kèm
	tên khoa đã tiêu mất — KHÔNG im lặng cắt số lượng xuống, vì người duyệt
	sẽ không biết mình vừa duyệt một số khác số họ nhìn thấy.
	"""
	for d in dong:
		han, _da_dung = han_muc_con(doc.hdnt, d["item_code"])
		if han is None:
			# BR-O15 — hạn mức khai 0 = KHÔNG GIỚI HẠN.
			continue
		if d["qty"] > han:
			khoa_da_tieu = frappe.get_all(
				"Sales Order",
				filters={"custom_hdnt": doc.hdnt, "docstatus": ["<", 2]},
				fields=["distinct custom_khoa_phong as khoa"],
			)
			ten_khoa = ", ".join(
				frappe.db.get_value("Customer Department", r.khoa, "ten_khoa_phong")
				or "Toàn viện" for r in khoa_da_tieu if r.khoa
			) or "khoa khác"
			frappe.throw(
				f'Hạn mức hợp đồng cho "{d["item_code"]}" chỉ còn {han}, '
				f"phiếu này duyệt {d['qty']}. Đã dùng bởi: {ten_khoa}.",
				frappe.ValidationError,
			)
