<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api'
import { store } from '../store'
import { fmtVND, addDaysISO } from '../format'
import { useIsMobile } from '../useMobile'

const router = useRouter()
const isMobile = useIsMobile()

const deliveryDate = ref(addDaysISO(2))
const address = ref('')
const po = ref('')
const note = ref('')

const confirmOpen = ref(false)
const placing = ref(false)
const error = ref('')
const placedOrder = ref(null) // { sales_order, total }

const lines = computed(() => store.cartLines)
const isEmpty = computed(() => lines.value.length === 0)
const addresses = computed(() => store.me?.addresses || [])

function stepDown(code, qty) {
  store.setQty(code, qty - 1)
}
function stepUp(line) {
  // Không vượt hạn mức còn lại của mặt hàng (remaining lấy từ catalog).
  const max = line.remaining || Infinity
  store.setQty(line.item_code, Math.min(max, line.qty + 1))
}
function onQtyInput(line, e) {
  let v = Math.max(1, parseInt(e.target.value) || 1)
  if (line.remaining) v = Math.min(line.remaining, v)
  store.setQty(line.item_code, v)
  e.target.value = v
}

async function confirmOrder() {
  placing.value = true
  error.value = ''
  try {
    const items = lines.value.map((l) => ({ item_code: l.item_code, qty: l.qty }))
    const res = await api.call('portal_order_place', {
      contract: store.contract,
      items: JSON.stringify(items),
      po: po.value || null,
      delivery_date: deliveryDate.value || null,
      note: note.value || null,
      address: address.value || null,
    })
    placedOrder.value = res
    store.clearCart()
    confirmOpen.value = false
  } catch (e) {
    error.value = e.message || 'Không thể đặt hàng. Vui lòng thử lại.'
    confirmOpen.value = false
  } finally {
    placing.value = false
  }
}

onMounted(async () => {
  // Đảm bảo có địa chỉ giao + hợp đồng khi vào thẳng /cart (reload mất store).
  try {
    if (!store.me) store.setMe(await api.call('portal_me'))
    if (address.value === '' && (store.me?.addresses || []).length) {
      address.value = store.me.addresses[0].name
    }
    if (!store.contract && !isEmpty.value) {
      const cs = (await api.call('portal_contracts')) || []
      if (cs.length) store.setContract(cs[0].name)
    }
  } catch (e) {
    /* không chặn hiển thị giỏ */
  }
})
</script>

