"""Nhập nhân sự bệnh viện từ tệp Excel — tạo tài khoản, khoa phòng, phân quyền.

Task 15 (QĐ-G17…G23). Khuôn BA BƯỚC lấy nguyên của `api/kho.py`
(`kho_import_template` → `kho_import_preview` → `kho_import_commit`), chỉ khác
chỗ đứng: màn này nằm trong **Desk của Miyano**, không phải SPA của khách.
Không đẻ khuôn thứ ba.

Bốn điều đáng nhớ trước khi sửa file này:

1. **Khách hàng CHỌN TRÊN MÀN HÌNH, không nằm trong tệp** (QĐ-G18). Bộ cột cố
   ý KHÔNG có "tên bệnh viện": một cột gõ tay là đường để nhập nhầm người của
   viện này sang viện khác — đúng thứ cơ chế cách ly dữ liệu sinh ra để chặn.
2. **Bước xem trước là chốt chính, không phải trang trí.** Tạo tài khoản đăng
   nhập là việc khó lùi. `_phan_tich()` KHÔNG GHI GÌ, và nó phải đoán trước
   TẤT CẢ các chốt mà `PortalMember.validate()`/`CustomerDepartment.validate()`
   sẽ nổ lúc ghi — một lần "xem trước bảo được, commit nổ giữa chừng" là đúng
   kiểu hỏng mà task này sinh ra để dẹp.
3. **Tất-cả-hoặc-không cho dòng BỊ TỪ CHỐI** (cùng khuôn `import_ton_dau`),
   nhưng dòng *cảnh báo* (QĐ-G23) thì không chặn ai — nó chỉ báo và để Miyano
   quyết.
4. **Mật khẩu trả về ĐÚNG MỘT LẦN** trong kết quả của `commit` (QĐ-G19).
   Không ghi vào tệp, không gửi email, không ghi vào log/Comment/Error Log.
"""

import io
import secrets
import unicodedata

import frappe
from frappe.utils.password import update_password
from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter

# Dùng lại NGUYÊN phép kiểm sở hữu tệp của đường import kho (`api/kho.py`):
# tra File bằng `file_url`, so `owner` với người đang gọi, ép đuôi .xlsx, và
# trả mọi lỗi bằng tiếng Việt không lộ tên doctype. Một bản sao thứ hai của
# phép kiểm đó là một chỗ nữa để quên vá.
from miyano_portal.api.kho import _resolve_owned_spreadsheet
from miyano_portal.api.portal import chan_neu_khong_phai_nhan_vien_miyano, portal_provision
from miyano_portal.kho import import_ton_dau, similarity
from miyano_portal.miyano_portal.doctype.portal_member.portal_member import (
	NHAN_VIEN_KHOA,
	QUAN_LY,
)

# (nhãn cột hiển thị, tên field nội bộ) — MỘT bộ cột duy nhất cho cả ba việc:
# sinh tệp mẫu, đọc tệp xem trước, đọc tệp lúc ghi.
COLUMNS = [
	("Họ tên", "ho_ten"),
	("Email", "email"),
	("Khoa", "ten_khoa"),
	("Mã khoa", "ma_khoa"),
	("Vai trò", "vai_tro"),
]

# Cột bắt buộc phải CÓ MẶT trong header. "Khoa"/"Mã khoa" không bắt buộc có
# mặt vì một tệp toàn Quản lý là hợp lệ (Quản lý nhìn toàn viện).
REQUIRED_HEADER = {"ho_ten", "email", "vai_tro"}

VAI_TRO_HOP_LE = (QUAN_LY, NHAN_VIEN_KHOA)

# Trạng thái của một dòng ở bước xem trước — đúng bốn thứ mà người ngồi duyệt
# tệp cần phân biệt.
TAO_MOI = "tao_moi"
BO_QUA = "bo_qua"
CANH_BAO = "canh_bao"
TU_CHOI = "tu_choi"


def _norm(value) -> str:
	if value is None:
		return ""
	return unicodedata.normalize("NFC", str(value)).strip()


# ---------------------------------------------------------------------------
# Bước 1 — tệp mẫu
# ---------------------------------------------------------------------------


