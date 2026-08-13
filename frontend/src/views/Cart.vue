<script setup>
// E6/F-04 [MỚI — BR-R2] — Giỏ HAI NGĂN: "Theo HĐNT" ([Hiện có], không đổi
// hành vi) và "Mua lẻ" ([MỚI]). Mỗi ngăn có bảng dòng/tổng tiền/nút xác nhận
// RIÊNG và đặt thành MỘT Sales Order riêng (`portal_order_place(mode=...)`).
//
// Cố ý giữ HAI khối trạng thái/hàm TÁCH RIÊNG (không gộp thành một hàm nhận
// tham số "ngăn nào") — cùng lý do backend tách `_xay_don_hdnt`/
// `_xay_don_ban_le` thay vì viết một hàm chung: ngăn HĐNT không được đổi
// một dòng hành vi nào so với bản đã chạy thật, viết một lớp trừu tượng
// dùng chung cho cả hai sẽ buộc phải đọc lại và có nguy cơ sửa nhầm nhánh
// đã ổn định chỉ để phục vụ nhánh mới.
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api'
import { store } from '../store'
import { fmtVND, addWorkDaysISO, todayISO } from '../format'
import { useIsMobile } from '../useMobile'
import { showToast } from '../toast'

const router = useRouter()
const isMobile = useIsMobile()

const addresses = computed(() => store.me?.addresses || [])

// Tab đang xem — mặc định mở ngăn nào đang có hàng; còn cả hai trống hoặc cả
// hai đều có hàng thì mặc định Theo HĐNT (ngăn [Hiện có]).
const tab = ref(store.cartLines.length === 0 && store.cartLeLines.length > 0 ? 'le' : 'hd')
// Tab "Mua lẻ" chỉ hiện khi ngăn đó ĐANG CÓ hàng. Một khách không được bật
// mua lẻ không bao giờ đưa được hàng vào `cartLe` (Catalog.vue chặn từ
// nguồn — nút "+ Giỏ lẻ" chỉ tồn tại sau khi `portal_catalog_ban_le` xác
// nhận quyền), nên "có hàng trong cartLe" và "được phép mua lẻ" là một —
// dùng điều kiện rẻ hơn (không cần gọi lại API chỉ để dò quyền lần nữa).
const hienTabLe = computed(() => store.cartLeLines.length > 0 || tab.value === 'le')

// ================= NGĂN THEO HĐNT [Hiện có] =================
const hdLines = computed(() => store.cartLines)
const hdEmpty = computed(() => hdLines.value.length === 0)
const hdDeliveryDate = ref(addWorkDaysISO(2)) // BR-O13
const ngayGiaoToiThieu = todayISO()
const hdAddress = ref('')
const hdPo = ref('')
const hdNote = ref('')
const hdConfirmOpen = ref(false)
const hdPlacing = ref(false)
const hdError = ref('')
const hdLoiDong = ref([])
const hdMaLoi = computed(() => new Set(hdLoiDong.value.map((d) => d.item_code).filter(Boolean)))
const hdPlacedOrder = ref(null)

function hdStepDown(code, qty) {
  store.setQty(code, qty - 1)
}
function hdStepUp(line) {
  const max = line.remaining || Infinity
  store.setQty(line.item_code, Math.min(max, line.qty + 1))
}
function hdQtyInput(line, e) {
  let v = Math.max(1, parseInt(e.target.value) || 1)
  if (line.remaining) v = Math.min(line.remaining, v)
  store.setQty(line.item_code, v)
  e.target.value = v
}
function hdMoXacNhan() {
  store.moModalXacNhan()
  hdConfirmOpen.value = true
}
async function hdConfirmOrder() {
  if (hdPlacing.value) return
  hdPlacing.value = true
  hdError.value = ''
  hdLoiDong.value = []
  try {
    const itemsPayload = hdLines.value.map((l) => ({ item_code: l.item_code, qty: l.qty }))
    const res = await api.call('portal_order_place', {
      contract: store.contract,
      items: JSON.stringify(itemsPayload),
      po: hdPo.value || null,
      delivery_date: hdDeliveryDate.value || null,
      note: hdNote.value || null,
      address: hdAddress.value || null,
      request_id: store.requestId,
      mode: 'hdnt',
    })
    if (res.da_ton_tai) {
      showToast(`Đơn ${res.sales_order} đã được tạo trước đó.`)
    }
    hdPlacedOrder.value = res
    store.clearCart()
    store.ketThucDatHang()
    hdConfirmOpen.value = false
  } catch (e) {
    if (e.loi && e.loi.length) {
      hdLoiDong.value = e.loi
    } else {
      hdError.value = e.message || 'Không thể đặt hàng. Vui lòng thử lại.'
    }
    hdConfirmOpen.value = false
  } finally {
    hdPlacing.value = false
  }
}

