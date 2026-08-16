"""Nạp 100 mặt hàng vật tư y tế + tồn kho vào kho Miyano — DỮ LIỆU TEST.

    bench --site erptest.local execute miyano_portal.setup.seed_100_vat_tu.chay

Dùng để có một danh mục đủ dày mà thử màn "Mua lẻ" (tìm kiếm toàn danh mục,
phân trang 10/20/50), thử kiểm hàng theo lô, và thử các báo cáo tồn kho.

**Idempotent**: chạy lại KHÔNG sinh mặt hàng trùng và KHÔNG cộng tồn hai lần.
Muốn nạp thêm tồn thì gọi `chay(them_ton=True)` — tường minh, vì cộng tồn âm
thầm mỗi lần chạy là cách nhanh nhất để mọi báo cáo sau này sai mà không ai
biết tại sao.

Mọi mặt hàng đều gắn `Item Default` công ty **Miyano Việt Nam** / kho **Kho
Miyano - MYN**. Site có hai pháp nhân, và bỏ trống mặc định là để lại đúng chỗ
lệch công ty đã từng phải đi dọn một lần.
"""

import frappe

COMPANY = "Miyano Việt Nam"
KHO = "Kho Miyano - MYN"
PRICE_LIST = "Standard Selling"
TIEN_TO = "MYN-"
DAU_HIEU_TON = "[seed_100_vat_tu] Tồn ban đầu 100 mặt hàng"

