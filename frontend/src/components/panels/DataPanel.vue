<script setup>
import { inject, ref } from "vue";
import {
  NAlert,
  NButton,
  NCard,
  NSpace,
  NText,
  NUpload,
  useDialog,
  useMessage,
} from "naive-ui";
import { apiDownload, apiUpload } from "../../api/client";

const ledger = inject("ledger");
const message = useMessage();
const dialog = useDialog();

const exporting = ref(false);
const importing = ref(false);
const selectedFile = ref(null);

async function handleExport() {
  exporting.value = true;
  try {
    await apiDownload("/data/export");
    message.success("备份已下载");
  } catch (err) {
    message.error(err.message || "导出失败");
  } finally {
    exporting.value = false;
  }
}

function handleFileChange({ file }) {
  selectedFile.value = file?.file || null;
}

function handleRestore() {
  const file = selectedFile.value;
  if (!file) {
    message.warning("请先选择备份文件");
    return;
  }
  if (!file.name.toLowerCase().endsWith(".json")) {
    message.warning("请选择 .json 备份文件");
    return;
  }

  dialog.warning({
    title: "确认恢复备份",
    content:
      "恢复将删除当前账号下的全部账本数据，并用备份文件内容覆盖。此操作不可撤销，是否继续？",
    positiveText: "确认恢复",
    negativeText: "取消",
    onPositiveClick: () => performImport(file),
  });
}

async function performImport(file) {
  importing.value = true;
  try {
    const result = await apiUpload("/data/import", file);
    await ledger.refreshAll();
    selectedFile.value = null;

    const counts = result.counts || {};
    const summary = [
      `倒T ${counts.t_records ?? 0} 条`,
      `进货 ${counts.ing_records ?? 0} 条`,
      `selled ${counts.selled_records ?? 0} 条`,
      `分配 ${counts.ing_allocations ?? 0} 条`,
    ].join("，");

    if (
      result.backup_username &&
      result.current_username &&
      result.backup_username !== result.current_username
    ) {
      message.success(
        `已恢复备份（来源用户 ${result.backup_username}）：${summary}`
      );
    } else {
      message.success(`恢复成功：${summary}`);
    }
  } catch (err) {
    message.error(err.message || "恢复失败");
  } finally {
    importing.value = false;
  }
}
</script>

<template>
  <NSpace vertical :size="16">
    <NAlert type="info" :bordered="false">
      导出当前账号的全部账本数据为 JSON 备份；恢复时会<strong>覆盖</strong>现有数据，请先导出一份最新备份。
    </NAlert>

    <NCard title="导出存档" size="small">
      <NSpace vertical :size="12">
        <NText depth="3">
          包含倒 T、进货、selled、分配记录，可用于换机迁移或本地备份。
        </NText>
        <NButton type="primary" :loading="exporting" @click="handleExport">
          下载备份文件
        </NButton>
      </NSpace>
    </NCard>

    <NCard title="从备份恢复" size="small">
      <NSpace vertical :size="12">
        <NText depth="3">
          上传此前导出的 JSON 文件，将覆盖当前账号下的全部个人数据。
        </NText>
        <NUpload
          :max="1"
          accept=".json,application/json"
          :default-upload="false"
          @change="handleFileChange"
        >
          <NButton>选择备份文件</NButton>
        </NUpload>
        <NButton
          type="warning"
          :loading="importing"
          :disabled="!selectedFile"
          @click="handleRestore"
        >
          覆盖恢复
        </NButton>
      </NSpace>
    </NCard>
  </NSpace>
</template>
