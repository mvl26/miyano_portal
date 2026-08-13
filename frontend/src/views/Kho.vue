<script setup>
import { ref, reactive, onMounted, onUnmounted } from 'vue'
import api from '../api'
import { fmtVND, fmtDate, daysUntil } from '../format'
import { useIsMobile } from '../useMobile'

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

// --- Trạng thái mở rộng theo từng dòng + cache lô hàng ---
const expanded = reactive({}) // vat_tu -> bool
const lotsByItem = reactive({}) // vat_tu -> { loading, error, data }

async function loadTon() {
  listLoading.value = true
  listError.value = ''
  try {
    items.value = (await api.callKho('kho_ton', { tim: search.value || undefined })) || []
  } catch (e) {
    listError.value = e.message || 'Không tải được tồn kho.'
  } finally {
    listLoading.value = false
  }
}

function onSearchInput() {
  clearTimeout(searchTimer)
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
      <div class="flex" v-if="!noWarehouse" style="gap: 8px">
        <router-link to="/kho/nhap" class="btn-o btn-sm">Phiếu nhập</router-link>
        <router-link to="/kho/xuat" class="btn-o btn-sm">Phiếu xuất</router-link>
        <router-link to="/kho/import" class="btn-o btn-sm">Nhập tồn đầu kỳ</router-link>
        <router-link to="/kho/vat-tu" class="btn-o btn-sm">Danh mục vật tư</router-link>
        <router-link to="/kho/ncc" class="btn-o btn-sm">NCC của tôi</router-link>
        <router-link to="/kho/nhat-ky" class="btn-o btn-sm">Nhật ký vật tư</router-link>
        <router-link to="/kho/bao-cao" class="btn-o btn-sm">Báo cáo</router-link>
      </div>
    </div>

    <div v-if="meLoading" class="loading">Đang tải…</div>

    <!-- Chưa được mở kho: thông báo bình tĩnh, không phải lỗi hệ thống -->
    <div v-else-if="noWarehouse" class="note">
      {{ noWarehouseMsg || 'Đơn vị của bạn chưa được mở kho trên cổng. Vui lòng liên hệ nhân viên kinh doanh Miyano.' }}
    </div>
    <div v-else-if="meError" class="empty">{{ meError }}</div>

    <template v-else>
      <!-- Header gọn: tên kho + thủ kho (mobile, vì topbar desktop đã ẩn) -->
      <div class="card mb10" v-if="isMobile">
        <div class="sb">
          <b>{{ me?.ten_kho }}</b>
        </div>
        <p class="tag" style="margin-top: 4px">Thủ kho: {{ me?.thu_kho || '—' }}</p>
        <div class="flex" style="gap: 8px; margin-top: 10px; flex-wrap: wrap">
          <router-link to="/kho/nhap" class="btn-o btn-sm">Phiếu nhập</router-link>
          <router-link to="/kho/xuat" class="btn-o btn-sm">Phiếu xuất</router-link>
          <router-link to="/kho/import" class="btn-o btn-sm">Nhập tồn đầu kỳ</router-link>
          <router-link to="/kho/vat-tu" class="btn-o btn-sm">Danh mục vật tư</router-link>
          <router-link to="/kho/ncc" class="btn-o btn-sm">NCC của tôi</router-link>
          <router-link to="/kho/nhat-ky" class="btn-o btn-sm">Nhật ký vật tư</router-link>
          <router-link to="/kho/bao-cao" class="btn-o btn-sm">Báo cáo</router-link>
        </div>
      </div>

      <div class="field" style="max-width: 360px">
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
      <div v-else-if="!isMobile" class="card" style="padding: 0; overflow-x: auto">
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
              <tr class="clickable" @click="toggle(it)">
                <td><b>{{ it.ma_vat_tu }}</b></td>
                <td>{{ it.ten_vat_tu }}</td>
                <td>{{ it.dvt }}</td>
                <td class="right">{{ fmtQty(it.so_luong) }}</td>
                <td class="right">{{ fmtVND(it.gia_tri) }}</td>
                <td class="right">{{ it.so_lo_count }}</td>
                <td>
                  <template v-if="it.han_gan_nhat">
                    {{ fmtDate(it.han_gan_nhat) }}
                    <span
                      v-if="expiryInfo(it.han_gan_nhat).label"
                      class="badge"
                      :class="expiryInfo(it.han_gan_nhat).cls"
                      style="margin-left: 6px"
                    >{{ expiryInfo(it.han_gan_nhat).icon }} {{ expiryInfo(it.han_gan_nhat).label }}</span>
                  </template>
                  <span v-else class="tag">—</span>
                </td>
                <td>{{ expanded[it.vat_tu] ? '▾' : '▸' }}</td>
              </tr>
              <tr v-if="expanded[it.vat_tu]">
                <td colspan="8" style="background: #f8fafc; padding: 12px 16px">
                  <div v-if="lotsByItem[it.vat_tu]?.loading" class="loading">Đang tải lô…</div>
                  <div v-else-if="lotsByItem[it.vat_tu]?.error" class="empty">
                    {{ lotsByItem[it.vat_tu].error }}
                  </div>
                  <div v-else-if="!lotsByItem[it.vat_tu]?.data?.length" class="empty">Không có lô nào.</div>
                  <table v-else style="background: transparent">
                    <thead>
                      <tr>
                        <th>Số lô</th><th>Hạn sử dụng</th><th class="right">Số lượng</th><th class="right">Đơn giá</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-for="lo in lotsByItem[it.vat_tu].data" :key="lo.so_lo">
                        <td>{{ lo.so_lo || '—' }}</td>
                        <td>
                          <template v-if="lo.han_su_dung">
                            {{ fmtDate(lo.han_su_dung) }}
                            <span
                              v-if="expiryInfo(lo.han_su_dung).label"
                              class="badge"
                              :class="expiryInfo(lo.han_su_dung).cls"
                              style="margin-left: 6px"
                            >{{ expiryInfo(lo.han_su_dung).icon }} {{ expiryInfo(lo.han_su_dung).label }}</span>
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

      <!-- MOBILE: thẻ -->
      <template v-else>
        <div v-for="it in items" :key="it.vat_tu" class="card mb10 clickable" @click="toggle(it)">
          <div class="sb">
            <b>{{ it.ma_vat_tu }}</b>
            <span>{{ expanded[it.vat_tu] ? '▾' : '▸' }}</span>
          </div>
          <p class="tag" style="margin-top: 4px">{{ it.ten_vat_tu }}</p>
          <p class="sb" style="margin-top: 8px; font-size: 13px">
            <span>{{ fmtQty(it.so_luong) }} {{ it.dvt }} · {{ it.so_lo_count }} lô</span>
            <b>{{ fmtVND(it.gia_tri) }}</b>
          </p>
          <p style="margin-top: 6px; font-size: 12px" v-if="it.han_gan_nhat">
            Hạn gần nhất: {{ fmtDate(it.han_gan_nhat) }}
            <span
              v-if="expiryInfo(it.han_gan_nhat).label"
              class="badge"
              :class="expiryInfo(it.han_gan_nhat).cls"
              style="margin-left: 6px"
            >{{ expiryInfo(it.han_gan_nhat).icon }} {{ expiryInfo(it.han_gan_nhat).label }}</span>
          </p>

          <div v-if="expanded[it.vat_tu]" class="mt10" style="margin-top: 10px" @click.stop>
            <hr class="sep" />
            <div v-if="lotsByItem[it.vat_tu]?.loading" class="loading">Đang tải lô…</div>
            <div v-else-if="lotsByItem[it.vat_tu]?.error" class="empty">{{ lotsByItem[it.vat_tu].error }}</div>
            <div v-else-if="!lotsByItem[it.vat_tu]?.data?.length" class="empty">Không có lô nào.</div>
            <div v-else v-for="lo in lotsByItem[it.vat_tu].data" :key="lo.so_lo" class="rowline">
              <span>
                Lô {{ lo.so_lo || '—' }}
                <template v-if="lo.han_su_dung">· HSD {{ fmtDate(lo.han_su_dung) }}</template>
                <template v-else>· Không thời hạn</template>
              </span>
              <span><b>{{ fmtQty(lo.so_luong) }}</b> · {{ fmtVND(lo.don_gia) }}</span>
            </div>
          </div>
        </div>
      </template>
    </template>
  </div>
</template>
