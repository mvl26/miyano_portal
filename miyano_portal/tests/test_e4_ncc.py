"""E4 phần A: NCC của kho, phiếu "Mua ngoài (NCC khác)", tồn đầu kỳ một lần,
cảnh báo xuất lô hết hạn (thu hẹp), cảnh báo trùng tên vật tư.

Bám theo 40_TestCases.md TC-E4-01, 02, 03, 04, 05, 06, 10 (TC-E4-07/08/09 là
Phần B — nhật ký/NXT theo đợt/nhóm hạn — không thuộc phạm vi file này).

Khuôn: gọi thẳng hàm trong miyano_portal.api.kho dưới frappe.set_user(...),
đúng cổng duy nhất mà portal dùng — giống test_kho_phieu_api.py.
"""

import io
from datetime import date

import frappe
from frappe.tests.utils import FrappeTestCase
from openpyxl import Workbook

from miyano_portal.api import kho as kho_api
from miyano_portal.kho import import_ton_dau, ledger
from miyano_portal.setup.seed_kho_demo import seed_kho_demo

BM_USER = "bvbm@demo.miyano"
PXN_USER = "pxnabc@demo.miyano"


class _E4Fixture(FrappeTestCase):
    def setUp(self):
        self.kho = seed_kho_demo()
        frappe.db.delete("Customer Supplier", {"kho": ["in", [self.kho["kho_bm"], self.kho["kho_pxn"]]]})
        frappe.db.delete("Customer Stock Ledger Entry", {"kho": ["in", [self.kho["kho_bm"], self.kho["kho_pxn"]]]})
        frappe.db.delete("Customer Stock Lot Balance", {"kho": ["in", [self.kho["kho_bm"], self.kho["kho_pxn"]]]})
        frappe.db.delete("Customer Stock Receipt", {"kho": ["in", [self.kho["kho_bm"], self.kho["kho_pxn"]]]})

    def tearDown(self):
        frappe.set_user("Administrator")

    def _nhap(self, kho=None, vat_tu=None, so_lo="LO-A", so_luong=100, don_gia=50000,
              han=None, loai_nhap="Nhập khác", submit=True, **extra):
        doc = frappe.get_doc({
            "doctype": "Customer Stock Receipt",
            "kho": kho or self.kho["kho_bm"],
            "ngay": "2026-02-01",
            "loai_nhap": loai_nhap,
            "nguoi_giao": "Trần Văn Giao",
            "items": [{
                "vat_tu": vat_tu or self.kho["vt_bm"],
                "so_lo": so_lo, "han_su_dung": han,
                "so_luong": so_luong, "don_gia": don_gia,
            }],
            **extra,
        })
        doc.insert(ignore_permissions=True)
        if submit:
            doc.submit()
        return doc


# ---------------------------------------------------------------------------
# US-E4.1 — Danh mục NCC của kho: trùng tuyệt đối chặn, gần giống gợi ý,
# cách ly theo kho, không xoá được khi đã dùng trên phiếu.
# ---------------------------------------------------------------------------


