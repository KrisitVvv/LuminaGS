# JSON 解析错误修复 - Unexpected end of JSON input

## 问题描述

用户在更新项目配置时遇到错误：
```
更新项目配置失败：SyntaxError: Unexpected end of JSON input
```

## 根本原因

该错误发生在 `projectManager.js` 的以下两个方法中：

1. **`updateProject()`** - 第 205 行
2. **`updateProjectConfig()`** - 第 494 行

当项目配置文件出现以下情况时，`JSON.parse()` 会失败：
- 文件为空（0 字节）
- 文件内容被截断
- 并发写入冲突导致数据损坏
- 磁盘写入延迟或中断

## 解决方案

### 1. 增强错误处理

在 `updateProject()` 和 `updateProjectConfig()` 方法中添加多层防护：

#### 第一层：读取文件时的错误捕获
```javascript
let configContent;
try {
  configContent = await fs.readFile(projectIndex.configFile, 'utf8');
  console.log(`[ProjectManager] ✓ 成功读取配置文件`);
} catch (readError) {
  console.error(`[ProjectManager] ✗ 读取配置文件失败:`, readError.message);
  throw new Error(`无法读取项目配置文件：${readError.message}`);
}
```

#### 第二层：JSON 解析时的错误捕获和自动修复
```javascript
let projectConfig;
try {
  projectConfig = JSON.parse(configContent);
  console.log(`[ProjectManager] ✓ JSON 解析成功`);
} catch (parseError) {
  console.error(`[ProjectManager] ✗ JSON 解析失败：${parseError.message}`);
  console.error(`[ProjectManager] 文件内容预览:`, configContent.substring(0, 200));
  
  // 尝试自动修复：提取第一个完整的 JSON 对象
  let braceCount = 0;
  let endIndex = -1;
  
  for (let i = 0; i < configContent.length; i++) {
    if (configContent[i] === '{') braceCount++;
    if (configContent[i] === '}') braceCount--;
    
    if (braceCount === 0 && configContent[i] === '}') {
      endIndex = i + 1;
      break;
    }
  }
  
  if (endIndex !== -1) {
    const jsonStr = configContent.substring(0, endIndex);
    try {
      projectConfig = JSON.parse(jsonStr);
      console.log(`[ProjectManager] ✓ JSON 修复成功`);
    } catch (fixError) {
      throw new Error(`JSON 损坏且无法修复：${parseError.message}`);
    }
  } else {
    throw new Error(`JSON 严重损坏，无法恢复：${parseError.message}`);
  }
}
```

### 2. 修复策略说明

#### 括号匹配算法
通过计算大括号 `{}` 的嵌套层级来定位第一个完整的 JSON 对象：

1. 初始化 `braceCount = 0`
2. 遍历文件内容：
   - 遇到 `{` 时 `braceCount++`
   - 遇到 `}` 时 `braceCount--`
   - 当 `braceCount === 0` 且当前字符是 `}` 时，找到完整对象
3. 提取从开头到第一个闭合 `}` 的子字符串
4. 尝试解析这个子字符串

#### 适用场景
- ✅ 文件末尾有额外逗号
- ✅ 文件被追加了重复字段
- ✅ 文件被部分截断但保留了完整结构
- ❌ 文件完全为空
- ❌ JSON 结构本身不完整

### 3. 日志增强

添加详细的调试日志帮助排查问题：

```javascript
console.log(`[ProjectManager] ✓ 成功读取配置文件：${projectIndex.configFile}`);
console.log(`[ProjectManager] ✓ JSON 解析成功`);
console.log(`[ProjectManager] 尝试自动修复 JSON...`);
console.log(`[ProjectManager] ✓ JSON 修复成功`);
console.error(`[ProjectManager] ✗ JSON 解析失败`);
console.error(`[ProjectManager] 文件内容预览:`, ...);
```

## 修改的文件

### e:/GraduationProject/LuminaGS/gs-ir-visualization/electron/projectManager.js

#### 修改 1: updateProject() 方法（第 194-251 行）
- 添加了文件读取的错误捕获
- 添加了 JSON 解析的错误捕获
- 实现了自动修复逻辑
- 增强了日志输出

