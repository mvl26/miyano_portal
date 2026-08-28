"""Một khách hàng demo hoàn chỉnh: tài khoản cổng + kho khách hàng + dữ liệu
chạy đúng luồng nghiệp vụ đã định trong `docs/superpowers/specs/2026-08-06-kho-khach-hang-design.md`.

Chạy:

    bench --site erptest.local execute miyano_portal.setup.demo_kho_flow.chay_tat_ca

Idempotent: gọi bao nhiêu lần cũng ra cùng một kết quả, và chạy tiếp được từ
chỗ dở dang nếu một lần chạy trước bị đứt giữa chừng.

Vì sao là MODULE RIÊNG chứ không sửa `uat_scenario.py` / `seed_kho_demo.py`:
hai module đó đang là nguồn dữ liệu cho `test_uat_scenario.py` và tám file test
kho; thêm dữ liệu vào chúng là đổi tiền đề của những test đó mà không được gì.
Module này GỌI LẠI `setup_uat()` để dùng chung ba mặt hàng + kho Miyano + tồn
kho phía Miyano, rồi dựng phần của riêng nó lên trên.

KHÔNG gọi `frappe.db.commit()` ở bất kỳ đâu trong file (cùng lý do đã ghi trong
`seed_kho_demo.py`): `bench execute` tự commit khi chạy xong không lỗi, còn một
commit nằm bên trong sẽ phá `rollback` của FrappeTestCase nếu sau này có test
nào seed từ đây.
"""

import frappe

from miyano_portal.api import kho as kho_api
from miyano_portal.setup import uat_runner
from miyano_portal.setup.uat_scenario import (
	COMPANY,
	WAREHOUSE_NAME as KHO_MIYANO,
	setup_uat,
)

# --- Khách hàng demo -------------------------------------------------------

CUSTOMER = "Bệnh viện Đa khoa Minh Đức (DEMO)"
CUSTOMER_TAX_ID = "0101234567"
CUSTOMER_ADDRESS = "88 Nguyễn Trãi, Thanh Xuân, Hà Nội"
PORTAL_EMAIL = "bvminhduc@demo.miyano"
PORTAL_PASSWORD = "Portal@123"
CONTACT_NAME = "Khoa Dược BV Đa khoa Minh Đức"
PRICE_LIST = "HĐNT-BVMinhDuc-2026"

TEN_KHO = "Kho Khoa Dược"
MA_KHO = "MD"
THU_KHO = "Trần Thị Bích Ngọc"

# --- Danh mục vật tư của kho khách -----------------------------------------
# Ba mã đầu là mã Miyano (có `item_code`, chính là ba Item của uat_scenario);
# mã cuối là MÃ RIÊNG của bệnh viện — `item_code = None`, không hề tồn tại
# Item nào tương ứng bên ERPNext. Đây là trường hợp §3.2 của thiết kế mô tả và
# là thứ tài liệu vận hành cần một ví dụ thật để giải thích.
VAT_TU = [
	{
		"ma_vat_tu": "MYN-GLOVE-M",
		"ten_vat_tu": "Găng tay khám nitrile size M – hộp 100 cái",
		"dvt": "Hộp",
		"item_code": "MYN-GLOVE-M",
		"nhom": "Vật tư tiêu hao",
		"quy_cach": "Hộp 100 cái",
		"gia_von": 70000,
	},
	{
		"ma_vat_tu": "MYN-SYR-10",
		"ten_vat_tu": "Bơm tiêm 10ml G21 – hộp 100 cái",
		"dvt": "Hộp",
		"item_code": "MYN-SYR-10",
		"nhom": "Vật tư tiêu hao",
		"quy_cach": "Hộp 100 cái",
		"gia_von": 65000,
	},
	{
		"ma_vat_tu": "MYN-ALT",
		"ten_vat_tu": "Hoá chất sinh hoá ALT (GPT) – hộp 4×50ml",
		"dvt": "Hộp",
		"item_code": "MYN-ALT",
		"nhom": "Hoá chất xét nghiệm",
		"quy_cach": "Hộp 4×50ml",
		"gia_von": 950000,
	},
	{
		"ma_vat_tu": "MD-BONG-01",
		"ten_vat_tu": "Bông y tế cuộn 500g (bệnh viện tự mua)",
		"dvt": "Cuộn",
		"item_code": None,
		"nhom": "Vật tư tiêu hao",
		"quy_cach": "Cuộn 500g",
		"gia_von": 45000,
	},
]

