<script setup>
import {
  NConfigProvider,
  NDialogProvider,
  NMessageProvider,
  darkTheme,
  zhCN,
  dateZhCN,
} from "naive-ui";
import { goldThemeOverrides } from "./theme";
import AppShell from "./components/AppShell.vue";
</script>

<template>
  <NConfigProvider
    :theme="darkTheme"
    :theme-overrides="goldThemeOverrides"
    :locale="zhCN"
    :date-locale="dateZhCN"
  >
    <NMessageProvider>
      <NDialogProvider>
        <AppShell />
      </NDialogProvider>
    </NMessageProvider>
  </NConfigProvider>
</template>
