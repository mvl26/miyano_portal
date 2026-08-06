"""Engine ghi sổ kho khách hàng.

`Customer Stock Ledger Entry` là nguồn sự thật duy nhất: chỉ ghi thêm, không
sửa, không xoá. `Customer Stock Lot Balance` là cache dẫn xuất, tái dựng lại
được bất cứ lúc nào bằng rebuild_lot_balance().

Cố ý KHÔNG dùng Stock Ledger Entry / Bin của ERPNext: kho khách không thuộc
Company nào, và cả hai company của Miyano đều bật perpetual inventory nên mọi
bút toán kho ở đó đều chảy vào sổ kế toán của Miyano.
"""

import frappe

LOT_KHONG_CO = "KHONG-LO"

# Số lượng nhỏ hơn ngưỡng này coi như bằng 0, tránh rác do sai số dấu phẩy động
# tích luỹ qua nhiều lần cộng trừ.
EPS = 0.0005


def _lot_balance_name(kho: str, vat_tu: str, so_lo: str) -> str | None:
	return frappe.db.get_value(
		"Customer Stock Lot Balance",
		{"kho": kho, "vat_tu": vat_tu, "so_lo": so_lo},
		"name",
	)


def _current_qty(kho: str, vat_tu: str, so_lo: str) -> float:
	name = _lot_balance_name(kho, vat_tu, so_lo)
	if not name:
		return 0.0
	return float(frappe.db.get_value("Customer Stock Lot Balance", name, "so_luong") or 0)


def _ensure_non_negative(kho, vat_tu, so_lo, cu_qty, delta):
	"""Chặn một bút toán đẩy tồn của lô xuống âm.

	Tồn âm không chỉ vô nghĩa vật lý: nó còn âm thầm phá đơn giá bình quân gia
	quyền của lần nhập tiếp theo (cu_qty âm kéo don_gia lệch), và vì
	get_lot_balances() lọc so_luong > EPS nên một lô đang âm biến mất khỏi mọi
	báo cáo thay vì báo lỗi. Gọi ở hai điểm: post_lines() gọi trước khi insert
	dòng sổ (để không bao giờ ghi một dòng làm tồn âm vào sổ append-only,
	không xoá được), và _apply_to_balance() gọi lại làm lưới an toàn thứ hai
	cho rebuild_lot_balance() — nơi replay thẳng từ sổ, không đi qua
	post_lines().
	"""
	moi_qty = cu_qty + float(delta)
	if moi_qty < -EPS:
		frappe.throw(
			f"Không đủ tồn để xuất lô {so_lo} (vật tư {vat_tu}, kho {kho}): "
			f"tồn hiện có {cu_qty}, yêu cầu xuất {abs(float(delta))}.",
			frappe.ValidationError,
		)


def _apply_to_balance(kho, vat_tu, so_lo, han_su_dung, delta, don_gia):
	"""Cộng `delta` vào tồn của một lô và cập nhật đơn giá.

	Nhập (delta > 0) làm đơn giá lô thành bình quân gia quyền của các lần nhập.
	Xuất (delta < 0) không đổi đơn giá — giá vốn xuất chính là đơn giá đang có
	của lô, đó là toàn bộ lý do sổ này theo lô thay vì cần engine định giá.
	"""
	name = _lot_balance_name(kho, vat_tu, so_lo)
	if name:
		bal = frappe.get_doc("Customer Stock Lot Balance", name)
	else:
		bal = frappe.new_doc("Customer Stock Lot Balance")
		bal.kho = kho
		bal.vat_tu = vat_tu
		bal.so_lo = so_lo
		bal.so_luong = 0
		bal.don_gia = 0

	cu_qty = float(bal.so_luong or 0)
	_ensure_non_negative(kho, vat_tu, so_lo, cu_qty, delta)
	moi_qty = cu_qty + float(delta)

	if delta > 0:
		tong = cu_qty + float(delta)
		if tong > EPS:
			bal.don_gia = (
				cu_qty * float(bal.don_gia or 0) + float(delta) * float(don_gia)
			) / tong
		else:
			bal.don_gia = float(don_gia)

	bal.so_luong = 0.0 if abs(moi_qty) < EPS else moi_qty
	# Hạn dùng ghi lần đầu; lần nhập sau của cùng lô không được ghi đè bằng
	# giá trị rỗng, nhưng được phép bổ sung nếu trước đó chưa có.
	if han_su_dung and not bal.han_su_dung:
		bal.han_su_dung = han_su_dung
	bal.gia_tri = float(bal.so_luong) * float(bal.don_gia or 0)
	bal.flags.ignore_permissions = True
	bal.save(ignore_permissions=True)


