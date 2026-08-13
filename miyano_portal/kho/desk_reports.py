"""Báo cáo kho khách hàng phía DESK — nhân viên Miyano xem TẤT CẢ khách hàng
cùng lúc. Phase 6 của thiết kế (docs/superpowers/specs/2026-08-06-kho-khach-
hang-design.md §4.6, §6).

Khác với `kho/reports.py` (một kho tại một thời điểm — dùng cho portal, kho
luôn suy từ phiên đăng nhập của khách), các hàm ở đây LẶP qua danh sách
`Customer Warehouse` rồi gọi lại ĐÚNG các hàm đã có trong `reports.py` cho
từng kho, gắn thêm `customer`/`customer_name`/`kho`/`ten_kho` vào mỗi dòng.
KHÔNG hàm nào ở đây viết lại phép cộng N-X-T, phép gộp tồn theo lô, hay phép
lọc cảnh báo hạn — toàn bộ số học vẫn chỉ tồn tại một nơi duy nhất, đúng yêu
cầu "không viết lại phép tính lần thứ hai" (xem docstring đầu reports.py).

An toàn dữ liệu: các hàm này chỉ được gọi từ ba Report doctype (is_standard,
report_type=Script Report) bị khoá theo role ở tầng framework — xem
setup/install_kho_desk_reports.py. Role `Customer` không có `report:1` trên
bất kỳ doctype kho nào (không có DocPerm nào hết, xem hooks.py), nên
`frappe.has_permission(ref_doctype, "report")` tự chặn trước khi các hàm dưới
đây có cơ hội chạy — không hàm nào ở đây tự kiểm quyền, đúng như các báo cáo
desk khác của Frappe/ERPNext (quyền nằm ở cổng vào report, không nằm trong
thân hàm lấy dữ liệu).

Nhóm theo docname `vat_tu`/`kho`, KHÔNG BAO GIỜ theo `ma_vat_tu`/`ten_kho`:
hai khách hàng khác nhau hoàn toàn có thể tự đặt trùng mã vật tư của riêng họ
(`Vật Tư Kho Khách.ma_vat_tu` chỉ unique trong phạm vi MỘT kho — xem §3.2 của
thiết kế), gộp theo mã sẽ âm thầm cộng tồn của khách A vào khách B.
"""

import frappe

from miyano_portal.kho import reports
from miyano_portal.kho.ledger import EPS


def _active_khos(customer: str | None = None) -> list[dict]:
	"""Danh sách `Customer Warehouse`, lọc theo khách hàng nếu có truyền vào.

	Không lọc theo `active`: một kho đã ngừng hoạt động vẫn có thể còn hàng
	tồn thật (báo cáo 1, 3) hoặc phát sinh lịch sử trong kỳ được chọn (báo cáo
	2) — ẩn nó đi sẽ biến "khách đã dừng" thành "khách không tồn tại" trong
	mắt nhân viên, đúng lúc họ cần biết để thu hồi/thanh lý."""
	filters = {}
	if customer:
		filters["customer"] = customer
	return frappe.get_all(
		"Customer Warehouse", filters=filters,
		fields=["name", "customer", "ten_kho"],
	)


def _customer_names(customers: list[str]) -> dict[str, str]:
	if not customers:
		return {}
	return dict(frappe.get_all(
		"Customer", filters={"name": ["in", list(set(customers))]},
		fields=["name", "customer_name"], as_list=True,
	))


def ton_kho_khach_hang_rows(
	customer: str | None = None,
	item: str | None = None,
	sap_het_han_trong_ngay=None,
) -> list[dict]:
	"""Tồn hiện tại của MỌI khách hàng (hoặc một khách nếu lọc), một dòng cho
	mỗi (kho, vật tư) — gọi lại `reports.ton_hien_tai_rows()` cho từng kho, đây
	chính là hàm N-X-T tồn hiện tại đã dùng cho portal (`kho_ton`)."""
	khos = _active_khos(customer)
	names = _customer_names([k["customer"] for k in khos])

	han_toi = None
	so_ngay = frappe.utils.cint(sap_het_han_trong_ngay) if sap_het_han_trong_ngay not in (None, "") else None
	if so_ngay:
		han_toi = frappe.utils.add_days(frappe.utils.getdate(frappe.utils.today()), so_ngay)

	out = []
	for k in khos:
		for row in reports.ton_hien_tai_rows(k["name"], tim=item or None):
			if han_toi is not None:
				han = row.get("han_gan_nhat")
				if not han or frappe.utils.getdate(han) > han_toi:
					continue
			out.append({
				"customer": k["customer"],
				"customer_name": names.get(k["customer"]) or k["customer"],
				"kho": k["name"],
				"ten_kho": k["ten_kho"],
				**row,
			})
	return sorted(out, key=lambda r: (r["customer_name"], r["ten_vat_tu"]))


