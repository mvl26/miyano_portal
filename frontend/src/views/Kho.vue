<script setup>
import { ref, reactive, watch, onMounted, onUnmounted } from 'vue'
import api from '../api'
import { fmtVND, fmtDate, daysUntil } from '../format'
import { useIsMobile } from '../useMobile'
import PhanTrang from '../components/PhanTrang.vue'
import Icon from '../components/Icon.vue'

const isMobile = useIsMobile()

// --- Trạng thái đầu trang: thông tin kho (kho_me) ---
const meLoading = ref(true)
const noWarehouse = ref(false) // PermissionError riêng: khách chưa được mở kho
const noWarehouseMsg = ref('')
const meError = ref('') // lỗi khác (hệ thống) khi tải kho_me
const me = ref(null)

// --- Trạng thái bảng tồn kho (kho_ton) ---
const listLoading = ref(true)
const listError = ref('')
const items = ref([])
const search = ref('')
let searchTimer = null
// Brief 2026-08-15 (phân trang).
const trang = ref(1)
const soDong = ref(20)
const tong = ref(0)

// --- Trạng thái mở rộng theo từng dòng + cache lô hàng ---
const expanded = reactive({}) // vat_tu -> bool
const lotsByItem = reactive({}) // vat_tu -> { loading, error, data }

async function loadTon() {
  listLoading.value = true
  listError.value = ''
  try {
    const res = await api.callKho('kho_ton', {
      tim: search.value || undefined,
      start: (trang.value - 1) * soDong.value,
      limit: soDong.value,
    })
    items.value = res?.rows || []
    tong.value = res?.tong || 0
  } catch (e) {
    listError.value = e.message || 'Không tải được tồn kho.'
  } finally {
    listLoading.value = false
  }
}

watch([trang, soDong], loadTon)

function onSearchInput() {
  clearTimeout(searchTimer)
  trang.value = 1
  searchTimer = setTimeout(loadTon, 300)
}

function toggle(item) {
  const key = item.vat_tu
  expanded[key] = !expanded[key]
  if (expanded[key] && !lotsByItem[key]) {
    lotsByItem[key] = { loading: true, error: '', data: [] }
    api
      .callKho('kho_lo', { vat_tu: key })
      .then((rows) => {
        lotsByItem[key].data = rows || []
      })
      .catch((e) => {
        lotsByItem[key].error = e.message || 'Không tải được danh sách lô.'
      })
      .finally(() => {
        lotsByItem[key].loading = false
      })
  }
}

// Số lượng: chỉ thêm dấu phân cách nghìn, không phải tiền tệ nên không dùng fmtVND.
function fmtQty(v) {
  return Number(v || 0).toLocaleString('vi-VN')
}

// Trạng thái hạn dùng: quá hạn / sắp hết hạn (≤90 ngày) / còn hạn.
// Không chỉ dựa vào màu — luôn kèm nhãn chữ + ký hiệu.
function expiryInfo(han) {
  if (!han) return { cls: '', label: '', icon: '' }
  const d = daysUntil(han)
  if (d === null) return { cls: '', label: '', icon: '' }
  if (d < 0) return { cls: 'b-red', label: `Quá hạn ${Math.abs(d)} ngày`, icon: '⛔' }
  if (d <= 90) return { cls: 'b-orange', label: `Còn ${d} ngày`, icon: '⚠' }
  return { cls: '', label: '', icon: '' }
}

onMounted(async () => {
  try {
    me.value = await api.callKho('kho_me')
  } catch (e) {
    if (e.name === 'PermissionError') {
      noWarehouse.value = true
      noWarehouseMsg.value = e.message || ''
    } else {
      meError.value = e.message || 'Không tải được thông tin kho.'
    }
    meLoading.value = false
    listLoading.value = false
    return
  }
  meLoading.value = false
  await loadTon()
})

onUnmounted(() => clearTimeout(searchTimer))
</script>

