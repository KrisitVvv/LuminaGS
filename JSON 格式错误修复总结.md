# JSON 格式错误修复总结

## 🎯 问题描述

用户报告更新项目时出现 JSON 解析错误：
```
SyntaxError: Unexpected non-whitespace character after JSON at position 2169 (line 102 column 2)
```

## 🔍 问题原因

### 损坏的 JSON 文件结构

检查发现 `project_20260313_024_20260313_0245_c0y.json` 文件在第 102 行后有**重复的字段**：

```json
{
  // ... 正常内容 ...
  "bakingStatus": "idle",
  "bakingProgress": 0,
  "bakingLogs": []
},                    // ← 多余的逗号
  "bakingStatus": "idle",    // ← 重复字段
  "bakingProgress": 0,       // ← 重复字段
  "bakingLogs": []           // ← 重复字段
}
```

### 可能的根本原因

1. **并发写入冲突**
   - `updateProject()` 和 `updateProjectConfig()` 可能同时写入同一个文件
   - 两个方法都调用 `fs.writeFile()`，没有加锁机制

2. **写入过程中被中断**
   - 如果第一次写入未完成时第二次写入开始，可能导致内容重叠

3. **之前的原子写入逻辑遗留问题**
   - 虽然已改为直接写入，但可能之前的 bug 导致文件损坏

---

## ✅ 修复方案

### 1. 紧急修复 - 手动修复损坏的文件

**创建修复脚本**: `simple-fix-json.js`

```javascript
const fs = require('fs');

async function fixJson(filePath) {
  // 读取文件
  const content = await fs.promises.readFile(filePath, 'utf8');
  
  // 通过大括号匹配提取第一个完整的 JSON 对象
  let braceCount = 0;
  let endIndex = -1;
  
  for (let i = 0; i < content.length; i++) {
    if (content[i] === '{') braceCount++;
    if (content[i] === '}') braceCount--;
    
    if (braceCount === 0 && content[i] === '}') {
      endIndex = i + 1;
      break;
    }
  }
  
  // 提取并验证 JSON
  const jsonStr = content.substring(0, endIndex);
  const parsed = JSON.parse(jsonStr);
  
  // 重新格式化并保存
  const formatted = JSON.stringify(parsed, null, 2);
  await fs.promises.writeFile(filePath, formatted, 'utf8');
}
```

**运行修复**:
```bash
node simple-fix-json.js "e:\GraduationProject\Testoutput\.luminags\project_xxx.json"
```

**修复结果**:
- ✅ 成功提取第一个完整的 JSON 对象
- ✅ 移除多余的重复字段
- ✅ 重新格式化并保存

---

### 2. 长期防护 - 增强写入验证

**修改文件**: `gs-ir-visualization/electron/projectManager.js`

#### 修改点 1: `updateProject()` 方法（第 319-340 行）

```javascript
// 保存回文件
console.log(`[ProjectManager] 开始写入项目配置：${projectIndex.configFile}`);
try {
  const content = JSON.stringify(projectConfig, null, 2);
  await fs.writeFile(
    projectIndex.configFile,
    content,
    'utf8'
  );
  console.log(`[ProjectManager] ✓ 项目配置已更新：${projectIndex.configFile}`);
  
  // 验证写入的文件是否有效
  await fs.access(projectIndex.configFile);
  const verifyContent = await fs.readFile(projectIndex.configFile, 'utf8');
  JSON.parse(verifyContent); // 如果能解析成功说明文件完好
  console.log(`[ProjectManager] ✓ 文件验证通过`);
} catch (writeError) {
  console.error(`[ProjectManager] 写入项目配置失败：${writeError.message}`);
  console.error(`[ProjectManager] 错误堆栈:`, writeError.stack);
  throw writeError;
}
```

#### 修改点 2: `updateProjectConfig()` 方法（第 562-581 行）

```javascript
// 5. 安全写入：直接覆盖原文件（避免原子写入导致文件瞬间消失）
console.log(`[ProjectManager] 开始写入配置文件：${projectIndex.configFile}`);
try {
  const content = JSON.stringify(projectConfig, null, 2);
  await fs.writeFile(
    projectIndex.configFile,
    content,
    'utf8'
  );
  console.log(`[ProjectManager] ✓ 配置文件已更新：${projectIndex.configFile}`);
  
  // 验证文件是否存在且格式正确
  await fs.access(projectIndex.configFile);
  const verifyContent = await fs.readFile(projectIndex.configFile, 'utf8');
  JSON.parse(verifyContent); // 验证 JSON 格式
  console.log(`[ProjectManager] ✓ 文件验证成功`);
} catch (writeError) {
  console.error(`[ProjectManager] 写入配置文件失败：${writeError.message}`);
  console.error(`[ProjectManager] 错误堆栈:`, writeError.stack);
  throw writeError;
}
```

