# ProgressPage 渲染队列导致 JSON 文件删除问题排查

## 🔍 问题描述

用户报告：从 ProgressPage.vue 的渲染队列点击进入项目后，JSON 文件被删除。

## 📊 代码分析结果

### 已检查的关键方法

1. **`ProgressPage.resumeProject()`** (第 938-965 行)
   - ✅ 仅执行路由跳转
   - ✅ 不会删除任何文件

2. **`ProgressPage.loadProjectQueue()`** (第 880-907 行)
   - ✅ 调用 `getProjectList` API
   - ✅ 每 5 秒自动刷新一次

3. **`main.js: get-project-list`** (第 1983-1993 行)
   - ✅ 调用 `projectManager.getAllProjects()`
   - ✅ 调用 `projectManager.scanProjects()`

4. **`projectManager.scanProjects()`** (第 363-400 行)
   - ✅ 只读取和检查文件
   - ✅ 不会删除文件

5. **`projectManager.loadProject()`** (第 342-361 行)
   - ✅ 只读取配置文件
   - ✅ 不会删除文件

6. **`projectManager.updateProjectConfig()`** (第 457-562 行)
   - ⚠️ 包含 `fs.unlink()` 删除操作
   - ✅ 但这是**原子写入**的正常流程（先删后写）

## 🎯 可能的原因分析

### 假设 1：原子写入失败导致文件丢失

**场景**：
1. `updateProjectConfig` 执行原子写入
2. 创建临时文件 `.tmp`
3. 删除原文件
4. **重命名失败**（进程崩溃、权限问题等）
5. 导致原文件已删除，新文件未创建

**验证方法**：
- 查看控制台日志，搜索 `[ProjectManager] 原子写入` 相关日志
- 检查是否有 `.tmp` 文件残留

### 假设 2：多个地方同时写入导致竞争

**场景**：
1. ProgressPage 每 5 秒刷新项目列表
2. TrainPage 也在自动保存配置
3. 两个写入操作冲突
4. 导致文件损坏或丢失

**验证方法**：
- 检查日志中的时间戳，看是否有并发写入

### 假设 3：路径错误导致删除了错误的文件

**场景**：
1. `projectIndex.configFile` 路径计算错误
2. 删除了其他项目的配置文件

**验证方法**：
- 检查日志中打印的配置文件路径

## 🛠️ 已添加的调试日志

### 1. loadProject 方法
```javascript
console.log(`[ProjectManager] 开始加载项目：${projectId}`);
console.log(`[ProjectManager] 找到项目索引，配置文件路径：${projectIndex.configFile}`);
console.log(`[ProjectManager] ✓ 项目加载成功：${projectId}`);
```

### 2. updateProjectConfig 方法
```javascript
console.log(`[ProjectManager] 开始更新项目配置：${projectId}`);
console.log(`[ProjectManager] 更新内容:`, JSON.stringify(configUpdates, null, 2));
console.log(`[ProjectManager] 找到项目，配置文件路径：${projectIndex.configFile}`);
console.log(`[ProjectManager] 原始配置:`, JSON.stringify(projectConfig.config, null, 2));
```

### 3. 原子写入过程
```javascript
console.log(`[ProjectManager] 原子写入 - 临时文件：${tempFile}`);
console.log(`[ProjectManager] 删除旧配置文件：${projectIndex.configFile}`);
console.log(`[ProjectManager] 旧配置文件不存在（正常）：${projectIndex.configFile}`);
console.log(`[ProjectManager] ✓ 配置文件已更新：${projectIndex.configFile}`);
```

## 🧪 测试步骤

### 步骤 1：重现问题
1. 打开应用，进入 ProgressPage
2. 等待渲染队列刷新（观察控制台日志）
3. 点击某个项目进入 TrainPage
4. 观察是否出现文件删除

### 步骤 2：检查日志
在控制台中搜索以下关键字：
- `[ProjectManager] 开始加载项目`
- `[ProjectManager] 开始更新项目配置`
- `[ProjectManager] 原子写入`
- `[ProjectManager] 删除旧配置文件`

### 步骤 3：检查文件系统
查看 `.luminags` 目录：
```bash
dir E:\GraduationProject\Testoutput\.luminags
```

检查：
- JSON 文件是否存在
- 是否有 `.tmp` 临时文件残留
- 文件最后修改时间

## 📋 预期日志输出

### 正常的加载流程
```
[ProjectManager] 开始加载项目：project_20260313_022_20260313_0227_buy
[ProjectManager] 找到项目索引，配置文件路径：E:\GraduationProject\Testoutput\.luminags\project_20260313_022_20260313_0227_buy.json
[ProjectManager] ✓ 项目加载成功：project_20260313_022_20260313_0227_buy
```

### 正常的更新流程
```
[ProjectManager] 开始更新项目配置：project_20260313_022_20260313_0227_buy
[ProjectManager] 更新内容：{ ... }
[ProjectManager] 找到项目，配置文件路径：E:\GraduationProject\Testoutput\.luminags\project_20260313_022_20260313_0227_buy.json
[ProjectManager] 原始配置：{ ... }
[ProjectManager] 原子写入 - 临时文件：E:\GraduationProject\Testoutput\.luminags\project_20260313_022_20260313_0227_buy.json.tmp
[ProjectManager] 删除旧配置文件：E:\GraduationProject\Testoutput\.luminags\project_20260313_022_20260313_0227_buy.json
[ProjectManager] ✓ 配置文件已更新：E:\GraduationProject\Testoutput\.luminags\project_20260313_022_20260313_0227_buy.json
```

### 异常情况的日志
如果看到以下日志，说明有问题：
```
[ProjectManager] 旧配置文件不存在（正常）：...
// 如果在没有更新操作时出现，说明文件已被删除
```

## 💡 可能的解决方案

### 方案 1：增加文件锁机制
防止并发写入冲突

### 方案 2：改进原子写入的错误处理
```javascript
try {
  await fs.rename(tempFile, projectIndex.configFile);
} catch (err) {
  // 重命名失败，回滚到原文件
  console.error('原子写入失败，尝试回滚:', err);
  // 恢复逻辑...
}
```

### 方案 3：减少自动刷新频率
将 ProgressPage 的刷新间隔从 5 秒改为 10 秒

### 方案 4：在加载项目时不触发更新
确保 `loadProject` 只是读取，不触发任何写入

## 📝 下一步行动

1. **运行应用并观察日志**
   - 从 ProgressPage 点击进入项目
   - 记录所有 `[ProjectManager]` 开头的日志
   
2. **检查文件系统状态**
   - JSON 文件是否真的消失
   - 还是内容被清空
   
3. **根据日志定位问题**
   - 如果是并发问题，会看到多个写入操作交织
   - 如果是原子写入失败，会看到错误日志

4. **提供详细的重现步骤**
   - 具体点击哪个位置
   - 多长时间后发生
   - 是否必现

---

**当前状态**: 已添加详细调试日志，等待用户测试反馈 🔍
