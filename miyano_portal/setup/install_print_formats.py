import frappe

NAME = "Miyano - Xác nhận đơn hàng"
HTML = """
<div class="print-heading"><h2>XÁC NHẬN ĐƠN HÀNG / ORDER CONFIRMATION</h2></div>
<p><b>Khách hàng / Customer:</b> {{ doc.customer_name }}</p>
<p><b>Số đơn / Order No:</b> {{ doc.name }}
   &nbsp; <b>Ngày / Date:</b> {{ frappe.utils.formatdate(doc.transaction_date, "dd/mm/yyyy") }}</p>
<p><b>Số PO khách / Customer PO:</b> {{ doc.custom_so_po_khach or "" }}</p>
<table class="table table-bordered">
  <thead><tr>
    <th>Mã / Code</th><th>Tên hàng / Item</th><th>SL / Qty</th>
    <th>Đơn giá / Rate</th><th>Thành tiền / Amount</th>
  </tr></thead>
  <tbody>
  {% for i in doc.items %}
    {%- if not la_dong_giu_cho(i.item_code) %}
    <tr>
      <td>{{ i.item_code }}</td><td>{{ i.item_name }}</td>
      <td class="text-right">{{ i.qty }}</td>
      <td class="text-right">{{ "{:,.0f}".format(i.rate) }} ₫</td>
      <td class="text-right">{{ "{:,.0f}".format(i.amount) }} ₫</td>
    </tr>
    {%- endif %}
  {% endfor %}
  </tbody>
</table>
<p class="text-right"><b>Tổng cộng / Total:</b> {{ "{:,.0f}".format(doc.grand_total) }} ₫</p>
"""

NAME_DN = "Miyano - Phiếu giao hàng"
HTML_DN = """
<div class="print-heading"><h2>PHIẾU GIAO HÀNG / DELIVERY NOTE</h2></div>
<p><b>Khách hàng / Customer:</b> {{ doc.customer_name }}</p>
<p><b>Số phiếu / Delivery No:</b> {{ doc.name }}
   &nbsp; <b>Ngày / Date:</b> {{ frappe.utils.formatdate(doc.posting_date, "dd/mm/yyyy") }}</p>
<p><b>Đơn hàng / Sales Order:</b> {{ doc.items[0].against_sales_order if doc.items else "" }}</p>
<table class="table table-bordered">
  <thead><tr>
    <th>Mã / Code</th><th>Tên hàng / Item</th><th>SL / Qty</th>
    <th>Đơn giá / Rate</th><th>Thành tiền / Amount</th>
  </tr></thead>
  <tbody>
  {% for i in doc.items %}
    <tr>
      <td>{{ i.item_code }}</td><td>{{ i.item_name }}</td>
      <td class="text-right">{{ i.qty }}</td>
      <td class="text-right">{{ "{:,.0f}".format(i.rate) }} ₫</td>
      <td class="text-right">{{ "{:,.0f}".format(i.amount) }} ₫</td>
    </tr>
  {% endfor %}
  </tbody>
</table>
<p class="text-right"><b>Tổng cộng / Total:</b> {{ "{:,.0f}".format(doc.grand_total) }} ₫</p>
"""

NAME_SI = "Miyano - Hoá đơn"
HTML_SI = """
<div class="print-heading"><h2>HOÁ ĐƠN BÁN HÀNG / SALES INVOICE</h2></div>
<p><b>Khách hàng / Customer:</b> {{ doc.customer_name }}</p>
<p><b>Số hoá đơn / Invoice No:</b> {{ doc.name }}
   &nbsp; <b>Ngày / Date:</b> {{ frappe.utils.formatdate(doc.posting_date, "dd/mm/yyyy") }}</p>
<p><b>Đơn hàng / Sales Order:</b> {{ doc.items[0].sales_order if doc.items else "" }}</p>
<table class="table table-bordered">
  <thead><tr>
    <th>Mã / Code</th><th>Tên hàng / Item</th><th>SL / Qty</th>
    <th>Đơn giá / Rate</th><th>Thành tiền / Amount</th>
  </tr></thead>
  <tbody>
  {% for i in doc.items %}
    <tr>
      <td>{{ i.item_code }}</td><td>{{ i.item_name }}</td>
      <td class="text-right">{{ i.qty }}</td>
      <td class="text-right">{{ "{:,.0f}".format(i.rate) }} ₫</td>
      <td class="text-right">{{ "{:,.0f}".format(i.amount) }} ₫</td>
    </tr>
  {% endfor %}
  </tbody>
</table>
<p class="text-right"><b>Tổng cộng / Total:</b> {{ "{:,.0f}".format(doc.grand_total) }} ₫</p>
<p class="text-right"><b>Còn nợ / Outstanding:</b> {{ "{:,.0f}".format(doc.outstanding_amount) }} ₫</p>
"""