def nxt_khach_hang_rows(customer: str | None = None, tu_ngay=None, den_ngay=None) -> list[dict]:
	"""Nhập-Xuất-Tồn của MỌI khách hàng cho cùng một khoảng ngày — gọi lại
	`reports.nxt_item_rows()` cho từng kho, KHÔNG cộng gộp số của hai khách
	vào cùng một dòng dù họ trùng mã vật tư."""
	khos = _active_khos(customer)
	names = _customer_names([k["customer"] for k in khos])

	out = []
	for k in khos:
		for row in reports.nxt_item_rows(k["name"], tu_ngay, den_ngay):
			out.append({
				"customer": k["customer"],
				"customer_name": names.get(k["customer"]) or k["customer"],
				"kho": k["name"],
				"ten_kho": k["ten_kho"],
				**row,
			})
	return sorted(out, key=lambda r: (r["customer_name"], r["ten_vat_tu"]))


def canh_bao_han_khach_hang_rows(customer: str | None = None, so_ngay: int = 90) -> list[dict]:
	"""Cảnh báo hạn dùng của MỌI khách hàng gộp vào một danh sách, gần nhất
	(đã hết hạn lâu nhất, rồi sắp hết hạn sớm nhất) đứng trước — gọi lại
	`reports.canh_bao_han_rows()` cho từng kho rồi sắp xếp lại TOÀN CỤC theo
	`han_su_dung`: mỗi kho riêng đã tăng dần, gộp nhiều dãy tăng dần rồi sắp
	lại theo đúng khoá đó vẫn giữ nguyên bất biến "hết hạn trước, sắp hết hạn
	sau" trên toàn danh sách, không chỉ trong phạm vi một khách.

	Kể từ US-E4.8 (VĐ-2), `reports.canh_bao_han_rows()` còn trả về lô KHÔNG có
	hạn dùng với `han_su_dung=None` (nhóm "Không có hạn dùng", xem docstring ở
	đó) — khoá sắp xếp phải tự đẩy nhóm này xuống cuối, giống hệt cách hàm gốc
	tự sắp trong phạm vi MỘT kho, nếu không `sorted()` sẽ ném TypeError khi so
	sánh `None < datetime.date`."""
	khos = _active_khos(customer)
	names = _customer_names([k["customer"] for k in khos])

	out = []
	for k in khos:
		for row in reports.canh_bao_han_rows(k["name"], so_ngay=so_ngay):
			out.append({
				"customer": k["customer"],
				"customer_name": names.get(k["customer"]) or k["customer"],
				"kho": k["name"],
				"ten_kho": k["ten_kho"],
				**row,
			})
	# Sentinel của nhóm "không hạn" là `today` (một `datetime.date`), KHÔNG
	# phải chuỗi rỗng (M-4, review E4 phần B) — khớp đúng kiểu dữ liệu mà
	# `reports.canh_bao_han_rows()` tự dùng cho phép sắp xếp giống hệt của nó
	# (không mix kiểu `str`/`date` giữa hai nơi làm cùng một việc, dù cả hai
	# đều không sai — nhánh `is None` luôn chặn trước khi phần tử thứ hai của
	# khoá bị so sánh chéo kiểu).
	today = frappe.utils.getdate(frappe.utils.today())
	return sorted(
		out, key=lambda r: (r["han_su_dung"] is None, r["han_su_dung"] or today, r["so_lo"])
	)


# ------------------------------------------------------------------- E3 (Phần B)
# Hai report dưới đây KHÔNG gọi lại reports.py: nguồn dữ liệu là
# `Customer Stock Receipt`/`Item` (mốc đối soát BR-K16/BR-K17), không phải sổ
# kho — đúng loại số liệu khác với ba báo cáo N-X-T/tồn/hạn ở trên.

_TRANG_THAI_PHIEU = {0: "Nháp", 1: "Đã ghi sổ", 2: "Đã huỷ"}