# --- Thiết bị (Task 15) ------------------------------------------------------
# Hai máy CÙNG MODEL, một chính một dự phòng — ví dụ thật cho câu hỏi §3.1 của
# spec 27/08 mà HDSD-quan-ly-vat-tu-theo-may.md phải trả lời: "một vật tư dùng
# được cho NHIỀU máy". `MYN-ALT` (đã có sẵn trong VAT_TU) được gắn vào bảng
# "Máy sử dụng" của CẢ HAI máy này (_ensure_thiet_bi_gan_vat_tu), rồi xuất cho
# cả hai (_xuat_theo_may) để báo cáo "Vật tư · Máy · Khoa phòng" có số liệu
# thật ở phần tách theo máy, không chỉ một dòng "Chưa gắn máy". `MYN-GLOVE-M`
# (găng tay) KHÔNG gắn máy nào — ví dụ thật cho "vật tư dùng chung".
# `khoa_phong` để trống (máy dùng chung) — demo này không dựng `Customer
# Department`, nằm ngoài phạm vi Task 15 (chỉ thêm THIẾT BỊ vào kịch bản).
THIET_BI = [
	{
		"ma_thiet_bi": "MAY-SH-01",
		"ten_thiet_bi": "Máy sinh hoá tự động XN-550 (chính)",
		"hang_san_xuat": "Sysmex",
		"xuat_xu": "Nhật Bản",
		"model": "XN-550",
		"so_serial": "SH01-2024-0091",
	},
	{
		"ma_thiet_bi": "MAY-SH-02",
		"ten_thiet_bi": "Máy sinh hoá tự động XN-550 (dự phòng)",
		"hang_san_xuat": "Sysmex",
		"xuat_xu": "Nhật Bản",
		"model": "XN-550",
		"so_serial": "SH02-2024-0114",
	},
]
MA_VAT_TU_DUNG_HAI_MAY = "MYN-ALT"

# --- Tồn đầu kỳ: CỐ Ý trải lô theo ba mốc hạn dùng --------------------------
# Delivery Note trên site này không gắn lô (Item không bật batch), nên phiếu
# nhập sinh từ đơn hàng luôn rơi vào lô "KHONG-LO" và KHÔNG có hạn dùng. Nếu
# tồn đầu kỳ cũng không có hạn dùng thì gợi ý FEFO và cả hai phần của báo cáo
# "Cảnh báo hạn dùng" đều rỗng — demo và tài liệu sẽ không có gì để chỉ.
# `so_ngay_han` được cộng vào ngày hôm nay lúc chạy nên dữ liệu không bao giờ
# "hết đát" theo thời gian thật.
TON_DAU = [
	# (ma_vat_tu, so_lo, so_ngay_han, so_luong, don_gia)
	("MYN-GLOVE-M", "GL2504-A", -25, 18, 68000),   # đã hết hạn, còn tồn
	("MYN-GLOVE-M", "GL2508-B", 40, 60, 70000),    # sắp hết hạn trong 90 ngày
	("MYN-GLOVE-M", "GL2601-C", 540, 120, 72000),  # còn hạn dài
	("MYN-SYR-10", "SY2506-A", 75, 40, 64000),
	("MYN-SYR-10", "SY2512-B", 420, 90, 66000),
	("MYN-ALT", "ALT2505-A", -10, 3, 940000),      # hoá chất đã quá hạn
	("MYN-ALT", "ALT2509-B", 60, 12, 950000),
	("MD-BONG-01", "BONG-2026-01", 300, 50, 45000),
]

# Số phiếu PO của khách, dùng luôn làm KHOÁ IDEMPOTENT cho từng đơn: chạy lại
# script sẽ tìm thấy đơn cũ theo số PO này thay vì đẻ thêm đơn mới.
PO_DON_1 = "PO-MD-2026-001"
PO_DON_2 = "PO-MD-2026-002"
PO_DON_3 = "PO-MD-2026-003"

# Nhãn nhận diện các phiếu kho do script này sinh ra (khoá idempotent thứ hai,
# cho những chứng từ không có số PO để bám vào).
NHAN_TON_DAU = "[DEMO] Tồn đầu kỳ chuyển sang khi mở kho trên cổng"
NHAN_XUAT_SU_DUNG = "[DEMO] Xuất cho Khoa Xét nghiệm dùng trong tuần"
NHAN_XUAT_HUY = "[DEMO] Xuất huỷ lô đã quá hạn theo biên bản huỷ"
NHAN_NHAP_SAI = "[DEMO] Phiếu nhập nhầm — dùng để minh hoạ huỷ phiếu/phiếu đảo"
NHAN_XUAT_THEO_MAY = "[DEMO] Xuất hoá chất cho cả hai máy sinh hoá dùng chung"

# Tồn tối thiểu phía kho Miyano để ba đơn hàng demo giao được. Dưới ngưỡng này
# thì bù lên MUC_BU_TON bằng một phiếu nhập kho ERPNext.
TON_TOI_THIEU_MIYANO = 120
MUC_BU_TON = 400


# ---------------------------------------------------------------------------
# Tiện ích
# ---------------------------------------------------------------------------


class _lam_khach:
	"""Chạy một khối lệnh DƯỚI phiên của tài khoản cổng.

	Cần thiết chứ không phải trang trí: mọi endpoint trong `api/kho.py` và
	`api/portal.py` đều suy kho/khách hàng từ `frappe.session.user`. Chạy bằng
	Administrator sẽ hoặc ném lỗi "chưa gắn với khách hàng nào", hoặc tệ hơn là
	đi qua một nhánh code khác hẳn nhánh mà khách thật sự đi.
	"""

	def __enter__(self):
		self._truoc = frappe.session.user
		frappe.set_user(PORTAL_EMAIL)
		return self

	def __exit__(self, *args):
		frappe.set_user(self._truoc)
		return False


def _ngay(so_ngay: int) -> str:
	return frappe.utils.add_days(frappe.utils.today(), so_ngay)


def _log(msg: str) -> None:
	print(f"  · {msg}")


# ---------------------------------------------------------------------------
# Phần 1 — Khách hàng, tài khoản cổng, hợp đồng nguyên tắc
# ---------------------------------------------------------------------------