class TestNccSave(_E4Fixture):
    def test_create_new_ncc(self):
        frappe.set_user(BM_USER)
        out = kho_api.kho_ncc_save({"ten_ncc": "Công ty TNHH ABC", "mst": "0101234567"})
        self.assertTrue(out["name"].startswith("NCC-"))
        self.assertEqual(out["mst"], "0101234567")
        self.assertEqual(out["goi_y_trung"], [])
        self.assertEqual(frappe.db.get_value("Customer Supplier", out["name"], "kho"),
                          self.kho["kho_bm"])

    def test_exact_duplicate_name_in_same_kho_blocked(self):
        """TC-E4-01 (Â): trùng tuyệt đối trong kho -> chặn."""
        frappe.set_user(BM_USER)
        kho_api.kho_ncc_save({"ten_ncc": "Công ty ABC"})
        with self.assertRaises(frappe.ValidationError) as ctx:
            kho_api.kho_ncc_save({"ten_ncc": "Công ty ABC"})
        self.assertIn("trùng", str(ctx.exception))

    def test_exact_duplicate_ignores_diacritics_and_case(self):
        """"trùng tuyệt đối" so không dấu — gõ lệch dấu/hoa-thường vẫn coi là
        cùng một tên, không phải "gần giống"."""
        frappe.set_user(BM_USER)
        kho_api.kho_ncc_save({"ten_ncc": "Cty ABC"})
        with self.assertRaises(frappe.ValidationError):
            kho_api.kho_ncc_save({"ten_ncc": "cty abc"})

    def test_exact_duplicate_ignores_whitespace_and_punctuation(self):
        """M-1 (review): "Cty  ABC" (hai dấu cách) và "Cty ABC." (dấu chấm
        cuối) đều là cùng một tên với "Cty ABC" — không được lọt thành hai
        NCC khác nhau chỉ vì lệch khoảng trắng/dấu câu."""
        frappe.set_user(BM_USER)
        kho_api.kho_ncc_save({"ten_ncc": "Cty ABC"})
        with self.assertRaises(frappe.ValidationError):
            kho_api.kho_ncc_save({"ten_ncc": "Cty  ABC"})
        with self.assertRaises(frappe.ValidationError):
            kho_api.kho_ncc_save({"ten_ncc": "Cty ABC."})

    def test_near_duplicate_name_suggests_instead_of_blocking(self):
        """TC-E4-01 (B): gần giống >= 85% (không dấu) -> KHÔNG chặn, trả
        goi_y_trung để client gợi ý chọn NCC có sẵn (NL-7.3)."""
        frappe.set_user(BM_USER)
        first = kho_api.kho_ncc_save({"ten_ncc": "Công ty TNHH Thiết bị y tế ABC"})
        out = kho_api.kho_ncc_save({"ten_ncc": "Cong ty TNHH Thiet bi y te ABD"})
        self.assertNotEqual(out["name"], first["name"])
        self.assertTrue(out["goi_y_trung"])
        self.assertIn(first["name"], out["goi_y_trung"][0])

    def test_different_customers_can_share_same_supplier_name(self):
        """Unique theo (kho, ten_ncc), KHÔNG unique toàn cục."""
        frappe.set_user(BM_USER)
        bm = kho_api.kho_ncc_save({"ten_ncc": "Công ty Dùng Chung"})
        frappe.set_user(PXN_USER)
        pxn = kho_api.kho_ncc_save({"ten_ncc": "Công ty Dùng Chung"})
        self.assertNotEqual(bm["name"], pxn["name"])

    def test_mst_must_be_10_or_13_digits(self):
        frappe.set_user(BM_USER)
        with self.assertRaises(frappe.ValidationError) as ctx:
            kho_api.kho_ncc_save({"ten_ncc": "NCC Sai MST", "mst": "12345"})
        self.assertIn("10 hoặc 13", str(ctx.exception))

    def test_update_existing_ncc(self):
        frappe.set_user(BM_USER)
        created = kho_api.kho_ncc_save({"ten_ncc": "NCC Sửa Được"})
        out = kho_api.kho_ncc_save({
            "name": created["name"], "ten_ncc": "NCC Sửa Được", "dien_thoai": "0900000000",
        })
        self.assertEqual(out["name"], created["name"])
        self.assertEqual(out["dien_thoai"], "0900000000")

    def test_cannot_save_other_customers_ncc(self):
        """Cách ly: `name` do client gửi khi sửa phải được kiểm sở hữu trước
        khi chạm doc — không endpoint nào nhận kho/customer từ client."""
        frappe.set_user(BM_USER)
        mine = kho_api.kho_ncc_save({"ten_ncc": "NCC Của BM"})
        frappe.set_user(PXN_USER)
        with self.assertRaises(frappe.PermissionError):
            kho_api.kho_ncc_save({"name": mine["name"], "ten_ncc": "Chiếm đoạt"})
        # Không bị sửa nửa chừng.
        self.assertEqual(
            frappe.db.get_value("Customer Supplier", mine["name"], "ten_ncc"), "NCC Của BM"
        )

    def test_used_on_receipt_cannot_be_deleted_only_deactivated(self):
        frappe.set_user(BM_USER)
        ncc = kho_api.kho_ncc_save({"ten_ncc": "NCC Đã Dùng"})
        self._nhap(loai_nhap="Mua ngoài (NCC khác)", ncc=ncc["name"], so_chung_tu_ncc="HD-01")

        # M-3 (review): frappe.LinkExistsError LÀ subclass của ValidationError
        # — assertRaises(ValidationError) trần vẫn pass y hệt nếu on_trash bị
        # xoá sạch và Frappe tự chặn bằng LinkExistsError của riêng nó (vì
        # `ncc` là Link field). Assert thêm đúng thông điệp CỦA on_trash để
        # chốt chặn bị gỡ thì test này thật sự đỏ.
        with self.assertRaises(frappe.ValidationError) as ctx:
            frappe.delete_doc("Customer Supplier", ncc["name"], ignore_permissions=True)
        self.assertIn("Hãy tắt", str(ctx.exception))
        self.assertTrue(frappe.db.exists("Customer Supplier", ncc["name"]))

        out = kho_api.kho_ncc_save({"name": ncc["name"], "ten_ncc": "NCC Đã Dùng", "active": 0})
        self.assertEqual(out["active"], 0)

    def test_inactive_ncc_not_selectable_on_new_receipt(self):
        """"NCC tắt không chọn được trên phiếu mới" — chốt chặn server-side,
        không chỉ lọc dropdown phía client."""
        frappe.set_user(BM_USER)
        ncc = kho_api.kho_ncc_save({"ten_ncc": "NCC Sẽ Tắt"})
        kho_api.kho_ncc_save({"name": ncc["name"], "ten_ncc": "NCC Sẽ Tắt", "active": 0})
        with self.assertRaises(frappe.ValidationError) as ctx:
            self._nhap(loai_nhap="Mua ngoài (NCC khác)", ncc=ncc["name"], so_chung_tu_ncc="HD-02")
        self.assertIn("ngừng hoạt động", str(ctx.exception))


