<template>
  <section class="settings-container">
    <div class="settings-content">
      <h2 class="page-title">偏好设置</h2>
      <div class="settings-form">
        <div class="settings-section">
          <h4 class="section-title">渲染引擎</h4>
          <div class="engine-options">
            <div 
              class="engine-option" 
              :class="{ 'selected': renderingEngine === 'cuda' }"
              @click="setRenderingEngine('cuda')"
            >
              <div class="option-header">
                <span class="iconify engine-icon" data-icon="solar:bolt-bold"></span>
                <span class="option-title">Cuda Acceleration</span>
              </div>
              <p class="option-description">使用原生 CUDA 内核进行高并发高斯投影，性能最高。</p>
            </div>
            <div 
              class="engine-option" 
              :class="{ 'selected': renderingEngine === 'webui' }"
              @click="showWebUINotAvailable"
            >
              <div class="option-header">
                <span class="iconify engine-icon" data-icon="solar:globus-linear"></span>
                <span class="option-title">WebUI Mode</span>
              </div>
              <p class="option-description">兼容模式，适用于远程预览或显存受限场景。</p>
            </div>
          </div>
        </div>
        <div class="actions-footer">
          <button class="reset-btn" @click="resetSettings">重置</button>
          <button class="apply-btn" @click="applySettings">应用更改</button>
        </div>
      </div>
    </div>
    <div v-if="webUINoticeVisible" class="notice-dialog-overlay" @click="closeWebUINotice">
      <div class="notice-dialog" @click.stop>
        <div class="dialog-header">
          <h3 class="dialog-title">提示</h3>
        </div>
        <div class="dialog-content">
          <div class="notice-content">
            <span class="iconify notice-icon" data-icon="solar:info-circle-bold"></span>
            <p class="notice-text">该功能暂不可用</p>
          </div>
        </div>
        <div class="dialog-footer">
          <button class="btn-confirm-notice" @click="closeWebUINotice">确定</button>
        </div>
      </div>
    </div>
  </section>
</template>

<script>
export default {
  name: 'SettingsPage',
  data() {
    return {
      renderingEngine: 'cuda',
      autoSaveEnabled: true,
      cacheDirectory: '/home/user/.cache/luminags',
      webUINoticeVisible: false
    }
  },
  methods: {
    setRenderingEngine(engine) {
      this.renderingEngine = engine;
    },
    toggleAutoSave() {
      this.autoSaveEnabled = !this.autoSaveEnabled;
    },
    changeCacheDirectory() {
      console.log('更改缓存目录');
    },
    showWebUINotAvailable() {
      this.webUINoticeVisible = true;
    },
    closeWebUINotice() {
      this.webUINoticeVisible = false;
    },
    resetSettings() {
      this.renderingEngine = 'cuda';
      this.autoSaveEnabled = true;
      console.log('重置设置');
    },
    applySettings() {
      console.log('应用设置');
    }
  }
}
</script>

