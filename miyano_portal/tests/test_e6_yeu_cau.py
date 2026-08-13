"""E6 phần A — Yêu cầu hàng hoá (QT11). TC-E6-05, 06, 07, 08, 12
(40_TestCases.md); US-E6.3/E6.4/E6.6; BR-Y1…Y5; NL-11.1/11.2/11.3/11.6.

Cách ly cơ bản (mã hoá/không nhận `customer` từ client, phủ toàn bộ doctype
động của module) nằm ở test_kho_isolation.py — file này chỉ kiểm hành vi
nghiệp vụ riêng của E6.
"""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, get_datetime, now_datetime, nowdate

from miyano_portal import demand_pipeline
from miyano_portal.api import portal
from miyano_portal.portal_sla import (
    cong_gio_lam_viec,
    gio_lam_viec_troi_qua,
    quet_yeu_cau_qua_han,
    sla_yeu_cau_gio,
)
from miyano_portal.setup.seed_demo import seed_demo

CUSTOMER_BM = "Bệnh viện Bạch Mai"
CUSTOMER_PXN = "PXN ABC"
BM_USER = "bvbm@demo.miyano"
PXN_USER = "pxnabc@demo.miyano"
SALES_USER = "sales_user@demo.miyano"  # System User thật, có sẵn trên site,
# dùng chung với nhiều module test khác (xem test_e1_thieu_gia_va_reorder.py).
PURCHASE_USER = "purchase_user_e6@demo.miyano"

TRANG_THAI_KET_THUC = (
    "Đã chuyển thành đơn", "Không đáp ứng được", "Khách huỷ", "Hết hạn",
)


def _payload(**overrides):
    data = {
        "loai": "Tìm nguồn hàng mới",
        "ten_hang": "Que thử HbA1c",
        "dvt": "Hộp",
        "so_luong_du_kien": 20,
    }
    data.update(overrides)
    return data


_USER_CUA_KHACH = {CUSTOMER_BM: BM_USER, CUSTOMER_PXN: PXN_USER}


def _tao_yeu_cau(customer, **kw):
    """Dựng thẳng qua get_doc (bỏ qua endpoint) cho các test chỉ cần MỘT bản
    ghi hợp lệ ở trạng thái bất kỳ — nhanh hơn và không phụ thuộc hành vi
    portal_yeu_cau_save()."""
    data = {
        "doctype": "Portal Item Request",
        "customer": customer,
        "nguoi_yeu_cau": _USER_CUA_KHACH.get(customer, "test@demo.miyano"),
        "loai": "Tìm nguồn hàng mới",
        "ten_hang": "Yêu cầu mặc định test",
        "dvt": "Hộp",
        "so_luong_du_kien": 5,
    }
    data.update(kw)
    doc = frappe.get_doc(data)
    doc.insert(ignore_permissions=True)
    return doc


def _anh_jpeg_hop_le() -> bytes:
    """Frappe's File controller strips EXIF from image uploads (before_insert
    -> save_file -> strip_exif_data -> PIL.Image.open) — nội dung giả bất kỳ
    làm PIL ném UnidentifiedImageError trước khi test kịp chạm tới logic của
    chúng ta. Dựng một ảnh JPEG 2x2 thật, nhỏ nhất có thể, để vượt qua bước
    đó."""
    import io
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (2, 2), color=(200, 0, 0)).save(buf, format="JPEG")
    return buf.getvalue()


def _make_file(owner_user, filename, is_private=1, content=None, file_size=None):
    truoc = frappe.session.user
    frappe.set_user(owner_user)
    try:
        doc = frappe.get_doc({
            "doctype": "File",
            "file_name": filename,
            "content": content if content is not None else _anh_jpeg_hop_le(),
            "is_private": is_private,
        })
        doc.insert(ignore_permissions=True)
    finally:
        frappe.set_user(truoc)
    if file_size is not None:
        frappe.db.set_value("File", doc.name, "file_size", file_size, update_modified=False)
        doc.reload()
    return doc


def _ensure_purchase_user():
    """Fixture RIÊNG của module này — KHÔNG dùng vai trò Purchase User có sẵn
    trên site (nếu có), đúng bẫy #5 của brief: không đếm trên dữ liệu ngoài
    tầm kiểm soát của setUp. Idempotent, cùng khuôn _ensure_staff_user() của
    test_kho_isolation.py."""
    if not frappe.db.exists("User", PURCHASE_USER):
        frappe.get_doc({
            "doctype": "User", "email": PURCHASE_USER, "first_name": "Purchase",
            "user_type": "System User", "send_welcome_email": 0,
            "roles": [{"role": "Purchase User"}],
        }).insert(ignore_permissions=True)
    return PURCHASE_USER


