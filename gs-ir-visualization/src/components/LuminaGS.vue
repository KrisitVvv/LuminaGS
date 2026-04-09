<template>
  <div class="main-container">
    <header class="top-bar">
      <div class="draggable-region"></div>
      <div class="window-controls-container">
          <img @click="minimizeWindow" :src="'/src/drawable/minimizing.png'" class="window-btn-icon">
          <img v-if="!isMaximized" :src="'/src/drawable/maximizing.png'" @click="maximizeRestoreWindow" alt="Maximize" class="window-btn-icon" style="width: 1rem;">
          <img v-else :src="'/src/drawable/recover.png'" @click="maximizeRestoreWindow" alt="Restore" class="window-btn-icon" style="width: 0.9rem;">
          <img :src="'/src/drawable/close.png'" @click="closeWindow" alt="Close" class="window-btn-icon" style="margin-right: 2.2rem;">
        </div>
    </header>
    
    <div class="layout-container">
      <aside 
        class="sidebar"
        :class="sidebarExpanded ? 'expanded' : 'collapsed'"
        @mouseenter="startExpandTimer"
        @mouseleave="cancelExpandTimer"
      >
        <div class="sidebar-content">
          <div class="logo-area">
            <div class="logo">
              <span class="icon iconify" data-icon="solar:3d-cube-bold"></span>
            </div>
          </div>
          
          <nav class="main-navigation">
            <div class="nav-menu nav-expanded" v-show="sidebarExpanded">
              <router-link class="nav-item" :to="{name: 'workbench'}" active-class="active-nav-item">
                <span class="icon iconify" data-icon="solar:clapperboard-edit-linear"></span>
                <span class="nav-text">工作台</span>
              </router-link>
              <router-link class="nav-item" :to="{name: 'projects'}" active-class="active-nav-item">
                <span class="icon iconify" data-icon="solar:folder-2-linear"></span>
                <span class="nav-text">项目</span>
              </router-link>
              <router-link class="nav-item" :to="{name: 'progress'}" active-class="active-nav-item">
                <span class="icon iconify" data-icon="solar:chart-2-linear"></span>
                <span class="nav-text">渲染进度</span>
              </router-link>
              <router-link class="nav-item" :to="{name: 'settings'}" active-class="active-nav-item">
                <span class="icon iconify" data-icon="solar:settings-linear"></span>
                <span class="nav-text">设置</span>
              </router-link>
            </div>
            
            <div class="nav-menu nav-collapsed" v-show="!sidebarExpanded">
              <router-link class="nav-item-collapsed" :to="{name: 'workbench'}" active-class="active-nav-item">
                <span class="icon iconify" data-icon="solar:clapperboard-edit-linear"></span>
              </router-link>
              <router-link class="nav-item-collapsed" :to="{name: 'projects'}" active-class="active-nav-item">
                <span class="icon iconify" data-icon="solar:folder-2-linear"></span>
              </router-link>
              <router-link class="nav-item-collapsed" :to="{name: 'progress'}" active-class="active-nav-item">
                <span class="icon iconify" data-icon="solar:chart-2-linear"></span>
              </router-link>
              <router-link class="nav-item-collapsed" :to="{name: 'settings'}" active-class="active-nav-item">
                <span class="icon iconify" data-icon="solar:settings-linear"></span>
              </router-link>
            </div>
          </nav>
          
          <div class="sidebar-footer">
            <div class="user-avatar">
              <img alt="User Profile" class="avatar-img" :src="avatarImage" @error="onImageError">
            </div>
          </div>
        </div>
      </aside>
      
      <main class="main-content-area" :class="sidebarExpanded ? 'sidebar-expanded' : 'sidebar-collapsed'">
        <header class="content-header">
          <div class="header-primary">
            <div class="header-details">
              <h1 class="page-title">{{ pageTitle }}</h1>
              <p class="page-description">2026年01月30日 · 场景：Lumina_Atrium_01</p>
            </div>
          </div>
          <div class="header-secondary">
            <div class="system-monitor">
              <span class="status-light"></span>
              <span class="status-message">RTX 4090: 42°C | 12.4GB VRAM</span>
            </div>
            <button class="primary-action export-button">
              <span class="action-icon" data-icon="solar:play-bold"></span>
              导出渲染
            </button>
          </div>
        </header>
        
        <div class="content-body">
          <slot></slot>
        </div>
      </main>
    </div>
  </div>
</template>

<script>
import { RouterView, RouterLink } from 'vue-router'