# (mã, tên, nhóm, ĐVT, đơn giá VND, theo lô?)
#
# `theo_lo=True` cho những thứ THẬT SỰ có hạn dùng trong nghề: hoá chất, sinh
# phẩm, dịch truyền, test nhanh, sát khuẩn. Không bật tràn lan — mỗi mặt hàng
# theo lô là một lần thủ kho phải chọn lô lúc xuất.
VAT_TU: list[tuple[str, str, str, str, int, bool]] = [
	# ---------------------------------------------------------------- Găng tay
	("GLOVE-NIT-S", "Găng tay khám nitrile size S – hộp 100 cái", "Găng tay", "Hộp", 95000, False),
	("GLOVE-NIT-L", "Găng tay khám nitrile size L – hộp 100 cái", "Găng tay", "Hộp", 95000, False),
	("GLOVE-LAT-M", "Găng tay khám latex có bột size M – hộp 100 cái", "Găng tay", "Hộp", 78000, False),
	("GLOVE-LAT-KB", "Găng tay khám latex không bột size M – hộp 100 cái", "Găng tay", "Hộp", 86000, False),
	("GLOVE-PT-7", "Găng tay phẫu thuật vô trùng số 7 – đôi", "Găng tay", "Đôi", 12000, True),
	("GLOVE-PT-75", "Găng tay phẫu thuật vô trùng số 7.5 – đôi", "Găng tay", "Đôi", 12000, True),
	# -------------------------------------------------------------- Khẩu trang
	("MASK-3L", "Khẩu trang y tế 3 lớp – hộp 50 cái", "Khẩu trang", "Hộp", 32000, False),
	("MASK-4L", "Khẩu trang y tế 4 lớp kháng khuẩn – hộp 50 cái", "Khẩu trang", "Hộp", 45000, False),
	("MASK-N95", "Khẩu trang N95 chuẩn NIOSH – hộp 20 cái", "Khẩu trang", "Hộp", 180000, False),
	("MASK-PT", "Khẩu trang phẫu thuật buộc dây – hộp 50 cái", "Khẩu trang", "Hộp", 52000, False),
	("MASK-TE", "Khẩu trang trẻ em 3 lớp – hộp 50 cái", "Khẩu trang", "Hộp", 30000, False),
	# ---------------------------------------------------------------- Băng gạc
	("GAUZE-5X5", "Gạc vô trùng 5×5cm – gói 10 miếng", "Băng gạc", "Gói", 8500, True),
	("GAUZE-10X10", "Gạc vô trùng 10×10cm – gói 10 miếng", "Băng gạc", "Gói", 14000, True),
	("GAUZE-15X15", "Gạc vô trùng 15×15cm – gói 10 miếng", "Băng gạc", "Gói", 22000, True),
	("GAUZE-CUON", "Băng gạc cuộn 10cm × 5m", "Băng gạc", "Cuộn", 9000, False),
	("BAND-CHUN", "Băng thun chun giãn 10cm × 4.5m", "Băng gạc", "Cuộn", 18000, False),
	("BAND-DINH", "Băng dính lụa y tế 2.5cm × 5m", "Băng gạc", "Cuộn", 7500, False),
	("BAND-CANHAN", "Băng keo cá nhân – hộp 100 miếng", "Băng gạc", "Hộp", 26000, False),
	("BAND-CAMMAU", "Gạc cầm máu alginate 10×10cm", "Băng gạc", "Miếng", 68000, True),
	("BAND-TRONGSUOT", "Băng dán trong suốt vô trùng 6×7cm", "Băng gạc", "Miếng", 5200, True),
	("BAND-TAMGIAC", "Băng tam giác sơ cứu", "Băng gạc", "Cái", 12000, False),
	# ------------------------------------------------------------- Bông y tế
	("COT-500", "Bông y tế tiệt trùng gói 500g", "Bông y tế", "Gói", 62000, False),
	("COT-100", "Bông y tế tiệt trùng gói 100g", "Bông y tế", "Gói", 15000, False),
	("COT-VIEN", "Bông viên tiệt trùng – hộp 100 viên", "Bông y tế", "Hộp", 28000, True),
	("COT-TAM", "Tăm bông vô trùng – gói 100 cái", "Bông y tế", "Gói", 19000, True),
	# --------------------------------------------------------------- Bơm tiêm
	("SYR-1", "Bơm tiêm 1ml (insulin) – hộp 100 cái", "Bơm tiêm", "Hộp", 120000, False),
	("SYR-3", "Bơm tiêm 3ml G23 – hộp 100 cái", "Bơm tiêm", "Hộp", 88000, False),
	("SYR-5", "Bơm tiêm 5ml G21 – hộp 100 cái", "Bơm tiêm", "Hộp", 98000, False),
	("SYR-20", "Bơm tiêm 20ml G18 – hộp 50 cái", "Bơm tiêm", "Hộp", 135000, False),
	("SYR-50", "Bơm tiêm 50ml đầu catheter – hộp 25 cái", "Bơm tiêm", "Hộp", 210000, False),
	("SYR-CHOAN", "Bơm cho ăn 60ml – cái", "Bơm tiêm", "Cái", 15000, False),
	("SYR-BOMTIEMDIEN", "Bơm tiêm điện 50ml chuyên dụng – cái", "Bơm tiêm", "Cái", 24000, False),
	("SYR-3P", "Bơm tiêm 3 chạc khoá – cái", "Bơm tiêm", "Cái", 8000, False),
	# ---------------------------------------------------------------- Kim tiêm
	("NEEDLE-18G", "Kim tiêm 18G – hộp 100 cái", "Kim tiêm", "Hộp", 42000, False),
	("NEEDLE-21G", "Kim tiêm 21G – hộp 100 cái", "Kim tiêm", "Hộp", 40000, False),
	("NEEDLE-23G", "Kim tiêm 23G – hộp 100 cái", "Kim tiêm", "Hộp", 40000, False),
	("NEEDLE-27G", "Kim tiêm 27G – hộp 100 cái", "Kim tiêm", "Hộp", 46000, False),
	("NEEDLE-LUON-20", "Kim luồn tĩnh mạch 20G – cái", "Kim tiêm", "Cái", 11000, True),
	("NEEDLE-BUOM-23", "Kim bướm lấy máu 23G – cái", "Kim tiêm", "Cái", 4500, True),
	# -------------------------------------------------------------- Dây truyền
	("TUBE-DICH", "Dây truyền dịch có bầu đếm giọt – bộ", "Dây truyền", "Bộ", 7500, True),
	("TUBE-MAU", "Dây truyền máu có lọc – bộ", "Dây truyền", "Bộ", 16000, True),
	("TUBE-OXY", "Dây thở oxy 2 nhánh – cái", "Dây truyền", "Cái", 9000, False),
	("TUBE-HUT", "Ống hút đờm 12Fr – cái", "Dây truyền", "Cái", 6500, False),
	("TUBE-SONDE", "Sonde dạ dày 16Fr – cái", "Dây truyền", "Cái", 18000, False),
	# -------------------------------------------------------------- Dịch truyền
	("IV-NACL-500", "Natri clorid 0.9% chai 500ml", "Nước muối sinh lý", "Chai", 12000, True),
	("IV-NACL-1000", "Natri clorid 0.9% túi 1000ml", "Nước muối sinh lý", "Túi", 19000, True),
	("IV-NACL-100", "Natri clorid 0.9% chai 100ml", "Nước muối sinh lý", "Chai", 7000, True),
	("IV-GLU5-500", "Glucose 5% chai 500ml", "Glucose", "Chai", 13000, True),
	("IV-GLU10-500", "Glucose 10% chai 500ml", "Glucose", "Chai", 15000, True),
	("IV-RINGER-500", "Ringer Lactate chai 500ml", "Ringer Lactate", "Chai", 14500, True),
	("IV-NUOCCAT-5", "Nước cất pha tiêm ống 5ml – hộp 100 ống", "Dịch truyền", "Hộp", 95000, True),
	("IV-NUOCCAT-10", "Nước cất pha tiêm ống 10ml – hộp 50 ống", "Dịch truyền", "Hộp", 78000, True),
	# -------------------------------------------------------------- Test nhanh
	("TEST-COVID", "Test nhanh kháng nguyên SARS-CoV-2 – hộp 25 test", "Test nhanh", "Hộp", 480000, True),
	("TEST-CUM", "Test nhanh cúm A/B – hộp 20 test", "Test nhanh", "Hộp", 520000, True),
	("TEST-SXH", "Test nhanh sốt xuất huyết NS1 – hộp 25 test", "Test nhanh", "Hộp", 610000, True),
	("TEST-HBSAG", "Test nhanh HBsAg – hộp 50 test", "Test nhanh", "Hộp", 340000, True),
	("TEST-HCV", "Test nhanh HCV – hộp 50 test", "Test nhanh", "Hộp", 420000, True),
	("TEST-HIV", "Test nhanh HIV 1/2 – hộp 30 test", "Test nhanh", "Hộp", 560000, True),
	("TEST-THAI", "Que thử thai nhanh – hộp 50 que", "Test nhanh", "Hộp", 145000, True),
	("TEST-MAUAN", "Test nhanh máu ẩn trong phân – hộp 25 test", "Test nhanh", "Hộp", 380000, True),
	# ------------------------------------------------------- Hoá chất sinh phẩm
	("CHEM-AST", "Hoá chất sinh hoá AST (GOT) – hộp 4×50ml", "Hóa chất sinh phẩm", "Hộp", 720000, True),
	("CHEM-GLU", "Hoá chất định lượng Glucose – hộp 4×50ml", "Hóa chất sinh phẩm", "Hộp", 650000, True),
	("CHEM-URE", "Hoá chất định lượng Ure – hộp 4×50ml", "Hóa chất sinh phẩm", "Hộp", 680000, True),
	("CHEM-CREA", "Hoá chất định lượng Creatinin – hộp 4×50ml", "Hóa chất sinh phẩm", "Hộp", 690000, True),
	("CHEM-CHOL", "Hoá chất định lượng Cholesterol – hộp 4×50ml", "Hóa chất sinh phẩm", "Hộp", 700000, True),
	("CHEM-TRIG", "Hoá chất định lượng Triglycerid – hộp 4×50ml", "Hóa chất sinh phẩm", "Hộp", 710000, True),
	("CHEM-CRP", "Hoá chất định lượng CRP – hộp 2×20ml", "Hóa chất sinh phẩm", "Hộp", 1250000, True),
	("CHEM-HBA1C", "Hoá chất định lượng HbA1c – hộp 2×20ml", "Hóa chất sinh phẩm", "Hộp", 1480000, True),
	("CHEM-CALIB", "Huyết thanh chuẩn đa thông số – lọ 5ml", "Hóa chất sinh phẩm", "Lọ", 890000, True),
	("CHEM-CONTROL", "Huyết thanh kiểm tra mức 1+2 – hộp 2×5ml", "Hóa chất sinh phẩm", "Hộp", 1150000, True),
	# ------------------------------------------------------------ Cồn/Sát khuẩn
	("ALC-70-500", "Cồn 70 độ chai 500ml", "Cồn y tế", "Chai", 22000, True),
	("ALC-90-500", "Cồn 90 độ chai 500ml", "Cồn y tế", "Chai", 24000, True),
	("ALC-IODINE", "Povidone iodine 10% chai 500ml", "Sát khuẩn", "Chai", 68000, True),
	("ALC-OXY", "Oxy già 3% chai 500ml", "Sát khuẩn", "Chai", 18000, True),
	("ALC-XATAY", "Dung dịch rửa tay nhanh 500ml", "Sát khuẩn", "Chai", 55000, True),
	("ALC-CHLORHEX", "Chlorhexidine 0.5% chai 500ml", "Sát khuẩn", "Chai", 92000, True),
	("ALC-TAMCON", "Tăm bông tẩm cồn – hộp 100 miếng", "Sát khuẩn", "Hộp", 24000, True),
	("ALC-CLOMIN", "Cloramin B bột khử khuẩn – gói 1kg", "Sát khuẩn", "Gói", 135000, True),
	# ------------------------------------------------------------ Vật tư bảo hộ
	("PPE-AOMO", "Áo mổ vô trùng dùng một lần – cái", "Vật tư bảo hộ", "Cái", 38000, False),
	("PPE-AOCHOANG", "Áo choàng cách ly không dệt – cái", "Vật tư bảo hộ", "Cái", 26000, False),
	("PPE-MUPT", "Mũ phẫu thuật không dệt – gói 100 cái", "Vật tư bảo hộ", "Gói", 42000, False),
	("PPE-BAOGIAY", "Bao giày y tế – gói 100 cái", "Vật tư bảo hộ", "Gói", 36000, False),
	("PPE-KINH", "Kính bảo hộ y tế chống giọt bắn – cái", "Vật tư bảo hộ", "Cái", 45000, False),
	("PPE-TAMCHAN", "Tấm chắn giọt bắn – cái", "Vật tư bảo hộ", "Cái", 18000, False),
	# ---------------------------------------------------------- Vật tư tiêu hao
	("CONS-LAMKINH", "Lam kính hiển vi – hộp 50 cái", "Vật tư tiêu hao", "Hộp", 32000, False),
	("CONS-LAMELLE", "Lamen phủ 22×22mm – hộp 100 cái", "Vật tư tiêu hao", "Hộp", 28000, False),
	("CONS-ONGNGHIEM", "Ống nghiệm EDTA 2ml – hộp 100 ống", "Vật tư tiêu hao", "Hộp", 165000, True),
	("CONS-ONGSINHHOA", "Ống nghiệm sinh hoá không chống đông 5ml – hộp 100 ống", "Vật tư tiêu hao", "Hộp", 148000, True),
	("CONS-DAUCON", "Đầu côn vàng 200µl – gói 1000 cái", "Vật tư tiêu hao", "Gói", 78000, False),
	("CONS-DAUCON-XANH", "Đầu côn xanh 1000µl – gói 500 cái", "Vật tư tiêu hao", "Gói", 92000, False),
	("CONS-COCNUOCTIEU", "Cốc đựng nước tiểu vô trùng 60ml – gói 100 cái", "Vật tư tiêu hao", "Gói", 88000, False),
	("CONS-HOPBENHPHAM", "Hộp vận chuyển bệnh phẩm 3 lớp – cái", "Vật tư tiêu hao", "Cái", 125000, False),
	("CONS-TUIRAC", "Túi rác y tế màu vàng 60L – gói 50 túi", "Vật tư tiêu hao", "Gói", 95000, False),
	("CONS-HOPKIM", "Hộp đựng vật sắc nhọn 5L – cái", "Vật tư tiêu hao", "Cái", 58000, False),
	# ------------------------------------------------- Vật tư thay thế / cấy ghép
	("IMP-STENT-3", "Stent mạch vành phủ thuốc 3.0×18mm", "Stent mạch", "Cái", 28500000, True),
	("IMP-STENT-35", "Stent mạch vành phủ thuốc 3.5×23mm", "Stent mạch", "Cái", 29800000, True),
	("IMP-KHOPHANG", "Khớp háng toàn phần không xi măng – bộ", "Khớp nhân tạo", "Bộ", 42000000, True),
	("IMP-KHOPGOI", "Khớp gối toàn phần – bộ", "Khớp nhân tạo", "Bộ", 48000000, True),
	("IMP-VIT-45", "Vít xương xốp 4.5mm – cái", "Vít/Đinh xương", "Cái", 850000, True),
	("IMP-NEP-8", "Nẹp khoá 8 lỗ titan – cái", "Vít/Đinh xương", "Cái", 4200000, True),
]

