"""Chép ngược chín trường CR-03 từ PHIẾU sang các ĐƠN đã duyệt trước bản vá.

Vì sao cần patch này: `dat_hang._xay_don` chép dòng "hàng chưa có trong hệ
thống" từ phiếu sang đơn bằng một DANH SÁCH TRẮNG bốn trường (`ten_hang`,
`dvt`, `so_luong`, `ghi_chu`). Chín trường CR-03 — model, hãng, nước SX, quy
cách, NCC, giá đang mua, ẢNH, cờ không-có-ảnh, mô tả nhận dạng — bị bỏ lại ở
phiếu và không bao giờ tới đơn. Vá ở `999b39d` chỉ chữa cho đơn duyệt TỪ NAY;
đơn cũ vẫn trống, và Miyano vẫn không đọc được thứ khách đã khai cho chúng.

BỐN NGUYÊN TẮC, đều là ràng buộc chứ không phải sở thích:

1. **KHÔNG BAO GIỜ ĐÈ.** Chỉ điền vào ô đang RỖNG. Nhân viên Miyano có thể đã
   tự gõ tay một model vào dòng đơn để làm việc; đè lên là xoá công của họ để
   thay bằng dữ liệu cũ hơn.

2. **NHẬP NHẰNG THÌ BỎ QUA, KHÔNG ĐOÁN.** Không có khoá nối giữa dòng phiếu
   và dòng đơn (dòng đơn là bản ghi con MỚI, tên khác hẳn). Nối bằng
   `ten_hang` + `dvt`. Một phiếu có HAI dòng cùng tên cùng ĐVT thì không phân
   biệt được — bỏ qua và đếm vào báo cáo. Chép nhầm dữ liệu của mặt hàng này
   sang mặt hàng kia còn tệ hơn để trống: người đọc không có cách nào biết.

3. **KHÔNG ĐỤNG `modified` CỦA ĐƠN.** Phần lớn đơn đã submit; `frappe.db.
   set_value(..., update_modified=False)` ghi thẳng ô của bản ghi con mà
   không đổi dấu thời gian của chứng từ. Đổi `modified` của một đơn đã chốt
   là làm nhiễu mọi phép đối chiếu "ai sửa gì lúc nào".

4. **CHẠY LẠI KHÔNG SINH THÊM GÌ.** Lần hai mọi ô đích đã có giá trị nên
   không còn ô rỗng nào để điền.
"""

import frappe

# Chín trường CR-03. `khong_co_anh` là Check (mặc định 0) nên "rỗng" của nó
# là 0 — xử riêng ở dưới, không gộp chung phép kiểm chuỗi rỗng.
TRUONG_CHUOI = (
    "model_ma", "hang_san_xuat", "nuoc_san_xuat", "quy_cach",
    "ncc_hien_tai", "anh", "mo_ta_nhan_dang",
)
TRUONG_SO = ("gia_hien_tai",)
TRUONG_CO = ("khong_co_anh",)

DT_CON = "Sales Order Dat Ngoai Item"


def execute():
    # Chỉ đơn CÓ trỏ về phiếu — không có `custom_de_xuat` thì không có nguồn
    # nào để chép ngược, và đoán theo khách/ngày là mời một phép nối sai.
    dong_don = frappe.db.sql(
        """
        SELECT d.name, d.parent, d.ten_hang, d.dvt, so.custom_de_xuat AS phieu
        FROM `tabSales Order Dat Ngoai Item` d
        JOIN `tabSales Order` so
          ON so.name = d.parent AND d.parenttype = 'Sales Order'
        WHERE IFNULL(so.custom_de_xuat, '') != ''
        """,
        as_dict=True,
    )
    if not dong_don:
        return

    da_chep = 0
    nhap_nhang = 0
    khong_co_nguon = 0

    for d in dong_don:
        nguon = frappe.db.sql(
            """
            SELECT name, model_ma, hang_san_xuat, nuoc_san_xuat, quy_cach,
                   ncc_hien_tai, gia_hien_tai, anh, khong_co_anh, mo_ta_nhan_dang
            FROM `tabSales Order Dat Ngoai Item`
            WHERE parent = %(phieu)s AND parenttype = 'Portal De Xuat Mua'
              AND ten_hang = %(ten_hang)s AND IFNULL(dvt, '') = IFNULL(%(dvt)s, '')
            """,
            {"phieu": d.phieu, "ten_hang": d.ten_hang, "dvt": d.dvt},
            as_dict=True,
        )
        if not nguon:
            khong_co_nguon += 1
            continue
        if len(nguon) > 1:
            # Nguyên tắc 2 — không đoán. Đếm để báo cáo, để người vận hành
            # biết còn bao nhiêu dòng cần xử tay.
            nhap_nhang += 1
            continue

        p = nguon[0]
        dich = frappe.db.get_value(
            DT_CON, d.name,
            list(TRUONG_CHUOI + TRUONG_SO + TRUONG_CO),
            as_dict=True,
        )
        can_ghi = {}
        for f in TRUONG_CHUOI:
            if not (dich.get(f) or "").strip() and (p.get(f) or "").strip():
                can_ghi[f] = p.get(f)
        for f in TRUONG_SO:
            if not float(dich.get(f) or 0) and float(p.get(f) or 0):
                can_ghi[f] = p.get(f)
        for f in TRUONG_CO:
            if not dich.get(f) and p.get(f):
                can_ghi[f] = p.get(f)

        if not can_ghi:
            continue
        # Nguyên tắc 3 — không đụng `modified` của đơn đã chốt.
        frappe.db.set_value(DT_CON, d.name, can_ghi, update_modified=False)
        da_chep += 1

    if da_chep or nhap_nhang:
        print(
            f"[miyano_portal] CR-03 chép ngược sang đơn cũ: {da_chep} dòng đã "
            f"điền, {nhap_nhang} dòng nhập nhằng (bỏ qua, cần xử tay), "
            f"{khong_co_nguon} dòng phiếu gốc cũng không có dữ liệu."
        )
