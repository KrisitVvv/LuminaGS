import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    redirect: '/workbench'
  },
  {
    path: '/workbench',
    name: 'workbench',
    component: () => import('../components/pages/WorkbenchPage.vue')
  },
  {
    path: '/projects',
    name: 'projects',
    component: () => import('../components/pages/ProjectsPage.vue')
  },
  {
    path: '/train',
    name: 'train',
    component: () => import('../components/pages/TrainPage.vue')
  },
  {
    path: '/environment',
    name: 'environment',
    component: () => import('../components/pages/EnvironmentSetup.vue')
  },
  {
    path: '/progress',
    name: 'progress',
    component: () => import('../components/pages/ProgressPage.vue')
  },
  {
    path: '/settings',
    name: 'settings',
    component: () => import('../components/pages/SettingsPage.vue')
  },
  {
    path: '/editor/:projectId?',
    name: 'editor',
    component: () => import('../components/pages/EditorPage.vue')
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// 全局路由守卫，仅对训练页面进行环境检查
let environmentChecked = false
let environmentValid = null

router.beforeEach(async (to, from, next) => {
  // 只在访问训练页面时检查环境
  if (to.name === 'train') {
    // 如果还没有检查过环境，先检查
    if (!environmentChecked) {
      try {
        const envCheck = await window.electronAPI?.checkEnvironment()
        environmentValid = envCheck?.success && envCheck?.valid
        environmentChecked = true
        
        console.log('训练页面环境检查结果:', environmentValid)
        
        // 如果环境无效，重定向到环境页面
        if (!environmentValid) {
          next('/environment')
          return
        }
      } catch (error) {
        console.error('环境检查失败:', error)
        // 检查失败也跳转到环境页面
        next('/environment')
        return
      }
    } else {
      // 已经检查过环境
      if (!environmentValid) {
        // 环境无效，强制跳转到环境页面
        next('/environment')
        return
      }
    }
  }
  
  // 其他页面直接放行
  next()
})

export default router