<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api'
import { useIsMobile } from '../useMobile'
import { useImportWizard } from '../useImportWizard'
import ImportErrorRows from '../components/ImportErrorRows.vue'
import Icon from '../components/Icon.vue'

const router = useRouter()
const isMobile = useIsMobile()

const templateUrl = api.khoDownloadUrl('kho_vat_tu_export') // "mẫu" = chính danh mục hiện tại

const {
  fileInput, selectedFile,
  previewing, committing, previewError, preview, result,
  canConfirm, onPickFile, onPreview, onCommit, startOver,
} = useImportWizard({
  previewMethod: 'kho_vat_tu_import_preview',
  commitMethod: 'kho_vat_tu_import_commit',
  successMsg: 'Đã nhập danh mục vật tư thành công.',
  failMsg: 'Nhập danh mục vật tư thất bại.',
})

// Chỉ để trình bày: bước đang ở của trình tự tải mẫu → xem trước → xác nhận
// (chấm số cạnh tiêu đề mỗi bước). Không tham gia logic nhập.
// lopBuoc[n] = 'done' | 'cur' | '' cho bước n (1..4).
const lopBuoc = computed(() => {
  const hienTai = preview.value ? 4 : selectedFile.value ? 2 : 1
  return [0, 1, 2, 3, 4].map((n) => (n < hienTai ? 'done' : n === hienTai ? 'cur' : ''))
})

const HANH_DONG_LABEL = {
  tao_moi: { text: 'Tạo mới', cls: 'b-blue' },
  cap_nhat: { text: 'Cập nhật', cls: 'b-green' },
}

function goToDanhMuc() {
  router.push('/kho/vat-tu')
}
</script>

