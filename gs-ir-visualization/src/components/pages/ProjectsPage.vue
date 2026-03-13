<template>
  <section class="projects-container">
    <div class="projects-content">
      <!-- 头部区域 -->
      <div class="header-section">
        <h2 class="page-title">所有项目 ({{ projects.length }})</h2>
        <div class="header-actions">
          <input 
            class="search-input" 
            placeholder="搜索项目..." 
            type="text" 
            v-model="searchQuery"
          >
          <button class="new-project-btn" @click="createNewProject">新建项目</button>
        </div>
      </div>
      
      <!-- 加载状态 -->
      <div v-if="loading" class="loading-state">
        <span class="iconify" data-icon="solar:spinner-4"></span>
        正在加载项目...
      </div>
      
      <!-- 空状态 -->
      <div v-else-if="projects.length === 0" class="empty-state">
        <span class="iconify" data-icon="solar:folder-open-linear"></span>
        <p>暂无项目</p>
        <button class="create-btn" @click="createNewProject">创建第一个项目</button>
      </div>
      
      <!-- 项目列表 -->
      <div v-else class="projects-grid">
        <div 
          v-for="project in filteredProjects" 
          :key="project.projectId" 
          class="project-card"
          @click="openProject(project)"
        >
          <div class="card-image">
            <img v-if="getProjectImage(project)" :alt="project.name" :src="getProjectImage(project)">
            <div v-else class="image-placeholder">
              <span class="iconify" data-icon="solar:image-linear"></span>
            </div>
            <div class="status-badge" :class="statusClass(project.status)">
              {{ getStatusText(project.status) }}
            </div>
          </div>
          <div class="card-content">
            <h3 class="project-name">{{ project.name }}</h3>
            <p class="project-meta">{{ formatLastModified(project.lastModified) }}</p>
            <div class="card-footer">
              <div class="stage-badge" v-if="project.stage">
                {{ getStageText(project.stage) }}
              </div>
              <span class="iconify menu-icon" data-icon="solar:menu-dots-bold"></span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>

<script>
export default {
  name: 'ProjectsPage',
  data() {
    return {
      searchQuery: '',
      projects: [],
      loading: false
    }
  },
  created() {
    this.loadProjects();
  },
  computed: {
    filteredProjects() {
      if (!this.searchQuery) return this.projects;
      return this.projects.filter(project => 
        project.name.toLowerCase().includes(this.searchQuery.toLowerCase())
      );
    }
  },
  methods: {
    async loadProjects() {
      console.log('[ProjectsPage] 开始加载项目列表');
      this.loading = true;
      
      try {
        const result = await window.electronAPI?.getProjectList();
        
        if (result?.success && result.data) {
          this.projects = result.data;
          console.log(`[ProjectsPage] ✓ 加载了 ${this.projects.length} 个项目`);
        } else {
          console.error('[ProjectsPage] 加载失败:', result?.error);
          this.projects = [];
        }
      } catch (error) {
        console.error('[ProjectsPage] 加载项目失败:', error);
        this.projects = [];
      } finally {
        this.loading = false;
      }
    },
    
    getProjectImage(project) {
      // 优先使用缩略图路径
      if (project.thumbnailPath) {
        // 将本地路径转换为可访问的 URL
        // 注意：这里需要使用 Electron 的 file:// 协议或后端提供的 API
        // 暂时返回 null 显示占位图
        return null;
      }
      
      // 如果没有缩略图，尝试使用预览图路径
      if (project.previewImagePath) {
        return null;
      }
      
      return null;
    },
    
    formatLastModified(timestamp) {
      if (!timestamp) return '未知';
      
      const date = new Date(timestamp);
      const now = new Date();
      const diffMs = now - date;
      const diffMins = Math.floor(diffMs / 60000);
      const diffHours = Math.floor(diffMs / 3600000);
      const diffDays = Math.floor(diffMs / 86400000);
      
      if (diffMins < 1) return '刚刚修改';
      if (diffMins < 60) return `${diffMins} 分钟前`;
      if (diffHours < 24) return `${diffHours} 小时前`;
      if (diffDays < 30) return `${diffDays} 天前`;
      
      return date.toLocaleDateString('zh-CN');
    },
    
    getStatusText(status) {
      const statusMap = {
        'waiting': '等待中',
        'training': '训练中',
        'baking': '烘焙中',
        'completed': '已完成',
        'error': '错误',
        'disconnected': '未连接'
      };
      return statusMap[status] || status || '未知';
    },
    
    statusClass(status) {
      const classes = {
        'waiting': 'status-waiting',
        'training': 'status-training',
        'baking': 'status-baking',
        'completed': 'status-completed',
        'error': 'status-error',
        'disconnected': 'status-disconnected'
      };
      return classes[status] || '';
    },
    
    getStageText(stage) {
      const stageMap = {
        'stage1': 'Stage1',
        'baking': 'Baking',
        'stage2': 'Stage2'
      };
      return stageMap[stage] || '';
    },
    
    createNewProject() {
      console.log('[ProjectsPage] 创建新项目');
      // 跳转到 TrainPage 创建新项目
      this.$router.push({ name: 'train' });
    },
    
    openProject(project) {
      console.log('打开项目:', project.name, project.projectId);
      // 跳转到 TrainPage，传递项目 ID
      this.$router.push({ 
        name: 'train', 
        query: { projectId: project.projectId } 
      });
    }
  }
}
</script>

