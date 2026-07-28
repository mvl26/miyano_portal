const MP = { cart: [], contract: null, badge: {
  "Chờ xác nhận":"b-cho","Đang xử lý":"b-xuly","Đang giao":"b-giao",
  "Hoàn thành":"b-done","Đã huỷ":"b-huy"} };

// SPA chạy trên trang website (extends templates/web.html) nên `frappe.call`
// (desk helper) KHÔNG có sẵn ở đây — gọi thẳng /api/method/<method> bằng
// fetch() kèm CSRF token (window.CSRF_TOKEN, bơm từ index.py qua index.html).
// Giữ nguyên chữ ký call(method, args) => Promise<message> để không phải
// sửa các nơi gọi (await call("portal_me"), call("portal_catalog", {...})...).
function call(method, args){
  return fetch("/api/method/miyano_portal.api.portal." + method, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Frappe-CSRF-Token": window.CSRF_TOKEN || "",
      "Accept": "application/json",
    },
    body: JSON.stringify(args || {}),
    credentials: "same-origin",
  }).then(res => res.json().catch(() => ({})).then(data => {
    if(!res.ok){
      throw new Error(extractErrorMessage(data) || ("Lỗi máy chủ (" + res.status + ")"));
    }
    return data.message;
  }));
}

function extractErrorMessage(data){
  if(!data) return "";
  if(data._server_messages){
    try{
      const arr = JSON.parse(data._server_messages);
      const msgs = arr.map(m=>{ try{ return JSON.parse(m).message; }catch(e){ return m; } }).filter(Boolean);
      if(msgs.length) return msgs.join(" — ");
    }catch(e){ /* ignore */ }
  }
  if(data.exception){
    const parts = String(data.exception).split(":");
    return parts[parts.length - 1].trim();
  }
  return "";
}
const vnd = n => (n||0).toLocaleString('vi-VN')+' ₫';
const el = document.getElementById.bind(document);
const esc = s => String(s==null?'':s).replace(/[&<>"']/g, c=>(
  {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

function showError(e){
  el("mp-view").innerHTML = `<h2>Lỗi</h2><p class="err">${esc(e && e.message ? e.message : "Không thể tải dữ liệu.")}</p>`;
}

async function viewDashboard(){
  try{
    const me = await call("portal_me");
    const contracts = await call("portal_contracts");
    el("mp-view").innerHTML = `<h2>Xin chào, ${esc(me.customer_name)}</h2>
      <p>Tổng công nợ: <b>${vnd(me.outstanding)}</b></p>
      <h3>Hợp đồng nguyên tắc</h3>
      ${contracts.length ? `<ul>${contracts.map(c=>`<li>${esc(c.name)} — hạn mức đã dùng ${c.used_pct}%</li>`).join('')}</ul>`
                          : '<p>Chưa có hợp đồng nguyên tắc còn hiệu lực.</p>'}`;
  }catch(e){ showError(e); }
}

async function viewCatalog(){
  try{
    const contracts = await call("portal_contracts");
    if(!contracts.length){ el("mp-view").innerHTML="<p>Chưa có HĐNT hiệu lực.</p>"; return; }
    MP.contract = MP.contract || contracts[0].name;
    const cat = await call("portal_catalog", {contract: MP.contract});
    const selector = contracts.length > 1
      ? `<p>Hợp đồng:
          <select id="mp-contract-select" onchange="switchContract(this.value)">
            ${contracts.map(c=>`<option value="${esc(c.name)}" ${c.name===MP.contract?'selected':''}>${esc(c.name)}</option>`).join('')}
          </select></p>`
      : '';
    el("mp-view").innerHTML = `<h2>Danh mục — ${esc(MP.contract)}</h2>
      ${selector}
      <table><thead><tr><th>Mã</th><th>Tên</th><th>ĐVT</th><th>Đơn giá</th>
      <th>Còn lại</th><th>SL</th><th></th></tr></thead><tbody>
      ${cat.map((r,i)=>`<tr><td>${esc(r.item_code)}</td><td>${esc(r.item_name)}</td><td>${esc(r.uom)}</td>
        <td>${vnd(r.rate)}</td><td>${r.remaining}</td>
        <td><input id="q${i}" type="number" min="1" style="width:80px"></td>
        <td><button onclick="addToCart('${esc(r.item_code)}','${esc(r.item_name)}',${r.rate},${r.remaining},${i})">Thêm</button></td></tr>`).join('')}
      </tbody></table>`;
  }catch(e){ showError(e); }
}

window.switchContract = function(name){
  MP.contract = name;
  viewCatalog();
};

window.addToCart = function(code,name,rate,rem,i){
  const qty = parseFloat(el("q"+i).value||0);
  if(qty<=0) return alert("Số lượng phải > 0");
  if(qty>rem) return alert("Vượt hạn mức còn lại: "+rem);
  const existing = MP.cart.find(r=>r.item_code===code);
  if(existing){ existing.qty += qty; }
  else{ MP.cart.push({item_code:code,item_name:name,rate,qty}); }
  el("mp-cart-count").innerText = MP.cart.length;
};

async function viewCart(){
  if(!MP.cart.length){ el("mp-view").innerHTML="<h2>Giỏ hàng</h2><p>Giỏ hàng trống.</p>"; return; }
  const total = MP.cart.reduce((s,r)=>s+r.rate*r.qty,0);
  el("mp-view").innerHTML = `<h2>Giỏ hàng</h2>
    <table><thead><tr><th>Mã</th><th>Tên</th><th>SL</th><th>Đơn giá</th><th>Thành tiền</th></tr></thead>
    <tbody>${MP.cart.map(r=>`<tr><td>${esc(r.item_code)}</td><td>${esc(r.item_name)}</td><td>${r.qty}</td>
      <td>${vnd(r.rate)}</td><td>${vnd(r.rate*r.qty)}</td></tr>`).join('')}</tbody></table>
    <p><b>Tổng: ${vnd(total)}</b></p>
    <p>Số PO khách: <input id="mp-po"></p>
    <p>Ghi chú: <input id="mp-note"></p>
    <button onclick="placeOrder()">Xác nhận đặt hàng</button>
    <p id="mp-err" class="err"></p>`;
}

window.placeOrder = async function(){
  try{
    const res = await call("portal_order_place", {
      contract: MP.contract,
      items: JSON.stringify(MP.cart.map(r=>({item_code:r.item_code,qty:r.qty}))),
      po: el("mp-po").value, note: el("mp-note").value});
    MP.cart = []; el("mp-cart-count").innerText = 0;
    el("mp-view").innerHTML = `<h2>Đặt hàng thành công</h2>
      <p>Mã đơn: <b>${esc(res.sales_order)}</b> — đã gửi sang Miyano chờ xác nhận.</p>`;
  }catch(e){ el("mp-err").innerText = (e && e.message) || "Lỗi đặt hàng"; }
};

async function viewOrders(){
  try{
    const rows = await call("portal_order_history");
    el("mp-view").innerHTML = `<h2>Đơn hàng của tôi</h2>
      ${rows.length ? `<table><thead><tr><th>Mã</th><th>Ngày</th><th>Giá trị</th><th>Trạng thái</th></tr></thead>
      <tbody>${rows.map(r=>`<tr><td>${esc(r.name)}</td><td>${esc(r.transaction_date)}</td>
        <td>${vnd(r.grand_total)}</td>
        <td><span class="mp-badge ${MP.badge[r.status_vi]||'b-cho'}">${esc(r.status_vi)}</span></td></tr>`).join('')}
      </tbody></table>` : '<p>Chưa có đơn hàng nào.</p>'}`;
  }catch(e){ showError(e); }
}

async function viewInvoices(){
  try{
    const me = await call("portal_me");
    const rows = await call("portal_invoices");
    el("mp-view").innerHTML = `<h2>Hoá đơn &amp; công nợ</h2>
      <p>Tổng công nợ: <b>${vnd(me.outstanding)}</b></p>
      ${rows.length ? `<table><thead><tr><th>Số HĐ</th><th>Ngày</th><th>Giá trị</th><th>Còn nợ</th><th>Trạng thái</th></tr></thead>
      <tbody>${rows.map(r=>`<tr><td>${esc(r.name)}</td><td>${esc(r.posting_date)}</td>
        <td>${vnd(r.grand_total)}</td><td>${vnd(r.outstanding_amount)}</td><td>${esc(r.status_vi)}</td></tr>`).join('')}
      </tbody></table>` : '<p>Chưa có hoá đơn nào.</p>'}`;
  }catch(e){ showError(e); }
}

const VIEWS = {dashboard:viewDashboard, catalog:viewCatalog, cart:viewCart,
               orders:viewOrders, invoices:viewInvoices};
document.querySelectorAll('.mp-link[data-view]').forEach(a=>a.addEventListener('click', ()=>{
  document.querySelectorAll('.mp-link').forEach(x=>x.classList.remove('active'));
  a.classList.add('active');
  VIEWS[a.dataset.view]();
}));
viewDashboard();
