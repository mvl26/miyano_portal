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
	sau" trên toàn danh sách, không chỉ trong phạm vi một khách."""
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
	return sorted(out, key=lambda r: (r["han_su_dung"], r["so_lo"]))
