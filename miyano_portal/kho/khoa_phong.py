"""Danh mục khoa phòng của kho khách hàng — US-E8.1, BR-CP1/CP3.

Cùng khuôn với kho/ncc.py (đọc docstring ở đó trước): tầng này KHÔNG biết gì
về phiên đăng nhập, `kho` luôn do nơi gọi (api/kho.py) truyền vào sau khi đã
resolve từ phiên.

Chốt chặn "trùng tuyệt đối trong BỆNH VIỆN" (NL-4.13) sống ở
customer_department.py:validate() — chạy trên MỌI đường ghi (Desk lẫn
endpoint này), không lặp lại ở đây. Module này chỉ tính thêm gợi ý "gần
giống" (KHÔNG chặn) cho response của kho_khoa_phong_save, và gợi ý Người
nhận theo lịch sử của khoa (BR-CP3).
"""

import frappe

from miyano_portal.kho import similarity
from miyano_portal.kho.import_ton_dau import _norm

TRUONG_MO_TA = ("ma_khoa", "ghi_chu")

_GOI_Y_NGUOI_NHAN_THANG = 12
_GOI_Y_NGUOI_NHAN_TOI_DA = 10


def _existing_rows(kho: str, exclude: str | None) -> list:
	"""Lọc theo `customer` (không phải `kho`) — vòng sửa 1, phát hiện 4:
	`customer_department.py:_chan_trung_tuyet_doi()` đã chuyển sang lọc theo
	`customer` từ bước 2 (khoa phòng khoá theo bệnh viện, không theo kho).
	Từ bước 2, một khách có thể có VỪA khoa phòng gắn kho VỪA khoa phòng
	KHÔNG gắn kho — nếu ở đây vẫn lọc theo `kho`, gợi ý "gần giống" bỏ sót
	các khoa không gắn kho của cùng khách, và tệ hơn: xem trước
	(`chi_kiem_tra`) có thể báo "không trùng" trong khi lưu thật lại bị
	validate() chặn vì nó so đúng phạm vi `customer`."""
	customer = frappe.db.get_value("Customer Warehouse", kho, "customer")
	rows = frappe.get_all(
		"Customer Department", filters={"customer": customer}, fields=["name", "ten_khoa_phong"]
	)
	if exclude:
		rows = [r for r in rows if r.name != exclude]
	return rows


def _goi_y_gan_giong(kho: str, ten: str, exclude: str | None) -> list[str]:
	"""NL-4.13: liệt kê khoa phòng có tên GẦN GIỐNG (không phải trùng tuyệt
	đối — trùng tuyệt đối đã bị validate() chặn từ trước khi tới đây) để
	client gợi ý chọn thay vì tạo mới. Không chặn."""
	goi_y = []
	for row in _existing_rows(kho, exclude):
		if similarity.phan_loai(ten, row.ten_khoa_phong) == "gan_giong":
			goi_y.append(f"{row.name}: {row.ten_khoa_phong}")
	return goi_y


def ra_dict(name: str) -> dict:
	row = frappe.db.get_value(
		"Customer Department", name,
		["name", "ten_khoa_phong", "ma_khoa", "ghi_chu", "active"],
		as_dict=True,
	)
	for f in ("ma_khoa", "ghi_chu"):
		row[f] = row[f] or ""
	row["active"] = int(row["active"] or 0)
	return row