# ---------------------------------------------------------------------------
# Doctype — BR-Y1 (máy trạng thái), BR-Y2 (lý do bắt buộc), BR-Y4 (không xoá)
# ---------------------------------------------------------------------------

class TestPortalItemRequestDoctype(FrappeTestCase):
    def setUp(self):
        seed_demo()

    def test_yeu_cau_moi_mac_dinh_trang_thai_moi(self):
        doc = _tao_yeu_cau(CUSTOMER_BM)
        self.assertEqual(doc.trang_thai, "Mới")
        self.assertTrue(doc.name.startswith("YCH-"))

    def test_khong_dap_ung_thieu_ly_do_bi_chan(self):  # TC-E6-08
        doc = _tao_yeu_cau(CUSTOMER_BM)
        doc.trang_thai = "Đang tìm nguồn"
        doc.save(ignore_permissions=True)
        doc.trang_thai = "Không đáp ứng được"
        with self.assertRaises(frappe.ValidationError):
            doc.save(ignore_permissions=True)

    def test_khong_dap_ung_co_ly_do_thi_luu_duoc(self):  # TC-E6-08
        doc = _tao_yeu_cau(CUSTOMER_BM)
        doc.trang_thai = "Đang tìm nguồn"
        doc.save(ignore_permissions=True)
        doc.trang_thai = "Không đáp ứng được"
        doc.ly_do_khong_dap_ung = "Không tìm được nguồn hàng phù hợp."
        doc.save(ignore_permissions=True)
        doc.reload()
        self.assertEqual(doc.trang_thai, "Không đáp ứng được")

    def test_chuyen_thang_tu_moi_sang_da_bao_gia_bi_chan(self):  # BR-Y1
        doc = _tao_yeu_cau(CUSTOMER_BM)
        doc.trang_thai = "Đã báo giá"
        with self.assertRaises(frappe.ValidationError):
            doc.save(ignore_permissions=True)

    def test_can_them_thong_tin_ve_lai_dang_tim_nguon_hop_le(self):  # BR-Y1
        doc = _tao_yeu_cau(CUSTOMER_BM)
        doc.trang_thai = "Đang tìm nguồn"
        doc.save(ignore_permissions=True)
        doc.trang_thai = "Cần thêm thông tin"
        doc.save(ignore_permissions=True)
        doc.trang_thai = "Đang tìm nguồn"
        doc.save(ignore_permissions=True)  # không ném — cạnh hai chiều hợp lệ
        doc.reload()
        self.assertEqual(doc.trang_thai, "Đang tìm nguồn")

    def test_trang_thai_ket_thuc_khong_chuyen_tiep_duoc(self):  # BR-Y1/BR-Y4
        doc = _tao_yeu_cau(CUSTOMER_BM)
        doc.trang_thai = "Khách huỷ"
        doc.save(ignore_permissions=True)
        doc.trang_thai = "Đang tìm nguồn"
        with self.assertRaises(frappe.ValidationError):
            doc.save(ignore_permissions=True)

    def test_khong_xoa_duoc_du_o_trang_thai_nao(self):  # BR-Y4
        doc = _tao_yeu_cau(CUSTOMER_BM)
        with self.assertRaises(frappe.ValidationError):
            frappe.delete_doc("Portal Item Request", doc.name, ignore_permissions=True)
        doc2 = _tao_yeu_cau(CUSTOMER_BM, ten_hang="Yêu cầu 2")
        doc2.trang_thai = "Khách huỷ"
        doc2.save(ignore_permissions=True)
        with self.assertRaises(frappe.ValidationError):
            frappe.delete_doc("Portal Item Request", doc2.name, ignore_permissions=True)

    def test_khong_docperm_cho_customer(self):
        for table in ("DocPerm", "Custom DocPerm"):
            rows = frappe.get_all(
                table, filters={"parent": "Portal Item Request", "role": "Customer"},
            )
            self.assertEqual(rows, [], table)

    def test_dinh_kien_ngay_can_qua_khu_bi_chan(self):
        with self.assertRaises(frappe.ValidationError):
            _tao_yeu_cau(CUSTOMER_BM, ngay_can=add_days(nowdate(), -1))

    def test_dinh_ky_thieu_chu_ky_bi_chan(self):
        with self.assertRaises(frappe.ValidationError):
            _tao_yeu_cau(CUSTOMER_BM, tan_suat="Định kỳ")