export default {
  name: 'LuminaGS',
  components: {
    RouterView,
    RouterLink
  },
  props: {
  },
  data() {
    return {
      sidebarExpanded: false,
      expandTimer: null,
      avatarImage: 'https://modao.cc/agent-py/media/generated_images/2026-01-30/6190da8135da4d32999730787ce10cac.jpg',
      isMaximized: false,
      maximizedHandler: null,
      restoredHandler: null
    }
  },
  computed: {
    pageTitle() {
      const routeTitles = {
        'workbench': '系统概览',
        'projects': '项目管理中心',
        'progress': '渲染任务调度',
        'train': '模型深度训练',
        'settings': '系统设置',
        'editor': '高斯模型编辑器'
      };
      return routeTitles[this.$route.name] || '系统概览';
    }
  },
  methods: {
    startExpandTimer() {
      if (this.expandTimer) {
        clearTimeout(this.expandTimer);
      }
      this.expandTimer = setTimeout(() => {
        this.sidebarExpanded = true;
      }, 1000); 
    },
    cancelExpandTimer() {
      if (this.expandTimer) {
        clearTimeout(this.expandTimer);
        this.expandTimer = null;
      }
      this.sidebarExpanded = false;
    },
    onImageError() {
      this.avatarImage = '/default-avatar.png';
    },
    // 窗口控制方法
    minimizeWindow() {
      if (window.electronAPI) {
        window.electronAPI.minimizeWindow();
      }
    },
    
    maximizeRestoreWindow() {
      if (window.electronAPI) {
        if (this.isMaximized) {
          window.electronAPI.restoreWindow();
          this.isMaximized = false;
        } else {
          window.electronAPI.maximizeWindow();
          this.isMaximized = true;
        }
      }
    },
    
    closeWindow() {
      if (window.electronAPI) {
        window.electronAPI.closeWindow();
      }
    }
  },
  mounted() {
    this.maximizedHandler = () => {
      console.log('收到窗口最大化事件');
      this.isMaximized = true;
    };
    
    this.restoredHandler = () => {
      console.log('收到窗口恢复事件');
      this.isMaximized = false;
    };
    
    window.addEventListener('window-maximized', this.maximizedHandler);
    window.addEventListener('window-restored', this.restoredHandler);
    this.$nextTick(() => {
      if (window.electronAPI) {
        console.log('组件挂载完成，当前窗口状态:', this.isMaximized ? '最大化' : '普通');
      }
    });
  },
  beforeUnmount() {
    if (this.expandTimer) {
      clearTimeout(this.expandTimer);
    }
    
    // 移除监听器
    if (this.maximizedHandler) {
      window.removeEventListener('window-maximized', this.maximizedHandler);
    }
    if (this.restoredHandler) {
      window.removeEventListener('window-restored', this.restoredHandler);
    }
    
    console.log('组件卸载，事件监听器已移除');
  }
}
</script>

<style scoped>
.main-container {
  background-color: #f8fafc;
  font-family: ui-sans-serif, system-ui, sans-serif;
  color: #0f172a;
  height: 100vh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  margin: 0;
  padding: 0;
}

.layout-container {
  display: flex;
  height: 100vh;
  padding-top: 4rem;
  margin: 0;
  padding: 0;
}

.top-bar {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  height: 4rem;
  background-color: white;
  border-bottom: 1px solid #e2e8f0;
  z-index: 40;
  display: flex;
  align-items: center;
  justify-content: flex-end;
}

.draggable-region {
  position: absolute;
  top: 0;
  left: 0;
  width: calc(100% - 150px);
  height: 100%;
  -webkit-app-region: drag;
}

.window-controls-container {
  margin: 0.5rem;
  display: flex;
  align-items: center;
  -webkit-app-region: no-drag;
}

.window-btn-icon {
  width: 1.2rem;
  margin: 0.7rem;
  cursor: pointer;
}

.sidebar {
  position: fixed;
  left: 0;
  top: 0;
  height: 100vh;
  background-color: white;
  border-right: 1px solid #e2e8f0;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding-top: 1.5rem;
  z-index: 40;
  transition: all 0.3s ease;
  min-width: 5rem;
}

.sidebar.expanded {
  width: 15rem;
}

.sidebar.collapsed {
  width: 5rem;
  min-width: 5rem;
}

.sidebar-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  height: 100%;
  width: 100%;
}

.logo-area {
  margin-bottom: 2.5rem;
}

