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
báo cho quản lý TRƯỚC KHI họ bấm") — VẾ MỘT (tính lại tại thời điểm duyệt)
đã có SẴN nhờ kiến trúc: `dat_hang.tao_sales_order` luôn tra `Item Price`
MỚI NHẤT tại thời điểm gọi (`_gia_hien_hanh`), không có snapshot giá nào bị
cache lại rồi tái dùng lặng lẽ ở đây. VẾ HAI (báo TRƯỚC KHI bấm, tức một màn
xem trước cho quản lý) KHÔNG cài ở task này: cột lưu "giá khoa đã thấy"
(`Portal De Xuat Mua Item.don_gia`) tồn tại trên doctype nhưng KHÔNG có
đường ghi nào trong app điền vào nó (đã kiểm bằng grep toàn app) — không có
snapshot nào để so sánh, nên chưa có gì để cảnh báo. Việc này cần một task
riêng ghi `don_gia` tại thời điểm khoa xem giá trước, rồi mới có một số để
so với giá tính lại lúc duyệt.
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
	return {"sales_order": kq["sales_order"], "de_xuat": doc.name}


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