def build_template_bytes() -> bytes:
	"""Tệp mẫu .xlsx: đúng 5 cột theo thứ tự COLUMNS, kèm hai dòng ví dụ (một
	cho mỗi vai trò — dòng Quản lý CỐ Ý để trống Khoa/Mã khoa để người điền
	thấy ngay rằng đó là hợp lệ).

	Tải mẫu xuống rồi nạp lại ngay (không sửa gì) phải đi lọt bước xem trước —
	cùng cam kết như tệp mẫu của kho, xem `import_ton_dau.build_template_bytes`.
	"""
	wb = Workbook()
	ws = wb.active
	ws.title = "Nhân sự"
	ws.append([label for label, _ in COLUMNS])
	for cell in ws[1]:
		cell.font = Font(bold=True)
	ws.append(["Nguyễn Thị Hoa", "quanly@benhvien.example", "", "", QUAN_LY])
	ws.append([
		"Trần Văn Bình", "huyethoc@benhvien.example", "Huyết học", "HUYETHOC", NHAN_VIEN_KHOA,
	])
	for i, width in enumerate([26, 32, 24, 14, 18], start=1):
		ws.column_dimensions[get_column_letter(i)].width = width
	buf = io.BytesIO()
	wb.save(buf)
	return buf.getvalue()


# ---------------------------------------------------------------------------
# Bước 2 — đọc và phân tích, KHÔNG GHI GÌ
# ---------------------------------------------------------------------------


def _kiem_khach(customer) -> str:
	customer = _norm(customer)
	if not customer or not frappe.db.exists("Customer", customer):
		frappe.throw(
			"Không tìm thấy khách hàng để nhập nhân sự. Chọn lại bệnh viện trên màn hình.",
			frappe.ValidationError,
		)
	return customer


def _kiem_ma_khoa(ma: str) -> str | None:
	"""Soi trước ĐÚNG các luật của `CustomerDepartment._chuan_hoa_ma_khoa()`.

	Cố ý là một BẢN SOI, không phải bản sao thứ hai của luật: nguồn sự thật
	vẫn là controller (nó vẫn chạy lúc `insert`). Chỗ này chỉ để bước xem
	trước nói ra được lỗi TRƯỚC khi ai đó bấm Ghi — nếu controller đổi luật
	mà quên chỗ này, hậu quả là commit nổ và savepoint quay lại, không phải
	dữ liệu sai lọt xuống.
	"""
	if len(ma) > 20:
		return "Mã khoa không được quá 20 ký tự."
	if not ma.isalnum() or not ma.isascii():
		return "Mã khoa chỉ được dùng chữ cái không dấu và chữ số (ví dụ HUYETHOC)."
	if ma in {"CHUNG"}:
		return f'"{ma}" là mã dành riêng của hệ thống, không đặt cho khoa phòng được.'
	return None


def _tim_khoa_da_co(khoa_hien_co: list, ten: str, ma: str) -> tuple[dict | None, str | None]:
	"""Khớp một ô Khoa/Mã khoa trong tệp với khoa phòng ĐÃ CÓ của bệnh viện.

	Mã khoa có tiếng nói cuối cùng khi cả hai cùng có: nó là định danh, tên là
	chữ tự do. So tên không dấu, cùng phép so `_chan_trung_tuyet_doi()` của
	`Customer Department` dùng — nếu so lệch nhau, tệp sẽ "tạo khoa mới" ở xem
	trước rồi vỡ vì trùng tên lúc ghi.
	"""
	if ma:
		for row in khoa_hien_co:
			if (row.get("ma_khoa") or "").upper() == ma:
				return row, None
	if ten:
		for row in khoa_hien_co:
			if similarity.la_trung_tuyet_doi(ten, row.get("ten_khoa_phong")):
				ma_cu = (row.get("ma_khoa") or "").upper()
				if ma and ma_cu and ma_cu != ma:
					return None, (
						f'Khoa "{row["ten_khoa_phong"]}" của bệnh viện này đang mang mã '
						f'"{ma_cu}", không khớp Mã khoa "{ma}" trong tệp.'
					)
				return row, None
	return None, None


