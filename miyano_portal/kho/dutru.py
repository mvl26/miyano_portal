"""E5 — Dự trù & vòng lặp Just-in-Time: ADU, ROP, gợi ý min/max, cảnh báo
thiếu tồn (BR-P1…P5, NL-9.1…9.5).

Vòng lặp (xem PRD E5 §Công thức chuẩn):

    ADU = tổng SL "Xuất sử dụng" đã ghi sổ trong kỳ trượt N ngày / N
      · N = Settings.so_ngay_adu (mặc định 90)
      · LOẠI TRỪ phiếu đảo và dòng da_dao = 1 (BR-P1, NL-9.4)
      · KHÔNG tính: Xuất huỷ, Xuất trả lại, Điều chỉnh kiểm kê
    ROP = ADU × lead_time_ngay + ton_toi_thieu                      (BR-P2)
    SL gợi ý đặt = ton_toi_da − tồn khả dụng, LÀM TRÒN LÊN theo boi_so_dat (BR-P4)
    Ngày phủ tồn = tồn khả dụng / ADU (1 lẻ thập phân; ADU=0 → "—")

QUAN TRỌNG — phân biệt HAI đường đọc min/ROP/max, cố ý không gộp làm một:

  * `kho_min_max_goi_y()` (US-E5.1 nút "Gợi ý từ tiêu thụ") TÍNH LẠI ROP từ
    ADU tươi + `ton_toi_thieu`/`lead_time_ngay` ĐANG LƯU trên vật tư — CHƯA
    LƯU gì, chỉ để khách xem trước khi tự bấm Lưu. `min`/`max` trong phản hồi
    là giá trị ĐANG LƯU, được ECHO lại nguyên văn — hệ thống không tự "sáng
    tác" một con số an toàn tồn kho nào cả (BR-P2: "khách chốt, hệ thống chỉ
    gợi ý ROP"). Vật tư chưa từng khai `ton_toi_thieu` thì `rop` trả `None`
    — không có tồn an toàn thì không có gì để cộng vào ADU×lead_time.
  * `kho_canh_bao_ton()` (US-E5.2, màn dự trù) đọc THẲNG `ton_toi_thieu`/
    `diem_dat_lai`/`ton_toi_da` đã LƯU trên `Customer Warehouse Item` để so
    với tồn hiện tại — KHÔNG tự ý dùng con số "gợi ý" thay cho giá trị khách
    chưa lưu, đúng nguyên tắc "giá trị hiệu lực là giá trị khách lưu".

Chuẩn hoá đầu vào (bẫy đã trả giá ở E6, review C-2, xem docstring
`api/portal.py::portal_order_place`): tên `Customer Warehouse Item` do CLIENT
gửi (tham số `vat_tu_list` của `kho_min_max_goi_y`) không bao giờ được so
bằng Python `set`/`==` — `vat_tu_list_cua_kho()` dưới đây xác nhận sở hữu
bằng ĐÚNG MỘT truy vấn `frappe.get_all(filters={"name": ["in", ...]})`, để
collation `utf8mb4_unicode_ci` của MariaDB tự xử lý khớp tên, không phải một
phép so sánh chuỗi Python song song có thể lệch kết quả.

"CHƯA KHAI" NGHĨA LÀ GÌ CHO MỘT FIELD SỐ — quyết định thiết kế đo trực
nghiệm, không phải giả định: `ton_toi_thieu`/`diem_dat_lai`/`ton_toi_da`/
`boi_so_dat` là Float/Int trên MỘT DOCTYPE THƯỜNG (không phải Single), và cột
DB tương ứng luôn `NOT NULL DEFAULT 0` (`SHOW COLUMNS` xác nhận:
`decimal(21,9) NO ... 0.000000000` — hành vi CHUẨN của Frappe cho MỌI field
kiểu số, không có cách khai báo nào tắt được). Khác với
`Miyano Portal Settings.nguong_cham_luan_chuyen_ngay` (Single field —
`tabSingles` đơn giản KHÔNG CÓ dòng khi field chưa từng lưu, phân biệt được
"chưa cấu hình" với "lưu giá trị 0" — xem `reports.py::_nguong_cham_luan_
chuyen()`), MỘT DÒNG của `Customer Warehouse Item` LUÔN có sẵn cả bốn cột này
với giá trị 0 ngay từ lúc insert, dù người dùng chưa từng chạm vào ô nào —
không có "dòng vắng mặt" nào để phân biệt. Vì vậy `chua_khai()` coi 0 (và
None/"" ở tầng payload trước khi lưu) là "CHƯA KHAI" cho cả bốn trường —
đánh đổi đã biết và chấp nhận: một khách hàng thật sự muốn "0 tồn an toàn/
0 điểm đặt lại" (rất hiếm với vật tư y tế đang JIT hoá) sẽ đọc y hệt "chưa
khai". `ton_toi_da = 0` (max = 0) thì KHÔNG có đánh đổi nào — không ai đặt
mục tiêu tồn tối đa bằng 0 trong khi vẫn quản vật tư đó, nên hai nghĩa trùng
khít."""

