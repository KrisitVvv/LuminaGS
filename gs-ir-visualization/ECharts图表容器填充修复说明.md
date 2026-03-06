# ECharts 图表容器填充修复说明

## 📋 问题描述

Loss 和 PSNR 两个 ECharts 图表在 `charts-grid` 容器中并排显示时，右侧 PSNR 图表区域存在明显白色间隙，未能完全填充其所在的布局单元格。

## 🔍 根本原因

1. **`.chart-card` 缺少明确的宽高设置**：未设置 `width: 100%` 和 `height: 100%`
2. **ECharts 初始化后未调用 `resize()`**：导致图表未正确计算容器尺寸
3. **缺少窗口 resize 监听处理**：`handleResize` 方法未实现

## ✅ 修复方案

### 1️⃣ CSS 样式优化

**文件**：`src/components/pages/TrainPage.vue`（第 1613-1618 行）

**修改内容**：
```css
.chart-card {
  background: white;
  padding: 1rem;
  border-radius: 1rem;
  border: 1px solid #e2e8f0;
  box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
  width: 100%;              /* ✓ 新增：宽度占满父容器 */
  height: 100%;             /* ✓ 新增：高度占满父容器 */
  box-sizing: border-box;   /* ✓ 新增：包含 padding 在宽度内 */
  display: flex;            /* ✓ 新增：弹性布局 */
  flex-direction: column;   /* ✓ 新增：垂直方向排列子元素 */
}
```

**说明**：
- `width: 100%` - 确保卡片宽度填满网格单元格
- `height: 100%` - 确保卡片高度填满父容器
- `box-sizing: border-box` - 确保 padding 不会增加实际宽度
- `display: flex` + `flex-direction: column` - 确保内部元素垂直排列并填满空间

---

### 2️⃣ ECharts 初始化后立即调整大小

**文件**：`src/components/pages/TrainPage.vue`（第 478-483 行、第 542-547 行）

**修改内容**：
```javascript
initCharts() {
  // 初始化 Loss 图表
  const lossChartEl = this.$refs.lossChart;
  if (lossChartEl) {
    this.lossChartInstance = echarts.init(lossChartEl);
    this.lossChartInstance.setOption({
      // ... 配置项 ...
    });
    
    // ✓ 强制调整大小以确保填满容器
    setTimeout(() => {
      this.lossChartInstance.resize();
    }, 100);
  }
  
  // 初始化 PSNR 图表
  const psnrChartEl = this.$refs.psnrChart;
  if (psnrChartEl) {
    this.psnrChartInstance = echarts.init(psnrChartEl);
    this.psnrChartInstance.setOption({
      // ... 配置项 ...
    });
    
    // ✓ 强制调整大小以确保填满容器
    setTimeout(() => {
      this.psnrChartInstance.resize();
    }, 100);
  }
}
```

**说明**：
- 使用 `setTimeout(..., 100)` 延迟 100ms 调用 `resize()`
- 确保 DOM 完全渲染后再调整图表大小
- 两个图表都应用相同的处理逻辑

---

### 3️⃣ 实现 handleResize 方法

**文件**：`src/components/pages/TrainPage.vue`（第 420-430 行）

**修改内容**：
```javascript
handleResize() {
  // 窗口大小变化时调整图表大小
  this.$nextTick(() => {
    if (this.lossChartInstance) {
      this.lossChartInstance.resize();
    }
    if (this.psnrChartInstance) {
      this.psnrChartInstance.resize();
    }
  });
}
```

**说明**：
- 使用 `$nextTick()` 确保 DOM 更新后再调整
- 同时调整两个图表的大小
- 该方法已在 `mounted()` 中注册为 `window.resize` 事件监听器

---

## 📊 布局结构分析

### 原始结构
```
.monitoring-panel
  └─ .tab-content
      └─ .charts-grid (display: grid)
          ├─ .chart-card (Loss)
          │   ├─ .chart-title
          │   └─ .chart-container (ref="lossChart")
          └─ .chart-card (PSNR)
              ├─ .chart-title
              └─ .chart-container (ref="psnrChart")
```

### CSS Grid 配置
```css
.charts-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;  /* 等分两列 */
  gap: 1.5rem;                      /* 列间距 */
}
```

### 盒模型对比

**修复前**：
```
.chart-card
  width: auto (可能小于父容器)
  height: auto (可能小于父容器)
  padding: 1rem (额外增加宽度)
```

**修复后**：
```
.chart-card
  width: 100% (填满父容器)
  height: 100% (填满父容器)
  box-sizing: border-box (padding 包含在宽度内)
  display: flex (子元素自动填满剩余空间)
```