# Số lượng nhập theo nhóm — hàng cấy ghép giá vài chục triệu thì kho không ôm
# vài trăm cái, còn găng tay thì có. Tồn phi thực tế làm mọi báo cáo dự trù và
# đề xuất đặt hàng trở nên vô nghĩa để nhìn.
SL_THEO_NHOM = {
	"Stent mạch": 5, "Khớp nhân tạo": 3, "Vít/Đinh xương": 20,
	"Hóa chất sinh phẩm": 40, "Test nhanh": 60,
}
SL_MAC_DINH = 300

# Hạn dùng rải ra: vài lô sắp hết hạn để thử báo cáo "Cảnh báo hạn dùng", còn
# lại dài hạn. Một danh mục mà mọi lô cùng hạn thì không thử được gì.
HAN_DUNG_NGAY = (45, 120, 240, 400, 700)


def _dam_bao_uom(ten: str) -> None:
	if not frappe.db.exists("UOM", ten):
		frappe.get_doc({"doctype": "UOM", "uom_name": ten, "must_be_whole_number": 1}).insert(
			ignore_permissions=True
		)


def _dam_bao_nhom(ten: str) -> None:
	if frappe.db.exists("Item Group", ten):
		return
	cha = frappe.db.get_value("Item Group", {"is_group": 1, "parent_item_group": ["is", "not set"]}, "name")
	frappe.get_doc({
		"doctype": "Item Group", "item_group_name": ten,
		"parent_item_group": cha or "All Item Groups", "is_group": 0,
	}).insert(ignore_permissions=True)