// ================= NGĂN MUA LẺ [MỚI] =================
const leLines = computed(() => store.cartLeLines)
const leEmpty = computed(() => leLines.value.length === 0)
const leDeliveryDate = ref(addWorkDaysISO(2))
const leAddress = ref('')
const lePo = ref('')
const leNote = ref('')
const leConfirmOpen = ref(false)
const lePlacing = ref(false)
const leError = ref('')
const leLoiDong = ref([])
const leMaLoi = computed(() => new Set(leLoiDong.value.map((d) => d.item_code).filter(Boolean)))
const lePlacedOrder = ref(null)

function leStepDown(code, qty) {
  store.setQtyLe(code, qty - 1)
}
function leStepUp(line) {
  store.setQtyLe(line.item_code, line.qty + 1)
}
function leQtyInput(line, e) {
  const v = Math.max(1, parseInt(e.target.value) || 1)
  store.setQtyLe(line.item_code, v)
  e.target.value = v
}
function leMoXacNhan() {
  store.moModalXacNhanLe()
  leConfirmOpen.value = true
}
async function leConfirmOrder() {
  if (lePlacing.value) return
  lePlacing.value = true
  leError.value = ''
  leLoiDong.value = []
  try {
    const itemsPayload = leLines.value.map((l) => ({ item_code: l.item_code, qty: l.qty }))
    const res = await api.call('portal_order_place', {
      items: JSON.stringify(itemsPayload),
      po: lePo.value || null,
      delivery_date: leDeliveryDate.value || null,
      note: leNote.value || null,
      address: leAddress.value || null,
      request_id: store.requestIdLe,
      mode: 'ban_le',
    })
    if (res.da_ton_tai) {
      showToast(`Đơn ${res.sales_order} đã được tạo trước đó.`)
    }
    lePlacedOrder.value = res
    store.clearCartLe()
    store.ketThucDatHangLe()
    leConfirmOpen.value = false
  } catch (e) {
    if (e.loi && e.loi.length) {
      leLoiDong.value = e.loi
    } else {
      leError.value = e.message || 'Không thể đặt hàng. Vui lòng thử lại.'
    }
    leConfirmOpen.value = false
  } finally {
    lePlacing.value = false
  }
}

onMounted(async () => {
  // Đảm bảo có địa chỉ giao + hợp đồng khi vào thẳng /cart (reload mất store).
  try {
    if (!store.me) store.setMe(await api.call('portal_me'))
    const macDinh = (store.me?.addresses || [])[0]?.name || ''
    if (hdAddress.value === '') hdAddress.value = macDinh
    if (leAddress.value === '') leAddress.value = macDinh
    if (!store.contract && !hdEmpty.value) {
      const cs = (await api.call('portal_contracts')) || []
      if (cs.length) store.setContract(cs[0].name)
    }
  } catch (e) {
    /* không chặn hiển thị giỏ */
  }
})
</script>