<template>
  <div>
    <div class="topbar" v-if="!isMobile">
      <div>
        <h2>Nhập danh mục vật tư</h2>
        <div class="sub">Tải mẫu Excel, sửa vật tư, xem trước rồi xác nhận — không có gì được ghi cho tới khi bạn xác nhận.</div>
      </div>
    </div>
    <h2 v-else class="mb4">Nhập danh mục vật tư</h2>
    <p class="tag mb16" v-if="isMobile">
      Tải mẫu, sửa vật tư, xem trước rồi xác nhận.
    </p>

    <!-- Đã nhập xong -->
    <div v-if="result" class="card success">
      <div class="success-ic"><Icon name="check-circle" :size="32" /></div>
      <h3 class="mb8">Đã nhập danh mục vật tư thành công</h3>
      <p>Tạo mới: <b>{{ result.tao_moi }}</b> · Cập nhật: <b>{{ result.cap_nhat }}</b></p>
      <div class="flex wrap jc-c mt16">
        <button class="btn" @click="goToDanhMuc">Xem danh mục</button>
        <button class="btn-o" @click="startOver"><Icon name="upload" :size="16" />Nhập thêm tệp khác</button>
      </div>
    </div>

    <template v-else>
      <!-- Bước 1: tải mẫu -->
      <div class="card mb10">
        <div class="sb wrap gap12">
          <div class="buoc-hd grow">
            <span class="buoc-so" :class="lopBuoc[1]">
              <Icon v-if="lopBuoc[1] === 'done'" name="check" :size="15" />
              <template v-else>1</template>
            </span>
            <div class="buoc-tt">
              <b>Bước 1 · Tải tệp mẫu</b>
              <p class="tag mt4">
                Gồm các cột: Mã vật tư, Tên vật tư, ĐVT, Mã hàng Miyano, Quy cách, Nhóm, Đang dùng.
                Mẫu chính là bản xuất danh mục hiện tại — sửa trực tiếp trên đó rồi tải lên lại.
              </p>
            </div>
          </div>
          <a :href="templateUrl" class="btn-o btn-sm" download><Icon name="download" :size="16" />Tải mẫu Excel</a>
        </div>
      </div>

      <!-- Bước 2: chọn & xem trước -->
      <div class="card mb10">
        <div class="buoc-hd">
          <span class="buoc-so" :class="lopBuoc[2]">
            <Icon v-if="lopBuoc[2] === 'done'" name="check" :size="15" />
            <template v-else>2</template>
          </span>
          <b class="buoc-tt">Bước 2 · Chọn tệp đã sửa và xem trước</b>
        </div>
        <div class="buoc-body">
          <div class="flex wrap mt10">
            <input ref="fileInput" type="file" accept=".xlsx" class="chon-tep" @change="onPickFile" />
            <button class="btn" :disabled="!selectedFile || previewing" @click="onPreview">
              <Icon name="eye" :size="16" />{{ previewing ? 'Đang đọc tệp…' : 'Xem trước' }}
            </button>
          </div>
          <p v-if="previewError" class="warn mt10">{{ previewError }}</p>
        </div>
      </div>

      <!-- Bước 3: kết quả xem trước -->
      <div v-if="preview" class="card mb10">
        <div class="buoc-hd">
          <span class="buoc-so" :class="lopBuoc[3]">
            <Icon v-if="lopBuoc[3] === 'done'" name="check" :size="15" />
            <template v-else>3</template>
          </span>
          <b class="buoc-tt">Bước 3 · Kết quả xem trước</b>
        </div>

        <div class="flex wrap gap8 mt10 buoc-body">
          <span class="badge b-blue">{{ preview.summary.tao_moi }} dòng tạo mới</span>
          <span class="badge b-green">{{ preview.summary.cap_nhat }} dòng cập nhật</span>
          <span v-if="preview.error_count" class="badge b-red">{{ preview.error_count }} dòng lỗi</span>
        </div>

        <!-- Danh sách lỗi -->
        <ImportErrorRows :rows="preview.rows_error" />

        <!-- Bảng dòng hợp lệ -->
        <div v-if="preview.rows_ok.length" class="mt10 mt14 tbl-scroll tall bang-xt">
          <table>
            <thead>
              <tr>
                <th class="right">Dòng</th>
                <th>Mã vật tư</th>
                <th>Tên vật tư</th>
                <th>ĐVT</th>
                <th>Quy cách</th>
                <th>Nhóm</th>
                <th>Đang dùng</th>
                <th>Hành động</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in preview.rows_ok" :key="row.line">
                <td class="right muted">{{ row.line }}</td>
                <td class="cell-code"><b>{{ row.ma_vat_tu }}</b></td>
                <td>{{ row.ten_vat_tu }}</td>
                <td>{{ row.dvt }}</td>
                <td>{{ row.quy_cach || '—' }}</td>
                <td>{{ row.nhom || '—' }}</td>
                <td>{{ row.active ? 'Có' : 'Không' }}</td>
                <td>
                  <span class="badge" :class="HANH_DONG_LABEL[row.hanh_dong].cls">
                    {{ HANH_DONG_LABEL[row.hanh_dong].text }}
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <div v-else class="empty">Không có dòng hợp lệ nào trong tệp này.</div>
      </div>

      <!-- Bước 4: xác nhận -->
      <div v-if="preview" class="card">
        <div class="buoc-hd">
          <span class="buoc-so" :class="lopBuoc[4]">4</span>
          <b class="buoc-tt">Bước 4 · Xác nhận nhập</b>
        </div>
        <div class="buoc-body">
          <p class="tag mt4">
            Xác nhận sẽ tạo mới hoặc cập nhật các vật tư trong danh mục theo tệp đã tải lên.
            Mã vật tư không đổi được qua tệp này; vật tư đã có phát sinh trong sổ mà tệp ghi ĐVT
            khác sẽ bị báo lỗi ngay ở bước xem trước.
          </p>
          <div class="flex wrap mt10">
            <button class="btn" :disabled="!canConfirm || committing" @click="onCommit">
              <Icon name="check" :size="16" />{{ committing ? 'Đang ghi…' : 'Xác nhận nhập' }}
            </button>
            <span v-if="preview.error_count" class="warn inline-flex">
              <Icon name="alert-circle" :size="14" />Còn {{ preview.error_count }} dòng lỗi — sửa tệp và xem trước lại trước khi xác nhận.
            </span>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
/* Trình tự bước thật của trình nhập Excel: tải mẫu → chọn tệp & xem trước →
   kết quả → xác nhận. Chấm số bên trái: đã qua (xanh lá, dấu tích), đang ở
   (Medical Blue), chưa tới (xám). Chữ "Bước N · …" giữ nguyên. */
.buoc-hd { display: flex; gap: 12px; align-items: flex-start; }
.buoc-so {
  width: 28px;
  height: 28px;
  min-width: 28px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  font-size: 13px;
  font-weight: 700;
  background: #eef1f5;
  color: var(--text-3);
  font-variant-numeric: tabular-nums;
}
.buoc-so.cur { background: var(--accent); color: #fff; box-shadow: 0 0 0 4px var(--accent-soft); }
.buoc-so.done { background: var(--ok); color: #fff; }
.buoc-tt { padding-top: 3px; }
.buoc-body { padding-left: 40px; }
.chon-tep { flex: 1; min-width: 0; max-width: 420px; }
.bang-xt { border: 1px solid var(--line); border-radius: var(--r-md); }
.jc-c { justify-content: center; }
@media (max-width: 900px) {
  .buoc-body { padding-left: 0; }
  .chon-tep { max-width: none; flex-basis: 100%; }
}
</style>