import math

import frappe

from miyano_portal.kho import ledger, reports
from miyano_portal.kho.ledger import EPS
from miyano_portal.portal_mua_le import items_thuoc_hdnt_hieu_luc

LOAI_XUAT_SU_DUNG = "Xuất sử dụng"

_SO_NGAY_ADU_MAC_DINH = 90
_SO_NGAY_DU_LIEU_TOI_THIEU_MAC_DINH = 30
_ADU_30_CO_DINH = 30  # cửa sổ ADU30 CỐ ĐỊNH (NL-9.2, chỉ để đối chiếu, không dùng trong công thức nào)

# Thứ tự ưu tiên hiển thị/lọc — "thiếu" cấp bách nhất, "on_dinh" cuối cùng.
_MUC_DO_NGHIEM_TRONG = {"thieu": 0, "sap_thieu": 1, "chua_thiet_lap": 2, "on_dinh": 3}

_TRANG_KHO_CANH_BAO_TON = 50  # cùng cỡ trang với nhat_ky_rows() (reports.py)


def chua_khai(gia_tri) -> bool:
	"""True nếu `gia_tri` nên coi là "chưa khai" — None/rỗng (payload trước
	khi lưu) HOẶC 0 (giá trị THẬT SỰ đọc lại từ cột DB `NOT NULL DEFAULT 0`,
	xem docstring đầu file cho lý do không có lựa chọn nào khác)."""
	if gia_tri in (None, ""):
		return True
	return abs(float(gia_tri)) < EPS


def _settings_int(fieldname: str, mac_dinh: int) -> int:
	"""Đọc một field Int của `Miyano Portal Settings` KHÔNG qua
	`get_single_value` — hàm đó ép giá trị qua `cast_fieldtype()`
	(`cint(None) == 0`), nên "chưa từng lưu" và "lưu giá trị 0" ra CÙNG MỘT
	SỐ, không phân biệt được (C-1, review E4 phần B — xem docstring đầy đủ ở
	`reports.py::_nguong_cham_luan_chuyen()`, bẫy hệt vậy áp cho `so_ngay_adu`/
	`so_ngay_du_lieu_toi_thieu`). `get_singles_dict(cast=False)` (mặc định)
	trả dict THÔ, field chưa từng có dòng trong `tabSingles` đơn giản KHÔNG
	CÓ MẶT — phân biệt được với "có dòng, giá trị chuỗi rỗng/0".

	Phòng thủ hai lớp: patch `v1_6.seed_portal_settings_defaults` đã seed cả
	hai field này xuống `tabSingles` khi migrate; hàm này vẫn tự rơi về
	`mac_dinh` cho site/DB chưa từng chạy patch đó."""
	raw = frappe.db.get_singles_dict("Miyano Portal Settings").get(fieldname)
	if raw in (None, ""):
		return mac_dinh
	return frappe.utils.cint(raw)


def so_ngay_adu() -> int:
	return _settings_int("so_ngay_adu", _SO_NGAY_ADU_MAC_DINH)


def so_ngay_du_lieu_toi_thieu() -> int:
	return _settings_int("so_ngay_du_lieu_toi_thieu", _SO_NGAY_DU_LIEU_TOI_THIEU_MAC_DINH)


def _xuat_su_dung_issue_names(kho: str) -> list[str]:
	"""Tên các phiếu Xuất SỬ DỤNG (loai_xuat="Xuất sử dụng") của một kho —
	KHÔNG bao gồm "Xuất huỷ - hết hạn"/"Xuất trả lại"/"Điều chỉnh kiểm kê"
	(BR-P1/NL-9.4: những loại đó không phải tiêu thụ) và KHÔNG bao gồm
	"Phiếu đảo" (đó là bút toán bù trừ tự động, không phải một lượt xuất
	thật — cùng nguyên tắc `LOAI_DAO` dùng khắp `kho/voucher.py`)."""
	return frappe.get_all(
		"Customer Stock Issue",
		filters={"kho": kho, "loai_xuat": LOAI_XUAT_SU_DUNG},
		pluck="name",
	)


