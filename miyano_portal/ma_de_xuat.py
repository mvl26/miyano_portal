"""Sinh mã đề xuất `DXA-HUYETHOC-260819-01` (spec §6.1).

Bộ đếm theo bộ ba (bệnh viện, khoa, ngày) — KHÔNG phải một naming_series của
Frappe, vốn chỉ đếm theo một tiền tố cố định. Dùng `getseries()` với tiền tố
động: nó ghi vào `tabSeries` bằng `INSERT ... ON DUPLICATE KEY UPDATE current
= current + 1`, nguyên tử ở tầng MariaDB.

KHÔNG được thay bằng `SELECT MAX(ma_de_xuat) + 1`: hai phiên cùng đọc MAX sẽ
ra cùng một số, và lỗi đó chỉ lộ khi hai khoa bấm gửi trong cùng một giây —
tức là không bao giờ lộ trên máy dev.
"""

import frappe
from frappe.model.naming import getseries
from frappe.utils import getdate, nowdate

MA_TOAN_VIEN = "CHUNG"


def sinh_ma(customer: str, khoa_phong: str | None, ngay=None) -> str:
	ma_ngan = frappe.db.get_value("Customer", customer, "custom_ma_ngan")
	if not ma_ngan:
		frappe.throw(
			f'Đơn vị "{customer}" chưa có Mã ngắn. Liên hệ Miyano để đặt Mã '
			"ngắn trước khi dùng chức năng đề xuất mua.",
			frappe.ValidationError,
		)
	if khoa_phong:
		ma_khoa = frappe.db.get_value("Customer Department", khoa_phong, "ma_khoa")
		if not ma_khoa:
			frappe.throw(
				f'Khoa phòng "{khoa_phong}" chưa có Mã khoa.', frappe.ValidationError
			)
	else:
		ma_khoa = MA_TOAN_VIEN
	yymmdd = getdate(ngay or nowdate()).strftime("%y%m%d")
	tien_to = f"{ma_ngan}-{ma_khoa}-{yymmdd}-"
	return tien_to + getseries(tien_to, 2)
