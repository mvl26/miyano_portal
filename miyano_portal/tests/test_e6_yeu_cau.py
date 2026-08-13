"""E6 phần A — Yêu cầu hàng hoá (QT11). TC-E6-05, 06, 07, 08, 12
(40_TestCases.md); US-E6.3/E6.4/E6.6; BR-Y1…Y5; NL-11.1/11.2/11.3/11.6.

Cách ly cơ bản (mã hoá/không nhận `customer` từ client, phủ toàn bộ doctype
động của module) nằm ở test_kho_isolation.py — file này chỉ kiểm hành vi
nghiệp vụ riêng của E6.
"""

import os

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
    chúng ta. Dựng một ảnh JPEG nhỏ, MÀU NGẪU NHIÊN mỗi lần gọi (không phải
    hằng số cố định).

    Lý do màu ngẫu nhiên (bắt được bằng chính test cộng dồn đính kèm):
    `File.validate_duplicate_entry()` coi hai File có cùng `content_hash` là
    "cùng một file vật lý" và cho hai bản ghi File riêng biệt (hai `name`
    khác nhau) TRỎ CHUNG một `file_url` trên đĩa. Với nội dung ảnh CỐ ĐỊNH,
    ba lần gọi `_make_file` trong cùng một test tạo ra ba `File.name` khác
    nhau nhưng chỉ MỘT `file_url` — `_resolve_owned_attachment` (tra theo
    file_url) khi đó chỉ thấy một tệp, không phải ba, và test đếm-dồn đính
    kèm sẽ đỏ sai chỗ. Nội dung ngẫu nhiên giữ mỗi lần gọi là MỘT tệp thật sự
    khác nhau, đúng với việc khách tải lên nhiều ảnh khác nhau trong đời thật."""
    import io
    import random
    from PIL import Image
    buf = io.BytesIO()
    mau = (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
    Image.new("RGB", (2, 2), color=mau).save(buf, format="JPEG")
    return buf.getvalue()


def _make_file(owner_user, filename, is_private=1, content=None):
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
    return doc


def _dem_dinh_kem(name) -> int:
    return frappe.db.count(
        "File", {"attached_to_doctype": "Portal Item Request", "attached_to_name": name}
    )


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

    def test_qua_5_file_cong_don_giua_tao_va_sua_bi_chan(self):
        """Giới hạn 5 file là TỔNG số đính kèm của yêu cầu, không phải số
        file trong một lần gọi — 3 file lúc tạo + 3 file lúc sửa (còn "Mới")
        phải chặn ở lần sửa, không được cộng dồn vượt quá."""
        frappe.set_user(BM_USER)
        dot_1 = [_make_file(BM_USER, f"dot1_{i}.jpg") for i in range(3)]
        out = portal.portal_yeu_cau_save(
            _payload(ten_hang="Nhiều đợt đính kèm"),
            file_urls=[f.file_url for f in dot_1],
        )
        dot_2 = [_make_file(BM_USER, f"dot2_{i}.jpg") for i in range(3)]
        with self.assertRaises(frappe.ValidationError) as cm:
            portal.portal_yeu_cau_save(
                _payload(ten_hang="Nhiều đợt đính kèm"),
                name=out["name"],
                file_urls=[f.file_url for f in dot_2],
            )
        self.assertIn("Tối đa 5 file", str(cm.exception))
        # 3 file đợt 1 vẫn còn nguyên, không có gì từ đợt 2 được gắn.
        self.assertEqual(
            frappe.db.count(
                "File",
                {"attached_to_doctype": "Portal Item Request", "attached_to_name": out["name"]},
            ),
            3,
        )

    def test_file_qua_10mb_bi_chan(self):  # TC-E6-05, ca 3
        """F-1 (review) — chặn phải dựa trên NỘI DUNG thật, không phải field
        `file_size` (client kiểm soát được qua form_dict, xem docstring
        `_resolve_owned_attachment`). Tải lên >10MB THẬT — đuôi .xlsx để
        tránh hai nhánh xác thực nội dung riêng của Frappe (strip EXIF ảnh
        JPEG, quét JS trong PDF) vốn không liên quan tới thứ đang kiểm ở đây."""
        frappe.set_user(BM_USER)
        noi_dung_lon = os.urandom(11 * 1024 * 1024)
        f = _make_file(BM_USER, "qua_lon.xlsx", content=noi_dung_lon)
        with self.assertRaises(frappe.ValidationError) as cm:
            portal.portal_yeu_cau_save(_payload(), file_urls=[f.file_url])
        self.assertIn("10MB", str(cm.exception))

    def test_file_gia_mao_file_size_van_bi_chan(self):
        """F-1 (review) — trước bản vá, đặt `File.file_size` nhỏ (giống hệt
        cách form_dict.file_size của client ghi đè số đã đo) khiến file lớn
        lọt qua. Giữ test này để khoá đúng ca tấn công: nội dung >10MB thật
        NHƯNG field file_size bị set sai (nhỏ) trên bản ghi — vẫn phải chặn,
        vì endpoint không còn đọc field này nữa."""
        frappe.set_user(BM_USER)
        noi_dung_lon = os.urandom(11 * 1024 * 1024)
        f = _make_file(BM_USER, "gia_mao.xlsx", content=noi_dung_lon)
        frappe.db.set_value("File", f.name, "file_size", 100, update_modified=False)
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
        """F-5 (review) đổi CƠ CHẾ tra cứu sang lọc thẳng `owner` trong câu
        truy vấn (thay vì tra theo file_url rồi mới so owner) — hệ quả là
        một File của người khác giờ không còn "tìm thấy nhưng bị chặn"
        (PermissionError) mà "không tìm thấy" (ValidationError) NGAY TỪ ĐẦU,
        đúng khuôn `_yeu_cau_cua_khach` (M-1): không phân biệt được nữa giữa
        "tệp không tồn tại" và "tệp của người khác" qua loại lỗi."""
        f = _make_file(PXN_USER, "cua_pxn.jpg")
        frappe.set_user(BM_USER)
        with self.assertRaises(frappe.ValidationError) as cm:
            portal.portal_yeu_cau_save(_payload(), file_urls=[f.file_url])
        self.assertIn("Không tìm thấy tệp", str(cm.exception))

    # -- F-5 (review) — File.validate_duplicate_entry() gộp nhiều File.name
    # trùng nội dung vào chung một file_url; _resolve_owned_attachment phải
    # không mất/dời/nhầm đính kèm khi va chạm đó xảy ra. -----------------

    def test_dinh_kem_trung_noi_dung_hai_yeu_cau_khac_khong_bi_doi_chu(self):
        """GIỚI HẠN THẲNG THẮN: khi HAI File CÙNG CHƯA GẮN VÀO ĐÂU chia sẻ
        chung một `file_url` (nội dung trùng), giao thức chỉ mang `file_url`
        — server KHÔNG có cách nào biết client "muốn nói" File.name nào
        trong hai cái. Không cố giả vờ có một ánh xạ tất định ở đây (đoán
        sai vẫn là đoán); bất biến ĐÚNG cần giữ là: không có gì bị MẤT — cả
        hai yêu cầu đều có đúng một đính kèm, và hai File.name gốc được dùng
        hết, mỗi cái cho đúng MỘT yêu cầu (không cái nào bị bỏ rơi hay dùng
        chung hai lần)."""
        frappe.set_user(BM_USER)
        noi_dung = _anh_jpeg_hop_le()
        f1 = _make_file(BM_USER, "trung_1.jpg", content=noi_dung)
        f2 = _make_file(BM_USER, "trung_2.jpg", content=noi_dung)
        self.assertEqual(f1.file_url, f2.file_url, "tiền đề: hai File dùng CHUNG file_url")
        self.assertNotEqual(f1.name, f2.name, "nhưng là hai File.name khác nhau")

        out_a = portal.portal_yeu_cau_save(
            _payload(ten_hang="Yêu cầu A trùng nội dung"), file_urls=[f1.file_url]
        )
        out_b = portal.portal_yeu_cau_save(
            _payload(ten_hang="Yêu cầu B trùng nội dung"), file_urls=[f2.file_url]
        )
        f1.reload()
        f2.reload()
        # Không có gì bị BỎ RƠI (cả hai vẫn gắn vào MỘT yêu cầu nào đó)...
        self.assertIn(f1.attached_to_name, (out_a["name"], out_b["name"]))
        self.assertIn(f2.attached_to_name, (out_a["name"], out_b["name"]))
        # ...và không có gì bị DÙNG CHUNG cho cả hai yêu cầu.
        self.assertNotEqual(f1.attached_to_name, f2.attached_to_name)
        self.assertEqual(
            {f1.attached_to_name, f2.attached_to_name}, {out_a["name"], out_b["name"]}
        )
        self.assertEqual(_dem_dinh_kem(out_a["name"]), 1)
        self.assertEqual(_dem_dinh_kem(out_b["name"]), 1)

    def test_dinh_kem_da_gan_o_yeu_cau_khac_bi_tu_choi_khong_bi_doi_chu(self):
        frappe.set_user(BM_USER)
        noi_dung = _anh_jpeg_hop_le()
        f1 = _make_file(BM_USER, "da_gan_1.jpg", content=noi_dung)
        out_a = portal.portal_yeu_cau_save(
            _payload(ten_hang="Yêu cầu A đã có đính kèm"), file_urls=[f1.file_url]
        )
        # Không còn File nào CHƯA gắn mang cùng file_url — client (nhầm hoặc
        # cố ý) gửi lại đúng file_url đó cho một yêu cầu MỚI KHÁC.
        with self.assertRaises(frappe.ValidationError) as cm:
            portal.portal_yeu_cau_save(
                _payload(ten_hang="Yêu cầu C mượn nhầm đính kèm"),
                file_urls=[f1.file_url],
            )
        self.assertIn("đã được đính kèm", str(cm.exception))
        # ...và đính kèm gốc của A không hề bị đụng tới.
        f1.reload()
        self.assertEqual(f1.attached_to_name, out_a["name"])

    def test_sua_gui_lai_dinh_kem_cu_khong_loi_khong_doi_chu(self):
        """Idempotent: sửa nháp "Mới", gửi lại NGUYÊN file_url đã gắn từ lần
        tạo — không được coi là "đính kèm ở yêu cầu khác"."""
        frappe.set_user(BM_USER)
        f = _make_file(BM_USER, "giu_nguyen.jpg")
        out = portal.portal_yeu_cau_save(
            _payload(ten_hang="Sẽ sửa lại"), file_urls=[f.file_url]
        )
        portal.portal_yeu_cau_save(
            _payload(ten_hang="Sẽ sửa lại — đã cập nhật"),
            name=out["name"], file_urls=[f.file_url],
        )
        f.reload()
        self.assertEqual(f.attached_to_name, out["name"])

    def test_dinh_kem_trung_noi_dung_khac_khach_khong_bi_chan_nham(self):
        """Hai khách khác nhau cùng tải lên một tài liệu trùng byte (ví dụ
        datasheet công khai của hãng) — lọc theo `owner` phải đủ để mỗi
        khách vẫn resolve ĐÚNG File.name của chính mình, không đụng vào File
        của khách kia."""
        noi_dung_chung = _anh_jpeg_hop_le()
        f_bm = _make_file(BM_USER, "datasheet.jpg", content=noi_dung_chung)
        f_pxn = _make_file(PXN_USER, "datasheet.jpg", content=noi_dung_chung)
        self.assertEqual(f_bm.file_url, f_pxn.file_url, "tiền đề: trùng file_url")

        frappe.set_user(BM_USER)
        out_bm = portal.portal_yeu_cau_save(
            _payload(ten_hang="BM tải datasheet"), file_urls=[f_bm.file_url]
        )
        frappe.set_user(PXN_USER)
        out_pxn = portal.portal_yeu_cau_save(
            _payload(ten_hang="PXN tải datasheet"), file_urls=[f_pxn.file_url]
        )
        f_bm.reload()
        f_pxn.reload()
        self.assertEqual(f_bm.attached_to_name, out_bm["name"])
        self.assertEqual(f_pxn.attached_to_name, out_pxn["name"])
        self.assertEqual(f_bm.owner, BM_USER)
        self.assertEqual(f_pxn.owner, PXN_USER)

    # -- F-4 (review) — vat_tu_kho phải thuộc kho của CHÍNH khách gọi -------

    def test_vat_tu_kho_cua_khach_khac_bi_chan(self):
        from miyano_portal.setup.seed_kho_demo import seed_kho_demo
        kho = seed_kho_demo()
        frappe.set_user(BM_USER)
        with self.assertRaises(frappe.PermissionError):
            portal.portal_yeu_cau_save(
                _payload(ten_hang="Mượn vật tư PXN", vat_tu_kho=kho["vt_pxn"])
            )
        self.assertFalse(
            frappe.db.exists(
                "Portal Item Request",
                {"customer": CUSTOMER_BM, "ten_hang": "Mượn vật tư PXN"},
            )
        )

    def test_vat_tu_kho_cua_chinh_minh_duoc_chap_nhan(self):
        from miyano_portal.setup.seed_kho_demo import seed_kho_demo
        kho = seed_kho_demo()
        frappe.set_user(BM_USER)
        out = portal.portal_yeu_cau_save(
            _payload(ten_hang="Dùng vật tư của chính BM", vat_tu_kho=kho["vt_bm"])
        )
        doc = frappe.get_doc("Portal Item Request", out["name"])
        self.assertEqual(doc.vat_tu_kho, kho["vt_bm"])

    # -- M-1 (review) — không lộ "tồn tại hay không" qua LOẠI lỗi -----------

    def test_sua_yeu_cau_khong_ton_tai_va_cua_khach_khac_cung_mot_loi(self):
        """Trước bản vá: tên không tồn tại -> DoesNotExistError (tiếng Anh);
        tên của khách khác -> PermissionError. Hai loại lỗi khác nhau đủ để
        dò xem một mã YCH-nnnnn có tồn tại hay không. Giờ cả hai PHẢI cùng
        một loại lỗi."""
        frappe.set_user(PXN_USER)
        cua_pxn = portal.portal_yeu_cau_save(_payload(ten_hang="Của PXN riêng"))

        frappe.set_user(BM_USER)
        with self.assertRaises(frappe.PermissionError):
            portal.portal_yeu_cau_save(_payload(), name="YCH-KHONG-TON-TAI-999")
        with self.assertRaises(frappe.PermissionError):
            portal.portal_yeu_cau_save(_payload(), name=cua_pxn["name"])

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

    def test_huy_yeu_cau_khong_ton_tai_va_cua_khach_khac_cung_mot_loi(self):  # M-1
        frappe.set_user(PXN_USER)
        cua_pxn = portal.portal_yeu_cau_save(_payload(ten_hang="Của PXN riêng"))
        frappe.set_user(BM_USER)
        with self.assertRaises(frappe.PermissionError):
            portal.portal_yeu_cau_cancel("YCH-KHONG-TON-TAI-999", "Huỷ")
        with self.assertRaises(frappe.PermissionError):
            portal.portal_yeu_cau_cancel(cua_pxn["name"], "Huỷ")


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

    def test_tra_loi_yeu_cau_khong_ton_tai_va_cua_khach_khac_cung_mot_loi(self):  # M-1
        frappe.set_user(PXN_USER)
        cua_pxn = portal.portal_yeu_cau_save(_payload(ten_hang="Của PXN riêng"))
        frappe.set_user(BM_USER)
        with self.assertRaises(frappe.PermissionError):
            portal.portal_yeu_cau_tra_loi("YCH-KHONG-TON-TAI-999", "Nội dung")
        with self.assertRaises(frappe.PermissionError):
            portal.portal_yeu_cau_tra_loi(cua_pxn["name"], "Nội dung")


# ---------------------------------------------------------------------------
# portal_yeu_cau_detail / portal_yeu_cau_file — F-2, F-3
# ---------------------------------------------------------------------------

class TestPortalYeuCauDetailVaFile(FrappeTestCase):
    def setUp(self):
        seed_demo()

    def tearDown(self):
        frappe.set_user("Administrator")

    def test_detail_tra_du_field_phan_hoi(self):  # F-2
        doc = _tao_yeu_cau(CUSTOMER_BM, ten_hang="Cần chi tiết")  # bắt đầu "Mới"
        doc.trang_thai = "Đang tìm nguồn"
        doc.phan_hoi = "Miyano cần thêm quy cách đóng gói."
        doc.gia_bao = 150000
        doc.lead_time_ngay = 10
        doc.save(ignore_permissions=True)

        frappe.set_user(BM_USER)
        kq = portal.portal_yeu_cau_detail(doc.name)
        self.assertEqual(kq["phan_hoi"], "Miyano cần thêm quy cách đóng gói.")
        self.assertEqual(kq["gia_bao"], 150000)
        self.assertEqual(kq["lead_time_ngay"], 10)
        self.assertEqual(kq["trang_thai"], "Đang tìm nguồn")

    def test_detail_tra_ca_comment_va_dinh_kem(self):  # F-2
        frappe.set_user(BM_USER)
        f = _make_file(BM_USER, "chi_tiet.jpg")
        out = portal.portal_yeu_cau_save(_payload(ten_hang="Có bình luận"), file_urls=[f.file_url])
        portal.portal_yeu_cau_tra_loi(out["name"], "Đây là câu trả lời của tôi.")

        kq = portal.portal_yeu_cau_detail(out["name"])
        self.assertTrue(
            any("câu trả lời của tôi" in (c.get("content") or "") for c in kq["binh_luan"])
        )
        ten_file = {d["file_name"] for d in kq["dinh_kem"]}
        self.assertIn("chi_tiet.jpg", ten_file)

    def test_detail_yeu_cau_khach_khac_bi_chan(self):  # TC-E6-12/M-1
        frappe.set_user(PXN_USER)
        cua_pxn = portal.portal_yeu_cau_save(_payload(ten_hang="Của PXN"))
        frappe.set_user(BM_USER)
        with self.assertRaises(frappe.PermissionError):
            portal.portal_yeu_cau_detail(cua_pxn["name"])
        with self.assertRaises(frappe.PermissionError):
            portal.portal_yeu_cau_detail("YCH-KHONG-TON-TAI-999")

    def test_file_tai_duoc_boi_nguoi_khac_cung_khach(self):  # F-3
        """Người thứ hai của CÙNG bệnh viện (không phải người đã bấm upload)
        vẫn phải tải được đính kèm của yêu cầu do đơn vị mình gửi."""
        second_bm = "second_bm@demo.miyano"
        frappe.set_user("Administrator")
        portal.portal_provision(CUSTOMER_BM, second_bm)

        frappe.set_user(BM_USER)
        f = _make_file(BM_USER, "cho_ca_hai.jpg")
        out = portal.portal_yeu_cau_save(
            _payload(ten_hang="Đính kèm dùng chung"), file_urls=[f.file_url]
        )

        frappe.set_user(second_bm)
        kq = portal.portal_yeu_cau_detail(out["name"])
        file_name = kq["dinh_kem"][0]["name"]
        portal.portal_yeu_cau_file(out["name"], file_name)  # không được ném lỗi
        self.assertEqual(frappe.local.response.filename, "cho_ca_hai.jpg")
        self.assertTrue(frappe.local.response.filecontent)

    def test_file_yeu_cau_khach_khac_bi_chan(self):  # F-3/TC-E6-12
        frappe.set_user(PXN_USER)
        f = _make_file(PXN_USER, "cua_pxn.jpg")
        out = portal.portal_yeu_cau_save(_payload(ten_hang="Của PXN"), file_urls=[f.file_url])

        frappe.set_user(BM_USER)
        with self.assertRaises(frappe.PermissionError):
            portal.portal_yeu_cau_file(out["name"], f.name)

    def test_file_dinh_kem_khong_thuoc_yeu_cau_bi_chan(self):  # F-3
        """Đúng khách nhưng SAI yêu cầu (file thuộc YCH-A, đòi tải qua
        YCH-B) — vẫn phải chặn, không chỉ kiểm khách."""
        frappe.set_user(BM_USER)
        f = _make_file(BM_USER, "cua_a.jpg")
        out_a = portal.portal_yeu_cau_save(
            _payload(ten_hang="Yêu cầu A"), file_urls=[f.file_url]
        )
        out_b = portal.portal_yeu_cau_save(_payload(ten_hang="Yêu cầu B"))
        with self.assertRaises(frappe.ValidationError):
            portal.portal_yeu_cau_file(out_b["name"], f.name)


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

    def _so_lan_nhac(self, doc_name) -> int:
        """M-5 (review) — đếm Notification Log CHO ĐÚNG TÊN bản ghi của
        CHÍNH test này, không đọc giá trị trả về (int tuyệt đối) của
        quet_yeu_cau_qua_han(): giá trị đó phụ thuộc SỐ NGƯỜI có role Sales
        Manager trên site (job insert một dòng MỖI người nhận — xem
        _nguoi_nhan() trong portal_sla.py), một con số ngoài tầm kiểm soát
        của setUp (đúng bẫy #5 của brief). Vì vậy các test dưới đây KHÔNG so
        con số này với một hằng số tuyệt đối — chỉ so nó TRƯỚC/SAU trong
        cùng một test (test_moi_yeu_cau_chi_nhac_mot_lan_moi_ngay), hoặc so
        có/không (>0 hay ==0)."""
        return frappe.db.count(
            "Notification Log", {"subject": ("like", f"%{doc_name}%")}
        )

    def test_yeu_cau_qua_sla_o_moi_thi_nhac_manager(self):
        doc = self._tao_qua_han("2026-08-05 08:00:00", ten_hang="Treo lâu rồi")
        quet_yeu_cau_qua_han(moc=self.MOC)
        self.assertGreater(self._so_lan_nhac(doc.name), 0)

    def test_yeu_cau_chua_qua_sla_thi_im(self):
        doc = self._tao_qua_han("2026-08-12 13:00:00", ten_hang="Còn mới nguyên")
        quet_yeu_cau_qua_han(moc=self.MOC)
        self.assertEqual(self._so_lan_nhac(doc.name), 0)

    def test_moi_yeu_cau_chi_nhac_mot_lan_moi_ngay(self):
        doc = self._tao_qua_han("2026-08-05 08:00:00", ten_hang="Nhắc một lần")
        quet_yeu_cau_qua_han(moc=self.MOC)
        sau_lan_1 = self._so_lan_nhac(doc.name)
        self.assertGreater(sau_lan_1, 0)
        quet_yeu_cau_qua_han(moc=self.MOC)
        self.assertEqual(
            self._so_lan_nhac(doc.name), sau_lan_1,
            "chạy hourly mà nhắc mỗi giờ là spam",
        )

    def test_yeu_cau_da_xu_ly_khong_bi_nhac(self):
        doc = self._tao_qua_han("2026-08-05 08:00:00", ten_hang="Đã có người nhận")
        doc.reload()
        doc.trang_thai = "Đang tìm nguồn"
        doc.save(ignore_permissions=True)
        quet_yeu_cau_qua_han(moc=self.MOC)
        self.assertEqual(self._so_lan_nhac(doc.name), 0)

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
        quet_yeu_cau_qua_han(moc=self.MOC)
        self.assertGreater(
            self._so_lan_nhac(doc.name), 0,
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

    def test_trang_thai_ket_thuc_dung_chung_mot_nguon(self):  # F-6
        """Không được có bản sao thứ hai của tuple này — xem docstring
        demand_pipeline.py. Một trạng thái kết thúc thứ năm thêm vào
        controller mà quên sửa nơi khác sẽ tự động lệch nếu có hai bản độc
        lập; import chung một object thì không có gì để lệch."""
        from miyano_portal.miyano_portal.doctype.portal_item_request.portal_item_request import (
            TRANG_THAI_KET_THUC as tu_controller,
        )
        self.assertIs(demand_pipeline.TRANG_THAI_KET_THUC, tu_controller)

    def test_yeu_cau_rows_gan_nhan_va_thoi_gian_xu_ly_dung(self):  # F-6
        """End-to-end trên bản ghi THẬT (không dựng dict tay như hai test
        trên) — phủ đúng phần `yeu_cau_rows()` gán nhãn `ket_thuc`/
        `da_chuyen_don`/`thoi_gian_xu_ly_gio` mà trước bản vá không có test
        nào chạm tới."""
        seed_demo()
        frappe.db.delete(
            "Portal Item Request",
            {"customer": CUSTOMER_BM, "ten_hang": ("like", "F6 demand%")},
        )

        con_mo = _tao_yeu_cau(CUSTOMER_BM, ten_hang="F6 demand - con mo")

        khong_dap_ung = _tao_yeu_cau(CUSTOMER_BM, ten_hang="F6 demand - khong dap ung")
        frappe.db.sql(
            "update `tabPortal Item Request` set creation=%s where name=%s",
            ("2026-08-01 08:00:00", khong_dap_ung.name),
        )
        khong_dap_ung.reload()
        khong_dap_ung.trang_thai = "Đang tìm nguồn"
        khong_dap_ung.save(ignore_permissions=True)
        khong_dap_ung.trang_thai = "Không đáp ứng được"
        khong_dap_ung.ly_do_khong_dap_ung = "Không tìm được nguồn."
        khong_dap_ung.save(ignore_permissions=True)

        chuyen_don = _tao_yeu_cau(CUSTOMER_BM, ten_hang="F6 demand - chuyen don")
        frappe.db.sql(
            "update `tabPortal Item Request` set creation=%s where name=%s",
            ("2026-08-01 08:00:00", chuyen_don.name),
        )
        chuyen_don.reload()
        chuyen_don.trang_thai = "Đang tìm nguồn"
        chuyen_don.save(ignore_permissions=True)
        chuyen_don.trang_thai = "Đã báo giá"
        chuyen_don.save(ignore_permissions=True)
        chuyen_don.trang_thai = "Đã chuyển thành đơn"
        chuyen_don.save(ignore_permissions=True)

        by_name = {
            r["name"]: r
            for r in demand_pipeline.yeu_cau_rows(customer=CUSTOMER_BM)
        }

        r_mo = by_name[con_mo.name]
        self.assertEqual(r_mo["ket_thuc"], 0)
        self.assertEqual(r_mo["da_chuyen_don"], 0)
        self.assertIsNone(r_mo["thoi_gian_xu_ly_gio"])

        r_kdu = by_name[khong_dap_ung.name]
        self.assertEqual(r_kdu["ket_thuc"], 1)
        self.assertEqual(r_kdu["da_chuyen_don"], 0)
        self.assertGreater(r_kdu["thoi_gian_xu_ly_gio"], 0)

        r_cd = by_name[chuyen_don.name]
        self.assertEqual(r_cd["ket_thuc"], 1)
        self.assertEqual(r_cd["da_chuyen_don"], 1)
        self.assertGreater(r_cd["thoi_gian_xu_ly_gio"], 0)
