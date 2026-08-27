"""Danh mục thiết bị của khách hàng — logic thuần, không whitelist.

Đường ghi: các hàm ở đây được gọi từ api/kho.py SAU khi endpoint đã suy
`customer`/`user` từ phiên (Task 7). Chúng ghi bằng ignore_permissions=True —
đúng khuôn kho/khoa_phong.py::save(). Xem Global Constraint 2 của kế hoạch: THÊM
DOCPERM KHÔNG BAO GIỜ LÀ CÁCH SỬA một PermissionError ở đây.

`Customer Equipment` treo vào `customer` (không có field `kho`) — khác NCC/
khoa phòng, hàm ở module này nhận `customer`, không nhận `kho`.
"""

import frappe

from miyano_portal.kho import similarity
from miyano_portal.portal_context import pham_vi_don

# Trường nhận thẳng từ client cho cả tạo mới lẫn sửa (khoa_phong/active/name
# xử lý riêng — xem save()).
TRUONG_NHAN_TU_CLIENT = (
	"ma_thiet_bi", "ten_thiet_bi", "hang_san_xuat", "xuat_xu",
	"model", "so_serial", "nam_san_xuat", "ngay_lap_dat", "ghi_chu",
)

# Các ô của form tạo nhanh. "Nhanh" nói về SỐ Ô, không nói về độ chặt —
# tao_nhanh() đi qua đúng validate() của doctype như form đầy đủ (nó chỉ là
# save() với payload bị bó hẹp về đúng các trường này).
#
# SAI KHÁC SO VỚI BRIEF: docstring "Khung bắt buộc" của brief gốc ghi "Sáu ô
# của form tạo nhanh", nhưng tuple đi kèm (và payload của test
# `test_tao_nhanh_dien_du_sau_o`) chỉ liệt kê ĐÚNG NĂM trường. Giữ năm
# trường theo tuple+test (hợp đồng thật), sửa số đếm trong lời văn — không tự
# bịa thêm trường thứ sáu (ứng viên khả dĩ nhất là `model`, đã có sẵn trong
# TRUONG_NHAN_TU_CLIENT, nhưng brief không xác nhận — nếu Task 7 dựng form 6
# ô, chỉ cần thêm "model" vào tuple này).
TRUONG_TAO_NHANH = ("ten_thiet_bi", "ma_thiet_bi", "hang_san_xuat", "xuat_xu", "so_serial")

# Trường mô tả tự do — rỗng hoá thành "" khi trả ra (không trả None cho SPA).
_TRUONG_MO_TA_RONG = ("hang_san_xuat", "xuat_xu", "model", "so_serial", "ghi_chu")

# Important #2 (review vòng 1) — thông điệp DUY NHẤT cho "không tồn tại" VÀ
# "tồn tại nhưng của bệnh viện khác", đúng khuôn `portal_context.LOI_KHONG_
# THAY`: phân biệt hai câu đó là lộ thêm thông tin ("bệnh viện khác có thiết
# bị mã X") mà một khách hàng không cần biết.
LOI_KHONG_THAY = "Không tìm thấy thiết bị."