def _tao_item(ma, ten, nhom, dvt, gia, theo_lo) -> bool:
	"""Trả True nếu vừa tạo mới."""
	code = TIEN_TO + ma
	if frappe.db.exists("Item", code):
		return False
	doc = frappe.get_doc({
		"doctype": "Item",
		"item_code": code,
		"item_name": ten,
		"item_group": nhom,
		"stock_uom": dvt,
		"is_stock_item": 1,
		"has_batch_no": 1 if theo_lo else 0,
		# `create_new_batch=0` — lô do người nhập chỉ định, không để ERPNext tự
		# sinh mã lô vô nghĩa. Cùng lựa chọn với dữ liệu demo sẵn có.
		"create_new_batch": 0,
		"has_expiry_date": 1 if theo_lo else 0,
		"description": ten,
	})
	doc.append("item_defaults", {"company": COMPANY, "default_warehouse": KHO})
	doc.insert(ignore_permissions=True)
	return True


def _dam_bao_gia(ma: str, gia: int) -> None:
	code = TIEN_TO + ma
	ten = frappe.db.get_value(
		"Item Price", {"item_code": code, "price_list": PRICE_LIST, "selling": 1}, "name"
	)
	if ten:
		return
	frappe.get_doc({
		"doctype": "Item Price", "item_code": code, "price_list": PRICE_LIST,
		"selling": 1, "price_list_rate": gia, "currency": "VND",
	}).insert(ignore_permissions=True)