def _du_lieu_tieu_thu(kho: str, vat_tu: str) -> list[dict]:
	"""MỘT lượt quét sổ cho MỌI dòng "Xuất sử dụng" hợp lệ của một vật tư —
	dùng chung cho cả ADU30, ADU (kỳ N), và số ngày dữ liệu (BR-P1): không
	quét sổ ba lần cho ba con số cùng một nguồn, đúng khuôn `nxt_data()` của
	`reports.py`.

	`da_dao=0` loại dòng GỐC đã bị đảo (huỷ) — dòng ĐẢO (bù trừ, dương) của
	nó nằm trên MỘT phiếu "Phiếu đảo" riêng, đã bị loại ở
	`_xuat_su_dung_issue_names()` qua điều kiện `loai_xuat`. Hai điều kiện
	này cùng nhau loại trừ TRỌN VẸN một cặp huỷ (dòng gốc VÀ dòng bù trừ),
	đúng yêu cầu DoD "một phiếu xuất huỷ và một phiếu đảo lẫn vào dữ liệu".
	"""
	issue_names = _xuat_su_dung_issue_names(kho)
	if not issue_names:
		return []
	return frappe.get_all(
		"Customer Stock Ledger Entry",
		filters={
			"kho": kho, "vat_tu": vat_tu,
			"chung_tu_type": "Customer Stock Issue",
			"chung_tu": ["in", issue_names],
			"da_dao": 0,
		},
		fields=["ngay", "so_luong"],
	)


def _tong_trong_ky(entries: list[dict], tu: "frappe.utils.getdate", den: "frappe.utils.getdate") -> float:
	tong = 0.0
	for e in entries:
		ngay = frappe.utils.getdate(e["ngay"])
		if tu <= ngay <= den:
			tong += -float(e["so_luong"])  # so_luong âm cho dòng xuất
	return tong


TIEU_THU_RONG = {"adu_30": 0.0, "adu_90": 0.0, "so_ngay_du_lieu": 0}


def _tinh_tieu_thu_tu_entries(entries: list[dict], hom_nay=None) -> dict:
	"""Lõi thuần tính toán của `tinh_tieu_thu()`/`tieu_thu_theo_kho()` — nhận
	sẵn danh sách dòng sổ (đã quét), KHÔNG tự truy vấn DB, để hai nơi gọi
	(một vật tư, cả kho) dùng chung ĐÚNG MỘT công thức mà không viết lại lần
	thứ hai. Xem `tinh_tieu_thu()` cho ý nghĩa từng con số."""
	hom_nay = hom_nay or frappe.utils.getdate(frappe.utils.today())
	n = so_ngay_adu()
	tu_30 = frappe.utils.add_days(hom_nay, -(_ADU_30_CO_DINH - 1))
	tu_n = frappe.utils.add_days(hom_nay, -(n - 1))
	adu_30 = round(_tong_trong_ky(entries, tu_30, hom_nay) / _ADU_30_CO_DINH, 6)
	adu_n = round(_tong_trong_ky(entries, tu_n, hom_nay) / n, 6)

	if entries:
		ngay_dau = min(frappe.utils.getdate(e["ngay"]) for e in entries)
		so_ngay_du_lieu = (hom_nay - ngay_dau).days + 1
	else:
		so_ngay_du_lieu = 0

	return {"adu_30": adu_30, "adu_90": adu_n, "so_ngay_du_lieu": so_ngay_du_lieu}