def _ensure_price_list() -> str:
	if not frappe.db.exists("Price List", PRICE_LIST):
		frappe.get_doc({
			"doctype": "Price List",
			"price_list_name": PRICE_LIST,
			"selling": 1,
			"currency": "VND",
		}).insert(ignore_permissions=True)
	return PRICE_LIST


def _gia_ban(item_code: str) -> float:
	"""Giá bán của Miyano cho mặt hàng này, lấy từ bảng giá của kịch bản UAT.

	Không hardcode lại: hai bảng giá lệch nhau thì `portal_order_place` vẫn
	chạy (nó đọc bảng giá của chính khách) nhưng con số trên demo sẽ không
	khớp bất kỳ chứng từ nào khác trên site.
	"""
	from miyano_portal.setup.uat_scenario import ITEMS as UAT_ITEMS

	for it in UAT_ITEMS:
		if it["item_code"] == item_code:
			return float(it["rate"])
	raise ValueError(f"Không tìm thấy giá UAT cho {item_code}")


def _ensure_item_prices() -> None:
	for vt in VAT_TU:
		if not vt["item_code"]:
			continue
		if frappe.db.exists(
			"Item Price",
			{"item_code": vt["item_code"], "price_list": PRICE_LIST, "selling": 1},
		):
			continue
		frappe.get_doc({
			"doctype": "Item Price",
			"item_code": vt["item_code"],
			"price_list": PRICE_LIST,
			"uom": vt["dvt"],
			"selling": 1,
			"price_list_rate": _gia_ban(vt["item_code"]),
			"currency": "VND",
		}).insert(ignore_permissions=True)


def _ensure_customer() -> str:
	if not frappe.db.exists("Customer", CUSTOMER):
		frappe.get_doc({
			"doctype": "Customer",
			"customer_name": CUSTOMER,
			"customer_type": "Company",
			"customer_group": "All Customer Groups",
			"territory": "All Territories",
			"tax_id": CUSTOMER_TAX_ID,
			"default_price_list": PRICE_LIST,
		}).insert(ignore_permissions=True)
	elif frappe.db.get_value("Customer", CUSTOMER, "default_price_list") != PRICE_LIST:
		frappe.db.set_value("Customer", CUSTOMER, "default_price_list", PRICE_LIST)
	return CUSTOMER


def _ensure_address() -> str:
	ten = f"{CUSTOMER}-Shipping"
	if not frappe.db.exists("Address", ten):
		addr = frappe.new_doc("Address")
		addr.address_title = CUSTOMER
		addr.address_type = "Shipping"
		addr.address_line1 = CUSTOMER_ADDRESS
		addr.city = "Hà Nội"
		addr.country = "Vietnam"
		addr.is_shipping_address = 1
		addr.append("links", {"link_doctype": "Customer", "link_name": CUSTOMER})
		addr.name = ten
		addr.insert(ignore_permissions=True, set_name=ten)
	return ten


def _ensure_portal_user() -> str:
	"""Tài khoản cổng + Contact + User Permission.

	Đi qua ĐÚNG endpoint mà nhân viên Miyano dùng (`portal_provision`) để
	script và tài liệu không mô tả hai con đường khác nhau, rồi đặt thêm mật
	khẩu demo — thứ `portal_provision` cố ý không làm (ngoài đời khách nhận
	thư mời và tự đặt mật khẩu).
	"""
	from miyano_portal.api.portal import portal_provision

	moi = not frappe.db.exists("User", PORTAL_EMAIL)
	portal_provision(CUSTOMER, PORTAL_EMAIL, send_invite=False)

	user = frappe.get_doc("User", PORTAL_EMAIL)
	thay_doi = False
	if user.first_name != CONTACT_NAME:
		user.first_name = CONTACT_NAME
		thay_doi = True
	if not user.enabled:
		user.enabled = 1
		thay_doi = True
	# Mật khẩu CHỈ đặt ngay lần tạo đầu tiên: đặt lại ở mỗi lần chạy sẽ ghi đè
	# mật khẩu mà người dùng demo có thể đã tự đổi.
	if moi:
		user.new_password = PORTAL_PASSWORD
		thay_doi = True
	if thay_doi:
		user.save(ignore_permissions=True)
	return PORTAL_EMAIL


def _ensure_blanket_order() -> str:
	ten = frappe.db.get_value(
		"Blanket Order", {"customer": CUSTOMER, "blanket_order_type": "Selling"}, "name"
	)
	if not ten:
		bo = frappe.get_doc({
			"doctype": "Blanket Order",
			"blanket_order_type": "Selling",
			"customer": CUSTOMER,
			"company": COMPANY,
			"from_date": frappe.utils.get_year_start(frappe.utils.today()),
			"to_date": frappe.utils.add_months(frappe.utils.today(), 12),
			"items": [
				{"item_code": vt["item_code"], "qty": 500, "rate": _gia_ban(vt["item_code"])}
				for vt in VAT_TU
				if vt["item_code"]
			],
		})
		bo.insert(ignore_permissions=True)
		ten = bo.name
	if frappe.db.get_value("Blanket Order", ten, "docstatus") == 0:
		frappe.get_doc("Blanket Order", ten).submit()
	return ten


# ---------------------------------------------------------------------------
# Phần 2 — Kho khách hàng: mở kho, danh mục, tồn đầu kỳ
# ---------------------------------------------------------------------------