def _khoa_ep_theo_phien(user: str, khoa_client):
	"""BR-TB-6 — ép khoa theo phiên, không tin client.

	Nhân viên khoa: BỎ QUA HOÀN TOÀN giá trị client gửi, luôn trả khoa của
	chính họ. Quản lý: nhận giá trị client (validate() của doctype —
	`customer_equipment.py::_chan_khoa_khac_benh_vien()` — đã kiểm khoa đó
	thuộc ĐÚNG bệnh viện `customer` khi ghi, nên không lặp lại kiểm đó ở
	đây).

	SỬA SO VỚI KHUNG CODE TRONG task-6-brief.md (đính chính vòng review 1 —
	nguồn trích dẫn trước đây SAI): khối "Khung bắt buộc" trong task-6-brief.md
	tự viết hàm này bằng cách đọc thẳng `get_portal_member(user).vai_tro`/
	`.khoa_phong`, chỉ dẫn docstring của CHÍNH nó là "Cùng nguyên tắc
	`portal_context.khoa_phong_cho_don()`" — không có câu cấm nào trong
	task-6-brief.md. Câu cấm "đừng tự đọc vai_tro/khoa_phong rồi tự suy — bản
	đầu của kế hoạch làm vậy và đã fail-open" nằm trong CHỈ THỊ GIAO TASK gửi
	kèm (không phải trong file brief), và chính chỉ thị đó là căn cứ cho
	quyết định viết lại này — hai nguồn khác nhau đưa ra hai định hướng khác
	nhau, không phải "brief tự mâu thuẫn nội bộ" như report vòng 1 từng ghi
	nhầm. Quyết định viết lại vẫn đúng và đã được duyệt; chỉ sửa lại trích
	dẫn cho chính xác.

	Lỗi thực chất của khung code brief: nếu một Nhân viên khoa
	`active=1` mà `khoa_phong` rỗng (đi vòng qua validate() bằng
	`db.set_value`/`db_set()`, xem docstring `pham_vi_don()`), bản khung sẽ
	trả `None` — tạo ra một MÁY DÙNG CHUNG ngoài ý muốn, cùng họ lỗi fail-
	open mà đoạn mô tả cảnh báo, chỉ khác chỗ đứng (ghi thay vì đọc). Gọi
	`pham_vi_don()` — nguồn DUY NHẤT — để thừa hưởng đúng chốt fail-closed
	(`PermissionError`) của nó thay vì tự suy lại.

	KHÔNG dùng `portal_context.khoa_phong_cho_don()` dù tên rất gần: (1)
	nhánh Nhân viên khoa của nó trả thẳng `get_portal_member(user).khoa_phong`
	— KHÔNG fail-closed khi rỗng, ngược với thứ hàm này cần; (2) nhánh Quản
	lý của nó so khoa được chọn với `Portal Member.customer` của PHIÊN, chứ
	không phải tham số `customer` mà nơi gọi truyền vào — có thể lệch nếu
	sau này một quản lý thao tác hộ nhiều bệnh viện. Đổi lại, mất một phép
	kiểm mà `khoa_phong_cho_don()` có mà hàm này không lặp lại: nó còn từ
	chối một khoa đã `active=0`; ở đây việc đó nhường lại cho
	`_chan_khoa_khac_benh_vien()` của doctype, vốn CHỈ kiểm `customer`,
	không kiểm `active` — một quản lý về lý thuyết vẫn gán được một khoa đã
	ngừng hoạt động. Chấp nhận khoảng hở nhỏ này để giữ MỘT nguồn kiểm
	(`pham_vi_don`) thay vì trộn hai nguồn logic khoa khác nhau."""
	pv = pham_vi_don(user)
	if not pv:
		# Quản lý — pham_vi_don() trả {} (không giới hạn theo khoa).
		return khoa_client or None
	return pv["custom_khoa_phong"]


def _chan_sua_ngoai_pham_vi(user: str, name: str) -> None:
	"""BR-TB-7 + BR-TB-8b. Cùng lý do dùng `pham_vi_don()` như
	`_khoa_ep_theo_phien()` ở trên — không tự đọc `vai_tro`/`khoa_phong`."""
	pv = pham_vi_don(user)
	if not pv:
		return
	khoa_minh = pv["custom_khoa_phong"]
	kp = frappe.db.get_value("Customer Equipment", name, "khoa_phong")
	if not kp:
		raise frappe.PermissionError(
			"Máy dùng chung không thuộc khoa nào — chỉ quản lý đơn vị sửa được."
		)
	if kp != khoa_minh:
		raise frappe.PermissionError("Máy này thuộc khoa khác.")


def _ten_khoa(ten_khoa_ds: set) -> dict:
	ten_khoa_ds = {k for k in ten_khoa_ds if k}
	if not ten_khoa_ds:
		return {}
	return dict(frappe.get_all(
		"Customer Department", filters={"name": ["in", list(ten_khoa_ds)]},
		fields=["name", "ten_khoa_phong"], as_list=True,
	))


def _chuan_hoa_row(row: dict) -> dict:
	for f in _TRUONG_MO_TA_RONG:
		row[f] = row[f] or ""
	row["nam_san_xuat"] = int(row["nam_san_xuat"]) if row.get("nam_san_xuat") else None
	row["active"] = int(row["active"] or 0)
	return row