class TestNccList(_E4Fixture):
    def test_isolation_customer_b_does_not_see_customer_a_supplier(self):
        """TC-E4-02 (Â): KH-B gọi kho_ncc_list không thấy NCC của KH-A."""
        frappe.set_user(BM_USER)
        kho_api.kho_ncc_save({"ten_ncc": "NCC Riêng Của BM"})
        frappe.set_user(PXN_USER)
        names = [r["ten_ncc"] for r in kho_api.kho_ncc_list()]
        self.assertNotIn("NCC Riêng Của BM", names)

    def test_list_only_own_kho(self):
        frappe.set_user(BM_USER)
        kho_api.kho_ncc_save({"ten_ncc": "NCC Của BM"})
        frappe.set_user(PXN_USER)
        kho_api.kho_ncc_save({"ten_ncc": "NCC Của PXN"})
        frappe.set_user(BM_USER)
        names = {r["ten_ncc"] for r in kho_api.kho_ncc_list()}
        self.assertEqual(names, {"NCC Của BM"})

    def test_inactive_excluded_unless_ca_inactive(self):
        frappe.set_user(BM_USER)
        ncc = kho_api.kho_ncc_save({"ten_ncc": "NCC Tắt"})
        kho_api.kho_ncc_save({"name": ncc["name"], "ten_ncc": "NCC Tắt", "active": 0})
        self.assertEqual(kho_api.kho_ncc_list(), [])
        rows = kho_api.kho_ncc_list(ca_inactive=1)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["active"], 0)

    def test_list_reports_receipt_count_and_value(self):
        frappe.set_user(BM_USER)
        ncc = kho_api.kho_ncc_save({"ten_ncc": "NCC Có Phiếu"})
        # `ngay` PHẢI nằm trong 90 ngày gần "hôm nay" thật (frappe.utils.today()
        # tại lúc chạy test) — gia_tri_90n lọc theo mốc động, không phải mốc
        # hardcode trong quá khứ như phần lớn fixture khác của file này.
        self._nhap(loai_nhap="Mua ngoài (NCC khác)", ncc=ncc["name"], so_chung_tu_ncc="HD-09",
                    so_luong=10, don_gia=1000, ngay=frappe.utils.today())
        rows = kho_api.kho_ncc_list()
        row = next(r for r in rows if r["name"] == ncc["name"])
        self.assertEqual(row["so_phieu"], 1)
        self.assertEqual(row["gia_tri_90n"], 10000)


# ---------------------------------------------------------------------------
# US-E4.2 — Phiếu nhập "Mua ngoài (NCC khác)": BR-N1 (bắt buộc NCC), BR-N2
# (chứng từ không bắt buộc, gắn cờ thiếu), BR-K19 (loại kiểm kê tăng mới),
# BR-K9 (Phiếu đảo vẫn không chọn tay được).
# ---------------------------------------------------------------------------


