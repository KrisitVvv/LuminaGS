<template>
  <section class="projects-container">
    <div class="projects-content">
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
      <div v-if="loading" class="loading-state">
        <span class="iconify" data-icon="solar:spinner-4"></span>
        正在加载项目...
      </div>
      
      <div v-else-if="projects.length === 0" class="empty-state">
        <span class="iconify" data-icon="solar:folder-open-linear"></span>
        <p>暂无项目</p>
        <button class="create-btn" @click="createNewProject">创建第一个项目</button>
      </div>
      
      <!-- 项目列表 -->
      <div v-else class="projects-grid">
        <!-- ✅ 全屏加载覆盖层 -->
        <div v-if="loadingProjects.length > 0" class="fullscreen-loading-overlay">
          <div class="loading-content">
            <span class="iconify loading-spinner" data-icon="solar:spinner-4"></span>
            <p class="loading-title">正在启动查看器...</p>
            <p class="loading-subtitle">请稍候，查看器正在初始化</p>
          </div>
        </div>
        
        <div 
          v-for="project in filteredProjects" 
          :key="project.projectId" 
          class="project-card"
          :class="{ 'disabled': loadingProjects.includes(project.projectId) }"
          @click="openProject(project)"
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
              <div 
                class="menu-icon-wrapper"
                @mousedown.stop.prevent="showContextMenu($event, project)"
                @click.stop.prevent="showContextMenu($event, project)"
              >
                <span class="iconify menu-icon" data-icon="solar:menu-dots-bold"></span>
              </div>
            </div>
          </div>
        </div>
        <div v-if="contextMenuVisible" class="context-menu-overlay" @click="hideContextMenu">
          <div 
            class="context-menu"
            :style="{ top: contextMenuPosition.top + 'px', left: contextMenuPosition.left + 'px' }"
            @click.stop
          >
            <button class="context-menu-btn" type="button" @click.stop="showRenameDialog(currentSelectedProject)">
              <span class="iconify" data-icon="solar:pen-bold"></span>
              <span>重命名项目</span>
            </button>
            <button class="context-menu-btn danger" type="button" @click.stop="deleteProject(currentSelectedProject)">
              <span class="iconify" data-icon="solar:trash-bin-trash-bold"></span>
              <span>删除项目</span>
            </button>
          </div>
        </div>
        
        <div v-if="renameDialogVisible" class="rename-dialog-overlay" @click="closeRenameDialog">
          <div class="rename-dialog" @click.stop>
            <div class="dialog-header">
              <h3 class="dialog-title">重命名项目</h3>
            </div>
            <div class="dialog-content">
              <label class="dialog-label">项目名称</label>
              <input 
                ref="renameInput"
                class="dialog-input" 
                type="text" 
                v-model="newProjectName"
                placeholder="请输入项目名称"
                @keyup.enter="confirmRename"
                @keyup.esc="closeRenameDialog"
              >
              <p v-if="errorMessage" class="error-message">{{ errorMessage }}</p>
            </div>
            <div class="dialog-footer">
              <button class="btn-cancel" @click="closeRenameDialog">取消</button>
              <button class="btn-confirm" @click="confirmRename" :disabled="isConfirming">确认</button>
            </div>
          </div>
        </div>
        
        <div v-if="deleteDialogVisible" class="delete-dialog-overlay" @click="closeDeleteDialog">
          <div class="delete-dialog" @click.stop>
            <div class="dialog-header danger-header">
              <h3 class="dialog-title danger-title">删除项目</h3>
            </div>
            <div class="dialog-content">
              <div class="delete-warning">
                <span class="iconify warning-icon" data-icon="solar:danger-triangle-bold"></span>
                <div class="warning-text">
                  <p class="warning-title">此操作将永久删除以下内容：</p>
                  <ul class="warning-list">
                    <li>项目的所有输出文件</li>
                    <li>训练生成的检查点和模型</li>
                    <li>渲染结果和日志文件</li>
                  </ul>
                </div>
              </div>
              <div class="project-info">
                <p class="info-label">项目名称：</p>
                <p class="info-value">{{ currentSelectedProject?.name || '' }}</p>
              </div>
              <div class="project-info">
                <p class="info-label">项目路径：</p>
                <p class="info-value path-value">{{ currentSelectedProject?.outputPath || '' }}</p>
              </div>
              <div class="confirm-input-wrapper">
                <label class="dialog-label">请输入 "DELETE" 以确认删除：</label>
                <input 
                  ref="deleteInput"
                  class="dialog-input delete-input" 
                  type="text" 
                  v-model="deleteConfirmText"
                  placeholder="输入 DELETE 确认删除"
                  @keyup.enter="confirmDelete"
                  @keyup.esc="closeDeleteDialog"
                >
                <p v-if="deleteErrorMessage" class="error-message">{{ deleteErrorMessage }}</p>
              </div>
            </div>
            <div class="dialog-footer">
              <button class="btn-cancel" @click="closeDeleteDialog">取消</button>
              <button class="btn-delete" @click="confirmDelete" :disabled="!canDelete || isDeleting">
                <span class="iconify" data-icon="solar:trash-bin-trash-bold"></span>
                <span>{{ isDeleting ? '正在删除...' : '删除项目' }}</span>
              </button>
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
      platform: 'win32',
      contextMenuVisible: false,
      contextMenuPosition: { top: 0, left: 0 },
      currentSelectedProject: null,
      renameDialogVisible: false,
      newProjectName: '',
      errorMessage: '',
      isConfirming: false,
      deleteDialogVisible: false,
      deleteConfirmText: '',
      deleteErrorMessage: '',
      isDeleting: false,
      // ✅ 正在加载的项目 ID 集合（使用数组以保证响应式）
      loadingProjects: []
    }
  },
  async created() {
    try {
      this.platform = await window.electronAPI?.getPlatform() || 'win32';
      console.log('[ProjectsPage] 操作系统平台:', this.platform);
      
      // 自动同步 sourcePath 字段
      console.log('[ProjectsPage] 🔍 检查并同步 sourcePath 字段...');
      const syncResult = await window.electronAPI?.syncSourcePathToProjects();
      if (syncResult?.success) {
        console.log(`[ProjectsPage] ✅ ${syncResult.message}`);
        // 同步后重新加载项目列表
        this.loadProjects();
      }
    } catch (error) {
      console.error('[ProjectsPage] 获取平台失败:', error);
    }
    this.loadProjects();
  },
  computed: {
    completedCount() {
      //只统计已完成的项目数量
      return this.projects.filter(project => 
        project.status === 'completed'
      ).length;
    },
    
    filteredProjects() {
      if (!this.searchQuery) {
        // 只显示已完成的项目
        return this.projects.filter(project => 
          project.status === 'completed'
        );
      }
      return this.projects.filter(project => 
        project.status === 'completed' &&
        project.name.toLowerCase().includes(this.searchQuery.toLowerCase())
      );
    },
    canDelete() {
      return this.deleteConfirmText === 'DELETE';
    }
  },
  methods: {
    async loadProjects() {
      console.log('[ProjectsPage] 🔍 开始加载项目列表...');
      this.loading = true;
          
      try {
        const result = await window.electronAPI?.getProjectList();
            
        if (result?.success && result.data) {
          this.projects = result.data;
          console.log(`[ProjectsPage] ✅ 加载了 ${this.projects.length} 个项目`);
          this.projects.forEach((project, index) => {
            console.log(`[ProjectsPage] 项目 ${index + 1}:`, {
              projectId: project.projectId,
              name: project.name,
              status: project.status,
              outputPath: project.outputPath || '无',
              thumbnailPath: project.thumbnailPath || '无',
              previewImagePath: project.previewImagePath || '无'
            });
          });
              
          //异步加载项目图片 URL
          await this.loadAllProjectImages();
        } else {
          console.error('[ProjectsPage] ❌ 加载失败:', result?.error);
          this.projects = [];
        }
      } catch (error) {
        console.error('[ProjectsPage] ❌ 加载项目失败:', error);
        this.projects = [];
      } finally {
        this.loading = false;
      }
    },
    
    // 批量加载所有项目的图片 URL
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
            console.log(`[ProjectsPage] 项目 ${i + 1} 图片加载成功：${imageUrl}`);
          } else {
            project.imageLoaded = false;
            console.log(`[ProjectsPage] 项目 ${i + 1} 无可用图片`);
          }
        } catch (error) {
          project.imageLoaded = false;
          console.error(`[ProjectsPage] 项目 ${i + 1} 图片加载失败:`, error);
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
    
    async openProject(project) {
      console.log('====== [ProjectsPage] 点击项目 ======');
      console.log('[ProjectsPage] 打开项目:', project.name, project.projectId, project.outputPath);
      console.log('[ProjectsPage] 完整项目数据:', JSON.stringify(project, null, 2));
      
      // 检查是否有项目 ID
      if (!project.projectId) {
        console.error('[ProjectsPage] ❌ 项目 ID 为空！');
        return;
      }
      
      // 检查是否有输出路径
      if (!project.outputPath) {
        console.warn('[ProjectsPage] ⚠️ 项目输出路径为空，使用默认值');
        project.outputPath = `output/${project.projectId}`;
      }
      
      console.log('[ProjectsPage] 🐍 准备启动 Python 实时查看器...');
      
      // ✅ 检查是否已经在加载中
      if (this.loadingProjects.includes(project.projectId)) {
        console.warn('[ProjectsPage] ⚠️ 该项目已在加载中，忽略重复点击');
        return;
      }
      
      try {
        // 设置加载状态
        this.loadingProjects.push(project.projectId);
        console.log(`[ProjectsPage] ⏳ 开始加载项目：${project.projectId}`);
        
        // 构建命令参数
        const checkpointPath = `${project.outputPath}\\chkpnt40000.pth`;
        
        // 数据集路径：优先从项目配置中获取
        // 注意：实际应该通过 project.configFile 读取详细配置文件获取 sourcePath
        // 但当前 projects.json 已经包含 sourcePath 字段，简化处理直接使用
        let sourcePath = project.datasetPath || project.sourcePath;
        
        console.log('[ProjectsPage] 🔍 检查项目配置数据:', {
          hasConfigFile: !!project.configFile,
          hasSourcePath: !!project.sourcePath,
          hasDatasetPath: !!project.datasetPath,
          configFile: project.configFile
        });
        
        if (!sourcePath) {
          console.error('[ProjectsPage] ❌ 项目数据集中路径缺失，项目已损坏！');
          
          // 弹出错误提示
          alert(`项目已损坏

项目名称：${project.name}

错误原因：找不到数据集路径
该项目的配置文件 (project.json) 中缺少 dataset_path 字段。

请检查项目配置或重新创建项目。`);
          
          return; // 终止后续操作
        } else {
          console.log('[ProjectsPage] ✓ 使用项目配置的数据集路径:', sourcePath);
        }
        
        const args = [
          '-m', project.outputPath,
          '-s', sourcePath,
          '--checkpoint', checkpointPath,
          '--resolution_scale', '1.0'
        ];
        
        console.log('[ProjectsPage] 执行命令:', 'conda run -n gsir python', args.join(' '));
        console.log('[ProjectsPage] 参数详情:', {
          model_path: project.outputPath,
          source_path: sourcePath,
          checkpoint: checkpointPath,
          resolution_scale: 1.0,
          conda_env: 'gsir'
        });
        
        // 调用 Electron API 启动 Python 脚本（使用 conda activate gsir）
        // 工作目录设置为项目输出目录，确保能正确找到模型文件
        const result = await window.electronAPI?.spawnPythonProcess({
          script: 'realtime_gaussian_viewer_gui.py',
          args: args,
          cwd: project.outputPath, // 使用项目输出目录作为工作目录
          useConda: true,          // 使用 conda 运行
          condaEnv: 'gsir',        // 指定 conda 环境名称
          scriptDir: 'E:\\GraduationProject\\LuminaGS\\GS-IR' // TODO: 脚本所在目录，需要从配置中读取
        });
        
        // ✅ 根据结果处理加载状态
        if (result?.success) {
          console.log('[ProjectsPage] ✓ Python 进程启动成功，PID:', result.pid);
          console.log('[ProjectsPage] ✓ GUI 已初始化完成，立即移除加载动画');
          // ✅ 成功时立即移除加载状态
          const index = this.loadingProjects.indexOf(project.projectId);
          if (index > -1) {
            this.loadingProjects.splice(index, 1);
          }
        } else {
          console.error('[ProjectsPage] ❌ Python 进程启动失败:', result?.error);
          // ✅ 失败时也移除加载状态
          const index = this.loadingProjects.indexOf(project.projectId);
          if (index > -1) {
            this.loadingProjects.splice(index, 1);
          }
        }
      } catch (error) {
        console.error('[ProjectsPage] ❌ 启动 Python 进程异常:', error);
        
        // ✅ 检查是否是超时错误
        if (error.message && error.message.includes('超时')) {
          alert(`⚠️ 加载超时

${error.message}

建议：
1. 检查计算机性能是否足够
2. 确认数据集大小是否正常
3. 尝试重新创建项目`);
        }
        
        // ✅ 异常时也要移除加载状态
        const index = this.loadingProjects.indexOf(project.projectId);
        if (index > -1) {
          this.loadingProjects.splice(index, 1);
        }
      }
      
      console.log(`[ProjectsPage] ✅ 完成加载项目：${project.projectId}`);
      console.log('[ProjectsPage] ✓ 操作完成');
      console.log('====================================\n');
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
    
    // ✅ 新增：显示重命名弹窗
    showRenameDialog(project) {
      if (!project) return;
      
      this.hideContextMenu();
      this.currentSelectedProject = project;
      this.newProjectName = project.name;
      this.errorMessage = '';
      this.isConfirming = false;
      this.renameDialogVisible = true;
      
      console.log('[ProjectsPage] 打开重命名弹窗:', project.name);
      
      // 弹窗打开后自动聚焦输入框并选中文本
      this.$nextTick(() => {
        if (this.$refs.renameInput) {
          this.$refs.renameInput.focus();
          this.$refs.renameInput.select();
        }
      });
    },
    
    // ✅ 新增：关闭重命名弹窗
    closeRenameDialog() {
      this.renameDialogVisible = false;
      this.newProjectName = '';
      this.errorMessage = '';
      this.isConfirming = false;
      this.currentSelectedProject = null;
      console.log('[ProjectsPage] 关闭重命名弹窗');
    },
    
    // ✅ 新增：确认重命名
    async confirmRename() {
      if (!this.currentSelectedProject) return;
      
      const project = this.currentSelectedProject;
      const trimmedName = this.newProjectName.trim();
      
      console.log('[ProjectsPage] 确认重命名:', trimmedName);
      
      // 验证名称
      if (!trimmedName) {
        this.errorMessage = '项目名称不能为空';
        return;
      }
      
      // 检查名称是否改变
      if (trimmedName === project.name) {
        this.errorMessage = '项目名称未改变';
        return;
      }
      
      // 验证非法字符（不允许包含 \ / : * ? " < > |）
      const invalidCharsPattern = /[\\/:*?"<>|]/;
      if (invalidCharsPattern.test(trimmedName)) {
        this.errorMessage = '项目名称不能包含以下字符：\\ / : * ? " < > |';
        return;
      }
      
      // 开始重命名
      this.isConfirming = true;
      this.errorMessage = '';
      
      try {
        // 调用 Electron API 更新项目配置
        // 这会同时更新 projects.json 和项目配置文件中的 name 字段
        const result = await window.electronAPI?.updateProjectConfig(project.projectId, {
          projectName: trimmedName
        });
        
        if (result?.success) {
          console.log(`[ProjectsPage] ✓ 重命名成功：${project.name} -> ${trimmedName}`);
          // 更新本地数据
          project.name = trimmedName;
          this.closeRenameDialog();
        } else {
          console.error('[ProjectsPage] ❌ 重命名失败:', result?.error);
          this.errorMessage = '重命名失败：' + (result?.error || '未知错误');
        }
      } catch (error) {
        console.error('[ProjectsPage] ❌ 重命名异常:', error);
        this.errorMessage = '重命名失败：' + error.message;
      } finally {
        this.isConfirming = false;
      }
    },
    
    async renameProject(project) {
      this.showRenameDialog(project);
    },
    
    // ✅ 新增：显示删除确认弹窗
    showDeleteDialog(project) {
      if (!project) return;
      
      this.hideContextMenu();
      this.currentSelectedProject = project;
      this.deleteConfirmText = '';
      this.deleteErrorMessage = '';
      this.isDeleting = false;
      this.deleteDialogVisible = true;
      
      console.log('[ProjectsPage] 打开删除确认弹窗:', project.name);
      
      // 弹窗打开后自动聚焦输入框
      this.$nextTick(() => {
        if (this.$refs.deleteInput) {
          this.$refs.deleteInput.focus();
        }
      });
    },
    
    // ✅ 新增：关闭删除确认弹窗
    closeDeleteDialog() {
      this.deleteDialogVisible = false;
      this.deleteConfirmText = '';
      this.deleteErrorMessage = '';
      this.isDeleting = false;
      this.currentSelectedProject = null;
      console.log('[ProjectsPage] 关闭删除确认弹窗');
    },
    
    // ✅ 新增：确认删除项目（彻底删除所有内容）
    async confirmDelete() {
      if (!this.currentSelectedProject) return;
      
      const project = this.currentSelectedProject;
      
      // 验证是否输入了 DELETE
      if (this.deleteConfirmText !== 'DELETE') {
        this.deleteErrorMessage = '请输入 "DELETE" 以确认删除';
        return;
      }
      
      console.log('[ProjectsPage] 确认删除项目:', project.name);
      
      // 开始删除
      this.isDeleting = true;
      this.deleteErrorMessage = '';
      
      try {
        // 调用 Electron API 删除项目及其所有输出文件
        // 这会删除整个 outputPath 目录下的所有内容
        const result = await window.electronAPI?.deleteProjectAndOutput(project.projectId, project.outputPath);
        
        if (result?.success) {
          console.log(`[ProjectsPage] ✓ 删除成功：${project.name}`);
          // 从列表中移除该项目
          const index = this.projects.findIndex(p => p.projectId === project.projectId);
          if (index !== -1) {
            this.projects.splice(index, 1);
          }
          this.closeDeleteDialog();
        } else {
          console.error('[ProjectsPage] ❌ 删除失败:', result?.error);
          this.deleteErrorMessage = '删除失败：' + (result?.error || '未知错误');
        }
      } catch (error) {
        console.error('[ProjectsPage] ❌ 删除异常:', error);
        this.deleteErrorMessage = '删除失败：' + error.message;
      } finally {
        this.isDeleting = false;
      }
    },
    
    // ✅ 修改：删除项目（保留作为兼容，实际使用 showDeleteDialog）
    async deleteProject(project) {
      this.showDeleteDialog(project);
    },
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
  position: relative;
}

/* ✅ 加载状态 - 禁用点击 */
.project-card.disabled {
  cursor: not-allowed;
  opacity: 0.7;
  pointer-events: none;
}

.project-card:hover {
  box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04);
  border-color: #ddd6fe;
}

/* ✅ 全屏加载动画覆盖层 */
.fullscreen-loading-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  width: 100vw;
  height: 100vh;
  background-color: rgba(255, 255, 255, 0.95);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
  backdrop-filter: blur(8px);
  animation: fadeIn 0.3s ease-out;
}

