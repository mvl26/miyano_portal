"""Báo cáo kho khách hàng: Nhập-Xuất-Tồn, thẻ kho, cảnh báo hạn dùng.

Tính trực tiếp từ `Customer Stock Ledger Entry` — nguồn sự thật duy nhất.
KHÔNG dùng `Customer Stock Lot Balance` cho hai báo cáo N-X-T và thẻ kho: đó
chỉ là cache TỒN HIỆN TẠI, không trả lời được câu hỏi lịch sử ("tồn đầu kỳ
ngày X là bao nhiêu"). Cache chỉ đúng vai cho cảnh báo hạn dùng — một câu hỏi
VỀ HIỆN TẠI ("lô nào đang tồn và sắp hết hạn"), nơi nó nhất quán với kho_ton().

Một bộ cột (COLUMNS) cho mỗi loại báo cáo, dùng CHUNG cho JSON trả về portal
và cho xuất Excel — theo round-tripping-spreadsheets: màn hình và file xuất
không được lệch cột. Nhãn cột ở đây PHẢI khớp từng chữ với mảng tương ứng
trong `frontend/src/kho-bao-cao-columns.js` — test_kho_reports.py khẳng định
điều đó bằng cách đọc lại chính file .js.

Dòng sổ có `da_dao=1` KHÔNG bị lọc bỏ khỏi bất kỳ tổng nào ở đây: đó là dòng
gốc đã bị đảo, còn dòng đảo (âm, chứng từ riêng, ngày = ngày huỷ) là một dòng
sổ khác, hoàn toàn hợp lệ và phải được cộng vào đúng kỳ của NÓ. Lọc theo
`da_dao` sẽ làm dòng gốc "biến mất" khỏi kỳ nó được ghi trong khi dòng đảo vẫn
còn, phá vỡ hằng đẳng thức tồn đầu + nhập − xuất = tồn cuối ngay lập tức.
"""

import io

import frappe
from openpyxl import Workbook
from openpyxl.utils import get_column_letter
from openpyxl.styles import Font

from miyano_portal.kho import ledger

EPS = ledger.EPS

NXT_COLUMNS = [
	("Mã vật tư", "ma_vat_tu"),
	("Tên vật tư", "ten_vat_tu"),
	("ĐVT", "dvt"),
	("Tồn đầu - SL", "ton_dau_sl"),
	("Tồn đầu - Thành tiền", "ton_dau_tt"),
	("Nhập - SL", "nhap_sl"),
	("Nhập - Thành tiền", "nhap_tt"),
	("Xuất - SL", "xuat_sl"),
	("Xuất - Thành tiền", "xuat_tt"),
	("Tồn cuối - SL", "ton_cuoi_sl"),
	("Tồn cuối - Thành tiền", "ton_cuoi_tt"),
]

# Cùng tám cột số của NXT_COLUMNS, thêm Số lô / Hạn sử dụng, bớt Mã/Tên/ĐVT
# (đã cố định ở mức vật tư khi bung xuống lô — xem BaoCaoNXT.vue).
NXT_LOT_COLUMNS = [
	("Số lô", "so_lo"),
	("Hạn sử dụng", "han_su_dung"),
	("Tồn đầu - SL", "ton_dau_sl"),
	("Tồn đầu - Thành tiền", "ton_dau_tt"),
	("Nhập - SL", "nhap_sl"),
	("Nhập - Thành tiền", "nhap_tt"),
	("Xuất - SL", "xuat_sl"),
	("Xuất - Thành tiền", "xuat_tt"),
	("Tồn cuối - SL", "ton_cuoi_sl"),
	("Tồn cuối - Thành tiền", "ton_cuoi_tt"),
]

THE_KHO_COLUMNS = [
	("Ngày", "ngay"),
	("Số chứng từ", "chung_tu"),
	("Loại chứng từ", "loai_chung_tu"),
	("Đối tác / Nơi nhận", "doi_tac"),
	("Số lô", "so_lo"),
	("SL nhập", "sl_nhap"),
	("SL xuất", "sl_xuat"),
	("Tồn luỹ kế", "ton_luy_ke"),
]