def ra_dict(name: str, customer: str) -> dict:
	"""Một máy dạng phẳng cho SPA — kèm `ten_khoa_phong` để hiển thị (Link
	`khoa_phong` không tự có tên đi kèm), đúng lý do Gap 1 của `ncc.py`.

	Important #2 (review vòng 1) — THÊM tham số `customer` và TỰ KIỂM sở hữu
	ở đây, dù trong phạm vi Task 6 hàm này chỉ được gọi sau khi `save()` đã
	kiểm rồi (nên có vẻ "thừa"). Bắt buộc vì brief liệt `ra_dict` vào nhóm
	"Produces" — một hàm PUBLIC của module — và Task 7 sắp nối các hàm này
	vào endpoint nhận `name` THẲNG từ client (vd. "xem chi tiết một máy theo
	docname"); nối `ra_dict(name)` không kiểm gì vào một endpoint như vậy là
	đọc xuyên bệnh viện. Sửa ngay tại nguồn thay vì để lại một cái bẫy cho
	Task 7 phải tự nhớ kiểm ở tầng gọi.

	`name` không tồn tại VÀ `name` tồn tại nhưng của bệnh viện khác dùng
	CHUNG một thông điệp lỗi (`LOI_KHONG_THAY`) — không phân biệt, đúng
	nguyên tắc `portal_context.dam_bao_xem_duoc()` đã áp cho Sales Order/
	Delivery Note/Sales Invoice: phân biệt hai câu đó là lộ thêm việc "một
	bệnh viện khác có thiết bị mã X" cho khách hàng hiện tại."""
	row = frappe.db.get_value(
		"Customer Equipment", name,
		["name", "customer", "ma_thiet_bi", "ten_thiet_bi", "khoa_phong",
		 "hang_san_xuat", "xuat_xu", "model", "so_serial", "nam_san_xuat",
		 "ngay_lap_dat", "ghi_chu", "active"],
		as_dict=True,
	)
	if not row or row["customer"] != customer:
		raise frappe.PermissionError(LOI_KHONG_THAY)
	_chuan_hoa_row(row)
	row["ten_khoa_phong"] = _ten_khoa({row["khoa_phong"]}).get(row["khoa_phong"], "")
	return row


