<template>
  <section class="workbench-container">
    <div class="workbench-content">
      <!-- 统计卡片区域 -->
      <div class="stats-section">
        <div class="stats-grid">
          <div class="stat-card">
            <div class="stat-icon purple">
              <span class="iconify" data-icon="solar:folder-open-bold"></span>
            </div>
            <div class="stat-value">24</div>
            <div class="stat-label">总项目数</div>
          </div>
          <div class="stat-card">
            <div class="stat-icon blue">
              <span class="iconify" data-icon="solar:clock-circle-bold"></span>
            </div>
            <div class="stat-value">156h</div>
            <div class="stat-label">本月渲染时长</div>
          </div>
          <div class="stat-card">
            <div class="stat-icon green">
              <span class="iconify" data-icon="solar:database-bold"></span>
            </div>
            <div class="stat-value">1.2TB</div>
            <div class="stat-label">存储占用</div>
          </div>
          <div class="stat-card">
            <div class="stat-icon orange">
              <span class="iconify" data-icon="solar:user-bold"></span>
            </div>
            <div class="stat-value">85%</div>
            <div class="stat-label">服务器健康度</div>
          </div>
        </div>
      </div>
      
      <!-- 主要内容区域 -->
      <div class="main-content-grid">
        <div class="activity-panel">
          <h3 class="panel-title">最新动态</h3>
          <div class="activity-list">
            <div class="activity-item">
              <div class="activity-indicator purple"></div>
              <div class="activity-content">
                <p class="activity-text">项目 "智慧园区" 渲染完成</p>
                <p class="activity-time">2026-01-30 14:20</p>
              </div>
            </div>
            <div class="activity-item">
              <div class="activity-indicator blue"></div>
              <div class="activity-content">
                <p class="activity-text">系统更新：优化了 Gaussian Splatting 的 VRAM 回收机制</p>
                <p class="activity-time">2026-01-29 09:00</p>
              </div>
            </div>
          </div>
        </div>
        <div class="quick-links-panel">
          <h3 class="panel-title">快速链接</h3>
          <div class="links-grid">
            <button class="link-button" @click="navigateToTrain">
              <span class="iconify" data-icon="solar:document-add-linear"></span>
              <span class="link-text">新建渲染任务</span>
            </button>
            <button class="link-button" @click="navigateToProjects">
              <span class="iconify" data-icon="solar:library-linear"></span>
              <span class="link-text">查看模型</span>
            </button>
            <button class="link-button" @click="navigateToSettings">
              <span class="iconify" data-icon="solar:settings-linear"></span>
              <span class="link-text">系统设置</span>
            </button>
            <button class="link-button" @click="navigateToProgress">
              <span class="iconify" data-icon="solar:chart-linear"></span>
              <span class="link-text">性能监控</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>

<script>
import { useRouter } from 'vue-router'

export default {
  name: 'WorkbenchPage',
  setup() {
    const router = useRouter()
    
    const navigateToTrain = () => {
      router.push({ name: 'train' })
    }
    
    const navigateToProjects = () => {
      router.push({ name: 'projects' })
    }
    
    const navigateToSettings = () => {
      router.push({ name: 'settings' })
    }
    
    const navigateToProgress = () => {
      router.push({ name: 'progress' })
    }
    
    return {
      navigateToTrain,
      navigateToProjects,
      navigateToSettings,
      navigateToProgress
    }
  }
}
</script>

<style scoped>
.workbench-container {
  height: 100%;
  background-color: #f8fafc;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.workbench-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 1.5rem;
  overflow-y: auto;
  gap: 1.5rem;
  /* 确保没有额外的margin造成间隙 */
  margin: 0;
}

.stats-section {
  flex-shrink: 0;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(1, 1fr);
  gap: 1.5rem;
}

@media (min-width: 768px) {
  .stats-grid {
    grid-template-columns: repeat(4, 1fr);
  }
}

.stat-card {
  background: white;
  padding: 1.5rem;
  border-radius: 1rem;
  border: 1px solid #e2e8f0;
  box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  /* 确保卡片之间没有额外间隙 */
  margin: 0;
}

.stat-icon {
  margin-bottom: 0.5rem;
  font-size: 1.5rem;
}

.stat-icon.purple {
  color: #9333ea;
}

.stat-icon.blue {
  color: #3b82f6;
}

.stat-icon.green {
  color: #10b981;
}

.stat-icon.orange {
  color: #f97316;
}

.stat-value {
  font-size: 1.5rem;
  font-weight: 700;
  color: #1e293b;
  margin-bottom: 0.25rem;
}

.stat-label {
  font-size: 0.75rem;
  color: #94a3b8;
}

.main-content-grid {
  display: grid;
  grid-template-columns: repeat(1, 1fr);
  gap: 1.5rem;
  flex-grow: 1;
}

@media (min-width: 1024px) {
  .main-content-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

/* 面板样式 */
.activity-panel,
.quick-links-panel {
  background: white;
  padding: 1.5rem;
  border-radius: 1rem;
  border: 1px solid #e2e8f0;
  display: flex;
  flex-direction: column;
  box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
  /* 确保面板没有额外margin */
  margin: 0;
}

.panel-title {
  font-size: 1.125rem;
  font-weight: bold;
  color: #1e293b;
  margin-bottom: 1rem;
}

/* 活动列表 */
.activity-list {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  flex-grow: 1;
}

.activity-item {
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
  padding: 0.75rem;
  border-radius: 0.5rem;
  cursor: pointer;
  transition: background-color 0.2s ease;
}

.activity-item:hover {
  background-color: #f8fafc;
}

.activity-indicator {
  width: 0.5rem;
  height: 0.5rem;
  border-radius: 50%;
  margin-top: 0.5rem;
  flex-shrink: 0;
}

.activity-indicator.purple {
  background-color: #9333ea;
}

.activity-indicator.blue {
  background-color: #3b82f6;
}

.activity-content {
  flex: 1;
}

.activity-text {
  font-size: 0.875rem;
  font-weight: 500;
  margin-bottom: 0.25rem;
  color: #1e293b;
}

.activity-time {
  font-size: 0.75rem;
  color: #94a3b8;
}

/* 快速链接 */
.links-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 1rem;
  flex-grow: 1;
}

.link-button {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1rem;
  border: 1px solid #f1f5f9;
  border-radius: 0.75rem;
  background: transparent;
  cursor: pointer;
  transition: all 0.2s ease;
  height: 100%;
}

.link-button:hover {
  background-color: #f5f3ff;
  border-color: #ddd6fe;
}

.link-button .iconify {
  color: #9333ea;
  margin-right: 0.5rem;
}

.link-text {
  font-size: 0.875rem;
  font-weight: 500;
  color: #1e293b;
}
</style>