---

## 🎯 预期效果

### 视觉效果
- ✅ Loss 和 PSNR 图表**等宽**且**紧密排列**
- ✅ 两个图表**完全填满**各自的卡片容器
- ✅ **无多余白色间隙**
- ✅ 左右对称，视觉均衡

### 响应式行为
- ✅ 窗口大小调整时**自动适应**
- ✅ 图表始终保持**填满容器**
- ✅ 无变形或拉伸失真

---

## 🔧 技术要点

### 1. Grid 布局
```css
grid-template-columns: 1fr 1fr;
```
- `1fr` 表示"分数单位"，两个 `1fr` 意味着平均分配空间
- 比使用百分比更灵活，能自动处理 gap

### 2. Flexbox 配合
```css
display: flex;
flex-direction: column;
```
- 确保 `.chart-card` 内的子元素（标题 + 图表容器）垂直排列
- 图表容器会自动占据剩余空间

### 3. ECharts resize() 时机
```javascript
setTimeout(() => {
  chart.resize();
}, 100);
```
- 延迟 100ms 确保 DOM 已完全渲染
- 避免在容器尺寸未确定时调整图表

### 4. box-sizing: border-box
```css
box-sizing: border-box;
```
- padding 和 border 包含在 width/height 内
- 避免 padding 导致实际尺寸超出 100%

---

## 🚀 使用步骤

1. **重启 Electron 应用**
   ```bash
   cd gs-ir-visualization
   npm run dev
   ```

2. **打开训练页面**：导航到 TrainPage

3. **启动训练**：点击"开始 Stage1"

4. **观察图表显示**：
   - Loss 和 PSNR 图表应等宽显示
   - 无右侧空白区域
   - 图表完全填充卡片

5. **测试响应式**：
   - 调整浏览器窗口大小
   - 图表应自动调整并保持填满状态

---

## 🐛 故障排查

### 问题 1：图表仍然有空白

**检查项**：
1. 浏览器开发者工具 → Elements → 选中 `.chart-card`
2. 查看 Computed 面板中的 width 和 height
3. 确认是否为 100%

**解决方法**：
```javascript
// 在 initCharts 中添加更详细的日志
console.log('图表容器尺寸:', {
  width: this.$refs.lossChart.offsetWidth,
  height: this.$refs.lossChart.offsetHeight
});
```

### 问题 2：窗口调整时图表不跟随

**检查项**：
1. Console 中是否有错误
2. `handleResize` 是否被调用

**解决方法**：
```javascript
// 添加调试日志
handleResize() {
  console.log('窗口大小变化，调整图表...');
  this.$nextTick(() => {
    if (this.lossChartInstance) {
      console.log('调整 Loss 图表');
      this.lossChartInstance.resize();
    }
    if (this.psnrChartInstance) {
      console.log('调整 PSNR 图表');
      this.psnrChartInstance.resize();
    }
  });
}
```

### 问题 3：图表变形或拉伸

**原因**：ECharts 的 grid 配置可能不合适

**解决方法**：调整 grid 配置：
```javascript
grid: {
  left: '12%',   // 增加左边距
  right: '8%',   // 增加右边距
  bottom: '18%', // 增加下边距
  top: '8%',     // 增加上边距
  containLabel: true
}
```

---

## 📝 修改文件清单

1. ✅ `src/components/pages/TrainPage.vue`
   - `.chart-card` CSS 样式（第 1613-1618 行）
   - `initCharts()` 方法（第 478-483 行、第 542-547 行）
   - `handleResize()` 方法（第 420-430 行）

---

## ✅ 验证清单

- [x] `.chart-card` 设置 `width: 100%`
- [x] `.chart-card` 设置 `height: 100%`
- [x] `.chart-card` 设置 `box-sizing: border-box`
- [x] `.chart-card` 设置 `display: flex`
- [x] Loss 图表初始化后调用 `resize()`
- [x] PSNR 图表初始化后调用 `resize()`
- [x] `handleResize()` 方法已实现
- [x] 窗口 resize 事件已监听
- [x] 代码无语法错误

---

## 📞 技术支持

如遇到问题，请使用浏览器开发者工具：

1. **Elements 面板**：检查 DOM 结构和 CSS
2. **Computed 面板**：查看实际计算的宽高
3. **Console 面板**：查看调试日志
4. **Network 面板**：确认资源加载正常

---

**修复完成日期**：2026 年 3 月 6 日  
**修复方案**：CSS Flexbox + ECharts resize()  
**测试状态**：✓ 已通过语法检查
