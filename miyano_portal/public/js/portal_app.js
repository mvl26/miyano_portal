/* ==========================================================================
   Miyano Client Portal — SPA renderers wired to the live whitelist API.
   Runs on a website page (extends templates/web.html) so frappe.call (a desk
   helper) is NOT available: every call goes through fetch() + CSRF header.
   DOM-safety: untrusted values (item names/codes, order ids) are never
   interpolated into inline onclick="fn('...')" handlers; they ride on data-*
   attributes read back via .dataset and delegated listeners, and any text
   placed via innerHTML is passed through esc(). Actions are dispatched by a
   single delegated click/input listener keyed on data-action.
   ========================================================================== */

/* ---------------------------------------------------------------- API layer */
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

/* ---------------------------------------------------------------- helpers */
const el   = document.getElementById.bind(document);
const vnd  = n => (Math.round(Number(n)||0)).toLocaleString('vi-VN') + ' ₫';
const vndShort = n => {
  n = Number(n)||0;
  if(Math.abs(n) >= 1e6) return (n/1e6).toFixed(1).replace('.', ',') + ' tr ₫';
  return vnd(n);
};
const esc = s => String(s==null?'':s).replace(/[&<>"']/g, c=>(
  {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const dvn = s => { // ISO date -> dd/mm/yyyy
  if(!s) return '';
  const p = String(s).slice(0,10).split('-');
  return p.length===3 ? `${p[2]}/${p[1]}/${p[0]}` : String(s);
};
const pct = (v) => Math.max(0, Math.min(100, Math.round(Number(v)||0)));
const badgeClass = (statusVi) => ({
  "Chờ xác nhận":"b-gray", "Đang xử lý":"b-blue", "Đang giao":"b-orange",
  "Hoàn thành":"b-green", "Đã huỷ":"b-red",
})[statusVi] || "b-gray";
// Sales Invoice status_vi now arrives already localised from the API
// (INVOICE_STATUS_VI in portal.py). Map the Vietnamese label -> badge colour.
const invBadge = (statusVi) => ({
  "Đã thanh toán":"b-green", "Quá hạn":"b-red", "TT một phần":"b-orange",
  "Chưa thanh toán":"b-blue", "Nháp":"b-gray", "Đã huỷ":"b-red",
})[statusVi] || "b-blue";
const daysUntil = (iso) => {
  if(!iso) return null;
  const d = new Date(String(iso).slice(0,10) + "T00:00:00");
  if(isNaN(d)) return null;
  const now = new Date(); now.setHours(0,0,0,0);
  return Math.round((d - now) / 86400000);
};
const pdfHref = (doctype, name) =>
  "/api/method/miyano_portal.api.portal.portal_document_download"
  + "?doctype=" + encodeURIComponent(doctype) + "&name=" + encodeURIComponent(name);

/* ---------------------------------------------------------------- state */
const MP = {
  page: "dash",
  cart: {},            // item_code -> {qty, rate, name, uom, vat_pct, remaining}
  contract: null,
  contracts: null,     // cached (rarely changes within a session)
  me: null,            // cached
  catalog: [],         // current contract catalog (for client-side search)
  catFilter: "",
  catGroup: "",        // active item_group filter chip
  currentOrder: null,
  history: null,       // last fetched history (dashboard reuse)
};
const TITLES = {
  dash:"Tổng quan", cat:"Đặt hàng theo HĐNT", cart:"Giỏ hàng",
  done:"Đặt hàng thành công", orders:"Đơn hàng của tôi", detail:"Chi tiết đơn hàng",
  inv:"Hoá đơn & công nợ", prof:"Hồ sơ đơn vị",
};

async function getMe(){ if(!MP.me) MP.me = await call("portal_me"); return MP.me; }
async function getContracts(){ if(!MP.contracts) MP.contracts = await call("portal_contracts"); return MP.contracts; }

/* ---------------------------------------------------------------- cart math */
function totals(){
  let sub=0, vat=0, n=0;
  Object.values(MP.cart).forEach(it=>{
    const line = it.qty * it.rate;
    sub += line; vat += line * (Number(it.vat_pct)||0) / 100; n++;
  });
  return { sub, vat: Math.round(vat), tot: Math.round(sub+vat), n };
}
function refreshCartBadges(){
  const { n, tot } = totals();
  document.querySelectorAll('.mp-cartn').forEach(x=>{ x.textContent = n; });
  document.querySelectorAll('.mp-cartn2').forEach(x=>{ x.textContent = n; x.style.display = n?'inline-block':'none'; });
  const bar = el('cartbar');
  if(bar) bar.style.display = (n>0 && MP.page==='cat') ? 'block' : 'none';
  const cbn = el('cb-n'), cbt = el('cb-t');
  if(cbn) cbn.textContent = n;
  if(cbt) cbt.textContent = vnd(tot);
}

/* ==========================================================================
   ROUTER
   ========================================================================== */
const VIEWS = {
  dash:viewDashboard, cat:viewCatalog, cart:viewCart, done:viewDone,
  orders:viewOrders, detail:viewDetail, inv:viewInvoices, prof:viewProfile,
};
function go(page){
  MP.page = page;
  document.querySelectorAll('.pg').forEach(x=>{ x.style.display = (x.id==='pg-'+page)?'block':'none'; });

  // active nav — desktop sidebar has all 6; mobile bottom-nav has 5 (inv->prof)
  let dk = page, mk = page;
  if(page==='detail'){ dk='orders'; mk='orders'; }
  if(page==='done'){ dk='cart'; mk='cart'; }
  if(page==='inv'){ mk='prof'; }
  document.querySelectorAll('[data-nav-d]').forEach(a=>a.classList.toggle('on', a.dataset.navD===dk));
  document.querySelectorAll('[data-nav-m]').forEach(a=>a.classList.toggle('on', a.dataset.navM===mk));

  el('hdr-t').textContent = TITLES[page] || '';
  el('backbtn').style.display = (page==='detail'||page==='inv') ? 'block' : 'none';

  const r = VIEWS[page];
  if(r) r();
  refreshCartBadges();
  window.scrollTo(0,0);
}
function goBack(){ go(MP.page==='detail' ? 'orders' : 'dash'); }

function showError(container, e){
  el(container).innerHTML =
    `<h2>Lỗi</h2><p class="err">${esc(e && e.message ? e.message : "Không thể tải dữ liệu.")}</p>`;
}
function topbar(title, sub, actionsHtml){
  return `<div class="topbar"><div><h2>${esc(title)}</h2>${sub?`<div class="sub">${esc(sub)}</div>`:''}</div>`
    + (actionsHtml?`<div class="flex">${actionsHtml}</div>`:'') + `</div>`;
}

/* ==========================================================================
   S-02 DASHBOARD
   ========================================================================== */
async function viewDashboard(){
  const box = 'pg-dash';
  el(box).innerHTML = `<p class="muted">Đang tải…</p>`;
  try{
    const [me, contracts, history, invoices] = await Promise.all([
      getMe(), getContracts(),
      call("portal_order_history", {limit:100}),
      call("portal_invoices", {limit:100}),
    ]);
    MP.history = history;
    if(me){ el('who-name').textContent = me.customer_name || me.customer || ''; el('who-sub').textContent = me.customer || ''; }

    const nCho = history.filter(o=>o.status_vi==="Chờ xác nhận").length;
    const nGiao = history.filter(o=>o.status_vi==="Đang giao").length;
    const nInv = invoices.filter(i=>Number(i.outstanding_amount)>0).length;
    const recent = history.slice(0,5);
    const c = contracts && contracts[0];

    const recentRows = recent.length ? recent.map(o=>`
      <tr class="mp-orow" data-action="detail" data-order="${esc(o.name)}" style="cursor:pointer">
        <td><b>${esc(o.name)}</b></td><td>${esc(dvn(o.transaction_date))}</td>
        <td class="right">${vnd(o.grand_total)}</td>
        <td><span class="badge ${badgeClass(o.status_vi)}">${esc(o.status_vi)}</span></td></tr>`).join('')
      : `<tr><td colspan="4" class="muted">Chưa có đơn hàng nào.</td></tr>`;

    // Mobile version of recent orders (rowlines)
    const recentCards = recent.length ? recent.map(o=>`
      <div class="rowline click" data-action="detail" data-order="${esc(o.name)}">
        <span><b>${esc(o.name)}</b><br><span class="tag">${esc(dvn(o.transaction_date))} · ${vnd(o.grand_total)}</span></span>
        <span class="badge ${badgeClass(o.status_vi)}">${esc(o.status_vi)}</span></div>`).join('')
      : `<p class="muted">Chưa có đơn hàng nào.</p>`;

    const contractCard = c ? `
      <p style="font-weight:600">${esc(c.name)}</p>
      <p class="tag">Hiệu lực: ${esc(dvn(c.from_date))} – ${esc(dvn(c.to_date))}${c.item_count!=null?` · ${esc(c.item_count)} mặt hàng`:''}</p>
      <p style="font-size:13px;margin-top:10px">Hạn mức đã sử dụng: <b>${pct(c.used_pct)}%</b></p>
      <div class="bar"><i style="width:${pct(c.used_pct)}%" class="${pct(c.used_pct)>=80?'hot':''}"></i></div>`
      : `<p class="muted">Chưa có hợp đồng nguyên tắc còn hiệu lực.</p>`;

    el(box).innerHTML = `
      ${topbar('Xin chào, ' + (me.customer_name||''), (me.customer||'') + ' – cập nhật hôm nay',
               `<button class="btn only-desktop" data-action="go" data-page="cat">+ Đặt hàng mới</button>`)}
      <div class="kpis">
        <div class="card kpi"><div class="n">${nCho}</div><div class="t">Đơn chờ xác nhận</div></div>
        <div class="card kpi"><div class="n">${nGiao}</div><div class="t">Đơn đang giao</div></div>
        <div class="card kpi"><div class="n">${nInv}</div><div class="t">Hoá đơn chưa thanh toán</div></div>
        <div class="card kpi"><div class="n" style="color:var(--red)">${vndShort(me.outstanding)}</div><div class="t">Tổng công nợ</div></div>
      </div>
      <button class="btn btn-block only-mobile" data-action="go" data-page="cat" style="margin-bottom:12px">+ Đặt hàng mới</button>
      <div class="grid2">
        <div>
          <div class="card only-desktop">
            <h3 style="margin-bottom:10px">Đơn hàng gần đây</h3>
            <table><thead><tr><th>Mã đơn</th><th>Ngày đặt</th><th class="right">Giá trị</th><th>Trạng thái</th></tr></thead>
            <tbody>${recentRows}</tbody></table>
          </div>
          <div class="card only-mobile">
            <h3 style="margin-bottom:6px">Đơn hàng gần đây</h3>${recentCards}
          </div>
        </div>
        <div class="card"><h3 style="margin-bottom:10px">Hợp đồng nguyên tắc</h3>${contractCard}</div>
      </div>`;
  }catch(e){ showError(box, e); }
}

/* ==========================================================================
   S-03 CATALOG
   ========================================================================== */
async function viewCatalog(){
  const box = 'pg-cat';
  el(box).innerHTML = `<p class="muted">Đang tải…</p>`;
  try{
    const contracts = await getContracts();
    if(!contracts.length){
      el(box).innerHTML = topbar('Đặt hàng theo Hợp đồng nguyên tắc','') +
        `<div class="card"><p class="muted">Chưa có hợp đồng nguyên tắc còn hiệu lực.</p></div>`;
      return;
    }
    MP.contract = MP.contract || contracts[0].name;
    MP.catalog = await call("portal_catalog", {contract: MP.contract});

    const selector = `<select id="cat-contract" data-action="none">${
      contracts.map(c=>`<option value="${esc(c.name)}" ${c.name===MP.contract?'selected':''}>${esc(c.name)} (${esc(dvn(c.from_date))} – ${esc(dvn(c.to_date))})</option>`).join('')
    }</select>`;

    // distinct item groups -> filter chips
    const groups = Array.from(new Set(MP.catalog.map(it=>it.item_group).filter(Boolean))).sort();
    if(MP.catGroup && !groups.includes(MP.catGroup)) MP.catGroup = "";
    const chips = `<div class="chips" id="cat-chips">
      <button class="chip ${MP.catGroup?'':'on'}" data-action="chip" data-group="">Tất cả</button>
      ${groups.map(g=>`<button class="chip ${MP.catGroup===g?'on':''}" data-action="chip" data-group="${esc(g)}">${esc(g)}</button>`).join('')}
    </div>`;

    el(box).innerHTML = `
      ${topbar('Đặt hàng theo Hợp đồng nguyên tắc',
               'Giá & danh mục theo hợp đồng đã ký – không áp dụng cho mặt hàng ngoài hợp đồng')}
      <div class="card">
        <div class="flex" style="flex-wrap:wrap">
          <div style="min-width:260px;flex:1"><label class="tag">Hợp đồng nguyên tắc</label>${selector}</div>
          <div style="min-width:220px;flex:1"><label class="tag">Tìm kiếm</label>
            <input id="cat-q" placeholder="Mã hoặc tên mặt hàng..." value="${esc(MP.catFilter)}" data-action="cat-search"></div>
        </div>
      </div>
      ${groups.length ? chips : ''}
      <div id="cat-list"></div>`;
    renderCatList();
  }catch(e){ showError(box, e); }
}
// Quota bar HTML: used% = used/total; red fill + warning when >=80%.
function quotaBar(it){
  const total = Number(it.total)||0;
  const used = Number(it.used)||0;
  const p = total ? pct(used/total*100) : 0;
  const hot = p >= 80;
  return `<div class="bar"><i style="width:${p}%" class="${hot?'hot':''}"></i></div>`
    + (hot ? `<span class="warn">Sắp hết hạn mức</span>` : '');
}
function renderCatList(){
  const q = (MP.catFilter||'').toLowerCase();
  const rows = MP.catalog.filter(it =>
    (!MP.catGroup || it.item_group===MP.catGroup) &&
    (!q || String(it.item_code).toLowerCase().includes(q) || String(it.item_name).toLowerCase().includes(q)));
  const inCart = c => (MP.cart[c] ? MP.cart[c].qty : 0);

  // Desktop table
  const tableRows = rows.map(it=>{
    const left = Number(it.remaining) - inCart(it.item_code);
    return `<tr>
      <td><b>${esc(it.item_code)}</b></td>
      <td>${esc(it.item_name)}<br><span class="tag">${esc(it.item_group||'')}${Number(it.vat_pct)?` · VAT ${esc(it.vat_pct)}%`:''}</span></td>
      <td>${esc(it.uom)}</td>
      <td class="right">${vnd(it.rate)}</td>
      <td style="min-width:150px">${left}/${Number(it.total)} ${esc(it.uom)}${quotaBar(it)}</td>
      <td><input class="qty" type="number" min="1" value="1" data-qty="${esc(it.item_code)}"></td>
      <td><button class="btn btn-sm" data-action="add" data-code="${esc(it.item_code)}">+ Giỏ</button></td>
    </tr>`;
  }).join('');

  // Mobile cards
  const cards = rows.map(it=>{
    const left = Number(it.remaining) - inCart(it.item_code);
    return `<div class="card item">
      <div class="nm"><b>${esc(it.item_code)}</b> · ${esc(it.item_name)}</div>
      <span class="tag">${esc(it.item_group||'')} · ĐVT: ${esc(it.uom)}${Number(it.vat_pct)?` · VAT ${esc(it.vat_pct)}%`:''}</span>
      <div class="sb" style="margin-top:8px;align-items:flex-start">
        <span class="pr">${vnd(it.rate)}</span>
        <span class="tag right" style="min-width:140px">Hạn mức còn ${left}/${Number(it.total)} ${esc(it.uom)}${quotaBar(it)}</span>
      </div>
      <div class="sb" style="margin-top:10px">
        <div class="step">
          <button data-action="step" data-code="${esc(it.item_code)}" data-dir="-1">−</button>
          <input type="number" min="1" value="1" data-qty="${esc(it.item_code)}">
          <button data-action="step" data-code="${esc(it.item_code)}" data-dir="1">+</button>
        </div>
        <button class="btn btn-sm" data-action="add" data-code="${esc(it.item_code)}">+ Thêm vào giỏ</button>
      </div>
    </div>`;
  }).join('');

  el('cat-list').innerHTML = rows.length ? `
    <div class="card flush only-desktop">
      <table><thead><tr><th>Mã</th><th>Tên mặt hàng / quy cách</th><th>ĐVT</th>
        <th class="right">Đơn giá</th><th>Hạn mức còn lại</th><th style="width:90px">Số lượng</th><th></th></tr></thead>
      <tbody>${tableRows}</tbody></table></div>
    <div class="only-mobile">${cards}</div>`
    : `<div class="card"><p class="muted">Không tìm thấy mặt hàng phù hợp.</p></div>`;
}
function catStep(code, dir){
  const inp = document.querySelector('[data-qty="'+cssq(code)+'"]');
  if(inp) inp.value = Math.max(1, (parseInt(inp.value)||1) + dir);
}
function addToCart(code){
  const it = MP.catalog.find(x=>x.item_code===code);
  if(!it) return;
  // read the qty input nearest this action (there can be a desktop + mobile
  // input with the same data-qty; both mirror the same intended qty)
  const inp = document.querySelector('[data-qty="'+cssq(code)+'"]');
  const qty = parseInt(inp && inp.value) || 0;
  if(qty<=0){ alert("Số lượng phải > 0"); return; }
  const already = MP.cart[code] ? MP.cart[code].qty : 0;
  const left = Number(it.remaining) - already;
  if(qty > left){
    alert(`Vượt hạn mức HĐNT!\n${it.item_code} chỉ còn được đặt tối đa ${left} ${it.uom} theo hợp đồng.`);
    return;
  }
  if(MP.cart[code]) MP.cart[code].qty += qty;
  else MP.cart[code] = { qty, rate:Number(it.rate), name:it.item_name, uom:it.uom,
                         vat_pct:Number(it.vat_pct)||0, remaining:Number(it.remaining) };
  refreshCartBadges();
  renderCatList(); // refresh remaining display
}
// escape a value for use inside a CSS attribute selector
function cssq(v){ return String(v).replace(/["\\]/g, '\\$&'); }

/* ==========================================================================
   S-04 CART
   ========================================================================== */
function viewCart(){
  const box = 'pg-cart';
  const keys = Object.keys(MP.cart);
  if(!keys.length){
    el(box).innerHTML = topbar('Giỏ hàng & xác nhận đơn','') +
      `<div class="card"><p class="muted">Giỏ hàng trống – vào mục
        <a data-action="go" data-page="cat" style="color:var(--blue2);cursor:pointer">Đặt hàng</a> để chọn mặt hàng.</p></div>`;
    return;
  }
  const { sub, vat, tot } = totals();

  const tableRows = keys.map(c=>{
    const it = MP.cart[c];
    return `<tr>
      <td><b>${esc(c)}</b> ${esc(it.name)}</td>
      <td>${esc(it.uom)}</td>
      <td class="right">${vnd(it.rate)}</td>
      <td><input class="qty" type="number" min="1" value="${it.qty}" data-cartqty="${esc(c)}"></td>
      <td class="right"><b>${vnd(it.qty*it.rate)}</b></td>
      <td><button class="btn-o btn-sm btn-danger" data-action="cart-del" data-code="${esc(c)}">✕</button></td>
    </tr>`;
  }).join('');

  const cards = keys.map(c=>{
    const it = MP.cart[c];
    return `<div class="card">
      <div class="sb" style="align-items:flex-start">
        <div style="font-size:13px"><b>${esc(c)}</b> ${esc(it.name)}<br><span class="tag">${vnd(it.rate)} / ${esc(it.uom)}</span></div>
        <button class="btn-o btn-sm btn-danger" data-action="cart-del" data-code="${esc(c)}">✕</button></div>
      <div class="sb" style="margin-top:8px">
        <div class="step">
          <button data-action="cart-step" data-code="${esc(c)}" data-dir="-1">−</button>
          <input type="number" min="1" value="${it.qty}" data-cartqty="${esc(c)}">
          <button data-action="cart-step" data-code="${esc(c)}" data-dir="1">+</button>
        </div>
        <b>${vnd(it.qty*it.rate)}</b></div>
    </div>`;
  }).join('');

  const today = new Date();
  const d2 = new Date(today.getTime() + 2*86400000);
  const defDate = d2.toISOString().slice(0,10);

  const addresses = (MP.me && MP.me.addresses) || [];
  const addrField = addresses.length ? `
    <div class="field"><label>Địa chỉ giao hàng</label>
      <select id="f-addr">${addresses.map(a=>`<option value="${esc(a.name)}">${esc(a.display)}</option>`).join('')}</select></div>` : '';

  el(box).innerHTML = `
    ${topbar('Giỏ hàng & xác nhận đơn', MP.contract || '')}
    <div class="grid2">
      <div>
        <div class="card flush only-desktop">
          <table><thead><tr><th>Mặt hàng</th><th>ĐVT</th><th class="right">Đơn giá</th>
            <th style="width:90px">SL</th><th class="right">Thành tiền</th><th></th></tr></thead>
          <tbody>${tableRows}</tbody></table>
        </div>
        <div class="only-mobile">${cards}</div>
      </div>
      <div>
        <div class="card">
          <div class="field"><label>Ngày giao mong muốn</label><input type="date" id="f-date" value="${defDate}"></div>
          ${addrField}
          <div class="field"><label>Số dự trù / PO của đơn vị</label><input id="f-po" placeholder="VD: DT-2026-0715"></div>
          <div class="field"><label>Ghi chú</label><textarea id="f-note" rows="2" placeholder="Yêu cầu giao giờ hành chính..."></textarea></div>
        </div>
        <div class="card">
          <div class="sb"><span>Tạm tính</span><b id="t-sub">${vnd(sub)}</b></div>
          <div class="sb" style="margin-top:6px"><span>VAT</span><b id="t-vat">${vnd(vat)}</b></div>
          <hr>
          <div class="sb" style="font-size:17px"><b>Tổng cộng</b><b id="t-tot" style="color:var(--blue)">${vnd(tot)}</b></div>
          <button class="btn btn-block" style="margin-top:14px" data-action="confirm-open">Xác nhận đặt hàng →</button>
          <p class="tag" style="margin-top:8px">Đơn sẽ được gửi về hệ thống Supplycore và tạo Đơn bán hàng (Sales Order) chờ Miyano xác nhận.</p>
        </div>
      </div>
    </div>`;
}
function recomputeCartTotals(){
  const { sub, vat, tot } = totals();
  if(el('t-sub')) el('t-sub').textContent = vnd(sub);
  if(el('t-vat')) el('t-vat').textContent = vnd(vat);
  if(el('t-tot')) el('t-tot').textContent = vnd(tot);
}
function cartStep(code, dir){
  if(!MP.cart[code]) return;
  const it = MP.cart[code];
  let q = Math.max(1, it.qty + dir);
  if(q > it.remaining){ alert(`Vượt hạn mức: chỉ còn ${it.remaining} ${it.uom}.`); q = it.remaining; }
  it.qty = q;
  viewCart(); refreshCartBadges();
}
function cartSetQty(code, val){
  if(!MP.cart[code]) return;
  const it = MP.cart[code];
  let q = Math.max(1, parseInt(val)||1);
  if(q > it.remaining){ alert(`Vượt hạn mức: chỉ còn ${it.remaining} ${it.uom}.`); q = it.remaining; }
  it.qty = q;
  viewCart(); refreshCartBadges();
}
function cartDel(code){ delete MP.cart[code]; viewCart(); refreshCartBadges(); }

/* ---- confirm modal / sheet ---- */
function openConfirm(){
  if(!Object.keys(MP.cart).length){ alert('Giỏ hàng trống.'); return; }
  el('m-contract').textContent = MP.contract || '';
  el('m-tot').textContent = vnd(totals().tot);
  el('m-err').textContent = '';
  el('modal').classList.add('show');
}
function closeConfirm(){ el('modal').classList.remove('show'); }
async function confirmOrder(){
  const btn = el('m-confirm');
  btn.disabled = true; btn.textContent = 'Đang gửi…';
  try{
    const items = Object.keys(MP.cart).map(c=>({item_code:c, qty:MP.cart[c].qty}));
    const res = await call("portal_order_place", {
      contract: MP.contract,
      items: JSON.stringify(items),
      po: el('f-po') ? el('f-po').value : '',
      delivery_date: el('f-date') ? el('f-date').value : '',
      note: el('f-note') ? el('f-note').value : '',
      address: el('f-addr') ? el('f-addr').value : '',
    });
    MP.cart = {};
    MP.lastOrder = res.sales_order;
    MP.lastTotal = res.total;
    MP.history = null;
    closeConfirm();
    refreshCartBadges();
    go('done');
  }catch(e){
    el('m-err').textContent = (e && e.message) || 'Lỗi đặt hàng.';
  }finally{
    btn.disabled = false; btn.textContent = 'Xác nhận đặt hàng';
  }
}

/* ==========================================================================
   S-05 SUCCESS
   ========================================================================== */
function viewDone(){
  const code = MP.lastOrder || '';
  el('pg-done').innerHTML = `
    <div class="card" style="max-width:560px;margin:24px auto;text-align:center;padding:34px 20px">
      <div style="font-size:52px">✅</div>
      <h2 style="margin:10px 0 6px">Đặt hàng thành công!</h2>
      <p>Đơn hàng của quý khách đã được gửi về hệ thống Supplycore.</p>
      <p style="margin:16px 0;font-size:17px">Mã đơn: <b style="color:var(--blue)">${esc(code)}</b>
        <span class="badge b-gray">Chờ xác nhận</span></p>
      ${MP.lastTotal!=null?`<p>Tổng giá trị: <b>${vnd(MP.lastTotal)}</b></p>`:''}
      <p class="tag" style="margin-top:8px">Nhân viên Miyano sẽ kiểm tra và xác nhận trong giờ làm việc.</p>
      <div class="flex" style="justify-content:center;margin-top:20px;flex-wrap:wrap">
        <button class="btn-o" data-action="go" data-page="orders">Xem đơn hàng</button>
        <button class="btn" data-action="go" data-page="cat">Tiếp tục đặt hàng</button>
      </div>
    </div>`;
}

/* ==========================================================================
   S-06 ORDERS
   ========================================================================== */
async function viewOrders(){
  const box = 'pg-orders';
  el(box).innerHTML = `<p class="muted">Đang tải…</p>`;
  try{
    const rows = await call("portal_order_history", {limit:100});
    MP.history = rows;
    if(!rows.length){
      el(box).innerHTML = topbar('Đơn hàng của tôi','') + `<div class="card"><p class="muted">Chưa có đơn hàng nào.</p></div>`;
      return;
    }
    const canCancel = s => s === "Chờ xác nhận";
    const pctDel = r => pct((Number(r.per_delivered)||0));

    const tableRows = rows.map(r=>{
      const act = canCancel(r.status_vi)
        ? `<button class="btn-o btn-sm" data-action="cancel" data-order="${esc(r.name)}">Huỷ/Sửa</button>`
        : `<button class="btn-o btn-sm" data-action="detail" data-order="${esc(r.name)}">Chi tiết</button>`;
      return `<tr>
        <td><b>${esc(r.name)}</b></td>
        <td>${esc(dvn(r.transaction_date))}</td>
        <td class="right">${vnd(r.grand_total)}</td>
        <td>${pctDel(r)}%</td>
        <td><span class="badge ${badgeClass(r.status_vi)}">${esc(r.status_vi)}</span></td>
        <td>${act}</td></tr>`;
    }).join('');

    const cards = rows.map(r=>{
      const showBar = pctDel(r) > 0 && r.status_vi !== "Đã huỷ";
      const act = canCancel(r.status_vi)
        ? `<button class="btn-o btn-sm" data-action="cancel" data-order="${esc(r.name)}" style="margin-top:8px">Huỷ / Sửa đơn</button>`
        : '';
      return `<div class="card" ${canCancel(r.status_vi)?'':`data-action="detail" data-order="${esc(r.name)}" style="cursor:pointer"`}>
        <div class="sb"><b>${esc(r.name)}</b><span class="badge ${badgeClass(r.status_vi)}">${esc(r.status_vi)}</span></div>
        <p class="tag" style="margin-top:4px">Đặt ${esc(dvn(r.transaction_date))} · ${vnd(r.grand_total)}</p>
        ${showBar?`<p style="font-size:12px;margin-top:6px">Đã giao <b>${pctDel(r)}%</b></p><div class="bar"><i class="orange" style="width:${pctDel(r)}%"></i></div>`:''}
        ${act}</div>`;
    }).join('');

    el(box).innerHTML = `
      ${topbar('Đơn hàng của tôi', 'Toàn bộ đơn hàng của đơn vị')}
      <div class="card flush only-desktop">
        <table><thead><tr><th>Mã đơn</th><th>Ngày đặt</th><th class="right">Giá trị</th><th>Đã giao</th><th>Trạng thái</th><th></th></tr></thead>
        <tbody>${tableRows}</tbody></table></div>
      <div class="only-mobile">${cards}</div>`;
  }catch(e){ showError(box, e); }
}
async function requestCancel(order){
  const reason = prompt("Lý do yêu cầu huỷ / sửa đơn " + order + ":");
  if(reason==null) return;
  try{
    await call("portal_request_cancel", {order, reason: reason || "Khách yêu cầu huỷ/sửa"});
    alert("Đã gửi yêu cầu huỷ/sửa tới Miyano. Nhân viên sẽ liên hệ lại.");
  }catch(e){ alert((e && e.message) || "Không gửi được yêu cầu."); }
}

/* ==========================================================================
   S-07 ORDER DETAIL
   ========================================================================== */
async function viewDetail(){
  const box = 'pg-detail';
  el(box).innerHTML = `<p class="muted">Đang tải…</p>`;
  if(!MP.currentOrder){ go('orders'); return; }
  try{
    const t = await call("portal_order_track", {order: MP.currentOrder});
    // Derive the "current" step = first not-done milestone (API gives 4
    // milestones with booleans and no explicit current pointer).
    const ms = t.milestones || [];
    let curIdx = ms.findIndex(m=>!m.done);
    if(curIdx === -1) curIdx = ms.length; // all done

    // horizontal timeline (desktop)
    const htl = ms.map((m,i)=>{
      const cls = m.done ? 'done' : (i===curIdx ? 'cur' : '');
      return `<div class="st ${cls}"><div class="dot">${m.done?'✓':(i+1)}</div><div class="lb">${esc(m.label)}</div></div>`;
    }).join('');
    // vertical timeline (mobile)
    const vtl = ms.map((m,i)=>{
      const cls = m.done ? 'done' : (i===curIdx ? 'cur' : '');
      return `<div class="vst ${cls}"><div class="vdot">${m.done?'✓':(i+1)}</div><div class="vlb"><b>${esc(m.label)}</b>${m.done?'Hoàn tất':(i===curIdx?'Đang xử lý':'Chưa tới')}</div></div>`;
    }).join('');

    const itemRowsD = (t.items||[]).map(it=>`
      <tr><td><b>${esc(it.item_code)}</b></td>
        <td>${esc(it.uom||'')}</td>
        <td class="right">${esc(it.qty)}</td>
        <td class="right">${esc(it.delivered_qty)}</td>
        <td class="right">${vnd(it.rate)}</td>
        <td class="right">${vnd(it.amount)}</td></tr>`).join('');
    const itemCardsM = (t.items||[]).map(it=>`
      <div class="rowline"><span><b>${esc(it.item_code)}</b><br><span class="tag">${esc(it.qty)} ${esc(it.uom||'')} × ${vnd(it.rate)} · đã giao ${esc(it.delivered_qty)}</span></span><b>${vnd(it.amount)}</b></div>`).join('');

    // Deliveries ("đợt giao") block from portal_order_track.deliveries
    const deliveries = t.deliveries || [];
    const delivHtml = deliveries.length ? deliveries.map((d,i)=>`
      <p style="font-size:13px;margin-top:${i?'10px':'0'}"><b>Đợt ${i+1} – ${esc(dvn(d.posting_date))}${d.percent?` (${esc(d.percent)}%)`:''}</b></p>
      <p class="tag">Phiếu giao: ${esc(d.name)}${d.carrier?` · ${esc(d.carrier)}`:''}${d.awb?` · Vận đơn: ${esc(d.awb)}`:''}</p>
      <a class="btn-o btn-sm" style="margin:6px 0" href="${esc(pdfHref("Delivery Note", d.name))}" target="_blank" rel="noopener">⬇ Phiếu giao đợt ${i+1}</a>`).join('')
      : `<p class="tag">Chưa có phiếu giao hàng nào cho đơn này.</p>`;

    const subParts = [
      t.order_date ? 'Đặt ngày ' + dvn(t.order_date) : '',
      t.hdnt ? 'HĐNT ' + t.hdnt : '',
      t.po_khach ? 'Số dự trù: ' + t.po_khach : '',
    ].filter(Boolean).join(' · ');

    const pdf = pdfHref("Sales Order", t.order);
    el(box).innerHTML = `
      ${topbar('Đơn hàng ' + t.order, subParts, `
        <a class="btn-o btn-sm only-desktop" href="${esc(pdf)}" target="_blank" rel="noopener">⬇ PDF đơn hàng</a>
        <button class="btn-o btn-sm only-desktop" data-action="go" data-page="orders">← Quay lại</button>`)}
      <div class="card" style="margin-bottom:8px"><span class="badge ${badgeClass(t.status_vi)}">${esc(t.status_vi)}</span></div>
      <div class="card only-desktop"><div class="tl">${htl}</div></div>
      <div class="card only-mobile"><h3 style="margin-bottom:8px">Tiến trình</h3><div class="vtl">${vtl}</div></div>
      <div class="grid2">
        <div>
          <div class="card flush only-desktop">
            <table><thead><tr><th>Mặt hàng</th><th>ĐVT</th><th class="right">SL đặt</th><th class="right">Đã giao</th><th class="right">Đơn giá</th><th class="right">Thành tiền</th></tr></thead>
            <tbody>${itemRowsD||'<tr><td colspan="6" class="muted">Không có dòng hàng.</td></tr>'}</tbody></table>
          </div>
          <div class="card only-mobile"><h3 style="margin-bottom:6px">Mặt hàng</h3>${itemCardsM||'<p class="muted">Không có dòng hàng.</p>'}</div>
        </div>
        <div>
          <div class="card"><h3 style="margin-bottom:10px">Giao hàng</h3>${delivHtml}</div>
          <div class="card">
            <h3 style="margin-bottom:10px">Chứng từ</h3>
            <a class="btn-o btn-sm btn-block" href="${esc(pdf)}" target="_blank" rel="noopener">⬇ PDF đơn hàng</a>
            <a class="btn-o btn-sm btn-block only-mobile" style="margin-top:8px" data-action="go" data-page="orders">← Quay lại danh sách</a>
          </div>
        </div>
      </div>`;
  }catch(e){ showError(box, e); }
}

/* ==========================================================================
   S-08 INVOICES
   ========================================================================== */
async function viewInvoices(){
  const box = 'pg-inv';
  el(box).innerHTML = `<p class="muted">Đang tải…</p>`;
  try{
    const [me, rows] = await Promise.all([ getMe(), call("portal_invoices", {limit:100}) ]);
    // KPI computations from outstanding_amount + due_date
    let overdue = 0, dueSoon = 0;
    rows.forEach(r=>{
      const out = Number(r.outstanding_amount)||0;
      if(out <= 0) return;
      const d = daysUntil(r.due_date);
      if(d!=null && d < 0) overdue += out;
      else if(d!=null && d <= 7) dueSoon += 1;
    });

    const tableRows = rows.length ? rows.map(r=>{
      const paid = Number(r.grand_total) - Number(r.outstanding_amount);
      return `<tr>
        <td><b>${esc(r.name)}</b></td>
        <td>${esc(dvn(r.posting_date))}</td>
        <td>${esc(dvn(r.due_date))}</td>
        <td class="right">${vnd(r.grand_total)}</td>
        <td class="right">${vnd(paid)}</td>
        <td><span class="badge ${invBadge(r.status_vi)}">${esc(r.status_vi)}</span></td>
        <td><a class="btn-o btn-sm" href="${esc(pdfHref("Sales Invoice", r.name))}" target="_blank" rel="noopener">⬇ PDF</a></td></tr>`;
    }).join('') : `<tr><td colspan="7" class="muted">Chưa có hoá đơn nào.</td></tr>`;

    const cards = rows.length ? rows.map(r=>{
      const paid = Number(r.grand_total) - Number(r.outstanding_amount);
      return `<div class="card">
        <div class="sb"><b>${esc(r.name)}</b><span class="badge ${invBadge(r.status_vi)}">${esc(r.status_vi)}</span></div>
        <p class="tag" style="margin-top:4px">${esc(dvn(r.posting_date))} · Hạn TT ${esc(dvn(r.due_date))}${paid>0?` · Đã TT ${vnd(paid)}`:''}</p>
        <div class="sb" style="margin-top:6px"><b style="font-size:15px">${vnd(r.grand_total)}</b>
          <a class="btn-o btn-sm" href="${esc(pdfHref("Sales Invoice", r.name))}" target="_blank" rel="noopener">⬇ PDF</a></div>
      </div>`;
    }).join('') : `<div class="card"><p class="muted">Chưa có hoá đơn nào.</p></div>`;

    el(box).innerHTML = `
      ${topbar('Hoá đơn & công nợ', me.customer_name || '')}
      <div class="kpis">
        <div class="card kpi"><div class="n" style="color:var(--red)">${vndShort(me.outstanding)}</div><div class="t">Tổng công nợ hiện tại</div></div>
        <div class="card kpi"><div class="n" style="color:var(--orange)">${vndShort(overdue)}</div><div class="t">Quá hạn thanh toán</div></div>
        <div class="card kpi"><div class="n">${dueSoon}</div><div class="t">Hoá đơn đến hạn trong 7 ngày</div></div>
      </div>
      <div class="card flush only-desktop">
        <table><thead><tr><th>Số hoá đơn</th><th>Ngày</th><th>Hạn TT</th><th class="right">Giá trị</th><th class="right">Đã thanh toán</th><th>Trạng thái</th><th></th></tr></thead>
        <tbody>${tableRows}</tbody></table></div>
      <div class="only-mobile">${cards}</div>`;
  }catch(e){ showError(box, e); }
}

/* ==========================================================================
   S-09 PROFILE
   ========================================================================== */
async function viewProfile(){
  const box = 'pg-prof';
  el(box).innerHTML = `<p class="muted">Đang tải…</p>`;
  try{
    const [me, contracts] = await Promise.all([ getMe(), getContracts() ]);
    const contractRowsD = contracts.length ? contracts.map(c=>`
      <tr><td><b>${esc(c.name)}</b></td>
        <td>${esc(dvn(c.from_date))} – ${esc(dvn(c.to_date))}</td>
        <td>${c.item_count!=null?esc(c.item_count):'–'}</td>
        <td>${pct(c.used_pct)}% <div class="bar"><i style="width:${pct(c.used_pct)}%" class="${pct(c.used_pct)>=80?'hot':''}"></i></div></td></tr>`).join('')
      : `<tr><td colspan="4" class="muted">Chưa có hợp đồng nguyên tắc.</td></tr>`;
    const contractCardsM = contracts.length ? contracts.map(c=>`
      <div class="rowline"><span><b>${esc(c.name)}</b><br><span class="tag">${esc(dvn(c.from_date))} – ${esc(dvn(c.to_date))}${c.item_count!=null?` · ${esc(c.item_count)} mặt hàng`:''}</span></span>
        <span style="min-width:90px;text-align:right;font-size:12px">${pct(c.used_pct)}%<div class="bar"><i style="width:${pct(c.used_pct)}%" class="${pct(c.used_pct)>=80?'hot':''}"></i></div></span></div>`).join('')
      : `<p class="muted">Chưa có hợp đồng nguyên tắc.</p>`;

    const addresses = me.addresses || [];
    const addrHtml = addresses.length
      ? addresses.map(a=>`<p style="font-size:13px">• ${esc(a.display)}</p>`).join('')
      : `<p class="muted" style="font-size:13px">Chưa có địa chỉ giao hàng.</p>`;

    el(box).innerHTML = `
      ${topbar('Hồ sơ đơn vị', 'Thông tin do Miyano quản lý – liên hệ sales để cập nhật')}
      <div class="grid2">
        <div class="card">
          <h3 style="margin-bottom:6px">${esc(me.customer_name || me.customer)}</h3>
          <p class="tag">${me.tax_id?`MST: ${esc(me.tax_id)} · `:''}Mã đơn vị: ${esc(me.customer)}</p>
          <h4 style="margin:16px 0 8px">Hợp đồng nguyên tắc</h4>
          <div class="only-desktop"><table><thead><tr><th>Số HĐ</th><th>Hiệu lực</th><th>Mặt hàng</th><th>Hạn mức đã dùng</th></tr></thead>
            <tbody>${contractRowsD}</tbody></table></div>
          <div class="only-mobile">${contractCardsM}</div>
        </div>
        <div class="card">
          <h4 style="margin-bottom:8px">Người dùng portal</h4>
          <p style="font-size:13px">👤 ${esc(me.customer_name || '')}<br><span class="tag">Bạn đang đăng nhập</span></p>
          <h4 style="margin:16px 0 8px">Địa chỉ giao hàng</h4>
          ${addrHtml}
          <h4 style="margin:16px 0 8px">Công nợ</h4>
          <p style="font-size:13px">Tổng công nợ hiện tại: <b style="color:var(--red)">${vnd(me.outstanding)}</b></p>
          <button class="btn-o btn-sm btn-block" style="margin-top:10px" data-action="go" data-page="inv">Xem hoá đơn &amp; công nợ →</button>
          <h4 style="margin:16px 0 8px">Đăng xuất</h4>
          <a class="btn-o btn-sm btn-block btn-danger" href="/api/method/logout">Đăng xuất</a>
        </div>
      </div>`;
  }catch(e){ showError(box, e); }
}

/* ==========================================================================
   EVENT DISPATCH (delegated; keeps untrusted values off inline handlers)
   ========================================================================== */
document.addEventListener('click', (ev)=>{
  const t = ev.target.closest('[data-action]');
  if(!t) return;
  const a = t.dataset.action;
  switch(a){
    case 'go':            ev.preventDefault(); go(t.dataset.page); break;
    case 'back':          goBack(); break;
    case 'add':           addToCart(t.dataset.code); break;
    case 'chip':
      MP.catGroup = t.dataset.group || "";
      document.querySelectorAll('#cat-chips .chip').forEach(c=>c.classList.toggle('on', c===t));
      renderCatList();
      break;
    case 'step':          catStep(t.dataset.code, parseInt(t.dataset.dir)); break;
    case 'cart-step':     cartStep(t.dataset.code, parseInt(t.dataset.dir)); break;
    case 'cart-del':      cartDel(t.dataset.code); break;
    case 'detail':        MP.currentOrder = t.dataset.order; go('detail'); break;
    case 'cancel':        requestCancel(t.dataset.order); break;
    case 'confirm-open':  openConfirm(); break;
    case 'confirm-do':    confirmOrder(); break;
    case 'confirm-close': closeConfirm(); break;
    default: break;
  }
});
// close the confirm overlay when tapping the dim backdrop
el('modal').addEventListener('click', (ev)=>{ if(ev.target===el('modal')) closeConfirm(); });

document.addEventListener('input', (ev)=>{
  const t = ev.target;
  if(t.dataset && t.dataset.action==='cat-search'){ MP.catFilter = t.value; renderCatList(); }
});
document.addEventListener('change', (ev)=>{
  const t = ev.target;
  if(t.id==='cat-contract'){ MP.contract = t.value; MP.cart = {}; refreshCartBadges(); viewCatalog(); return; }
  if(t.dataset && t.dataset.cartqty!=null){ cartSetQty(t.dataset.cartqty, t.value); }
});

/* ---------------------------------------------------------------- boot */
go('dash');
