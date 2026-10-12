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


def _dong_gia_bo_doc_chap_nhan(bang: str, khach: str, item_code: str, dvt: str) -> list[dict]:
	"""Mọi dòng giá bán của mã trong `bang` mà BỘ ĐỌC có thể chấp nhận cho khách
	này (bỏ qua hiệu lực ngày): không nhà cung cấp/lô, `customer` trống hoặc đúng
	khách, đơn vị gốc hoặc trống. Bộ ghi chỉ được sửa trong tập này, nếu không
	giá ghi xuống sẽ nằm ở một dòng mà bộ đọc không bao giờ thấy."""
	return frappe.db.sql(
		"""select name, price_list_rate, customer, valid_from, valid_upto
		   from `tabItem Price`
		   where item_code = %s and price_list = %s and selling = 1
		     and ifnull(supplier, '') = '' and ifnull(batch_no, '') = ''
		     and (ifnull(customer, '') = '' or customer = %s)
		     and (ifnull(uom, '') = '' or uom = %s)""",
		(item_code, bang, khach, dvt), as_dict=True,
	)


def _chon_dong_de_sua(dong: list[dict]) -> dict | None:
	"""Dòng mà bộ đọc đang trả (hoặc sẽ trả sau khi sửa giá nó).

	Thứ tự khớp `gia_bang_gia_nhieu`: còn hiệu lực hôm nay trước, rồi giá dương
	(dòng giá 0 bị bộ đọc bỏ qua nên sửa nó không đổi được kết quả khi đã có
	dòng dương), rồi dòng gắn riêng khách, rồi `valid_from` mới nhất, rồi `name`.
	Không dòng nào còn hiệu lực (hết hạn / chưa tới ngày) thì lấy dòng ưu tiên
	nhất trong số đó và sửa lại hiệu lực — chèn dòng mới bên cạnh sẽ để lại hai
	dòng cùng khoá nghiệp vụ.
	"""
	hom_nay = getdate(today())

	def khoa(d):
		con_han = (d.valid_from is None or getdate(d.valid_from) <= hom_nay) and (
			d.valid_upto is None or getdate(d.valid_upto) >= hom_nay
		)
		return (
			con_han, con_han and flt(d.price_list_rate) > 0, bool(d.customer),
			getdate(d.valid_from) if d.valid_from else getdate("1900-01-01"), d.name,
		)

	return max(dong, key=khoa) if dong else None


def ghi_gia_vao_bang(
	bang: str, customer: str, item_code: str, gia: float, tien_te: str | None = None
) -> float | None:
	"""Ghi `gia` (theo đơn vị gốc) của `item_code` vào `bang` sao cho BỘ ĐỌC
	(`gia_bang_gia_nhieu`) trả đúng nó cho `customer`. Trả giá cũ của dòng bị
	sửa, `None` khi chèn dòng mới.

	Bộ ghi DUY NHẤT của cổng — khách đồng ý báo giá (§5.2) và đồng bộ từ hợp
	đồng (`gia_hdnt.dong_bo`) cùng đi qua đây. Hai bộ ghi tự chọn dòng là hai
	chỗ lệch được với bộ đọc: một phép upsert theo `{item_code, price_list}`
	thuần sẽ sửa trúng dòng khác đơn vị hay dòng chung đang bị dòng riêng của
	khách che, và giá ghi xuống không bao giờ hiện ra.
	"""
	dvt = frappe.db.get_value("Item", item_code, "stock_uom")
	dong = _chon_dong_de_sua(_dong_gia_bo_doc_chap_nhan(bang, customer, item_code, dvt))
	if dong:
		gia_cu = flt(dong.price_list_rate) or None
		frappe.db.set_value("Item Price", dong.name, {
			"price_list_rate": gia, "valid_from": today(), "valid_upto": None,
		})
		return gia_cu
	frappe.get_doc({
		"doctype": "Item Price", "item_code": item_code, "price_list": bang,
		"selling": 1, "buying": 0, "uom": dvt,
		"currency": tien_te or frappe.db.get_value("Price List", bang, "currency") or "VND",
		"price_list_rate": gia, "valid_from": today(),
	}).insert(ignore_permissions=True)
	return None


def ghi_gia_da_dong_y(so, nguoi_dong_y: str | None = None) -> list[dict]:
	"""Ghi đơn giá các dòng "Báo giá" của `so` vào Price List của khách.

	Spec 2026-10-09 §5.2. Gọi SAU khi khách đã đồng ý. Chỉ dòng mang dấu "Báo giá"
	và có giá dương; dòng "Bảng giá" đã là giá của bảng rồi. Giá ghi theo đơn vị
	gốc. Ném lỗi khi ghi hỏng hoặc khi đọc lại không ra giá vừa ghi — người gọi bọc.
	"""
	from miyano_portal.portal_mua_le import ITEM_GIU_CHO

	bang = dam_bao_bang_gia_rieng(so.customer)
	tien_te = frappe.db.get_value("Price List", bang, "currency") or "VND"
	theo_ma: dict[str, float] = {}
	trung = set()
	for d in so.items:
		if d.item_code == ITEM_GIU_CHO or d.get("custom_nguon_gia") != NGUON_BAO_GIA:
			continue
		if flt(d.rate) <= 0:
			continue
		gia = flt(d.rate) / (flt(d.conversion_factor) or 1)
		if d.item_code in theo_ma and theo_ma[d.item_code] != gia:
			trung.add(d.item_code)
		theo_ma[d.item_code] = gia          # dòng sau cùng thắng
		# Dấu để chốt 3 (chot_bao_gia) so với giá nhân viên sửa về sau.
		frappe.db.set_value("Sales Order Item", d.name, "custom_gia_khach_dong_y",
		                    flt(d.rate), update_modified=False)

	ket_qua = []
	for item_code, gia in theo_ma.items():
		gia_cu = ghi_gia_vao_bang(bang, so.customer, item_code, gia, tien_te)
		ket_qua.append({"item_code": item_code, "gia_cu": gia_cu, "gia_moi": gia})

	if ket_qua:
		doc_lai = gia_bang_gia_nhieu(so.customer, list(theo_ma))
		lech = [m for m, g in theo_ma.items() if doc_lai.get(m) != g]
		if lech:
			raise RuntimeError(
				"Đọc lại Price List không ra giá vừa ghi cho: " + ", ".join(lech)
			)
		dong_ghi = [
			f"{d['item_code']}: "
			f"{frappe.utils.fmt_money(d['gia_cu'], currency=tien_te) if d['gia_cu'] else 'chưa có'}"
			f" → {frappe.utils.fmt_money(d['gia_moi'], currency=tien_te)}"
			for d in ket_qua
		]
		ghi_chu = (
			f"[Portal] Ghi giá khách đã đồng ý vào {bang}"
			+ (f" (người đồng ý: {nguoi_dong_y})" if nguoi_dong_y else "")
			+ " — " + "; ".join(dong_ghi)
		)
		if trung:
			ghi_chu += (
				". Lưu ý: " + ", ".join(sorted(trung))
				+ " có nhiều dòng khác giá trên đơn, đã lấy dòng sau cùng."
			)
		# Chạy dưới phiên của khách (role Customer, không quyền Comment trên
		# Sales Order) nên chèn thẳng thay vì `so.add_comment`.
		frappe.get_doc({
			"doctype": "Comment", "comment_type": "Comment",
			"reference_doctype": "Sales Order", "reference_name": so.name,
			"content": ghi_chu, "comment_email": nguoi_dong_y or frappe.session.user,
		}).insert(ignore_permissions=True)
	return ket_qua
