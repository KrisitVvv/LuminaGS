<template>
  <section class="projects-container">
    <div class="projects-content">
      <!-- 头部区域 -->
      <div class="header-section">
        <h2 class="page-title">所有项目 ({{ completedCount }})</h2>
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
        >
          <div class="card-image">
            <img v-if="project.imageLoaded" :alt="project.name" :src="project.imageUrl">
            <div v-else class="image-placeholder">
              <span class="iconify" data-icon="solar:image-linear"></span>
            </div>
          </div>
          <div class="card-content">
            <h3 class="project-name">{{ project.name }}</h3>
            <p class="project-meta">{{ formatLastModified(project.lastModified) }}</p>
            <div class="card-footer">
              <!-- ✅ 使用更大的点击区域 -->
              <div 
                class="menu-icon-wrapper"
                @mousedown.stop.prevent="showContextMenu($event, project)"
                @click.stop.prevent="showContextMenu($event, project)"
              >
                <span 
                  class="iconify menu-icon" 
                  data-icon="solar:menu-dots-bold"
                ></span>
              </div>
            </div>
          </div>
        </div>
        
        <!-- ✅ 新增：上下文菜单 -->
        <div 
          v-if="contextMenuVisible" 
          class="context-menu-overlay"
          @click="hideContextMenu"
        >
          <div 
            class="context-menu"
            :style="{ top: contextMenuPosition.top + 'px', left: contextMenuPosition.left + 'px' }"
            @click.stop
          >
            <div class="context-menu-item" @click.stop="renameProject(currentSelectedProject)">
              <span class="iconify" data-icon="solar:pen-bold"></span>
              <span>重命名项目</span>
            </div>
            <div class="context-menu-item danger" @click.stop="deleteProject(currentSelectedProject)">
              <span class="iconify" data-icon="solar:trash-bin-trash-bold"></span>
              <span>删除项目</span>
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
      loading: false,
      platform: 'win32', // 默认值，会在 created 中获取真实值
      // ✅ 新增：上下文菜单相关数据
      contextMenuVisible: false,
      contextMenuPosition: { top: 0, left: 0 },
      currentSelectedProject: null
    }
  },
  async created() {
    // 获取操作系统平台
    try {
      this.platform = await window.electronAPI?.getPlatform() || 'win32';
      console.log('[ProjectsPage] 操作系统平台:', this.platform);
    } catch (error) {
      console.error('[ProjectsPage] 获取平台失败:', error);
    }
    
    this.loadProjects();
  },
  computed: {
    completedCount() {
      // ✅ 只统计已完成的项目数量
      return this.projects.filter(project => 
        project.status === 'completed'
      ).length;
    },
    
    filteredProjects() {
      if (!this.searchQuery) {
        // ✅ 只显示已完成的项目
        return this.projects.filter(project => 
          project.status === 'completed'
        );
      }
      // 搜索时也只显示已完成的项目
      return this.projects.filter(project => 
        project.status === 'completed' &&
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
          
          // ✅ 新增：详细打印每个项目的缩略图信息
          this.projects.forEach((project, index) => {
            console.log(`[ProjectsPage] 项目 ${index + 1}:`, {
              projectId: project.projectId,
              name: project.name,
              status: project.status,
              thumbnailPath: project.thumbnailPath || '无',
              previewImagePath: project.previewImagePath || '无'
            });
          });
          
          // ✅ 新增：异步加载所有项目的图片 URL
          await this.loadAllProjectImages();
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
    
    // ✅ 新增：批量加载所有项目的图片 URL
    async loadAllProjectImages() {
      console.log('[ProjectsPage] 开始加载所有项目图片...');
      
      for (let i = 0; i < this.projects.length; i++) {
        const project = this.projects[i];
        
        try {
          // 尝试加载缩略图或预览图
          const imageUrl = await this.getProjectImage(project);
          
          if (imageUrl) {
            project.imageUrl = imageUrl;
            project.imageLoaded = true;
            console.log(`[ProjectsPage] ✓ 项目 ${i + 1} 图片加载成功：${imageUrl}`);
          } else {
            project.imageLoaded = false;
            console.log(`[ProjectsPage] ⚠️ 项目 ${i + 1} 无可用图片`);
          }
        } catch (error) {
          project.imageLoaded = false;
          console.error(`[ProjectsPage] ❌ 项目 ${i + 1} 图片加载失败:`, error);
        }
      }
      
      console.log('[ProjectsPage] 所有项目图片加载完成');
    },
    
    async getProjectImage(project) {
      // ✅ 新增：首先检查 project 对象是否有 thumbnailPath 或 previewImagePath
      console.log(`[ProjectsPage] 检查项目图片：${project.projectId}`, {
        thumbnailPath: project.thumbnailPath,
        previewImagePath: project.previewImagePath
      });
      
      // 优先使用缩略图路径
      if (project.thumbnailPath) {
        try {
          // ✅ 使用 Electron API 转换为可访问的 URL
          const result = await window.electronAPI?.convertFilePath(project.thumbnailPath);
          
          if (result?.success && result.url) {
            console.log(`[ProjectsPage] 🖼️ 加载缩略图：${result.url}`);
            return result.url;
          } else {
            console.warn(`[ProjectsPage] ⚠️ 转换缩略图路径失败：`, result?.error);
            return null;
          }
        } catch (error) {
          console.error('[ProjectsPage] ❌ 转换缩略图路径失败:', error);
          return null;
        }
      }
      
      // 如果没有缩略图，尝试使用预览图路径
      if (project.previewImagePath) {
        try {
          const result = await window.electronAPI?.convertFilePath(project.previewImagePath);
          
          if (result?.success && result.url) {
            console.log(`[ProjectsPage] 🖼️ 加载预览图：${result.url}`);
            return result.url;
          } else {
            console.warn(`[ProjectsPage] ⚠️ 转换预览图路径失败：`, result?.error);
            return null;
          }
        } catch (error) {
          console.error('[ProjectsPage] ❌ 转换预览图路径失败:', error);
          return null;
        }
      }
      
      console.log(`[ProjectsPage] ℹ️ 无可用图片：${project.projectId}`);
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
    },
    
    // ✅ 新增：显示上下文菜单
    showContextMenu(event, project) {
      console.log('[ProjectsPage] 🔴 showContextMenu 被调用！', event.type);
      
      event.preventDefault();
      event.stopPropagation();
      event.stopImmediatePropagation();
      
      this.currentSelectedProject = project;
      
      // 计算菜单位置（确保不超出屏幕）
      const menuWidth = 200;
      const menuHeight = 100;
      const rect = event.target.getBoundingClientRect();
      
      let top = rect.bottom + window.scrollY;
      let left = rect.right - menuWidth + window.scrollX;
      
      // 检查是否超出右边界
      if (left + menuWidth > window.innerWidth) {
        left = window.innerWidth - menuWidth - 10;
      }
      
      // 检查是否超出下边界
      if (top + menuHeight > window.innerHeight) {
        top = rect.top - menuHeight + window.scrollY;
      }
      
      this.contextMenuPosition = { top, left };
      this.contextMenuVisible = true;
      
      console.log('[ProjectsPage] ✓ 菜单已显示:', {
        project: project.name,
        position: { top, left }
      });
    },
    
    // ✅ 新增：隐藏上下文菜单
    hideContextMenu() {
      this.contextMenuVisible = false;
      this.currentSelectedProject = null;
    },
    
    // ✅ 新增：重命名项目
    async renameProject(project) {
      if (!project) return;
      
      this.hideContextMenu();
      
      console.log('[ProjectsPage] 重命名项目:', project.name);
      
      // 使用原生 prompt 进行重命名
      const newName = prompt('请输入新的项目名称:', project.name);
      
      if (!newName || newName.trim() === '') {
        console.log('[ProjectsPage] 取消重命名');
        return;
      }
      
      if (newName === project.name) {
        console.log('[ProjectsPage] 名称未改变');
        return;
      }
      
      try {
        // 调用 Electron API 更新项目配置
        const result = await window.electronAPI?.updateProjectConfig(project.projectId, {
          name: newName.trim()
        });
        
        if (result?.success) {
          console.log(`[ProjectsPage] ✓ 重命名成功：${project.name} -> ${newName}`);
          // 更新本地数据
          project.name = newName.trim();
          alert(`项目重命名成功！\n新名称：${newName}`);
        } else {
          console.error('[ProjectsPage] ❌ 重命名失败:', result?.error);
          alert('重命名失败：' + (result?.error || '未知错误'));
        }
      } catch (error) {
        console.error('[ProjectsPage] ❌ 重命名异常:', error);
        alert('重命名失败：' + error.message);
      }
    },
    
    // ✅ 新增：删除项目
    async deleteProject(project) {
      if (!project) return;
      
      this.hideContextMenu();
      
      console.log('[ProjectsPage] 删除项目:', project.name);
      
      // 确认删除
      const confirmed = confirm(`确定要删除项目 "${project.name}" 吗？\n\n此操作将删除项目的输出目录，但不会删除项目配置文件。`);
      
      if (!confirmed) {
        console.log('[ProjectsPage] 取消删除');
        return;
      }
      
      try {
        // 调用 Electron API 删除项目输出
        const result = await window.electronAPI?.deleteProjectAndOutput(project.projectId, project.outputPath);
        
        if (result?.success) {
          console.log(`[ProjectsPage] ✓ 删除成功：${project.name}`);
          // 从列表中移除该项目
          const index = this.projects.findIndex(p => p.projectId === project.projectId);
          if (index !== -1) {
            this.projects.splice(index, 1);
          }
          alert(`项目已删除！`);
        } else {
          console.error('[ProjectsPage] ❌ 删除失败:', result?.error);
          alert('删除失败：' + (result?.error || '未知错误'));
        }
      } catch (error) {
        console.error('[ProjectsPage] ❌ 删除异常:', error);
        alert('删除失败：' + error.message);
      }
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
  justify-content: right;
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
  cursor: pointer;
  padding: 0.25rem;
  border-radius: 0.25rem;
  transition: all 0.2s ease;
  /* ✅ 确保可以点击 */
  pointer-events: auto;
  user-select: none;
  -webkit-tap-highlight-color: transparent;
}

.menu-icon:hover {
  background-color: #f1f5f9;
  color: #475569;
}

.menu-icon:active {
  background-color: #e2e8f0;
}

/* ✅ 新增：上下文菜单样式 */
.context-menu-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 9999;
  /* 透明背景，点击关闭菜单 */
}

/* ✅ 新增：菜单图标包装器样式 */
.menu-icon-wrapper {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0.25rem;
  cursor: pointer;
  border-radius: 0.25rem;
  transition: all 0.2s ease;
  /* ✅ 确保可以点击且不被遮挡 */
  pointer-events: auto;
  user-select: none;
}

.menu-icon-wrapper:hover {
  background-color: #f1f5f9;
}

.menu-icon-wrapper:active {
  background-color: #e2e8f0;
}

.context-menu {
  position: absolute;
  background: white;
  border-radius: 0.5rem;
  box-shadow: 0 10px 25px rgba(0, 0, 0, 0.15), 0 0 0 1px rgba(0, 0, 0, 0.05);
  padding: 0.5rem;
  min-width: 200px;
  animation: menuFadeIn 0.15s ease-out;
  z-index: 10000;
}

@keyframes menuFadeIn {
  from {
    opacity: 0;
    transform: scale(0.95);
  }
  to {
    opacity: 1;
    transform: scale(1);
  }
}

.context-menu-item {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.625rem 0.75rem;
  border-radius: 0.375rem;
  cursor: pointer;
  transition: all 0.15s ease;
  font-size: 0.875rem;
  color: #334155;
}

.context-menu-item:hover {
  background-color: #f1f5f9;
}

.context-menu-item .iconify {
  font-size: 1.125rem;
  color: #64748b;
}

.context-menu-item.danger {
  color: #dc2626;
}

.context-menu-item.danger:hover {
  background-color: #fef2f2;
}

.context-menu-item.danger .iconify {
  color: #dc2626;
}
</style>