NAME_BG = "Miyano - Báo giá"
HTML_BG = """
<div class="print-heading"><h2>BÁO GIÁ / QUOTATION</h2></div>
<p><b>Khách hàng / Customer:</b> {{ doc.customer_name }}</p>
<p><b>Số đơn / Order No:</b> {{ doc.name }}
   &nbsp; <b>Ngày báo giá / Quotation Date:</b>
   {{ frappe.utils.formatdate(doc.custom_ngay_gui_khach_duyet or doc.transaction_date, "dd/mm/yyyy") }}</p>
<p><b>Hiệu lực đến / Valid Until:</b>
   {{ han_hieu_luc_bao_gia(doc).strftime('%d/%m/%Y') }}</p>
<table class="table table-bordered">
  <thead><tr>
    <th>Mã / Code</th><th>Tên hàng / Item</th><th>ĐVT / UoM</th><th>SL / Qty</th>
    <th>Đơn giá / Rate</th><th>Thành tiền / Amount</th>
  </tr></thead>
  <tbody>
  {% for i in doc.items %}
    {%- if not la_dong_giu_cho(i.item_code) %}
    <tr>
      <td>{{ i.item_code }}</td><td>{{ i.item_name }}</td><td>{{ i.uom }}</td>
      <td class="text-right">{{ i.qty }}</td>
      <td class="text-right">{{ "{:,.0f}".format(i.rate).replace(",", ".") }} ₫</td>
      <td class="text-right">{{ "{:,.0f}".format(i.amount).replace(",", ".") }} ₫</td>
    </tr>
    {%- endif %}
  {% endfor %}
  </tbody>
</table>
{% set cho_nguon = doc.get("custom_dat_ngoai") | selectattr("da_xu_ly", "equalto", 0) | list %}
{% if cho_nguon %}
<h4>Hàng đang tìm nguồn / Items being sourced</h4>
<table class="table table-bordered">
  <thead><tr><th>Tên hàng / Item</th><th>ĐVT / UoM</th><th>SL / Qty</th></tr></thead>
  <tbody>
  {% for d in cho_nguon %}
    <tr><td>{{ d.ten_hang }}</td><td>{{ d.dvt }}</td>
        <td class="text-right">{{ d.so_luong }}</td></tr>
  {% endfor %}
  </tbody>
</table>
<p class="text-muted">Các mặt hàng trên chưa có trong báo giá; Miyano sẽ báo giá bổ sung sau khi tìm được nguồn.</p>
{% endif %}
{# Lệch so với brief gốc — xem ghi chú trong nhomB-report.md §"chỗ lệch": #}
{# `item_khop` KHÔNG BAO GIỜ tự sinh một dòng "items" mới ở bất cứ đâu trong #}
{# codebase (đã kiểm `_xay_don_ban_le`/`dong_bo_da_xu_ly_dat_ngoai` — hàm sau #}
{# chỉ BẬT cờ `da_xu_ly`, không `so.append("items", ...)`) — nên một dòng đặt #}
{# ngoài ĐÃ khớp mã (`da_xu_ly=1`) không nằm trong `doc.items` VÀ bị lọc khỏi #}
{# bảng "chưa xử lý" ở trên: KHÔNG bảng nào in nó ra. Đúng lỗi mà docstring #}
{# test (`test_bao_gia_pdf.py`) đặt lên hàng đầu — "thiếu dòng đặt ngoài đã #}
{# khớp mã là khách nhận báo giá thiếu đúng món họ lo nhất". Thêm bảng riêng #}
{# cho nhóm ĐÃ khớp, ghi rõ mã Miyano đã gán — khách thấy yêu cầu của mình #}
{# được phục vụ bằng dòng hàng nào trong bảng trên, kể cả khi đó là một mã #}
{# đã có sẵn trong giỏ (không phải một dòng "items" riêng mới thêm). #}
{% set da_khop = doc.get("custom_dat_ngoai") | selectattr("da_xu_ly", "equalto", 1) | list %}
{% if da_khop %}
<h4>Hàng đặt ngoài đã khớp mã / Matched items</h4>
<table class="table table-bordered">
  <thead><tr>
    <th>Tên hàng khách yêu cầu / Requested</th>
    <th>Mã đã khớp / Matched code</th>
    <th>SL / Qty</th>
  </tr></thead>
  <tbody>
  {% for d in da_khop %}
    <tr><td>{{ d.ten_hang }}</td><td>{{ d.item_khop }}</td>
        <td class="text-right">{{ d.so_luong }}</td></tr>
  {% endfor %}
  </tbody>
</table>
<p class="text-muted">Các mặt hàng trên đã được Miyano khớp mã và tính vào bảng báo giá phía trên.</p>
{% endif %}
<p class="text-right"><b>Tổng cộng / Total:</b> {{ "{:,.0f}".format(doc.grand_total).replace(",", ".") }} ₫</p>
"""
# review Minor — CHỈ mẫu Báo giá (`HTML_BG`, mới) đổi sang dấu chấm phân
# nhóm (`1.234.567 ₫`, đúng quy ước dự án). Ba mẫu CŨ ở trên (`HTML`,
# `HTML_DN`, `HTML_SI`) vẫn dùng `"{:,.0f}"` (dấu phẩy, sai quy ước) — đó
# là NỢ CŨ, cố ý KHÔNG sửa ở đây để không lan phạm vi ngoài mẫu Báo giá mới.

FORMATS = [
    (NAME, "Sales Order", HTML),
    (NAME_DN, "Delivery Note", HTML_DN),
    (NAME_SI, "Sales Invoice", HTML_SI),
    (NAME_BG, "Sales Order", HTML_BG),
]


def install_portal_print_formats():
    for name, doc_type, html in FORMATS:
        if frappe.db.exists("Print Format", name):
            continue
        frappe.get_doc({
            "doctype": "Print Format",
            "name": name,
            "doc_type": doc_type,
            "standard": "No",
            "custom_format": 1,
            "print_format_type": "Jinja",
            "html": html,
        }).insert(ignore_permissions=True)
