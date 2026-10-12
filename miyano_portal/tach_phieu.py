"""Tách một lần đặt trộn thành hai phiếu (spec 2026-10-09 §4.1, quyết định Q6).

Hàng có giá trong Price List đi thẳng tới Miyano xác nhận; hàng chờ báo giá
đi vòng báo giá. Hai nhóm đi hai tốc độ khác nhau, nên mỗi nhóm là MỘT phiếu
và MỘT đơn — quan hệ một phiếu ↔ một đơn của cả hệ thống giữ nguyên.
"""

import frappe

from miyano_portal import bang_gia_khach

DOCTYPE = "Portal De Xuat Mua"

HAU_TO_GIA = ":gia"
HAU_TO_BAO_GIA = ":baogia"

# Thông tin đầu phiếu chép sang phiếu thứ hai. KHÔNG có `hdnt`: cổng không
# còn kiểm soát theo hợp đồng (quyết định Q3); phiếu Nháp lập trước đó có
# thể còn mang nó, và phiếu chờ báo giá sinh ra ở đây không được thừa hưởng.
_TRUONG_CHUNG = (
	"customer", "khoa_phong", "ngay_can", "dia_chi_giao", "ghi_chu",
	"ly_do_yeu_cau", "ten_don_hang",
)

# Khoá định danh của dòng con — bỏ khi chép dòng sang phiếu mới.
_KHOA_DINH_DANH = (
	"name", "parent", "parenttype", "parentfield", "idx", "creation",
	"modified", "modified_by", "owner", "docstatus",
)


def _ma_chinh_tac(ma) -> str:
	"""`Item.name` chính tắc của mã client gửi. `tabItem` so không phân biệt
	hoa/thường và bỏ khoảng trắng cuối, còn `gia_bang_gia_nhieu` trả kết quả
	khoá theo `Item.name` và so bằng Python — cùng lý do `dat_hang.
	tao_sales_order` chuẩn hoá mã trước khi hỏi giá (review C-2 ở đó). Mã
	không tra ra Item thì trả nguyên: nó rơi về nhóm chờ báo giá và tầng dựng
	đơn / Link của phiếu tự từ chối bằng thông điệp của chính nó."""
	tho = (ma or "").strip()
	if not tho:
		return tho
	return frappe.db.get_value("Item", tho, "name") or tho


def chia_dong(customer: str, items: list[dict]) -> tuple[list[dict], list[dict]]:
	"""Chia dòng theo §3.2: `(co_gia, cho_bao_gia)`. Mỗi phần tử là CHÍNH dict
	đầu vào, giữ nguyên thứ tự."""
	ma = [_ma_chinh_tac(d.get("item_code")) for d in items]
	co_gia_theo_ma = bang_gia_khach.gia_bang_gia_nhieu(customer, ma)
	co_gia = [d for d, m in zip(items, ma) if m in co_gia_theo_ma]
	cho_bao_gia = [d for d, m in zip(items, ma) if m not in co_gia_theo_ma]
	return co_gia, cho_bao_gia


def lien_ket(ten_a: str, ten_b: str, ma_lan_dat: str) -> None:
	frappe.db.set_value(DOCTYPE, ten_a, {
		"ma_lan_dat": ma_lan_dat, "phieu_cung_lan_dat": ten_b,
	}, update_modified=False)
	frappe.db.set_value(DOCTYPE, ten_b, {
		"ma_lan_dat": ma_lan_dat, "phieu_cung_lan_dat": ten_a,
	}, update_modified=False)


def _chuyen_anh(tu: str, sang: str, dat_ngoai) -> None:
	"""Ảnh của dòng gõ tay đính vào PHIẾU chứ không vào dòng con (xem
	`portal_dat_ngoai_tai_anh`), và `portal_dat_ngoai_xem_anh` chỉ phục vụ ảnh
	đính đúng phiếu đang xem. Dòng đi sang phiếu mới thì tệp phải đi theo;
	phiếu gốc không còn dòng gõ tay nào nên không còn ai cần tệp ở đó."""
	ds_url = set()
	for d in dat_ngoai:
		try:
			ds = frappe.parse_json(d.get("anh")) if d.get("anh") else []
		except Exception:
			ds = []
		ds_url.update(u for u in ds or [] if isinstance(u, str) and u)
	if not ds_url:
		return
	for ten in frappe.get_all("File", filters={
		"attached_to_doctype": DOCTYPE, "attached_to_name": tu,
		"file_url": ["in", list(ds_url)],
	}, pluck="name"):
		frappe.db.set_value("File", ten, "attached_to_name", sang,
		                    update_modified=False)


