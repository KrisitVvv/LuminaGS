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
            <div class="stat-value">{{ projectCount }}</div>
            <div class="stat-label">总项目数</div>
          </div>
          <div class="stat-card">
            <div class="stat-icon blue">
              <span class="iconify" data-icon="solar:clock-circle-bold"></span>
            </div>
            <div class="stat-value">{{ renderHours }}h</div>
            <div class="stat-label">本月渲染时长</div>
          </div>
          <div class="stat-card">
            <div class="stat-icon green">
              <span class="iconify" data-icon="solar:database-bold"></span>
            </div>
            <div class="stat-value">{{ storageSize }}</div>
            <div class="stat-label">存储占用</div>
          </div>
        </div>
      </div>
      
      <!-- 主要内容区域 -->
      <div class="main-content-grid">
        <div class="activity-panel">
          <h3 class="panel-title">最新动态</h3>
          <div class="activity-list" v-if="recentActivities.length > 0">
            <div 
              v-for="(activity, index) in recentActivities" 
              :key="index"
              class="activity-item"
            >
              <div class="activity-indicator" :class="activity.color"></div>
              <div class="activity-content">
                <p class="activity-text">{{ activity.text }}</p>
                <p class="activity-time">{{ activity.time }}</p>
              </div>
            </div>
          </div>
          <div v-else class="empty-activities">
            <p>暂无动态</p>
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
import { ref, onMounted } from 'vue'

export default {
  name: 'WorkbenchPage',
  setup() {
    const router = useRouter()
    const projectCount = ref(0)
    const renderHours = ref(0)
    const storageSize = ref('0 GB')
    const recentActivities = ref([])
    
    // 加载统计数据
    const loadStats = async () => {
      try {
        const result = await window.electronAPI.getProjectList()
        if (!result.success) {
          console.error('[Workbench] 获取项目列表失败:', result.error)
          return
        }
        
        const projects = result.data || []
        const completedProjects = projects.filter(p => p.status === 'completed')
        projectCount.value = completedProjects.length
        
        // 计算本月渲染时长（从项目的training_time累加）
        const now = new Date()
        const currentMonth = now.getMonth()
        const currentYear = now.getFullYear()
        
        let totalSeconds = 0
        for (const project of completedProjects) {
          if (project.training_time) {
            // 检查是否是本月的项目（简单判断：如果有lastModified时间）
            if (project.lastModified) {
              const modifiedDate = new Date(project.lastModified)
              if (modifiedDate.getMonth() === currentMonth && 
                  modifiedDate.getFullYear() === currentYear) {
                totalSeconds += project.training_time
              }
            } else {
              // 如果没有lastModified，全部计入
              totalSeconds += project.training_time
            }
          }
        }
        
        // 转换为小时（保留1位小数）
        renderHours.value = (totalSeconds / 3600).toFixed(1)
        
        // 计算存储占用 - 遍历所有已完成项目的 output 目录
        let totalBytes = 0
        for (const project of completedProjects) {
          try {
            // 使用 Electron API 获取项目输出目录大小
            const sizeResult = await window.electronAPI.getDirectorySize(project.outputPath)
            if (sizeResult.success) {
              totalBytes += sizeResult.data
            }
          } catch (err) {
            console.warn(`[Workbench] 无法获取项目 ${project.name} 的大小:`, err)
          }
        }
        
        // 格式化存储大小
        if (totalBytes < 1024 * 1024 * 1024) {
          storageSize.value = (totalBytes / (1024 * 1024)).toFixed(1) + ' MB'
        } else {
          storageSize.value = (totalBytes / (1024 * 1024 * 1024)).toFixed(1) + ' GB'
        }
        
        console.log('[Workbench] 统计数据加载成功:', {
          projectCount: projectCount.value,
          renderHours: renderHours.value,
          storageSize: storageSize.value,
          totalBytes: totalBytes
        })
        
        // 生成最新动态
        generateActivities(completedProjects)
      } catch (error) {
        console.error('[Workbench] 加载统计数据失败:', error)
      }
    }
    
    // 生成最新动态
    const generateActivities = (projects) => {
      const activities = []
      
      // 按最后修改时间排序，取最近的项目
      const sortedProjects = [...projects].sort((a, b) => {
        const timeA = a.lastModified ? new Date(a.lastModified).getTime() : 0
        const timeB = b.lastModified ? new Date(b.lastModified).getTime() : 0
        return timeB - timeA
      })
      
      // 取前5个最新项目
      const latestProjects = sortedProjects.slice(0, 5)
      
      for (const project of latestProjects) {
        let activityText = ''
        let color = 'purple'
        
        if (project.status === 'completed') {
          activityText = `项目 "${project.name}" 渲染完成`
          color = 'green'
        } else if (project.status === 'training') {
          activityText = `项目 "${project.name}" 正在训练中`
          color = 'blue'
        } else if (project.status === 'queued') {
          activityText = `项目 "${project.name}" 已加入队列`
          color = 'orange'
        }
        
        // 格式化时间
        let timeStr = '未知时间'
        if (project.lastModified) {
          const date = new Date(project.lastModified)
          const year = date.getFullYear()
          const month = String(date.getMonth() + 1).padStart(2, '0')
          const day = String(date.getDate()).padStart(2, '0')
          const hours = String(date.getHours()).padStart(2, '0')
          const minutes = String(date.getMinutes()).padStart(2, '0')
          timeStr = `${year}-${month}-${day} ${hours}:${minutes}`
        }
        
        activities.push({
          text: activityText,
          time: timeStr,
          color: color
        })
      }
      
      recentActivities.value = activities
    }
    
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
    
    // 组件挂载时加载数据
    onMounted(() => {
      loadStats()
    })
    
    return {
      projectCount,
      renderHours,
      storageSize,
      recentActivities,
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
    grid-template-columns: repeat(3, 1fr);
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

.empty-activities {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #94a3b8;
  font-size: 0.875rem;
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