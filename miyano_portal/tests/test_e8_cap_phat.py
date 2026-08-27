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
    """P2 #1 (kiểm thử hệ thống): TC-E8-01 bản trước gọi thẳng
    `khoa_phong_mod.save(kho, {...})` với `kho` tiêm tay — không `set_user`
    nào ở đây từng được đọc để suy ra kho. Đường thật của cổng khách là
    `kho_khoa_phong_save` (kho suy từ `get_portal_kho()`)."""

    def test_exact_duplicate_blocked_diacritic_and_case_insensitive(self):
        """TC-E8-01 (Â): trùng tuyệt đối (bỏ dấu/hoa-thường) trong kho -> chặn."""
        frappe.set_user(BM_USER)
        kho_api.kho_khoa_phong_save({"ten_khoa_phong": "Khoa Hồi sức"})
        with self.assertRaises(frappe.ValidationError):
            kho_api.kho_khoa_phong_save({"ten_khoa_phong": "khoa hoi suc"})

    def test_similar_name_suggests_does_not_block(self):
        """TC-E8-01 (B): gần giống -> KHÔNG chặn, trả goi_y_trung."""
        frappe.set_user(BM_USER)
        kho_api.kho_khoa_phong_save({"ten_khoa_phong": "Khoa Hồi sức tích cực"})
        out = kho_api.kho_khoa_phong_save({
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
        frappe.set_user(BM_USER)
        kho_api.kho_khoa_phong_save({"ten_khoa_phong": "Khoa Nội"})
        # Không được ném lỗi: trùng tên GIỮA hai kho khác nhau là hợp lệ —
        # mỗi kho suy từ đúng phiên đăng nhập của khách đó.
        frappe.set_user(PXN_USER)
        kho_api.kho_khoa_phong_save({"ten_khoa_phong": "Khoa Nội"})

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

    def test_90n_stats_exclude_cancelled_and_reversal_vouchers(self):
        """F-3 (review E8, CHẶN): thủ kho xuất rồi huỷ ngay vì nhầm khoa —
        kịch bản đời thật, không phải tình huống hiếm. Phiếu GỐC rớt khỏi
        docstatus=1 một cách tự nhiên, nhưng phiếu ĐẢO (hệ tự tạo, BR-K9)
        docstatus=1 và mang khoa_phong + tong_tien dương y hệt phiếu gốc —
        nếu _thong_ke_90n không tự loại "Phiếu đảo", màn "Danh mục khoa
        phòng" sẽ hiện 1 phiếu/giá trị dương cho một khoa mà báo cáo cấp
        phát (đúng) lại hiện 0 — hai con số của CÙNG một khoa chọi nhau."""
        khoa = khoa_phong_mod.save(self.kho["kho_bm"], {"ten_khoa_phong": "Khoa Xuất Rồi Huỷ"})
        doc = self._xuat(khoa_phong=khoa["name"], so_luong=10, ngay=frappe.utils.today())
        doc.submit()
        doc.cancel()

        rows = khoa_phong_mod.list_rows(self.kho["kho_bm"])
        row = next(r for r in rows if r["name"] == khoa["name"])
        self.assertEqual(row["so_phieu_90n"], 0, "phiếu đã huỷ + phiếu đảo không được tính")
        self.assertEqual(row["gia_tri_90n"], 0.0, "phiếu đã huỷ + phiếu đảo không được tính")

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

    def test_null_moc_self_heals_and_grandfathers_existing_drafts(self):
        """F-1 (review E8) — quyết định ĐÃ ĐỔI HƯỚNG: cờ bật NHƯNG mốc rỗng
        (chỉ xảy ra khi bật cờ bằng đường bỏ qua validate() — kịch bản THẬT
        là patch rollout/Data Import bật hàng loạt cho nhiều bệnh viện) KHÔNG
        còn áp bắt buộc cho MỌI phiếu (bản đầu làm vậy — SAI HƯỚNG, tự đóng
        băng mọi phiếu nháp đang mở ở mọi kho, đúng "khoá tồn đọng" mà
        NL-4.11 sinh ra để tránh). Giờ tự lành: ghi now() làm mốc ngay lần
        đầu chạm phải, ân hạn đúng cho MỌI phiếu nháp đang tồn — kể cả một
        phiếu "cổ" tạo từ rất lâu."""
        frappe.db.set_value(
            "Customer Warehouse", self.kho["kho_bm"], "bat_buoc_khoa_phong", 1
        )
        self.assertFalse(
            frappe.db.get_value(
                "Customer Warehouse", self.kho["kho_bm"], "bat_buoc_khoa_phong_tu"
            )
        )
        doc_cu = self._xuat(khoa_phong=None)
        frappe.db.set_value(doc_cu.doctype, doc_cu.name, "creation", "2000-01-01 00:00:00")
        doc_cu.reload()
        doc_cu.submit()  # KHÔNG được ném lỗi — được ân hạn (tự lành)
        self.assertEqual(doc_cu.docstatus, 1)

        # Mốc giờ đã được ghi (tự lành) — kiểm tra ngược lại tính hội tụ:
        moc_sau_tu_lanh = frappe.db.get_value(
            "Customer Warehouse", self.kho["kho_bm"], "bat_buoc_khoa_phong_tu"
        )
        self.assertTrue(moc_sau_tu_lanh, "phải ghi lại mốc để lần sau khỏi tự lành lại")

        # Một phiếu MỚI, tạo SAU thời điểm tự lành, vẫn phải bị chặn như bình
        # thường — tự lành không có nghĩa là tắt hẳn chốt.
        doc_moi = self._xuat(khoa_phong=None)
        with self.assertRaises(frappe.ValidationError):
            doc_moi.submit()


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
        """SỬA (đợt sửa cuối, C-1): trước đây endpoint CỐ Ý không kiểm sở
        hữu `khoa_phong`, dựa vào chốt chặn ở tầng controller
        (`_validate_khoa_phong_thuoc_kho`, chạy trong `validate()`) — nhưng
        đó chính là oracle "hai loại lỗi/hai thông điệp phân biệt tồn tại
        docname" (một `KP-#####` bịa chết bằng `LinkValidationError` tiếng
        Anh ở `_validate_links()`, một khoa CÓ THẬT của khách khác chết
        bằng `ValidationError` tiếng Việt ở controller). Endpoint giờ tự
        guard bằng `_khoa_cua_kho()` TRƯỚC khi giá trị chạm `insert()`,
        chặn bằng `PermissionError` — cùng khuôn `_thiet_bi_cua_khach()`.
        Test này đi qua ĐÚNG đường lưu thật của SPA để xác nhận điều đó,
        không giả định suông."""
        frappe.set_user(PXN_USER)
        khoa_pxn = kho_api.kho_khoa_phong_save({"ten_khoa_phong": "Khoa PXN Qua Endpoint"})
        frappe.set_user(BM_USER)
        with self.assertRaises(frappe.PermissionError) as ctx:
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
        """TC-E8-06 (C): P2 #1 (kiểm thử hệ thống) — TC nêu đích danh
        `kho_nguoi_nhan_goi_y(...)`, đường thật của cổng khách, chứ không
        phải `khoa_phong_mod.nguoi_nhan_goi_y(kho, khoa, tu_khoa)` gọi thẳng
        với `kho` tiêm tay (khác arity: endpoint không nhận `kho` từ client,
        tự suy từ phiên qua `get_portal_kho()`)."""
        frappe.set_user(BM_USER)
        out = kho_api.kho_nguoi_nhan_goi_y(self.khoa_hs.name, "t")
        self.assertEqual(out, ["BS. Tuấn"])

    def test_suggestions_do_not_bleed_across_departments(self):
        frappe.set_user(BM_USER)
        out = kho_api.kho_nguoi_nhan_goi_y(self.khoa_xn.name, None)
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
    """F-4 (review E8, CHẶN) đã đổi thiết kế: khoa phòng KHÔNG in thành một
    dòng riêng "Khoa phòng nhận:" nữa (sẽ chọi với dòng "Nơi nhận" cũ, xem
    docstring đầu install_kho_print_formats.py) — tên khoa giờ THAY THẾ giá
    trị của chính ô "Nơi nhận" khi có `khoa_phong`. Các test dưới đây khoá
    đúng thiết kế MỚI, không còn tìm nhãn "Khoa phòng nhận"."""

    def test_tt107_and_tt200_show_department_as_the_noi_nhan_value(self):
        from frappe.www.printview import get_html_and_style
        from miyano_portal.setup.install_kho_print_formats import NAME_XUAT_TT107, NAME_XUAT_TT200

        khoa = _make_khoa(self.kho["kho_bm"], "Khoa In Phiếu")
        doc = self._xuat(khoa_phong=khoa.name, nguoi_nhan="BS. In Test")
        doc.submit()

        for print_format in (NAME_XUAT_TT107, NAME_XUAT_TT200):
            with self.subTest(print_format=print_format):
                html = get_html_and_style(doc=doc.as_json(), print_format=print_format)["html"]
                self.assertNotIn("Khoa phòng nhận", html, "không còn dòng riêng — đã gộp vào Nơi nhận")
                self.assertIn("Khoa In Phiếu", html)
                self.assertIn("BS. In Test", html)

    def test_department_wins_over_stale_noi_nhan_no_conflicting_statement(self):
        """Đúng kịch bản F-4 nêu: thủ kho gõ `noi_nhan` tự do THEO THÓI QUEN
        CŨ (trước khi chọn khoa phòng có cấu trúc) rồi mới chọn khoa_phong —
        hai giá trị lệch nhau. Phiếu in ra chỉ được có ĐÚNG MỘT phát biểu về
        nơi nhận: tên khoa (có cấu trúc, đáng tin hơn), không phải cả hai."""
        from frappe.www.printview import get_html_and_style
        from miyano_portal.setup.install_kho_print_formats import NAME_XUAT_TT107

        khoa = _make_khoa(self.kho["kho_bm"], "Khoa Đúng")
        doc = self._xuat(khoa_phong=khoa.name)
        doc.noi_nhan = "Khoa Sai (gõ tay trước đó)"
        doc.save(ignore_permissions=True)
        doc.submit()
        html = get_html_and_style(doc=doc.as_json(), print_format=NAME_XUAT_TT107)["html"]
        self.assertIn("Khoa Đúng", html)
        self.assertNotIn("Khoa Sai (gõ tay trước đó)", html)

    def test_tt107_still_shows_free_text_noi_nhan_when_no_department(self):
        """Đường lùi: phiếu KHÔNG gắn khoa_phong (kho chưa bật bắt buộc) vẫn
        phải hiện đúng `noi_nhan` tự do như hành vi trước E8 — không bị f-4
        vô tình xoá mất đường cũ."""
        from frappe.www.printview import get_html_and_style
        from miyano_portal.setup.install_kho_print_formats import NAME_XUAT_TT107

        doc = self._xuat(khoa_phong=None)
        doc.noi_nhan = "Khoa Hồi sức tích cực"
        doc.save(ignore_permissions=True)
        doc.submit()
        html = get_html_and_style(doc=doc.as_json(), print_format=NAME_XUAT_TT107)["html"]
        self.assertIn("Khoa Hồi sức tích cực", html)

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
        self.dao_cua_doc_se_huy = frappe.db.get_value(
            "Customer Stock Issue", {"phieu_goc": self.doc_se_huy.name}, "name"
        )
        # F-2 (review E8, CHẶN): _tao_phieu_dao() luôn đặt `ngay = today()`
        # (ngày HUỶ THẬT, không phải ngày phiếu gốc) — nếu suite chạy vào một
        # ngày NGOÀI kỳ báo cáo cố định 01-12/08/2026 (rất có thể, vì đây là
        # demo data cố định còn "hôm nay" thì trôi), phiếu đảo tự bị BỘ LỌC
        # NGÀY loại ra trước khi kịp chạm tới chốt `loai_xuat != "Xuất sử
        # dụng"` mà reports.bao_cao_cap_phat_rows() thực sự dùng để loại nó
        # (BR-CP4) — nghĩa là chốt ĐÓ không hề được test này chạm tới, và sức
        # chẩn đoán của cả lớp test phụ thuộc lịch chạy CI. Ép cả phiếu đảo
        # LẪN dòng sổ của nó vào TRONG kỳ (ngày huỷ 08/08, cùng kỳ với ngày
        # xuất 05/08 — đúng kịch bản thật "huỷ trong vài ngày") để buộc report
        # phải tự loại bằng ĐÚNG cơ chế loai_xuat, không nhờ ngày tháng.
        frappe.db.set_value("Customer Stock Issue", self.dao_cua_doc_se_huy, "ngay", "2026-08-08")
        frappe.db.set_value(
            "Customer Stock Ledger Entry", {"chung_tu": self.dao_cua_doc_se_huy}, "ngay", "2026-08-08"
        )

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

        # F-2 (review E8): với phiếu đảo giờ nằm TRONG kỳ (setUp), 538.000
        # đúng bằng số PRD CHỈ KHI report tự loại đúng bằng loai_xuat, không
        # phải nhờ ngày tháng — nếu chốt đó vỡ (gộp lẫn "Phiếu đảo"), dòng bù
        # trừ 3 hộp sẽ bị trừ khống vào Khoa Hồi sức (số âm), 538.000 sẽ tụt
        # xuống ~92.000 và test này tự đỏ vì SỐ sai, không cần biết thêm gì.
        for n in result["nhom"]:
            for d in n["dong"]:
                self.assertGreaterEqual(d["gia_tri"], 0, "không dòng nào được mang giá trị âm")
                self.assertGreaterEqual(d["sl"], 0, "không dòng nào được mang số lượng âm")

    def test_chua_gan_khoa_group_is_separate_not_hidden(self):
        result = self._chay()
        khoa_phong_values = [n["khoa_phong"] for n in result["nhom"]]
        self.assertIn(None, khoa_phong_values, "nhóm Chưa gắn khoa phải có mặt, không bị giấu")

    def test_reversed_voucher_excluded(self):
        """Phiếu đảo (self.dao_cua_doc_se_huy) được ép nằm TRONG kỳ báo cáo ở
        setUp() — nên phép loại trừ dưới đây chỉ pass được nhờ ĐÚNG chốt
        `loai_xuat != "Xuất sử dụng"` (BR-CP4), không nhờ bộ lọc ngày (xem
        F-2, review E8: trước bản sửa, test này xanh vì lý do sai)."""
        result = self._chay()
        all_phieu = {row["phieu"] for n in result["nhom"] for row in n["dong"]}
        self.assertNotIn(self.doc_se_huy.name, all_phieu)
        # Đảo cũng không lẻn vào dưới danh nghĩa "Phiếu đảo" của chính nó.
        self.assertIsNotNone(self.dao_cua_doc_se_huy)
        self.assertNotIn(self.dao_cua_doc_se_huy, all_phieu)

        # Khoa Hồi sức KHÔNG được bị trừ khống bởi dòng bù trừ (3 hộp x
        # 46.000 = 138.000): nếu chốt loai_xuat vỡ, dòng đảo (so_luong DƯƠNG,
        # xem docstring ledger.post_lines) sẽ bị hàm đảo dấu (-e["so_luong"])
        # biến thành ÂM trong bao_cao_cap_phat_rows, kéo tổng của khoa xuống
        # dưới 538.000 đúng 138.000 — số PRD (538.000, đã khẳng định ở
        # test_exact_numbers_from_prd) TỰ NÓ là bằng chứng, nhắc lại ở đây để
        # ý định của test không phụ thuộc test khác.
        by_ten = {n["ten_hien_thi"]: n for n in result["nhom"]}
        self.assertAlmostEqual(by_ten["Khoa Hồi sức"]["gia_tri"], 538000, places=2)

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


# ---------------------------------------------------------------------------
# Yêu cầu chủ đầu tư 2026-08-17 — cấp phát GỘP THEO THÁNG × khoa phòng
# ---------------------------------------------------------------------------


class TestBaoCaoCapPhatTheoThang(_KhoE8Fixture):
    """Kỳ 01/06 - 31/08/2026, kho Bạch Mai:

      * Khoa Hồi sức, tháng 06: MỘT phiếu hai vật tư — Găng 4 hộp x46.000
        (184.000) + Cồn 5 chai x17.000 (85.000) = 269.000;
      * Khoa Hồi sức, tháng 07: một phiếu Găng 3 hộp ĐÃ HUỶ (phiếu đảo bị ép
        nằm TRONG kỳ) — tháng 07 phải KHÔNG có dòng nào;
      * Khoa Hồi sức, tháng 08: Găng 2 hộp = 92.000;
      * Khoa Xét nghiệm, tháng 08: Găng 3 hộp = 138.000;
      * Chưa gắn khoa, tháng 06: Găng 1 hộp = 46.000.

    Tổng kỳ = 545.000.

    Vì sao bộ số này chứ không phải bộ số của TestBaoCaoCapPhat: ba tính chất
    mà chỉ báo cáo THEO THÁNG mới có cơ hội làm sai đều nằm trong đó — biên
    giữa hai tháng, một tháng bị rỗng vì phiếu đảo (mà không được kéo tháng
    khác lệch theo), và một phiếu nhiều vật tư (số phiếu phải ĐẾM PHÂN BIỆT,
    số lượng KHÔNG được cộng qua hai ĐVT).
    """

    TU_NGAY = "2026-06-01"
    DEN_NGAY = "2026-08-31"

    def setUp(self):
        super().setUp()
        # Lô riêng đúng đơn giá của bộ số trên (LO-A của fixture là 50.000).
        self._nhap(self.kho["kho_bm"], self.kho["vt_bm"], "LO-GANG", 100, 46000, self.han)
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

        # Tháng 06 — MỘT phiếu, HAI vật tư khác ĐVT (Hộp/Chai).
        self.phieu_t6 = self._xuat_nhieu("2026-06-10", self.khoa_hs.name, [
            (self.kho["vt_bm"], "LO-GANG", 4),
            (self.vt_con.name, "LO-CON", 5),
        ])
        # Tháng 06 — chưa gắn khoa (kho chưa bật bắt buộc, mặc định của fixture).
        self._xuat_nhieu("2026-06-20", None, [(self.kho["vt_bm"], "LO-GANG", 1)])
        # Tháng 08.
        self._xuat_nhieu("2026-08-05", self.khoa_hs.name, [(self.kho["vt_bm"], "LO-GANG", 2)])
        self._xuat_nhieu("2026-08-07", self.khoa_xn.name, [(self.kho["vt_bm"], "LO-GANG", 3)])

        # Tháng 07 — xuất rồi huỷ. Cùng bài học F-2 (review E8): _tao_phieu_dao
        # luôn đặt ngày = HÔM NAY, nên nếu không ép phiếu đảo vào TRONG kỳ thì
        # nó bị bộ lọc ngày loại hộ và chốt `loai_xuat != "Xuất sử dụng"` không
        # hề được test này chạm tới — test sẽ xanh vì lý do sai.
        self.phieu_t7 = self._xuat_nhieu(
            "2026-07-05", self.khoa_hs.name, [(self.kho["vt_bm"], "LO-GANG", 3)]
        )
        self.phieu_t7.cancel()
        self.dao_t7 = frappe.db.get_value(
            "Customer Stock Issue", {"phieu_goc": self.phieu_t7.name}, "name"
        )
        frappe.db.set_value("Customer Stock Issue", self.dao_t7, "ngay", "2026-07-20")
        frappe.db.set_value(
            "Customer Stock Ledger Entry", {"chung_tu": self.dao_t7}, "ngay", "2026-07-20"
        )

    def _xuat_nhieu(self, ngay, khoa_phong, items):
        """Một phiếu xuất NHIỀU dòng — `_xuat()` của fixture chỉ dựng một dòng,
        mà tính chất "một phiếu nhiều vật tư vẫn là MỘT phiếu" thì không thể
        test bằng phiếu một dòng."""
        doc = frappe.get_doc({
            "doctype": "Customer Stock Issue",
            "kho": self.kho["kho_bm"], "ngay": ngay, "loai_xuat": "Xuất sử dụng",
            "khoa_phong": khoa_phong, "nguoi_nhan": "ĐD. Trực",
            "items": [
                {"vat_tu": vt, "so_lo": lo, "so_luong": sl} for vt, lo, sl in items
            ],
        })
        doc.insert(ignore_permissions=True)
        doc.submit()
        return doc

    # --- helpers -----------------------------------------------------------

    def _chay(self, **kwargs):
        """Qua ĐÚNG cổng cổng khách — kho phải suy từ phiên BM_USER, không
        truyền tay vào reports.*, giống hệt SPA thật."""
        frappe.set_user(BM_USER)
        try:
            return kho_api.kho_bao_cao_cap_phat_thang(self.TU_NGAY, self.DEN_NGAY, **kwargs)
        finally:
            frappe.set_user("Administrator")

    def _theo_khoa_thang(self, ket_qua=None):
        kq = ket_qua or self._chay()
        return {(n["ten_hien_thi"], n["thang"]): n for n in kq["nhom"]}

    # --- các con số --------------------------------------------------------

    def test_gop_dung_tung_thang_cho_tung_khoa(self):
        kq = self._chay()
        m = self._theo_khoa_thang(kq)

        self.assertAlmostEqual(m[("Khoa Hồi sức", "2026-06")]["gia_tri"], 269000, places=2)
        self.assertAlmostEqual(m[("Khoa Hồi sức", "2026-08")]["gia_tri"], 92000, places=2)
        self.assertAlmostEqual(m[("Khoa Xét nghiệm", "2026-08")]["gia_tri"], 138000, places=2)
        self.assertAlmostEqual(m[("Chưa gắn khoa", "2026-06")]["gia_tri"], 46000, places=2)
        self.assertAlmostEqual(kq["tong_gia_tri"], 545000, places=2)

    def test_thang_khong_phat_sinh_thi_khong_co_dong(self):
        """Khoa Hồi sức không có gì trong tháng 07 (phiếu duy nhất đã huỷ) —
        không được sinh ra một dòng 0 đồng, và cũng không được vắng mặt ở hai
        tháng nó CÓ phát sinh."""
        m = self._theo_khoa_thang()
        self.assertNotIn(("Khoa Hồi sức", "2026-07"), m)
        self.assertIn(("Khoa Hồi sức", "2026-06"), m)
        self.assertIn(("Khoa Hồi sức", "2026-08"), m)

    def test_phieu_dao_khong_lam_lech_thang_khac(self):
        """Phiếu đảo nằm TRONG kỳ (ép ở setUp) nên chỉ chốt `loai_xuat` mới
        loại được nó. Nếu chốt đó vỡ, dòng bù trừ 3 hộp x46.000 = 138.000 (số
        lượng DƯƠNG trên sổ, bị hàm đảo dấu thành ÂM) sẽ hiện ra thành một
        tháng 07 giá trị -138.000 và kéo tổng kỳ từ 545.000 xuống 407.000 —
        cả hai khẳng định dưới đây tự đỏ."""
        # Chống test rỗng nghĩa: khẳng định phiếu đảo THẬT SỰ đang nằm trong
        # kỳ và mang số lượng DƯƠNG trên sổ. Không có ba dòng này thì cả test
        # có thể xanh chỉ vì bộ lọc ngày đã loại hộ, và phép loại theo
        # `loai_xuat` chưa từng được chạm tới (đúng lỗi F-2 của review E8).
        self.assertIsNotNone(self.dao_t7)
        so_lieu_dao = frappe.db.get_all(
            "Customer Stock Ledger Entry",
            filters={"chung_tu": self.dao_t7},
            fields=["ngay", "so_luong", "da_dao"],
        )
        self.assertTrue(so_lieu_dao)
        for r in so_lieu_dao:
            self.assertTrue(
                frappe.utils.getdate(self.TU_NGAY)
                <= frappe.utils.getdate(r.ngay)
                <= frappe.utils.getdate(self.DEN_NGAY)
            )
            self.assertGreater(r.so_luong, 0)
            self.assertEqual(int(r.da_dao or 0), 0)

        kq = self._chay()
        m = self._theo_khoa_thang(kq)
        self.assertNotIn(("Khoa Hồi sức", "2026-07"), m)
        self.assertAlmostEqual(kq["tong_gia_tri"], 545000, places=2)
        for n in kq["nhom"]:
            self.assertGreaterEqual(n["gia_tri"], 0, f"{n['ten_hien_thi']}/{n['thang']} âm")
            for d in n["dong"]:
                self.assertGreaterEqual(d["sl"], 0)

    def test_so_phieu_dem_phan_biet_khong_dem_dong(self):
        """Một phiếu 2 vật tư = MỘT phiếu, hai mặt hàng. Đếm dòng sẽ ra 2 và
        biến báo cáo tháng thành thứ không đối chiếu được với sổ giấy."""
        n = self._theo_khoa_thang()[("Khoa Hồi sức", "2026-06")]
        self.assertEqual(n["so_phieu"], 1)
        self.assertEqual(n["so_mat_hang"], 2)
        for d in n["dong"]:
            self.assertEqual(d["so_phieu"], 1)

    def test_khong_cong_so_luong_qua_hai_dvt(self):
        """4 hộp Găng + 5 chai Cồn KHÔNG được thành "9" ở bất cứ đâu: mỗi vật
        tư một dòng, giữ nguyên ĐVT của nó."""
        n = self._theo_khoa_thang()[("Khoa Hồi sức", "2026-06")]
        theo_dvt = {d["dvt"]: d["sl"] for d in n["dong"]}
        self.assertEqual(theo_dvt.get("Hộp"), 4)
        self.assertEqual(theo_dvt.get("Chai"), 5)
        self.assertNotIn(9, [d["sl"] for d in n["dong"]])
        # Và dòng tiêu đề nhóm KHÔNG mang khoá "sl" nào cả — chỗ duy nhất số
        # lượng có nghĩa là dòng vật tư.
        self.assertNotIn("sl", n)

    def test_chua_gan_khoa_tach_rieng_va_nam_cuoi(self):
        kq = self._chay()
        khoa_values = [n["khoa_phong"] for n in kq["nhom"]]
        self.assertIn(None, khoa_values, "nhóm Chưa gắn khoa phải có mặt, không bị giấu")
        self.assertIsNone(kq["nhom"][-1]["khoa_phong"], "Chưa gắn khoa phải ở cuối bảng")

    def test_nhan_thang_va_thu_tu_sap_xep(self):
        kq = self._chay()
        m = self._theo_khoa_thang(kq)
        self.assertEqual(m[("Khoa Hồi sức", "2026-06")]["nhan_thang"], "06/2026")

        # Khoa trước, tháng TĂNG DẦN trong cùng khoa — các tháng của một khoa
        # phải nằm liền nhau để đọc được xu hướng tiêu thụ.
        co_ten = [(n["ten_hien_thi"], n["thang"]) for n in kq["nhom"] if n["khoa_phong"]]
        self.assertEqual(co_ten, sorted(co_ten))
        hs = [t for ten, t in co_ten if ten == "Khoa Hồi sức"]
        self.assertEqual(hs, ["2026-06", "2026-08"])

    def test_loc_theo_mot_khoa_phong(self):
        m = self._theo_khoa_thang(self._chay(khoa_phong=self.khoa_xn.name))
        self.assertEqual(set(m), {("Khoa Xét nghiệm", "2026-08")})

    def test_phan_trang_cat_theo_cap_khoa_thang(self):
        """`tong` là số CẶP (khoa, tháng) có phát sinh — 4 trong bộ số này —
        không phải số khoa (3) và cũng không phải số dòng vật tư (5)."""
        kq = self._chay(limit=2, start=0)
        self.assertEqual(kq["tong"], 4)
        self.assertEqual(len(kq["nhom"]), 2)
        # Tổng vẫn là tổng TOÀN KỲ, tính trước khi cắt trang.
        self.assertAlmostEqual(kq["tong_gia_tri"], 545000, places=2)

    def test_khach_khac_khong_thay_du_lieu_bach_mai(self):
        frappe.set_user(PXN_USER)
        try:
            kq = kho_api.kho_bao_cao_cap_phat_thang(self.TU_NGAY, self.DEN_NGAY)
        finally:
            frappe.set_user("Administrator")
        self.assertEqual(kq["nhom"], [])
        self.assertAlmostEqual(kq["tong_gia_tri"], 0, places=2)

    # --- Excel: cùng con số với màn hình ------------------------------------

    def test_excel_be_phang_dung_bang_so_lieu_man_hinh(self):
        from miyano_portal.kho import reports

        kho = self.kho["kho_bm"]
        grouped = reports.cap_phat_thang_rows(kho, self.TU_NGAY, self.DEN_NGAY)
        flat = reports.cap_phat_thang_flat_rows(kho, self.TU_NGAY, self.DEN_NGAY)

        # Số dòng phẳng = tổng số dòng vật tư của mọi nhóm; tổng tiền khớp.
        self.assertTrue(flat)
        self.assertEqual(len(flat), sum(len(n["dong"]) for n in grouped["nhom"]))
        self.assertAlmostEqual(
            sum(r["gia_tri"] for r in flat), grouped["tong_gia_tri"], places=2
        )
        # Mỗi dòng phẳng mang đủ khoá của bộ cột xuất Excel — thiếu một khoá
        # thì build_xlsx im lặng để ô trống.
        for _label, field in reports.CAP_PHAT_THANG_COLUMNS:
            for r in flat:
                self.assertIn(field, r)

    # --- Desk (mọi khách hàng) ---------------------------------------------

    def test_desk_report_khong_ro_ri_giua_khach_hang(self):
        from miyano_portal.kho import desk_reports

        rows_bm = desk_reports.cap_phat_thang_theo_khoa_rows(
            customer="Bệnh viện Bạch Mai", tu_ngay=self.TU_NGAY, den_ngay=self.DEN_NGAY,
        )
        rows_pxn = desk_reports.cap_phat_thang_theo_khoa_rows(
            customer="PXN ABC", tu_ngay=self.TU_NGAY, den_ngay=self.DEN_NGAY,
        )
        self.assertTrue(rows_bm)
        self.assertEqual(rows_pxn, [])
        for r in rows_bm:
            self.assertEqual(r["customer"], "Bệnh viện Bạch Mai")

        m = {(r["khoa_phong"], r["thang"]): r for r in rows_bm}
        self.assertAlmostEqual(m[("Khoa Hồi sức", "2026-06")]["gia_tri"], 269000, places=2)
        self.assertEqual(m[("Khoa Hồi sức", "2026-06")]["so_phieu"], 1)
        self.assertEqual(m[("Khoa Hồi sức", "2026-06")]["so_mat_hang"], 2)

    def test_desk_report_co_y_khong_co_cot_so_luong(self):
        """Chốt của một quyết định, không phải của một phép tính: ở mức
        (khoa, tháng) không được có cột số lượng — nó cộng hộp với chai. Nếu
        có ai thêm vào sau này, test này đỏ và buộc đọc lại lý do."""
        from miyano_portal.kho import desk_reports
        from miyano_portal.miyano_portal.report.cấp_phát_theo_tháng_và_khoa_phòng import (
            cấp_phát_theo_tháng_và_khoa_phòng as rp,
        )

        rows = desk_reports.cap_phat_thang_theo_khoa_rows(
            customer="Bệnh viện Bạch Mai", tu_ngay=self.TU_NGAY, den_ngay=self.DEN_NGAY,
        )
        self.assertTrue(rows)
        self.assertNotIn("sl", rows[0])
        self.assertNotIn("sl", [c["fieldname"] for c in rp.COLUMNS])

    def test_desk_report_execute_chay_duoc_va_mac_dinh_12_thang(self):
        """Chạy qua ĐÚNG `execute()` (đường Desk thật), và khoảng ngày mặc
        định phải phủ 12 tháng gần nhất — không phải tháng hiện tại, vì một
        báo cáo "theo từng tháng" mặc định một tháng thì vô dụng."""
        from miyano_portal.miyano_portal.report.cấp_phát_theo_tháng_và_khoa_phòng import (
            cấp_phát_theo_tháng_và_khoa_phòng as rp,
        )

        # KHÔNG truyền tu_ngay/den_ngay — đây chính là điều cần test.
        columns, data = rp.execute({"customer": "Bệnh viện Bạch Mai"})
        self.assertTrue(columns)

        thang_thay_duoc = {r["thang"] for r in data}
        thang_cu = min(
            frappe.utils.getdate(x) for x in ("2026-06-10", "2026-08-05")
        ).strftime("%Y-%m")
        hom_nay = frappe.utils.getdate(frappe.utils.today())
        # Fixture đặt dữ liệu ở tháng 06/2026; chỉ khẳng định khi "hôm nay"
        # còn nằm trong 12 tháng kể từ đó — nếu suite chạy sau 06/2027 thì dữ
        # liệu cố định ra ngoài kỳ mặc định một cách hợp lệ, và một test tự
        # đỏ theo lịch thì tệ hơn là không có test (bài học "date rot").
        trong_tam = frappe.utils.date_diff(hom_nay, frappe.utils.getdate("2026-06-10")) < 330
        if trong_tam:
            self.assertIn(
                thang_cu, thang_thay_duoc,
                "khoảng ngày mặc định phải phủ 12 tháng — nếu nó là THÁNG HIỆN "
                "TẠI như báo cáo N-X-T thì tháng 06 biến mất và báo cáo "
                '"theo từng tháng" chỉ còn đúng một tháng',
            )