def post_lines(voucher, lines: list[dict]) -> list[str]:
	"""Ghi các dòng của một phiếu vào sổ và cập nhật tồn theo lô.

	`so_luong` trong mỗi dòng đã mang dấu: dương là nhập, âm là xuất.
	Bỏ qua dòng đã ghi rồi (khoá theo `chung_tu_row`) nên gọi lại an toàn.
	"""
	created = []
	for line in lines:
		row_id = line["chung_tu_row"]
		if frappe.db.exists(
			"Customer Stock Ledger Entry",
			{
				"chung_tu_type": voucher.doctype,
				"chung_tu": voucher.name,
				"chung_tu_row": row_id,
			},
		):
			continue

		so_luong = float(line["so_luong"])
		don_gia = float(line.get("don_gia") or 0)

		# Chặn TRƯỚC khi insert dòng sổ: sổ là append-only, không xoá được, nên
		# nếu chặn muộn hơn (trong _apply_to_balance, sau insert) một dòng làm
		# tồn âm sẽ đã nằm vĩnh viễn trong sổ trước khi lỗi được ném ra.
		_ensure_non_negative(
			voucher.kho, line["vat_tu"], line["so_lo"],
			_current_qty(voucher.kho, line["vat_tu"], line["so_lo"]), so_luong,
		)

		entry = frappe.new_doc("Customer Stock Ledger Entry")
		entry.kho = voucher.kho
		entry.ngay = voucher.ngay
		entry.vat_tu = line["vat_tu"]
		entry.so_lo = line["so_lo"]
		entry.han_su_dung = line.get("han_su_dung")
		entry.so_luong = so_luong
		entry.don_gia = don_gia
		entry.gia_tri = so_luong * don_gia
		entry.chung_tu_type = voucher.doctype
		entry.chung_tu = voucher.name
		entry.chung_tu_row = row_id
		entry.flags.ignore_permissions = True
		entry.insert(ignore_permissions=True)
		created.append(entry.name)

		_apply_to_balance(
			voucher.kho, line["vat_tu"], line["so_lo"],
			line.get("han_su_dung"), so_luong, don_gia,
		)
	return created


def get_lot_balance(kho: str, vat_tu: str, so_lo: str) -> dict | None:
	return frappe.db.get_value(
		"Customer Stock Lot Balance",
		{"kho": kho, "vat_tu": vat_tu, "so_lo": so_lo},
		["name", "so_luong", "don_gia", "han_su_dung"],
		as_dict=True,
	)


def get_lot_balances(kho: str, vat_tu: str) -> list[dict]:
	"""Các lô còn tồn của một vật tư, sắp theo FEFO.

	Hạn gần nhất xuất trước; lô không có hạn dùng xếp cuối vì không thể so sánh
	với lô có hạn — để chúng lên đầu sẽ khiến hàng sắp hết hạn nằm lại kho.
	"""
	rows = frappe.get_all(
		"Customer Stock Lot Balance",
		filters={"kho": kho, "vat_tu": vat_tu, "so_luong": [">", EPS]},
		fields=["name", "so_lo", "han_su_dung", "so_luong", "don_gia"],
	)
	return sorted(
		rows,
		key=lambda r: (r["han_su_dung"] is None, r["han_su_dung"] or "", r["so_lo"]),
	)


def mark_reversed(chung_tu_type: str, chung_tu: str) -> None:
	frappe.db.set_value(
		"Customer Stock Ledger Entry",
		{"chung_tu_type": chung_tu_type, "chung_tu": chung_tu},
		"da_dao",
		1,
		update_modified=False,
	)


def rebuild_lot_balance(kho: str | None = None) -> int:
	"""Dựng lại toàn bộ tồn theo lô từ sổ.

	Lưới an toàn khi nghi ngờ cache lệch sổ. Chạy được từ dòng lệnh:
	    bench --site <site> execute miyano_portal.kho.ledger.rebuild_lot_balance
	"""
	filters = {"kho": kho} if kho else {}
	frappe.db.delete("Customer Stock Lot Balance", filters)

	entries = frappe.get_all(
		"Customer Stock Ledger Entry",
		filters=filters,
		fields=["kho", "vat_tu", "so_lo", "han_su_dung", "so_luong", "don_gia"],
		# creation không đủ để làm tiebreaker duy nhất: dữ liệu di trú (xem
		# miyano_portal/migration/export_supplycore.py) có thể giữ nguyên
		# timestamp gốc và trùng creation giữa các dòng, hoặc hai insert rơi
		# cùng micro giây. _apply_to_balance không giao hoán trên don_gia nên
		# thứ tự replay phải xác định — dãy SKK-.######### tăng dần đơn điệu
		# nên dùng name làm tiebreaker.
		order_by="creation asc, name asc",
	)
	for e in entries:
		_apply_to_balance(
			e["kho"], e["vat_tu"], e["so_lo"], e["han_su_dung"],
			float(e["so_luong"]), float(e["don_gia"] or 0),
		)
	return frappe.db.count("Customer Stock Lot Balance", filters)
