"""US-E5.4 — job daily quét vật tư dưới min/ROP theo từng kho, gửi email
tổng hợp theo tần suất cấu hình TRÊN CHÍNH `Customer Warehouse`
(`canh_bao_ton_email_bat`/`canh_bao_ton_email_tan_suat` — "bật theo kho",
mặc định TẮT, đúng AC2 của US-E5.4).

"Ghi nhận... để hiển thị thẻ Dashboard 'Vật tư dưới mức tồn (n)'" (AC1)
KHÔNG cần một bảng cache riêng ở đây: `dutru.canh_bao_ton()` (endpoint
`kho_canh_bao_ton`) đã tính TRỰC TIẾP từ sổ kho + `Customer Warehouse Item`
mỗi lần gọi — đủ rẻ (bị giới hạn bởi một kho) để màn Dashboard portal gọi
SỐNG lấy `thieu + cham_rop` làm số "(n)", không có gì để job phải ghi xuống
DB trước rồi Dashboard đọc lại. Việc thật sự CẦN một job chạy đúng một lần
mỗi ngày là email digest: đó là thứ DUY NHẤT cần một trạng thái BỀN qua
nhiều lần chạy (tần suất "Hàng tuần" phải nhớ lần gửi trước, một lệnh gọi
API sống không tự có trạng thái đó).

Đăng ký ở `hooks.py::scheduler_events["daily"]`.
"""

import frappe

from miyano_portal.kho import dutru

TAN_SUAT_HANG_NGAY = "Hàng ngày"
TAN_SUAT_HANG_TUAN = "Hàng tuần"
_CHU_KY_NGAY = {TAN_SUAT_HANG_NGAY: 1, TAN_SUAT_HANG_TUAN: 7}
_TRANG_THAI_CANH_BAO = ("thieu", "sap_thieu")


def _email_khach_hang(customer: str) -> str | None:
	"""Cùng khuôn `portal_bao_gia._email_khach()` (ưu tiên Contact Email
	`is_primary`, rồi email đầu tiên tìm được) — khác chỗ tra thẳng từ
	`customer` vì job này không có sẵn một Sales Order để đọc
	`contact_email`."""
	parent = frappe.db.get_value(
		"Dynamic Link",
		{"parenttype": "Contact", "link_doctype": "Customer", "link_name": customer},
		"parent",
	)
	if not parent:
		return None
	return frappe.db.get_value(
		"Contact Email", {"parent": parent, "is_primary": 1}, "email_id"
	) or frappe.db.get_value("Contact Email", {"parent": parent}, "email_id")


def _den_han_gui(kho_row: dict, hom_nay) -> bool:
	"""Chưa từng gửi lần nào -> đến hạn ngay. Đã gửi rồi -> đủ `chu_ky_ngay`
	kể từ lần gửi trước mới đến hạn tiếp — đây là cơ chế chống spam cho tần
	suất "Hàng tuần"; "Hàng ngày" luôn có `chu_ky_ngay=1` nên mỗi lần job
	`daily` chạy (đúng một lần/ngày) đều qua được cổng này."""
	tan_suat = kho_row.get("canh_bao_ton_email_tan_suat") or TAN_SUAT_HANG_TUAN
	chu_ky = _CHU_KY_NGAY.get(tan_suat, 7)
	lan_cuoi = kho_row.get("canh_bao_ton_email_gui_lan_cuoi")
	if not lan_cuoi:
		return True
	return frappe.utils.date_diff(hom_nay, frappe.utils.getdate(lan_cuoi)) >= chu_ky


def _noi_dung_email(kho_row: dict, warned: list[dict]) -> str:
	nhan_trang_thai = {"thieu": "Thiếu", "sap_thieu": "Sắp thiếu"}
	dong = "".join(
		f"<tr><td>{frappe.utils.escape_html(r['ten'])}</td>"
		f"<td>{r['ton']:g}</td>"
		f"<td>{nhan_trang_thai.get(r['trang_thai'], r['trang_thai'])}</td></tr>"
		for r in warned
	)
	return (
		f"<p>Kho <b>{frappe.utils.escape_html(kho_row['ten_kho'])}</b> có "
		f"<b>{len(warned)}</b> vật tư dưới mức tồn tối thiểu/điểm đặt lại:</p>"
		f"<table border='1' cellpadding='4' style='border-collapse:collapse'>"
		f"<tr><th>Vật tư</th><th>Tồn</th><th>Trạng thái</th></tr>{dong}</table>"
		f"<p>Vui lòng vào cổng khách hàng để xem chi tiết và thêm vào giỏ bổ sung.</p>"
	)


def _gui_email_canh_bao(kho_row: dict, warned: list[dict]) -> None:
	"""Không bao giờ để lỗi gửi mail chặn việc cập nhật `gui_lan_cuoi` của
	KHO KHÁC trong cùng lượt quét — cùng nguyên tắc phòng thủ với
	`portal_bao_gia._gui_email_het_han()`/`portal_thong_bao.py`."""
	email = _email_khach_hang(kho_row["customer"])
	if not email:
		return
	try:
		frappe.sendmail(
			recipients=[email],
			subject=f"Cảnh báo thiếu tồn kho {kho_row['ten_kho']} ({len(warned)} vật tư)",
			message=_noi_dung_email(kho_row, warned),
			reference_doctype="Customer Warehouse",
			reference_name=kho_row["name"],
			now=False,
		)
	except Exception:
		frappe.log_error(
			title="portal_du_tru_job: gửi email cảnh báo tồn thất bại",
			message=frappe.get_traceback(),
		)


def quet_canh_bao_ton_daily(moc=None) -> int:
	"""Quét MỌI kho đã BẬT email cảnh báo (`canh_bao_ton_email_bat=1`,
	mặc định TẮT — US-E5.4 AC2), đến hạn theo tần suất, và CÓ vật tư dưới
	min/ROP — gửi một email tổng hợp mỗi kho, ghi lại `gui_lan_cuoi`. Trả số
	kho vừa gửi.

	Không gửi khi danh sách rỗng: một kho không có vật tư nào dưới mức
	không có gì để "tổng hợp", và gửi một email rỗng mỗi tuần chỉ dạy khách
	hàng bỏ qua email cảnh báo — đúng bài học đã ghi trong BR-P3 (kho/
	dutru.py) áp dụng cho kênh email."""
	hom_nay = frappe.utils.getdate(moc) if moc else frappe.utils.getdate(frappe.utils.today())
	khos = frappe.get_all(
		"Customer Warehouse",
		filters={"active": 1, "canh_bao_ton_email_bat": 1},
		fields=[
			"name", "customer", "ten_kho",
			"canh_bao_ton_email_tan_suat", "canh_bao_ton_email_gui_lan_cuoi",
		],
	)
	dem = 0
	for k in khos:
		if not _den_han_gui(k, hom_nay):
			continue
		rows = dutru.canh_bao_ton_rows(k["name"], k["customer"])
		warned = [r for r in rows if r["trang_thai"] in _TRANG_THAI_CANH_BAO]
		if not warned:
			continue
		_gui_email_canh_bao(k, warned)
		frappe.db.set_value(
			"Customer Warehouse", k["name"], "canh_bao_ton_email_gui_lan_cuoi",
			hom_nay, update_modified=False,
		)
		dem += 1
	return dem