<template>
  <div>
    <div class="topbar" v-if="!isMobile">
      <div>
        <h2>Kho của tôi</h2>
        <div class="sub" v-if="me">{{ me.ten_kho }} · Thủ kho: {{ me.thu_kho || '—' }}</div>
      </div>
      <nav class="flex kho-loi" v-if="!noWarehouse" aria-label="Lối vào các màn kho">
        <router-link to="/kho/nhap" class="btn-o btn-sm"><Icon name="arrow-down-to-line" :size="16" />Phiếu nhập</router-link>
        <router-link to="/kho/xuat" class="btn-o btn-sm"><Icon name="arrow-up-from-line" :size="16" />Phiếu xuất</router-link>
        <router-link to="/kho/import" class="btn-o btn-sm"><Icon name="file-spreadsheet" :size="16" />Nhập tồn đầu kỳ</router-link>
        <router-link to="/kho/vat-tu" class="btn-o btn-sm"><Icon name="package" :size="16" />Danh mục vật tư</router-link>
        <router-link to="/kho/ncc" class="btn-o btn-sm"><Icon name="truck" :size="16" />NCC của tôi</router-link>
        <router-link to="/kho/khoa-phong" class="btn-o btn-sm"><Icon name="hospital" :size="16" />Khoa phòng</router-link>
        <router-link to="/kho/thiet-bi" class="btn-o btn-sm"><Icon name="stethoscope" :size="16" />Thiết bị</router-link>
        <router-link to="/kho/nhat-ky" class="btn-o btn-sm"><Icon name="history" :size="16" />Nhật ký vật tư</router-link>
        <router-link to="/kho/bao-cao" class="btn-o btn-sm"><Icon name="bar-chart" :size="16" />Báo cáo</router-link>
        <!-- Task 14 — brief chỉ liệt router.js/App.vue/kho-bao-cao-columns.js
             là file phải sửa, BỎ SÓT chính lối vào màn (không router-link
             nào trỏ /kho/bao-cao-thiet-bi thì màn chỉ gõ URL tay mới tới
             được) — thêm ở đây, cạnh nút "Báo cáo" cũ, cùng khuôn Task 12 đã
             làm cho "Thiết bị"/"Khoa phòng" (thêm CẢ hai chỗ desktop lẫn
             mobile cùng lúc, không để lệch). -->
        <router-link to="/kho/bao-cao-thiet-bi" class="btn-o btn-sm"><Icon name="clipboard-list" :size="16" />Báo cáo vật tư · máy · khoa</router-link>
      </nav>
    </div>

    <div v-if="meLoading" class="loading">Đang tải…</div>

    <!-- Chưa được mở kho: thông báo bình tĩnh, không phải lỗi hệ thống -->
    <div v-else-if="noWarehouse" class="note note-ic">
      <Icon name="info" />
      <div>{{ noWarehouseMsg || 'Đơn vị của bạn chưa được mở kho trên cổng. Vui lòng liên hệ nhân viên kinh doanh Miyano.' }}</div>
    </div>
    <div v-else-if="meError" class="empty">{{ meError }}</div>

    <template v-else>
      <!-- Header gọn: tên kho + thủ kho (mobile, vì topbar desktop đã ẩn) -->
      <div class="card mb10" v-if="isMobile">
        <div class="sb">
          <b class="row gap8 text-navy"><Icon name="warehouse" :size="18" />{{ me?.ten_kho }}</b>
        </div>
        <p class="tag mt4">Thủ kho: {{ me?.thu_kho || '—' }}</p>
        <nav class="flex kho-loi kho-loi-m mt10" aria-label="Lối vào các màn kho">
          <router-link to="/kho/nhap" class="btn-o btn-sm"><Icon name="arrow-down-to-line" :size="16" />Phiếu nhập</router-link>
          <router-link to="/kho/xuat" class="btn-o btn-sm"><Icon name="arrow-up-from-line" :size="16" />Phiếu xuất</router-link>
          <router-link to="/kho/import" class="btn-o btn-sm"><Icon name="file-spreadsheet" :size="16" />Nhập tồn đầu kỳ</router-link>
          <router-link to="/kho/vat-tu" class="btn-o btn-sm"><Icon name="package" :size="16" />Danh mục vật tư</router-link>
          <router-link to="/kho/ncc" class="btn-o btn-sm"><Icon name="truck" :size="16" />NCC của tôi</router-link>
          <!-- Task 12 — "Khoa phòng" thiếu ở hàng mobile này từ trước (E8),
               chỉ có ở topbar desktop phía trên. Thêm luôn CẢ HAI ở đây: để
               "Thiết bị" một mình mà bỏ qua khoảng trống liền kề là để lại
               đúng kiểu bất đối xứng khó hiểu — sửa cùng lúc, không phải mở
               rộng phạm vi task. -->
          <router-link to="/kho/khoa-phong" class="btn-o btn-sm"><Icon name="hospital" :size="16" />Khoa phòng</router-link>
          <router-link to="/kho/thiet-bi" class="btn-o btn-sm"><Icon name="stethoscope" :size="16" />Thiết bị</router-link>
          <router-link to="/kho/nhat-ky" class="btn-o btn-sm"><Icon name="history" :size="16" />Nhật ký vật tư</router-link>
          <router-link to="/kho/bao-cao" class="btn-o btn-sm"><Icon name="bar-chart" :size="16" />Báo cáo</router-link>
          <!-- Task 14 — cùng lý do bình luận ở khối desktop phía trên. -->
          <router-link to="/kho/bao-cao-thiet-bi" class="btn-o btn-sm"><Icon name="clipboard-list" :size="16" />Báo cáo vật tư · máy · khoa</router-link>
        </nav>
      </div>

      <div class="field mw-sm kho-tim">
        <Icon name="search" :size="16" class="kho-tim-ic" />
        <input
          type="text"
          v-model="search"
          @input="onSearchInput"
          placeholder="Tìm theo mã hoặc tên vật tư…"
        />
      </div>

      <div v-if="listLoading" class="loading">Đang tải…</div>
      <div v-else-if="listError" class="empty">{{ listError }}</div>
      <div v-else-if="!items.length" class="empty">
        {{ search ? 'Không tìm thấy vật tư phù hợp.' : 'Kho hiện chưa có tồn kho.' }}
      </div>

      <!-- DESKTOP: bảng -->
      <div v-else-if="!isMobile" class="card card-flush">
        <div class="tbl-scroll tall">
          <table>
            <thead>
              <tr>
                <th>Mã vật tư</th>
                <th>Tên vật tư</th>
                <th>ĐVT</th>
                <th class="right">SL tồn</th>
                <th class="right">Giá trị</th>
                <th class="right">Số lô</th>
                <th>Hạn gần nhất</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              <template v-for="it in items" :key="it.vat_tu">
                <tr class="clickable" :class="{ 'kho-mo': expanded[it.vat_tu] }" :aria-expanded="!!expanded[it.vat_tu]" @click="toggle(it)">
                  <td class="cell-code">{{ it.ma_vat_tu }}</td>
                  <td>{{ it.ten_vat_tu }}</td>
                  <td>{{ it.dvt }}</td>
                  <td class="right">{{ fmtQty(it.so_luong) }}</td>
                  <td class="right">{{ fmtVND(it.gia_tri) }}</td>
                  <td class="right">{{ it.so_lo_count }}</td>
                  <td class="nowrap">
                    <template v-if="it.han_gan_nhat">
                      {{ fmtDate(it.han_gan_nhat) }}
                      <span
                        v-if="expiryInfo(it.han_gan_nhat).label"
                        class="badge no-dot ml6"
                        :class="expiryInfo(it.han_gan_nhat).cls"
                      ><Icon :name="expiryInfo(it.han_gan_nhat).cls === 'b-red' ? 'ban' : 'alert-triangle'" :size="13" />{{ expiryInfo(it.han_gan_nhat).label }}</span>
                    </template>
                    <span v-else class="tag">—</span>
                  </td>
                  <td class="kho-chev"><Icon :name="expanded[it.vat_tu] ? 'chevron-down' : 'chevron-right'" :size="18" /></td>
                </tr>
                <tr v-if="expanded[it.vat_tu]" class="kho-lo-hang">
                  <td colspan="8" class="kho-lo">
                    <div v-if="lotsByItem[it.vat_tu]?.loading" class="loading">Đang tải lô…</div>
                    <div v-else-if="lotsByItem[it.vat_tu]?.error" class="empty">
                      {{ lotsByItem[it.vat_tu].error }}
                    </div>
                    <div v-else-if="!lotsByItem[it.vat_tu]?.data?.length" class="empty">Không có lô nào.</div>
                    <table v-else class="kho-lo-tbl">
                      <thead>
                        <tr>
                          <th>Số lô</th><th>Hạn sử dụng</th><th class="right">Số lượng</th><th class="right">Đơn giá</th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr v-for="lo in lotsByItem[it.vat_tu].data" :key="lo.so_lo">
                          <td class="mono">{{ lo.so_lo || '—' }}</td>
                          <td class="nowrap">
                            <template v-if="lo.han_su_dung">
                              {{ fmtDate(lo.han_su_dung) }}
                              <span
                                v-if="expiryInfo(lo.han_su_dung).label"
                                class="badge no-dot ml6"
                                :class="expiryInfo(lo.han_su_dung).cls"
                              ><Icon :name="expiryInfo(lo.han_su_dung).cls === 'b-red' ? 'ban' : 'alert-triangle'" :size="13" />{{ expiryInfo(lo.han_su_dung).label }}</span>
                            </template>
                            <span v-else class="tag">Không thời hạn</span>
                          </td>
                          <td class="right">{{ fmtQty(lo.so_luong) }}</td>
                          <td class="right">{{ fmtVND(lo.don_gia) }}</td>
                        </tr>
                      </tbody>
                    </table>
                  </td>
                </tr>
              </template>
            </tbody>
          </table>
        </div>
        <PhanTrang v-model:trang="trang" v-model:so-dong="soDong" :tong="tong" />
      </div>

      <!-- MOBILE: thẻ -->
      <template v-else>
        <div v-for="it in items" :key="it.vat_tu" class="card mb10 clickable" :aria-expanded="!!expanded[it.vat_tu]" @click="toggle(it)">
          <div class="sb">
            <b class="cell-code">{{ it.ma_vat_tu }}</b>
            <span class="kho-chev"><Icon :name="expanded[it.vat_tu] ? 'chevron-down' : 'chevron-right'" :size="18" /></span>
          </div>
          <p class="tag mt4">{{ it.ten_vat_tu }}</p>
          <p class="sb mt8 fs13">
            <span>{{ fmtQty(it.so_luong) }} {{ it.dvt }} · {{ it.so_lo_count }} lô</span>
            <b class="tnum">{{ fmtVND(it.gia_tri) }}</b>
          </p>
          <p class="mt6 fs12" v-if="it.han_gan_nhat">
            Hạn gần nhất: {{ fmtDate(it.han_gan_nhat) }}
            <span
              v-if="expiryInfo(it.han_gan_nhat).label"
              class="badge no-dot ml6"
              :class="expiryInfo(it.han_gan_nhat).cls"
            ><Icon :name="expiryInfo(it.han_gan_nhat).cls === 'b-red' ? 'ban' : 'alert-triangle'" :size="13" />{{ expiryInfo(it.han_gan_nhat).label }}</span>
          </p>

          <div v-if="expanded[it.vat_tu]" class="mt10" @click.stop>
            <hr class="sep" />
            <div v-if="lotsByItem[it.vat_tu]?.loading" class="loading">Đang tải lô…</div>
            <div v-else-if="lotsByItem[it.vat_tu]?.error" class="empty">{{ lotsByItem[it.vat_tu].error }}</div>
            <div v-else-if="!lotsByItem[it.vat_tu]?.data?.length" class="empty">Không có lô nào.</div>
            <div v-else v-for="lo in lotsByItem[it.vat_tu].data" :key="lo.so_lo" class="rowline">
              <span>
                Lô <span class="mono">{{ lo.so_lo || '—' }}</span>
                <template v-if="lo.han_su_dung">· HSD {{ fmtDate(lo.han_su_dung) }}</template>
                <template v-else>· Không thời hạn</template>
              </span>
              <span class="tnum nowrap"><b>{{ fmtQty(lo.so_luong) }}</b> · {{ fmtVND(lo.don_gia) }}</span>
            </div>
          </div>
        </div>
        <PhanTrang v-model:trang="trang" v-model:so-dong="soDong" :tong="tong" />
      </template>
    </template>
  </div>
