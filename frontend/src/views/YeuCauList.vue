<script setup>
// Task 11 (QĐ-G11, chủ đầu tư chốt 21/08/2026) — "Yêu cầu của tôi".
//
// Màn này NUỐT hai màn cũ: `Orders.vue` (`/orders`, danh sách Sales Order)
// và `DeXuatList.vue` (`/de-xuat`, danh sách phiếu đề xuất). Lý do gộp:
// một yêu cầu của khoa nằm ở "Đề xuất mua" khi còn là phiếu rồi NHẢY sang
// "Đơn hàng của tôi" sau khi quản lý duyệt — để tìm lại yêu cầu của chính
// mình, nhân viên phải biết trước nó đang ở giai đoạn NỘI BỘ nào, tức phải
// học sơ đồ kiến trúc của hệ thống.
//
// Một yêu cầu xuất hiện ĐÚNG MỘT LẦN, ở bất kỳ giai đoạn nào. Phiếu và đơn
// sinh ra từ nó là MỘT dòng — server đã gộp (`portal_yeu_cau_cua_toi`), client
// KHÔNG tự ghép hai danh sách.
//
// "Duyệt" (`/duyet`) KHÔNG gộp vào đây: đó là HÀNG CHỜ VIỆC của quản lý,
// khác mục đích với *danh sách của tôi*. Gộp hai thứ khác mục đích chỉ vì
// chúng cùng kiểu dữ liệu là lặp lại đúng lỗi task này đang sửa.
import { ref, watch, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../api'
import { fmtVND, fmtDate, giaiDoanBadge } from '../format'
import { useIsMobile } from '../useMobile'
import { store } from '../store'
import PhanTrang from '../components/PhanTrang.vue'

const route = useRoute()
const router = useRouter()
const isMobile = useIsMobile()

const loading = ref(true)
const error = ref('')
const rows = ref([])
const filter = ref('') // '' = Tất cả
const trang = ref(1)
const soDong = ref(20)
const tong = ref(0)

// ĐÚNG bộ `GIAI_DOAN_HOP_LE` của backend, không nhiều không ít: một chip
// backend không biết sẽ ăn lỗi "Giai đoạn không hợp lệ", còn một giai đoạn
// thiếu chip thì yêu cầu ở đó chỉ tìm được qua "Tất cả".
const FILTERS = [
  '', 'Nháp', 'Chờ duyệt', 'Đã duyệt', 'Chờ báo giá', 'Đã giao',
  'Từ chối', 'Đã huỷ',
]

// Khoa phòng chỉ có MÃ (`KP-00001`) trong payload — cùng khuôn
// DeXuatList.vue/PhieuXuat.vue: nạp danh mục khoa phòng của kho rồi tự map
// mã -> tên. Best-effort: một khách chưa mở kho vẫn phải xem được danh
// sách, chỉ mất phần dịch tên khoa.
const khoaPhongList = ref([])
async function loadKhoaPhongList() {
  try {
    khoaPhongList.value = await api.callKho('kho_khoa_phong_list', { ca_inactive: 1 })
  } catch (e) {
    // Im lặng — cột khoa phòng rơi về hiện mã thô, không chặn cả danh sách.
  }
}
function tenKhoa(ma) {
  if (!ma) return ''
  const k = khoaPhongList.value.find((x) => x.name === ma)
  return k ? k.ten_khoa_phong : ma
}

function pct(r) {
  return Math.round(Number(r.per_delivered || 0))
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const res = await api.call('portal_yeu_cau_cua_toi', {
      start: (trang.value - 1) * soDong.value,
      limit: soDong.value,
      // '' (chip "Tất cả") bị JSON.stringify loại khỏi body -> backend
      // nhận `giai_doan=None` -> không lọc.
      giai_doan: filter.value || undefined,
    })
    rows.value = res?.rows || []
    tong.value = res?.tong || 0
  } catch (e) {
    error.value = e.message || 'Không tải được danh sách yêu cầu.'
  } finally {
    loading.value = false
  }
}

// Đổi chip -> về trang 1 (kết quả lọc mới có thể ít hơn trang đang xem).
// Chip đang chọn sống trong URL để nút "Quay lại" của màn chi tiết dựng
// lại được đúng nó (C3, giữ nguyên cơ chế của DeXuatList.vue).
watch(filter, (f) => {
  trang.value = 1
  router.replace({ name: 'yeu-cau', query: f ? { chip: f } : {} })
})
watch([trang, soDong, filter], load)