class TestPhieuMuaNgoai(_E4Fixture):
    def test_mua_ngoai_without_ncc_blocked_with_literal_message(self):
        """TC-E4-03 (Â): thiếu NCC -> chặn, thông điệp NGUYÊN VĂN NL-7.1."""
        frappe.set_user(BM_USER)
        with self.assertRaises(frappe.ValidationError) as ctx:
            self._nhap(loai_nhap="Mua ngoài (NCC khác)")
        self.assertEqual(
            "Chọn nhà cung cấp cho phiếu mua ngoài.", str(ctx.exception)
        )

    def test_mua_ngoai_missing_chung_tu_still_saves_and_posts_with_flag(self):
        """TC-E4-04 (C): bỏ trống so_chung_tu_ncc -> vẫn lưu/ghi sổ được,
        gắn thieu_chung_tu=1; kho_phieu_list lọc được theo cờ.

        I-4 (review): đi qua kho_phieu_nhap_save/kho_phieu_submit (đường lưu
        thật portal dùng), KHÔNG phải frappe.get_doc — để TC-E4-04 thật sự
        được phủ qua endpoint, không chỉ qua controller.
        """
        frappe.set_user(BM_USER)
        ncc = kho_api.kho_ncc_save({"ten_ncc": "NCC Thiếu Chứng Từ"})
        out = kho_api.kho_phieu_nhap_save({
            "ngay": frappe.utils.today(), "loai_nhap": "Mua ngoài (NCC khác)",
            "ncc": ncc["name"],
            "items": [{"vat_tu": self.kho["vt_bm"], "so_lo": "LO-TCT",
                       "so_luong": 5, "don_gia": 2000}],
        })
        out = kho_api.kho_phieu_submit("Customer Stock Receipt", out["name"])
        self.assertEqual(out["docstatus"], 1)
        self.assertEqual(out["thieu_chung_tu"], 1)

        rows_thieu = kho_api.kho_phieu_list("nhap", thieu_chung_tu=1)
        self.assertIn(out["name"], [r["name"] for r in rows_thieu])
        rows_du = kho_api.kho_phieu_list("nhap", thieu_chung_tu=0)
        self.assertNotIn(out["name"], [r["name"] for r in rows_du])

    def test_mua_ngoai_with_chung_tu_has_no_flag(self):
        frappe.set_user(BM_USER)
        ncc = kho_api.kho_ncc_save({"ten_ncc": "NCC Đủ Chứng Từ"})
        doc = self._nhap(
            loai_nhap="Mua ngoài (NCC khác)", ncc=ncc["name"], so_chung_tu_ncc="HD-2026-001"
        )
        self.assertEqual(doc.thieu_chung_tu, 0)

    def test_ngay_chung_tu_after_ngay_phieu_blocked(self):
        frappe.set_user(BM_USER)
        ncc = kho_api.kho_ncc_save({"ten_ncc": "NCC Ngày Sai"})
        with self.assertRaises(frappe.ValidationError):
            self._nhap(
                loai_nhap="Mua ngoài (NCC khác)", ncc=ncc["name"],
                so_chung_tu_ncc="HD-01", ngay_chung_tu="2026-02-15",
            )

    def test_dieu_chinh_kiem_ke_tang_is_selectable_and_increases_stock(self):
        """BR-K19: "Điều chỉnh kiểm kê (tăng)" là loại nhập riêng, hệ số +1
        giống "Nhập khác" — không dùng chung "Nhập khác" cho kiểm kê."""
        frappe.set_user(BM_USER)
        doc = self._nhap(loai_nhap="Điều chỉnh kiểm kê (tăng)", so_luong=15, don_gia=1000)
        self.assertEqual(doc.docstatus, 1)
        bal = ledger.get_lot_balance(self.kho["kho_bm"], self.kho["vt_bm"], "LO-A")
        self.assertEqual(bal["so_luong"], 15)

    def test_phieu_dao_still_not_selectable_by_hand(self):
        """BR-K9 (hồi quy): thêm hai loai_nhap mới KHÔNG được nới lỏng guard
        chặn tự chọn "Phiếu đảo"."""
        frappe.set_user(BM_USER)
        with self.assertRaises(frappe.ValidationError) as ctx:
            self._nhap(loai_nhap="Phiếu đảo")
        self.assertIn("Không thể tạo phiếu đảo bằng tay", str(ctx.exception))

    def test_endpoint_accepts_ncc_fields_and_persists_them(self):
        """Đường lưu thật (kho_phieu_nhap_save), không chỉ frappe.get_doc.

        I-4 (review): assert trên dict trả về của MỘT lần gọi không chứng
        minh được gì — dict đó là doc.as_dict() trong bộ nhớ, không đọc lại
        DB. Bài học E3 là "field chết ở lần lưu THỨ HAI" (kho_phieu_nhap_save
        dựng lại items từ payload mỗi lần lưu) — nên bài test phải LƯU-SỬA-LƯU
        rồi đọc lại bằng frappe.db.get_value(), không phải tin dict trả về.
        """
        frappe.set_user(BM_USER)
        ncc = kho_api.kho_ncc_save({"ten_ncc": "NCC Qua Endpoint"})
        ngay_phieu = frappe.utils.today()
        out = kho_api.kho_phieu_nhap_save({
            "ngay": ngay_phieu, "loai_nhap": "Mua ngoài (NCC khác)",
            "ncc": ncc["name"], "so_chung_tu_ncc": "HD-777",
            "ngay_chung_tu": frappe.utils.add_days(ngay_phieu, -1),
            "items": [{"vat_tu": self.kho["vt_bm"], "so_lo": "LO-EP", "so_luong": 5, "don_gia": 2000}],
        })
        # Lần lưu THỨ HAI trên CÙNG phiếu (sửa nháp) — đây chính là chỗ E3 vỡ.
        out = kho_api.kho_phieu_nhap_save({
            "name": out["name"],
            "ngay": ngay_phieu, "loai_nhap": "Mua ngoài (NCC khác)",
            "ncc": ncc["name"], "so_chung_tu_ncc": "HD-777",
            "ngay_chung_tu": frappe.utils.add_days(ngay_phieu, -1),
            "items": [{"vat_tu": self.kho["vt_bm"], "so_lo": "LO-EP", "so_luong": 5, "don_gia": 2000}],
        })

        row = frappe.db.get_value(
            "Customer Stock Receipt", out["name"],
            ["ncc", "so_chung_tu_ncc", "ngay_chung_tu", "thieu_chung_tu"], as_dict=True,
        )
        self.assertEqual(row.ncc, ncc["name"])
        self.assertEqual(row.so_chung_tu_ncc, "HD-777")
        self.assertEqual(row.ngay_chung_tu.isoformat(), frappe.utils.add_days(ngay_phieu, -1))
        self.assertEqual(row.thieu_chung_tu, 0)

    def test_endpoint_cannot_spoof_thieu_chung_tu_flag(self):
        """I-4 (review): client gửi thieu_chung_tu=0 kèm so_chung_tu_ncc rỗng
        — cờ hệ thống KHÔNG được nhận từ client, controller phải tự tính lại
        bất kể payload nói gì. Đọc lại từ DB, không tin response."""
        frappe.set_user(BM_USER)
        ncc = kho_api.kho_ncc_save({"ten_ncc": "NCC Giả Mạo Cờ"})
        out = kho_api.kho_phieu_nhap_save({
            "ngay": frappe.utils.today(), "loai_nhap": "Mua ngoài (NCC khác)",
            "ncc": ncc["name"], "so_chung_tu_ncc": "",
            "thieu_chung_tu": 0,  # cố giả mạo — phải bị bỏ qua
            "items": [{"vat_tu": self.kho["vt_bm"], "so_lo": "LO-GIA", "so_luong": 5, "don_gia": 2000}],
        })
        self.assertEqual(
            frappe.db.get_value("Customer Stock Receipt", out["name"], "thieu_chung_tu"), 1
        )

    def test_ncc_from_other_kho_rejected(self):
        frappe.set_user(PXN_USER)
        pxn_ncc = kho_api.kho_ncc_save({"ten_ncc": "NCC Của PXN"})
        frappe.set_user(BM_USER)
        with self.assertRaises(frappe.ValidationError) as ctx:
            self._nhap(loai_nhap="Mua ngoài (NCC khác)", ncc=pxn_ncc["name"], so_chung_tu_ncc="HD-X")
        self.assertIn("không thuộc kho", str(ctx.exception))


