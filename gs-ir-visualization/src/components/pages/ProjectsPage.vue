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
          <button class="new-project-btn">新建项目</button>
        </div>
      </div>
      
      <div class="projects-grid">
        <div 
          v-for="project in filteredProjects" 
          :key="project.id" 
          class="project-card"
          @click="openProject(project)"
        >
          <div class="card-image">
            <img :alt="project.name" :src="project.image">
            <div class="status-badge" :class="statusClass(project.status)">
              {{ project.status }}
            </div>
          </div>
          <div class="card-content">
            <h3 class="project-name">{{ project.name }}</h3>
            <p class="project-meta">{{ project.lastModified }} · {{ project.size }}</p>
            <div class="card-footer">
              <div class="members-group">
                <div 
                  v-for="(member, idx) in project.members.slice(0, 3)" 
                  :key="idx" 
                  class="member-avatar" 
                  :class="member.color"
                ></div>
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
      projects: [
        {
          id: 1,
          name: '智慧园区 - A区数字化',
          image: 'https://modao.cc/agent-py/media/generated_images/2026-01-30/964aff127c88401c84551665fc35fe26.jpg',
          lastModified: '最后修改: 2小时前',
          size: '3.4GB',
          status: '已完成',
          members: [
            { color: 'bg-blue-400' },
            { color: 'bg-purple-400' }
          ]
        },
        {
          id: 2,
          name: '城市夜景重光照',
          image: 'https://modao.cc/agent-py/media/generated_images/2026-01-30/6190da8135da4d32999730787ce10cac.jpg',
          lastModified: '最后修改: 1天前',
          size: '2.1GB',
          status: '训练中',
          members: [
            { color: 'bg-green-400' }
          ]
        },
        {
          id: 3,
          name: '工业厂房资产库',
          image: 'https://modao.cc/agent-py/media/generated_images/2026-01-30/13470a0341134dabbdfa3d0aeda0fad5.jpg',
          lastModified: '最后修改: 3天前',
          size: '5.7GB',
          status: '渲染中',
          members: [
            { color: 'bg-amber-400' },
            { color: 'bg-red-400' }
          ]
        }
      ]
    }
  },
  computed: {
    filteredProjects() {
      if (!this.searchQuery) return this.projects
      return this.projects.filter(project => 
        project.name.toLowerCase().includes(this.searchQuery.toLowerCase())
      )
    }
  },
  methods: {
    openProject(project) {
      console.log('打开项目:', project.name)
      // 跳转到编辑器页面，传递项目ID
      this.$router.push({ 
        name: 'editor', 
        params: { projectId: project.id } 
      })
    },
    statusClass(status) {
      const classes = {
        '已完成': 'status-completed',
        '训练中': 'status-training', 
        '渲染中': 'status-rendering'
      }
      return classes[status] || ''
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

.status-badge {
  position: absolute;
  top: 0.75rem;
  right: 0.75rem;
  padding: 0.25rem 0.75rem;
  border-radius: 9999px;
  font-size: 0.75rem;
  font-weight: 500;
}

.status-completed {
  background-color: #dcfce7;
  color: #166534;
}

.status-training {
  background-color: #fef3c7;
  color: #92400e;
}

.status-rendering {
  background-color: #dbeafe;
  color: #1e40af;
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

.members-group {
  display: flex;
  gap: -0.5rem;
}

.member-avatar {
  width: 1.5rem;
  height: 1.5rem;
  border-radius: 50%;
  border: 2px solid white;
}

.menu-icon {
  color: #94a3b8;
  font-size: 1.25rem;
}
</style>