def _phan_tich(content: bytes, customer: str) -> dict:
	"""Đọc và kiểm toàn bộ tệp, KHÔNG GHI GÌ vào database.

	Trả verdict theo khuôn `previewing-imports-before-writing`: MỖI dòng của
	tệp đều có mặt trong `rows` kèm số dòng gốc (1-based, tính cả header) và
	một trạng thái nói rõ *sẽ tạo / bỏ qua vì đã có / chỉ cảnh báo / bị từ
	chối vì lý do gì* — không dòng nào biến mất lặng lẽ.
	"""
	ws = import_ton_dau.mo_workbook(content)
	header_row, col_index = import_ton_dau.read_header(ws, COLUMNS, REQUIRED_HEADER)

	khoa_hien_co = frappe.get_all(
		"Customer Department",
		filters={"customer": customer},
		fields=["name", "ten_khoa_phong", "ma_khoa", "active"],
	)
	quan_ly_hien_co = frappe.db.get_value(
		"Portal Member", {"customer": customer, "vai_tro": QUAN_LY, "active": 1}, "user"
	)
	co_ma_ngan = bool(frappe.db.get_value("Customer", customer, "custom_ma_ngan"))

	rows: list[dict] = []
	khoa_se_tao: list[dict] = []
	email_da_gap: dict[str, int] = {}
	quan_ly_trong_tep: dict | None = None
	loi_toan_tep: list[str] = []
	canh_bao_toan_tep: list[str] = []

	for line, row_cells in enumerate(
		ws.iter_rows(min_row=header_row + 1, max_row=ws.max_row), start=header_row + 1
	):
		raw = {field: _cell(row_cells, col) for field, col in col_index.items()}
		if all(v is None or (isinstance(v, str) and not v.strip()) for v in raw.values()):
			continue  # dòng trắng hoàn toàn — bỏ qua, không tính vào tổng

		ho_ten = _norm(raw.get("ho_ten"))
		email = _norm(raw.get("email")).lower()
		ten_khoa = _norm(raw.get("ten_khoa"))
		ma_khoa = _norm(raw.get("ma_khoa")).upper()
		vai_tro_raw = _norm(raw.get("vai_tro"))

		dong = {
			"line": line, "ho_ten": ho_ten, "email": email, "ten_khoa": ten_khoa,
			"ma_khoa": ma_khoa, "vai_tro": "", "khoa": None, "khoa_moi": False,
			"khoa_key": None, "trang_thai": TAO_MOI, "errors": [], "ghi_chu": "",
		}
		rows.append(dong)
		errors = dong["errors"]

		# --- (a) chốt hình thức -------------------------------------------
		if not ho_ten:
			errors.append("Thiếu Họ tên")
		if not email:
			errors.append("Thiếu Email")
		elif not frappe.utils.validate_email_address(email):
			errors.append(f'Email không hợp lệ: "{email}"')
		elif email in email_da_gap:
			errors.append(f"Email này đã có ở dòng {email_da_gap[email]} trong tệp")
		elif email:
			email_da_gap[email] = line

		vai_tro = next(
			(v for v in VAI_TRO_HOP_LE if similarity.la_trung_tuyet_doi(vai_tro_raw, v)), None
		)
		if not vai_tro:
			errors.append(
				f'Vai trò không hợp lệ: "{vai_tro_raw}" — chỉ nhận "{QUAN_LY}" hoặc '
				f'"{NHAN_VIEN_KHOA}"'
			)
		dong["vai_tro"] = vai_tro or vai_tro_raw
		if errors:
			dong["trang_thai"] = TU_CHOI
			continue

		# --- (b) email này đã là ai chưa? ----------------------------------
		# Gõ nhầm email NỘI BỘ Miyano vào tệp của bệnh viện là một tai nạn có
		# bán kính rộng: `portal_provision` sẽ gắn `User Permission` trên
		# Customer cho tài khoản đó, và một System User bị giới hạn theo một
		# khách hàng sẽ mất tầm nhìn ở khắp ERPNext — hỏng theo kiểu rất khó
		# lần ra nguyên nhân. Chặn ở đây, không phải sau khi đã ghi.
		if frappe.db.get_value("User", email, "user_type") == "System User":
			errors.append(
				f'"{email}" là tài khoản nội bộ (System User) trên hệ thống Miyano, '
				"không cấp làm tài khoản cổng của bệnh viện được."
			)
			dong["trang_thai"] = TU_CHOI
			continue
		khach_dang_thuoc = frappe.db.get_value("Portal Member", {"user": email}, "customer")
		if khach_dang_thuoc and khach_dang_thuoc != customer:
			# QĐ-G23 — có thể là người thật làm ở hai nơi, cũng có thể là gõ
			# nhầm. KHÔNG tạo lại, KHÔNG đổi mật khẩu của họ, không chặn các
			# dòng khác: báo và để Miyano quyết.
			dong["trang_thai"] = CANH_BAO
			errors.append(
				f'Email này đã thuộc khách hàng "{khach_dang_thuoc}" — không tạo lại và '
				"không đổi mật khẩu của họ. Kiểm tra lại: gõ nhầm, hay đúng là một người "
				"làm ở hai nơi?"
			)
			continue
		if khach_dang_thuoc == customer:
			dong["trang_thai"] = BO_QUA
			dong["ghi_chu"] = "Đã có tài khoản ở bệnh viện này — bỏ qua, không đụng tới."
			continue

		# --- (c) chốt nghiệp vụ --------------------------------------------
		if vai_tro == QUAN_LY:
			if ten_khoa or ma_khoa:
				errors.append(
					"Quản lý nhìn xuyên mọi khoa nên không gắn vào khoa phòng nào. "
					"Bỏ trống cột Khoa và Mã khoa."
				)
			elif quan_ly_hien_co:
				errors.append(
					f"Bệnh viện này đã có quản lý là {quan_ly_hien_co}. Tắt thành viên đó "
					f'trước, hoặc đặt tài khoản này là "{NHAN_VIEN_KHOA}".'
				)
			elif quan_ly_trong_tep:
				errors.append(
					f"Tệp đã có một Quản lý ở dòng {quan_ly_trong_tep['line']} "
					f"({quan_ly_trong_tep['email']}) — mỗi bệnh viện chỉ một quản lý."
				)
			else:
				quan_ly_trong_tep = dong
		else:
			if not co_ma_ngan:
				errors.append(
					f'Khách hàng "{customer}" chưa có Mã ngắn — đặt Mã ngắn cho bệnh viện '
					"trước khi cấp tài khoản theo khoa phòng."
				)
			if not ten_khoa and not ma_khoa:
				errors.append(
					f"{NHAN_VIEN_KHOA} phải được gán một khoa phòng — điền cột Khoa "
					"(và Mã khoa nếu có)."
				)
			else:
				da_co, loi_khoa = _tim_khoa_da_co(khoa_hien_co, ten_khoa, ma_khoa)
				if loi_khoa:
					errors.append(loi_khoa)
				elif da_co:
					dong["khoa"] = da_co["name"]
					dong["ten_khoa"] = da_co["ten_khoa_phong"]
					if not da_co.get("active"):
						dong["ghi_chu"] = (
							f'Khoa "{da_co["ten_khoa_phong"]}" đang TẮT — bật lại nếu vẫn dùng.'
						)
				else:
					errors.extend(_ghi_nhan_khoa_moi(dong, khoa_se_tao, ten_khoa, ma_khoa))

		if errors:
			dong["trang_thai"] = TU_CHOI

	if not co_ma_ngan and any(
		r["vai_tro"] == NHAN_VIEN_KHOA and r["trang_thai"] in (TAO_MOI, TU_CHOI) for r in rows
	):
		loi_toan_tep.append(
			f'Khách hàng "{customer}" chưa có Mã ngắn. Đặt Mã ngắn trên hồ sơ khách hàng '
			"rồi nhập lại — mã ngắn đi vào tên phiếu Đề nghị mua của khoa phòng."
		)
	se_co_quan_ly = quan_ly_trong_tep is not None and quan_ly_trong_tep["trang_thai"] == TAO_MOI
	if not quan_ly_hien_co and not se_co_quan_ly:
		canh_bao_toan_tep.append(
			"Tệp này không tạo Quản lý nào và bệnh viện cũng chưa có quản lý đang hoạt "
			"động — sẽ không ai duyệt được phiếu Đề nghị mua của các khoa."
		)

	dem = {trang_thai: 0 for trang_thai in (TAO_MOI, BO_QUA, CANH_BAO, TU_CHOI)}
	for row in rows:
		dem[row["trang_thai"]] += 1
	# Khoa mới chỉ còn ý nghĩa nếu dòng dẫn tới nó không bị từ chối vì lý do khác.
	khoa_se_tao = [k for k in khoa_se_tao if any(
		r["trang_thai"] == TAO_MOI and r["khoa_moi"] and r["khoa_key"] == k["key"] for r in rows
	)]
	return {
		"customer": customer,
		"total": len(rows),
		"so_tao_moi": dem[TAO_MOI],
		"so_bo_qua": dem[BO_QUA],
		"so_canh_bao": dem[CANH_BAO],
		"so_tu_choi": dem[TU_CHOI],
		"rows": rows,
		"khoa_se_tao": khoa_se_tao,
		"loi_toan_tep": loi_toan_tep,
		"canh_bao_toan_tep": canh_bao_toan_tep,
	}


