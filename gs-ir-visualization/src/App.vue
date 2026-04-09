<script setup>
import { RouterView, useRoute } from 'vue-router'
import LuminaGS from './components/LuminaGS.vue'
import { computed } from 'vue'

const route = useRoute()

const isEditorPage = computed(() => route.name === 'editor')
</script>

<template>
  <div v-if="isEditorPage">
    <RouterView />
  </div>
  <LuminaGS v-else>
    <RouterView />
  </LuminaGS>
</template>

<style scoped>
</style>