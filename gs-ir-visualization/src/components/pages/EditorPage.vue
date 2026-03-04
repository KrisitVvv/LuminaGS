<template>
  <section class="editor-container">
    <!-- 左侧功能面板 -->
    <div class="sidebar">
      <!-- 模型管理区域 -->
      <div class="sidebar-section">
        <div class="section-header">
          <h2 class="section-title">模型列表</h2>
        </div>
        <div class="model-list">
          <div 
            v-for="model in models" 
            :key="model.id"
            class="model-item"
            :class="{ 'active': activeModel === model.id }"
            @click="selectModel(model.id)"
          >
            <div class="model-icon">
              <span class="iconify" :data-icon="model.icon"></span>
            </div>
            <div class="model-info">
              <div class="model-name">{{ model.name }}.<span class="extension">{{ model.extension }}</span></div>
            </div>
          </div>
        </div>
        <button class="import-btn" @click="openImportDialog">
          <span class="iconify" data-icon="solar:add-circle-bold"></span>
          导入模型
        </button>
      </div>

      <!-- 参数控制区域 -->
      <div class="sidebar-section">
        <div class="section-header">
          <h2 class="section-title">参数控制</h2>
        </div>
        
        <!-- 光照控制 -->
        <div class="control-group">
          <div class="group-title">光照调节</div>
          <div class="control-item">
            <label class="control-label">光线亮度</label>
            <div class="slider-container">
              <input class="slider" type="range" v-model="lightIntensity" min="0" max="100">
              <span class="slider-value">{{ lightIntensity }}%</span>
            </div>
          </div>
          <div class="control-item">
            <label class="control-label">光线倾角</label>
            <div class="slider-container">
              <input class="slider" type="range" v-model="lightPitch" min="0" max="90">
              <span class="slider-value">{{ lightPitch }}°</span>
            </div>
          </div>
          <div class="control-item">
            <label class="control-label">光线偏角</label>
            <div class="slider-container">
              <input class="slider" type="range" v-model="lightYaw" min="0" max="360">
              <span class="slider-value">{{ lightYaw }}°</span>
            </div>
          </div>
        </div>

        <!-- 场景控制 -->
        <div class="control-group">
          <div class="group-title">场景参数</div>
          <div class="control-item">
            <label class="control-label">点云密度</label>
            <div class="slider-container">
              <input class="slider" type="range" v-model="gaussianDensity" min="10" max="100">
              <span class="slider-value">{{ gaussianDensity }}%</span>
            </div>
          </div>
        </div>

        <!-- 效果开关 -->
        <div class="control-group">
          <div class="group-title">后期效果</div>
          <div class="toggle-item">
            <span class="toggle-label">全局光照 (SSGI)</span>
            <label class="switch">
              <input type="checkbox" v-model="ssgiEnabled">
              <span class="slider-toggle"></span>
            </label>
          </div>
          <div class="toggle-item">
            <span class="toggle-label">景深控制 (DoF)</span>
            <label class="switch">
              <input type="checkbox" v-model="dofEnabled">
              <span class="slider-toggle"></span>
            </label>
          </div>
        </div>
      </div>
    </div>

    <!-- 主视图区域 -->
    <div class="main-view">
      <div class="viewport">
        <img alt="3DGS Real-time Rendering Viewport" class="viewport-image" src="https://modao.cc/agent-py/media/generated_images/2026-01-30/13470a0341134dabbdfa3d0aeda0fad5.jpg">
        <div class="viewport-overlay">
          <div class="overlay-content">
            <span class="iconify camera-icon" data-icon="solar:camera-minimalistic-bold"></span>
            <p class="viewport-title">3DGS 模型查看器</p>
            <p class="current-model" v-if="selectedModel">{{ selectedModel.name }}.{{ selectedModel.extension }}</p>
          </div>
        </div>
      </div>
      
      <!-- 底部工具栏 -->
      <div class="toolbar">
        <div class="toolbar-group">
          <button class="tool-btn">
            <span class="iconify" data-icon="solar:move-bold"></span>
          </button>
          <button class="tool-btn">
            <span class="iconify" data-icon="solar:rotate-bold"></span>
          </button>
          <button class="tool-btn">
            <span class="iconify" data-icon="solar:scale-bold"></span>
          </button>
        </div>
        <div class="toolbar-group">
          <button class="tool-btn">
            <span class="iconify" data-icon="solar:refresh-bold"></span>
          </button>
          <router-link class="tool-btn back-btn" :to="{name: 'projects'}">
            <span class="iconify" data-icon="solar:backspace-bold"></span>
            返回项目
          </router-link>
        </div>
      </div>
    </div>

    <!-- 导入对话框 -->
    <div class="modal" v-if="showImportDialog" @click="closeImportDialog">
      <div class="modal-content" @click.stop>
        <h3 class="modal-title">导入模型</h3>
        <div class="import-options">
          <div class="import-option" @click="importFromFile">
            <span class="iconify option-icon" data-icon="solar:folder-with-files-bold"></span>
            <div class="option-text">
              <div class="option-title">从文件导入</div>
              <div class="option-desc">支持PLY、OBJ等3D文件格式</div>
            </div>
          </div>
          <div class="import-option" @click="importFromFolder">
            <span class="iconify option-icon" data-icon="solar:folder-open-bold"></span>
            <div class="option-text">
              <div class="option-title">从文件夹导入</div>
              <div class="option-desc">批量导入整个文件夹</div>
            </div>
          </div>
          <div class="import-option" @click="importSample">
            <span class="iconify option-icon" data-icon="solar:server-square-cloud-bold"></span>
            <div class="option-text">
              <div class="option-title">导入示例</div>
              <div class="option-desc">使用内置示例模型</div>
            </div>
          </div>
        </div>
        <div class="modal-actions">
          <button class="cancel-btn" @click="closeImportDialog">取消</button>
        </div>
      </div>
    </div>
  </section>
