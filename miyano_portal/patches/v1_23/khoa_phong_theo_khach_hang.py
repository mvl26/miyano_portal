"""Điền `Customer Department.customer` từ `kho.customer`, và viết hoa `ma_khoa`.

Chạy MỘT LẦN cho mỗi site. Bản ghi nào không suy ra được khách hàng (kho đã
bị xoá) thì KHÔNG đoán — ghi Error Log để vận hành xử tay, vì đoán sai ở đây
là gán một khoa phòng cho nhầm bệnh viện.

VÒNG SỬA 1 (review): trước task này `ma_khoa` chỉ có luật "≤20 ký tự" — bản
patch gốc chỉ viết hoa mà KHÔNG xác thực theo luật MỚI của
`customer_department.py:_chuan_hoa_ma_khoa()` (chỉ A-Z0-9, không trùng trong
cùng bệnh viện sau khi chuẩn hoá, không phải mã dành riêng). `db.set_value`
bỏ qua validate() nên một mã vi phạm có thể nằm lì trong DB, chỉ lộ ra khi ai
đó sau này sửa một trường KHÁC của đúng bản ghi đó rồi bất ngờ dính lỗi
`ma_khoa` không liên quan gì tới việc họ đang làm.

Áp dụng đúng tinh thần "không đoán, ghi Error Log" của nhánh mồ côi ở trên
cho cả `ma_khoa`: mã KHÔNG hợp lệ (sai charset) hoặc TRÙNG nhau sau khi
chuẩn hoá trong cùng một bệnh viện thì GIỮ NGUYÊN, không sửa, không đoán ai
được giữ mã — chỉ ghi Error Log liệt kê rõ tên bản ghi + mã hiện tại. KHÔNG
ném lỗi: một `frappe.throw` giữa `bench migrate` biến vấn đề dữ liệu thành
sự cố triển khai, chặn đứng toàn bộ site. Mã hợp lệ vẫn được viết hoa như cũ.
"""

import frappe

# Trùng nguyên văn customer_department.py:CustomerDepartment.MA_DANH_RIENG —
# không import class doctype vào patch để tránh phụ thuộc ngoài ý muốn vào
# thời điểm nạp module trong lúc migrate; patch là kịch bản MỘT LẦN, chỉ cần
# khớp đúng luật tại THỜI ĐIỂM viết patch này, không cần tự động theo luật
# tương lai.
MA_DANH_RIENG = {"CHUNG"}


def _hop_le(ma: str) -> bool:
	return bool(ma) and len(ma) <= 20 and ma.isalnum() and ma.isascii() and ma not in MA_DANH_RIENG


def execute():
	rows = frappe.get_all(
		"Customer Department", fields=["name", "kho", "customer", "ma_khoa"]
	)

	# --- Bước 1: suy `customer` từ `kho.customer` (giữ nguyên logic gốc) ---
	mo_coi = []
	for r in rows:
		if r.customer:
			continue
		cust = frappe.db.get_value("Customer Warehouse", r.kho, "customer") if r.kho else None
		if not cust:
			mo_coi.append(r.name)
			continue
		r.customer = cust  # cập nhật in-memory để bước 2 nhóm trùng đúng bệnh viện
		frappe.db.set_value("Customer Department", r.name, "customer", cust, update_modified=False)

	if mo_coi:
		frappe.log_error(
			title="Khoa phòng không suy ra được khách hàng",
			message=(
				"Các khoa phòng sau không có `kho` hợp lệ để suy ra `customer`, "
				"cần gán tay: " + ", ".join(mo_coi)
			),
		)

	# --- Bước 2: viết hoa `ma_khoa` hợp lệ, ghi Error Log cho mã vi phạm ---
	# Bỏ qua bản ghi mồ côi ở bước 1: chưa có `customer` thì không có "trong
	# cùng bệnh viện" nào để so trùng — để dành xử cùng lúc với việc gán
	# `customer` tay.
	theo_khach_upper = {}
	vi_pham = []
	for r in rows:
		if r.name in mo_coi or not r.ma_khoa:
			continue
		upper = r.ma_khoa.strip().upper()
		if not _hop_le(upper):
			vi_pham.append(f'{r.name} (mã hiện tại: "{r.ma_khoa}")')
			continue
		theo_khach_upper.setdefault((r.customer, upper), []).append((r.name, r.ma_khoa))

	for (_, upper), ban_ghi in theo_khach_upper.items():
		if len(ban_ghi) > 1:
			# Trùng sau chuẩn hoá — KHÔNG tự chọn ai giữ mã, để vận hành xử tay.
			ten = ", ".join(f'{name} (mã hiện tại: "{ma}")' for name, ma in ban_ghi)
			vi_pham.append(f'trùng mã "{upper}" sau khi viết hoa giữa: {ten}')
			continue
		name, ma_cu = ban_ghi[0]
		if ma_cu != upper:
			frappe.db.set_value("Customer Department", name, "ma_khoa", upper, update_modified=False)

	if vi_pham:
		frappe.log_error(
			title="Mã khoa vi phạm luật mới sau khi chuẩn hoá",
			message=(
				"Các khoa phòng sau có `ma_khoa` không hợp lệ theo luật mới "
				"(chỉ A-Z0-9, ≤20 ký tự, không trùng trong cùng bệnh viện sau "
				"khi viết hoa, không phải mã dành riêng CHUNG) — cần sửa tay:\n"
				+ "\n".join(vi_pham)
			),
		)