</template>

<style scoped>
/* Cụm lối tắt tới các màn kho con: chiếm trọn một hàng dưới tiêu đề,
   các ô cùng cỡ, icon đứng trước chữ. */
.kho-loi {
  flex-basis: 100%;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(196px, 1fr));
  gap: 8px;
}
.kho-loi .btn-o { justify-content: flex-start; min-height: 40px; }
.kho-loi .btn-o .ic { color: var(--accent); }
.kho-loi-m { grid-template-columns: 1fr 1fr; }
.kho-loi-m .btn-o { white-space: normal; text-align: left; line-height: 1.25; padding: 6px 10px; }

/* Ô tìm kiếm có icon kính lúp bên trái. */
.kho-tim { position: relative; }
.kho-tim-ic { position: absolute; left: 12px; top: 12px; color: var(--text-3); pointer-events: none; }
.kho-tim input { padding-left: 36px; }

/* Cột chevron mở/đóng lô. */
.kho-chev { width: 40px; color: var(--text-3); text-align: center; }
tr.kho-mo td { background: var(--accent-soft); }
tr.kho-mo .kho-chev { color: var(--accent); }

/* Bảng lô lồng trong dòng vật tư: nền nhạt, header không dính (chỉ header
   bảng ngoài dính khi cuộn). */
tr.kho-lo-hang:hover td.kho-lo { background: var(--surface-2); }
.kho-lo { background: var(--surface-2); padding: 8px 16px 12px 40px; }
.kho-lo-tbl { background: transparent; }
.kho-lo-tbl th { position: static; box-shadow: none; background: transparent; }
.kho-lo-tbl td { background: transparent; padding-top: 8px; padding-bottom: 8px; }
.kho-lo-tbl tr:hover td { background: var(--surface); }
</style>
