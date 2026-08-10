<script setup>
import { useRouter } from 'vue-router'
import api from '../api'
import { useIsMobile } from '../useMobile'
import { useImportWizard } from '../useImportWizard'
import ImportErrorRows from '../components/ImportErrorRows.vue'

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
    <h2 v-else style="margin-bottom: 4px">Nhập danh mục vật tư</h2>
    <p class="tag" v-if="isMobile" style="margin-bottom: 16px">
      Tải mẫu, sửa vật tư, xem trước rồi xác nhận.
    </p>

    <!-- Đã nhập xong -->
    <div v-if="result" class="card">
      <h3 style="margin-bottom: 8px">✅ Đã nhập danh mục vật tư thành công</h3>
      <p>Tạo mới: <b>{{ result.tao_moi }}</b> · Cập nhật: <b>{{ result.cap_nhat }}</b></p>
      <div class="flex" style="margin-top: 16px">
        <button class="btn" @click="goToDanhMuc">Xem danh mục</button>
        <button class="btn-o" @click="startOver">Nhập thêm tệp khác</button>
      </div>
    </div>

    <template v-else>
      <!-- Bước 1: tải mẫu -->
      <div class="card mb10">
        <div class="sb">
          <div>
            <b>Bước 1 · Tải tệp mẫu</b>
            <p class="tag" style="margin-top: 4px">
              Gồm các cột: Mã vật tư, Tên vật tư, ĐVT, Mã hàng Miyano, Quy cách, Nhóm, Đang dùng.
              Mẫu chính là bản xuất danh mục hiện tại — sửa trực tiếp trên đó rồi tải lên lại.
            </p>
          </div>
          <a :href="templateUrl" class="btn-o btn-sm" download>⬇ Tải mẫu Excel</a>
        </div>
      </div>

      <!-- Bước 2: chọn & xem trước -->
      <div class="card mb10">
        <b>Bước 2 · Chọn tệp đã sửa và xem trước</b>
        <div class="flex" style="margin-top: 10px; flex-wrap: wrap">
          <input ref="fileInput" type="file" accept=".xlsx" @change="onPickFile" />
          <button class="btn" :disabled="!selectedFile || previewing" @click="onPreview">
            {{ previewing ? 'Đang đọc tệp…' : 'Xem trước' }}
          </button>
        </div>
        <p v-if="previewError" class="warn" style="margin-top: 10px">{{ previewError }}</p>
      </div>

      <!-- Bước 3: kết quả xem trước -->
      <div v-if="preview" class="card mb10">
        <b>Bước 3 · Kết quả xem trước</b>

        <div class="flex" style="margin-top: 10px; flex-wrap: wrap; gap: 8px">
          <span class="badge b-blue">{{ preview.summary.tao_moi }} dòng tạo mới</span>
          <span class="badge b-green">{{ preview.summary.cap_nhat }} dòng cập nhật</span>
          <span v-if="preview.error_count" class="badge b-red">{{ preview.error_count }} dòng lỗi</span>
        </div>

        <!-- Danh sách lỗi -->
        <ImportErrorRows :rows="preview.rows_error" />

        <!-- Bảng dòng hợp lệ -->
        <div v-if="preview.rows_ok.length" class="mt10" style="margin-top: 14px; overflow-x: auto">
          <table>
            <thead>
              <tr>
                <th>Dòng</th>
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
                <td>{{ row.line }}</td>
                <td><b>{{ row.ma_vat_tu }}</b></td>
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
        <b>Bước 4 · Xác nhận nhập</b>
        <p class="tag" style="margin-top: 4px">
          Xác nhận sẽ tạo mới hoặc cập nhật các vật tư trong danh mục theo tệp đã tải lên.
          Mã vật tư không đổi được qua tệp này; vật tư đã có phát sinh trong sổ mà tệp ghi ĐVT
          khác sẽ bị báo lỗi ngay ở bước xem trước.
        </p>
        <button class="btn" style="margin-top: 10px" :disabled="!canConfirm || committing" @click="onCommit">
          {{ committing ? 'Đang ghi…' : 'Xác nhận nhập' }}
        </button>
        <span v-if="preview.error_count" class="warn" style="margin-left: 10px">
          Còn {{ preview.error_count }} dòng lỗi — sửa tệp và xem trước lại trước khi xác nhận.
        </span>
      </div>
    </template>
  </div>
</template>
