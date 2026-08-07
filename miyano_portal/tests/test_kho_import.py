"""Import danh mục + tồn đầu kỳ có preview — tests/test_kho_import.py.

TDD: mỗi test dưới đây được viết để canh một guard cụ thể trong
miyano_portal/kho/import_ton_dau.py và miyano_portal/api/kho.py, và đã được
xác nhận THẤT BẠI khi guard tương ứng bị gỡ (xem p2-import-report.md).
"""

import io
from datetime import date

import frappe
from frappe.tests.utils import FrappeTestCase
from openpyxl import Workbook

from miyano_portal.api import kho as kho_api
from miyano_portal.kho import import_ton_dau
from miyano_portal.setup.seed_kho_demo import seed_kho_demo

BM_USER = "bvbm@demo.miyano"
PXN_USER = "pxnabc@demo.miyano"

HEADERS = [label for label, _ in import_ton_dau.COLUMNS]

# Vật tư đã khớp Item.item_code của Miyano nhưng CHƯA có trong kho BM (khác
# với MYN-GLOVE-M — cái đó seed_kho_demo() đã tạo sẵn cho kho BM, nên dùng nó
# sẽ rơi vào nhóm "existing_in_kho" chứ không phải "matched_miyano").
GOOD_ROW_MIYANO_NEW = [
    "MYN-SYR-10", "Bơm tiêm 10ml", "Cái", "LO-TD-01",
    date(2027, 6, 30), 50, 4500, "Hộp 100 cái", "",
]
GOOD_ROW_PRIVATE = [
    "BM-RIENG-01", "Băng ép tự mua", "Cuộn", "LO-TD-02",
    date(2027, 1, 1), 20, 8000, "", "",
]
GOOD_ROW_EXISTING = [
    "MYN-GLOVE-M", "Găng tay y tế size M", "Hộp", "LO-TD-03",
    date(2027, 3, 1), 10, 45000, "", "",
]


def _xlsx_bytes(rows, headers=None):
    wb = Workbook()
    ws = wb.active
    ws.append(headers if headers is not None else HEADERS)
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# Mã vật tư do seed_kho_demo() tạo sẵn cho kho BM — GIỮ LẠI khi dọn dẹp giữa
# các test method (FrappeTestCase chỉ rollback ở cuối class, không phải sau
# mỗi test), mọi mã khác (do chính các test trong file này tạo ra) bị xoá.
_SEED_CODES_BM = {"MYN-GLOVE-M", "BM-GAC-01"}


class _ImportTestBase(FrappeTestCase):
    def setUp(self):
        self.kho = seed_kho_demo()
        self._created_files = []
        # Dọn sạch dữ liệu giao dịch còn sót lại từ test method trước trong
        # CÙNG lớp — cùng khuôn mẫu setUp của test_kho_receipt.py/test_kho_issue.py,
        # mở rộng thêm Receipt và Customer Warehouse Item vì các test ở đây so
        # sánh CHÍNH XÁC số lượng và sự tồn tại của từng mã, không chỉ tồn kho.
        frappe.db.delete("Customer Stock Receipt", {"kho": self.kho["kho_bm"]})
        frappe.db.delete("Customer Stock Ledger Entry", {"kho": self.kho["kho_bm"]})
        frappe.db.delete("Customer Stock Lot Balance", {"kho": self.kho["kho_bm"]})
        frappe.db.delete("Customer Warehouse Item", {
            "kho": self.kho["kho_bm"], "ma_vat_tu": ["not in", list(_SEED_CODES_BM)],
        })

    def tearDown(self):
        frappe.set_user("Administrator")
        for name in self._created_files:
            try:
                frappe.delete_doc("File", name, ignore_permissions=True, force=True)
            except Exception:
                pass

    def _upload(self, content: bytes, filename="ton_dau.xlsx", user=BM_USER):
        frappe.set_user(user)
        file_doc = frappe.get_doc({
            "doctype": "File",
            "file_name": filename,
            "is_private": 1,
            "content": content,
        })
        file_doc.insert(ignore_permissions=True)
        self._created_files.append(file_doc.name)
        return file_doc

    def _counts(self, kho):
        receipts = frappe.get_all("Customer Stock Receipt", filters={"kho": kho}, pluck="name")
        item_rows = (
            frappe.db.count("Customer Stock Receipt Item", {"parent": ["in", receipts]})
            if receipts else 0
        )
        return (
            frappe.db.count("Customer Warehouse Item", {"kho": kho}),
            len(receipts),
            item_rows,
            frappe.db.count("Customer Stock Ledger Entry", {"kho": kho}),
            frappe.db.count("Customer Stock Lot Balance", {"kho": kho}),
        )


