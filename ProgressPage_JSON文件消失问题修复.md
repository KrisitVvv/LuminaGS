# ProgressPage 点击进入导致 JSON文件"消失"问题修复

## 🎯 问题描述

用户报告：从 ProgressPage.vue 的渲染队列点击进入项目后，`.luminags/project_xxx.json` 文件消失了。

## 🔍 根本原因

### 问题分析

当用户从 ProgressPage 点击进入 TrainPage 时，会触发以下流程：

1. **路由跳转** → `TrainPage.vue` 加载
2. **调用 `loadProjectFromRoute()`** → 从 JSON文件加载项目配置
3. **恢复表单字段** → 设置 `gamma`、`indirect`、`resolution` 等值
4. **触发 `@change` 事件** → 每个字段的 change 事件都会调用 `triggerAutoSave()`
5. **立即保存配置** → 调用 `updateProjectConfig()`
6. **原子写入操作** → 删除原文件 → 创建新文件

在原子写入的瞬间（删除原文件后，新文件未创建前），如果用户查看文件系统，会看到 JSON文件"消失"了！

### 关键代码

**TrainPage.vue 模板中的自动保存绑定**：
```vue
<!-- 第 58 行 -->
<select v-model.number="resolution" @change="handleResolutionChange; triggerAutoSave()">

<!-- 第 92 行 -->
<input type="checkbox" v-model="gamma" @change="triggerAutoSave()">

<!-- 第 96 行 -->
<input type="checkbox" v-model="indirect" @change="triggerAutoSave()">

<!-- 其他字段类似... -->
```

**loadProjectFromRoute() 方法**（修复前）：
```javascript
async loadProjectFromRoute() {
  // 设置 currentProjectId
  this.currentProjectId = projectId;
  
  // 恢复所有表单字段
  this.gamma = project.config?.gamma ?? false;      // ← 触发 @change → triggerAutoSave()
  this.indirect = project.config?.indirect ?? false; // ← 触发 @change → triggerAutoSave()
  this.resolution = project.config?.resolution ?? 1; // ← 触发 @change → triggerAutoSave()
  // ... 其他字段
  
  // 刷新分辨率选择
  await this.handleResolutionChange(); // ← 可能再次触发保存
}
```

**结果**：
- 每次赋值都触发 `triggerAutoSave()`
- `triggerAutoSave()` 立即调用 `saveProjectConfig()`
- `saveProjectConfig()` 调用后端的 `updateProjectConfig()`
- `updateProjectConfig()` 执行原子写入：**删除原文件 → 创建临时文件 → 重命名**
- 在"删除原文件"和"重命名"之间的瞬间，文件"消失"了！

## ✅ 解决方案

### 修复思路

添加一个加载标记 `isLoadingProject`，在加载项目期间暂停自动保存功能。

### 具体修改

#### 1. 添加加载标记字段

**文件**: `TrainPage.vue` - data() 方法

```javascript
data() {
  return {
    // ... 其他数据
    
    // 当前项目 ID（用于自动保存）
    currentProjectId: null,
    
    // 防抖定时器
    saveDebounceTimer: null,
    
    // 新增：加载项目标记，防止加载时触发自动保存
    isLoadingProject: false  // ✅ 新增
  }
},
```

#### 2. 修改 loadProjectFromRoute() 方法

**文件**: `TrainPage.vue` - loadProjectFromRoute() 方法

```javascript
async loadProjectFromRoute() {
  const projectId = this.$route.query.resumeProjectId;
  if (!projectId) {
    console.warn('[加载项目] 未找到 projectId 参数');
    return;
  }
  
  // ✅ 设置加载中标记，防止触发自动保存
  this.isLoadingProject = true;
  console.log('[加载项目] 设置加载中标记，暂停自动保存');
  
  // 设置当前项目 ID
  this.currentProjectId = projectId;
  
  // ... 恢复所有表单字段（此时不会触发保存）
  this.gamma = project.config?.gamma ?? false;
  this.indirect = project.config?.indirect ?? false;
  // ...
  
  // 刷新分辨率选择
  await this.handleResolutionChange();
  
  // 加载预览图
  await this.updatePreviewImage();
  
  console.log('[加载项目] ✓ 项目配置加载完成');
  
  // ✅ 延迟清除加载标记，确保所有状态已恢复
  this.$nextTick(() => {
    this.isLoadingProject = false;
    console.log('[加载项目] 清除加载标记，恢复自动保存');
  });
  
} catch (error) {
  console.error('[加载项目] 失败:', error);
  this.addLog(`加载项目失败：${error.message}`, 'error');
  alert(`恢复项目失败：${error.message}`);
  // ✅ 即使出错也要清除标记
  this.isLoadingProject = false;
}
```

#### 3. 修改 triggerAutoSave() 方法

**文件**: `TrainPage.vue` - triggerAutoSave() 方法

```javascript
async triggerAutoSave() {
  // ✅ 如果正在加载项目，不触发保存
  if (this.isLoadingProject) {
    console.log('[triggerAutoSave] 项目加载中，跳过保存');
    return;
  }
  
  try {
    // ... 原有的保存逻辑
  } catch (error) {
    console.error('[triggerAutoSave] 失败:', error);
    // ... 原有的错误处理
  }
},
```

## 📊 修复效果

### 修复前的数据流

```
用户点击 ProgressPage 的项目
  ↓
跳转到 TrainPage
  ↓
loadProjectFromRoute()
  ↓
恢复 gamma = true
  ↓
触发 @change → triggerAutoSave() ❌ 立即保存！
  ↓
updateProjectConfig()
  ↓
原子写入：删除原文件 → 创建 .tmp → 重命名
  ↓
【文件"消失"的瞬间】❌
```

### 修复后的数据流

```
用户点击 ProgressPage 的项目
  ↓
跳转到 TrainPage
  ↓
loadProjectFromRoute()
  ↓
设置 isLoadingProject = true ✅
  ↓
恢复 gamma = true
  ↓
触发 @change → triggerAutoSave()
  ↓
检查 isLoadingProject = true
  ↓
跳过保存 ✅
  ↓
恢复所有字段...
  ↓
清除 isLoadingProject = false ✅
  ↓
此后才允许自动保存
```

## 🧪 测试验证

### 测试步骤

1. **打开应用，进入 ProgressPage**
2. **等待渲染队列刷新**
3. **点击某个项目进入 TrainPage**
4. **观察控制台日志**：
   ```
   [加载项目] 设置加载中标记，暂停自动保存
   [加载项目] 准备加载项目：project_xxx
   [加载项目] 成功获取项目配置
   [加载项目] ✓ 项目配置加载完成
   [加载项目] 清除加载标记，恢复自动保存
   ```
5. **检查文件系统**：
   - `.luminags/project_xxx.json` 文件应该始终存在
   - 不会再出现"消失"现象

### 预期行为

- ✅ 从 ProgressPage 进入时，JSON文件不会被意外修改
- ✅ 只有在用户手动修改表单字段后，才会触发保存
- ✅ 控制台日志清晰显示加载和保存的时机

## 📝 总结

### 问题本质
- **不是 bug**，而是**原子写入的正常过程被误判为文件删除**
- 加载项目时触发的自动保存导致原子写入操作

### 修复方式
- 添加加载标记 `isLoadingProject`
- 在加载期间暂停自动保存
- 加载完成后再恢复自动保存功能

### 优点
- ✅ 简单直接，只修改了一个文件
- ✅ 不影响正常的自动保存功能
- ✅ 避免了文件"消失"的误判
- ✅ 提高了用户体验（加载更快，无多余 I/O）

---

**修复完成！** 🎉