def _ngay_bat_dau() -> str:
	"""Ngày bắt đầu quản lý kho = 01/01 của năm hiện tại.

	`get_year_start()` trả về `datetime.date`, còn mọi chỗ khác trong file làm
	việc với chuỗi `YYYY-MM-DD` — ép về chuỗi ngay tại đây để không có hai
	kiểu dữ liệu ngày cùng chảy qua `max()` hay `frappe.get_doc`.
	"""
	return str(frappe.utils.get_year_start(frappe.utils.today()))


def _ensure_kho() -> str:
	ten = frappe.db.get_value("Customer Warehouse", {"customer": CUSTOMER}, "name")
	if ten:
		return ten
	from miyano_portal.setup.install_kho_print_formats import DEFAULT_NHAP, DEFAULT_XUAT

	doc = frappe.get_doc({
		"doctype": "Customer Warehouse",
		"customer": CUSTOMER,
		"ten_kho": TEN_KHO,
		"ma_kho": MA_KHO,
		"active": 1,
		"thu_kho": THU_KHO,
		"dia_chi_kho": CUSTOMER_ADDRESS,
		"ngay_bat_dau": _ngay_bat_dau(),
		"ten_don_vi_in": CUSTOMER,
		"bo_phan_in": "Khoa Dược",
		# Mẫu in chỉ gắn khi Print Format đã được cài trên site (patch
		# v1_1/install_kho_print_formats). Chưa có thì để trống — API in vẫn
		# tự rơi về mẫu TT107 mặc định, không vỡ.
		"mau_phieu_nhap": DEFAULT_NHAP if frappe.db.exists("Print Format", DEFAULT_NHAP) else None,
		"mau_phieu_xuat": DEFAULT_XUAT if frappe.db.exists("Print Format", DEFAULT_XUAT) else None,
	})
	doc.insert(ignore_permissions=True)
	return doc.name


def _ensure_vat_tu(kho: str) -> dict:
	"""Trả về {ma_vat_tu: docname} cho toàn bộ danh mục."""
	out = {}
	for vt in VAT_TU:
		ten = frappe.db.get_value(
			"Customer Warehouse Item", {"kho": kho, "ma_vat_tu": vt["ma_vat_tu"]}, "name"
		)
		if not ten:
			item_code = vt["item_code"]
			if item_code and not frappe.db.exists("Item", item_code):
				item_code = None
			doc = frappe.get_doc({
				"doctype": "Customer Warehouse Item",
				"kho": kho,
				"ma_vat_tu": vt["ma_vat_tu"],
				"ten_vat_tu": vt["ten_vat_tu"],
				"dvt": vt["dvt"],
				"active": 1,
				"item_code": item_code,
				"quy_cach": vt["quy_cach"],
				"nhom": vt["nhom"],
			})
			doc.insert(ignore_permissions=True)
			ten = doc.name
		out[vt["ma_vat_tu"]] = ten
	return out


def _ensure_thiet_bi() -> dict:
	"""Trả về {ma_thiet_bi: docname} — cùng khuôn `_ensure_vat_tu()` ở trên:
	`Customer Equipment` treo vào `Customer` (không `Customer Warehouse`,
	QĐ-TB-8 của spec 27/08), nên đối chiếu idempotent theo `(customer,
	ma_thiet_bi)`, không theo `kho`.

	Ghi THẲNG bằng `frappe.get_doc(...).insert(ignore_permissions=True)`,
	KHÔNG qua endpoint `kho_thiet_bi_save`: khác `_dat_don()`/`_xuat_kho()`
	(nơi đi qua endpoint có ý nghĩa thật — session khách quyết logic BR-TB-6
	ép khoa, giá theo hợp đồng, gợi ý lô FEFO...), việc TẠO một máy dùng
	chung bởi Administrator không có nhánh business rule nào khác nhánh
	trực tiếp — cùng lý do `_ensure_kho()`/`_ensure_vat_tu()` ở trên cũng
	ghi thẳng."""
	out = {}
	for tb in THIET_BI:
		ten = frappe.db.get_value(
			"Customer Equipment", {"customer": CUSTOMER, "ma_thiet_bi": tb["ma_thiet_bi"]}, "name"
		)
		if not ten:
			doc = frappe.get_doc({
				"doctype": "Customer Equipment",
				"customer": CUSTOMER,
				"active": 1,
				**tb,
			})
			doc.insert(ignore_permissions=True)
			ten = doc.name
		out[tb["ma_thiet_bi"]] = ten
	return out


def _ensure_thiet_bi_gan_vat_tu(vat_tu: dict, thiet_bi: dict) -> None:
	"""Gắn CẢ HAI máy vào bảng "Máy sử dụng" của `MA_VAT_TU_DUNG_HAI_MAY` —
	ví dụ thật cho QĐ-TB-2 (một vật tư dùng được nhiều máy) mà HDSD cần chỉ
	trên màn hình thật. Idempotent bằng kiểm tra trước khi append (không
	dùng lại `thiet_bi_mod.gan_vao_vat_tu()` để khỏi mở phiên khách chỉ cho
	một thao tác ghi thẳng đơn giản — cùng lý lẽ ở `_ensure_thiet_bi()`)."""
	doc = frappe.get_doc("Customer Warehouse Item", vat_tu[MA_VAT_TU_DUNG_HAI_MAY])
	da_gan = {r.thiet_bi for r in doc.may_su_dung}
	thay_doi = False
	for ma in ("MAY-SH-01", "MAY-SH-02"):
		if thiet_bi[ma] not in da_gan:
			doc.append("may_su_dung", {"thiet_bi": thiet_bi[ma]})
			thay_doi = True
	if thay_doi:
		doc.save(ignore_permissions=True)