def _ma_lo(ma: str) -> str:
	return f"LO-{ma}-2026"


def _dam_bao_lo(ma: str, i: int) -> str:
	code = TIEN_TO + ma
	lo = _ma_lo(ma)
	if not frappe.db.exists("Batch", lo):
		frappe.get_doc({
			"doctype": "Batch", "batch_id": lo, "item": code,
			"expiry_date": frappe.utils.add_days(
				frappe.utils.nowdate(), HAN_DUNG_NGAY[i % len(HAN_DUNG_NGAY)]
			),
		}).insert(ignore_permissions=True)
	return lo


def _da_nhap_ton() -> bool:
	return bool(frappe.db.exists("Stock Entry", {"remarks": DAU_HIEU_TON, "docstatus": 1}))


def _nhap_ton(lo_theo_ma: dict[str, str]) -> list[str]:
	"""Nhập tồn bằng Stock Entry "Material Receipt", chia lô 25 dòng.

	Chia nhỏ chứ không một phiếu 100 dòng: một dòng hỏng làm hỏng cả phiếu, và
	100 dòng thì không nhìn ra dòng nào hỏng. 25 dòng vừa đủ để lỗi khoanh
	được mà không sinh ra 100 chứng từ rác.
	"""
	ten_phieu = []
	for dau in range(0, len(VAT_TU), 25):
		khuc = VAT_TU[dau:dau + 25]
		se = frappe.new_doc("Stock Entry")
		se.stock_entry_type = "Material Receipt"
		se.company = COMPANY
		se.posting_date = frappe.utils.nowdate()
		se.remarks = DAU_HIEU_TON
		for ma, _ten, nhom, dvt, gia, theo_lo in khuc:
			dong = {
				"item_code": TIEN_TO + ma,
				"qty": SL_THEO_NHOM.get(nhom, SL_MAC_DINH),
				"t_warehouse": KHO,
				"uom": dvt,
				"stock_uom": dvt,
				"conversion_factor": 1,
				# Giá nhập = 70% giá bán — không để 0, vì `basic_rate=0` làm mọi
				# bút toán giá vốn và báo cáo tồn theo giá trị thành số 0.
				"basic_rate": int(gia * 0.7),
			}
			if theo_lo:
				dong["batch_no"] = lo_theo_ma[ma]
				dong["use_serial_batch_fields"] = 1
			se.append("items", dong)
		se.insert(ignore_permissions=True)
		se.submit()
		ten_phieu.append(se.name)
	return ten_phieu