<template>
  <div>
    <div class="topbar" v-if="!isMobile">
      <div>
        <h2>Giỏ hàng &amp; xác nhận đơn</h2>
        <div class="sub">{{ store.me?.customer_name || '' }}</div>
      </div>
    </div>

    <!-- `hdPlacedOrder`/`lePlacedOrder` PHẢI loại trừ khỏi điều kiện rỗng:
         xác nhận xong thì `store.clearCart()`/`clearCartLe()` làm đúng ngăn
         đó rỗng NGAY LẬP TỨC — thiếu vế loại trừ này thì màn "Đặt hàng
         thành công!" biến mất chỉ sau một nhịp render, thay bằng thông điệp
         "Giỏ hàng trống" (server đã tạo đơn thành công, nhưng khách không
         còn thấy xác nhận). -->
    <div v-if="hdEmpty && leEmpty && !hdPlacedOrder && !lePlacedOrder" class="card" style="color: var(--gray)">
      Giỏ hàng trống – vào mục
      <a href="#" style="color: var(--blue2)" @click.prevent="router.push('/catalog')">Đặt hàng</a>
      để chọn mặt hàng.
    </div>

    <template v-else>
      <div class="tabs">
        <button :class="{ on: tab === 'hd' }" @click="tab = 'hd'">Theo HĐNT ({{ hdLines.length }})</button>
        <button v-if="hienTabLe" :class="{ on: tab === 'le' }" @click="tab = 'le'">
          Mua lẻ ({{ leLines.length }}) <span class="newtag">MỚI</span>
        </button>
      </div>

      <!-- ============ NGĂN THEO HĐNT ============ -->
      <div v-show="tab === 'hd'">
        <!-- Thành công -->
        <div v-if="hdPlacedOrder" class="card success">
          <div style="font-size: 52px">✅</div>
          <h2 style="margin: 10px 0 6px">Đặt hàng thành công!</h2>
          <p style="margin: 14px 0; font-size: 17px">
            Mã đơn: <b style="color: var(--blue)">{{ hdPlacedOrder.sales_order }}</b>
            <span class="badge b-gray">Chờ xác nhận</span>
          </p>
          <p class="tag">Nhân viên Miyano sẽ kiểm tra và xác nhận trong giờ làm việc.</p>
          <div class="flex" style="justify-content: center; margin-top: 20px; flex-wrap: wrap">
            <button class="btn-o" @click="router.push('/orders')">Xem đơn hàng</button>
            <button class="btn" @click="hdPlacedOrder = null; router.push('/catalog')">Tiếp tục đặt hàng</button>
          </div>
        </div>

        <div v-else-if="hdEmpty" class="card" style="color: var(--gray)">
          Ngăn Theo HĐNT trống —
          <a href="#" style="color: var(--blue2)" @click.prevent="router.push('/catalog')">chọn thêm mặt hàng</a>.
        </div>

        <template v-else>
          <div v-if="hdError" class="note" style="color: var(--red); border-color: #fecaca; background: #fef2f2">{{ hdError }}</div>
          <div v-if="hdLoiDong.length" class="note note-loi">
            <b>Chưa gửi được đơn — cần sửa {{ hdLoiDong.length }} mục:</b>
            <ul class="ds-loi"><li v-for="(d, i) in hdLoiDong" :key="i">{{ d.thong_diep }}</li></ul>
          </div>

          <div class="grid2">
            <div>
              <div v-if="!isMobile" class="card" style="padding: 0; overflow-x: auto">
                <table>
                  <thead>
                    <tr>
                      <th>MÃ</th><th>TÊN VẬT TƯ</th><th>ĐVT</th><th class="right">Đơn giá</th>
                      <th style="width: 120px">SL</th><th class="right">Thành tiền</th><th></th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="l in hdLines" :key="l.item_code" :class="{ 'dong-loi': hdMaLoi.has(l.item_code) }">
                      <td><b>{{ l.item_code }}</b></td>
                      <td>{{ l.item_name }}</td>
                      <td>{{ l.uom }}</td>
                      <td class="right">{{ fmtVND(l.rate) }}</td>
                      <td>
                        <div class="step">
                          <button @click="hdStepDown(l.item_code, l.qty)">−</button>
                          <input :value="l.qty" @change="hdQtyInput(l, $event)" inputmode="numeric" />
                          <button @click="hdStepUp(l)">+</button>
                        </div>
                      </td>
                      <td class="right"><b>{{ fmtVND(l.qty * l.rate) }}</b></td>
                      <td><button class="btn-o btn-sm" style="color: var(--red); border-color: var(--red)" @click="store.removeFromCart(l.item_code)">✕</button></td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <template v-else>
                <div v-for="l in hdLines" :key="l.item_code" class="card mb10" :class="{ 'dong-loi': hdMaLoi.has(l.item_code) }">
                  <div class="sb">
                    <span><b>{{ l.item_code }}</b><br /><span style="font-size: 13px">{{ l.item_name }}</span></span>
                    <button class="btn-o btn-sm" style="color: var(--red); border-color: var(--red)" @click="store.removeFromCart(l.item_code)">✕</button>
                  </div>
                  <div class="tag" style="margin: 4px 0 8px">{{ fmtVND(l.rate) }} / {{ l.uom }}</div>
                  <div class="sb">
                    <div class="step">
                      <button @click="hdStepDown(l.item_code, l.qty)">−</button>
                      <input :value="l.qty" @change="hdQtyInput(l, $event)" inputmode="numeric" />
                      <button @click="hdStepUp(l)">+</button>
                    </div>
                    <b class="pr">{{ fmtVND(l.qty * l.rate) }}</b>
                  </div>
                </div>
              </template>
            </div>

            <div>
              <div class="card mb10" style="margin-bottom: 14px">
                <div class="h3">Thông tin giao hàng</div>
                <div class="field"><label>Ngày giao mong muốn</label><input type="date" v-model="hdDeliveryDate" :min="ngayGiaoToiThieu" /></div>
                <div class="field">
                  <label>Địa chỉ giao hàng</label>
                  <select v-model="hdAddress"><option v-for="a in addresses" :key="a.name" :value="a.name">{{ a.display }}</option></select>
                </div>
                <div class="field"><label>Số dự trù / PO của đơn vị</label><input v-model="hdPo" placeholder="VD: DT-2026-0715" /></div>
                <div class="field"><label>Ghi chú</label><textarea rows="2" v-model="hdNote" placeholder="Yêu cầu giao giờ hành chính..."></textarea></div>
              </div>
              <div class="card">
                <div class="sb"><span>Tạm tính</span><b>{{ fmtVND(store.cartSubtotal) }}</b></div>
                <div class="sb" style="margin-top: 6px"><span>VAT (5–8%)</span><b>{{ fmtVND(store.cartVat) }}</b></div>
                <hr class="sep" />
                <div class="sb" style="font-size: 17px"><span><b>Tổng cộng</b></span><b style="color: var(--blue)">{{ fmtVND(store.cartTotal) }}</b></div>
                <button class="btn" style="width: 100%; margin-top: 14px" @click="hdMoXacNhan">Xác nhận đặt hàng →</button>
                <p class="tag" style="margin-top: 8px">Đơn sẽ được gửi về hệ thống Supplycore và tạo Đơn bán hàng (Sales Order) chờ Miyano xác nhận.</p>
              </div>
            </div>
          </div>
        </template>
      </div>

      <!-- ============ NGĂN MUA LẺ [MỚI] ============ -->
      <div v-show="tab === 'le'">
        <div v-if="lePlacedOrder" class="card success">
          <div style="font-size: 52px">✅</div>
          <h2 style="margin: 10px 0 6px">Đặt đơn mua lẻ thành công!</h2>
          <p style="margin: 14px 0; font-size: 17px">
            Mã đơn: <b style="color: var(--purple)">{{ lePlacedOrder.sales_order }}</b>
            <span class="badge b-gray">Chờ xác nhận</span>
          </p>
          <p class="tag">Đơn ngoài HĐNT — Miyano sẽ xác nhận giá và lượng trước khi giao.</p>
          <div class="flex" style="justify-content: center; margin-top: 20px; flex-wrap: wrap">
            <button class="btn-o" @click="router.push('/orders')">Xem đơn hàng</button>
            <button class="btn" @click="lePlacedOrder = null; tab = 'hd'; router.push('/catalog')">Tiếp tục đặt hàng</button>
          </div>
        </div>

        <div v-else-if="leEmpty" class="card" style="color: var(--gray)">
          Ngăn Mua lẻ trống —
          <a href="#" style="color: var(--blue2)" @click.prevent="router.push('/catalog')">chọn thêm mặt hàng</a>.
        </div>

        <template v-else>
          <div class="note">
            Ngăn <b>Mua lẻ</b> — không thuộc HĐNT, không hạn mức; Miyano sẽ xác nhận giá và lượng
            trước khi giao. Đặt thành <b>đơn riêng</b>.
          </div>
          <div v-if="leError" class="note" style="color: var(--red); border-color: #fecaca; background: #fef2f2">{{ leError }}</div>
          <div v-if="leLoiDong.length" class="note note-loi">
            <b>Chưa gửi được đơn — cần sửa {{ leLoiDong.length }} mục:</b>
            <ul class="ds-loi"><li v-for="(d, i) in leLoiDong" :key="i">{{ d.thong_diep }}</li></ul>
          </div>

          <div class="grid2">
            <div>
              <div v-if="!isMobile" class="card" style="padding: 0; overflow-x: auto">
                <table>
                  <thead>
                    <tr>
                      <th>MẶT HÀNG</th><th>ĐVT</th><th class="right">Giá lẻ</th>
                      <th style="width: 120px">SL</th><th class="right">Thành tiền</th><th></th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="l in leLines" :key="l.item_code" :class="{ 'dong-loi': leMaLoi.has(l.item_code) }">
                      <td><b>{{ l.item_code }}</b> {{ l.item_name }}</td>
                      <td>{{ l.uom }}</td>
                      <td class="right">{{ fmtVND(l.rate) }}</td>
                      <td>
                        <div class="step">
                          <button @click="leStepDown(l.item_code, l.qty)">−</button>
                          <input :value="l.qty" @change="leQtyInput(l, $event)" inputmode="numeric" />
                          <button @click="leStepUp(l)">+</button>
                        </div>
                      </td>
                      <td class="right"><b>{{ fmtVND(l.qty * l.rate) }}</b></td>
                      <td><button class="btn-o btn-sm" style="color: var(--red); border-color: var(--red)" @click="store.removeFromCartLe(l.item_code)">✕</button></td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <template v-else>
                <div v-for="l in leLines" :key="l.item_code" class="card mb10" :class="{ 'dong-loi': leMaLoi.has(l.item_code) }">
                  <div class="sb">
                    <span><b>{{ l.item_code }}</b><br /><span style="font-size: 13px">{{ l.item_name }}</span></span>
                    <button class="btn-o btn-sm" style="color: var(--red); border-color: var(--red)" @click="store.removeFromCartLe(l.item_code)">✕</button>
                  </div>
                  <div class="tag" style="margin: 4px 0 8px">{{ fmtVND(l.rate) }} / {{ l.uom }}</div>
                  <div class="sb">
                    <div class="step">
                      <button @click="leStepDown(l.item_code, l.qty)">−</button>
                      <input :value="l.qty" @change="leQtyInput(l, $event)" inputmode="numeric" />
                      <button @click="leStepUp(l)">+</button>
                    </div>
                    <b class="pr">{{ fmtVND(l.qty * l.rate) }}</b>
                  </div>
                </div>
              </template>
            </div>

            <div>
              <!-- Thông tin giao hàng riêng cho ngăn Mua lẻ — bản mẫu tĩnh
                   (50_Prototype) không vẽ khối này cho cart-le, nhưng đơn Mua
                   lẻ vẫn là một Sales Order độc lập cần ngày giao/địa chỉ
                   riêng; bỏ hẳn khối này sẽ khiến Miyano không biết giao đi
                   đâu. Xem báo cáo bàn giao — cố ý khác bản mẫu ở đây. -->
              <div class="card mb10" style="margin-bottom: 14px">
                <div class="h3">Thông tin giao hàng</div>
                <div class="field"><label>Ngày giao mong muốn</label><input type="date" v-model="leDeliveryDate" :min="ngayGiaoToiThieu" /></div>
                <div class="field">
                  <label>Địa chỉ giao hàng</label>
                  <select v-model="leAddress"><option v-for="a in addresses" :key="a.name" :value="a.name">{{ a.display }}</option></select>
                </div>
                <div class="field"><label>Số dự trù / PO của đơn vị</label><input v-model="lePo" placeholder="VD: DT-2026-0715" /></div>
                <div class="field"><label>Ghi chú</label><textarea rows="2" v-model="leNote" placeholder="Ghi chú cho Miyano..."></textarea></div>
              </div>
              <div class="card">
                <div class="sb"><span>Tạm tính</span><b>{{ fmtVND(store.cartLeSubtotal) }}</b></div>
                <div class="sb" style="margin-top: 6px"><span>VAT</span><b>{{ fmtVND(store.cartLeVat) }}</b></div>
                <hr class="sep" />
                <div class="sb" style="font-size: 17px"><span><b>Tổng cộng</b></span><b style="color: var(--purple)">{{ fmtVND(store.cartLeTotal) }}</b></div>
                <button class="btn" style="width: 100%; margin-top: 14px; background: var(--purple)" @click="leMoXacNhan">Xác nhận đặt đơn MUA LẺ →</button>
                <p class="tag" style="margin-top: 8px">Đơn ngoài HĐNT, không áp dụng hạn mức — Miyano sẽ xác nhận trước khi giao.</p>
              </div>
            </div>
          </div>
        </template>
      </div>
    </template>

    <!-- Confirm — ngăn HĐNT -->
    <div v-if="hdConfirmOpen && !isMobile" class="modal" @click.self="hdConfirmOpen = false">
      <div class="card">
        <h3>Xác nhận gửi đơn hàng?</h3>
        <p style="font-size: 13px; margin: 10px 0">
          Đơn hàng theo <b>{{ store.contract }}</b>, tổng giá trị
          <b>{{ fmtVND(store.cartTotal) }}</b> sẽ được gửi về hệ thống Supplycore của Miyano và tạo Đơn bán hàng (Sales Order) chờ xác nhận.
        </p>
        <div class="note">Bằng việc xác nhận, quý khách đồng ý đặt hàng theo đơn giá và điều khoản của Hợp đồng nguyên tắc đã ký.</div>
        <div class="flex" style="justify-content: flex-end; margin-top: 14px">
          <button class="btn-o" @click="hdConfirmOpen = false">Quay lại</button>
          <button class="btn" :disabled="hdPlacing" @click="hdConfirmOrder">{{ hdPlacing ? 'Đang gửi…' : 'Xác nhận đặt hàng' }}</button>
        </div>
      </div>
    </div>
    <div v-if="hdConfirmOpen && isMobile" class="sheet" @click.self="hdConfirmOpen = false">
      <div class="in">
        <div class="grab"></div>
        <h3 style="font-size: 16px">Xác nhận gửi đơn hàng?</h3>
        <p style="font-size: 13px; margin: 8px 0">
          Đơn theo <b>{{ store.contract }}</b>, tổng <b>{{ fmtVND(store.cartTotal) }}</b> sẽ gửi về Supplycore và tạo Đơn bán hàng (Sales Order) chờ xác nhận.
        </p>
        <div class="note">Quý khách đồng ý đặt hàng theo đơn giá và điều khoản của Hợp đồng nguyên tắc đã ký.</div>
        <button class="btn" style="width: 100%; margin-top: 8px" :disabled="hdPlacing" @click="hdConfirmOrder">{{ hdPlacing ? 'Đang gửi…' : 'Xác nhận đặt hàng' }}</button>
        <button class="btn-o" style="width: 100%; margin-top: 8px; border: none" @click="hdConfirmOpen = false">Quay lại</button>
      </div>
    </div>

    <!-- Confirm — ngăn Mua lẻ [MỚI]: câu điều khoản RIÊNG, không nhắc HĐNT -->
    <div v-if="leConfirmOpen && !isMobile" class="modal" @click.self="leConfirmOpen = false">
      <div class="card">
        <h3>Xác nhận gửi đơn mua lẻ?</h3>
        <p style="font-size: 13px; margin: 10px 0">
          Đơn <b>Mua lẻ</b> (ngoài HĐNT), tổng giá trị <b>{{ fmtVND(store.cartLeTotal) }}</b> sẽ được
          gửi về hệ thống Supplycore của Miyano. Đơn cần Miyano xác nhận giá và lượng trước khi giao —
          không áp dụng hạn mức hợp đồng nguyên tắc.
        </p>
        <div class="note">Bằng việc xác nhận, quý khách đồng ý đặt đơn mua lẻ theo đơn giá đã niêm yết.</div>
        <div class="flex" style="justify-content: flex-end; margin-top: 14px">
          <button class="btn-o" @click="leConfirmOpen = false">Quay lại</button>
          <button class="btn" style="background: var(--purple)" :disabled="lePlacing" @click="leConfirmOrder">{{ lePlacing ? 'Đang gửi…' : 'Xác nhận đặt đơn mua lẻ' }}</button>
        </div>
      </div>
    </div>
    <div v-if="leConfirmOpen && isMobile" class="sheet" @click.self="leConfirmOpen = false">
      <div class="in">
        <div class="grab"></div>
        <h3 style="font-size: 16px">Xác nhận gửi đơn mua lẻ?</h3>
        <p style="font-size: 13px; margin: 8px 0">
          Đơn <b>Mua lẻ</b> (ngoài HĐNT), tổng <b>{{ fmtVND(store.cartLeTotal) }}</b> — Miyano xác nhận
          giá và lượng trước khi giao, không áp dụng hạn mức hợp đồng nguyên tắc.
        </p>
        <div class="note">Quý khách đồng ý đặt đơn mua lẻ theo đơn giá đã niêm yết.</div>
        <button class="btn" style="width: 100%; margin-top: 8px; background: var(--purple)" :disabled="lePlacing" @click="leConfirmOrder">{{ lePlacing ? 'Đang gửi…' : 'Xác nhận đặt đơn mua lẻ' }}</button>
        <button class="btn-o" style="width: 100%; margin-top: 8px; border: none" @click="leConfirmOpen = false">Quay lại</button>
      </div>
    </div>
  </div>
</template>