def _phieu_theo_nhan(doctype: str, kho: str, nhan: str) -> str | None:
	return frappe.db.get_value(
		doctype, {"kho": kho, "dien_giai": nhan, "docstatus": ["<", 2]}, "name"
	)


def _ensure_ton_dau(kho: str, vat_tu: dict) -> str:
	"""Một phiếu nhập `Tồn đầu kỳ` duy nhất, mang toàn bộ lô mở kho."""
	da_co = _phieu_theo_nhan("Customer Stock Receipt", kho, NHAN_TON_DAU)
	if da_co:
		if frappe.db.get_value("Customer Stock Receipt", da_co, "docstatus") == 0:
			frappe.get_doc("Customer Stock Receipt", da_co).submit()
		return da_co

	# Ngày phiếu không được trước `ngay_bat_dau` của kho (voucher.validate_ngay).
	ngay = max(_ngay(-120), _ngay_bat_dau())
	doc = frappe.get_doc({
		"doctype": "Customer Stock Receipt",
		"kho": kho,
		"ngay": ngay,
		"loai_nhap": "Tồn đầu kỳ",
		"nguoi_giao": "Kiểm kê bàn giao khi mở kho",
		"chung_tu_kem": "BB kiểm kê 01/2026",
		"dien_giai": NHAN_TON_DAU,
		"items": [
			{
				"vat_tu": vat_tu[ma],
				"so_lo": so_lo,
				"han_su_dung": _ngay(so_ngay_han),
				"so_luong": so_luong,
				"don_gia": don_gia,
			}
			for ma, so_lo, so_ngay_han, so_luong, don_gia in TON_DAU
		],
	})
	doc.insert(ignore_permissions=True)
	doc.submit()
	return doc.name


# ---------------------------------------------------------------------------
# Phần 3 — Luồng đặt hàng Miyano → giao hàng → phiếu nhập kho khách
# ---------------------------------------------------------------------------


def _ton_kho_miyano(item_code: str) -> float:
	return float(
		frappe.db.get_value(
			"Bin", {"item_code": item_code, "warehouse": KHO_MIYANO}, "actual_qty"
		)
		or 0
	)


def _bu_ton_miyano() -> dict:
	"""Bảo đảm kho Miyano còn đủ hàng để ba đơn demo giao được.

	Kịch bản UAT chỉ nhập tồn MỘT LẦN rồi không bao giờ bù lại (đúng ý đồ của
	nó), nên sau vài vòng demo kho có thể cạn và Delivery Note sẽ ném
	NegativeStockError. Ở đây bù riêng, không đụng vào hàm của uat_scenario.
	"""
	from miyano_portal.setup.uat_scenario import ITEMS as UAT_ITEMS

	thieu = [it for it in UAT_ITEMS if _ton_kho_miyano(it["item_code"]) < TON_TOI_THIEU_MIYANO]
	if not thieu:
		return {it["item_code"]: _ton_kho_miyano(it["item_code"]) for it in UAT_ITEMS}

	se = frappe.get_doc({
		"doctype": "Stock Entry",
		"stock_entry_type": "Material Receipt",
		"company": COMPANY,
		"to_warehouse": KHO_MIYANO,
		"items": [
			{
				"item_code": it["item_code"],
				"qty": MUC_BU_TON - _ton_kho_miyano(it["item_code"]),
				"t_warehouse": KHO_MIYANO,
				"basic_rate": it["opening_rate"],
			}
			for it in thieu
		],
	})
	se.insert(ignore_permissions=True)
	se.submit()
	_log(f"Bù tồn kho Miyano cho {len(thieu)} mặt hàng ({se.name})")
	return {it["item_code"]: _ton_kho_miyano(it["item_code"]) for it in UAT_ITEMS}


def _dat_don(contract: str, po: str, gio_hang: list[dict], ghi_chu: str) -> str:
	"""Đặt một đơn QUA ĐÚNG endpoint của cổng, dưới phiên của khách.

	Không dựng thẳng Sales Order: chỉ đường này mới đặt `custom_nguon_don`,
	`custom_hdnt`, `against_blanket_order` và kiểm hạn mức hợp đồng đúng như
	một đơn khách đặt thật.
	"""
	da_co = frappe.db.get_value(
		"Sales Order", {"custom_so_po_khach": po, "docstatus": ["<", 2]}, "name"
	)
	if da_co:
		return da_co
	from miyano_portal.api.portal import portal_order_place

	with _lam_khach():
		kq = portal_order_place(
			contract=contract,
			items=gio_hang,
			po=po,
			delivery_date=_ngay(3),
			note=ghi_chu,
		)
	_log(f"Đặt đơn {kq['sales_order']} (PO {po})")
	return kq["sales_order"]


def _xac_nhan_don(so: str) -> None:
	if frappe.db.get_value("Sales Order", so, "docstatus") == 0:
		uat_runner.submit_so(so)
		_log(f"Miyano xác nhận đơn {so}")