CANH_BAO_COLUMNS = [
	("Mã vật tư", "ma_vat_tu"),
	("Tên vật tư", "ten_vat_tu"),
	("ĐVT", "dvt"),
	("Số lô", "so_lo"),
	("Hạn sử dụng", "han_su_dung"),
	("Số ngày còn lại", "so_ngay_con_lai"),
	("Số lượng tồn", "so_luong"),
	("Trạng thái", "trang_thai"),
]

_CHUNG_TU_LABEL = {
	"Customer Stock Receipt": "Phiếu nhập",
	"Customer Stock Issue": "Phiếu xuất",
}


def _r(v) -> float:
	"""Làm tròn rác dấu phẩy động về 0 (cùng ngưỡng EPS với ledger.py)."""
	v = float(v or 0)
	return 0.0 if abs(v) < EPS else round(v, 6)


def _new_bucket() -> dict:
	return {
		"ton_dau_sl": 0.0, "ton_dau_tt": 0.0,
		"nhap_sl": 0.0, "nhap_tt": 0.0,
		"xuat_sl": 0.0, "xuat_tt": 0.0,
	}


def _close(bucket: dict) -> dict:
	"""Tồn cuối LUÔN được TÍNH, không bao giờ đọc từ nơi khác (kể cả cache):
	đó là điều duy nhất khiến tồn đầu + nhập − xuất = tồn cuối đúng theo cấu
	trúc, không phải nhờ hai phép tính độc lập tình cờ khớp nhau."""
	out = dict(bucket)
	out["ton_cuoi_sl"] = out["ton_dau_sl"] + out["nhap_sl"] - out["xuat_sl"]
	out["ton_cuoi_tt"] = out["ton_dau_tt"] + out["nhap_tt"] - out["xuat_tt"]
	return {k: _r(v) for k, v in out.items()}


def _vat_tu_info(kho: str) -> dict:
	"""Tra cứu tên/ĐVT cho MỌI vật tư từng có trong kho, kể cả đã `active=0`:
	một báo cáo lịch sử phải hiển thị được vật tư đã ngừng dùng nếu nó có
	phát sinh trong kỳ — khác với kho_vat_tu_list() (chỉ vật tư đang dùng,
	dùng để CHỌN khi lập phiếu mới)."""
	rows = frappe.get_all(
		"Customer Warehouse Item",
		filters={"kho": kho},
		fields=["name", "ma_vat_tu", "ten_vat_tu", "dvt"],
	)
	return {r["name"]: r for r in rows}


def ton_hien_tai_rows(kho: str, tim: str | None = None) -> list[dict]:
	"""Tồn hiện tại của MỘT kho, gộp các lô về một dòng cho mỗi vật tư.

	Chuyển từ `api/kho.py::kho_ton()` (Phase 2) sang đây nguyên trạng — cùng
	một phép gộp, giờ dùng chung bởi cả `kho_ton()` (portal, một kho suy từ
	phiên đăng nhập) và `kho.desk_reports.ton_kho_khach_hang_rows()` (desk,
	Phase 6, lặp qua NHIỀU kho rồi gọi lại đúng hàm này cho từng kho). Không
	được viết lại phép cộng này lần thứ hai ở bất cứ đâu khác.

	Đọc từ `Customer Stock Lot Balance` — đây là câu hỏi VỀ HIỆN TẠI, giống
	`canh_bao_han_rows()`, không phải lịch sử."""
	lots = frappe.get_all(
		"Customer Stock Lot Balance",
		filters={"kho": kho, "so_luong": [">", EPS]},
		fields=["vat_tu", "so_lo", "han_su_dung", "so_luong", "gia_tri"],
	)

	gop = {}
	for lot in lots:
		g = gop.setdefault(lot["vat_tu"], {
			"vat_tu": lot["vat_tu"], "so_luong": 0.0, "gia_tri": 0.0,
			"so_lo_count": 0, "han_gan_nhat": None,
		})
		g["so_luong"] += float(lot["so_luong"])
		g["gia_tri"] += float(lot["gia_tri"] or 0)
		g["so_lo_count"] += 1
		han = lot["han_su_dung"]
		if han and (g["han_gan_nhat"] is None or han < g["han_gan_nhat"]):
			g["han_gan_nhat"] = han

	out = []
	for vat_tu, g in gop.items():
		vt = frappe.db.get_value(
			"Customer Warehouse Item", vat_tu,
			["ma_vat_tu", "ten_vat_tu", "dvt", "item_code"], as_dict=True,
		)
		if not vt:
			continue
		if tim:
			hay = f"{vt.ma_vat_tu} {vt.ten_vat_tu}".lower()
			if tim.lower() not in hay:
				continue
		out.append({**g, **{
			"ma_vat_tu": vt.ma_vat_tu, "ten_vat_tu": vt.ten_vat_tu,
			"dvt": vt.dvt, "item_code": vt.item_code or "",
		}})
	return sorted(out, key=lambda r: r["ten_vat_tu"])