<style scoped>
.projects-container {
  height: 100%;
  background-color: #ffffff;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.projects-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 1.5rem;
  overflow-y: auto;
  gap: 1.5rem;
}

.header-section {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-shrink: 0;
}

.page-title {
  font-size: 1.5rem;
  font-weight: bold;
  color: #1e293b;
}

.header-actions {
  display: flex;
  gap: 0.75rem;
  align-items: center;
}

.search-input {
  background-color: #f1f5f9;
  border: none;
  border-radius: 0.5rem;
  padding: 0.5rem 1rem;
  font-size: 0.875rem;
  width: 16rem;
  outline: none;
  transition: box-shadow 0.2s ease;
}

.search-input:focus {
  box-shadow: 0 0 0 2px rgba(147, 51, 234, 0.2);
}

.new-project-btn {
  background-color: #7e22ce;
  color: white;
  padding: 0.5rem 1rem;
  border-radius: 0.5rem;
  font-size: 0.875rem;
  font-weight: 500;
  border: none;
  cursor: pointer;
  transition: background-color 0.2s ease;
}

.new-project-btn:hover {
  background-color: #6b21a8;
}

.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 4rem 2rem;
  color: #94a3b8;
  gap: 1rem;
}

.loading-state .iconify {
  font-size: 3rem;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 4rem 2rem;
  color: #94a3b8;
  gap: 1rem;
}

.empty-state .iconify {
  font-size: 4rem;
}

.empty-state p {
  font-size: 1.125rem;
  margin: 0;
}

.create-btn {
  background-color: #7e22ce;
  color: white;
  padding: 0.625rem 1.5rem;
  border-radius: 0.5rem;
  font-size: 0.875rem;
  font-weight: 500;
  border: none;
  cursor: pointer;
  transition: background-color 0.2s ease;
  margin-top: 0.5rem;
}

.create-btn:hover {
  background-color: #6b21a8;
}

.projects-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 1rem;
  flex-grow: 1;
}

@media (max-width: 1200px) {
  .projects-grid {
    grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  }
}

@media (max-width: 768px) {
  .projects-grid {
    grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
    gap: 0.75rem;
  }
  
  .projects-content {
    padding: 1rem;
  }
}

.project-card {
  border: 1px solid #e2e8f0;
  border-radius: 1rem;
  overflow: hidden;
  cursor: pointer;
  transition: all 0.2s ease;
  background: white;
  box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 280px;
  max-height: 320px;
}

.project-card:hover {
  box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04);
  border-color: #ddd6fe;
}

.card-image {
  height: 10rem;
  background-color: #f1f5f9;
  position: relative;
  overflow: hidden;
  flex-shrink: 0;
}

.card-image img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  transition: transform 0.3s ease;
}

.project-card:hover .card-image img {
  transform: scale(1.05);
}

.image-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: #f1f5f9;
  color: #cbd5e1;
}

.image-placeholder .iconify {
  font-size: 3rem;
}

.status-badge {
  position: absolute;
  top: 0.75rem;
  right: 0.75rem;
  padding: 0.25rem 0.75rem;
  border-radius: 9999px;
  font-size: 0.75rem;
  font-weight: 500;
}

.status-waiting {
  background-color: #f3f4f6;
  color: #374151;
}

.status-training {
  background-color: #fef3c7;
  color: #92400e;
}

.status-baking {
  background-color: #ffedd5;
  color: #9a3412;
}

.status-completed {
  background-color: #dcfce7;
  color: #166534;
}

.status-error {
  background-color: #fee2e2;
  color: #991b1b;
}

.status-disconnected {
  background-color: #f3f4f6;
  color: #6b7280;
}

.card-content {
  padding: 1rem;
  display: flex;
  flex-direction: column;
  flex-grow: 1;
}

.project-name {
  font-weight: bold;
  color: #1e293b;
  margin-bottom: 0.25rem;
  font-size: 1.125rem;
  flex-grow: 1;
  line-height: 1.4;
}

.project-meta {
  font-size: 0.75rem;
  color: #94a3b8;
  margin-bottom: 1rem;
  flex-shrink: 0;
}

.card-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: auto;
  flex-shrink: 0;
}

.stage-badge {
  padding: 0.25rem 0.75rem;
  border-radius: 9999px;
  font-size: 0.75rem;
  font-weight: 500;
  background-color: #ede9fe;
  color: #6b21a8;
}

.menu-icon {
  color: #94a3b8;
  font-size: 1.25rem;
}
</style>