def gui_duyet_co_tach(doc) -> list:
	"""Gửi duyệt phiếu `doc`; nếu nó trộn hai loại hàng thì tách trước.

	Phiếu GỐC giữ hàng có giá. Phiếu MỚI nhận hàng chờ báo giá và mọi dòng gõ
	tay. Cả hai chạy trong giao dịch của request: lỗi ở bất kỳ bước nào thì
	Frappe rollback toàn bộ, không để lại phiếu mồ côi.

	Ruling R6 — chỉ tách ở lần gửi duyệt ĐẦU TIÊN (`ma_de_xuat` còn trống).
	Phiếu đã có mã (gửi lại sau Thu hồi / Từ chối) là phiếu quản lý và khoa
	đã gọi tên, dòng cũ của nó đã đóng băng nguồn giá; gửi lại giữ MỘT phiếu
	dù lúc này nó mang cả hai loại dòng.
	"""
	if doc.ma_de_xuat:
		doc.gui_duyet()
		return [doc]

	co_gia, cho_bao_gia = chia_dong(doc.customer, [r.as_dict() for r in doc.items])
	dat_ngoai = [d.as_dict() for d in (doc.get("dat_ngoai") or [])]
	if not (co_gia and (cho_bao_gia or dat_ngoai)):
		doc.gui_duyet()
		return [doc]

	# Kiểm TRƯỚC mọi lần ghi những thứ `gui_duyet()` của phiếu thứ hai sẽ
	# kiểm (nó nhận đúng lý do và đúng các dòng gõ tay này): phiếu gốc không
	# bị cắt dòng và không tiêu số nào trong dãy mã rồi mới phát hiện phiếu
	# kia không gửi được.
	doc.kiem_truoc_gui_duyet()

	def _dong_moi(d):
		return {k: v for k, v in dict(d).items() if k not in _KHOA_DINH_DANH}

	moi = frappe.get_doc({
		"doctype": DOCTYPE, "trang_thai": "Nháp",
		**{f: doc.get(f) for f in _TRUONG_CHUNG},
		"items": [_dong_moi(d) for d in cho_bao_gia],
		"dat_ngoai": [_dong_moi(d) for d in dat_ngoai],
	}).insert(ignore_permissions=True)
	# Phiếu mới phải thuộc về người đã lập phiếu gốc: quyền gửi/thu hồi và
	# cột "người tạo" trên danh sách đều đọc `owner`. Qua `de_xuat_gui_duyet`
	# người gọi CHÍNH LÀ chủ phiếu nên dòng này không đổi gì; nó ở đây cho
	# người gọi khác (script, desk).
	frappe.db.set_value(DOCTYPE, moi.name, "owner", doc.owner, update_modified=False)
	moi.reload()
	_chuyen_anh(doc.name, moi.name, dat_ngoai)

	ma_co_gia = {d["item_code"] for d in co_gia}
	doc.set("items", [r for r in doc.items if r.item_code in ma_co_gia])
	doc.set("dat_ngoai", [])
	doc.save(ignore_permissions=True)

	# Một lần bấm gửi là MỘT việc chờ quản lý: tắt thông báo riêng của từng
	# phiếu (cờ đặt ngay trước `gui_duyet()` — `reload()` phía trên không giữ
	# cờ) và gửi một thông báo gọi tên cả hai mã sau khi đã nối hai phiếu.
	doc.flags.khong_bao_gui_duyet = True
	doc.gui_duyet()
	moi.flags.khong_bao_gui_duyet = True
	moi.gui_duyet()
	lien_ket(doc.name, moi.name, doc.ma_de_xuat)
	doc.reload()
	moi.reload()
	from miyano_portal.portal_thong_bao_khach import bao_de_xuat_gui_duyet

	bao_de_xuat_gui_duyet(doc, cung_lan_dat=moi)
	return [doc, moi]
