"""Dựng đơn "Mua lẻ" đang dở cho các bộ test của luồng cũ.

Từ spec 2026-10-12 §5, hai đường tạo đơn của cổng (`de_xuat_duyet.
duyet_va_tao_don`, `portal.portal_order_place`) sinh Quotation cho giỏ còn
hàng chưa có giá hoặc dòng gõ tay; không đường nào của cổng còn sinh Sales
Order "Mua lẻ". Đơn "Mua lẻ" đã có vẫn chạy nốt bằng mã luồng cũ (§9), nên
các bộ test canh luồng đó (điền giá, khớp mã dòng gõ tay, khách đồng ý, sửa
số lượng, xin sửa, in phiếu) vẫn cần một đơn như vậy đứng sau một phiếu.

Hai hàm dưới gọi `dat_hang.tao_sales_order` TRỰC TIẾP rồi nối đơn với phiếu
đúng như hai đường cũ từng làm. Chỉ dùng để dựng dữ liệu; không phải thứ
được kiểm.
"""

import frappe

from miyano_portal import dat_hang, nhat_ky
from miyano_portal.api import portal
from miyano_portal.portal_context import khoa_phong_cho_don


def duyet_thanh_don(ten_phieu: str, nguoi_duyet: str) -> dict:
	"""Phiếu "Chờ duyệt" → "Đã duyệt" với một Sales Order đứng sau, như nhánh
	đơn của `duyet_va_tao_don`, không hỏi phiếu có phải đi báo giá hay không."""
	doc = frappe.get_doc("Portal De Xuat Mua", ten_phieu)
	dong = [
		{"item_code": d.item_code, "qty": float(d.so_luong_duyet or 0)}
		for d in doc.items if float(d.so_luong_duyet or 0) > 0
	]
	kq = dat_hang.tao_sales_order(
		doc.customer, items=dong, dat_ngoai=[d.as_dict() for d in doc.dat_ngoai],
		delivery_date=doc.ngay_can, address=doc.dia_chi_giao, note=doc.ghi_chu,
		request_id=doc.request_id or doc.name, khoa_phong=doc.khoa_phong,
		ma=doc.ma_de_xuat,
	)
	if kq.get("da_ton_tai"):
		raise AssertionError(
			f"Fixture: đơn {kq['sales_order']} đã có sẵn cho phiếu {doc.name}."
		)
	doc.sales_order = kq["sales_order"]
	doc.duyet(nguoi_duyet)
	frappe.db.set_value("Sales Order", kq["sales_order"], {
		"custom_de_xuat": doc.name,
		"custom_ma_tra_cuu": doc.ma_de_xuat,
		"custom_ten_don_hang": doc.get("ten_don_hang") or "",
	})
	nhat_ky.ghi(
		nhat_ky.SK_DON_TAO, customer=doc.customer, khoa_phong=doc.khoa_phong,
		de_xuat=doc.name, sales_order=kq["sales_order"], vai=nhat_ky.VAI_HE_THONG,
	)
	return {"sales_order": kq["sales_order"], "bao_gia": None, "de_xuat": doc.name}


def dat_truc_tiep(
	customer: str, *, items=None, dat_ngoai=None, request_id=None, khoa_phong=None,
	mode="ban_le", delivery_date=None, note=None, address=None, po=None,
	ten_don_hang=None,
) -> dict:
	"""Một Sales Order cùng phiếu tự duyệt đứng sau, như `portal_order_place`
	từng làm cho giỏ một loại. Gọi dưới phiên của quản lý đặt hàng: người đó
	thành `nguoi_duyet` của phiếu."""
	khoa = khoa_phong_cho_don(khoa_phong)
	kq = dat_hang.tao_sales_order(
		customer, mode=mode, items=items, dat_ngoai=dat_ngoai, po=po,
		delivery_date=delivery_date, note=note, address=address,
		request_id=request_id, khoa_phong=khoa,
	)
	kq["bao_gia"] = None
	kq["de_xuat"] = portal._dam_bao_phieu_tu_duyet(
		customer=customer, khoa_phong=khoa, mode=mode, contract=None,
		dat_ngoai=dat_ngoai, delivery_date=delivery_date, address=address,
		note=note, request_id=request_id, ten_don_hang=ten_don_hang,
		sales_order=kq["sales_order"], da_ton_tai=bool(kq.get("da_ton_tai")),
	)
	kq["loai_don"] = frappe.db.get_value(
		"Sales Order", kq["sales_order"], "custom_loai_don"
	)
	return kq