def nxt_data(kho: str, tu_ngay, den_ngay) -> dict:
	"""Gộp sổ kho theo từng vật tư VÀ theo từng lô trong một lượt quét.

	Trả dict thô {"items": {...}, "lots": {vat_tu: {so_lo: {...}}}, "lot_han":
	{vat_tu: {so_lo: han}}} — nxt_item_rows()/nxt_lot_rows() tự chọn mức và tự
	lọc/enrich. Một lượt quét duy nhất cho cả hai mức để bung xuống lô không
	phải quét lại sổ lần thứ hai.
	"""
	tu = frappe.utils.getdate(tu_ngay)
	den = frappe.utils.getdate(den_ngay)
	if tu > den:
		frappe.throw("Từ ngày phải trước hoặc bằng Đến ngày.", frappe.ValidationError)

	entries = frappe.get_all(
		"Customer Stock Ledger Entry",
		filters={"kho": kho, "ngay": ["<=", den]},
		fields=["vat_tu", "so_lo", "han_su_dung", "ngay", "so_luong", "gia_tri"],
	)

	per_item: dict[str, dict] = {}
	per_lot: dict[str, dict] = {}
	lot_han: dict[str, dict] = {}

	for e in entries:
		vt = e["vat_tu"]
		lo = e["so_lo"]
		ngay = frappe.utils.getdate(e["ngay"])
		sl = float(e["so_luong"])
		gt = float(e["gia_tri"] or 0)

		item_b = per_item.setdefault(vt, _new_bucket())
		lot_b = per_lot.setdefault(vt, {}).setdefault(lo, _new_bucket())
		if e.get("han_su_dung"):
			lot_han.setdefault(vt, {}).setdefault(lo, e["han_su_dung"])

		# Phân vùng TOÀN PHẦN theo (trước kỳ) / (nhập, so_luong>0) / (xuất,
		# còn lại): một dòng so_luong==0 (không xảy ra trong thực tế nhưng
		# không được để lọt qua cả hai nhánh) rơi vào "xuất" với biên độ 0 —
		# không mất, không đếm hai lần.
		for b in (item_b, lot_b):
			if ngay < tu:
				b["ton_dau_sl"] += sl
				b["ton_dau_tt"] += gt
			elif sl > 0:
				b["nhap_sl"] += sl
				b["nhap_tt"] += gt
			else:
				b["xuat_sl"] += -sl
				b["xuat_tt"] += -gt

	return {
		"items": {vt: _close(b) for vt, b in per_item.items()},
		"lots": {
			vt: {lo: _close(b) for lo, b in lots.items()}
			for vt, lots in per_lot.items()
		},
		"lot_han": lot_han,
	}