def _ghi_nhan_khoa_moi(dong: dict, khoa_se_tao: list[dict], ten: str, ma: str) -> list[str]:
	"""QĐ-G20: khoa chưa có thì tự tạo — nhưng phải NÓI RÕ ở bước xem trước.

	Gộp các dòng cùng trỏ về một khoa mới (theo mã, hoặc theo tên không dấu)
	để tệp có 30 người của khoa Huyết học không đẻ ra 30 khoa.
	"""
	errors: list[str] = []
	if not ten:
		return [
			f'Mã khoa "{ma}" chưa có trong danh mục khoa phòng của bệnh viện. Điền thêm '
			"cột Khoa (tên khoa) nếu muốn tạo mới."
		]
	if ma:
		loi_ma = _kiem_ma_khoa(ma)
		if loi_ma:
			return [loi_ma]
	for muc in khoa_se_tao:
		trung_ma = bool(ma) and muc["ma_khoa"] == ma
		trung_ten = similarity.la_trung_tuyet_doi(ten, muc["ten_khoa_phong"])
		if trung_ma or trung_ten:
			if trung_ma and not trung_ten:
				errors.append(
					f'Mã khoa "{ma}" đang dùng cho hai tên khoa khác nhau trong cùng tệp: '
					f'"{muc["ten_khoa_phong"]}" và "{ten}".'
				)
				return errors
			dong["khoa_moi"] = True
			dong["khoa_key"] = muc["key"]
			return errors
	key = f"{len(khoa_se_tao)}|{ma or similarity.khong_dau(ten)}"
	khoa_se_tao.append({"key": key, "ten_khoa_phong": ten, "ma_khoa": ma})
	dong["khoa_moi"] = True
	dong["khoa_key"] = key
	return errors