def list_rows(
	customer: str, user: str, tim_kiem: str | None = None, ca_inactive=0,
	khoa_phong: str | None = None, vat_tu: str | None = None,
	limit: int | None = None, start: int = 0,
) -> list[dict] | dict:
	"""Danh mục thiết bị — LỌC HAI TẦNG:

	Tầng 1a (BẮT BUỘC, không phải tuỳ chọn) — phạm vi khoa theo PHIÊN đăng
	nhập: Nhân viên khoa chỉ thấy máy khoa mình CỘNG máy dùng chung
	(`khoa_phong` rỗng); Quản lý nhìn xuyên mọi khoa. Dùng `pham_vi_don()`,
	cùng nguồn với `kho/permissions.py::thiet_bi_query` (lớp phòng thủ SQL) —
	hai tầng phòng thủ khác nhau nhưng PHẢI cùng một câu trả lời.

	Tầng 1b (tuỳ chọn) — tham số `khoa_phong` là lọc THÊM do CLIENT chọn (vd.
	Quản lý xem riêng một khoa qua dropdown màn danh mục). AND với tầng 1a,
	không thay thế — một Nhân viên khoa gửi kèm `khoa_phong` khác khoa mình
	vẫn không thấy gì thêm, vì tầng 1a đã lọc từ trước.

	Tầng 2 (tuỳ chọn) — tham số `vat_tu`: chỉ trả các máy có mặt trong bảng
	"Máy sử dụng" (`Customer Warehouse Item.may_su_dung`) của vật tư đó — hỗ
	trợ màn "Gắn máy vào vật tư" đề xuất đúng máy tương thích. Bảng RỖNG =
	vật tư đó CHƯA khai máy tương thích nào = KHÔNG lọc gì (mọi máy active
	đều là ứng viên hợp lệ để gắn lần đầu), không phải "tương thích với
	không máy nào" — đây là DANH MỤC TƯƠNG THÍCH, không phải ràng buộc cứng
	(Ràng buộc chung 3).

	Important #3 (review vòng 1) — `vat_tu` PHẢI được kiểm thuộc ĐÚNG
	`customer` của tham số hàm này TRƯỚC khi dùng để dựng tập máy cho phép.
	Thiếu bước này, `vat_tu` biến thành một ORACLE dò tồn tại xuyên bệnh
	viện: gửi một `vat_tu` có thật của bệnh viện khác (đã khai máy tương
	thích) trả `[]`, còn gửi một `vat_tu` không tồn tại (hoặc bảng máy rỗng)
	trả đủ danh sách — hai kết quả PHÂN BIỆT được là đủ để dò tuần tự
	`Customer Warehouse Item` (đặt tên `VTK-.#####`, đoán được) xem một mã có
	tồn tại và đã khai máy hay chưa, của BẤT KỲ bệnh viện nào, không chỉ
	bệnh viện của phiên. Sửa: `vat_tu` không thuộc `customer` (kể cả không
	tồn tại) được coi như KHÔNG được gửi — cùng quy ước "bảng rỗng = không
	lọc" ở trên, không phải một nhánh lỗi mới — nên hai trường hợp "của bệnh
	viện khác" và "không tồn tại" luôn cho CÙNG một kết quả (đầy đủ danh
	sách theo tầng 1/1b), không còn phân biệt được nữa.

	Cùng khuôn phân trang `ncc.list_rows()`/`khoa_phong.list_rows()`:
	`limit=None` (mặc định) trả list đầy đủ; truyền `limit` mới cắt trang và
	đổi hình dạng trả về sang `{"rows": [...], "tong": N}`.
	"""
	filters = {"customer": customer}
	if not frappe.utils.cint(ca_inactive):
		filters["active"] = 1

	rows = frappe.get_all(
		"Customer Equipment", filters=filters,
		fields=["name", "customer", "ma_thiet_bi", "ten_thiet_bi", "khoa_phong",
		 "hang_san_xuat", "xuat_xu", "model", "so_serial", "nam_san_xuat",
		 "ngay_lap_dat", "ghi_chu", "active"],
		# tiebreak `name` — `ten_thiet_bi` unique trong bệnh viện nhưng thêm
		# cho nhất quán với ncc.py/khoa_phong.py.
		order_by="ten_thiet_bi asc, name asc",
	)

	pv = pham_vi_don(user)
	khoa_phien = pv.get("custom_khoa_phong") if pv else None
	if khoa_phien:
		rows = [r for r in rows if not r.khoa_phong or r.khoa_phong == khoa_phien]

	if khoa_phong:
		rows = [r for r in rows if r.khoa_phong == khoa_phong]

	if vat_tu:
		kho_vt = frappe.db.get_value("Customer Warehouse Item", vat_tu, "kho")
		customer_vt = (
			frappe.db.get_value("Customer Warehouse", kho_vt, "customer") if kho_vt else None
		)
		# Important #3 — vat_tu không thuộc customer (kể cả không tồn tại)
		# thì coi như KHÔNG được gửi, không tạo oracle dò tồn tại xuyên bệnh
		# viện. Chỉ dựng tập máy cho phép khi tenant khớp.
		if customer_vt == customer:
			may_cho_phep = {
				r.thiet_bi for r in frappe.get_all(
					"Customer Warehouse Item Equipment",
					filters={"parent": vat_tu, "parenttype": "Customer Warehouse Item"},
					fields=["thiet_bi"],
				)
			}
			if may_cho_phep:
				rows = [r for r in rows if r.name in may_cho_phep]

	if tim_kiem:
		hay = similarity.khong_dau(tim_kiem)
		rows = [
			r for r in rows
			if hay in similarity.khong_dau(r.ten_thiet_bi)
			or hay in similarity.khong_dau(r.ma_thiet_bi)
		]

	phan_trang = limit not in (None, "")
	tong = len(rows)
	if phan_trang:
		limit = frappe.utils.cint(limit)
		start = frappe.utils.cint(start)
		rows = rows[start:start + limit]

	ten_khoa = _ten_khoa({r.khoa_phong for r in rows})
	out = []
	for r in rows:
		d = _chuan_hoa_row(dict(r))
		d["ten_khoa_phong"] = ten_khoa.get(d["khoa_phong"], "")
		out.append(d)
	return {"rows": out, "tong": tong} if phan_trang else out


