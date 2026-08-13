"""US-E6.6/UC-53 — số học cho report Desk "Demand pipeline yêu cầu hàng hoá".

Toàn bộ phép tính sống Ở ĐÂY; report .py (miyano_portal/report/demand_pipeline_
yêu_cầu_hàng_hoá/) chỉ khai cột/filter và gọi lại — theo đúng khuôn
kho/desk_reports.py (không viết lại phép tính lần thứ hai ở nơi khác).

Quyền hạn: hoàn toàn nằm ở Report doctype (ref_doctype=Portal Item Request,
roles=Sales Manager/Sales User/Purchase User, KHÔNG Customer — xem
setup/install_e6_desk_reports.py). `frappe.desk.query_report.run()` kiểm
`frappe.has_permission(ref_doctype, "report")` TRƯỚC khi execute() này được
gọi, nên các hàm dưới đây không tự kiểm quyền gì thêm — đúng khuôn các report
desk khác của app này.
"""

import frappe
from frappe.utils import get_datetime

# F-6 (review) — KHÔNG khai lại tuple này: bản gốc sống trong controller
# (portal_item_request.py), api/portal.py đã import từ đó cho NL-11.1; một
# bản sao thứ hai ở đây từng lệch âm thầm nếu ai đó thêm trạng thái kết thúc
# thứ năm mà quên sửa cả hai chỗ — mẫu số tỷ lệ chuyển đơn sẽ sai trong khi
# mọi test (dựng dict tay) vẫn xanh.
from miyano_portal.miyano_portal.doctype.portal_item_request.portal_item_request import (
	TRANG_THAI_KET_THUC,
)

TRANG_THAI_CHUYEN_DON = "Đã chuyển thành đơn"


def _customer_names(customers: list[str]) -> dict[str, str]:
	customers = list({c for c in customers if c})
	if not customers:
		return {}
	return dict(frappe.get_all(
		"Customer", filters={"name": ["in", customers]},
		fields=["name", "customer_name"], as_list=True,
	))


def _creation_filter(tu_ngay, den_ngay):
	if tu_ngay and den_ngay:
		return ["between", [f"{tu_ngay} 00:00:00", f"{den_ngay} 23:59:59"]]
	if tu_ngay:
		return [">=", f"{tu_ngay} 00:00:00"]
	if den_ngay:
		return ["<=", f"{den_ngay} 23:59:59"]
	return None


def yeu_cau_rows(
	customer: str | None = None,
	loai: str | None = None,
	tan_suat: str | None = None,
	trang_thai: str | None = None,
	tu_ngay: str | None = None,
	den_ngay: str | None = None,
) -> list[dict]:
	"""Một dòng mỗi `Portal Item Request`, đủ cột để Desk tự nhóm theo
	trạng thái/khách/nhóm bằng tính năng "Group By" sẵn có của Query Report —
	KHÔNG dựng sẵn bảng pivot ở server, vì "theo trạng thái/khách/nhóm" trong
	US-E6.6 là ba trục nhóm độc lập, không phải một tổ hợp cố định."""
	filters: dict = {}
	if customer:
		filters["customer"] = customer
	if loai:
		filters["loai"] = loai
	if tan_suat:
		filters["tan_suat"] = tan_suat
	if trang_thai:
		filters["trang_thai"] = trang_thai
	creation_filter = _creation_filter(tu_ngay, den_ngay)
	if creation_filter:
		filters["creation"] = creation_filter

	rows = frappe.get_all(
		"Portal Item Request",
		filters=filters,
		fields=[
			"name", "customer", "loai", "ten_hang", "tan_suat", "trang_thai",
			"creation", "modified", "don_lien_ket",
		],
		order_by="creation desc",
	)
	ten_khach = _customer_names([r.customer for r in rows])
	out = []
	for r in rows:
		d = dict(r)
		d["customer_name"] = ten_khach.get(d["customer"], d["customer"])
		ket_thuc = d["trang_thai"] in TRANG_THAI_KET_THUC
		d["ket_thuc"] = 1 if ket_thuc else 0
		d["da_chuyen_don"] = 1 if d["trang_thai"] == TRANG_THAI_CHUYEN_DON else 0
		if ket_thuc:
			# NỢ ĐÃ BIẾT (review, không sửa ở lần này): `modified` là mốc gần
			# đúng cho "lúc đóng", không phải mốc THẬT — một nhân viên sửa
			# ghi chú/field khác SAU KHI yêu cầu đã ở trạng thái kết thúc sẽ
			# thổi phồng con số này. Muốn đúng tuyệt đối cần một field riêng
			# ghi lại đúng lúc trang_thai đổi sang kết thúc (event log hoặc
			# cột `ket_thuc_luc`), ngoài phạm vi bản vá này. Cùng nợ với
			# "Đơn chậm xử lý" (patches/v1_4/tao_bao_cao_don_cham.py), vốn
			# cũng dùng timestampdiff trên mốc gần đúng cho mục đích tương tự.
			gio = (
				get_datetime(d["modified"]) - get_datetime(d["creation"])
			).total_seconds() / 3600.0
			d["thoi_gian_xu_ly_gio"] = round(gio, 1)
		else:
			d["thoi_gian_xu_ly_gio"] = None
		out.append(d)
	return out


def tom_tat(rows: list[dict]) -> dict:
	"""Tỷ lệ chuyển thành đơn = Đã chuyển thành đơn / tổng KẾT THÚC (US-E6.6).

	Mẫu số CHỈ gồm bốn trạng thái kết thúc (BR-Y4) — yêu cầu còn đang mở
	(Mới/Đang tìm nguồn/Cần thêm thông tin/Đã báo giá/Đã có hàng) không được
	tính vào mẫu, vì chúng chưa có kết quả để đánh giá.

	Nhóm `tan_suat == "Định kỳ"` (NL-11.7) TÁCH RIÊNG hoàn toàn khỏi nhóm
	"Một lần" — đầu vào cho quyết định đưa vào HĐNT kỳ tới, gộp chung sẽ pha
	loãng tín hiệu đó.
	"""
	def ty_le(tu, mau):
		return round(100.0 * tu / mau, 1) if mau else None

	ket_thuc = [r for r in rows if r["ket_thuc"]]
	chuyen_don = [r for r in ket_thuc if r["da_chuyen_don"]]
	dinh_ky = [r for r in rows if r["tan_suat"] == "Định kỳ"]
	dinh_ky_ket_thuc = [r for r in dinh_ky if r["ket_thuc"]]
	dinh_ky_chuyen_don = [r for r in dinh_ky_ket_thuc if r["da_chuyen_don"]]
	thoi_gian = [
		r["thoi_gian_xu_ly_gio"] for r in ket_thuc
		if r["thoi_gian_xu_ly_gio"] is not None
	]

	return {
		"tong": len(rows),
		"ket_thuc": len(ket_thuc),
		"chuyen_don": len(chuyen_don),
		"ty_le_chuyen_don": ty_le(len(chuyen_don), len(ket_thuc)),
		"thoi_gian_xu_ly_binh_quan_gio": (
			round(sum(thoi_gian) / len(thoi_gian), 1) if thoi_gian else None
		),
		"dinh_ky_tong": len(dinh_ky),
		"dinh_ky_ket_thuc": len(dinh_ky_ket_thuc),
		"dinh_ky_chuyen_don": len(dinh_ky_chuyen_don),
		"dinh_ky_ty_le_chuyen_don": ty_le(
			len(dinh_ky_chuyen_don), len(dinh_ky_ket_thuc)
		),
	}