# ---------------------------------------------------------------------------
# portal_yeu_cau_save — TC-E6-05 (đính kèm), TC-E6-06 (trùng gần đúng),
# TC-E6-12 (cách ly qua endpoint sửa)
# ---------------------------------------------------------------------------

class TestPortalYeuCauSave(FrappeTestCase):
    def setUp(self):
        seed_demo()
        frappe.db.set_value("Customer", CUSTOMER_BM, "account_manager", SALES_USER)
        _ensure_purchase_user()
        frappe.db.delete(
            "Notification Log", {"subject": ("like", "Portal - Yêu cầu hàng hoá mới%")}
        )

    def tearDown(self):
        frappe.set_user("Administrator")

    def test_tao_moi_thanh_cong_va_suy_khach_tu_phien(self):
        frappe.set_user(BM_USER)
        out = portal.portal_yeu_cau_save(_payload())
        self.assertTrue(out["name"].startswith("YCH-"))
        doc = frappe.get_doc("Portal Item Request", out["name"])
        self.assertEqual(doc.customer, CUSTOMER_BM)
        self.assertEqual(doc.nguoi_yeu_cau, BM_USER)
        self.assertEqual(doc.trang_thai, "Mới")
        self.assertIsNotNone(doc.sla_den_han)

    def test_customer_trong_payload_bi_bo_qua(self):
        """Không endpoint nào nhận `customer` từ client — payload cố tình
        khai một khách khác vẫn phải bị ghi đè bằng khách của phiên."""
        frappe.set_user(BM_USER)
        out = portal.portal_yeu_cau_save(_payload(customer="PXN ABC"))
        doc = frappe.get_doc("Portal Item Request", out["name"])
        self.assertEqual(doc.customer, CUSTOMER_BM)

    def test_thieu_dvt_bi_chan_va_khong_tao_ban_ghi(self):  # TC-E6-05, ca 1
        frappe.set_user(BM_USER)
        payload = _payload(ten_hang="Yêu cầu thiếu ĐVT")
        del payload["dvt"]
        with self.assertRaises(frappe.ValidationError) as cm:
            portal.portal_yeu_cau_save(payload)
        self.assertIn("ĐVT", str(cm.exception))
        self.assertEqual(
            frappe.db.count(
                "Portal Item Request",
                {"customer": CUSTOMER_BM, "ten_hang": payload["ten_hang"]},
            ),
            0,
        )

    def test_qua_5_file_bi_chan(self):  # TC-E6-05, ca 2
        frappe.set_user(BM_USER)
        files = [_make_file(BM_USER, f"dinh_kem_{i}.jpg") for i in range(6)]
        with self.assertRaises(frappe.ValidationError) as cm:
            portal.portal_yeu_cau_save(
                _payload(), file_urls=[f.file_url for f in files]
            )
        self.assertIn("Tối đa 5 file", str(cm.exception))

    def test_file_qua_10mb_bi_chan(self):  # TC-E6-05, ca 3
        frappe.set_user(BM_USER)
        f = _make_file(BM_USER, "qua_lon.jpg", file_size=11 * 1024 * 1024)
        with self.assertRaises(frappe.ValidationError) as cm:
            portal.portal_yeu_cau_save(_payload(), file_urls=[f.file_url])
        self.assertIn("10MB", str(cm.exception))

    def test_dinh_kem_hop_le_duoc_gan_va_van_private(self):  # BR-Y5
        frappe.set_user(BM_USER)
        f = _make_file(BM_USER, "hop_le.jpg")
        out = portal.portal_yeu_cau_save(_payload(), file_urls=[f.file_url])
        f.reload()
        self.assertEqual(f.attached_to_doctype, "Portal Item Request")
        self.assertEqual(f.attached_to_name, out["name"])
        self.assertEqual(f.is_private, 1)
        # BR-Y5: không có URL công khai — /private/files/, không phải /files/.
        self.assertTrue(f.file_url.startswith("/private/files/"), f.file_url)

    def test_dinh_kem_cong_khai_bi_chan(self):  # BR-Y5
        frappe.set_user(BM_USER)
        f = _make_file(BM_USER, "cong_khai.jpg", is_private=0)
        with self.assertRaises(frappe.ValidationError):
            portal.portal_yeu_cau_save(_payload(), file_urls=[f.file_url])

    def test_dinh_kem_sai_dinh_dang_bi_chan(self):  # NL-11.6
        frappe.set_user(BM_USER)
        f = _make_file(BM_USER, "chuong_trinh.exe")
        with self.assertRaises(frappe.ValidationError) as cm:
            portal.portal_yeu_cau_save(_payload(), file_urls=[f.file_url])
        self.assertIn("pdf/jpg/png/xlsx", str(cm.exception))

    def test_dinh_kem_khong_phai_cua_minh_bi_chan(self):
        f = _make_file(PXN_USER, "cua_pxn.jpg")
        frappe.set_user(BM_USER)
        with self.assertRaises(frappe.PermissionError):
            portal.portal_yeu_cau_save(_payload(), file_urls=[f.file_url])

    def test_canh_bao_trung_ten_gan_giong_van_tao_duoc(self):  # TC-E6-06
        frappe.set_user(BM_USER)
        dau = portal.portal_yeu_cau_save(_payload(ten_hang="Que thử HbA1c"))
        sau = portal.portal_yeu_cau_save(_payload(ten_hang="Que thu HbA1C"))
        self.assertIn(dau["name"], sau["canh_bao_trung"])
        self.assertTrue(frappe.db.exists("Portal Item Request", sau["name"]))

    def test_khong_canh_bao_khi_yeu_cau_cu_da_ket_thuc(self):  # NL-11.1
        frappe.set_user(BM_USER)
        dau = portal.portal_yeu_cau_save(_payload(ten_hang="Bông y tế loại 1"))
        frappe.db.set_value(
            "Portal Item Request", dau["name"], "trang_thai", "Khách huỷ"
        )
        sau = portal.portal_yeu_cau_save(_payload(ten_hang="Bông y tế loại 1"))
        self.assertEqual(sau["canh_bao_trung"], [])

    def test_ten_khong_lien_quan_khong_canh_bao(self):
        frappe.set_user(BM_USER)
        portal.portal_yeu_cau_save(_payload(ten_hang="Găng tay y tế"))
        sau = portal.portal_yeu_cau_save(_payload(ten_hang="Máy đo huyết áp"))
        self.assertEqual(sau["canh_bao_trung"], [])

    def test_sua_khi_dang_moi_thanh_cong(self):
        frappe.set_user(BM_USER)
        out = portal.portal_yeu_cau_save(_payload(ten_hang="Bản nháp"))
        out2 = portal.portal_yeu_cau_save(
            _payload(ten_hang="Bản đã sửa"), name=out["name"]
        )
        self.assertEqual(out2["name"], out["name"])
        doc = frappe.get_doc("Portal Item Request", out["name"])
        self.assertEqual(doc.ten_hang, "Bản đã sửa")

    def test_sua_yeu_cau_cua_khach_khac_bi_chan(self):  # TC-E6-12
        frappe.set_user(PXN_USER)
        out = portal.portal_yeu_cau_save(_payload(ten_hang="Của PXN"))
        frappe.set_user(BM_USER)
        with self.assertRaises(frappe.PermissionError):
            portal.portal_yeu_cau_save(_payload(ten_hang="Bị hack"), name=out["name"])
        # ...và nội dung KHÔNG bị đổi.
        doc = frappe.get_doc("Portal Item Request", out["name"])
        self.assertEqual(doc.ten_hang, "Của PXN")

    def test_sua_khi_khong_con_moi_bi_chan(self):
        doc = _tao_yeu_cau(CUSTOMER_BM, ten_hang="Đã xử lý")
        doc.trang_thai = "Đang tìm nguồn"
        doc.save(ignore_permissions=True)
        frappe.set_user(BM_USER)
        with self.assertRaises(frappe.ValidationError):
            portal.portal_yeu_cau_save(_payload(), name=doc.name)

    def test_tao_moi_bao_ca_sales_va_purchase_user(self):
        frappe.set_user(BM_USER)
        out = portal.portal_yeu_cau_save(_payload(ten_hang="Cần báo nội bộ"))
        for nguoi_nhan in (SALES_USER, PURCHASE_USER):
            with self.subTest(nguoi_nhan=nguoi_nhan):
                self.assertTrue(
                    frappe.db.exists(
                        "Notification Log",
                        {
                            "subject": ("like", f"%{out['name']}%"),
                            "for_user": nguoi_nhan,
                        },
                    ),
                    f"{nguoi_nhan} phải nhận thông báo yêu cầu mới",
                )


