"""Giá của cổng khách hàng: MỘT nguồn — Price List của khách.

Spec `docs/superpowers/specs/2026-10-09-gia-theo-price-list-design.md` §3, §5.
Chủ đầu tư chốt 09/10/2026: cổng không còn định giá theo hợp đồng nguyên tắc.
Mọi nơi cần giá của một mặt hàng cho một khách đều hỏi module này — danh mục,
phiếu đề xuất, dựng đơn, khớp mã hàng gõ tay, đặt lại đơn cũ.
"""

import frappe
from frappe.utils import flt, getdate, today

NGUON_BANG_GIA = "Bảng giá"
NGUON_BAO_GIA = "Báo giá"
LOAI_DON_BANG_GIA = "Theo bảng giá"


def gia_bang_gia_nhieu(customer: str, item_codes: list[str]) -> dict[str, float]:
	"""`{item_code: giá}` cho những mã CÓ giá. Mã vắng mặt = chưa có giá.

	Một truy vấn cho cả lô. Chỉ nhận dòng theo đơn vị gốc (cổng luôn đặt theo
	`stock_uom`), còn hiệu lực hôm nay, giá dương, không gắn nhà cung cấp/lô,
	và hoặc là dòng chung (`customer` trống) hoặc đúng của khách này. Dòng gắn
	riêng khách này thắng dòng chung; cùng loại thì `valid_from` mới nhất thắng;
	trùng thì `name` lớn hơn thắng — tất định.
	"""
	item_codes = [m for m in dict.fromkeys(item_codes or []) if m]
	if not item_codes:
		return {}
	bang = frappe.db.get_value("Customer", customer, "default_price_list")
	if not bang:
		return {}
	hom_nay = getdate(today())
	dong = frappe.db.sql(
		"""select ip.item_code, ip.price_list_rate
		   from `tabItem Price` ip
		   inner join `tabItem` it on it.name = ip.item_code
		   where ip.price_list = %(bang)s and ip.selling = 1
		     and ip.item_code in %(ma)s
		     and ip.price_list_rate > 0
		     and ifnull(ip.supplier, '') = '' and ifnull(ip.batch_no, '') = ''
		     and (ifnull(ip.customer, '') = '' or ip.customer = %(khach)s)
		     and (ifnull(ip.uom, '') = '' or ip.uom = it.stock_uom)
		     and (ip.valid_from is null or ip.valid_from <= %(nay)s)
		     and (ip.valid_upto is null or ip.valid_upto >= %(nay)s)
		   order by (ifnull(ip.customer, '') <> '') asc,
		     ifnull(ip.valid_from, '1900-01-01') asc, ip.name asc""",
		{"bang": bang, "khach": customer, "ma": tuple(item_codes), "nay": hom_nay},
		as_dict=True,
	)
	# Sắp tăng dần (dòng riêng khách sau dòng chung) rồi ghi đè: dòng cuối thắng.
	return {d.item_code: flt(d.price_list_rate) for d in dong}


def gia_bang_gia(customer: str, item_code: str) -> float | None:
	return gia_bang_gia_nhieu(customer, [item_code]).get(item_code)


def _khach_dung_bang(bang: str) -> list[str]:
	return frappe.get_all(
		"Customer", filters={"default_price_list": bang, "disabled": 0},
		pluck="name", order_by="name asc",
	)


def _ten_bang_moi(customer: str) -> str:
	ten = f"Bảng giá {customer}"
	if not frappe.db.exists("Price List", ten):
		return ten
	ma = frappe.db.get_value("Customer", customer, "custom_ma_ngan") or customer
	ten = f"Bảng giá {customer} ({ma})"
	i = 2
	while frappe.db.exists("Price List", ten):
		ten = f"Bảng giá {customer} ({ma}-{i})"
		i += 1
	return ten


def dam_bao_bang_gia_rieng(customer: str) -> str:
	"""Bảo đảm khách có Price List của RIÊNG mình; trả tên bảng.

	Chưa có → tạo "Bảng giá <tên khách>". Đang dùng chung với khách khác →
	tạo bảng riêng và chép sang các dòng giá bán mà khách NÀY được thấy (dòng
	chung và dòng gắn riêng khách này; bỏ dòng gắn khách khác, nhà cung cấp,
	lô). Ghi giá đàm
	phán của một bệnh viện vào bảng dùng chung là để bệnh viện khác thấy nó.
	"""
	bang = frappe.db.get_value("Customer", customer, "default_price_list")
	if bang and len(_khach_dung_bang(bang)) <= 1:
		return bang

	moi = frappe.get_doc({
		"doctype": "Price List", "price_list_name": _ten_bang_moi(customer),
		"currency": (frappe.db.get_value("Price List", bang, "currency") if bang else None)
		or "VND",
		"selling": 1, "enabled": 1,
	}).insert(ignore_permissions=True)

	if bang:
		for d in frappe.get_all(
			"Item Price",
			filters={
				"price_list": bang, "selling": 1,
				"customer": ["in", ["", None, customer]],
				"supplier": ["in", ["", None]],
				"batch_no": ["in", ["", None]],
			},
			fields=["item_code", "uom", "packing_unit", "price_list_rate", "currency",
			        "valid_from", "valid_upto", "lead_time_days", "note", "customer"],
		):
			frappe.get_doc({
				"doctype": "Item Price", "price_list": moi.name,
				"selling": 1, "buying": 0, **d,
			}).insert(ignore_permissions=True)

	frappe.db.set_value("Customer", customer, "default_price_list", moi.name)
	return moi.name