# ---------------------------------------------------------------------------
# US-E4.3 — Tồn đầu kỳ chỉ một lần (BR-K21): chặn từ bước UPLOAD/preview.
# ---------------------------------------------------------------------------


def _ton_dau_xlsx_bytes():
    wb = Workbook()
    ws = wb.active
    ws.append([label for label, _ in import_ton_dau.COLUMNS])
    ws.append(["VT-TD-01", "Vật tư tồn đầu", "Cái", "LO-TD", date(2027, 1, 1), 10, 5000, "", ""])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


class TestTonDauMotLan(_E4Fixture):
    def setUp(self):
        super().setUp()
        self._files = []

    def tearDown(self):
        for name in self._files:
            try:
                frappe.delete_doc("File", name, ignore_permissions=True, force=True)
            except Exception:
                pass
        super().tearDown()

    def _upload(self, user=BM_USER):
        frappe.set_user(user)
        f = frappe.get_doc({
            "doctype": "File", "file_name": "ton_dau.xlsx", "is_private": 1,
            "content": _ton_dau_xlsx_bytes(),
        })
        f.insert(ignore_permissions=True)
        self._files.append(f.name)
        return f

    def test_second_import_blocked_from_preview_step(self):
        """TC-E4-05 (Â): import tồn đầu kỳ lần 2 -> chặn ton_dau_da_nhap từ
        bước upload (preview), KHÔNG phải chỉ ở bước ghi (commit)."""
        frappe.set_user(BM_USER)
        f1 = self._upload()
        result = kho_api.kho_import_commit(f1.file_url)
        ngay = frappe.db.get_value("Customer Stock Receipt", result["receipt"], "ngay")

        f2 = self._upload()
        with self.assertRaises(frappe.ValidationError) as ctx:
            kho_api.kho_import_preview(f2.file_url)  # bước PREVIEW, chưa commit
        msg = str(ctx.exception)
        self.assertIn("Kho đã nhập tồn đầu kỳ ngày", msg)
        self.assertIn(frappe.utils.formatdate(ngay), msg)
        self.assertIn("Điều chỉnh kiểm kê", msg)

        # ...và commit (nếu vẫn được gọi trực tiếp, bỏ qua preview) cũng bị
        # chặn giống hệt, KHÔNG ghi thêm phiếu tồn đầu kỳ nào.
        so_phieu_truoc = frappe.db.count(
            "Customer Stock Receipt", {"kho": self.kho["kho_bm"], "loai_nhap": "Tồn đầu kỳ"}
        )
        with self.assertRaises(frappe.ValidationError):
            kho_api.kho_import_commit(f2.file_url)
        so_phieu_sau = frappe.db.count(
            "Customer Stock Receipt", {"kho": self.kho["kho_bm"], "loai_nhap": "Tồn đầu kỳ"}
        )
        self.assertEqual(so_phieu_truoc, so_phieu_sau)

    def test_manual_second_ton_dau_via_endpoint_blocked(self):
        """I-2 (review): BR-K21 KHÔNG chỉ chặn được ở bước upload Excel — thủ
        kho vẫn có thể mở màn Phiếu nhập, tự chọn loai_nhap="Tồn đầu kỳ" từ
        dropdown và gõ tay, một đường hoàn toàn không đi qua parse_workbook.
        Đi qua kho_phieu_nhap_save (endpoint thật), không phải get_doc."""
        frappe.set_user(BM_USER)
        f1 = self._upload()
        result = kho_api.kho_import_commit(f1.file_url)
        ngay = frappe.db.get_value("Customer Stock Receipt", result["receipt"], "ngay")

        # Chốt chặn nằm trong validate() của controller, nên chạy ngay từ bước
        # LƯU NHÁP (kho_phieu_nhap_save gọi insert()) — còn sớm hơn cả bước
        # ghi sổ. Đúng "chặn ngay từ bước upload" nhưng cho đường tay.
        with self.assertRaises(frappe.ValidationError) as ctx:
            kho_api.kho_phieu_nhap_save({
                "ngay": frappe.utils.today(), "loai_nhap": "Tồn đầu kỳ",
                "items": [{"vat_tu": self.kho["vt_bm"], "so_lo": "LO-TAY",
                           "so_luong": 5, "don_gia": 1000}],
            })
        msg = str(ctx.exception)
        self.assertIn("Kho đã nhập tồn đầu kỳ ngày", msg)
        self.assertIn(frappe.utils.formatdate(ngay), msg)
        self.assertEqual(
            frappe.db.count(
                "Customer Stock Receipt",
                {"kho": self.kho["kho_bm"], "loai_nhap": "Tồn đầu kỳ"},
            ),
            1,
            "không được tạo thêm phiếu tồn đầu kỳ nào, kể cả ở trạng thái nháp",
        )

    def test_cancel_ton_dau_then_reimport_allowed(self):
        """Huỷ phiếu tồn đầu kỳ là ĐƯỜNG PHỤC HỒI HỢP LỆ DUY NHẤT khi import
        sai — phải khẳng định bằng test, không để ngầm định."""
        frappe.set_user(BM_USER)
        result = kho_api.kho_import_commit(self._upload().file_url)
        kho_api.kho_phieu_cancel("Customer Stock Receipt", result["receipt"])

        f2 = self._upload()
        preview = kho_api.kho_import_preview(f2.file_url)
        self.assertEqual(preview["error_count"], 0)
        result2 = kho_api.kho_import_commit(f2.file_url)
        self.assertTrue(frappe.db.exists("Customer Stock Receipt", result2["receipt"]))

    def test_draft_ton_dau_kho_does_not_block_reimport(self):
        """Chỉ phiếu ĐÃ GHI SỔ (docstatus=1) mới tính là "đã commit" — một
        phiếu tồn đầu kỳ còn NHÁP không chặn import lại."""
        frappe.set_user(BM_USER)
        frappe.get_doc({
            "doctype": "Customer Stock Receipt",
            "kho": self.kho["kho_bm"], "ngay": "2026-01-01", "loai_nhap": "Tồn đầu kỳ",
            "items": [{"vat_tu": self.kho["vt_bm"], "so_lo": "LO-NHAP", "han_su_dung": None,
                       "so_luong": 1, "don_gia": 1000}],
        }).insert(ignore_permissions=True)  # KHÔNG submit

        f = self._upload()
        result = kho_api.kho_import_preview(f.file_url)
        self.assertEqual(result["error_count"], 0)

    def test_other_customers_kho_not_blocked(self):
        """Cách ly: kho A đã nhập tồn đầu không chặn kho B."""
        frappe.set_user(BM_USER)
        kho_api.kho_import_commit(self._upload().file_url)

        frappe.set_user(PXN_USER)
        result = kho_api.kho_import_preview(self._upload(user=PXN_USER).file_url)
        self.assertEqual(result["error_count"], 0)