# ---------------------------------------------------------------------------
# portal_yeu_cau_list
# ---------------------------------------------------------------------------

class TestPortalYeuCauList(FrappeTestCase):
    def setUp(self):
        seed_demo()

    def tearDown(self):
        frappe.set_user("Administrator")

    def test_chi_thay_yeu_cau_cua_chinh_minh(self):
        frappe.set_user(BM_USER)
        cua_bm = portal.portal_yeu_cau_save(_payload(ten_hang="Của BM"))
        frappe.set_user(PXN_USER)
        cua_pxn = portal.portal_yeu_cau_save(_payload(ten_hang="Của PXN"))

        frappe.set_user(BM_USER)
        rows = portal.portal_yeu_cau_list()
        ten = {r["name"] for r in rows}
        self.assertIn(cua_bm["name"], ten)
        self.assertNotIn(cua_pxn["name"], ten)

    def test_loc_theo_trang_thai(self):
        frappe.set_user(BM_USER)
        moi = portal.portal_yeu_cau_save(_payload(ten_hang="Còn mới"))
        huy = portal.portal_yeu_cau_save(_payload(ten_hang="Sẽ huỷ"))
        portal.portal_yeu_cau_cancel(huy["name"], "Không cần nữa")

        rows = portal.portal_yeu_cau_list(trang_thai="Mới")
        ten = {r["name"] for r in rows}
        self.assertIn(moi["name"], ten)
        self.assertNotIn(huy["name"], ten)

    def test_qua_sla_dung_khi_qua_han_va_con_moi(self):
        frappe.db.set_single_value("Miyano Portal Settings", "sla_yeu_cau_gio", 48)
        doc = _tao_yeu_cau(CUSTOMER_BM, ten_hang="Quá hạn từ lâu")
        frappe.db.sql(
            "update `tabPortal Item Request` set creation=%s where name=%s",
            ("2026-08-01 08:00:00", doc.name),
        )
        frappe.set_user(BM_USER)
        rows = portal.portal_yeu_cau_list()
        row = next(r for r in rows if r["name"] == doc.name)
        self.assertTrue(row["qua_sla"])

    def test_khong_qua_sla_khi_da_xu_ly(self):
        frappe.db.set_single_value("Miyano Portal Settings", "sla_yeu_cau_gio", 48)
        doc = _tao_yeu_cau(CUSTOMER_BM, ten_hang="Đã xử lý sớm")
        frappe.db.sql(
            "update `tabPortal Item Request` set creation=%s where name=%s",
            ("2026-08-01 08:00:00", doc.name),
        )
        doc.reload()
        doc.trang_thai = "Đang tìm nguồn"
        doc.save(ignore_permissions=True)
        frappe.set_user(BM_USER)
        rows = portal.portal_yeu_cau_list()
        row = next(r for r in rows if r["name"] == doc.name)
        self.assertFalse(row["qua_sla"])