def doi_soat_giao_nhan_rows(
	customer: str | None = None,
	chi_chenh_lech=False,
	qua_han_ngay=None,
) -> list[dict]:
	"""US-E3.5 (UC-48): một dòng cho mỗi DÒNG phiếu nhập có nguồn gốc Miyano
	(`sl_giao > 0` — cùng tiêu chí phân biệt với `_validate_doi_soat_giao_nhan`
	ở customer_stock_receipt.py, KHÔNG đoán theo `loai_nhap`).

	`chi_chenh_lech`: chỉ giữ dòng mà thực nhận khác SL giao (dùng EPS, không
	so bằng `==` với số thực).
	`qua_han_ngay`: chỉ giữ dòng thuộc phiếu CÒN NHÁP (`docstatus=0`) mà đã tạo
	quá N ngày — phiếu đã ghi sổ hay đã huỷ không tính "treo", nên bị loại
	khỏi bộ lọc này dù `qua_han_ngay` có được truyền hay không."""
	khos = _active_khos(customer)
	if not khos:
		return []
	kho_customer = {k["name"]: k["customer"] for k in khos}
	names = _customer_names([k["customer"] for k in khos])

	receipts = frappe.get_all(
		"Customer Stock Receipt",
		filters={"kho": ["in", list(kho_customer)], "docstatus": ["<", 2]},
		fields=["name", "kho", "docstatus", "delivery_note", "sales_order", "so_dot", "creation"],
	)
	if not receipts:
		return []
	receipt_by_name = {r["name"]: r for r in receipts}

	items = frappe.get_all(
		"Customer Stock Receipt Item",
		filters={"parent": ["in", list(receipt_by_name)], "sl_giao": [">", 0]},
		fields=["parent", "vat_tu", "ten_vat_tu", "so_luong", "sl_giao", "ly_do_chenh_lech"],
	)

	so_ngay_qua_han = frappe.utils.cint(qua_han_ngay) if qua_han_ngay not in (None, "") else None
	hom_nay = frappe.utils.getdate(frappe.utils.today())

	out = []
	for it in items:
		r = receipt_by_name.get(it["parent"])
		if not r:
			continue
		chenh = float(it["so_luong"] or 0) - float(it["sl_giao"] or 0)
		co_lech = abs(chenh) > EPS
		if chi_chenh_lech and not co_lech:
			continue
		if so_ngay_qua_han is not None:
			if int(r["docstatus"]) != 0:
				continue
			tuoi = frappe.utils.date_diff(hom_nay, frappe.utils.getdate(r["creation"]))
			if tuoi <= so_ngay_qua_han:
				continue
		customer_name_khach = names.get(kho_customer.get(r["kho"])) or kho_customer.get(r["kho"])
		out.append({
			"delivery_note": r.get("delivery_note"),
			"sales_order": r.get("sales_order"),
			"customer": kho_customer.get(r["kho"]),
			"customer_name": customer_name_khach,
			# so_dot lưu DB thành 0 khi "không xác định" (Int không nullable
			# — xem bàn giao Phần A), không phải "đợt 0". Trả None cho report
			# hiển thị ô trống thay vì con số 0 gây hiểu lầm.
			"so_dot": r.get("so_dot") or None,
			"ten_vat_tu": it.get("ten_vat_tu") or it.get("vat_tu"),
			"sl_giao": float(it.get("sl_giao") or 0),
			"so_luong": float(it.get("so_luong") or 0),
			"chenh": chenh,
			"ly_do_chenh_lech": it.get("ly_do_chenh_lech") or "",
			"phieu_nhap": r["name"],
			"trang_thai_phieu": _TRANG_THAI_PHIEU.get(int(r["docstatus"]), ""),
		})
	return sorted(out, key=lambda row: (row["customer_name"] or "", row["delivery_note"] or "", row["ten_vat_tu"] or ""))