class TestKhoImportPreview(_ImportTestBase):
    def test_preview_writes_nothing_and_classifies_correctly(self):
        content = _xlsx_bytes([GOOD_ROW_MIYANO_NEW, GOOD_ROW_PRIVATE, GOOD_ROW_EXISTING])
        f = self._upload(content)
        before = self._counts(self.kho["kho_bm"])

        frappe.set_user(BM_USER)
        result = kho_api.kho_import_preview(f.file_url)

        after = self._counts(self.kho["kho_bm"])
        self.assertEqual(before, after, "preview không được ghi gì vào database")

        self.assertEqual(result["total"], 3)
        self.assertEqual(result["ok_count"], 3)
        self.assertEqual(result["error_count"], 0)
        self.assertEqual(result["summary"], {
            "matched_miyano": 1, "private_new": 1, "existing_in_kho": 1,
        })

    def test_miyano_code_sets_item_code_row(self):
        content = _xlsx_bytes([GOOD_ROW_MIYANO_NEW])
        f = self._upload(content)
        frappe.set_user(BM_USER)
        result = kho_api.kho_import_preview(f.file_url)
        row = result["rows_ok"][0]
        self.assertEqual(row["match_type"], "miyano")
        self.assertEqual(row["item_code"], "MYN-SYR-10")

    def test_private_code_leaves_item_code_blank(self):
        content = _xlsx_bytes([GOOD_ROW_PRIVATE])
        f = self._upload(content)
        frappe.set_user(BM_USER)
        result = kho_api.kho_import_preview(f.file_url)
        row = result["rows_ok"][0]
        self.assertEqual(row["match_type"], "private")
        self.assertEqual(row["item_code"], "")

    def test_each_bad_row_reports_vietnamese_reason_with_line_number(self):
        rows = [
            # dòng 2: hạn sử dụng không hợp lệ
            ["BM-BAD-01", "Vật tư lỗi ngày", "Cái", "LO-1", "khong-phai-ngay", 10, 1000, "", ""],
            # dòng 3: số lượng không phải số
            ["BM-BAD-02", "Vật tư lỗi số lượng", "Cái", "LO-2", date(2027, 1, 1), "abc", 1000, "", ""],
            # dòng 4: đơn giá âm
            ["BM-BAD-03", "Vật tư lỗi đơn giá", "Cái", "LO-3", date(2027, 1, 1), 10, -500, "", ""],
            # dòng 5: thiếu tên vật tư (ô bắt buộc)
            ["BM-BAD-04", "", "Cái", "LO-4", date(2027, 1, 1), 10, 1000, "", ""],
        ]
        content = _xlsx_bytes(rows)
        f = self._upload(content)
        frappe.set_user(BM_USER)
        result = kho_api.kho_import_preview(f.file_url)

        self.assertEqual(result["error_count"], 4)
        self.assertEqual(result["ok_count"], 0)
        by_line = {r["line"]: r["errors"] for r in result["rows_error"]}
        self.assertEqual(set(by_line), {2, 3, 4, 5})
        self.assertTrue(any("Hạn sử dụng không hợp lệ" in e for e in by_line[2]))
        self.assertTrue(any("Số lượng không hợp lệ" in e for e in by_line[3]))
        self.assertTrue(any("Đơn giá không được âm" in e for e in by_line[4]))
        self.assertTrue(any("Thiếu Tên vật tư" in e for e in by_line[5]))
        for errs in by_line.values():
            for e in errs:
                self.assertNotIn("Traceback", e)

    def test_customer_without_warehouse_gets_specific_message(self):
        """Vietnamese "chưa được mở kho" for all three endpoints, mirroring
        the pattern already established in test_kho_api.py."""
        sp = "test_import_no_warehouse_sp"
        frappe.db.savepoint(sp)
        try:
            frappe.db.set_value("Customer Warehouse", self.kho["kho_pxn"], "active", 0)
            frappe.set_user(PXN_USER)
            for label, call in [
                ("template", lambda: kho_api.kho_import_template()),
                ("preview", lambda: kho_api.kho_import_preview("irrelevant")),
                ("commit", lambda: kho_api.kho_import_commit("irrelevant")),
            ]:
                with self.assertRaises(frappe.PermissionError, msg=label) as cm:
                    call()
                self.assertIn("chưa được mở kho", str(cm.exception), msg=label)
        finally:
            frappe.db.rollback(save_point=sp)
            frappe.clear_document_cache("Customer Warehouse", self.kho["kho_pxn"])

    def test_bogus_file_url_gives_vietnamese_message_not_doctype_name(self):
        """Một file_url không tồn tại (tệp đã bị xoá, tab cũ gửi lại) không
        được để lộ DoesNotExistError tiếng Anh nêu tên doctype "File"."""
        frappe.set_user(BM_USER)
        for label, call in [
            ("preview", lambda: kho_api.kho_import_preview("/private/files/khong-ton-tai.xlsx")),
            ("commit", lambda: kho_api.kho_import_commit("/private/files/khong-ton-tai.xlsx")),
        ]:
            with self.assertRaises(frappe.ValidationError, msg=label) as cm:
                call()
            msg = str(cm.exception)
            self.assertNotIn("File", msg, msg=label)
            self.assertNotIn("DoesNotExistError", msg, msg=label)
            self.assertNotIn("Traceback", msg, msg=label)

    def test_template_download_reimports_cleanly(self):
        frappe.set_user(BM_USER)
        kho_api.kho_import_template()
        content = frappe.local.response.filecontent
        self.assertEqual(frappe.local.response.type, "download")
        frappe.local.response.clear()

        f = self._upload(content, filename="mau.xlsx")
        frappe.set_user(BM_USER)
        result = kho_api.kho_import_preview(f.file_url)
        self.assertEqual(result["error_count"], 0)
        self.assertEqual(result["ok_count"], 1)
        self.assertEqual(result["rows_ok"][0]["match_type"], "private")