# ---------------------------------------------------------------------------
# portal_yeu_cau_cancel
# ---------------------------------------------------------------------------

class TestPortalYeuCauCancel(FrappeTestCase):
    def setUp(self):
        seed_demo()

    def tearDown(self):
        frappe.set_user("Administrator")

    def test_huy_thanh_cong(self):
        frappe.set_user(BM_USER)
        out = portal.portal_yeu_cau_save(_payload(ten_hang="Sẽ huỷ"))
        kq = portal.portal_yeu_cau_cancel(out["name"], "Không cần hàng này nữa.")
        self.assertEqual(kq["trang_thai"], "Khách huỷ")
        doc = frappe.get_doc("Portal Item Request", out["name"])
        self.assertEqual(doc.trang_thai, "Khách huỷ")

    def test_thieu_ly_do_bi_chan(self):
        frappe.set_user(BM_USER)
        out = portal.portal_yeu_cau_save(_payload(ten_hang="Cần lý do"))
        with self.assertRaises(frappe.ValidationError):
            portal.portal_yeu_cau_cancel(out["name"], "")

    def test_huy_yeu_cau_da_ket_thuc_bi_chan(self):
        doc = _tao_yeu_cau(CUSTOMER_BM, ten_hang="Đã kết thúc")
        doc.trang_thai = "Không đáp ứng được"
        doc.ly_do_khong_dap_ung = "Không có nguồn."
        doc.save(ignore_permissions=True)
        frappe.set_user(BM_USER)
        with self.assertRaises(frappe.ValidationError):
            portal.portal_yeu_cau_cancel(doc.name, "Muốn huỷ")

    def test_huy_yeu_cau_khach_khac_bi_chan(self):  # TC-E6-12
        frappe.set_user(PXN_USER)
        out = portal.portal_yeu_cau_save(_payload(ten_hang="Của PXN"))
        frappe.set_user(BM_USER)
        with self.assertRaises(frappe.PermissionError):
            portal.portal_yeu_cau_cancel(out["name"], "Muốn huỷ hộ")