# ---------------------------------------------------------------------------
# US-E4.4 — Cảnh báo xuất lô hết hạn: chỉ hỏi ở "Xuất sử dụng".
# ---------------------------------------------------------------------------


class TestCanhBaoXuatHetHan(_E4Fixture):
    def setUp(self):
        super().setUp()
        # I-1 (review): `ngay` của phiếu PHẢI cùng mốc "hôm nay" với
        # han_da_het — _chan_lo_het_han_chua_xac_nhan so hạn dùng với NGÀY
        # PHIẾU (self.ngay), không phải frappe.utils.today() tại lúc chạy
        # validate. Trộn một `han` tương đối với một `ngay` hardcode
        # ("2026-03-01") làm ý nghĩa test đảo chiều tuỳ ngày chạy — xem
        # test_lot_date_basis_is_ngay_phieu_not_system_today bên dưới cho hai
        # ca cụ thể mà lỗi đó gây ra.
        self.ngay_phieu = frappe.utils.today()
        self.han_da_het = frappe.utils.add_days(self.ngay_phieu, -10)
        self._nhap(so_lo="LO-HH", so_luong=20, don_gia=10000, han=self.han_da_het)

    def _xuat(self, loai_xuat, xac_nhan=0, so_luong=5, so_lo="LO-HH", ngay=None):
        doc = frappe.get_doc({
            "doctype": "Customer Stock Issue",
            "kho": self.kho["kho_bm"], "ngay": ngay or self.ngay_phieu, "loai_xuat": loai_xuat,
            "noi_nhan": "Khoa test", "nguoi_nhan": "NV test",
            "items": [{"vat_tu": self.kho["vt_bm"], "so_lo": so_lo, "so_luong": so_luong,
                       "xac_nhan_het_han": xac_nhan}],
        })
        doc.insert(ignore_permissions=True)
        return doc

    def test_xuat_su_dung_expired_lot_without_confirm_blocked(self):
        """TC-E4-06 (Â): "Xuất sử dụng" lô quá hạn không tick -> chặn."""
        frappe.set_user(BM_USER)
        doc = self._xuat("Xuất sử dụng", xac_nhan=0)
        with self.assertRaises(frappe.ValidationError) as ctx:
            doc.submit()
        self.assertIn("hết hạn", str(ctx.exception))

    def test_xuat_su_dung_expired_lot_with_confirm_allowed(self):
        """TC-E4-06 (C): tick xác nhận -> OK."""
        frappe.set_user(BM_USER)
        doc = self._xuat("Xuất sử dụng", xac_nhan=1)
        doc.submit()
        self.assertEqual(doc.docstatus, 1)

    def test_xuat_huy_het_han_does_not_ask(self):
        """TC-E4-06 (C): loại "Xuất huỷ - hết hạn" KHÔNG hỏi, dù không tick."""
        frappe.set_user(BM_USER)
        doc = self._xuat("Xuất huỷ - hết hạn", xac_nhan=0)
        doc.submit()
        self.assertEqual(doc.docstatus, 1)

    def test_other_loai_xuat_does_not_ask(self):
        """Các loại xuất khác (không phải "Xuất sử dụng") cũng không hỏi."""
        frappe.set_user(BM_USER)
        for loai in ("Xuất trả lại", "Điều chỉnh kiểm kê"):
            with self.subTest(loai=loai):
                doc = self._xuat(loai, xac_nhan=0, so_luong=1)
                doc.submit()
                self.assertEqual(doc.docstatus, 1)

    def test_backdated_issue_not_falsely_blocked(self):
        """I-1: "chặn nhầm" — lô hết hạn HÔM NAY nhưng phiếu ghi ngày quá khứ
        mà tại đó lô vẫn còn hạn -> không được đòi xác nhận."""
        frappe.set_user(BM_USER)
        han = frappe.utils.add_days(self.ngay_phieu, -10)
        ngay_bu = frappe.utils.add_days(self.ngay_phieu, -40)
        self._nhap(so_lo="LO-BU", so_luong=10, don_gia=5000, han=han)
        doc = self._xuat("Xuất sử dụng", xac_nhan=0, so_lo="LO-BU", ngay=ngay_bu)
        doc.submit()
        self.assertEqual(doc.docstatus, 1)

    def test_future_dated_issue_still_blocked(self):
        """I-1: "bỏ lọt" — lô CÒN hạn hôm nay nhưng phiếu ghi ngày tương lai
        mà tại đó lô đã hết hạn -> vẫn phải đòi xác nhận."""
        frappe.set_user(BM_USER)
        han = frappe.utils.add_days(self.ngay_phieu, 5)
        ngay_tuong_lai = frappe.utils.add_days(self.ngay_phieu, 20)
        self._nhap(so_lo="LO-TL", so_luong=10, don_gia=5000, han=han)
        doc = self._xuat("Xuất sử dụng", xac_nhan=0, so_lo="LO-TL", ngay=ngay_tuong_lai)
        with self.assertRaises(frappe.ValidationError) as ctx:
            doc.submit()
        self.assertIn("hết hạn", str(ctx.exception))


