"""HSD tối thiểu theo yêu cầu khách hàng: logic thuần (spec 2026-10-19).

Không đụng DB ngoài `ap_dung` (đọc cờ `has_batch_no` của Item). Các hàm còn lại
chỉ tính ngày để SO (cảnh báo) và Delivery Note (chặn) dùng chung một cách tính.
"""

import math

import frappe
from dateutil.relativedelta import relativedelta
from frappe import _
from frappe.utils import add_months, cint, getdate

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