class TestKhoImportCommit(_ImportTestBase):
    def test_one_bad_row_writes_nothing(self):
        bad_row = ["BM-BAD", "Thiếu số lượng", "Cái", "LO-X", date(2027, 1, 1), None, 1000, "", ""]
        content = _xlsx_bytes([GOOD_ROW_PRIVATE, bad_row])
        f = self._upload(content)
        before = self._counts(self.kho["kho_bm"])

        frappe.set_user(BM_USER)
        with self.assertRaises(frappe.ValidationError) as cm:
            kho_api.kho_import_commit(f.file_url)
        self.assertIn("dòng lỗi", str(cm.exception))
        self.assertNotIn("Traceback", str(cm.exception))

        after = self._counts(self.kho["kho_bm"])
        self.assertEqual(before, after, "một dòng lỗi thì KHÔNG dòng nào được ghi")
        self.assertFalse(frappe.db.exists("Customer Warehouse Item", {
            "kho": self.kho["kho_bm"], "ma_vat_tu": "BM-RIENG-01",
        }))

    def test_commit_links_miyano_item_code_and_never_creates_item(self):
        content = _xlsx_bytes([GOOD_ROW_MIYANO_NEW, GOOD_ROW_PRIVATE])
        f = self._upload(content)
        item_count_before = frappe.db.count("Item")

        frappe.set_user(BM_USER)
        result = kho_api.kho_import_commit(f.file_url)

        self.assertEqual(result["created_items"], 2)
        self.assertEqual(result["rows_written"], 2)

        miyano_vt = frappe.db.get_value(
            "Customer Warehouse Item",
            {"kho": self.kho["kho_bm"], "ma_vat_tu": "MYN-SYR-10"},
            ["item_code"], as_dict=True,
        )
        self.assertEqual(miyano_vt.item_code, "MYN-SYR-10")

        private_vt = frappe.db.get_value(
            "Customer Warehouse Item",
            {"kho": self.kho["kho_bm"], "ma_vat_tu": "BM-RIENG-01"},
            ["item_code"], as_dict=True,
        )
        self.assertIn(private_vt.item_code, (None, ""))

        # Mã khách tự thêm KHÔNG BAO GIỜ được phép tạo Item mới.
        self.assertFalse(frappe.db.exists("Item", "BM-RIENG-01"))
        self.assertEqual(frappe.db.count("Item"), item_count_before)

        receipt = frappe.get_doc("Customer Stock Receipt", result["receipt"])
        self.assertEqual(receipt.docstatus, 1)
        self.assertEqual(receipt.loai_nhap, "Tồn đầu kỳ")
        self.assertEqual(receipt.kho, self.kho["kho_bm"])
        self.assertEqual(len(receipt.items), 2)

        self.assertEqual(
            frappe.db.count("Customer Stock Ledger Entry", {"kho": self.kho["kho_bm"]}), 2
        )
        self.assertEqual(
            frappe.db.count("Customer Stock Lot Balance", {"kho": self.kho["kho_bm"]}), 2
        )

    def test_template_downloaded_and_committed_endtoend(self):
        frappe.set_user(BM_USER)
        kho_api.kho_import_template()
        content = frappe.local.response.filecontent
        frappe.local.response.clear()

        f = self._upload(content, filename="mau.xlsx")
        frappe.set_user(BM_USER)
        result = kho_api.kho_import_commit(f.file_url)
        self.assertEqual(result["rows_written"], 1)
        self.assertTrue(frappe.db.exists("Customer Warehouse Item", {
            "kho": self.kho["kho_bm"], "ma_vat_tu": "VT-001",
        }))

    def test_customer_a_cannot_import_using_customer_b_file(self):
        """A gọi preview/commit bằng file_url thuộc SỞ HỮU của B. Guard duy
        nhất khả thi ở đây là kiểm tra owner của File — hai endpoint không
        nhận tham số kho/khách nào để mà giả mạo trực tiếp."""
        content = _xlsx_bytes([GOOD_ROW_PRIVATE])
        f_bm = self._upload(content, user=BM_USER)

        before_bm = self._counts(self.kho["kho_bm"])
        before_pxn = self._counts(self.kho["kho_pxn"])

        frappe.set_user(PXN_USER)
        with self.assertRaises(frappe.PermissionError) as cm:
            kho_api.kho_import_preview(f_bm.file_url)
        self.assertNotIn("Traceback", str(cm.exception))

        with self.assertRaises(frappe.PermissionError):
            kho_api.kho_import_commit(f_bm.file_url)

        self.assertEqual(before_bm, self._counts(self.kho["kho_bm"]))
        self.assertEqual(before_pxn, self._counts(self.kho["kho_pxn"]))