# ---------------------------------------------------------------------------
# US-E4.5 — Cảnh báo trùng tên vật tư >= 85% (không dấu): mềm, không chặn.
# ---------------------------------------------------------------------------


class TestCanhBaoTrungTenVatTu(_E4Fixture):
    def test_similar_name_warns_but_still_creates(self):
        """TC-E4-10 (B): tên giống >= 85% -> cảnh báo mềm, vẫn tạo được."""
        frappe.set_user(BM_USER)
        out1 = kho_api.kho_vat_tu_tao({
            "ma_vat_tu": "VT-TRUNG-01", "ten_vat_tu": "Găng tay y tế size L", "dvt": "Hộp",
        })
        out2 = kho_api.kho_vat_tu_tao({
            "ma_vat_tu": "VT-TRUNG-02", "ten_vat_tu": "Gang tay y te size L", "dvt": "Hộp",
        })
        self.assertNotEqual(out1["name"], out2["name"])
        self.assertTrue(frappe.db.exists("Customer Warehouse Item", out2["name"]))
        self.assertIn(out1["name"], out2["canh_bao_trung"][0])

    def test_dissimilar_name_no_warning(self):
        frappe.set_user(BM_USER)
        kho_api.kho_vat_tu_tao({
            "ma_vat_tu": "VT-KHAC-01", "ten_vat_tu": "Bơm tiêm 5ml", "dvt": "Cái",
        })
        out = kho_api.kho_vat_tu_tao({
            "ma_vat_tu": "VT-KHAC-02", "ten_vat_tu": "Băng gạc y tế", "dvt": "Cuộn",
        })
        self.assertEqual(out["canh_bao_trung"], [])