def save(customer: str, user: str, du_lieu: dict) -> dict:
	"""Tạo mới (thiếu `name`) hoặc sửa (`name` có giá trị). Module TỰ kiểm
	tenant tường minh trước khi ghi (Ràng buộc chung 1: DocPerm không bao
	giờ là cách sửa một PermissionError) rồi ghi bằng ignore_permissions=True.

	`khoa_phong`:
	  - TẠO MỚI: luôn tính qua `_khoa_ep_theo_phien()`, KỂ CẢ khi client
	    không gửi khoá này — một Nhân viên khoa tạo máy mới (kể cả qua
	    `tao_nhanh()`, vốn không có `khoa_phong` trong TRUONG_TAO_NHANH) vẫn
	    phải bị ép về khoa mình, không được lặng lẽ rơi vào "dùng chung" vì
	    thiếu khoá.
	  - SỬA: CHỈ tính lại khi `"khoa_phong" in du_lieu` — một sửa không liên
	    quan (đổi tên, tắt active) không được phép âm thầm đổi `khoa_phong`
	    của một máy DÙNG CHUNG (`khoa_phong` rỗng, thấy được bởi MỌI khoa)
	    thành một khoa cụ thể nào đó chỉ vì client quên gửi field này. Với
	    Nhân viên khoa, việc bỏ qua tầng "luôn ép" này ở nhánh sửa vẫn AN
	    TOÀN: `_chan_sua_ngoai_pham_vi()` đã chặn họ sửa bất kỳ máy nào
	    ngoài đúng khoa mình từ trước, nên nếu họ ĐẾN được đây, máy đang sửa
	    chắc chắn đã thuộc khoa họ."""
	name = du_lieu.get("name")
	if name:
		doc = frappe.get_doc("Customer Equipment", name)
		if doc.customer != customer:
			raise frappe.PermissionError("Máy không thuộc đơn vị của bạn.")
		_chan_sua_ngoai_pham_vi(user, name)
	else:
		doc = frappe.new_doc("Customer Equipment")
		doc.customer = customer

	for truong in TRUONG_NHAN_TU_CLIENT:
		if truong in du_lieu:
			setattr(doc, truong, du_lieu.get(truong))

	if doc.is_new():
		doc.khoa_phong = _khoa_ep_theo_phien(user, du_lieu.get("khoa_phong"))
	elif "khoa_phong" in du_lieu:
		doc.khoa_phong = _khoa_ep_theo_phien(user, du_lieu.get("khoa_phong"))

	if "active" in du_lieu:
		doc.active = 1 if frappe.utils.cint(du_lieu.get("active")) else 0

	if doc.is_new():
		doc.insert(ignore_permissions=True)
	else:
		doc.save(ignore_permissions=True)

	return ra_dict(doc.name, customer)


def tao_nhanh(customer: str, user: str, du_lieu: dict) -> dict:
	""""Nhanh" nói về SỐ Ô client phải điền, KHÔNG nói về độ lỏng validate —
	đi qua ĐÚNG `save()`/validate() đầy đủ của `Customer Equipment` như form
	dài, chỉ giới hạn field nhận từ client về `TRUONG_TAO_NHANH`. Vì vậy
	cũng thừa hưởng đúng chốt "ép khoa theo phiên" của `save()` — xem
	docstring ở đó, đoạn "TẠO MỚI"."""
	du_lieu_gon = {k: du_lieu[k] for k in TRUONG_TAO_NHANH if k in du_lieu}
	return save(customer, user, du_lieu_gon)


def gan_vao_vat_tu(vat_tu: str, thiet_bi: str) -> dict:
	"""Gắn một máy vào bảng "Máy sử dụng" của vật tư — IDEMPOTENT (Ràng buộc
	chung 4): gọi hai lần không sinh dòng thứ hai. Bảng này là DANH MỤC
	TƯƠNG THÍCH thuần tuý, không tham gia phép cộng số lượng nào (Ràng buộc
	chung 3).

	Chữ ký KHÔNG có `customer`/`user` (khác mọi hàm khác trong module này) —
	nơi gọi có thể là một luồng nội bộ (vd. gắn máy ngay từ màn "Tạo nhanh
	thiết bị" của form vật tư) không luôn có sẵn cả hai. Vì vậy hàm TỰ suy
	tenant từ HAI ĐẦU (kho của vật tư -> customer của kho; customer của máy)
	và CHẶN khi lệch — không có bước này, gọi hàm với một `thiet_bi` của
	bệnh viện khác sẽ gắn xuyên bệnh viện trong im lặng."""
	kho = frappe.db.get_value("Customer Warehouse Item", vat_tu, "kho")
	customer_vt = frappe.db.get_value("Customer Warehouse", kho, "customer") if kho else None
	customer_tb = frappe.db.get_value("Customer Equipment", thiet_bi, "customer")
	if not customer_vt or not customer_tb or customer_vt != customer_tb:
		raise frappe.PermissionError("Máy và vật tư không cùng đơn vị.")

	doc = frappe.get_doc("Customer Warehouse Item", vat_tu)
	da_co = any(r.thiet_bi == thiet_bi for r in (doc.get("may_su_dung") or []))
	if not da_co:
		doc.append("may_su_dung", {"thiet_bi": thiet_bi})
		doc.save(ignore_permissions=True)

	from miyano_portal.kho import vat_tu as vat_tu_mod

	return vat_tu_mod.ra_dict(doc.name)
