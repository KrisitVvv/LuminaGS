<script setup>
import { RouterView, useRoute } from 'vue-router'
import LuminaGS from './components/LuminaGS.vue'
import { computed } from 'vue'

const route = useRoute()

// 判断是否是 EditorPage，如果是则不使用 LuminaGS 布局
const isEditorPage = computed(() => route.name === 'editor')
</script>

<template>
  <div v-if="isEditorPage">
    <!-- EditorPage 独立窗口模式，不使用主布局 -->
    <RouterView />
  </div>
  <LuminaGS v-else>
    <!-- 其他页面使用主布局 -->
    <RouterView />
  </LuminaGS>
</template>

<style scoped>
/* 组件样式已在LuminaGS.vue中定义 */
</style>