</template>

<script>
import { RouterLink } from 'vue-router'

export default {
  name: 'EditorPage',
  components: {
    RouterLink
  },
  data() {
    return {
      lightIntensity: 80,
      lightPitch: 45,
      lightYaw: 120,
      gaussianDensity: 75,
      ssgiEnabled: true,
      dofEnabled: false,
      activeModel: 1,
      showImportDialog: false,
      models: [
        {
          id: 1,
          name: 'fused',
          extension: 'ply',
          icon: 'solar:document-bold' // 统一使用文件图标
        },
        {
          id: 2,
          name: 'night_scene',
          extension: 'ply',
          icon: 'solar:document-bold' // 统一使用文件图标
        },
        {
          id: 3,
          name: 'factory_model',
          extension: 'ply',
          icon: 'solar:document-bold' // 统一使用文件图标
        }
      ],
      projectData: {
        1: {
          name: '智慧园区 - A区数字化',
          description: '工业园区3D重建与重光照项目'
        },
        2: {
          name: '城市夜景重光照',
          description: '城市建筑夜景照明效果优化'
        },
        3: {
          name: '工业厂房资产库',
          description: '工厂设施数字化资产管理'
        }
      }
    }
  },
  computed: {
    selectedModel() {
      return this.models.find(model => model.id === this.activeModel)
    },
    currentProject() {
      const projectId = this.$route.params.projectId
      return this.projectData[projectId]
    }
  },
  methods: {
    selectModel(modelId) {
      this.activeModel = modelId
    },
    openImportDialog() {
      this.showImportDialog = true
    },
    closeImportDialog() {
      this.showImportDialog = false
    },
    importFromFile() {
      console.log('从文件导入')
      this.closeImportDialog()
    },
    importFromFolder() {
      console.log('从文件夹导入')
      this.closeImportDialog()
    },
    importSample() {
      console.log('导入示例模型')
      this.closeImportDialog()
    }
  },
  mounted() {
    const projectId = this.$route.params.projectId
    if (projectId) {
      console.log('加载项目:', projectId)
    }
  },
  watch: {
    '$route'(to) {
      const projectId = to.params.projectId
      if (projectId) {
        console.log('切换到项目:', projectId)
      }
    }
  }
}
</script>