def tinh_tieu_thu(kho: str, vat_tu: str) -> dict:
	"""ADU30 (đối chiếu, NL-9.2), ADU kỳ N=so_ngay_adu() (dùng cho ROP/ngày
	phủ, BR-P2), và số ngày dữ liệu đã ghi nhận (BR-P3/NL-9.1) cho MỘT vật
	tư — MỘT lần quét sổ (`_du_lieu_tieu_thu()`), ba con số dẫn xuất.

	`so_ngay_du_lieu`: số ngày từ lần "Xuất sử dụng" ĐẦU TIÊN từng ghi (loại
	trừ dòng đã bị đảo) tới hôm nay, TÍNH CẢ HAI ĐẦU — 0 nếu chưa từng có
	dòng nào. Đây là "đã quan sát được bao lâu", không phải "có bao nhiêu
	dòng sổ": một vật tư chỉ xuất một lần duy nhất 91 ngày trước vẫn được
	coi là đủ dữ liệu, một vật tư xuất mười lần trong ba ngày qua thì chưa.

	Dùng cho `kho_min_max_goi_y()` (danh sách vật tư CLIENT TỰ CHỌN, thường
	vài dòng) — quét MỘT vật tư mỗi lần gọi là đủ rẻ. Với các hàm quét TOÀN
	KHO (`canh_bao_ton_rows()`/`desk_reports.tieu_thu_de_xuat_rows()`), dùng
	`tieu_thu_theo_kho()` bên dưới thay vì gọi hàm này trong một vòng lặp —
	xem docstring hàm đó cho lý do (N+1 truy vấn)."""
	return _tinh_tieu_thu_tu_entries(_du_lieu_tieu_thu(kho, vat_tu))


def tieu_thu_theo_kho(kho: str) -> dict[str, dict]:
	"""Bản GỘP của `tinh_tieu_thu()` cho MỌI vật tư của một kho trong ĐÚNG
	HAI truy vấn (danh sách phiếu Xuất sử dụng + toàn bộ dòng sổ của chúng),
	thay vì hai truy vấn CHO MỖI VẬT TƯ.

	Lý do tồn tại (round review — advisor): `canh_bao_ton_rows()` và
	`desk_reports.tieu_thu_de_xuat_rows()` đều lặp qua MỌI vật tư đang dùng
	của (các) kho rồi gọi `tinh_tieu_thu()` — với một kho vài năm dữ liệu,
	đó là N+1 truy vấn, và với report Desk (lặp qua MỌI kho × MỌI vật tư)
	đó là trường hợp XẤU NHẤT, không phải màn portal (một kho). Phân trang
	server của `canh_bao_ton()` KHÔNG cắt được chi phí này vì nó cắt SAU khi
	`canh_bao_ton_rows()` đã tính xong toàn bộ.

	Trả `{vat_tu: {...}}` — vật tư CHƯA TỪNG có dòng "Xuất sử dụng" nào đơn
	giản KHÔNG có mặt trong dict (không phải một dict rỗng tốn bộ nhớ cho
	hàng nghìn vật tư chưa từng xuất); nơi gọi tự rơi về `TIEU_THU_RONG`
	khi tra `dict.get(vat_tu)` không thấy — xem `canh_bao_ton_rows()`."""
	issue_names = _xuat_su_dung_issue_names(kho)
	if not issue_names:
		return {}
	entries = frappe.get_all(
		"Customer Stock Ledger Entry",
		filters={
			"kho": kho, "chung_tu_type": "Customer Stock Issue",
			"chung_tu": ["in", issue_names], "da_dao": 0,
		},
		fields=["vat_tu", "ngay", "so_luong"],
	)
	theo_vat_tu: dict[str, list[dict]] = {}
	for e in entries:
		theo_vat_tu.setdefault(e["vat_tu"], []).append(e)

	hom_nay = frappe.utils.getdate(frappe.utils.today())
	return {vt: _tinh_tieu_thu_tu_entries(es, hom_nay) for vt, es in theo_vat_tu.items()}


def ton_kha_dung(kho: str, vat_tu: str) -> float:
	"""Tổng tồn CÒN LẠI của một vật tư, cộng qua mọi lô — dùng lại
	`ledger.get_lot_balances()` (cache tồn theo lô đã có), không viết lại
	phép cộng lần thứ hai (đã có ở mức CẢ KHO trong
	`reports.ton_hien_tai_rows()`, nhưng hàm đó gộp nhiều vật tư một lúc còn
	ở đây chỉ cần MỘT vật tư nên gọi thẳng lô, giống cách
	`customer_stock_issue.py::_chan_xuat_qua_ton()` đã làm).

	Dùng cho vật tư ĐƠN LẺ; quét cả kho dùng `ton_kha_dung_theo_kho()`."""
	lots = ledger.get_lot_balances(kho, vat_tu)
	return round(sum(float(l["so_luong"]) for l in lots), 6)