# ---------------------------------------------------------------------------
# portal_yeu_cau_tra_loi — NL-11.3
# ---------------------------------------------------------------------------

class TestPortalYeuCauTraLoi(FrappeTestCase):
    def setUp(self):
        seed_demo()

    def tearDown(self):
        frappe.set_user("Administrator")

    def test_tra_loi_khi_can_them_thong_tin_tu_ve_dang_tim_nguon(self):
        doc = _tao_yeu_cau(CUSTOMER_BM, ten_hang="Cần hỏi thêm")
        doc.trang_thai = "Đang tìm nguồn"
        doc.save(ignore_permissions=True)
        doc.trang_thai = "Cần thêm thông tin"
        doc.save(ignore_permissions=True)

        frappe.set_user(BM_USER)
        kq = portal.portal_yeu_cau_tra_loi(doc.name, "Đây là quy cách chi tiết.")
        self.assertEqual(kq["trang_thai"], "Đang tìm nguồn")
        doc.reload()
        self.assertEqual(doc.trang_thai, "Đang tìm nguồn")
        noi_dung_comment = frappe.get_all(
            "Comment", filters={"reference_doctype": "Portal Item Request",
                                 "reference_name": doc.name},
            pluck="content",
        )
        self.assertTrue(any("quy cách chi tiết" in (c or "") for c in noi_dung_comment))

    def test_tra_loi_khi_khong_can_them_thong_tin_khong_doi_trang_thai(self):
        doc = _tao_yeu_cau(CUSTOMER_BM, ten_hang="Đang xử lý bình thường")
        doc.trang_thai = "Đang tìm nguồn"
        doc.save(ignore_permissions=True)
        frappe.set_user(BM_USER)
        kq = portal.portal_yeu_cau_tra_loi(doc.name, "Chỉ hỏi thăm tiến độ.")
        self.assertEqual(kq["trang_thai"], "Đang tìm nguồn")

    def test_tra_loi_yeu_cau_khach_khac_bi_chan(self):  # TC-E6-12
        frappe.set_user(PXN_USER)
        out = portal.portal_yeu_cau_save(_payload(ten_hang="Của PXN"))
        frappe.set_user(BM_USER)
        with self.assertRaises(frappe.PermissionError):
            portal.portal_yeu_cau_tra_loi(out["name"], "Nội dung lạ")

    def test_tra_loi_yeu_cau_da_ket_thuc_bi_chan(self):
        doc = _tao_yeu_cau(CUSTOMER_BM, ten_hang="Đã huỷ")
        doc.trang_thai = "Khách huỷ"
        doc.save(ignore_permissions=True)
        frappe.set_user(BM_USER)
        with self.assertRaises(frappe.ValidationError):
            portal.portal_yeu_cau_tra_loi(doc.name, "Xin mở lại")


# ---------------------------------------------------------------------------
# Job SLA leo thang — TC-E6-07 / NL-11.2
# ---------------------------------------------------------------------------

