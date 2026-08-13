"""E8 — Cấp phát hoá chất/vật tư cho khoa phòng (QĐ-9).

Nhóm TC-E8 (DevHandoff/40_TestCases.md) + các ca biên nêu trong
`.superpowers/sdd/e8/brief-cap-phat-khoa-phong.md`: mốc bật cờ
`bat_buoc_khoa_phong_tu` phải so đúng với THỜI ĐIỂM TẠO PHIẾU (không phải
thời điểm ghi sổ), và đường lưu THẬT của cổng khách (`kho_phieu_xuat_save`)
phải được test riêng — không chỉ `frappe.get_doc().save()`.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal.api import kho as kho_api
from miyano_portal.kho import khoa_phong as khoa_phong_mod
from miyano_portal.kho import ledger
from miyano_portal.setup.seed_kho_demo import seed_kho_demo

BM_USER = "bvbm@demo.miyano"
PXN_USER = "pxnabc@demo.miyano"


def _make_khoa(kho, ten, active=1):
    existing = frappe.db.get_value(
        "Customer Department", {"kho": kho, "ten_khoa_phong": ten}, "name"
    )
    if existing:
        doc = frappe.get_doc("Customer Department", existing)
        if int(doc.active) != int(active):
            doc.active = active
            doc.save(ignore_permissions=True)
        return doc
    doc = frappe.get_doc({
        "doctype": "Customer Department", "kho": kho, "ten_khoa_phong": ten,
        "active": active,
    })
    doc.insert(ignore_permissions=True)
    return doc


class _KhoE8Fixture(FrappeTestCase):
    """setUp dùng chung: kho BM sạch sổ + một lô còn hạn để xuất.

    FrappeTestCase chỉ rollback MỘT LẦN MỖI CLASS (không phải mỗi test
    method) — nhiều test dưới đây mượn CHUNG một fixture (kho_bm, đến từ
    seed_kho_demo() idempotent) rồi ghi/xoá dữ liệu lên nó. Nếu không tự dọn
    ở ĐẦU mỗi setUp(), một phiếu/khoa/cờ do test method A tạo/bật sẽ còn
    nguyên khi test method B chạy TRONG CÙNG class, làm B đỏ (hoặc tệ hơn,
    xanh SAI LÝ DO) tuỳ thứ tự chạy — cùng khuôn dọn dẹp mà
    test_kho_issue.py/test_kho_phieu_api.py đã dùng cho Ledger Entry/Lot
    Balance, mở rộng thêm Issue/Department/cờ kho vì E8 mới thêm ba nguồn
    trạng thái CHUNG đó."""

    def setUp(self):
        self.kho = seed_kho_demo()
        for k in (self.kho["kho_bm"], self.kho["kho_pxn"]):
            frappe.db.delete("Customer Stock Ledger Entry", {"kho": k})
            frappe.db.delete("Customer Stock Lot Balance", {"kho": k})
            frappe.db.delete("Customer Stock Issue", {"kho": k})
            frappe.db.delete("Customer Stock Receipt", {"kho": k})
            frappe.db.delete("Customer Department", {"kho": k})
            frappe.db.set_value("Customer Warehouse", k, {
                "bat_buoc_khoa_phong": 0, "bat_buoc_khoa_phong_tu": None,
            })
            frappe.clear_document_cache("Customer Warehouse", k)
        self.han = frappe.utils.add_days(frappe.utils.today(), 300)
        self._nhap(self.kho["kho_bm"], self.kho["vt_bm"], "LO-A", 100, 50000, self.han)

    def tearDown(self):
        frappe.set_user("Administrator")

    def _nhap(self, kho, vat_tu, so_lo, so_luong, don_gia, han):
        doc = frappe.get_doc({
            "doctype": "Customer Stock Receipt",
            "kho": kho, "ngay": "2026-02-01", "loai_nhap": "Nhập khác",
            "items": [{
                "vat_tu": vat_tu, "so_lo": so_lo, "han_su_dung": han,
                "so_luong": so_luong, "don_gia": don_gia,
            }],
        })
        doc.insert(ignore_permissions=True)
        doc.submit()
        return doc

    def _xuat(self, khoa_phong=None, loai_xuat="Xuất sử dụng", so_luong=5,
              nguoi_nhan="Nhân viên test", kho=None, vat_tu=None, so_lo="LO-A",
              ngay=None, insert=True):
        doc = frappe.get_doc({
            "doctype": "Customer Stock Issue",
            "kho": kho or self.kho["kho_bm"],
            "ngay": ngay or frappe.utils.today(),
            "loai_xuat": loai_xuat,
            "khoa_phong": khoa_phong,
            "nguoi_nhan": nguoi_nhan,
            "items": [{
                "vat_tu": vat_tu or self.kho["vt_bm"], "so_lo": so_lo,
                "so_luong": so_luong,
            }],
        })
        if insert:
            doc.insert(ignore_permissions=True)
        return doc


# ---------------------------------------------------------------------------
# US-E8.1/BR-CP1 — danh mục khoa phòng
# ---------------------------------------------------------------------------


class TestKhoaPhongCatalog(_KhoE8Fixture):
    def test_exact_duplicate_blocked_diacritic_and_case_insensitive(self):
        khoa_phong_mod.save(self.kho["kho_bm"], {"ten_khoa_phong": "Khoa Hồi sức"})
        with self.assertRaises(frappe.ValidationError):
            khoa_phong_mod.save(self.kho["kho_bm"], {"ten_khoa_phong": "khoa hoi suc"})

    def test_similar_name_suggests_does_not_block(self):
        khoa_phong_mod.save(self.kho["kho_bm"], {"ten_khoa_phong": "Khoa Hồi sức tích cực"})
        out = khoa_phong_mod.save(self.kho["kho_bm"], {
            "ten_khoa_phong": "Khoa Hồi sức tích cực1", "chi_kiem_tra": 1,
        })
        self.assertIsNone(out["name"])
        self.assertTrue(out["goi_y_trung"])
        self.assertFalse(
            frappe.db.exists("Customer Department", {
                "kho": self.kho["kho_bm"], "ten_khoa_phong": "Khoa Hồi sức tích cực1",
            }),
            "chi_kiem_tra không được ghi gì xuống DB",
        )

    def test_same_name_different_kho_allowed(self):
        khoa_phong_mod.save(self.kho["kho_bm"], {"ten_khoa_phong": "Khoa Nội"})
        # Không được ném lỗi: trùng tên GIỮA hai kho khác nhau là hợp lệ.
        khoa_phong_mod.save(self.kho["kho_pxn"], {"ten_khoa_phong": "Khoa Nội"})

    def test_used_department_cannot_be_deleted_only_deactivated(self):
        khoa = khoa_phong_mod.save(self.kho["kho_bm"], {"ten_khoa_phong": "Khoa Dùng Rồi"})
        self._xuat(khoa_phong=khoa["name"])  # draft là đủ để coi là "đã dùng"
        with self.assertRaises(frappe.ValidationError):
            frappe.delete_doc("Customer Department", khoa["name"], ignore_permissions=True)
        # Tắt (không xoá) phải làm được.
        out = khoa_phong_mod.save(self.kho["kho_bm"], {
            "name": khoa["name"], "ten_khoa_phong": "Khoa Dùng Rồi", "active": 0,
        })
        self.assertEqual(out["active"], 0)
        # Danh mục mặc định (ca_inactive=0) không còn liệt kê khoa đã tắt.
        active_rows = khoa_phong_mod.list_rows(self.kho["kho_bm"])
        self.assertNotIn(khoa["name"], [r["name"] for r in active_rows])
        all_rows = khoa_phong_mod.list_rows(self.kho["kho_bm"], ca_inactive=True)
        self.assertIn(khoa["name"], [r["name"] for r in all_rows])

    def test_inactive_department_cannot_be_selected_on_new_voucher(self):
        """NL-4.12 nửa còn lại (nửa "kiểm khi ghi sổ" đã có test riêng ở
        TestKhoaPhongInactiveGuard): khoa tắt không xuất hiện trong danh mục
        chọn của phiếu MỚI — client dựa vào kho_khoa_phong_list() mặc định
        (active=1) để dựng dropdown, nên đây chính là "không chọn được"."""
        khoa = khoa_phong_mod.save(self.kho["kho_bm"], {"ten_khoa_phong": "Khoa Tắt"})
        khoa_phong_mod.save(self.kho["kho_bm"], {"name": khoa["name"], "ten_khoa_phong": "Khoa Tắt", "active": 0})
        rows = khoa_phong_mod.list_rows(self.kho["kho_bm"])
        self.assertNotIn(khoa["name"], [r["name"] for r in rows])


class TestKhoaPhongPortalIsolation(_KhoE8Fixture):
    """TC-E8-02: KH-B gọi kho_khoa_phong_list chỉ thấy khoa của kho mình."""

    def test_list_scoped_to_own_kho(self):
        frappe.set_user(BM_USER)
        kho_api.kho_khoa_phong_save({"ten_khoa_phong": "Khoa Chỉ BM Thấy"})
        frappe.set_user(PXN_USER)
        kho_api.kho_khoa_phong_save({"ten_khoa_phong": "Khoa Chỉ PXN Thấy"})

        frappe.set_user(BM_USER)
        names = {r["ten_khoa_phong"] for r in kho_api.kho_khoa_phong_list()}
        self.assertIn("Khoa Chỉ BM Thấy", names)
        self.assertNotIn("Khoa Chỉ PXN Thấy", names)

    def test_save_on_other_customers_department_denied(self):
        frappe.set_user(PXN_USER)
        out = kho_api.kho_khoa_phong_save({"ten_khoa_phong": "Khoa PXN Sửa"})
        frappe.set_user(BM_USER)
        with self.assertRaises(frappe.PermissionError):
            kho_api.kho_khoa_phong_save({"name": out["name"], "ten_khoa_phong": "Hack"})

    def test_nguoi_nhan_goi_y_on_other_customers_department_denied(self):
        frappe.set_user(PXN_USER)
        out = kho_api.kho_khoa_phong_save({"ten_khoa_phong": "Khoa PXN NN"})
        frappe.set_user(BM_USER)
        with self.assertRaises(frappe.PermissionError):
            kho_api.kho_nguoi_nhan_goi_y(out["name"], "a")

    def test_bao_cao_cap_phat_on_other_customers_department_denied(self):
        frappe.set_user(PXN_USER)
        out = kho_api.kho_khoa_phong_save({"ten_khoa_phong": "Khoa PXN Report"})
        frappe.set_user(BM_USER)
        with self.assertRaises(frappe.PermissionError):
            kho_api.kho_bao_cao_cap_phat("2026-08-01", "2026-08-12", khoa_phong=out["name"])


# ---------------------------------------------------------------------------
# US-E8.2/BR-CP2 — điểm tinh tế nhất: mốc bật cờ so với thời điểm TẠO phiếu
# ---------------------------------------------------------------------------


class TestBatBuocKhoaPhongTiming(_KhoE8Fixture):
    def _bat_co(self, moc=None):
        """Bật cờ qua doc.save() thật (đi qua validate()) rồi, nếu có
        truyền `moc`, GHI ĐÈ mốc bằng frappe.db.set_value để test tất
        định — không phụ thuộc đồng hồ hệ thống tại lúc chạy CI."""
        w = frappe.get_doc("Customer Warehouse", self.kho["kho_bm"])
        w.bat_buoc_khoa_phong = 1
        w.save(ignore_permissions=True)
        if moc is not None:
            frappe.db.set_value(
                "Customer Warehouse", self.kho["kho_bm"], "bat_buoc_khoa_phong_tu", moc
            )
        return w

    def test_toggle_on_stamps_timestamp_exactly_once_on_0_to_1_transition(self):
        w = frappe.get_doc("Customer Warehouse", self.kho["kho_bm"])
        self.assertFalse(w.bat_buoc_khoa_phong_tu)
        w.bat_buoc_khoa_phong = 1
        w.save(ignore_permissions=True)
        w.reload()
        self.assertTrue(w.bat_buoc_khoa_phong_tu)

    def test_saving_again_while_still_on_does_not_move_the_timestamp(self):
        w = self._bat_co(moc="2026-08-12 10:00:00")
        w.reload()
        w.thu_kho = "Đổi tay khác, cờ vẫn bật"
        w.save(ignore_permissions=True)
        w.reload()
        self.assertEqual(str(w.bat_buoc_khoa_phong_tu), "2026-08-12 10:00:00")

    def test_retoggle_off_then_on_updates_to_the_latest_moment(self):
        w = self._bat_co(moc="2020-01-01 00:00:00")
        w.reload()
        w.bat_buoc_khoa_phong = 0
        w.save(ignore_permissions=True)
        w.bat_buoc_khoa_phong = 1
        w.save(ignore_permissions=True)
        w.reload()
        self.assertNotEqual(str(w.bat_buoc_khoa_phong_tu), "2020-01-01 00:00:00")

    def test_draft_created_before_moc_submits_without_khoa_phong(self):
        self._bat_co(moc="2026-08-12 10:00:00")
        doc = self._xuat(khoa_phong=None)
        frappe.db.set_value(doc.doctype, doc.name, "creation", "2026-08-12 09:00:00")
        doc.reload()
        doc.submit()  # KHÔNG được ném lỗi
        self.assertEqual(doc.docstatus, 1)

    def test_draft_created_after_moc_blocked_without_khoa_phong(self):
        self._bat_co(moc="2026-08-12 10:00:00")
        doc = self._xuat(khoa_phong=None)
        frappe.db.set_value(doc.doctype, doc.name, "creation", "2026-08-12 11:00:00")
        doc.reload()
        with self.assertRaises(frappe.ValidationError) as ctx:
            doc.submit()
        self.assertIn("Khoa phòng", str(ctx.exception))

    def test_draft_created_after_moc_submits_fine_with_khoa_phong(self):
        khoa = _make_khoa(self.kho["kho_bm"], "Khoa Đủ Điều Kiện")
        self._bat_co(moc="2026-08-12 10:00:00")
        doc = self._xuat(khoa_phong=khoa.name)
        frappe.db.set_value(doc.doctype, doc.name, "creation", "2026-08-12 11:00:00")
        doc.reload()
        doc.submit()
        self.assertEqual(doc.docstatus, 1)

    def test_other_loai_xuat_never_requires_khoa_phong_even_when_flag_on(self):
        self._bat_co(moc="2026-08-12 10:00:00")
        doc = self._xuat(khoa_phong=None, loai_xuat="Xuất huỷ - hết hạn")
        frappe.db.set_value(doc.doctype, doc.name, "creation", "2026-08-12 11:00:00")
        doc.reload()
        doc.submit()  # KHÔNG được ném lỗi — chỉ "Xuất sử dụng" mới bắt buộc
        self.assertEqual(doc.docstatus, 1)

    def test_null_moc_with_flag_on_enforces_for_every_voucher_fail_safe(self):
        """Ca biên ghi trong docstring
        CustomerWarehouse._ghi_moc_bat_buoc_khoa_phong(): cờ bật NHƯNG mốc
        rỗng (chỉ xảy ra khi bật cờ bằng đường bỏ qua validate(), ví dụ
        frappe.db.set_value thẳng) phải áp bắt buộc cho MỌI phiếu, kể cả một
        phiếu "cổ" tạo từ rất lâu — không có mốc để ân hạn."""
        frappe.db.set_value(
            "Customer Warehouse", self.kho["kho_bm"], "bat_buoc_khoa_phong", 1
        )
        self.assertFalse(
            frappe.db.get_value(
                "Customer Warehouse", self.kho["kho_bm"], "bat_buoc_khoa_phong_tu"
            )
        )
        doc = self._xuat(khoa_phong=None)
        frappe.db.set_value(doc.doctype, doc.name, "creation", "2000-01-01 00:00:00")
        doc.reload()
        with self.assertRaises(frappe.ValidationError):
            doc.submit()


class TestKhoaPhongInactiveGuard(_KhoE8Fixture):
    def test_inactive_department_blocks_submit(self):
        khoa = _make_khoa(self.kho["kho_bm"], "Khoa Sẽ Tắt")
        doc = self._xuat(khoa_phong=khoa.name)
        frappe.db.set_value("Customer Department", khoa.name, "active", 0)
        with self.assertRaises(frappe.ValidationError) as ctx:
            doc.submit()
        self.assertIn("tắt hoạt động", str(ctx.exception))

    def test_deactivating_department_after_submit_does_not_break_cancel_reversal(self):
        """Bẫy tinh vi nhất của chốt NL-4.12: nó phải hoàn toàn vắng mặt
        trên đường Phiếu đảo. _tao_phieu_dao() chạy trong on_cancel(), và
        on_cancel() KHÔNG BAO GIỜ được phép ném lỗi (xem docstring
        on_cancel trong customer_stock_issue.py) — nếu chốt lỡ áp cho cả
        phiếu đảo, một khoa bị tắt GIỮA lúc xuất và lúc huỷ sẽ làm việc HUỶ
        một phiếu ĐÃ GHI SỔ thất bại giữa chừng, để lại phiếu ở trạng thái
        không nhất quán."""
        khoa = _make_khoa(self.kho["kho_bm"], "Khoa Còn Hoạt Động Lúc Xuất")
        doc = self._xuat(khoa_phong=khoa.name, so_luong=10)
        doc.submit()
        bal_sau_xuat = ledger.get_lot_balance(self.kho["kho_bm"], self.kho["vt_bm"], "LO-A")
        self.assertEqual(bal_sau_xuat["so_luong"], 90)

        frappe.db.set_value("Customer Department", khoa.name, "active", 0)

        doc.cancel()  # KHÔNG được ném lỗi
        self.assertEqual(
            frappe.db.count(
                "Customer Stock Issue", {"phieu_goc": doc.name, "loai_xuat": "Phiếu đảo"}
            ),
            1,
            "phiếu đảo phải được sinh ra dù khoa phòng đã bị tắt",
        )
        bal_sau_huy = ledger.get_lot_balance(self.kho["kho_bm"], self.kho["vt_bm"], "LO-A")
        self.assertEqual(bal_sau_huy["so_luong"], 100, "tồn phải hoàn về đúng như trước khi xuất")


class TestKhoaPhongThuocKhoGuard(_KhoE8Fixture):
    def test_department_from_another_kho_rejected(self):
        khoa_pxn = _make_khoa(self.kho["kho_pxn"], "Khoa Của PXN")
        with self.assertRaises(frappe.ValidationError):
            self._xuat(khoa_phong=khoa_pxn.name, kho=self.kho["kho_bm"])


# ---------------------------------------------------------------------------
# "Đường lưu THẬT của cổng khách" — kho_phieu_xuat_save, không phải
# frappe.get_doc().save(). Đây là chính xác lỗ đã trả giá ở E5.
# ---------------------------------------------------------------------------


class TestKhoPhieuXuatSaveKhoaPhong(_KhoE8Fixture):
    def test_khoa_phong_and_nguoi_nhan_persist_through_the_real_endpoint(self):
        frappe.set_user(BM_USER)
        khoa = kho_api.kho_khoa_phong_save({"ten_khoa_phong": "Khoa Qua Endpoint"})
        out = kho_api.kho_phieu_xuat_save({
            "ngay": frappe.utils.today(), "loai_xuat": "Xuất sử dụng",
            "khoa_phong": khoa["name"], "nguoi_nhan": "BS. Tuấn",
            "items": [{"vat_tu": self.kho["vt_bm"], "so_lo": "LO-A", "so_luong": 5}],
        })
        self.assertEqual(out["khoa_phong"], khoa["name"])
        self.assertEqual(out["nguoi_nhan"], "BS. Tuấn")
        # Đọc lại từ DB, độc lập với hình dạng response của endpoint — chốt
        # thật là dữ liệu có NẰM XUỐNG DB hay không, không phải endpoint có
        # "vọng lại" đúng giá trị hay không.
        reloaded = frappe.get_doc("Customer Stock Issue", out["name"])
        self.assertEqual(reloaded.khoa_phong, khoa["name"])
        self.assertEqual(reloaded.nguoi_nhan, "BS. Tuấn")

    def test_khoa_phong_from_other_customer_rejected_through_endpoint(self):
        """Endpoint (kho_phieu_xuat_save) CỐ Ý không kiểm sở hữu khoa_phong —
        chốt chặn thật nằm ở controller (_validate_khoa_phong_thuoc_kho,
        chạy trong validate()) — nên vẫn phải chặn được, chỉ là chặn ở TẦNG
        KHÁC. Test này đi qua ĐÚNG đường lưu thật của SPA để xác nhận điều
        đó, không giả định suông."""
        frappe.set_user(PXN_USER)
        khoa_pxn = kho_api.kho_khoa_phong_save({"ten_khoa_phong": "Khoa PXN Qua Endpoint"})
        frappe.set_user(BM_USER)
        with self.assertRaises(frappe.ValidationError) as ctx:
            kho_api.kho_phieu_xuat_save({
                "ngay": frappe.utils.today(), "loai_xuat": "Xuất sử dụng",
                "khoa_phong": khoa_pxn["name"],
                "items": [{"vat_tu": self.kho["vt_bm"], "so_lo": "LO-A", "so_luong": 5}],
            })
        self.assertIn("không thuộc kho", str(ctx.exception))


# ---------------------------------------------------------------------------
# US-E8.3/BR-CP3 — gợi ý Người nhận
# ---------------------------------------------------------------------------


class TestNguoiNhanGoiY(_KhoE8Fixture):
    def setUp(self):
        super().setUp()
        self.khoa_hs = _make_khoa(self.kho["kho_bm"], "Khoa Hồi sức")
        self.khoa_xn = _make_khoa(self.kho["kho_bm"], "Khoa Xét nghiệm")
        for nguoi_nhan in ("BS. Tuấn", "ĐD. Lan"):
            doc = self._xuat(khoa_phong=self.khoa_hs.name, nguoi_nhan=nguoi_nhan, so_luong=1)
            doc.submit()
        doc = self._xuat(khoa_phong=self.khoa_xn.name, nguoi_nhan="KTV. Hùng", so_luong=1)
        doc.submit()

    def test_suggests_matching_recipients_scoped_to_department(self):
        out = khoa_phong_mod.nguoi_nhan_goi_y(self.kho["kho_bm"], self.khoa_hs.name, "t")
        self.assertEqual(out, ["BS. Tuấn"])

    def test_suggestions_do_not_bleed_across_departments(self):
        out = khoa_phong_mod.nguoi_nhan_goi_y(self.kho["kho_bm"], self.khoa_xn.name, None)
        self.assertIn("KTV. Hùng", out)
        self.assertNotIn("BS. Tuấn", out)
        self.assertNotIn("ĐD. Lan", out)

    def test_free_text_recipient_not_in_history_is_not_blocked(self):
        doc = self._xuat(khoa_phong=self.khoa_hs.name, nguoi_nhan="Người hoàn toàn mới")
        doc.submit()  # không bị chặn dù tên chưa từng xuất hiện

    def test_recipient_over_100_chars_rejected(self):
        with self.assertRaises(frappe.ValidationError):
            self._xuat(khoa_phong=self.khoa_hs.name, nguoi_nhan="A" * 101)


# ---------------------------------------------------------------------------
# US-E8.4/BR-CP5/TC-E8-09 — in phiếu hiển thị khoa phòng + người nhận
# ---------------------------------------------------------------------------


class TestInPhieuKhoaPhong(_KhoE8Fixture):
    def test_tt107_and_tt200_show_department_name_and_recipient(self):
        from frappe.www.printview import get_html_and_style
        from miyano_portal.setup.install_kho_print_formats import NAME_XUAT_TT107, NAME_XUAT_TT200

        khoa = _make_khoa(self.kho["kho_bm"], "Khoa In Phiếu")
        doc = self._xuat(khoa_phong=khoa.name, nguoi_nhan="BS. In Test")
        doc.submit()

        for print_format in (NAME_XUAT_TT107, NAME_XUAT_TT200):
            with self.subTest(print_format=print_format):
                html = get_html_and_style(doc=doc.as_json(), print_format=print_format)["html"]
                self.assertIn("Khoa phòng nhận", html)
                self.assertIn("Khoa In Phiếu", html)
                self.assertIn("BS. In Test", html)

    def test_tt107_hides_department_line_when_not_set(self):
        """Chốt ngược của guard `{% if doc.khoa_phong %}`: một phiếu KHÔNG
        gắn khoa (kho chưa bật bắt buộc) không được hiện một dòng "Khoa
        phòng nhận:" trống rỗng — client sẽ đọc dòng trống đó như một lỗi
        dữ liệu thay vì đúng ý nghĩa "chưa gắn khoa"."""
        from frappe.www.printview import get_html_and_style
        from miyano_portal.setup.install_kho_print_formats import NAME_XUAT_TT107

        doc = self._xuat(khoa_phong=None)
        doc.submit()
        html = get_html_and_style(doc=doc.as_json(), print_format=NAME_XUAT_TT107)["html"]
        self.assertNotIn("Khoa phòng nhận", html)

    def test_render_phieu_html_portal_route_also_shows_department(self):
        """`_render_phieu_html()` (cổng portal, KHÔNG đi qua
        frappe.www.printview) là đường render THẬT SỰ mà kho_phieu_pdf()
        dùng — phải kiểm riêng, không suy diễn từ đường desk ở trên (hai
        đường từng lệch context biến, xem test_kho_phieu_api.py)."""
        khoa = _make_khoa(self.kho["kho_bm"], "Khoa Portal Render")
        doc = self._xuat(khoa_phong=khoa.name, nguoi_nhan="ĐD. Portal")
        doc.submit()
        frappe.set_user(BM_USER)
        html = kho_api._render_phieu_html("Customer Stock Issue", doc.name, self.kho["kho_bm"])
        self.assertIn("Khoa Portal Render", html)
        self.assertIn("ĐD. Portal", html)


# ---------------------------------------------------------------------------
# US-E8.5/BR-CP4/TC-E8-07 — bộ số chuẩn của PRD E8
# ---------------------------------------------------------------------------


class TestBaoCaoCapPhat(_KhoE8Fixture):
    """Kỳ 01-12/08: Khoa Hồi sức 2 phiếu (Găng M 8 hộp x46.000 + Cồn 10 chai
    x17.000) = 538.000; Khoa Xét nghiệm 1 phiếu (Găng M 12 hộp x46.000) =
    552.000; 1 phiếu Xuất sử dụng KHÔNG gắn khoa: 5 hộp x46.000 = 230.000.
    Tổng = 1.320.000; %: 40,8 / 41,8 / 17,4. Phiếu bị đảo không tính.
    """

    def setUp(self):
        super().setUp()
        # setUp() của _KhoE8Fixture đã nhập LO-A giá 50.000 — không dùng ở
        # đây, cần đúng giá 46.000/17.000 nêu trong PRD nên nhập LÔ RIÊNG.
        self._nhap(self.kho["kho_bm"], self.kho["vt_bm"], "LO-GANG", 100, 46000, self.han)
        # Idempotent — cùng lý do _make_khoa/_make_ncc: setUp() chạy lại
        # nhiều lần trong cùng class (chỉ Ledger/Lot/Issue/Receipt/Department
        # được _KhoE8Fixture dọn ở đầu mỗi lần, KHÔNG dọn Warehouse Item vì
        # nó là danh mục lâu dài, không phải chứng từ theo kỳ).
        existing = frappe.db.get_value(
            "Customer Warehouse Item", {"kho": self.kho["kho_bm"], "ma_vat_tu": "CON-70"}, "name"
        )
        if existing:
            self.vt_con = frappe.get_doc("Customer Warehouse Item", existing)
        else:
            self.vt_con = frappe.get_doc({
                "doctype": "Customer Warehouse Item", "kho": self.kho["kho_bm"],
                "ma_vat_tu": "CON-70", "ten_vat_tu": "Cồn 70° 500ml", "dvt": "Chai",
            })
            self.vt_con.insert(ignore_permissions=True)
        self._nhap(self.kho["kho_bm"], self.vt_con.name, "LO-CON", 100, 17000, self.han)

        self.khoa_hs = _make_khoa(self.kho["kho_bm"], "Khoa Hồi sức")
        self.khoa_xn = _make_khoa(self.kho["kho_bm"], "Khoa Xét nghiệm")

        # Khoa Hồi sức: 2 phiếu.
        self._xuat_va_ghi_so(self.khoa_hs.name, self.kho["vt_bm"], "LO-GANG", 8, "BS. Tuấn")
        self._xuat_va_ghi_so(self.khoa_hs.name, self.vt_con.name, "LO-CON", 10, "ĐD. Lan")
        # Khoa Xét nghiệm: 1 phiếu.
        self._xuat_va_ghi_so(self.khoa_xn.name, self.kho["vt_bm"], "LO-GANG", 12, "KTV. Hùng")
        # Chưa gắn khoa (kho chưa bật bắt buộc — mặc định trong setUp).
        self._xuat_va_ghi_so(None, self.kho["vt_bm"], "LO-GANG", 5, "Không ghi")

        # Phiếu bị đảo: xuất rồi huỷ — KHÔNG được tính vào báo cáo.
        self.doc_se_huy = self._xuat_va_ghi_so(
            self.khoa_hs.name, self.kho["vt_bm"], "LO-GANG", 3, "Sẽ bị huỷ"
        )
        self.doc_se_huy.cancel()

    def _xuat_va_ghi_so(self, khoa_phong, vat_tu, so_lo, so_luong, nguoi_nhan):
        doc = self._xuat(
            khoa_phong=khoa_phong, vat_tu=vat_tu, so_lo=so_lo, so_luong=so_luong,
            nguoi_nhan=nguoi_nhan, ngay="2026-08-05",
        )
        doc.submit()
        return doc

    def test_exact_numbers_from_prd(self):
        result = self._chay()
        self.assertAlmostEqual(result["tong_gia_tri"], 1320000, places=2)

        by_ten = {n["ten_hien_thi"]: n for n in result["nhom"]}
        self.assertIn("Khoa Hồi sức", by_ten)
        self.assertIn("Khoa Xét nghiệm", by_ten)
        self.assertIn("Chưa gắn khoa", by_ten)

        self.assertAlmostEqual(by_ten["Khoa Hồi sức"]["gia_tri"], 538000, places=2)
        self.assertAlmostEqual(by_ten["Khoa Xét nghiệm"]["gia_tri"], 552000, places=2)
        self.assertAlmostEqual(by_ten["Chưa gắn khoa"]["gia_tri"], 230000, places=2)

        self.assertAlmostEqual(by_ten["Khoa Hồi sức"]["pct"], 40.8, places=1)
        self.assertAlmostEqual(by_ten["Khoa Xét nghiệm"]["pct"], 41.8, places=1)
        self.assertAlmostEqual(by_ten["Chưa gắn khoa"]["pct"], 17.4, places=1)

    def test_chua_gan_khoa_group_is_separate_not_hidden(self):
        result = self._chay()
        khoa_phong_values = [n["khoa_phong"] for n in result["nhom"]]
        self.assertIn(None, khoa_phong_values, "nhóm Chưa gắn khoa phải có mặt, không bị giấu")

    def test_reversed_voucher_excluded(self):
        result = self._chay()
        all_phieu = {row["phieu"] for n in result["nhom"] for row in n["dong"]}
        self.assertNotIn(self.doc_se_huy.name, all_phieu)
        # Đảo cũng không lẻn vào dưới danh nghĩa "Phiếu đảo" của chính nó.
        dao_name = frappe.db.get_value(
            "Customer Stock Issue", {"phieu_goc": self.doc_se_huy.name}, "name"
        )
        self.assertIsNotNone(dao_name)
        self.assertNotIn(dao_name, all_phieu)

    def test_drill_down_row_has_receiver_and_voucher(self):
        result = self._chay()
        by_ten = {n["ten_hien_thi"]: n for n in result["nhom"]}
        dong_hs = by_ten["Khoa Hồi sức"]["dong"]
        nguoi_nhan_set = {d["nguoi_nhan"] for d in dong_hs}
        self.assertEqual(nguoi_nhan_set, {"BS. Tuấn", "ĐD. Lan"})
        for d in dong_hs:
            self.assertTrue(d["phieu"])

    def test_desk_report_scoped_to_customer_no_leak(self):
        from miyano_portal.kho import desk_reports
        rows_bm = desk_reports.cap_phat_theo_khoa_rows(
            customer="Bệnh viện Bạch Mai", tu_ngay="2026-08-01", den_ngay="2026-08-12",
        )
        rows_pxn = desk_reports.cap_phat_theo_khoa_rows(
            customer="PXN ABC", tu_ngay="2026-08-01", den_ngay="2026-08-12",
        )
        self.assertTrue(rows_bm)
        self.assertEqual(rows_pxn, [])
        for r in rows_bm:
            self.assertEqual(r["customer"], "Bệnh viện Bạch Mai")

    def _chay(self):
        """Chạy qua ĐÚNG cổng cổng khách (kho_api.kho_bao_cao_cap_phat),
        không gọi thẳng reports.bao_cao_cap_phat_rows() — kho phải được suy
        từ phiên đăng nhập BM_USER, giống hệt SPA thật."""
        frappe.set_user(BM_USER)
        try:
            return kho_api.kho_bao_cao_cap_phat("2026-08-01", "2026-08-12")
        finally:
            frappe.set_user("Administrator")