def ton_kha_dung_theo_kho(kho: str) -> dict[str, float]:
	"""Bản GỘP của `ton_kha_dung()` cho MỌI vật tư — gọi lại
	`reports.ton_hien_tai_rows()` (đã MỘT truy vấn `Customer Stock Lot
	Balance` cho cả kho, gộp theo lô), không viết lại phép cộng lần thứ ba
	(lần thứ nhất ở `reports.ton_hien_tai_rows()`, lần thứ hai ở
	`ton_kha_dung()` cho một vật tư).

	`ton_hien_tai_rows()` chỉ trả vật tư CÓ tồn dương (`so_luong > EPS`) —
	vật tư đã hết sạch (tồn = 0, chính là ca "Thiếu" cấp bách nhất) hay chưa
	từng nhập không có mặt trong dict trả về. Nơi gọi PHẢI tự rơi về `0.0`
	khi tra không thấy (`dict.get(vat_tu, 0.0)`) — đây KHÔNG phải một khác
	biệt hành vi so với `ton_kha_dung()` (hàm đó cũng trả đúng 0.0 cho một
	vật tư không lô nào), chỉ là cách biểu diễn "0" khác nhau (dòng số 0 vs.
	dict không có khoá)."""
	return {r["vat_tu"]: float(r["so_luong"]) for r in reports.ton_hien_tai_rows(kho)}


def tinh_rop(adu_n, lead_time_ngay, ton_toi_thieu) -> float | None:
	"""BR-P2: ROP = ADU × lead_time_ngay + ton_toi_thieu. `None` nếu thiếu
	`lead_time_ngay` HOẶC `ton_toi_thieu` (`chua_khai()` — xem docstring đầu
	file) — không có tồn an toàn/lead time thì không có gì để cộng, không
	suy diễn một con số thay khách."""
	if chua_khai(lead_time_ngay) or chua_khai(ton_toi_thieu):
		return None
	return round(float(adu_n or 0) * float(lead_time_ngay) + float(ton_toi_thieu), 6)


def ngay_phu_ton(ton, adu_n):
	"""Ngày phủ tồn = tồn khả dụng / ADU (kỳ N), 1 lẻ thập phân. `adu_n<=0`
	(bằng 0 hoặc do dữ liệu âm bất thường) → "—" (không chia được/vô nghĩa)."""
	if not adu_n or float(adu_n) <= EPS:
		return "—"
	return round(float(ton) / float(adu_n), 1)


def sl_goi_y_dat(ton_toi_da, ton, boi_so_dat) -> float | None:
	"""BR-P4: SL gợi ý = ton_toi_da − tồn khả dụng, làm tròn LÊN theo
	`boi_so_dat`. `None` nếu chưa khai `ton_toi_da` (không có gì để gợi ý).
	Đã đạt/vượt max → 0 (không cần đặt thêm), không phải một số âm."""
	if chua_khai(ton_toi_da):
		return None
	thieu = float(ton_toi_da) - float(ton)
	if thieu <= EPS:
		return 0.0
	boi = float(boi_so_dat) if not chua_khai(boi_so_dat) else None
	if not boi:
		return round(thieu, 6)
	# trừ EPS trước khi ceil để rác dấu phẩy động (38.0000000001/10) không bị
	# đẩy lên bội số kế tiếp một cách sai lệch.
	so_boi = math.ceil(thieu / boi - EPS)
	return round(so_boi * boi, 6)


def goi_y_mot_vat_tu(kho: str, row: dict) -> dict:
	"""Lõi của `kho_min_max_goi_y()` (US-E5.1) cho MỘT vật tư đã xác nhận
	thuộc kho — xem docstring đầu file cho lý do `min`/`max` chỉ ECHO, không
	tự tính. `row` cần các khoá: name, ton_toi_thieu, ton_toi_da,
	lead_time_ngay."""
	tt = tinh_tieu_thu(kho, row["name"])
	if tt["so_ngay_du_lieu"] < so_ngay_du_lieu_toi_thieu():
		# NL-9.1 — chưa đủ dữ liệu: không điền số nào, kể cả ADU.
		return {"du_lieu": False}
	rop = tinh_rop(tt["adu_90"], row.get("lead_time_ngay"), row.get("ton_toi_thieu"))
	return {
		"adu_90": tt["adu_90"],
		"min": None if chua_khai(row.get("ton_toi_thieu")) else row.get("ton_toi_thieu"),
		"rop": rop,
		"max": None if chua_khai(row.get("ton_toi_da")) else row.get("ton_toi_da"),
	}


