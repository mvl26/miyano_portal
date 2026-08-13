import frappe

TEN = "Miyano Portal Settings"


def execute():
	"""Seed mọi field CÓ `default` khai trong meta của Miyano Portal Settings
	xuống `tabSingles` một lần, để `get_single_value` không bao giờ âm thầm
	rơi về giá trị rỗng cho một site chưa từng mở form Settings ra lưu.

	Bối cảnh (C-1, review E4 phần B): `frappe.db.get_single_value` đọc THẲNG
	`tabSingles`, KHÔNG rơi về `default` khai trong DocType JSON khi field đó
	chưa từng được ghi xuống bảng — "chưa ai lưu form Settings" và "cố ý để
	trống" đọc ra giống hệt nhau (None/rỗng), dù ý nghĩa nghiệp vụ khác nhau
	(`nguong_duyet_2_tang` để trống CÓ CHỦ ĐÍCH = một tầng duyệt, BR-O9/VĐ-8;
	`nguong_cham_luan_chuyen_ngay` để trống là DO CHƯA CẤU HÌNH, phải hiểu là
	90). Hậu quả đo trực nghiệm trên `erptest.local`: một site mới cài app,
	chưa ai bấm Lưu ở màn Settings, có `tabSingles` rỗng cho tới field này —
	`bao_cao_dot_rows()` đọc ngưỡng ra 0, tắt câm lặng toàn bộ cờ "chậm luân
	chuyển" của US-E4.7 mà không một dấu hiệu lỗi nào.

	Diệt cả họ lỗi thay vì vá riêng một field: mọi field Currency/Int/Select…
	có `default` không rỗng trong DocType JSON nhưng CHƯA có dòng trong
	`tabSingles` đều được seed đúng giá trị default đó — bao gồm cả
	`so_ngay_adu`, `so_ngay_du_lieu_toi_thieu`, `sla_xu_ly_don_gio`,
	`sla_yeu_cau_gio`, `hieu_luc_bao_gia_ngay` mà E2/E5/E6 đang/sắp đọc qua
	cùng khuôn `get_single_value(...) or <default>` — tất cả cùng dính đúng
	bẫy này trên một site chưa từng cấu hình tay.

	Idempotent: chỉ seed field CHƯA có dòng trong `tabSingles` — chạy lại bao
	nhiêu lần cũng không ghi đè giá trị người dùng đã tự chỉnh. Field có
	`default` rỗng (`nguong_duyet_2_tang`) không có gì để seed, giữ nguyên ý
	nghĩa "để trống có chủ đích".
	"""
	if not frappe.db.exists("DocType", TEN):
		return

	meta = frappe.get_meta(TEN)
	da_co = frappe.db.get_singles_dict(TEN)

	for df in meta.fields:
		if df.fieldname in da_co:
			continue
		if df.default in (None, ""):
			continue
		frappe.db.set_single_value(TEN, df.fieldname, df.default)