<style scoped>
.settings-container {
  height: 100%;
  background-color: white;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.settings-content {
  flex: 1;
  padding: 1.5rem;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  max-width: 48rem;
  margin: 0 auto;
  width: 100%;
}

.page-title {
  font-size: 1.5rem;
  font-weight: bold;
  color: #1e293b;
  margin-bottom: 2rem;
  font-family: ui-sans-serif, system-ui, sans-serif;
}

.settings-form {
  display: flex;
  flex-direction: column;
  gap: 2rem;
  flex-grow: 1;
}

.settings-section {
  padding-bottom: 2rem;
  border-bottom: 1px solid #f1f5f9;
}

.settings-section:last-child {
  border-bottom: none;
  padding-bottom: 0;
}

.section-title {
  font-size: 0.875rem;
  font-weight: bold;
  color: #1e293b;
  margin-bottom: 1rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.engine-options {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
}

.engine-option {
  border: 2px solid #e2e8f0;
  padding: 1rem;
  border-radius: 0.75rem;
  cursor: pointer;
  transition: all 0.2s ease;
}

.engine-option:hover {
  border-color: #cbd5e1;
}

.engine-option.selected {
  border-color: #7e22ce;
  background-color: #f5f3ff;
}

.option-header {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-bottom: 0.5rem;
}

.engine-icon {
  font-size: 1.25rem;
}

.engine-option.selected .engine-icon {
  color: #7e22ce;
}

.option-title {
  font-weight: bold;
  color: #1e293b;
}

.engine-option.selected .option-title {
  color: #7e22ce;
}

.option-description {
  font-size: 0.6875rem;
  color: #94a3b8;
}

.settings-list {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.setting-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.setting-info {
  flex: 1;
}

.setting-label {
  font-size: 0.875rem;
  font-weight: 500;
  color: #334155;
  margin-bottom: 0.25rem;
}

.setting-description {
  font-size: 0.75rem;
  color: #94a3b8;
}

.toggle-switch {
  width: 3rem;
  height: 1.5rem;
  background-color: #7e22ce;
  border-radius: 9999px;
  position: relative;
  cursor: pointer;
  transition: background-color 0.2s ease;
}

.toggle-switch.enabled {
  background-color: #7e22ce;
}

.toggle-switch:not(.enabled) {
  background-color: #cbd5e1;
}

.toggle-handle {
  position: absolute;
  top: 0.125rem;
  width: 1.25rem;
  height: 1.25rem;
  background-color: white;
  border-radius: 50%;
  transition: all 0.2s ease;
  left: 0.125rem;
}

.toggle-switch.enabled .toggle-handle {
  left: 1.625rem;
}

.change-btn {
  color: #7e22ce;
  font-size: 0.75rem;
  font-weight: bold;
  padding: 0.25rem 0.75rem;
  background-color: #f5f3ff;
  border-radius: 0.25rem;
  border: none;
  cursor: pointer;
}

.actions-footer {
  display: flex;
  justify-content: flex-end;
  gap: 1rem;
  margin-top: auto;
  padding-top: 2rem;
}

.reset-btn {
  padding: 0.5rem 1.5rem;
  color: #64748b;
  font-weight: 500;
  border: none;
  background: transparent;
  cursor: pointer;
  border-radius: 0.5rem;
}

.apply-btn {
  padding: 0.5rem 1.5rem;
  background-color: #7e22ce;
  color: white;
  border-radius: 0.5rem;
  font-weight: 500;
  border: none;
  cursor: pointer;
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
  transition: background-color 0.2s ease;
}

.apply-btn:hover {
  background-color: #6b21a8;
}

.notice-dialog-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 10000;
  animation: overlayFadeIn 0.2s ease;
}

@keyframes overlayFadeIn {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

.notice-dialog {
  background: white;
  border-radius: 1rem;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3), 0 0 0 1px rgba(0, 0, 0, 0.05);
  width: 100%;
  max-width: 400px;
  animation: dialogSlideIn 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
  overflow: hidden;
}

@keyframes dialogSlideIn {
  from {
    opacity: 0;
    transform: translateY(-20px) scale(0.95);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

.dialog-header {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1.5rem 1.5rem 0 1.5rem;
  margin-bottom: 1rem;
}

.dialog-title {
  font-size: 1.25rem;
  font-weight: 600;
  color: #1e293b;
  margin: 0;
}

.dialog-content {
  padding: 0 1.5rem 1.5rem 1.5rem;
}

.notice-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1rem;
  padding: 1rem 0;
}

.notice-icon {
  font-size: 3rem;
  color: #f59e0b;
}

.notice-text {
  font-size: 1rem;
  color: #475569;
  margin: 0;
  text-align: center;
}

.dialog-footer {
  display: flex;
  justify-content: center;
  padding: 1rem 1.5rem 1.5rem 1.5rem;
  background-color: #f8fafc;
  border-top: 1px solid #e2e8f0;
}

.btn-confirm-notice {
  padding: 0.625rem 1.5rem;
  font-size: 0.875rem;
  font-weight: 500;
  border-radius: 0.5rem;
  border: none;
  cursor: pointer;
  transition: all 0.2s ease;
  background-color: #7e22ce;
  color: white;
}

.btn-confirm-notice:hover {
  background-color: #6b21a8;
}

@media (max-width: 768px) {
  .engine-options {
    grid-template-columns: 1fr;
  }
  
  .settings-content {
    padding: 1rem;
  }
}
</style>