def chay(them_ton: bool = False) -> dict:
	frappe.set_user("Administrator")

	moi = 0
	lo_theo_ma: dict[str, str] = {}
	for i, (ma, ten, nhom, dvt, gia, theo_lo) in enumerate(VAT_TU):
		_dam_bao_uom(dvt)
		_dam_bao_nhom(nhom)
		if _tao_item(ma, ten, nhom, dvt, gia, theo_lo):
			moi += 1
		_dam_bao_gia(ma, gia)
		if theo_lo:
			lo_theo_ma[ma] = _dam_bao_lo(ma, i)

	da_co = _da_nhap_ton()
	phieu = []
	if da_co and not them_ton:
		print(
			"Tồn đã nhập trước đó — BỎ QUA bước nhập kho.\n"
			"Muốn cộng thêm tồn: chay(them_ton=True)."
		)
	else:
		phieu = _nhap_ton(lo_theo_ma)

	frappe.db.commit()

	tong = frappe.db.count("Item", {"item_code": ["like", TIEN_TO + "%"], "disabled": 0})
	kq = {
		"mat_hang_moi": moi,
		"tong_mat_hang_MYN": tong,
		"theo_lo": sum(1 for v in VAT_TU if v[5]),
		"phieu_nhap": phieu,
	}
	print(
		f"\nTạo mới {moi} mặt hàng (tổng {tong} mã {TIEN_TO}*), "
		f"{kq['theo_lo']} mặt hàng theo lô có hạn dùng."
	)
	if phieu:
		print(f"Phiếu nhập kho: {', '.join(phieu)} → kho {KHO}")
	return kq
