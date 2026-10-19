<script setup>
// Chi tiết một yêu cầu báo giá (spec 2026-10-12 §6.3, 2026-10-15 §5.2). Mỗi báo
// giá gửi khách (cả phiếu, hoặc từng đợt) là một `KhoiBaoGia`; server quyết
// định khách thấy gì và làm gì, màn này không tự suy từ trạng thái.
import { ref, computed, watch, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import api from '../api'
import { fmtDate } from '../format'
import { showToast } from '../toast'
import { nhanNhomBaoGia, nhomBaoGiaBadge, nhanDot } from '../bao-gia'
import ReasonModal from '../components/ReasonModal.vue'
import CotTenHang from '../components/CotTenHang.vue'
import KhoiBaoGia from '../components/KhoiBaoGia.vue'
import KhoiDongThoiGian from '../components/chi-tiet/KhoiDongThoiGian.vue'

const route = useRoute()

const loading = ref(true)
const error = ref('')
const bg = ref(null)
const nhatKy = ref([])
const dangTaiNhatKy = ref(false)

const dongChuaKhop = computed(() => (bg.value?.dat_ngoai || []).filter((d) => !d.da_xu_ly))
const coDot = computed(() => (bg.value?.dot || []).length > 0)
const moHuy = ref(false)
const dangHuy = ref(false)

async function load() {
  loading.value = true
  error.value = ''
  try {
    bg.value = await api.call('portal_bao_gia_chi_tiet', { ten: route.params.ten })
    napNhatKy()
  } catch (e) {
    bg.value = null
    error.value = e.message || 'Không tải được yêu cầu báo giá.'
  } finally {
    loading.value = false
  }
}

// Đọc sổ là việc phụ: không `await` ở `load()`, lỗi không làm hỏng màn chính.
async function napNhatKy() {
  if (!bg.value?.de_xuat) { nhatKy.value = []; return }
  dangTaiNhatKy.value = true
  try {
    nhatKy.value = (await api.call('portal_nhat_ky_yeu_cau', { de_xuat: bg.value.de_xuat })) || []
  } catch (e) {
    console.warn('[ChiTietBaoGia] không tải được nhật ký:', e)
    nhatKy.value = []
  } finally {
    dangTaiNhatKy.value = false
  }
}

// Huỷ các mặt hàng CHƯA báo (spec 2026-10-15 §4.4). Đợt đang chờ đồng ý vẫn
// còn hiệu lực. Hộp lý do chỉ đóng khi server đã nhận.
async function huyConLai(lyDo) {
  if (dangHuy.value) return
  dangHuy.value = true
  try {
    await api.call('portal_bao_gia_huy_con_lai', { ten: bg.value.bao_gia, ly_do: lyDo || undefined })
    moHuy.value = false
    showToast('Đã huỷ các mặt hàng chưa báo giá.')
    await load()
  } catch (e) {
    showToast(e.message || 'Không huỷ được phần còn lại.', 'error')
  } finally {
    dangHuy.value = false
  }
}

watch(() => route.params.ten, (moi) => { if (moi && route.name === 'bao-gia-detail') load() })
onMounted(load)
</script>

<template>
  <div>
    <div class="topbar">
      <router-link :to="{ name: 'bao-gia' }"><button class="btn-o" style="margin-bottom: 8px">← Quay lại</button></router-link>
    </div>

    <div v-if="loading" class="loading">Đang tải…</div>
    <div v-else-if="error" class="empty">{{ error }}</div>

    <template v-else-if="bg">
      <div class="card mb10">
        <div class="sb">
          <h3 style="margin: 0">{{ bg.ma || bg.bao_gia }}</h3>
          <span class="badge" :class="nhomBaoGiaBadge(bg.nhom)">{{ nhanNhomBaoGia(bg.nhom) }}</span>
        </div>
        <p v-if="bg.ten_don_hang" style="margin-top: 4px; overflow-wrap: anywhere">{{ bg.ten_don_hang }}</p>
        <p class="tag" style="margin-top: 4px">
          Yêu cầu báo giá {{ bg.bao_gia }} · gửi ngày {{ fmtDate(bg.ngay_tao) }}
          <template v-if="!coDot && bg.han_hieu_luc"> · hiệu lực đến <b>{{ fmtDate(bg.han_hieu_luc) }}</b></template>
        </p>
        <p v-if="bg.het_han" class="tag" style="margin-top: 6px; color: var(--red)">
          Báo giá đã quá hạn hiệu lực. Gửi yêu cầu báo giá mới nếu vẫn cần hàng.
        </p>
        <p v-if="bg.ly_do_tu_choi" class="tag" style="margin-top: 6px; color: var(--red)">
          Lý do từ chối: {{ bg.ly_do_tu_choi }}
        </p>
        <p v-if="bg.sales_order" style="margin-top: 6px">
          <router-link :to="{ name: 'order-detail', params: { name: bg.sales_order } }">
            Xem đơn hàng {{ bg.sales_order }} →
          </router-link>
        </p>
        <p v-else-if="bg.de_xuat" class="tag" style="margin-top: 6px">
          <router-link :to="{ name: 'de-xuat-detail', params: { ten: bg.de_xuat } }">Xem phiếu đề xuất gốc</router-link>
        </p>
      </div>

      <template v-if="coDot">
        <KhoiBaoGia v-for="d in bg.dot" :key="d.bao_gia" :bg="d" :tieu-de="nhanDot(d)" @xong="load" />

        <div v-if="bg.con_lai.length || bg.duoc_huy_con_lai" class="card mb10"
             style="padding: 0; overflow-x: auto">
          <div class="sb" style="padding: 12px 14px 0">
            <div class="h3" style="margin: 0">Chờ Miyano báo giá</div>
            <span class="badge b-blue">{{ bg.con_lai.length }} mặt hàng</span>
          </div>
          <table v-if="bg.con_lai.length">
            <thead><tr><CotTenHang head /><th>ĐVT</th><th class="right">Số lượng</th></tr></thead>
            <tbody>
              <tr v-for="it in bg.con_lai" :key="it.name">
                <CotTenHang :ma="it.item_code" :ten="it.item_name || ''" />
                <td>{{ it.uom }}</td><td class="right">{{ it.qty }}</td>
              </tr>
            </tbody>
          </table>
          <div v-if="bg.duoc_huy_con_lai" style="padding: 10px 14px">
            <button class="btn-o" :disabled="dangHuy" @click="moHuy = true">✕ Huỷ phần còn lại…</button>
            <span class="tag"> Các đợt đã gửi vẫn giữ nguyên.</span>
          </div>
        </div>
        <!-- Đã huỷ phần còn lại: một dòng thay cho khối "Chờ Miyano báo giá". -->
        <div v-if="bg.da_huy_con_lai" class="card mb10">
          <div class="h3" style="margin: 0">Đã huỷ các mặt hàng chưa báo giá</div>
          <p v-if="bg.ly_do_huy_con_lai" class="tag" style="margin-top: 4px; overflow-wrap: anywhere">
            Lý do: {{ bg.ly_do_huy_con_lai }}
          </p>
        </div>
      </template>
      <KhoiBaoGia v-else :bg="bg" @xong="load" />

      <div v-if="dongChuaKhop.length" class="card mb10">
        <div class="h3">Hàng quý vị mô tả — Miyano đang tìm mã</div>
        <div v-for="(d, i) in dongChuaKhop" :key="i" class="rowline">
          <span>{{ d.ten_hang }}</span><span class="tag">{{ d.so_luong }} {{ d.dvt }}</span>
        </div>
      </div>

      <KhoiDongThoiGian :dong="nhatKy" :dang-tai="dangTaiNhatKy" />

      <ReasonModal
        :open="moHuy"
        title="Huỷ phần còn lại"
        desc="Các mặt hàng chưa được báo giá sẽ không được báo nữa. Lý do không bắt buộc."
        placeholder="VD: Đã mua được ở nơi khác…"
        :min-len="0"
        :submitting="dangHuy"
        submit-label="Huỷ phần còn lại"
        @submit="huyConLai"
        @close="moHuy = false"
      />
    </template>
  </div>
</template>