def vat_tu_list_cua_kho(vat_tu_list: list[str], kho: str) -> list[dict]:
	"""Xác nhận MỘT LOẠT vật tư do client gửi (`kho_min_max_goi_y`) đều thuộc
	kho người gọi, qua ĐÚNG MỘT truy vấn `frappe.get_all(filters={"name": ["in",
	...], "kho": kho})` — để MariaDB (collation `utf8mb4_unicode_ci` của
	`tabCustomer Warehouse Item`) tự xử lý khớp tên, không so sánh Python
	`set`/`==` (bẫy đã trả giá ở E6, review C-2 — xem docstring đầu file).

	Fail-loud, cùng triết lý với `_vat_tu_cua_kho()`/`kho_bao_cao_dot()` của
	`api/kho.py`: một tên không khớp ĐÚNG một dòng thuộc kho này (không tồn
	tại, hoặc thuộc kho khác) làm CẢ YÊU CẦU bị từ chối, không lặng lẽ bỏ
	qua — im lặng bỏ một vật tư "lạ" ra khỏi phản hồi dễ bị đọc nhầm thành
	"vật tư đó chưa đủ dữ liệu" thay vì "bạn không có quyền xem nó"."""
	names = list(dict.fromkeys(v for v in (vat_tu_list or []) if v))
	if not names:
		return []
	rows = frappe.get_all(
		"Customer Warehouse Item",
		filters={"name": ["in", names], "kho": kho},
		fields=["name", "item_code", "ton_toi_thieu", "diem_dat_lai", "ton_toi_da", "lead_time_ngay", "boi_so_dat"],
	)
	if len(rows) != len(names):
		raise frappe.PermissionError("Có vật tư không thuộc kho của đơn vị bạn.")
	return rows


def min_max_goi_y(kho: str, vat_tu_list: list[str]) -> dict:
	rows = vat_tu_list_cua_kho(vat_tu_list, kho)
	return {row["name"]: goi_y_mot_vat_tu(kho, row) for row in rows}


def _trang_thai_dong(ton: float, min_, rop, co_nguong: bool) -> str:
	"""Suy trạng thái MỘT dòng cảnh báo tồn (US-E5.2):

	  * `co_nguong` False (chưa khai cả min lẫn ROP, nhưng lọt qua BR-P3 vì
	    ĐÃ đủ ≥30 ngày dữ liệu — xem `canh_bao_ton_rows()`) → "chua_thiet_lap".
	  * `min` đã khai VÀ tồn < min → "thieu" (đỏ).
	  * `rop` đã khai VÀ tồn < rop → "sap_thieu".
	  * Còn lại → "on_dinh".

	Kiểm `min` trước `rop` vì "Thiếu" là trạng thái NGHIÊM TRỌNG HƠN — một
	vật tư vừa dưới min vừa dưới rop (luôn đúng vì min ≤ rop khi cả hai đã
	lưu, do validate ở CustomerWarehouseItem) phải hiện "Thiếu", không phải
	"Sắp thiếu"."""
	if not co_nguong:
		return "chua_thiet_lap"
	if min_ not in (None, "") and ton < float(min_) - EPS:
		return "thieu"
	if rop not in (None, "") and ton < float(rop) - EPS:
		return "sap_thieu"
	return "on_dinh"