<style scoped>
.editor-container {
  height: 100%;
  display: flex;
  background-color: #ffffff;
  color: #1e293b;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

/* 侧边栏样式 - 整体滚动 */
.sidebar {
  width: 280px;
  background: #ffffff;
  border-right: 1px solid #e2e8f0;
  display: flex;
  flex-direction: column;
  overflow-y: auto;
  box-shadow: 2px 0 10px rgba(0, 0, 0, 0.05);
}

.sidebar-section {
  padding: 1.5rem;
  border-bottom: 1px solid #f1f5f9;
}

.sidebar-section:last-child {
  border-bottom: none;
}

/* 移除参数控制区域的独立滚动设置 */
/* .controls-section {
  flex: 1;
  overflow-y: auto;
  min-height: 0;
} */

.section-header {
  margin-bottom: 1.25rem;
}

.section-title {
  font-size: 1rem;
  font-weight: 600;
  color: #475569;
  margin: 0;
}

/* 模型列表样式 */
.model-list {
  margin-bottom: 1.5rem;
}

.model-item {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.75rem;
  margin-bottom: 0.5rem;
  background: #f8fafc;
  border-radius: 0.5rem;
  cursor: pointer;
  transition: all 0.2s ease;
  border: 1px solid transparent;
}

.model-item:hover {
  background: #f1f5f9;
  border-color: #e2e8f0;
}

.model-item.active {
  background: #f5f3ff;
  border-color: #c084fc;
  box-shadow: 0 2px 8px rgba(126, 34, 206, 0.1);
}

.model-icon {
  font-size: 1.25rem;
  color: #7e22ce;
}

.model-info {
  flex: 1;
}

.model-name {
  font-size: 0.875rem;
  font-weight: 500;
  color: #1e293b;
}

.extension {
  color: #7e22ce;
  font-weight: 600;
}

.import-btn {
  width: 100%;
  padding: 0.75rem;
  background: #7e22ce;
  color: white;
  border: none;
  border-radius: 0.5rem;
  font-size: 0.875rem;
  font-weight: 500;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  transition: all 0.2s ease;
}

.import-btn:hover {
  background: #6d1bb0;
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(126, 34, 206, 0.2);
}

/* 控制组样式 */
.control-group {
  margin-bottom: 1.5rem;
}

.control-group:last-child {
  margin-bottom: 0;
}

.group-title {
  font-size: 0.875rem;
  font-weight: 600;
  color: #64748b;
  margin-bottom: 1rem;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.control-item {
  margin-bottom: 1rem;
}

.control-item:last-child {
  margin-bottom: 0;
}

.control-label {
  display: block;
  font-size: 0.8125rem;
  color: #475569;
  margin-bottom: 0.5rem;
  font-weight: 500;
}

.slider-container {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.slider {
  flex: 1;
  height: 6px;
  border-radius: 3px;
  background: #e2e8f0;
  outline: none;
  -webkit-appearance: none;
}

.slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  appearance: none;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: #7e22ce;
  cursor: pointer;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  border: 2px solid #ffffff;
}

.slider::-moz-range-thumb {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: #7e22ce;
  cursor: pointer;
  border: 2px solid #ffffff;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.slider-value {
  font-size: 0.75rem;
  color: #94a3b8;
  min-width: 40px;
  text-align: right;
  font-weight: 500;
}

/* 开关样式 */
.toggle-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.75rem;
  background: #f8fafc;
  border-radius: 0.5rem;
  margin-bottom: 0.75rem;
  border: 1px solid #e2e8f0;
}

.toggle-item:last-child {
  margin-bottom: 0;
}

.toggle-label {
  font-size: 0.875rem;
  color: #1e293b;
  font-weight: 500;
}

.switch {
  position: relative;
  display: inline-block;
  width: 44px;
  height: 24px;
}

.switch input {
  opacity: 0;
  width: 0;
  height: 0;
}

.slider-toggle {
  position: absolute;
  cursor: pointer;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: #cbd5e1;
  transition: .3s;
  border-radius: 24px;
}

.slider-toggle:before {
  position: absolute;
  content: "";
  height: 20px;
  width: 20px;
  left: 2px;
  bottom: 2px;
  background-color: white;
  transition: .3s;
  border-radius: 50%;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

input:checked + .slider-toggle {
  background-color: #7e22ce;
}

input:checked + .slider-toggle:before {
  transform: translateX(20px);
}

/* 主视图区域 */
.main-view {
  flex: 1;
  display: flex;
  flex-direction: column;
  position: relative;
  background: transparent;
}

.viewport {
  flex: 1;
  position: relative;
  overflow: hidden;
}

.viewport-image {
  width: 100%;
  height: 100%;
  object-fit: cover;
  opacity: 0.9;
}

.viewport-overlay {
 
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.3);
}

.overlay-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  padding: 2rem;
  border-radius: 1rem;
}