def _cell(row_cells, col: int):
	idx = col - 1
	return row_cells[idx].value if idx < len(row_cells) else None


# ---------------------------------------------------------------------------
# Bước 3 — ghi thật
# ---------------------------------------------------------------------------


def _sinh_mat_khau() -> str:
	"""Mật khẩu bàn giao tay: 12 ký tự, bỏ các ký tự dễ đọc nhầm khi chép ra
	giấy (0/O, 1/l/I). `secrets` chứ không phải `random` — đây là bí mật đăng
	nhập, không phải một con số ngẫu nhiên cho vui."""
	bang = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789"
	return "".join(secrets.choice(bang) for _ in range(12))


def _ghi(content: bytes, customer: str) -> dict:
	"""Đọc lại TỪ ĐẦU trên server (không tin dữ liệu client gửi), rồi ghi.

	Dòng BỊ TỪ CHỐI khiến KHÔNG GÌ được ghi — tất-cả-hoặc-không, cùng khuôn
	`import_ton_dau.commit_workbook`. Dòng CẢNH BÁO (QĐ-G23) thì không chặn ai:
	nó được nhắc lại nguyên vẹn trong kết quả để cờ đó không rơi mất giữa hai
	bước.
	"""
	ket_qua = _phan_tich(content, customer)
	if ket_qua["so_tu_choi"]:
		dau_tien = next(r for r in ket_qua["rows"] if r["trang_thai"] == TU_CHOI)
		frappe.throw(
			f"Tệp có {ket_qua['so_tu_choi']} dòng bị từ chối trong tổng số "
			f"{ket_qua['total']} dòng (ví dụ dòng {dau_tien['line']}: "
			f"{'; '.join(dau_tien['errors'])}). Vui lòng sửa và tải lại — "
			"chưa có dữ liệu nào được ghi.",
			frappe.ValidationError,
		)

	mat_khau: dict[str, str] = {}
	khoa_da_tao: list[dict] = []
	sp = "nhan_su_import_commit_sp"
	frappe.db.savepoint(sp)
	try:
		key_to_khoa: dict[str, str] = {}
		for muc in ket_qua["khoa_se_tao"]:
			kp = frappe.get_doc({
				"doctype": "Customer Department", "customer": customer,
				"ten_khoa_phong": muc["ten_khoa_phong"], "ma_khoa": muc["ma_khoa"] or None,
				"active": 1,
			})
			kp.insert(ignore_permissions=True)
			key_to_khoa[muc["key"]] = kp.name
			khoa_da_tao.append({
				"name": kp.name, "ten_khoa_phong": kp.ten_khoa_phong, "ma_khoa": kp.ma_khoa or "",
			})

		for dong in ket_qua["rows"]:
			if dong["trang_thai"] != TAO_MOI:
				continue
			khoa = dong["khoa"] or key_to_khoa.get(dong["khoa_key"])
			# Tài khoản ĐÃ TỒN TẠI (User có sẵn nhưng chưa thuộc bệnh viện
			# nào) chỉ được GẮN vào bệnh viện này — không đặt lại mật khẩu của
			# một người đang dùng tài khoản đó cho việc khác.
			la_nguoi_moi = not frappe.db.exists("User", dong["email"])
			portal_provision(
				customer, dong["email"], send_invite=False,
				first_name=dong["ho_ten"], vai_tro=dong["vai_tro"], khoa_phong=khoa,
			)
			dong["khoa"] = khoa
			if la_nguoi_moi:
				mk = _sinh_mat_khau()
				update_password(dong["email"], mk)
				# "Bắt đổi ở lần đăng nhập đầu" (QĐ-G19): bản Frappe này chỉ
				# có chính sách theo SỐ NGÀY ở System Settings
				# (`force_user_to_reset_password`), không có cờ cho từng
				# người — đặt mốc đổi mật khẩu về quá khứ để chính sách đó
				# (khi bật) chộp đúng các tài khoản này ngay lần đăng nhập
				# đầu. Phải đặt SAU `update_password`.
				frappe.db.set_value(
					"User", dong["email"], "last_password_reset_date", "2000-01-01",
					update_modified=False,
				)
				mat_khau[dong["email"]] = mk
			else:
				dong["ghi_chu"] = (
					"Tài khoản đã tồn tại từ trước — chỉ gắn vào bệnh viện này, "
					"không đặt lại mật khẩu."
				)
	except Exception:
		frappe.db.rollback(save_point=sp)
		raise

	ket_qua["khoa_da_tao"] = khoa_da_tao
	ket_qua["mat_khau"] = mat_khau
	ket_qua.pop("khoa_se_tao", None)
	return ket_qua