// SỬA được ⟺ đúng quyền `de_xuat_luu_nhap` phía server (owner HOẶC quản
// lý). Client đoán khác server thì khách gõ xong mới ăn "Phiếu này không
// phải của bạn" và mất sạch công sửa — cùng điều kiện DeXuatList.vue đã
// dùng, mang nguyên sang.
function coTheSuaNhap(r) {
  return (
    r.giai_doan === 'Nháp'
    && !!r.de_xuat
    && (r.owner === store.me?.user || !!store.me?.la_quan_ly)
  )
}

// Đích của một dòng = CHỨNG TỪ CHÍNH LÀ yêu cầu đó:
//   * phiếu Nháp sửa được  -> màn Đặt hàng (`/dat-hang/:ten`), nơi duy
//     nhất có ô nhập số lượng cho một phiếu chưa gửi duyệt;
//   * có phiếu             -> chi tiết phiếu (khối truy vết + link sang
//     đơn đứng sau nó, xem DeXuatDetail.vue);
//   * không có phiếu       -> chi tiết đơn (đơn cũ, có trước luồng duyệt).
// Nút "Đơn hàng" riêng ở cột cuối đưa thẳng tới màn giao hàng cho dòng đã
// thành đơn — một LỐI VÀO NHÌN THẤY ĐƯỢC, không phải một quy tắc ẩn người
// dùng phải học.
function moYeuCau(r) {
  if (coTheSuaNhap(r)) {
    router.push({ name: 'dat-hang', params: { ten: r.de_xuat } })
    return
  }
  if (r.de_xuat) {
    router.push({
      name: 'de-xuat-detail',
      params: { ten: r.de_xuat },
      query: { tu: 'yeu-cau', ...(filter.value ? { chip: filter.value } : {}) },
    })
    return
  }
  router.push({ name: 'order-detail', params: { name: r.sales_order } })
}

function moDon(r) {
  router.push({ name: 'order-detail', params: { name: r.sales_order } })
}

onMounted(async () => {
  loadKhoaPhongList()
  // Khôi phục chip từ URL (nút "Quay lại" của màn chi tiết dựng lại nó).
  // Gán vào `filter` KÍCH HOẠT watcher, tức `load()` đã được xếp hàng —
  // gọi thêm `load()` ở cuối hàm là MỘT REQUEST THỪA, và nó về sau lời gọi
  // kia nên còn có thể ghi đè kết quả đúng bằng kết quả cũ. `DeXuatList.
  // vue` chấp nhận lời gọi thừa đó ("rẻ hơn một nhánh điều kiện"); ở đây
  // nhánh điều kiện là đúng một biến, nên không có gì để đánh đổi.
  let daXepHangLoad = false
  if (route.query.chip && FILTERS.includes(String(route.query.chip))) {
    filter.value = String(route.query.chip)
    daXepHangLoad = true
  }
  if (!store.me) {
    try {
      store.setMe(await api.call('portal_me'))
    } catch (e) {
      // Subtitle phạm vi + nút "Sửa" chỉ là gợi ý phụ — im lặng bỏ qua.
    }
  }
  if (!daXepHangLoad) load()
})
</script>