def canh_bao_ton_rows(kho: str, customer: str) -> list[dict]:
	"""Lõi của `kho_canh_bao_ton()` (US-E5.2) — MỌI vật tư ĐANG DÙNG
	(`active=1`) của một kho, đã áp BR-P3 (loại vật tư chưa khai min/ROP VÀ
	chưa đủ dữ liệu — không cảnh báo trên dữ liệu không đáng tin) và gắn kèm
	dữ liệu US-E5.3 (`dat_duoc_hdnt`, `sl_goi_y`) để màn giao diện quyết
	định hiện nút nào mà không phải gọi thêm API.

	Không phân trang ở đây — `canh_bao_ton()` bên dưới phân trang SAU KHI đã
	sắp xếp theo mức độ nghiêm trọng, để trang 1 luôn là những vật tư cần
	hành động trước, không phải một lát cắt ngẫu nhiên theo tên."""
	items = frappe.get_all(
		"Customer Warehouse Item",
		filters={"kho": kho, "active": 1},
		fields=["name", "ten_vat_tu", "dvt", "quy_cach", "item_code",
		        "ton_toi_thieu", "diem_dat_lai", "ton_toi_da", "boi_so_dat"],
	)
	if not items:
		return []

	thuoc_hdnt = items_thuoc_hdnt_hieu_luc(customer)
	nguong_du_lieu = so_ngay_du_lieu_toi_thieu()
	# MỘT lượt tính cho CẢ KHO (hai truy vấn) thay vì một cặp truy vấn cho
	# MỖI vật tư — xem docstring `tieu_thu_theo_kho()`/`ton_kha_dung_theo_kho()`
	# (round review — advisor: N+1 trên kho nhiều năm dữ liệu).
	tieu_thu_ca_kho = tieu_thu_theo_kho(kho)
	ton_ca_kho = ton_kha_dung_theo_kho(kho)

	out = []
	for it in items:
		min_ = None if chua_khai(it["ton_toi_thieu"]) else it["ton_toi_thieu"]
		rop = None if chua_khai(it["diem_dat_lai"]) else it["diem_dat_lai"]
		max_ = None if chua_khai(it["ton_toi_da"]) else it["ton_toi_da"]
		co_nguong = min_ is not None or rop is not None

		tt = tieu_thu_ca_kho.get(it["name"], TIEU_THU_RONG)
		if not co_nguong and tt["so_ngay_du_lieu"] < nguong_du_lieu:
			continue  # BR-P3 — chưa thiết lập VÀ chưa đủ dữ liệu: không cảnh báo.

		ton = ton_ca_kho.get(it["name"], 0.0)
		trang_thai = _trang_thai_dong(ton, min_, rop, co_nguong)
		item_code = it["item_code"] or ""
		out.append({
			"vat_tu": it["name"], "ten": it["ten_vat_tu"], "dvt": it["dvt"],
			"quy_cach": it["quy_cach"] or "", "item_code": item_code,
			"ton": ton, "adu_30": tt["adu_30"], "adu_90": tt["adu_90"],
			"ngay_phu": ngay_phu_ton(ton, tt["adu_90"]),
			"min": float(min_) if min_ is not None else None,
			"rop": float(rop) if rop is not None else None,
			"max": float(max_) if max_ is not None else None,
			"trang_thai": trang_thai,
			"sl_goi_y": sl_goi_y_dat(max_, ton, it["boi_so_dat"]),
			# US-E5.3 — nút nào hiện do CHÍNH màn giao diện quyết định dựa
			# trên cờ này, không lặp lại tra cứu items_thuoc_hdnt_hieu_luc()
			# một lần nữa ở tầng UI.
			"dat_duoc_hdnt": bool(item_code) and item_code in thuoc_hdnt,
		})

	return sorted(out, key=lambda r: (_MUC_DO_NGHIEM_TRONG.get(r["trang_thai"], 9), r["ten"]))


def canh_bao_ton(kho: str, customer: str, trang_thai: str | None = None, trang: int = 1) -> dict:
	"""Bọc phân trang + ba thẻ đếm quanh `canh_bao_ton_rows()` (DoD: phân
	trang phía server). Ba thẻ đếm LUÔN phản ánh TOÀN BỘ danh sách (trước
	khi lọc theo `trang_thai`) — bấm một thẻ để lọc bảng không được làm hai
	thẻ còn lại đổi số, nếu không người dùng sẽ không tin được các con số
	đang thấy."""
	rows = canh_bao_ton_rows(kho, customer)
	thieu = sum(1 for r in rows if r["trang_thai"] == "thieu")
	cham_rop = sum(1 for r in rows if r["trang_thai"] == "sap_thieu")
	chua_thiet_lap = sum(1 for r in rows if r["trang_thai"] == "chua_thiet_lap")

	if trang_thai:
		rows = [r for r in rows if r["trang_thai"] == trang_thai]

	trang = max(1, int(trang or 1))
	start = (trang - 1) * _TRANG_KHO_CANH_BAO_TON
	return {
		"thieu": thieu, "cham_rop": cham_rop, "chua_thiet_lap": chua_thiet_lap,
		"tong_dong": len(rows), "trang": trang, "so_dong_moi_trang": _TRANG_KHO_CANH_BAO_TON,
		"dong": rows[start:start + _TRANG_KHO_CANH_BAO_TON],
	}