def chat_luong_du_lieu_rows(customer: str | None = None, chi_chua_bat_co=True) -> list[dict]:
	"""US-E3.6: gộp theo Item (mặt hàng THẬT của Miyano, không phải theo
	`Customer Warehouse Item` — hai khách khác nhau có thể tự đặt trùng mã
	riêng của họ, nhưng `item_code` trỏ về đúng MỘT Item của Miyano) các dòng
	phiếu nhập từng rơi về `thieu_lo_han=1`, tức Item đó cần bật `Has Batch
	No`/`Has Expiry Date` phía Miyano (NL-3.7).

	Đếm TOÀN BỘ dòng lịch sử từng dính cờ này (không chỉ dòng "còn hiệu lực"
	— phiếu dù đã ghi sổ hay huỷ cũng đã là bằng chứng Item thiếu cấu hình
	lúc giao hàng), nhưng có kèm cờ `has_batch_no`/`has_expiry_date` HIỆN TẠI
	của Item để nhân viên thấy ngay cái nào đã được sửa, cái nào vẫn còn.

	`chi_chua_bat_co` (mặc định BẬT — đúng nghĩa đen của US-E3.6 "liệt kê
	item CẦN bật..."): ẩn Item mà Miyano đã bật CẢ HAI cờ sau khi phát hiện
	— dòng `thieu_lo_han` lịch sử của nó vẫn có thật (không xoá), nhưng nó
	không còn "cần" gì nữa nên không thuộc danh sách hành động này. Còn
	thiếu MỘT trong hai cờ vẫn coi là "cần", vì `thieu_lo_han` có thể tái
	diễn cho tới khi cả hai đều bật."""
	khos = _active_khos(customer)
	if not khos:
		return []
	kho_customer = {k["name"]: k["customer"] for k in khos}
	names = _customer_names([k["customer"] for k in khos])

	receipts = frappe.get_all(
		"Customer Stock Receipt",
		filters={"kho": ["in", list(kho_customer)], "docstatus": ["<", 2]},
		fields=["name", "kho", "ngay"],
	)
	if not receipts:
		return []
	receipt_by_name = {r["name"]: r for r in receipts}

	items = frappe.get_all(
		"Customer Stock Receipt Item",
		filters={"parent": ["in", list(receipt_by_name)], "thieu_lo_han": 1},
		fields=["parent", "vat_tu"],
	)
	if not items:
		return []

	vat_tu_names = list({it["vat_tu"] for it in items if it.get("vat_tu")})
	vt_info = {
		v["name"]: v for v in frappe.get_all(
			"Customer Warehouse Item",
			filters={"name": ["in", vat_tu_names]},
			fields=["name", "ma_vat_tu", "ten_vat_tu", "item_code"],
		)
	} if vat_tu_names else {}

	agg: dict[str, dict] = {}
	for it in items:
		r = receipt_by_name.get(it["parent"])
		if not r:
			continue
		vt = vt_info.get(it["vat_tu"]) or {}
		item_code = vt.get("item_code") or vt.get("ma_vat_tu") or it["vat_tu"]
		row = agg.setdefault(item_code, {
			"item_code": item_code,
			"ten_vat_tu": vt.get("ten_vat_tu") or "",
			"so_dong_thieu": 0,
			"khach_hang": set(),
			"lan_gan_nhat": None,
		})
		row["so_dong_thieu"] += 1
		kh = kho_customer.get(r["kho"])
		if kh:
			row["khach_hang"].add(kh)
		ngay = r.get("ngay")
		if ngay and (row["lan_gan_nhat"] is None or frappe.utils.getdate(ngay) > frappe.utils.getdate(row["lan_gan_nhat"])):
			row["lan_gan_nhat"] = ngay

	item_codes = list(agg)
	item_flags = {
		i["name"]: i for i in frappe.get_all(
			"Item", filters={"name": ["in", item_codes]},
			fields=["name", "item_name", "has_batch_no", "has_expiry_date"],
		)
	} if item_codes else {}

	out = []
	for item_code, row in agg.items():
		flags = item_flags.get(item_code) or {}
		has_batch_no = int(flags.get("has_batch_no") or 0)
		has_expiry_date = int(flags.get("has_expiry_date") or 0)
		if chi_chua_bat_co and has_batch_no and has_expiry_date:
			continue
		out.append({
			"item_code": item_code,
			"item_name": flags.get("item_name") or row["ten_vat_tu"],
			"has_batch_no": has_batch_no,
			"has_expiry_date": has_expiry_date,
			"so_dong_thieu": row["so_dong_thieu"],
			"so_khach_anh_huong": len(row["khach_hang"]),
			"lan_gan_nhat": row["lan_gan_nhat"],
		})
	return sorted(out, key=lambda r: (-r["so_dong_thieu"], r["item_code"]))