---

## 🔧 关键改进

### 1. 写入前缓存内容
```javascript
const content = JSON.stringify(projectConfig, null, 2);
```
- 提前序列化，确保数据一致性

### 2. 写入后验证
```javascript
// 验证文件存在性
await fs.access(projectIndex.configFile);

// 验证 JSON 格式
const verifyContent = await fs.readFile(projectIndex.configFile, 'utf8');
JSON.parse(verifyContent);
```
- 确保文件不仅存在，而且格式正确

### 3. 详细的错误日志
```javascript
catch (writeError) {
  console.error(`[ProjectManager] 写入项目配置失败：${writeError.message}`);
  console.error(`[ProjectManager] 错误堆栈:`, writeError.stack);
  throw writeError;
}
```
- 记录完整错误信息，便于调试

---

## 📊 修复对比

### 修复前 ❌

```javascript
// updateProject - 无验证
await fs.writeFile(
  projectIndex.configFile,
  JSON.stringify(projectConfig, null, 2),
  'utf8'
);

// 风险：
// - 不检查写入是否成功
// - 不验证文件格式
// - 如果并发写入会导致内容重叠
```

### 修复后 ✅

```javascript
// 1. 序列化内容
const content = JSON.stringify(projectConfig, null, 2);

// 2. 写入文件
await fs.writeFile(projectIndex.configFile, content, 'utf8');

// 3. 验证文件存在
await fs.access(projectIndex.configFile);

// 4. 验证 JSON 格式
const verifyContent = await fs.readFile(projectIndex.configFile, 'utf8');
JSON.parse(verifyContent);

// 5. 错误处理
try {
  // ...写入操作...
} catch (writeError) {
  console.error(`写入失败：${writeError.message}`);
  console.error(`错误堆栈:`, writeError.stack);
  throw writeError;
}
```

---

## 🛡️ 预防措施

### 1. 添加写入锁（未来改进）

虽然当前修复已经添加了验证，但为了防止并发写入冲突，可以考虑：

```javascript
class ProjectManager {
  constructor() {
    this.writeLocks = new Map(); // projectId -> boolean
  }
  
  async updateProject(projectId, data) {
    // 检查是否有其他写入正在进行
    if (this.writeLocks.get(projectId)) {
      console.warn(`[ProjectManager] 项目 ${projectId} 正在写入，等待...`);
      await this.waitForLock(projectId);
    }
    
    // 获取锁
    this.writeLocks.set(projectId, true);
    
    try {
      // 执行写入...
    } finally {
      // 释放锁
      this.writeLocks.set(projectId, false);
    }
  }
}
```

### 2. 定期备份配置文件

在关键操作前备份 JSON 文件：

```javascript
// 写入前备份
const backupPath = projectIndex.configFile + '.bak';
await fs.copyFile(projectIndex.configFile, backupPath);
```

### 3. 使用写入队列

将写入操作排队，确保顺序执行：

```javascript
class ProjectManager {
  constructor() {
    this.writeQueue = Promise.resolve();
  }
  
  async queueWrite(projectId, operation) {
    this.writeQueue = this.writeQueue.then(() => operation());
    return this.writeQueue;
  }
}
```

---

## 📝 工具文件

已创建两个修复工具：

### 1. `fix-json.js` - 智能修复工具
- 尝试自动修复常见的 JSON 错误
- 移除重复字段
- 批量修复支持

**用法**:
```bash
# 修复单个文件
node fix-json.js "path/to/file.json"

# 批量修复整个目录
node fix-json.js --all "path/to/.luminags"
```

### 2. `simple-fix-json.js` - 简单修复工具
- 提取第一个完整的 JSON 对象
- 简单粗暴但有效
- 适用于严重损坏的文件

**用法**:
```bash
node simple-fix-json.js "path/to/file.json"
```

---

## ✅ 验证清单

修复完成后，请检查以下内容：

- [ ] JSON 文件可以正常解析
- [ ] 所有必需字段都存在
- [ ] 没有重复的键
- [ ] 文件格式符合预期
- [ ] 应用可以正常读取和更新文件
- [ ] 日志中无 JSON 解析错误

---

## 🎯 总结

通过这次修复：

1. **紧急修复**: 使用脚本快速恢复了损坏的 JSON 文件
2. **长期防护**: 在两个写入方法中添加了详细的日志和验证逻辑
3. **问题追踪**: 确定了可能的根本原因是并发写入冲突
4. **预防建议**: 提出了写入锁、备份、队列等长期改进方案

下次如果遇到类似问题，可以使用提供的修复工具快速恢复！