def _giao_hang(so: str, qty_map: dict | None = None) -> str | None:
	"""Giao hàng cho một đơn. Trả về tên Delivery Note (mới hoặc đã có)."""
	dn = frappe.db.get_value(
		"Delivery Note Item", {"against_sales_order": so, "docstatus": 1}, "parent"
	)
	if dn:
		return dn
	kq = uat_runner.deliver_so(so, qty_map)
	_log(f"Giao hàng {kq['dn']} cho đơn {so}")
	return kq["dn"]


def _phieu_nhap_tu_dn(dn: str) -> str | None:
	return frappe.db.get_value(
		"Customer Stock Receipt", {"delivery_note": dn, "docstatus": ["<", 2]}, "name"
	)


def _ghi_so_phieu_nhap(ten_phieu: str) -> None:
	"""Thủ kho đối chiếu xong thì ghi sổ — qua ĐÚNG endpoint của cổng."""
	if frappe.db.get_value("Customer Stock Receipt", ten_phieu, "docstatus") != 0:
		return
	with _lam_khach():
		kho_api.kho_phieu_submit("Customer Stock Receipt", ten_phieu)
	_log(f"Thủ kho ghi sổ phiếu nhập {ten_phieu}")


# ---------------------------------------------------------------------------
# Phần 4 — Xuất kho, huỷ phiếu
# ---------------------------------------------------------------------------


def _xuat_kho(kho: str, vat_tu: str, so_luong: float, loai_xuat: str,
	          noi_nhan: str, nguoi_nhan: str, nhan: str, chap_nhan_het_han: bool = False) -> str | None:
	"""Lập + ghi sổ một phiếu xuất, lô do chính gợi ý FEFO của hệ thống chọn.

	Không tự chọn lô: đi qua `kho_lo_goi_y` để dữ liệu demo phản ánh đúng thứ
	tự lô mà khách sẽ thấy trên màn hình lập phiếu.
	"""
	da_co = _phieu_theo_nhan("Customer Stock Issue", kho, nhan)
	if da_co:
		if frappe.db.get_value("Customer Stock Issue", da_co, "docstatus") == 0:
			with _lam_khach():
				kho_api.kho_phieu_submit("Customer Stock Issue", da_co)
		return da_co

	with _lam_khach():
		goi_y = kho_api.kho_lo_goi_y(vat_tu, so_luong)
		dong = [
			{
				"vat_tu": vat_tu,
				"so_lo": lot["so_lo"],
				"so_luong": lot["de_xuat"],
				"xac_nhan_het_han": 1 if lot["het_han"] else 0,
			}
			for lot in goi_y["lots"]
			if lot["de_xuat"] > 0 and (chap_nhan_het_han or not lot["het_han"])
		]
		if not dong:
			return None
		phieu = kho_api.kho_phieu_xuat_save({
			"ngay": frappe.utils.today(),
			"loai_xuat": loai_xuat,
			"noi_nhan": noi_nhan,
			"nguoi_nhan": nguoi_nhan,
			"dien_giai": nhan,
			"items": dong,
		})
		kho_api.kho_phieu_submit("Customer Stock Issue", phieu["name"])
	_log(f"Xuất kho {phieu['name']} — {loai_xuat}")
	return phieu["name"]


def _xuat_theo_may(kho: str, dong_may: list[dict], loai_xuat: str,
	                noi_nhan: str, nguoi_nhan: str, nhan: str) -> str | None:
	"""Một phiếu "Xuất sử dụng" NHIỀU dòng, mỗi dòng gắn một MÁY KHÁC NHAU —
	`_xuat_kho()` ở trên chỉ xuất một vật tư/một dòng nên không đủ để báo cáo
	"Vật tư · Máy · Khoa phòng" (§9.2 spec) có số liệu tách theo máy cho CẢ
	HAI máy demo; thiếu hàm này, phần "theo máy" của báo cáo sẽ chỉ có một
	dòng thật (dòng còn lại toàn số 0 giả — đúng thứ spec §11 ca 1 cấm).

	`dong_may`: `[{"vat_tu": docname, "so_luong": n, "thiet_bi": docname}, ...]`.
	Mỗi dòng tự gọi `kho_lo_goi_y()` RIÊNG (không gộp số lượng rồi tự chia) —
	cùng lý do `_xuat_kho()` không tự chọn lô: dữ liệu demo phải phản ánh
	đúng gợi ý FEFO thật cho từng dòng, không phải một phép chia tay áng
	chừng. Chỉ lấy lô CÒN HẠN (giữ đơn giản, không cần tick xác nhận hết hạn
	ở kịch bản này — `_xuat_kho()` đã có ví dụ xuất huỷ hết hạn riêng)."""
	da_co = _phieu_theo_nhan("Customer Stock Issue", kho, nhan)
	if da_co:
		if frappe.db.get_value("Customer Stock Issue", da_co, "docstatus") == 0:
			with _lam_khach():
				kho_api.kho_phieu_submit("Customer Stock Issue", da_co)
		return da_co

	with _lam_khach():
		dong = []
		for d in dong_may:
			goi_y = kho_api.kho_lo_goi_y(d["vat_tu"], d["so_luong"])
			dong.extend(
				{
					"vat_tu": d["vat_tu"],
					"thiet_bi": d["thiet_bi"],
					"so_lo": lot["so_lo"],
					"so_luong": lot["de_xuat"],
					"xac_nhan_het_han": 0,
				}
				for lot in goi_y["lots"]
				if lot["de_xuat"] > 0 and not lot["het_han"]
			)
		if not dong:
			return None
		phieu = kho_api.kho_phieu_xuat_save({
			"ngay": frappe.utils.today(),
			"loai_xuat": loai_xuat,
			"noi_nhan": noi_nhan,
			"nguoi_nhan": nguoi_nhan,
			"dien_giai": nhan,
			"items": dong,
		})
		kho_api.kho_phieu_submit("Customer Stock Issue", phieu["name"])
	_log(f"Xuất kho theo máy {phieu['name']} — {loai_xuat}")
	return phieu["name"]