class TestQuetYeuCauQuaHan(FrappeTestCase):
    MOC = "2026-08-12 16:00:00"  # Thứ Tư — cùng mốc cố định với TestSLADonTreo

    def setUp(self):
        seed_demo()
        frappe.db.set_single_value("Miyano Portal Settings", "sla_yeu_cau_gio", 48)
        frappe.db.delete(
            "Notification Log",
            {"subject": ("like", "Portal - Yêu cầu hàng hoá treo SLA%")},
        )
        # Cùng lý do với TestSLADonTreo: FrappeTestCase rollback theo CLASS,
        # dọn sạch mọi "Mới" sót lại từ test trước trong cùng class.
        frappe.db.delete("Portal Item Request", {"trang_thai": "Mới"})

    def _tao_qua_han(self, tao_luc, **kw):
        doc = _tao_yeu_cau(CUSTOMER_BM, **kw)
        frappe.db.sql(
            "update `tabPortal Item Request` set creation=%s where name=%s",
            (tao_luc, doc.name),
        )
        return doc

    def test_yeu_cau_qua_sla_o_moi_thi_nhac_manager(self):
        doc = self._tao_qua_han("2026-08-05 08:00:00", ten_hang="Treo lâu rồi")
        self.assertEqual(quet_yeu_cau_qua_han(moc=self.MOC), 1)
        self.assertTrue(
            frappe.db.exists(
                "Notification Log", {"subject": ("like", f"%{doc.name}%")}
            )
        )

    def test_yeu_cau_chua_qua_sla_thi_im(self):
        self._tao_qua_han("2026-08-12 13:00:00", ten_hang="Còn mới nguyên")
        self.assertEqual(quet_yeu_cau_qua_han(moc=self.MOC), 0)

    def test_moi_yeu_cau_chi_nhac_mot_lan_moi_ngay(self):
        self._tao_qua_han("2026-08-05 08:00:00", ten_hang="Nhắc một lần")
        self.assertEqual(quet_yeu_cau_qua_han(moc=self.MOC), 1)
        self.assertEqual(
            quet_yeu_cau_qua_han(moc=self.MOC), 0,
            "chạy hourly mà nhắc mỗi giờ là spam",
        )

    def test_yeu_cau_da_xu_ly_khong_bi_nhac(self):
        doc = self._tao_qua_han("2026-08-05 08:00:00", ten_hang="Đã có người nhận")
        doc.reload()
        doc.trang_thai = "Đang tìm nguồn"
        doc.save(ignore_permissions=True)
        self.assertEqual(quet_yeu_cau_qua_han(moc=self.MOC), 0)

    def test_sua_nhap_khong_reset_dong_ho_sla(self):
        """LỆCH CÓ CHỦ Ý so với quet_don_treo (dùng `modified`): SLA của yêu
        cầu tính từ `creation`, vì khách được sửa nháp "Mới" của chính mình
        (portal_yeu_cau_save) — nếu job dùng `modified`, một lần khách sửa
        ghi chú sẽ âm thầm reset đồng hồ SLA nội bộ."""
        doc = self._tao_qua_han("2026-08-05 08:00:00", ten_hang="Sắp bị sửa")
        frappe.set_user(BM_USER)
        portal.portal_yeu_cau_save(_payload(ten_hang="Sắp bị sửa — đã cập nhật"),
                                    name=doc.name)
        frappe.set_user("Administrator")
        self.assertEqual(
            quet_yeu_cau_qua_han(moc=self.MOC), 1,
            "sửa nháp không được reset đồng hồ SLA tính từ creation",
        )


# ---------------------------------------------------------------------------
# cong_gio_lam_viec — chiều ngược của gio_lam_viec_troi_qua, phải khớp nhau
# (delta nhỏ do cắt ngày ở 23:59:59, xem docstring portal_sla.py)
# ---------------------------------------------------------------------------

class TestCongGioLamViec(FrappeTestCase):
    def test_doi_xung_voi_gio_lam_viec_troi_qua(self):
        bat_dau = "2026-08-10 09:00:00"  # Thứ Hai
        han = cong_gio_lam_viec(bat_dau, 48)
        gio_do_lai = gio_lam_viec_troi_qua(bat_dau, moc=han)
        self.assertAlmostEqual(gio_do_lai, 48.0, delta=0.01)

    def test_cong_gio_bo_qua_cuoi_tuan(self):
        # Thứ Sáu 17:00 + 16 giờ làm việc = Thứ Hai 09:00 (bỏ T7/CN).
        han = cong_gio_lam_viec("2026-08-07 17:00:00", 16)
        self.assertEqual(get_datetime(han).strftime("%Y-%m-%d %H:%M"), "2026-08-10 09:00")


# ---------------------------------------------------------------------------
# Email khách — BR-Y2 (đúng lý do), NL-11.3, xác nhận tạo
# ---------------------------------------------------------------------------

class TestEmailYeuCau(FrappeTestCase):
    def test_email_khong_dap_ung_mang_dung_ly_do(self):  # BR-Y2
        n = frappe.get_doc("Notification", "Portal - Yêu cầu không đáp ứng được")
        self.assertIn("ly_do_khong_dap_ung", n.message)
        self.assertEqual(n.document_type, "Portal Item Request")
        self.assertEqual(n.value_changed, "trang_thai")
        self.assertEqual(n.recipients[0].receiver_by_document_field, "nguoi_yeu_cau")
        self.assertTrue(n.enabled)

    def test_email_xac_nhan_tao_moi(self):
        n = frappe.get_doc("Notification", "Portal - Yêu cầu hàng hoá đã ghi nhận")
        self.assertEqual(n.event, "New")
        self.assertEqual(n.recipients[0].receiver_by_document_field, "nguoi_yeu_cau")

    def test_email_can_them_thong_tin(self):  # NL-11.3
        n = frappe.get_doc("Notification", "Portal - Yêu cầu cần thêm thông tin")
        self.assertEqual(n.value_changed, "trang_thai")
        self.assertIn("Cần thêm thông tin", n.condition)
        self.assertEqual(n.recipients[0].receiver_by_document_field, "nguoi_yeu_cau")


