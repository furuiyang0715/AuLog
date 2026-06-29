<script setup>
import { ref } from "vue";
import {
  NButton,
  NCard,
  NForm,
  NFormItem,
  NInput,
  NTabs,
  NTabPane,
} from "naive-ui";

const props = defineProps({
  loading: { type: Boolean, default: false },
});

const emit = defineEmits(["success"]);

const mode = ref("login");
const form = ref({ username: "", password: "" });

function submit() {
  emit("success", {
    mode: mode.value,
    username: form.value.username.trim(),
    password: form.value.password,
  });
  form.value.password = "";
}
</script>

<template>
  <div class="auth-screen">
    <NCard class="auth-card" title="AuLog" :bordered="false">
      <p class="hint-text">实物金倒 T 账本 · 登录后使用</p>
      <NTabs v-model:value="mode" type="segment" animated>
        <NTabPane name="login" tab="登录" />
        <NTabPane name="register" tab="注册" />
      </NTabs>
      <NForm @submit.prevent="submit">
        <NFormItem label="用户名">
          <NInput
            v-model:value="form.username"
            placeholder="至少 3 个字符"
            autocomplete="username"
          />
        </NFormItem>
        <NFormItem label="密码">
          <NInput
            v-model:value="form.password"
            type="password"
            show-password-on="click"
            placeholder="至少 6 个字符"
            :autocomplete="mode === 'login' ? 'current-password' : 'new-password'"
          />
        </NFormItem>
        <NButton type="primary" attr-type="submit" block :loading="loading">
          {{ mode === "login" ? "登录" : "注册" }}
        </NButton>
      </NForm>
    </NCard>
  </div>
</template>

<style scoped>
.auth-screen {
  display: flex;
  justify-content: center;
  padding: 3rem 1rem;
}

.auth-card {
  width: 100%;
  max-width: 420px;
}
</style>