.camera-icon {
  font-size: 3rem;
  color: #7e22ce;
  margin-bottom: 1rem;
  animation: pulse 2s infinite;
}

.viewport-title {
  font-size: 1.5rem;
  font-weight: bold;
  color: #475569;
  margin-bottom: 0.5rem;
  letter-spacing: 1px;
}

.current-model {
  font-size: 1.125rem;
  font-weight: bold;
  color: #7e22ce;
}

/* 工具栏 */
.toolbar {
  padding: 1rem 1.5rem;
  background: rgba(255, 255, 255, 0.9);
  border-top: 1px solid #e2e8f0;
  display: flex;
  justify-content: space-between;
  align-items: center;
  backdrop-filter: blur(10px);
}

.toolbar-group {
  display: flex;
  gap: 0.5rem;
}

.tool-btn {
  padding: 0.5rem 1rem;
  background: #f8fafc;
  color: #475569;
  border: 1px solid #e2e8f0;
  border-radius: 0.375rem;
  font-size: 0.8125rem;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  transition: all 0.2s ease;
}

.tool-btn:hover {
  background: #f1f5f9;
  border-color: #c084fc;
  color: #7e22ce;
}

.back-btn {
  background: #fef2f2;
  border-color: #fecaca;
  color: #ef4444;
}

.back-btn:hover {
  background: #fee2e2;
  border-color: #fca5a5;
  color: #dc2626;
}

/* 模态对话框 */
.modal {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-content {
  background: #ffffff;
  border-radius: 0.75rem;
  padding: 2rem;
  width: 90%;
  max-width: 400px;
  border: 1px solid #e2e8f0;
  box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1);
}

.modal-title {
  font-size: 1.25rem;
  font-weight: 600;
  color: #1e293b;
  margin-bottom: 1.5rem;
  text-align: center;
}

.import-options {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  margin-bottom: 1.5rem;
}

.import-option {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 1rem;
  background: #f8fafc;
  border-radius: 0.5rem;
  cursor: pointer;
  transition: all 0.2s ease;
  border: 1px solid #e2e8f0;
}

.import-option:hover {
  background: #f1f5f9;
  border-color: #c084fc;
  box-shadow: 0 2px 8px rgba(126, 34, 206, 0.1);
}

.option-icon {
  font-size: 1.5rem;
  color: #7e22ce;
}

.option-text {
  flex: 1;
}

.option-title {
  font-size: 0.9375rem;
  font-weight: 500;
  color: #1e293b;
  margin-bottom: 0.25rem;
}

.option-desc {
  font-size: 0.75rem;
  color: #64748b;
}

.modal-actions {
  display: flex;
  justify-content: center;
}

.cancel-btn {
  padding: 0.5rem 1.5rem;
  background: #f1f5f9;
  color: #64748b;
  border: 1px solid #e2e8f0;
  border-radius: 0.375rem;
  cursor: pointer;
  font-size: 0.875rem;
  transition: all 0.2s ease;
}

.cancel-btn:hover {
  background: #e2e8f0;
  color: #475569;
}

@keyframes pulse {
  0%, 100% {
    opacity: 1;
    transform: scale(1);
  }
  50% {
    opacity: 0.7;
    transform: scale(1.05);
  }
}

/* 滚动条样式 - 应用于整个侧边栏 */
.sidebar::-webkit-scrollbar {
  width: 6px;
}

.sidebar::-webkit-scrollbar-track {
  background: #f1f5f9;
}

.sidebar::-webkit-scrollbar-thumb {
  background: #cbd5e1;
  border-radius: 3px;
}

.sidebar::-webkit-scrollbar-thumb:hover {
  background: #94a3b8;
}

/* 移除参数控制区域的独立滚动条样式 */
/* .controls-section::-webkit-scrollbar {
  width: 6px;
}

.controls-section::-webkit-scrollbar-track {
  background: #f1f5f9;
  border-radius: 3px;
}

.controls-section::-webkit-scrollbar-thumb {
  background: #cbd5e1;
  border-radius: 3px;
}

.controls-section::-webkit-scrollbar-thumb:hover {
  background: #94a3b8;
} */
</style>