<template>
  <!-- SUCCESS (S-05) -->
  <div v-if="placedOrder" class="card success">
    <div style="font-size: 52px">✅</div>
    <h2 style="margin: 10px 0 6px">Đặt hàng thành công!</h2>
    <p>Đơn hàng của quý khách đã được gửi về hệ thống Supplycore.</p>
    <p style="margin: 14px 0; font-size: 17px">
      Mã đơn: <b style="color: var(--blue)">{{ placedOrder.sales_order }}</b>
      <span class="badge b-gray">Chờ xác nhận</span>
    </p>
    <p class="tag">Nhân viên Miyano sẽ kiểm tra và xác nhận trong giờ làm việc.</p>
    <div class="flex" style="justify-content: center; margin-top: 20px; flex-wrap: wrap">
      <button class="btn-o" @click="router.push('/orders')">Xem đơn hàng</button>
      <button class="btn" @click="placedOrder = null; router.push('/catalog')">Tiếp tục đặt hàng</button>
    </div>
  </div>

  <div v-else>
    <div class="topbar" v-if="!isMobile">
      <div>
        <h2>Giỏ hàng &amp; xác nhận đơn</h2>
        <div class="sub">{{ store.contract || 'Hợp đồng nguyên tắc' }} – {{ store.me?.customer_name || '' }}</div>
      </div>
    </div>

    <div v-if="error" class="note" style="color: var(--red); border-color: #fecaca; background: #fef2f2">{{ error }}</div>

    <!-- EMPTY -->
    <div v-if="isEmpty" class="card" style="color: var(--gray)">
      Giỏ hàng trống – vào mục
      <a href="#" style="color: var(--blue2)" @click.prevent="router.push('/catalog')">Đặt hàng</a>
      để chọn mặt hàng.
    </div>

    <div v-else class="grid2">
      <!-- Danh sách mặt hàng -->
      <div>
        <!-- DESKTOP: bảng -->
        <div v-if="!isMobile" class="card" style="padding: 0; overflow-x: auto">
          <table>
            <thead>
              <tr>
                <th>Mặt hàng</th><th>ĐVT</th><th class="right">Đơn giá</th>
                <th style="width: 120px">SL</th><th class="right">Thành tiền</th><th></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="l in lines" :key="l.item_code">
                <td><b>{{ l.item_code }}</b> {{ l.item_name }}</td>
                <td>{{ l.uom }}</td>
                <td class="right">{{ fmtVND(l.rate) }}</td>
                <td>
                  <div class="step">
                    <button @click="stepDown(l.item_code, l.qty)">−</button>
                    <input :value="l.qty" @change="onQtyInput(l, $event)" inputmode="numeric" />
                    <button @click="stepUp(l)">+</button>
                  </div>
                </td>
                <td class="right"><b>{{ fmtVND(l.qty * l.rate) }}</b></td>
                <td>
                  <button class="btn-o btn-sm" style="color: var(--red); border-color: var(--red)" @click="store.removeFromCart(l.item_code)">✕</button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- MOBILE: thẻ -->
        <template v-else>
          <div v-for="l in lines" :key="l.item_code" class="card mb10">
            <div class="sb">
              <span><b>{{ l.item_code }}</b> {{ l.item_name }}</span>
              <button class="btn-o btn-sm" style="color: var(--red); border-color: var(--red)" @click="store.removeFromCart(l.item_code)">✕</button>
            </div>
            <div class="tag" style="margin: 4px 0 8px">{{ fmtVND(l.rate) }} / {{ l.uom }}</div>
            <div class="sb">
              <div class="step">
                <button @click="stepDown(l.item_code, l.qty)">−</button>
                <input :value="l.qty" @change="onQtyInput(l, $event)" inputmode="numeric" />
                <button @click="stepUp(l)">+</button>
              </div>
              <b class="pr">{{ fmtVND(l.qty * l.rate) }}</b>
            </div>
          </div>
        </template>
      </div>

      <!-- Form giao hàng + tổng tiền -->
      <div>
        <div class="card mb10" style="margin-bottom: 14px">
          <div class="h3">Thông tin giao hàng</div>
          <div class="field">
            <label>Ngày giao mong muốn</label>
            <input type="date" v-model="deliveryDate" />
          </div>
          <div class="field">
            <label>Địa chỉ giao hàng</label>
            <select v-model="address">
              <option v-for="a in addresses" :key="a.name" :value="a.name">{{ a.display }}</option>
            </select>
          </div>
          <div class="field">
            <label>Số dự trù / PO của đơn vị</label>
            <input v-model="po" placeholder="VD: DT-2026-0715" />
          </div>
          <div class="field">
            <label>Ghi chú</label>
            <textarea rows="2" v-model="note" placeholder="Yêu cầu giao giờ hành chính..."></textarea>
          </div>
        </div>
        <div class="card">
          <div class="sb"><span>Tạm tính</span><b>{{ fmtVND(store.cartSubtotal) }}</b></div>
          <div class="sb" style="margin-top: 6px"><span>VAT (5–8%)</span><b>{{ fmtVND(store.cartVat) }}</b></div>
          <hr class="sep" />
          <div class="sb" style="font-size: 17px"><span><b>Tổng cộng</b></span><b style="color: var(--blue)">{{ fmtVND(store.cartTotal) }}</b></div>
          <button class="btn" style="width: 100%; margin-top: 14px" @click="confirmOpen = true">Xác nhận đặt hàng →</button>
          <p class="tag" style="margin-top: 8px">Đơn sẽ được gửi về hệ thống Supplycore và tạo Đơn bán hàng (Sales Order) chờ Miyano xác nhận.</p>
        </div>
      </div>
    </div>

    <!-- Confirm: desktop modal / mobile sheet -->
    <div v-if="confirmOpen && !isMobile" class="modal" @click.self="confirmOpen = false">
      <div class="card">
        <h3>Xác nhận gửi đơn hàng?</h3>
        <p style="font-size: 13px; margin: 10px 0">
          Đơn hàng theo <b>{{ store.contract }}</b>, tổng giá trị
          <b>{{ fmtVND(store.cartTotal) }}</b> sẽ được gửi về hệ thống Supplycore của Miyano và tạo Đơn bán hàng (Sales Order) chờ xác nhận.
        </p>
        <div class="note">Bằng việc xác nhận, quý khách đồng ý đặt hàng theo đơn giá và điều khoản của Hợp đồng nguyên tắc đã ký.</div>
        <div class="flex" style="justify-content: flex-end; margin-top: 14px">
          <button class="btn-o" @click="confirmOpen = false">Quay lại</button>
          <button class="btn" :disabled="placing" @click="confirmOrder">{{ placing ? 'Đang gửi…' : 'Xác nhận đặt hàng' }}</button>
        </div>
      </div>
    </div>
    <div v-if="confirmOpen && isMobile" class="sheet" @click.self="confirmOpen = false">
      <div class="in">
        <div class="grab"></div>
        <h3 style="font-size: 16px">Xác nhận gửi đơn hàng?</h3>
        <p style="font-size: 13px; margin: 8px 0">
          Đơn theo <b>{{ store.contract }}</b>, tổng <b>{{ fmtVND(store.cartTotal) }}</b> sẽ gửi về Supplycore và tạo Đơn bán hàng (Sales Order) chờ xác nhận.
        </p>
        <div class="note">Quý khách đồng ý đặt hàng theo đơn giá và điều khoản của Hợp đồng nguyên tắc đã ký.</div>
        <button class="btn" style="width: 100%; margin-top: 8px" :disabled="placing" @click="confirmOrder">{{ placing ? 'Đang gửi…' : 'Xác nhận đặt hàng' }}</button>
        <button class="btn-o" style="width: 100%; margin-top: 8px; border: none" @click="confirmOpen = false">Quay lại</button>
      </div>
    </div>
  </div>
</template>