def _thong_ke_90n(name: str) -> tuple[int, float]:
	"""Cùng khuôn ncc._thong_ke_90n(): đếm MỌI phiếu Xuất kho đã ghi sổ gắn
	khoa này trong 90 ngày, không lọc riêng `loai_xuat` — nhất quán với cách
	NCC đếm mọi `loai_nhap` (không chỉ "Mua ngoài"). Báo cáo cấp phát
	(kho_bao_cao_cap_phat, reports.py) thì CÓ lọc riêng "Xuất sử dụng" —
	hai con số phục vụ hai câu hỏi khác nhau ("khoa này có mặt trên bao
	nhiêu phiếu xuất nói chung" vs "khoa này được cấp phát bao nhiêu"), cố
	tình không dùng chung một phép đếm.

	F-3 (review E8, CHẶN): "không lọc riêng loai_xuat" chỉ hợp lệ cho việc
	KHÔNG thu hẹp về mỗi "Xuất sử dụng" — nó KHÔNG hợp lệ cho việc đếm cả
	"Phiếu đảo". Một cặp xuất-huỷ để lại phiếu GỐC docstatus=2 (rớt khỏi
	`docstatus=1` một cách tự nhiên) NHƯNG phiếu ĐẢO (BR-K9, hệ tự tạo)
	docstatus=1, mang khoa_phong copy nguyên từ phiếu gốc (xem
	_tao_phieu_dao) và tong_tien DƯƠNG — nếu không loại, một lần xuất-rồi-
	huỷ-ngay-vì-nhầm-khoa vẫn cộng đủ cả số phiếu lẫn giá trị vào đúng
	khoa đó, trong khi báo cáo cấp phát (reports.bao_cao_cap_phat_rows,
	lọc loai_xuat=="Xuất sử dụng") đúng đắn cho ra 0 — hai con số của CÙNG
	một khoa, trên hai màn cạnh nhau, chọi nhau."""
	tu_ngay = frappe.utils.add_days(frappe.utils.today(), -90)
	so_phieu = frappe.db.count(
		"Customer Stock Issue", {
			"khoa_phong": name, "docstatus": 1, "ngay": [">=", tu_ngay],
			"loai_xuat": ["!=", "Phiếu đảo"],
		}
	)
	tong = frappe.db.sql(
		"""select coalesce(sum(tong_tien), 0) from `tabCustomer Stock Issue`
		   where khoa_phong=%s and docstatus=1 and ngay >= %s and loai_xuat != %s""",
		(name, tu_ngay, "Phiếu đảo"),
	)
	return so_phieu, float(tong[0][0] or 0)


def list_rows(
	kho: str, tim_kiem: str | None = None, ca_inactive=False,
	limit: int | None = None, start: int = 0,
) -> list[dict] | dict:
	"""Danh mục khoa phòng — cùng khuôn `kho_ncc_list()`: trả ĐỦ chi tiết mô
	tả trong MỘT lượt, không chỉ vài cột hiển thị bảng (Gap 1, review E4
	phần B — xem docstring ncc.list_rows() cho lý do đầy đủ).

	Brief 2026-08-15 (phân trang) — cùng ràng buộc/khuôn `ncc.list_rows()`:
	endpoint `kho_khoa_phong_list` KIÊM HAI VAI (màn danh mục + dropdown
	NhatKy.vue/BaoCaoNXT.vue), `limit=None` giữ nguyên hành vi cũ (list
	đầy đủ), chỉ cắt trang khi `limit` được truyền — đọc docstring
	`ncc.list_rows()` cho lý do đầy đủ (lọc Python, cắt trước khi tính
	thống kê 90 ngày để không lãng phí truy vấn cho dòng không hiển thị).
	"""
	filters = {"kho": kho}
	if not frappe.utils.cint(ca_inactive):
		filters["active"] = 1
	rows = frappe.get_all(
		"Customer Department", filters=filters,
		fields=["name", "ten_khoa_phong", "ma_khoa", "ghi_chu", "active"],
		# tiebreak `name` — `ten_khoa_phong` không unique.
		order_by="ten_khoa_phong asc, name asc",
	)
	if tim_kiem:
		hay = similarity.khong_dau(tim_kiem)
		rows = [r for r in rows if hay in similarity.khong_dau(r.ten_khoa_phong)]

	phan_trang = limit not in (None, "")
	tong = len(rows)
	if phan_trang:
		limit = frappe.utils.cint(limit)
		start = frappe.utils.cint(start)
		rows = rows[start:start + limit]

	out = []
	for r in rows:
		so_phieu_90n, gia_tri_90n = _thong_ke_90n(r.name)
		out.append({
			"name": r.name,
			"ten_khoa_phong": r.ten_khoa_phong,
			"ma_khoa": r.ma_khoa or "",
			"ghi_chu": r.ghi_chu or "",
			"so_phieu_90n": so_phieu_90n,
			"gia_tri_90n": gia_tri_90n,
			"active": int(r.active or 0),
		})
	return {"rows": out, "tong": tong} if phan_trang else out


