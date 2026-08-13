"""Danh mục NCC (nhà cung cấp khác) của kho khách hàng — US-E4.1, BR-N3.

Cùng khuôn với kho/vat_tu.py: tầng này KHÔNG biết gì về phiên đăng nhập,
`kho` luôn do nơi gọi (api/kho.py) truyền vào sau khi đã resolve từ phiên.

Chốt chặn "trùng tuyệt đối" (NL-7.3) sống ở customer_supplier.py:validate() —
chạy trên MỌI đường ghi (Desk lẫn endpoint này), không lặp lại ở đây. Module
này chỉ tính thêm gợi ý "gần giống" (KHÔNG chặn) cho response của
kho_ncc_save, đúng NL-7.3: "gợi ý chọn NCC có sẵn thay vì tạo mới".
"""

import frappe

from miyano_portal.kho import similarity
from miyano_portal.kho.import_ton_dau import _norm

TRUONG_MO_TA = ("mst", "dien_thoai", "email", "dia_chi", "ghi_chu")


def _existing_rows(kho: str, exclude: str | None) -> list:
    rows = frappe.get_all(
        "Customer Supplier", filters={"kho": kho}, fields=["name", "ten_ncc"]
    )
    if exclude:
        rows = [r for r in rows if r.name != exclude]
    return rows


def _goi_y_gan_giong(kho: str, ten: str, exclude: str | None) -> list[str]:
    """NL-7.3: liệt kê NCC có tên GẦN GIỐNG (không phải trùng tuyệt đối —
    trùng tuyệt đối đã bị validate() chặn từ trước khi tới đây) để client gợi
    ý chọn thay vì tạo mới. Không chặn."""
    goi_y = []
    for row in _existing_rows(kho, exclude):
        if similarity.phan_loai(ten, row.ten_ncc) == "gan_giong":
            goi_y.append(f"{row.name}: {row.ten_ncc}")
    return goi_y


def ra_dict(name: str) -> dict:
    row = frappe.db.get_value(
        "Customer Supplier", name,
        ["name", "ten_ncc", "mst", "dien_thoai", "email", "dia_chi", "ghi_chu", "active"],
        as_dict=True,
    )
    for f in ("mst", "dien_thoai", "email", "dia_chi", "ghi_chu"):
        row[f] = row[f] or ""
    row["active"] = int(row["active"] or 0)
    return row


def _thong_ke_90n(name: str) -> tuple[int, float]:
    tu_ngay = frappe.utils.add_days(frappe.utils.today(), -90)
    so_phieu = frappe.db.count("Customer Stock Receipt", {"ncc": name, "docstatus": 1})
    tong = frappe.db.sql(
        """select coalesce(sum(tong_tien), 0) from `tabCustomer Stock Receipt`
           where ncc=%s and docstatus=1 and ngay >= %s""",
        (name, tu_ngay),
    )
    return so_phieu, float(tong[0][0] or 0)


def list_rows(kho: str, tim_kiem: str | None = None, ca_inactive=False) -> list[dict]:
    """Danh mục NCC — cùng khuôn `kho_vat_tu_list()` (Phase 3): trả ĐỦ chi
    tiết mô tả trong MỘT lượt, không chỉ vài cột hiển thị bảng.

    Gap 1 (review E4 phần B, báo lên từ agent giao diện): trước bản này chỉ
    có `name/ten_ncc/mst/so_phieu/gia_tri_90n/active` — bảng "NCC của tôi"
    thiếu cột Điện thoại, và màn Sửa không có cách nào đọc lại
    dien_thoai/email/dia_chi/ghi_chu HIỆN CÓ của một NCC đã tồn tại (không có
    endpoint "đọc một NCC" nào khác) để điền sẵn vào form — client buộc phải
    tự đoán/để trống, và LƯU đè sẽ xoá mất dữ liệu cũ vì `ncc.save()` chỉ ghi
    đè field nào CÓ trong payload nhưng client không đọc được giá trị cũ để
    gửi lại đúng. Trả nguyên `ra_dict()` (đã có sẵn, dùng chung cho response
    của `save()`) cho MỖI dòng thay vì việc thêm một endpoint riêng —  một
    lượt tải danh sách là đủ, không cần round-trip thứ hai."""
    filters = {"kho": kho}
    if not frappe.utils.cint(ca_inactive):
        filters["active"] = 1
    rows = frappe.get_all(
        "Customer Supplier", filters=filters,
        fields=["name", "ten_ncc", "mst", "dien_thoai", "email", "dia_chi", "ghi_chu", "active"],
        order_by="ten_ncc asc",
    )
    if tim_kiem:
        hay = similarity.khong_dau(tim_kiem)
        rows = [r for r in rows if hay in similarity.khong_dau(r.ten_ncc)]
    out = []
    for r in rows:
        so_phieu, gia_tri_90n = _thong_ke_90n(r.name)
        out.append({
            "name": r.name,
            "ten_ncc": r.ten_ncc,
            "mst": r.mst or "",
            "dien_thoai": r.dien_thoai or "",
            "email": r.email or "",
            "dia_chi": r.dia_chi or "",
            "ghi_chu": r.ghi_chu or "",
            "so_phieu": so_phieu,
            "gia_tri_90n": gia_tri_90n,
            "active": int(r.active or 0),
        })
    return out


def save(kho: str, du_lieu: dict) -> dict:
    """Tạo mới (name rỗng/None) hoặc sửa (name có giá trị, PHẢI thuộc kho —
    nơi gọi đã kiểm bằng _ncc_cua_kho() trước khi tới đây cho trường hợp sửa)."""
    name = du_lieu.get("name")
    ten = _norm(du_lieu.get("ten_ncc"))
    if not ten:
        frappe.throw("Thiếu Tên NCC.", frappe.ValidationError)

    goi_y = _goi_y_gan_giong(kho, ten, exclude=name)

    # Gap 3 (review E4 phần B): chế độ XEM TRƯỚC, không ghi gì — cùng khuôn
    # `vat_tu.tao()`. Chỉ áp cho TẠO MỚI (`name` rỗng): "Vẫn tạo/Huỷ" là hỏi
    # về một bản ghi CHƯA TỒN TẠI; sửa một NCC có sẵn không cần xem trước vì
    # không có gì phải rollback — đóng modal mà không gọi save() là đủ.
    if du_lieu.get("chi_kiem_tra") and not name:
        return {"name": None, "ten_ncc": ten, "goi_y_trung": goi_y}

    if name:
        doc = frappe.get_doc("Customer Supplier", name)
    else:
        doc = frappe.new_doc("Customer Supplier")
        doc.kho = kho

    doc.ten_ncc = ten
    for truong in TRUONG_MO_TA:
        if truong in du_lieu:
            setattr(doc, truong, _norm(du_lieu.get(truong)) or None)
    if "active" in du_lieu:
        doc.active = 1 if frappe.utils.cint(du_lieu.get("active")) else 0

    if doc.is_new():
        doc.insert(ignore_permissions=True)
    else:
        doc.save(ignore_permissions=True)

    out = ra_dict(doc.name)
    out["goi_y_trung"] = goi_y
    return out