<template>
  <div>
    <div class="topbar" v-if="!isMobile">
      <div>
        <h2>Yêu cầu của tôi</h2>
        <div class="sub">
          {{ store.me?.la_quan_ly
            ? 'Mọi yêu cầu của đơn vị — từ lúc còn là phiếu tới lúc nhận hàng'
            : 'Mọi yêu cầu của khoa bạn — từ lúc còn là phiếu tới lúc nhận hàng' }}
        </div>
      </div>
      <router-link :to="{ name: 'dat-hang' }"><button class="btn">+ Đặt hàng</button></router-link>
    </div>
    <div v-else class="mb10">
      <router-link :to="{ name: 'dat-hang' }"><button class="btn btn-sm">+ Đặt hàng</button></router-link>
    </div>

    <div class="chips">
      <button
        v-for="f in FILTERS"
        :key="f"
        class="chip"
        :class="{ on: filter === f }"
        @click="filter = f"
      >
        {{ f || 'Tất cả' }}
      </button>
    </div>

    <div v-if="loading" class="loading">Đang tải…</div>
    <div v-else-if="error" class="empty">{{ error }}</div>
    <!-- Câu rỗng phải nói ĐÚNG VAI người đang đọc — cùng bài học "Việc (b)"
         của DeXuatList.vue: quản lý xem phạm vi toàn đơn vị mà câu rỗng lại
         bảo "Khoa chưa có…" là hai câu trên cùng một màn nói hai phạm vi
         khác nhau, và câu sai là câu DUY NHẤT hiện khi màn trống. -->
    <div v-else-if="!rows.length" class="empty">
      {{ store.me?.la_quan_ly ? 'Đơn vị chưa có yêu cầu nào.' : 'Khoa chưa có yêu cầu nào.' }}
    </div>

    <!-- DESKTOP: bảng -->
    <div v-else-if="!isMobile" class="card" style="padding: 0; overflow-x: auto">
      <table>
        <thead>
          <tr>
            <th>Mã yêu cầu</th><th>Khoa phòng</th><th>Ngày yêu cầu</th>
            <th class="right">Giá trị</th><th style="min-width: 130px">Đã giao</th>
            <th>Giai đoạn</th><th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in rows" :key="r.khoa_sap_xep" class="clickable" @click="moYeuCau(r)">
            <td>
              <b v-if="r.ma">{{ r.ma }}</b>
              <span v-else class="tag">(chưa gửi duyệt)</span>
            </td>
            <td>{{ tenKhoa(r.khoa_phong) }}</td>
            <td>{{ fmtDate(r.thoi_diem) }}</td>
            <!-- Yêu cầu chưa thành đơn chưa có giá trị nào để nói — "—",
                 không phải một số 0 đọc như một con số thật. -->
            <td class="right">{{ r.sales_order ? fmtVND(r.grand_total) : '—' }}</td>
            <td>
              <template v-if="r.sales_order">
                {{ pct(r) }}%
                <div class="bar"><i :style="{ width: pct(r) + '%', background: 'var(--orange)' }"></i></div>
              </template>
              <span v-else class="tag">—</span>
            </td>
            <td>
              <span class="badge" :class="giaiDoanBadge(r.giai_doan)">{{ r.giai_doan }}</span>
              <!-- Giai đoạn gộp KHÔNG được nuốt mất tín hiệu chi tiết của
                   đơn ("Chờ xác nhận"/"Đang giao"/…) — nó là thứ nói ai
                   đang giữ việc. -->
              <div v-if="r.trang_thai_don" class="tag" style="margin-top: 2px">{{ r.trang_thai_don }}</div>
            </td>
            <td style="white-space: nowrap">
              <button v-if="coTheSuaNhap(r)" class="btn-o btn-sm" @click.stop="moYeuCau(r)">Sửa</button>
              <button v-if="r.sales_order" class="btn-o btn-sm" @click.stop="moDon(r)">Đơn hàng</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- MOBILE: thẻ -->
    <template v-else>
      <div
        v-for="r in rows"
        :key="r.khoa_sap_xep"
        class="card mb10 clickable"
        @click="moYeuCau(r)"
      >
        <div class="sb">
          <b v-if="r.ma">{{ r.ma }}</b>
          <span v-else class="tag">(chưa gửi duyệt)</span>
          <span class="badge" :class="giaiDoanBadge(r.giai_doan)">{{ r.giai_doan }}</span>
        </div>
        <p class="tag" style="margin-top: 4px">
          {{ tenKhoa(r.khoa_phong) }} · {{ fmtDate(r.thoi_diem) }}
          <template v-if="r.sales_order"> · {{ fmtVND(r.grand_total) }}</template>
          <template v-if="r.trang_thai_don"> · {{ r.trang_thai_don }}</template>
        </p>
        <template v-if="r.sales_order && pct(r) > 0">
          <p style="font-size: 12px; margin-top: 6px">Đã giao <b>{{ pct(r) }}%</b></p>
          <div class="bar"><i :style="{ width: pct(r) + '%', background: 'var(--orange)' }"></i></div>
        </template>
        <div style="margin-top: 8px">
          <button v-if="coTheSuaNhap(r)" class="btn-o btn-sm" @click.stop="moYeuCau(r)">Sửa</button>
          <button v-if="r.sales_order" class="btn-o btn-sm" @click.stop="moDon(r)">Đơn hàng</button>
        </div>
      </div>
    </template>

    <PhanTrang v-if="!loading && !error" v-model:trang="trang" v-model:so-dong="soDong" :tong="tong" />
  </div>
</template>