# ---------------------------------------------------------------------------
# Report Desk — US-E6.6/UC-53
# ---------------------------------------------------------------------------

class TestDemandPipelineReport(FrappeTestCase):
    REPORT = "Demand pipeline yêu cầu hàng hoá"

    def test_bao_cao_ton_tai_va_chay_duoc(self):
        from frappe.desk.query_report import run
        self.assertTrue(frappe.db.exists("Report", self.REPORT))
        kq = run(self.REPORT, ignore_prepared_report=True)
        self.assertIn("columns", kq)

    def test_bao_cao_khong_danh_cho_customer(self):
        roles = frappe.get_all(
            "Has Role", filters={"parent": self.REPORT, "parenttype": "Report"},
            pluck="role",
        )
        self.assertNotIn("Customer", roles)
        self.assertTrue(roles)
        for r in ("Sales Manager", "Sales User", "Purchase User"):
            self.assertIn(r, roles)

    def test_ty_le_chuyen_thanh_don_tinh_dung(self):
        rows = [
            {"trang_thai": "Đã chuyển thành đơn", "ket_thuc": 1, "da_chuyen_don": 1,
             "tan_suat": "Một lần", "thoi_gian_xu_ly_gio": 10.0},
            {"trang_thai": "Không đáp ứng được", "ket_thuc": 1, "da_chuyen_don": 0,
             "tan_suat": "Một lần", "thoi_gian_xu_ly_gio": 20.0},
            {"trang_thai": "Mới", "ket_thuc": 0, "da_chuyen_don": 0,
             "tan_suat": "Một lần", "thoi_gian_xu_ly_gio": None},
        ]
        tt = demand_pipeline.tom_tat(rows)
        self.assertEqual(tt["tong"], 3)
        self.assertEqual(tt["ket_thuc"], 2)
        self.assertEqual(tt["chuyen_don"], 1)
        # Mẫu số CHỈ gồm kết thúc (2), KHÔNG gồm "Mới" (3) — 1/2 = 50%.
        self.assertEqual(tt["ty_le_chuyen_don"], 50.0)
        self.assertEqual(tt["thoi_gian_xu_ly_binh_quan_gio"], 15.0)

    def test_nhom_dinh_ky_tach_rieng(self):  # NL-11.7
        rows = [
            {"trang_thai": "Đã chuyển thành đơn", "ket_thuc": 1, "da_chuyen_don": 1,
             "tan_suat": "Định kỳ", "thoi_gian_xu_ly_gio": 5.0},
            {"trang_thai": "Không đáp ứng được", "ket_thuc": 1, "da_chuyen_don": 0,
             "tan_suat": "Định kỳ", "thoi_gian_xu_ly_gio": 5.0},
            {"trang_thai": "Đã chuyển thành đơn", "ket_thuc": 1, "da_chuyen_don": 1,
             "tan_suat": "Một lần", "thoi_gian_xu_ly_gio": 5.0},
        ]
        tt = demand_pipeline.tom_tat(rows)
        self.assertEqual(tt["dinh_ky_tong"], 2)
        self.assertEqual(tt["dinh_ky_ket_thuc"], 2)
        self.assertEqual(tt["dinh_ky_chuyen_don"], 1)
        self.assertEqual(tt["dinh_ky_ty_le_chuyen_don"], 50.0)
        # Tổng thể (gộp cả định kỳ lẫn một lần) là 2/3 chuyển đơn — khác hẳn
        # con số riêng của nhóm Định kỳ, chứng minh hai nhóm KHÔNG bị trộn.
        self.assertAlmostEqual(tt["ty_le_chuyen_don"], 66.7, delta=0.1)

    def test_yeu_cau_rows_loc_theo_khach(self):
        seed_demo()
        frappe.db.delete("Portal Item Request", {"customer": ["in", [CUSTOMER_BM, CUSTOMER_PXN]]})
        _tao_yeu_cau(CUSTOMER_BM, ten_hang="Hàng của BM")
        _tao_yeu_cau(CUSTOMER_PXN, ten_hang="Hàng của PXN")
        rows = demand_pipeline.yeu_cau_rows(customer=CUSTOMER_BM)
        self.assertTrue(all(r["customer"] == CUSTOMER_BM for r in rows))
        self.assertTrue(any(r["ten_hang"] == "Hàng của BM" for r in rows))
