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

let environmentChecked = false
let environmentValid = null

router.beforeEach(async (to, from, next) => {
  if (to.name === 'train') {
    if (!environmentChecked) {
      try {
        const envCheck = await window.electronAPI?.checkEnvironment()
        environmentValid = envCheck?.success && envCheck?.valid
        environmentChecked = true
        
        console.log('训练页面环境检查结果:', environmentValid)
        
        if (!environmentValid) {
          next('/environment')
          return
        }
      } catch (error) {
        console.error('环境检查失败:', error)
        next('/environment')
        return
      }
    } else {
      if (!environmentValid) {
        next('/environment')
        return
      }
    }
  }
  next()
})

export default router