def _phieu_nhap_sai_va_dao(kho: str, vat_tu: dict) -> dict:
	"""Một phiếu nhập tay bị huỷ, để dữ liệu demo có sẵn một PHIẾU ĐẢO.

	Huỷ phiếu là nhánh nghiệp vụ khó giải thích nhất trong tài liệu (§4.5:
	không xoá dòng sổ, sinh phiếu ngược dấu); có sẵn một cặp phiếu gốc + phiếu
	đảo trên site thì người đọc mở ra xem được thay vì phải tin lời mô tả.
	"""
	goc = _phieu_theo_nhan("Customer Stock Receipt", kho, NHAN_NHAP_SAI)
	if goc is None:
		goc = frappe.db.get_value(
			"Customer Stock Receipt",
			{"kho": kho, "dien_giai": NHAN_NHAP_SAI, "docstatus": 2},
			"name",
		)
	if goc is None:
		with _lam_khach():
			phieu = kho_api.kho_phieu_nhap_save({
				"ngay": frappe.utils.today(),
				"loai_nhap": "Nhập khác",
				"nguoi_giao": "Nhà thuốc ngoài",
				"dien_giai": NHAN_NHAP_SAI,
				"items": [{
					"vat_tu": vat_tu["MD-BONG-01"],
					"so_lo": "BONG-2026-99",
					"han_su_dung": _ngay(250),
					"so_luong": 5,
					"don_gia": 46000,
				}],
			})
			kho_api.kho_phieu_submit("Customer Stock Receipt", phieu["name"])
			goc = phieu["name"]
		_log(f"Lập phiếu nhập tay {goc} (sẽ huỷ để sinh phiếu đảo)")

	if frappe.db.get_value("Customer Stock Receipt", goc, "docstatus") == 1:
		with _lam_khach():
			kho_api.kho_phieu_cancel("Customer Stock Receipt", goc)
		_log(f"Huỷ {goc} → hệ thống tự sinh phiếu đảo")

	dao = frappe.db.get_value(
		"Customer Stock Receipt", {"kho": kho, "phieu_goc": goc}, "name"
	)
	return {"phieu_goc": goc, "phieu_dao": dao}


# ---------------------------------------------------------------------------
# Điểm vào
# ---------------------------------------------------------------------------


def setup_khach_hang() -> dict:
	"""Phần 1 + 2: khách hàng, tài khoản cổng, hợp đồng, kho, danh mục, tồn đầu."""
	setup_uat()  # ba mặt hàng + kho Miyano + tồn phía Miyano
	_ensure_price_list()
	_ensure_item_prices()
	_ensure_customer()
	_ensure_address()
	_ensure_portal_user()
	contract = _ensure_blanket_order()

	kho = _ensure_kho()
	vat_tu = _ensure_vat_tu(kho)
	thiet_bi = _ensure_thiet_bi()
	_ensure_thiet_bi_gan_vat_tu(vat_tu, thiet_bi)
	ton_dau = _ensure_ton_dau(kho, vat_tu)

	_log(f"Khách hàng {CUSTOMER} · kho {kho} · hợp đồng {contract}")
	return {
		"customer": CUSTOMER,
		"portal_user": PORTAL_EMAIL,
		"password": PORTAL_PASSWORD,
		"contract": contract,
		"kho": kho,
		"vat_tu": vat_tu,
		"thiet_bi": thiet_bi,
		"phieu_ton_dau": ton_dau,
	}