def save(kho: str, du_lieu: dict) -> dict:
	"""Tạo mới (name rỗng/None) hoặc sửa (name có giá trị, PHẢI thuộc kho —
	nơi gọi đã kiểm bằng _khoa_cua_kho() trước khi tới đây cho trường hợp
	sửa). Cùng khuôn ncc.save(), kể cả chế độ xem trước `chi_kiem_tra`."""
	name = du_lieu.get("name")
	ten = _norm(du_lieu.get("ten_khoa_phong"))
	if not ten:
		frappe.throw("Thiếu Tên khoa phòng.", frappe.ValidationError)

	goi_y = _goi_y_gan_giong(kho, ten, exclude=name)

	if du_lieu.get("chi_kiem_tra") and not name:
		return {"name": None, "ten_khoa_phong": ten, "goi_y_trung": goi_y}

	if name:
		doc = frappe.get_doc("Customer Department", name)
	else:
		doc = frappe.new_doc("Customer Department")
		doc.kho = kho

	doc.ten_khoa_phong = ten
	for truong in TRUONG_MO_TA:
		if truong in du_lieu:
			setattr(doc, truong, _norm(du_lieu.get(truong)) or None)
	if "active" in du_lieu:
		doc.active = 1 if frappe.utils.cint(du_lieu.get("active")) else 0

	if doc.is_new():
		doc.insert(ignore_permissions=True)
	else:
		doc.save(ignore_permissions=True)

	out = ra_dict(doc.name)
	out["goi_y_trung"] = goi_y
	return out


def nguoi_nhan_goi_y(kho: str, khoa_phong: str, tu_khoa: str | None = None) -> list[str]:
	"""US-E8.3/BR-CP3: gợi ý Người nhận theo lịch sử của CHÍNH khoa phòng
	được chọn, 12 tháng gần nhất, khớp không dấu, tối đa 10 kết quả.

	Nguồn: `nguoi_nhan` distinct từ phiếu "Xuất sử dụng" ĐÃ GHI SỔ của khoa
	đó — nháp/loại xuất khác không phải "cấp phát thật", không tính.

	CỐ Ý không dùng `distinct=True` cùng `order_by` trên một field KHÔNG có
	trong SELECT: MariaDB dưới `sql_mode` mặc định của site (bao gồm
	ONLY_FULL_GROUP_BY-tương-đương cho DISTINCT + ORDER BY) từ chối tổ hợp
	đó. Đọc thô `nguoi_nhan`+`ngay` (không distinct) rồi tự khử trùng lặp và
	sắp xếp ở Python — dữ liệu vài chục dòng mỗi khoa mỗi năm, không đáng kể.
	"""
	tu_ngay = frappe.utils.add_months(frappe.utils.today(), -_GOI_Y_NGUOI_NHAN_THANG)
	rows = frappe.get_all(
		"Customer Stock Issue",
		filters={
			"kho": kho, "khoa_phong": khoa_phong, "loai_xuat": "Xuất sử dụng",
			"docstatus": 1, "ngay": [">=", tu_ngay],
		},
		fields=["nguoi_nhan", "ngay"],
		order_by="ngay desc",
	)

	ten_gan_nhat: dict[str, str] = {}
	for r in rows:
		v = (r.nguoi_nhan or "").strip()
		if not v:
			continue
		key = similarity.khong_dau(v)
		# rows đã sắp `ngay desc` — lần gặp ĐẦU TIÊN của mỗi key là lần dùng
		# GẦN NHẤT, giữ nguyên bản chính tả đó (không ghi đè bởi lần cũ hơn).
		ten_gan_nhat.setdefault(key, v)

	if tu_khoa:
		hay = similarity.khong_dau(tu_khoa)
		ten_gan_nhat = {k: v for k, v in ten_gan_nhat.items() if hay in k}

	return list(ten_gan_nhat.values())[:_GOI_Y_NGUOI_NHAN_TOI_DA]