# ---------------------------------------------------------------------------
# Ba endpoint của màn Desk
# ---------------------------------------------------------------------------


@frappe.whitelist()
def nhan_su_import_template() -> None:
	"""Tải bảng Excel để nhân viên bệnh viện điền."""
	chan_neu_khong_phai_nhan_vien_miyano()
	frappe.local.response.filename = "mau_nhap_nhan_su_benh_vien.xlsx"
	frappe.local.response.filecontent = build_template_bytes()
	frappe.local.response.type = "download"
	frappe.local.response.content_type = (
		"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
	)


@frappe.whitelist()
def nhan_su_import_preview(customer, file_url) -> dict:
	"""Đọc và phân tích tệp, KHÔNG GHI GÌ. Xem `_phan_tich`."""
	chan_neu_khong_phai_nhan_vien_miyano()
	customer = _kiem_khach(customer)
	return _phan_tich(_resolve_owned_spreadsheet(file_url), customer)


@frappe.whitelist()
def nhan_su_import_commit(customer, file_url) -> dict:
	"""Đọc lại VÀ kiểm lại từ đầu ở server rồi mới ghi — không tin bất kỳ dòng
	dữ liệu nào mà client (đã gọi xem trước trước đó) có thể gửi kèm.

	Khoá `mat_khau` trong kết quả là thứ DUY NHẤT mang mật khẩu vừa đặt, và
	nó chỉ đi đúng một chuyến về màn hình đang mở (QĐ-G19)."""
	chan_neu_khong_phai_nhan_vien_miyano()
	customer = _kiem_khach(customer)
	return _ghi(_resolve_owned_spreadsheet(file_url), customer)