def chay_flow(ctx: dict) -> dict:
	"""Phần 3 + 4: ba đơn hàng ở ba trạng thái khác nhau, phiếu nhập/xuất, phiếu đảo."""
	_bu_ton_miyano()
	contract, kho, vat_tu = ctx["contract"], ctx["kho"], ctx["vat_tu"]
	thiet_bi = ctx["thiet_bi"]

	# Đơn 1 — trọn vẹn: xác nhận → giao đủ → khách ghi sổ phiếu nhập → xuất hoá
	# đơn → thu tiền một phần (để màn hình Công nợ có số dư thật).
	don1 = _dat_don(contract, PO_DON_1, [
		{"item_code": "MYN-GLOVE-M", "qty": 20},
		{"item_code": "MYN-SYR-10", "qty": 15},
	], "Giao giờ hành chính, liên hệ Khoa Dược trước khi tới.")
	_xac_nhan_don(don1)
	dn1 = _giao_hang(don1)
	pn1 = _phieu_nhap_tu_dn(dn1)
	if pn1:
		_ghi_so_phieu_nhap(pn1)

	si1 = frappe.db.get_value(
		"Sales Invoice Item", {"sales_order": don1, "docstatus": 1}, "parent"
	)
	if not si1:
		si1 = uat_runner.invoice_so(don1)["si"]
		_log(f"Xuất hoá đơn {si1}")
	if not frappe.db.exists("Payment Entry Reference", {"reference_name": si1, "docstatus": 1}):
		tra = float(frappe.db.get_value("Sales Invoice", si1, "grand_total")) * 0.6
		uat_runner.pay_invoice(si1, round(tra, 0))
		_log(f"Thu tiền một phần cho {si1}")

	# Đơn 2 — giao thiếu: chỉ giao 1 trong 2 mặt hàng, và CỐ Ý để phiếu nhập
	# của khách ở trạng thái NHÁP. Đây là trạng thái "thủ kho chưa đối chiếu"
	# mà §4.3 mô tả và tài liệu cần chỉ được trên màn hình thật.
	don2 = _dat_don(contract, PO_DON_2, [
		{"item_code": "MYN-ALT", "qty": 6},
		{"item_code": "MYN-GLOVE-M", "qty": 10},
	], "Hoá chất cần giữ lạnh 2–8°C.")
	_xac_nhan_don(don2)
	dn2 = _giao_hang(don2, {"MYN-ALT": 4})
	pn2 = _phieu_nhap_tu_dn(dn2)

	# Đơn 3 — mới đặt, còn "Chờ xác nhận": để demo màn hình theo dõi đơn và
	# nút "Yêu cầu huỷ" (chỉ hiện khi đơn chưa được xác nhận).
	don3 = _dat_don(contract, PO_DON_3, [
		{"item_code": "MYN-SYR-10", "qty": 25},
	], "Đơn bổ sung cuối tháng.")

	# Xuất kho: một phiếu dùng thường (FEFO bỏ qua lô hết hạn) và một phiếu
	# xuất huỷ lô quá hạn (bắt tick xác nhận).
	xuat1 = _xuat_kho(
		kho, vat_tu["MYN-SYR-10"], 12, "Xuất sử dụng",
		"Khoa Xét nghiệm", "Lê Văn Hùng", NHAN_XUAT_SU_DUNG,
	)
	xuat2 = _xuat_kho(
		kho, vat_tu["MYN-ALT"], 2, "Xuất huỷ - hết hạn",
		"Hội đồng huỷ thuốc", "Phạm Thu Hà", NHAN_XUAT_HUY,
		chap_nhan_het_han=True,
	)

	# Task 15 — xuất CÙNG một hoá chất (MYN-ALT, đã gắn cả hai máy ở
	# _ensure_thiet_bi_gan_vat_tu) cho HAI máy sinh hoá khác nhau trong MỘT
	# phiếu, để bảng "theo máy" của báo cáo thiết bị có số liệu thật ở CẢ HAI
	# dòng máy, không chỉ một.
	#
	# `so_luong=3` (không phải 1): lô CÒN HẠN gần nhất của MYN-ALT xếp SAU lô
	# ALT2505-A đã hết hạn (còn đúng 1 đơn vị tồn, phần dư lại sau NHAN_XUAT_HUY
	# ở trên) trong thứ tự FEFO của `kho_lo_goi_y` — gợi ý greedy CHIA HẾT một
	# yêu cầu nhỏ (`so_luong=1`) cho riêng lô hết hạn đó, để lại 0 cho lô còn
	# hạn, và dòng bị lọc `not het_han` ở `_xuat_theo_may()` rỗng hoàn toàn (đã
	# đo thực nghiệm khi viết hàm này). `so_luong=3` tràn qua khỏi 1 đơn vị của
	# lô hết hạn, đủ để phần CÒN HẠN của gợi ý luôn có 2 đơn vị thật cho mỗi máy.
	xuat3 = _xuat_theo_may(
		kho,
		[
			{"vat_tu": vat_tu["MYN-ALT"], "so_luong": 3, "thiet_bi": thiet_bi["MAY-SH-01"]},
			{"vat_tu": vat_tu["MYN-ALT"], "so_luong": 3, "thiet_bi": thiet_bi["MAY-SH-02"]},
		],
		"Xuất sử dụng", "Khoa Xét nghiệm", "Nguyễn Văn Minh", NHAN_XUAT_THEO_MAY,
	)

	dao = _phieu_nhap_sai_va_dao(kho, vat_tu)

	return {
		"don_hoan_thanh": don1, "delivery_note_1": dn1, "phieu_nhap_da_ghi_so": pn1,
		"hoa_don": si1,
		"don_giao_thieu": don2, "delivery_note_2": dn2, "phieu_nhap_con_nhap": pn2,
		"don_cho_xac_nhan": don3,
		"phieu_xuat_su_dung": xuat1, "phieu_xuat_huy": xuat2,
		"phieu_xuat_theo_may": xuat3,
		**dao,
	}


def chay_tat_ca() -> dict:
	print("== Miyano Portal — dựng khách hàng demo và dữ liệu theo luồng ==")
	ctx = setup_khach_hang()
	kq = chay_flow(ctx)
	tong_hop = {**ctx, **kq}
	print("\n== Xong ==")
	for k, v in tong_hop.items():
		if k not in ("vat_tu", "thiet_bi"):
			print(f"  {k}: {v}")
	print("\n  Đăng nhập cổng: http://192.168.61.129:8003/portal/login")
	print(f"  Tài khoản: {PORTAL_EMAIL} / {PORTAL_PASSWORD}")
	return tong_hop