def nxt_item_rows(kho: str, tu_ngay, den_ngay, tim: str | None = None) -> list[dict]:
	"""Một dòng cho mỗi vật tư CÓ PHÁT SINH TRONG SỔ tính tới den_ngay — tức
	là có dòng sổ trước tu_ngay (tồn đầu khác 0 hoặc từng khác 0) HOẶC có dòng
	sổ trong kỳ. Vật tư tồn cuối bằng 0 do vừa nhập vừa xuất hết trong kỳ VẪN
	xuất hiện — không lọc theo tồn cuối ở bất cứ đâu trong hàm này."""
	data = nxt_data(kho, tu_ngay, den_ngay)
	info = _vat_tu_info(kho)
	out = []
	for vt, closed in data["items"].items():
		meta = info.get(vt)
		if not meta:
			continue
		if tim:
			hay = f"{meta['ma_vat_tu']} {meta['ten_vat_tu']}".lower()
			if tim.lower() not in hay:
				continue
		out.append({
			"vat_tu": vt, "ma_vat_tu": meta["ma_vat_tu"],
			"ten_vat_tu": meta["ten_vat_tu"], "dvt": meta["dvt"],
			**closed,
		})
	return sorted(out, key=lambda r: r["ten_vat_tu"])


def nxt_lot_rows(kho: str, vat_tu: str, tu_ngay, den_ngay) -> list[dict]:
	"""Bung một vật tư xuống mức lô cho CÙNG khoảng ngày. Tổng của các dòng
	trả về ở đây, trên cả tám cột số, PHẢI bằng đúng dòng vật tư tương ứng của
	nxt_item_rows() — cả hai đọc từ cùng một lượt quét nxt_data()."""
	data = nxt_data(kho, tu_ngay, den_ngay)
	lots = data["lots"].get(vat_tu, {})
	han = data["lot_han"].get(vat_tu, {})
	out = []
	for lo, closed in lots.items():
		out.append({"so_lo": lo, "han_su_dung": han.get(lo), **closed})
	return sorted(
		out, key=lambda r: (r["han_su_dung"] is None, r["han_su_dung"] or "", r["so_lo"])
	)


def the_kho_rows(kho: str, vat_tu: str, tu_ngay, den_ngay) -> list[dict]:
	"""Thẻ kho của một vật tư: mọi dòng sổ trong [tu_ngay, den_ngay], theo thứ
	tự thời gian, với cột tồn luỹ kế bắt đầu từ đúng tồn đầu kỳ (tổng sổ trước
	tu_ngay) — không bắt đầu từ 0, nếu không con số sẽ là hư cấu với mọi kỳ
	không mở đúng từ đầu lịch sử.

	Sắp theo `ngay asc, creation asc, name asc`: `ngay` một mình không đủ duy
	nhất (nhiều chứng từ cùng ngày), và trường `sort_field` mặc định của
	doctype (`creation`) một mình lại sai thứ tự khi có phiếu ghi lùi ngày —
	đúng lý do rebuild_lot_balance() đã ghi trong docstring của nó.
	"""
	tu = frappe.utils.getdate(tu_ngay)
	den = frappe.utils.getdate(den_ngay)
	if tu > den:
		frappe.throw("Từ ngày phải trước hoặc bằng Đến ngày.", frappe.ValidationError)

	opening = frappe.get_all(
		"Customer Stock Ledger Entry",
		filters={"kho": kho, "vat_tu": vat_tu, "ngay": ["<", tu]},
		pluck="so_luong",
	)
	balance = sum(float(v) for v in opening)

	entries = frappe.get_all(
		"Customer Stock Ledger Entry",
		filters={"kho": kho, "vat_tu": vat_tu, "ngay": ["between", [tu, den]]},
		fields=["name", "ngay", "so_lo", "so_luong", "chung_tu_type", "chung_tu", "creation"],
		order_by="ngay asc, creation asc, name asc",
	)

	receipt_names = {e["chung_tu"] for e in entries if e["chung_tu_type"] == "Customer Stock Receipt"}
	issue_names = {e["chung_tu"] for e in entries if e["chung_tu_type"] == "Customer Stock Issue"}
	nguoi_giao = {}
	if receipt_names:
		nguoi_giao = dict(frappe.get_all(
			"Customer Stock Receipt", filters={"name": ["in", list(receipt_names)]},
			fields=["name", "nguoi_giao"], as_list=True,
		))
	noi_nhan = {}
	if issue_names:
		noi_nhan = {
			r["name"]: r for r in frappe.get_all(
				"Customer Stock Issue", filters={"name": ["in", list(issue_names)]},
				fields=["name", "noi_nhan", "nguoi_nhan"],
			)
		}

	out = []
	for e in entries:
		sl = float(e["so_luong"])
		balance += sl
		if e["chung_tu_type"] == "Customer Stock Receipt":
			doi_tac = nguoi_giao.get(e["chung_tu"]) or ""
		else:
			r = noi_nhan.get(e["chung_tu"]) or {}
			doi_tac = " / ".join(x for x in [r.get("noi_nhan"), r.get("nguoi_nhan")] if x)
		out.append({
			"ngay": e["ngay"],
			"chung_tu": e["chung_tu"],
			"loai_chung_tu": _CHUNG_TU_LABEL.get(e["chung_tu_type"], e["chung_tu_type"]),
			"doi_tac": doi_tac,
			"so_lo": e["so_lo"],
			"sl_nhap": _r(sl) if sl > 0 else 0.0,
			"sl_xuat": _r(-sl) if sl < 0 else 0.0,
			"ton_luy_ke": _r(balance),
		})
	return out


