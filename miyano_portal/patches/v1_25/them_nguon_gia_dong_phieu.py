"""Task 2 (2026-08-19, gộp luồng đặt hàng) — backfill `Portal De Xuat Mua
Item.nguon_gia`/`blanket_order` cho phiếu ĐÃ CÓ trước khi hai field này
xuất hiện.

Phiếu cũ đều THUẦN một loại (trước task này một phiếu chỉ có thể là "HĐNT"
hay "Mua lẻ" cho CẢ PHIẾU, gắn với ĐÚNG MỘT hợp đồng khung `hdnt` ở đầu
phiếu — chưa hề có khái niệm phiếu trộn hay dòng thuộc nhiều hợp đồng), nên
suy thẳng của MỌI dòng trong phiếu đó từ `loai_don`/`hdnt` cũ của CHÍNH
phiếu: "HĐNT" -> `nguon_gia="Hợp đồng"`, `blanket_order=hdnt` (dù `hdnt` có
thể rỗng nếu phiếu HĐNT đó chưa từng được đóng dấu giá); "Mua lẻ" ->
`nguon_gia="Chờ báo giá"`, `blanket_order` để rỗng (Ruling P14 — dòng "Chờ
báo giá" không gắn hợp đồng nào).

M3 (review vòng 1) — phiếu chưa từng khai `loai_don` (rỗng/NULL, dữ liệu
rác/thử nghiệm cũ) CŨNG mặc định `nguon_gia="Chờ báo giá"`, KHÔNG bỏ qua
như bản đầu: để `nguon_gia` NULL khiến `co_dong_cho_bao_gia()` (so sánh
chuỗi `== "Chờ báo giá"`) đọc nhầm phiếu đó thành "không có dòng chờ báo
giá" — sai theo hướng nguy hiểm hơn (trông như phiếu thuần hợp đồng) so
với việc mặc định an toàn về "chưa biết giá, cần báo giá".

KHÔNG chạy lại thuật toán "hợp đồng thắng cuộc" (`PortalDeXuatMua._nguon_
gia_theo_ma()`, Ruling P14) cho dữ liệu cũ — thuật toán đó xét MỌI hợp đồng
CÒN HIỆU LỰC của khách TẠI THỜI ĐIỂM CHẠY PATCH, một khái niệm phụ thuộc
thời gian không có ý nghĩa gì với một phiếu đã ĐÓNG BĂNG dữ liệu từ lúc gửi
duyệt/tạo đơn trong quá khứ. `hdnt` cũ của chính phiếu đó — hợp đồng phiếu
đó THẬT SỰ đã dùng — là nguồn sự thật đúng đắn duy nhất, không phải hợp
đồng nào "thắng cuộc" theo luật mới nếu tính lại hôm nay.

`loai_don` đã bị xoá khỏi `portal_de_xuat_mua.json` (cùng task) — xoá field
khỏi JSON KHÔNG tự ALTER TABLE DROP COLUMN (Custom Field/DocField không tự
dọn cột vật lý), nên cột `tabPortal De Xuat Mua`.`loai_don` mồ côi vẫn còn
trong DB nhưng `frappe.get_doc`/ORM không còn thấy nó qua field nào nữa.
Patch này vì vậy phải đọc THẲNG cột đó qua `frappe.db.sql`, không qua
`get_doc`/`get_all` (chúng lọc theo field hiện có trong meta, sẽ không trả
`loai_don` nữa). `hdnt` KHÔNG mồ côi — field đó vẫn còn trong doctype
(legacy, Ruling P14), nên đọc chung trong cùng câu SQL là an toàn.

Bọc trong kiểm tra cột tồn tại (`_co_cot_loai_don`) — site MỚI (cài app từ
đầu SAU khi field này đã bị xoá khỏi JSON nguồn) sẽ không bao giờ có cột
`loai_don`, và patch phải no-op AN TOÀN trên site đó, không ném lỗi "Unknown
column".
"""

import frappe


def execute():
	if not _co_cot_loai_don():
		return

	rows = frappe.db.sql(
		"select `name`, `loai_don`, `hdnt` from `tabPortal De Xuat Mua`", as_dict=True
	)
	for r in rows:
		if not r.loai_don:
			# M3 (review vòng 1) — SỬA: trước bản vá, phiếu chưa từng khai
			# `loai_don` (dữ liệu rác/thử nghiệm cũ) bị BỎ QUA, để lại
			# `nguon_gia = NULL` trên các dòng của nó. `co_dong_cho_bao_gia()`
			# đọc `nguon_gia == "Chờ báo giá"` bằng so sánh CHUỖI — `NULL`
			# không khớp so sánh đó, nên một phiếu rỗng dữ liệu bị đọc NHẦM
			# thành "không có dòng chờ báo giá" (an toàn giả — sai theo
			# hướng NGUY HIỂM hơn, vì nó khiến phiếu trông như thuần hợp
			# đồng trong khi thực ra không biết gì về nó). Mặc định về
			# "Chờ báo giá" AN TOÀN hơn: không đoán bừa phiếu này có hợp
			# đồng nào, và giữ nguyên hành vi cũ của những phiếu THẬT sự
			# "Mua lẻ" (đường `else` bên dưới).
			frappe.db.sql(
				"update `tabPortal De Xuat Mua Item` set nguon_gia=%s where parent=%s",
				("Chờ báo giá", r.name),
			)
			continue
		if r.loai_don == "HĐNT":
			frappe.db.sql(
				"update `tabPortal De Xuat Mua Item` set nguon_gia=%s, "
				"blanket_order=%s where parent=%s",
				("Hợp đồng", r.hdnt, r.name),
			)
		else:
			frappe.db.sql(
				"update `tabPortal De Xuat Mua Item` set nguon_gia=%s where parent=%s",
				("Chờ báo giá", r.name),
			)


def _co_cot_loai_don() -> bool:
	"""`SHOW COLUMNS` thay vì `information_schema` — không cần biết tên DB
	hiện hành, và trả rỗng (không ném lỗi) khi cột không còn, đúng thứ patch
	này cần để no-op an toàn trên site mới."""
	cot = frappe.db.sql(
		"show columns from `tabPortal De Xuat Mua` like 'loai_don'"
	)
	return bool(cot)