#### 修改 2: updateProjectConfig() 方法（第 520-564 行）
- 同样的错误处理机制
- 同样的自动修复逻辑
- 同样的详细日志

## 测试验证

### 测试场景 1: 正常 JSON 文件
```bash
# 应该正常解析
node -e "
const fs = require('fs');
const content = fs.readFileSync('test.json', 'utf8');
const parsed = JSON.parse(content);
console.log('✓ 解析成功');
"
```

### 测试场景 2: 损坏的 JSON 文件（有重复字段）
```json
{
  "name": "test",
  "value": 123
},
  "status": "completed"
}
```

修复逻辑会提取：
```json
{
  "name": "test",
  "value": 123
}
```

### 测试场景 3: 空文件
```bash
# 应该抛出清晰的错误信息
node -e "
const fs = require('fs');
const content = '';
try {
  const parsed = JSON.parse(content);
} catch (e) {
  console.error('预期错误:', e.message);
}
"
```

## 预防措施

### 1. 写入时验证
在每次写入后立即验证文件完整性（已有）：
```javascript
await fs.writeFile(...);
const verifyContent = await fs.readFile(...);
JSON.parse(verifyContent); // 验证通过
```

### 2. 避免并发写入
- 使用防抖（debounce）减少频繁保存
- 确保同一时间只有一个写入操作

### 3. 使用原子写入（可选）
虽然之前因为原子写入导致文件"消失"问题而改用直接覆盖，但可以考虑更安全的方案：
```javascript
// 先写入临时文件，再重命名（但在 Windows 上有风险）
await fs.writeFile(tempPath, content);
await fs.rename(tempPath, finalPath);
```

### 4. 定期备份
可以定期备份重要的项目配置文件。

## 已知限制

### 1. 无法修复的情况
- 文件完全为空（0 字节）
- JSON 结构严重损坏（如缺少开括号）
- 编码错误或二进制损坏

### 2. 可能的数据丢失
自动修复可能会丢失部分数据（如追加的字段），但这比完全无法读取要好。

## 后续改进建议

### 1. 添加事务支持
```javascript
async updateProjectWithTransaction(projectId, data) {
  // 1. 备份原文件
  const backupPath = projectIndex.configFile + '.bak';
  await fs.copyFile(projectIndex.configFile, backupPath);
  
  try {
    // 2. 执行更新
    await this.updateProject(projectId, data);
    
    // 3. 验证成功
    await fs.unlink(backupPath);
  } catch (error) {
    // 4. 回滚
    await fs.copyFile(backupPath, projectIndex.configFile);
    await fs.unlink(backupPath);
    throw error;
  }
}
```

### 2. 添加文件锁
防止并发写入冲突。

### 3. 使用数据库
考虑使用 SQLite 等嵌入式数据库代替 JSON 文件，提供更好的事务支持和数据完整性。

## 故障排查流程

当再次遇到 JSON 解析错误时，按以下步骤排查：

1. **检查错误日志**
   ```
   [ProjectManager] ✗ JSON 解析失败：Unexpected end of JSON input
   [ProjectManager] 文件内容预览：{...}
   [ProjectManager] 尝试自动修复 JSON...
   ```

2. **查看文件状态**
   ```powershell
   Get-Item "path/to/config.json" | Select-Object Length, LastWriteTime
   Get-Content "path/to/config.json" -Raw
   ```

3. **手动修复（如果自动修复失败）**
   ```bash
   node simple-fix-json.js path/to/config.json
   ```

4. **验证修复结果**
   ```javascript
   const config = require('./path/to/config.json');
   console.log('✓ 加载成功');
   ```

## 总结

本次修复通过以下方式增强了 JSON 文件的健壮性：

✅ **多层防护**：读取、解析、写入都有错误处理  
✅ **自动修复**：能修复常见的 JSON 损坏问题  
✅ **详细日志**：便于故障排查  
✅ **清晰错误**：无法修复时提供明确的错误信息  

这些改进确保了即使在文件损坏的情况下，系统也能最大程度地恢复数据并继续运行。