def canh_bao_han_rows(kho: str, so_ngay: int = 90) -> list[dict]:
	"""Lô đã hết hạn (còn tồn) VÀ lô hết hạn trong `so_ngay` ngày tới, gần nhất
	trước — một sắp xếp ASCENDING duy nhất theo `han_su_dung` cho cả hai nhóm
	đã đủ: nhóm đã hết hạn (ngày trong quá khứ) luôn đứng trước nhóm sắp hết
	hạn (ngày trong tương lai), và trong mỗi nhóm ngày gần `hôm nay` nhất lên
	đầu — hết hạn lâu nhất trước (cấp bách nhất), sắp hết hạn sớm nhất trước.

	Đọc từ `Customer Stock Lot Balance` — cố ý, xem docstring đầu file: đây là
	câu hỏi VỀ HIỆN TẠI, không phải lịch sử.
	"""
	today = frappe.utils.getdate(frappe.utils.today())
	han_toi = frappe.utils.add_days(today, int(so_ngay))
	lots = frappe.get_all(
		"Customer Stock Lot Balance",
		filters={
			"kho": kho,
			"so_luong": [">", EPS],
			"han_su_dung": ["<=", han_toi],
		},
		fields=["vat_tu", "so_lo", "han_su_dung", "so_luong"],
	)
	info = _vat_tu_info(kho)
	out = []
	for lot in lots:
		han = frappe.utils.getdate(lot["han_su_dung"])
		meta = info.get(lot["vat_tu"]) or {}
		out.append({
			"vat_tu": lot["vat_tu"],
			"ma_vat_tu": meta.get("ma_vat_tu", ""),
			"ten_vat_tu": meta.get("ten_vat_tu", ""),
			"dvt": meta.get("dvt", ""),
			"so_lo": lot["so_lo"],
			"han_su_dung": han,
			"so_ngay_con_lai": (han - today).days,
			"so_luong": _r(lot["so_luong"]),
			"trang_thai": "Đã hết hạn" if han < today else "Sắp hết hạn",
		})
	return sorted(out, key=lambda r: (r["han_su_dung"], r["so_lo"]))


def build_xlsx(columns: list[tuple[str, str]], rows: list[dict], sheet_title: str) -> bytes:
	"""Dựng .xlsx với ĐÚNG bộ cột `columns`, theo ĐÚNG thứ tự — dùng chung cho
	cả ba loại báo cáo. Giá trị ghi thẳng kiểu gốc (số, ngày) chứ không format
	thành chuỗi hiển thị, để file mở lại được bằng công thức/pivot ngay, đúng
	nguyên tắc round-tripping-spreadsheets."""
	wb = Workbook()
	ws = wb.active
	ws.title = sheet_title[:31]  # giới hạn cứng của Excel cho tên sheet
	ws.append([label for label, _ in columns])
	for cell in ws[1]:
		cell.font = Font(bold=True)
	for row in rows:
		ws.append([row.get(field, "") for _, field in columns])
	for i, (label, _) in enumerate(columns, start=1):
		ws.column_dimensions[get_column_letter(i)].width = max(12, min(30, len(label) + 4))
	buf = io.BytesIO()
	wb.save(buf)
	return buf.getvalue()