.logo {
  width: 3rem;
  height: 3rem;
  background-color: #7e22ce;
  border-radius: 0.75rem;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4px 6px -1px rgba(126, 34, 206, 0.1), 0 2px 4px -1px rgba(126, 34, 206, 0.06);
}

.icon {
  color: #94a3b8;
  font-size: 1.5rem;
  transition: color 0.2s ease;
  display: inline-block;
  width: 1.5rem;
  height: 1.5rem;
}

.main-navigation {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 100%;
  padding: 0 1rem;
  margin-top: 1rem;
}

.nav-menu {
  width: 100%;
}

.nav-expanded .nav-item,
.nav-collapsed .nav-item-collapsed {
  display: flex;
  align-items: center;
  position: relative;
  margin-bottom: 2rem;
  width: 100%;
  padding: 0.5rem 0;
  min-height: 2.5rem;
}

.nav-collapsed .nav-item-collapsed {
  padding-left: 0.8rem;
}

.nav-expanded .nav-item {
  justify-content: flex-start;
  padding-left: 0.8rem;
}

.nav-text {
  margin-left: 0.5rem;
  font-weight: 500;
  transition: opacity 0.3s ease-in-out 0.5s;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.sidebar-footer {
  margin-top: auto;
  width: 100%;
  padding: 0 1rem;
}

.user-avatar {
  width: 2.5rem;
  height: 2.5rem;
  border-radius: 50%;
  border: 2px solid white;
  overflow: hidden;
}

.avatar-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.main-content-area {
  flex: 1;
  height: 100%;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  transition: margin-left 0.3s ease;
  margin-left: 5rem;
  padding: 0;
  margin-top: 0;
}

.main-content-area.sidebar-expanded {
  margin-left: 15rem;
}

@media (max-width: 768px) {
  .main-content-area {
    margin-left: 4rem;
  }
  
  .main-content-area.sidebar-expanded {
    margin-left: 12rem;
  }
}

.content-header {
  height: 4rem;
  background-color: white;
  border-bottom: 1px solid #e2e8f0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 1.5rem; 
  flex-shrink: 0;
}

.header-primary {
  display: flex;
  align-items: center;
  margin-bottom: 0.25rem;
}

.header-details .page-title {
  font-size: 1.125rem;
  font-weight: bold;
  color: #1e293b;
  margin: 0;
}

.header-details .page-description {
  font-size: 0.75rem;
  color: #94a3b8;
  margin: 0;
}

.header-secondary {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.system-monitor {
  display: flex;
  align-items: center;
  background-color: #e2e8f0;
  border-radius: 0.5rem;
  padding: 0.75rem;
  gap: 0.5rem;
}

.status-light {
  width: 0.5rem;
  height: 0.5rem;
  border-radius: 50%;
  background-color: #22c55e;
  animation: pulse-soft 2s infinite;
}

.status-message {
  font-size: 0.75rem;
  font-weight: 500;
  color: #64748b;
}

.primary-action {
  background-color: #7e22ce;
  color: white;
  padding: 0.5rem 1rem;
  border-radius: 0.5rem;
  font-size: 0.875rem;
  font-weight: 500;
  transition: all 0.2s ease;
  display: flex;
  align-items: center;
  border: none;
  cursor: pointer;
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
}

.primary-action:hover {
  background-color: #6b21a8;
}

.action-icon {
  margin-right: 0.5rem;
}

.content-body {
  flex: 1;
  overflow: hidden;
  position: relative;
  padding: 0;
  margin: 0;
}

@keyframes pulse-soft {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.7;
  }
}

.nav-item.router-link-exact-active .icon,
.nav-item-collapsed.router-link-exact-active .icon {
  color: #9333ea !important;
}

.nav-item:not(.router-link-exact-active) .icon,
.nav-item-collapsed:not(.router-link-exact-active) .icon {
  color: #94a3b8;
  transition: color 0.2s ease;
}

.nav-item:not(.router-link-exact-active):hover .icon,
.nav-item-collapsed:not(.router-link-exact-active):hover .icon {
  color: #9333ea !important;
}

.main-container::-webkit-scrollbar,
.content-body::-webkit-scrollbar,
.sidebar::-webkit-scrollbar {
  display: none;
}

.main-container,
.content-body,
.sidebar {
  -ms-overflow-style: none;
  scrollbar-width: none;
}

body {
  overflow: hidden;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

::-webkit-scrollbar {
  width: 0;
  background: transparent;
}
</style>