.loading-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 1.5rem;
}

.loading-spinner {
  font-size: 5rem;
  color: #a855f7;
  animation: spin 1s linear infinite;
}

.loading-title {
  font-size: 1.5rem;
  font-weight: 600;
  color: #1e293b;
  margin: 0;
}

.loading-subtitle {
  font-size: 1rem;
  color: #64748b;
  margin: 0;
  font-weight: 400;
}

@keyframes fadeIn {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
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
  background: none;
  border: none;
  width: 100%;
  text-align: left;
}

.context-menu-btn {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.625rem 0.75rem;
  border-radius: 0.375rem;
  cursor: pointer;
  transition: all 0.15s ease;
  font-size: 0.875rem;
  color: #334155;
  background: none;
  border: none;
  width: 100%;
  text-align: left;
  outline: none;
}

.context-menu-btn:hover {
  background-color: #f1f5f9;
}

.context-menu-btn .iconify {
  font-size: 1.125rem;
  color: #64748b;
}

.context-menu-btn.danger {
  color: #dc2626;
}

.context-menu-btn.danger:hover {
  background-color: #fef2f2;
}

.context-menu-btn.danger .iconify {
  color: #dc2626;
}

/* ✅ 新增：重命名弹窗样式 */
.rename-dialog-overlay {
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

.rename-dialog {
  background: white;
  border-radius: 1rem;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3), 0 0 0 1px rgba(0, 0, 0, 0.05);
  width: 100%;
  max-width: 480px;
  min-height: 200px;
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
  justify-content: space-between;
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

.dialog-label {
  display: block;
  font-size: 0.875rem;
  font-weight: 500;
  color: #475569;
  margin-bottom: 0.5rem;
}

.dialog-input {
  width: 100%;
  padding: 0.75rem 1rem;
  font-size: 1rem;
  border: 2px solid #e2e8f0;
  border-radius: 0.75rem;
  outline: none;
  transition: all 0.2s ease;
  background-color: #ffffff;
  color: #1e293b;
  box-sizing: border-box;
}

.dialog-input:focus {
  border-color: #a78bfa;
  box-shadow: 0 0 0 3px rgba(167, 139, 250, 0.1);
}

.dialog-input::placeholder {
  color: #94a3b8;
}

.error-message {
  margin-top: 0.75rem;
  padding: 0.75rem 1rem;
  background-color: #fef2f2;
  border-left: 3px solid #dc2626;
  border-radius: 0.5rem;
  font-size: 0.875rem;
  color: #dc2626;
  line-height: 1.5;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 0.75rem;
  padding: 1rem 1.5rem 1.5rem 1.5rem;
  background-color: #f8fafc;
  border-top: 1px solid #e2e8f0;
}

.btn-cancel,
.btn-confirm {
  padding: 0.625rem 1.5rem;
  font-size: 0.875rem;
  font-weight: 500;
  border-radius: 0.5rem;
  border: none;
  cursor: pointer;
  transition: all 0.2s ease;
}

.btn-cancel {
  background-color: #f1f5f9;
  color: #475569;
}

.btn-cancel:hover {
  background-color: #e2e8f0;
}

.btn-confirm {
  background-color: #7e22ce;
  color: white;
}

.btn-confirm:hover:not(:disabled) {
  background-color: #6b21a8;
}

.btn-confirm:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* ✅ 新增：删除弹窗样式 */
.delete-dialog-overlay {
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

.delete-dialog {
  background: white;
  border-radius: 1rem;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3), 0 0 0 1px rgba(0, 0, 0, 0.05);
  width: 100%;
  max-width: 560px;
  animation: dialogSlideIn 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
  overflow: hidden;
}

.danger-header {
  background-color: #fef2f2;
  padding-bottom: 1rem;
}

.danger-title {
  color: #dc2626;
}

.delete-warning {
  display: flex;
  gap: 1rem;
  padding: 1rem;
  background-color: #fff7ed;
  border-left: 4px solid #f97316;
  border-radius: 0.75rem;
  margin-bottom: 1.5rem;
}

.warning-icon {
  font-size: 2rem;
  color: #f97316;
  flex-shrink: 0;
}

.warning-text {
  flex: 1;
}

.warning-title {
  font-weight: 600;
  color: #9a3412;
  margin: 0 0 0.5rem 0;
  font-size: 0.9375rem;
}

.warning-list {
  margin: 0;
  padding-left: 1.25rem;
  color: #9a3412;
  font-size: 0.875rem;
  line-height: 1.6;
}

.warning-list li {
  margin-bottom: 0.25rem;
}

.project-info {
  display: flex;
  margin-bottom: 0.75rem;
  font-size: 0.875rem;
}

.info-label {
  font-weight: 500;
  color: #64748b;
  min-width: 80px;
  margin-right: 0.5rem;
}

.info-value {
  color: #334155;
  flex: 1;
}

.path-value {
  word-break: break-all;
  font-family: 'Courier New', monospace;
  background-color: #f1f5f9;
  padding: 0.25rem 0.5rem;
  border-radius: 0.25rem;
}

.confirm-input-wrapper {
  margin-top: 1.5rem;
}

.delete-input {
  font-weight: 600;
  letter-spacing: 0.05em;
}

.btn-delete {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.625rem 1.5rem;
  font-size: 0.875rem;
  font-weight: 500;
  border-radius: 0.5rem;
  border: none;
  cursor: pointer;
  transition: all 0.2s ease;
  background-color: #dc2626;
  color: white;
}

.btn-delete:hover:not(:disabled) {
  background-color: #b91c1c;
}

.btn-delete:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-delete .iconify {
  font-size: 1rem;
}
</style>
