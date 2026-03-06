<template>
  <section class="train-container">
    <div class="train-content">
      <!-- 左侧参数设置 -->
      <div class="params-panel">
        <h3 class="panel-title">训练参数</h3>
        <div class="params-form">
          <!-- 项目名称输入框 -->
          <div class="form-group">
            <label class="form-label">项目名称</label>
            <input 
              class="text-input" 
              v-model="projectName" 
              placeholder="留空则自动生成（如 project_20250405_1430）"
              @blur="sanitizeProjectName; triggerAutoSave()"
            >
          </div>
          
          <div class="form-group">
            <label class="form-label">输出路径 (-m)</label>
            <div class="input-group">
              <input class="path-input" v-model="modelPath" placeholder="outputs/lego/" @blur="triggerAutoSave()">
              <button class="browse-btn" @click="selectFolder('modelPath')"><span class="iconify" data-icon="solar:folder-linear"></span></button>
            </div>
          </div>
          
          <div class="form-group">
            <label class="form-label">数据集路径 (-s)</label>
            <div class="input-group">
              <input class="path-input" v-model="sourcePath" placeholder="datasets/TensoIR/lego/" @blur="triggerAutoSave()">
              <button class="browse-btn" @click="selectFolder('sourcePath')"><span class="iconify" data-icon="solar:folder-linear"></span></button>
            </div>
          </div>
          
          <div class="form-group">
            <label class="form-label">训练轮次 (Iterations)</label>
            <input class="number-input" type="number" v-model.number="iterations" @change="triggerAutoSave()">
          </div>
          
          <div class="form-group">
            <label class="form-label">Baking 检查点</label>
            <div class="input-group">
              <input class="path-input" v-model="checkpoint" placeholder="outputs/lego/chkpnt30000.pth" @blur="triggerAutoSave()">
              <button class="browse-btn" @click="selectFile('checkpoint')"><span class="iconify" data-icon="solar:file-linear"></span></button>
            </div>
          </div>
          
          <div class="form-section">
            <h4 class="section-title">Stage1 参数</h4>
            <div class="checkbox-group">
              <label class="checkbox-label">
                <input type="checkbox" v-model="evalMode" @change="triggerAutoSave()">
                <span>评估模式 (--eval)</span>
              </label>
            </div>
            <div class="form-group" style="margin-top: 0.75rem;">
              <label class="form-label">分辨率压缩 (-r)</label>
              <select class="select-input" v-model.number="resolution" @change="handleResolutionChange; triggerAutoSave()">
                <option :value="1">原始分辨率 (1/1)</option>
                <option :value="2">1/2 分辨率</option>
                <option :value="4">1/4 分辨率</option>
                <option :value="8">1/8 分辨率</option>
                <option :value="16">1/16 分辨率</option>
              </select>
              <div v-if="resolution === 16" class="help-text">
                <span class="iconify" data-icon="solar:info-circle-linear"></span>
                使用 image_8 目录，-r 参数自动设为 2
              </div>
            </div>
          </div>
          
          <div class="form-section">
            <h4 class="section-title">Baking 参数</h4>
            <div class="form-group">
              <label class="form-label">Bound</label>
              <input class="number-input" type="number" step="0.1" v-model.number="bound" @change="triggerAutoSave()">
            </div>
            <div class="form-group">
              <label class="form-label">Occlusion Resolution</label>
              <input class="number-input" type="number" v-model.number="occluRes" @change="triggerAutoSave()">
            </div>
            <div class="form-group">
              <label class="form-label">Occlusion Threshold</label>
              <input class="number-input" type="number" step="0.01" v-model.number="occlusion" @change="triggerAutoSave()">
            </div>
          </div>
          
          <div class="form-section">
            <h4 class="section-title">Stage2 参数</h4>
            <div class="checkbox-group">
              <label class="checkbox-label">
                <input type="checkbox" v-model="gamma" @change="triggerAutoSave()">
                <span>Gamma 校正 (--gamma)</span>
              </label>
              <label class="checkbox-label">
                <input type="checkbox" v-model="indirect" @change="triggerAutoSave()">
                <span>间接光照 (--indirect)</span>
              </label>
            </div>
          </div>
          
          <div class="actions-section">
            <button class="start-btn" @click="startStage1" :disabled="isTraining">
              <span class="iconify" data-icon="solar:play-bold"></span> 开始 Stage1
            </button>
            
            <button class="baking-btn" @click="startBaking" :disabled="isBaking || !canStartBaking">
              <span class="iconify" data-icon="solar:cookie-linear"></span> 开始 Baking
            </button>
            
            <button class="start-btn stage2-btn" @click="startStage2" :disabled="isTraining || !canStartStage2">
              <span class="iconify" data-icon="solar:play-bold"></span> 开始 Stage2
            </button>
            
            <div class="control-buttons">
              <button class="stop-btn" @click="stopTraining" :disabled="!isTraining && !isBaking">终止</button>
            </div>
            
            <!-- 数据集转换提示 -->
            <div v-if="needsConversion" class="conversion-alert">
              <div class="alert-icon">
                <span class="iconify" data-icon="solar:danger-circle-linear"></span>
              </div>
              <div class="alert-content">
                <div class="alert-title">需要转换数据集格式</div>
                <div class="alert-text">当前数据集不符合 TensoIR 或 Mip-NeRF 360 规范，需要使用 COLMAP 进行处理。</div>
              </div>
              <button class="convert-btn" @click="startConversion" :disabled="isConverting">
                <span class="iconify" :class="{ 'spin-icon': isConverting }" :data-icon="isConverting ? 'solar:refresh-linear' : 'solar:refresh-linear'"></span> 
                {{ isConverting ? '转换中...' : '开始转换' }}
              </button>
            </div>
          </div>
        </div>
      </div>
      
      <!-- 右侧监控与预览 -->
      <div class="monitoring-panel">
        <div class="tabs-header">
          <button 
            class="tab-button" 
            :class="{ active: activeTab === 'training' }"
            @click="activeTab = 'training'"
          >
            训练监控
          </button>
          <button 
            class="tab-button" 
            :class="{ active: activeTab === 'baking' }"
            @click="activeTab = 'baking'"
          >
            Baking 监控
          </button>
        </div>
        
        <div v-if="activeTab === 'training'" class="tab-content">
          <div class="charts-grid">
            <div class="chart-card">
              <h4 class="chart-title">损失函数 (Loss)</h4>
              <div ref="lossChart" class="chart-container"></div>
            </div>
            <div class="chart-card">
              <h4 class="chart-title">峰值信噪比 (PSNR)</h4>
              <div ref="psnrChart" class="chart-container"></div>
            </div>
            <div class="chart-card">
              <h4 class="chart-title">结构相似性 (SSIM)</h4>
              <div ref="ssimChart" class="chart-container"></div>
            </div>
            <div class="chart-card">
              <h4 class="chart-title">评估 L1 (Eval L1)</h4>
              <div ref="evalL1Chart" class="chart-container"></div>
            </div>
          </div>
          
          <div class="preview-card">
            <div class="preview-header">
              <h4 class="preview-title">动态迭代预览</h4>
              <button class="refresh-preview-btn" @click="updatePreviewImage" :disabled="!modelPath">
                <span class="iconify" data-icon="solar:refresh-linear"></span>
                刷新预览
              </button>
            </div>
            <div class="preview-container">
              <img v-if="previewImage" class="preview-image" :src="previewImage" alt="Training Preview">
              <div v-else class="preview-placeholder">等待训练数据...</div>
              <div class="iteration-overlay">Iter: {{ currentIteration }} / {{ iterations }}</div>
            </div>
          </div>
          
          <div class="log-card">
            <h4 class="log-title">训练日志</h4>
            <div ref="logContainer" class="log-container">
              <div v-for="(log, index) in logs" :key="index" class="log-line" :class="log.type">
                <span class="log-time">{{ log.time }}</span>
                <span class="log-message">{{ log.message }}</span>
              </div>
            </div>
          </div>
        </div>
        
        <div v-if="activeTab === 'baking'" class="tab-content">
          <div class="baking-status">
            <div class="status-item">
              <span class="status-label">状态:</span>
              <span :class="['status-value', bakingStatus]">{{ bakingStatusText }}</span>
            </div>
            <div class="status-item">
              <span class="status-label">进度:</span>
              <div class="progress-bar">
                <div class="progress-fill" :style="{ width: bakingProgress + '%' }"></div>
              </div>
              <span class="progress-text">{{ bakingProgress }}%</span>
            </div>
          </div>
          
          <div class="log-card">
            <h4 class="log-title">Baking 日志</h4>
            <div ref="bakingLogContainer" class="log-container">
              <div v-for="(log, index) in bakingLogs" :key="index" class="log-line" :class="log.type">
                <span class="log-time">{{ log.time }}</span>
                <span class="log-message">{{ log.message }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
    
    <!-- 数据集转换等待动画弹窗 -->
    <div v-if="isConverting" class="conversion-modal-overlay">
      <div class="conversion-modal">
        <div class="modal-header">
          <h3 class="modal-title">
            <span class="iconify spin-icon" data-icon="solar:refresh-linear"></span>
            正在运行 COLMAP
          </h3>
        </div>
        
        <div class="modal-body">
          <!-- 加载动画 -->
          <div class="loading-animation">
            <div class="spinner-ring"></div>
            <div class="spinner-ring"></div>
            <div class="spinner-ring"></div>
          </div>
          
          <!-- 进度提示 -->
          <div class="progress-info">
            <p class="loading-text">正在进行特征提取和三维重建</p>
            <p class="loading-subtext">这可能需要几分钟到几小时，取决于图片数量和设备性能</p>
          </div>
          
          <!-- 实时日志输出 -->
          <div class="conversion-log-container">
            <div class="log-header">
              <span class="iconify" data-icon="solar:file-text-linear"></span>
              COLMAP 输出日志
            </div>
            <div ref="conversionLogContainer" class="log-output">
              <div v-for="(log, index) in conversionLogs" :key="index" class="log-line" :class="log.type">
                <span class="log-time">{{ log.time }}</span>
                <span class="log-message">{{ log.message }}</span>
              </div>
            </div>
          </div>
        </div>
        
        <div class="modal-footer">
          <button class="cancel-btn" @click="stopConversion" :disabled="isStopping">
            <span class="iconify" data-icon="solar:stop-circle-linear"></span>
            {{ isStopping ? '停止中...' : '取消转换' }}
          </button>
        </div>
      </div>
    </div>
  </section>
</template>

<script>
import * as echarts from 'echarts';

export default {
  name: 'TrainPage',
  data() {
    return {
      // 训练参数
      projectName: '', // 项目名称
      modelPath: 'outputs/lego/',
      sourcePath: 'datasets/TensoIR/lego/',
      iterations: 30000,
      checkpoint: '',
      evalMode: true,
      gamma: false,
      indirect: false,
      bound: 1.5,
      occluRes: 128,
      resolution: 1, // 分辨率压缩参数，1、2、4、8 分别表示 1/1、1/2、1/4、1/8
      
      // 训练状态
      isTraining: false,
      isBaking: false,
      currentIteration: 0,
      activeTab: 'training',
      
      // 图表实例
      lossChartInstance: null,
      psnrChartInstance: null,
      ssimChartInstance: null,
      evalL1ChartInstance: null,  // 新增：Eval L1 图表实例
      
      // 响应式布局观察器
      resizeObserver: null,
      
      // 图表数据
      lossData: [],
      psnrData: [],
      ssimData: [],
      evalL1Data: [],  // 新增：Eval L1 数据
      
      // 日志
      logs: [],
      bakingLogs: [],
      
      // 预览
      previewImage: null,
            
      // Baking 状态
      bakingStatus: 'idle', // idle, running, completed, error
      bakingProgress: 0,
            
      // 定时器
      trainingTimer: null,
      
      // 数据集格式
      datasetFormat: 'unknown', // unknown, tensoir, mipnerf360, custom
      needsConversion: false,
      conversionProgress: 0,
      isConverting: false,
      isStopping: false,
      
      // 转换日志
      conversionLogs: [],
      
      // 图片子目录选择
      imageSubdir: 'images', // 默认值
      
      // 当前项目 ID（用于自动保存）
      currentProjectId: null,
      
      // 防抖定时器
      saveDebounceTimer: null
    }
  },
  computed: {
    canStartBaking() {
      return this.checkpoint && this.checkpoint.endsWith('.pth');
    },
    canStartStage2() {
      return this.checkpoint && this.checkpoint.endsWith('.pth');
    },
    bakingStatusText() {
      const statusMap = {
        idle: '未开始',
        running: '进行中',
        completed: '已完成',
        error: '错误'
      };
      return statusMap[this.bakingStatus] || '未知';
    }
  },
  async mounted() {
    this.initCharts();
    this.setupIPCListeners();
    window.addEventListener('resize', this.handleResize);
    
    // 监听 Electron 窗口状态变化事件
    window.addEventListener('window-maximized', this.handleWindowMaximized);
    window.addEventListener('window-restored', this.handleWindowRestored);
    
    // 使用 ResizeObserver 监听图表容器尺寸变化（基于窗体大小）
    this.setupResizeObserver();
    
    // 检查是否有 resumeProjectId 参数，有则加载项目配置
    if (this.$route.query.resumeProjectId) {
      await this.loadProjectFromRoute();
    }
    
    // 检查是否有初始预览图（从 ProgressPage 传递过来）
    if (this.$route.query.initialPreviewImage) {
      console.log('[初始预览] 收到来自 ProgressPage 的预览图');
      console.log('[初始预览] Base64 长度:', this.$route.query.initialPreviewImage.length);
      console.log('[初始预览] Base64 前缀:', this.$route.query.initialPreviewImage.substring(0, 22));
      
      // 使用 Image 对象预加载，确保图片可以正常显示
      const img = new Image();
      img.onload = () => {
        console.log('[初始预览] ✓ 图片预加载成功，更新到界面');
        this.previewImage = this.$route.query.initialPreviewImage;
      };
      img.onerror = (err) => {
        console.error('[初始预览] ✗ 图片预加载失败:', err);
        // 即使失败也尝试直接赋值
        this.previewImage = this.$route.query.initialPreviewImage;
      };
      img.src = this.$route.query.initialPreviewImage;
      
      // 清理 URL 参数，避免重复使用
      this.$router.replace({ query: { ...this.$route.query, initialPreviewImage: undefined } });
    }
  },
  beforeUnmount() {
    if (this.lossChartInstance) {
      this.lossChartInstance.dispose();
    }
    if (this.psnrChartInstance) {
      this.psnrChartInstance.dispose();
    }
    if (this.ssimChartInstance) {
      this.ssimChartInstance.dispose();
    }
    if (this.evalL1ChartInstance) {
      this.evalL1ChartInstance.dispose();
    }
    window.removeEventListener('resize', this.handleResize);
    window.removeEventListener('window-maximized', this.handleWindowMaximized);
    window.removeEventListener('window-restored', this.handleWindowRestored);
    
    // 清理 ResizeObserver
    if (this.resizeObserver) {
      this.resizeObserver.disconnect();
    }
  },
  methods: {
    async handleResolutionChange() {
      // 分辨率压缩逻辑优化：
      // 1. 优先查找预压缩目录（images_2, images_4, images_8）
      // 2. 如果预压缩目录不存在，回退到 images 目录并使用 -r 参数
      // 3. imageSubdir 决定输入来源，resolution 参数决定最终输出压缩比
      
      let preferredSubdir = 'images';
      let fallbackNeeded = false;
      
      if (this.resolution === 16) {
        // 1/16 分辨率：优先使用 images_8，其次 images_4，最后 images
        if (await this.checkDirectoryExists('images_8')) {
          preferredSubdir = 'images_8';
        } else if (await this.checkDirectoryExists('images_4')) {
          preferredSubdir = 'images_4';
        } else {
          preferredSubdir = 'images';
          fallbackNeeded = true;
        }
      } else if (this.resolution === 8) {
        // 1/8 分辨率：优先使用 images_8，否则用 images + r=8
        if (await this.checkDirectoryExists('images_8')) {
          preferredSubdir = 'images_8';
        } else {
          preferredSubdir = 'images';
          fallbackNeeded = true;
        }
      } else if (this.resolution === 4) {
        // 1/4 分辨率：优先使用 images_4，否则用 images + r=4
        if (await this.checkDirectoryExists('images_4')) {
          preferredSubdir = 'images_4';
        } else {
          preferredSubdir = 'images';
          fallbackNeeded = true;
        }
      } else if (this.resolution === 2) {
        // 1/2 分辨率：优先使用 images_2，否则用 images + r=2
        if (await this.checkDirectoryExists('images_2')) {
          preferredSubdir = 'images_2';
        } else {
          preferredSubdir = 'images';
          fallbackNeeded = true;
        }
      } else {
        // 原始分辨率：使用 images 目录，不需要压缩
        preferredSubdir = 'images';
      }
      
      this.imageSubdir = preferredSubdir;
      
      // 构建日志信息
      if (fallbackNeeded) {
        this.addLog(`分辨率 1/${this.resolution}：未找到预压缩目录，使用 ${this.imageSubdir} + -r ${this.resolution} 参数`, 'info');
      } else {
        this.addLog(`分辨率 1/${this.resolution}：使用预压缩目录 ${this.imageSubdir}`, 'success');
      }
    },
    
    // 清理项目名称（去除特殊字符和空格）
    sanitizeProjectName() {
      if (this.projectName) {
        // 只保留字母、数字、中文和下划线
        this.projectName = this.projectName.replace(/[^a-zA-Z0-9\u4e00-\u9fa5_]/g, '_');
      }
    },
    
    // 生成默认项目名称（时间戳格式）
    generateDefaultProjectName() {
      const now = new Date();
      const year = now.getFullYear();
      const month = String(now.getMonth() + 1).padStart(2, '0');
      const day = String(now.getDate()).padStart(2, '0');
      const hours = String(now.getHours()).padStart(2, '0');
      const minutes = String(now.getMinutes()).padStart(2, '0');
      return `project_${year}${month}${day}_${hours}${minutes}`;
    },
    
    // 检查数据集目录下的子目录是否存在
    async checkDirectoryExists(subdirName) {
      try {
        if (!this.sourcePath) {
          return false;
        }
        const result = await window.electronAPI?.checkDirectoryExists({
          basePath: this.sourcePath,
          subdir: subdirName
        });
        return result?.exists || false;
      } catch (error) {
        console.error(`检查目录 ${subdirName} 失败:`, error);
        return false;
      }
    },
    
    // 从路由参数加载项目配置
    async loadProjectFromRoute() {
      const projectId = this.$route.query.resumeProjectId;
      if (!projectId) {
        console.warn('[加载项目] 未找到 projectId 参数');
        return;
      }
      
      // 设置当前项目 ID（用于后续自动保存）
      this.currentProjectId = projectId;
      console.log('[加载项目] 设置 currentProjectId:', projectId);
      
      console.log('[加载项目] 准备加载项目:', projectId);
      
      try {
        // 调用 Electron API 获取项目详情
        const result = await window.electronAPI?.getProjectDetail(projectId);
        
        if (!result?.success || !result?.data) {
          throw new Error(result?.error || '加载项目失败');
        }
        
        const project = result.data;
        console.log('[加载项目] 成功获取项目配置:', project);
        
        // 填充表单字段
        this.projectName = project.name || '';
        this.modelPath = project.outputPath || '';
        this.sourcePath = project.sourcePath || '';
        this.iterations = project.config?.iterations || 30000;
        this.evalMode = project.config?.eval || true;
        this.resolution = project.config?.resolution || 1;
        this.gamma = project.config?.gamma || false;
        this.indirect = project.config?.indirect || false;
        this.bound = project.config?.bound || 1.5;
        this.occluRes = project.config?.occluRes || 128;
        this.occlusion = project.config?.occlusion || 0.8;
        
        // 恢复检查点路径（如果有）
        if (project.checkpoint) {
          // 优先使用保存的 checkpoint 路径
          this.checkpoint = project.checkpoint;
          console.log('[加载项目] 恢复 checkpoint 路径:', this.checkpoint);
        } else if (project.stage === 'stage2' || project.stage === 'baking') {
          // 如果没有保存 checkpoint，则从 outputPath 推导
          const lastSlashIndex = project.outputPath.lastIndexOf('/');
          if (lastSlashIndex !== -1) {
            const baseDir = project.outputPath.substring(0, lastSlashIndex);
            this.checkpoint = `${baseDir}/chkpnt${project.currentIteration || 30000}.pth`;
            console.log('[加载项目] 从 outputPath 推导 checkpoint 路径:', this.checkpoint);
          }
        }
        
        // 恢复图表数据
        if (project.metrics) {
          this.lossData = project.metrics.lossHistory || [];
          this.psnrData = project.metrics.psnrHistory || [];
          this.ssimData = project.metrics.ssimHistory || [];
          this.evalL1Data = project.metrics.evalL1History || [];  // 新增：Eval L1 数据
          
          console.log('[加载项目] 恢复图表数据:', {
            loss: this.lossData.length,
            psnr: this.psnrData.length,
            ssim: this.ssimData.length,
            evalL1: this.evalL1Data.length
          });
          
          // 延迟到下一个 tick 确保图表实例已初始化
          this.$nextTick(() => {
            this.updateLossChart();
            this.updatePsnrChart();
            this.updateSsimChart();
            this.updateEvalL1Chart();  // 新增：更新 Eval L1 图表
          });
        }
        
        // 恢复当前迭代次数
        this.currentIteration = project.currentIteration || 0;
        
        // 根据阶段设置状态
        if (project.status === 'training') {
          this.isTraining = true;
          this.addLog(`已恢复项目：${project.name}`, 'success');
          this.addLog(`继续训练 - 当前迭代：${this.currentIteration}`, 'info');
        } else if (project.status === 'waiting') {
          this.addLog(`项目已在队列中等待：${project.name}`, 'info');
        } else if (project.status === 'completed') {
          this.addLog(`项目已完成：${project.name}`, 'success');
        } else if (project.status === 'error') {
          this.addLog(`项目发生错误：${project.name}`, 'error');
        }
        
        // 刷新分辨率选择
        await this.handleResolutionChange();
        
        // 加载最新渲染预览图（如果有）
        console.log('[加载项目] 准备加载最新渲染预览图...');
        await this.updatePreviewImage();
        
        console.log('[加载项目] ✓ 项目配置加载完成');
        
      } catch (error) {
        console.error('[加载项目] 失败:', error);
        this.addLog(`加载项目失败：${error.message}`, 'error');
        alert(`恢复项目失败：${error.message}`);
      }
    },
    
    // 更新 Loss 图表（支持批量数据）
    updateLossChart() {
      if (!this.lossChartInstance) {
        console.warn('Loss 图表实例未初始化');
        return;
      }
      
      try {
        console.log('[更新 Loss 图表] 原始数据数量:', this.lossData.length);
        
        // 支持两种数据格式
        const xData = this.lossData.map(item => {
          // 新格式：{ iteration, value } 或旧格式：{ iter, loss }
          return (item.iteration || item.iter || 0).toString();
        });
        
        const seriesData = this.lossData.map(item => {
          // 新格式：{ iteration, value }
          if (item.value !== undefined && item.value !== null) {
            return parseFloat(item.value);
          }
          // 旧格式：{ iter, loss }
          if (item.loss !== undefined && item.loss !== null) {
            return parseFloat(item.loss);
          }
          return null;
        }).filter(v => v !== null); // 过滤掉 null 值
        
        console.log('[更新 Loss 图表] 有效数据数量:', seriesData.length);
        
        this.lossChartInstance.setOption({
          xAxis: { data: xData },
          series: [{ data: seriesData }]
        });
      } catch (error) {
        console.error('更新 Loss 图表失败:', error);
      }
    },
    
    // 更新 PSNR 图表（支持批量数据）
    updatePsnrChart() {
      if (!this.psnrChartInstance) {
        console.warn('PSNR 图表实例未初始化');
        return;
      }
      
      try {
        console.log('[更新 PSNR 图表] 原始数据数量:', this.psnrData.length);
        
        // 支持两种数据格式
        const xData = this.psnrData.map(item => {
          // 新格式：{ iteration, value } 或旧格式：{ iter, psnr }
          return (item.iteration || item.iter || 0).toString();
        });
        
        const seriesData = this.psnrData.map(item => {
          // 新格式：{ iteration, value }
          if (item.value !== undefined && item.value !== null) {
            return parseFloat(item.value);
          }
          // 旧格式：{ iter, psnr }
          if (item.psnr !== undefined && item.psnr !== null) {
            return parseFloat(item.psnr);
          }
          return null;
        }).filter(v => v !== null); // 过滤掉 null 值
        
        console.log('[更新 PSNR 图表] 有效数据数量:', seriesData.length);
        
        this.psnrChartInstance.setOption({
          xAxis: { data: xData },
          series: [{ data: seriesData }]
        });
      } catch (error) {
        console.error('更新 PSNR 图表失败:', error);
      }
    },
    
    // 更新 SSIM 图表（支持批量数据）
    updateSsimChart() {
      if (!this.ssimChartInstance) {
        console.warn('SSIM 图表实例未初始化');
        return;
      }
      
      try {
        console.log('[更新 SSIM 图表] 原始数据数量:', this.ssimData.length);
        
        // 支持两种数据格式
        const xData = this.ssimData.map(item => {
          // 新格式：{ iteration, value } 或旧格式：{ iter, ssim }
          return (item.iteration || item.iter || 0).toString();
        });
        
        const seriesData = this.ssimData.map(item => {
          // 新格式：{ iteration, value }
          if (item.value !== undefined && item.value !== null) {
            return parseFloat(item.value);
          }
          // 旧格式：{ iter, ssim }
          if (item.ssim !== undefined && item.ssim !== null) {
            return parseFloat(item.ssim);
          }
          return null;
        }).filter(v => v !== null); // 过滤掉 null 值
        
        console.log('[更新 SSIM 图表] 有效数据数量:', seriesData.length);
        
        this.ssimChartInstance.setOption({
          xAxis: { data: xData },
          series: [{ data: seriesData }]
        });
      } catch (error) {
        console.error('更新 SSIM 图表失败:', error);
      }
    },
    
    // 更新 Eval L1 图表（支持批量数据）
    updateEvalL1Chart() {
      if (!this.evalL1ChartInstance) {
        console.warn('Eval L1 图表实例未初始化');
        return;
      }
      
      try {
        console.log('[更新 Eval L1 图表] 原始数据数量:', this.evalL1Data.length);
        
        // 支持两种数据格式
        const xData = this.evalL1Data.map(item => {
          // 新格式：{ iteration, value, type } 或旧格式：{ iter, evalL1 }
          return (item.iteration || item.iter || 0).toString();
        });
        
        const seriesData = this.evalL1Data.map(item => {
          // 新格式：{ iteration, value }
          if (item.value !== undefined && item.value !== null) {
            return parseFloat(item.value);
          }
          // 旧格式：{ iter, evalL1 }
          if (item.evalL1 !== undefined && item.evalL1 !== null) {
            return parseFloat(item.evalL1);
          }
          return null;
        }).filter(v => v !== null); // 过滤掉 null 值
        
        console.log('[更新 Eval L1 图表] 有效数据数量:', seriesData.length);
        
        this.evalL1ChartInstance.setOption({
          xAxis: { data: xData },
          series: [{ data: seriesData }]
        });
      } catch (error) {
        console.error('更新 Eval L1 图表失败:', error);
      }
    },
    
    setupResizeObserver() {
      // 延迟确保 DOM 完全渲染
      this.$nextTick(() => {
        const chartsGrid = document.querySelector('.charts-grid');
        if (chartsGrid) {
          console.log('[响应式布局] 开始监听图表容器，初始宽度:', chartsGrid.offsetWidth);
          
          let resizeTimer = null;
          
          this.resizeObserver = new ResizeObserver(entries => {
            for (let entry of entries) {
              const { width } = entry.contentRect;
              console.log('[窗体大小] 图表容器宽度:', width.toFixed(2), 'px');
              
              // 使用防抖避免频繁调整
              clearTimeout(resizeTimer);
              resizeTimer = setTimeout(() => {
                // 根据容器实际宽度动态调整布局
                if (width < 600) {
                  // 窄窗体：单列布局
                  chartsGrid.style.gridTemplateColumns = '1fr';
                  console.log('[布局切换] 单列模式');
                } else {
                  // 宽窗体：2x2 网格布局
                  chartsGrid.style.gridTemplateColumns = 'repeat(2, 1fr)';
                  console.log('[布局切换] 2x2 网格模式');
                }
                
                // 同时调整所有图表大小（带延迟确保布局已更新）
                this.$nextTick(() => {
                  setTimeout(() => {
                    if (this.lossChartInstance) {
                      this.lossChartInstance.resize();
                      console.log('[图表调整] Loss 图表已调整');
                    }
                    if (this.psnrChartInstance) {
                      this.psnrChartInstance.resize();
                      console.log('[图表调整] PSNR 图表已调整');
                    }
                    if (this.ssimChartInstance) {
                      this.ssimChartInstance.resize();
                      console.log('[图表调整] SSIM 图表已调整');
                    }
                    if (this.evalL1ChartInstance) {
                      this.evalL1ChartInstance.resize();
                      console.log('[图表调整] Eval L1 图表已调整');
                    }
                  }, 50); // 延迟 50ms 确保 CSS 布局已应用
                });
              }, 100); // 100ms 防抖
            }
          });
          
          this.resizeObserver.observe(chartsGrid);
          console.log('[响应式布局] ✓ ResizeObserver 已启动');
        } else {
          console.warn('[响应式布局] ✗ 未找到 .charts-grid 元素');
        }
      });
    },
    
    handleResize() {
      // 窗口大小变化时调整图表大小
      this.$nextTick(() => {
        if (this.lossChartInstance) {
          this.lossChartInstance.resize();
        }
        if (this.psnrChartInstance) {
          this.psnrChartInstance.resize();
        }
        if (this.ssimChartInstance) {
          this.ssimChartInstance.resize();
        }
        if (this.evalL1ChartInstance) {
          this.evalL1ChartInstance.resize();
        }
      });
    },
    
    handleWindowMaximized() {
      console.log('[窗口状态] 最大化/全屏，调整图表...');
      this.$nextTick(() => {
        if (this.lossChartInstance) {
          this.lossChartInstance.resize();
        }
        if (this.psnrChartInstance) {
          this.psnrChartInstance.resize();
        }
        if (this.ssimChartInstance) {
          this.ssimChartInstance.resize();
        }
        if (this.evalL1ChartInstance) {
          this.evalL1ChartInstance.resize();
        }
      });
    },
    
    handleWindowRestored() {
      console.log('[窗口状态] 恢复窗口模式，调整图表...');
      // 延迟一点确保窗口尺寸已稳定
      setTimeout(() => {
        this.$nextTick(() => {
          if (this.lossChartInstance) {
            this.lossChartInstance.resize();
            console.log('[窗口状态] Loss 图表已调整');
          }
          if (this.psnrChartInstance) {
            this.psnrChartInstance.resize();
            console.log('[窗口状态] PSNR 图表已调整');
          }
          if (this.ssimChartInstance) {
            this.ssimChartInstance.resize();
            console.log('[窗口状态] SSIM 图表已调整');
          }
          if (this.evalL1ChartInstance) {
            this.evalL1ChartInstance.resize();
            console.log('[窗口状态] Eval L1 图表已调整');
          }
          
          // 打印容器尺寸用于调试
          const chartsGrid = document.querySelector('.charts-grid');
          if (chartsGrid) {
            console.log('[窗口状态] 图表容器尺寸:', {
              width: chartsGrid.offsetWidth,
              height: chartsGrid.offsetHeight,
              gridTemplateColumns: chartsGrid.style.gridTemplateColumns
            });
          }
        });
      }, 200);
    },
    
    initCharts() {
      // 初始化 Loss 图表
      const lossChartEl = this.$refs.lossChart;
      if (lossChartEl) {
        this.lossChartInstance = echarts.init(lossChartEl);
        this.lossChartInstance.setOption({
          tooltip: {
            trigger: 'axis',
            formatter: '{b}: @{c}'
          },
          xAxis: {
            type: 'category',
            name: '',
            data: [],
            axisLabel: {
              rotate: 45
            }
          },
          yAxis: {
            type: 'value',
            name: 'Loss'
          },
          series: [{
            data: [],
            type: 'line',
            smooth: true,
            lineStyle: {
              color: '#ef4444',
              width: 2
            },
            itemStyle: {
              color: '#ef4444'
            },
            areaStyle: {
              color: {
                type: 'linear',
                x: 0,
                y: 0,
                x2: 0,
                y2: 1,
                colorStops: [
                  { offset: 0, color: 'rgba(239, 68, 68, 0.3)' },
                  { offset: 1, color: 'rgba(239, 68, 68, 0.05)' }
                ]
              }
            }
          }],
          grid: {
            left: '10%',
            right: '5%',
            bottom: '15%',
            top: '5%',
            containLabel: true
          }
        });
        
        // 强制调整大小以确保填满容器
        setTimeout(() => {
          this.lossChartInstance.resize();
        }, 100);
      }
      
      // 初始化 PSNR 图表
      const psnrChartEl = this.$refs.psnrChart;
      if (psnrChartEl) {
        this.psnrChartInstance = echarts.init(psnrChartEl);
        this.psnrChartInstance.setOption({
          tooltip: {
            trigger: 'axis',
            formatter: '{b}: @{c} dB'
          },
          xAxis: {
            type: 'category',
            name: '',
            data: [],
            axisLabel: {
              rotate: 45
            }
          },
          yAxis: {
            type: 'value',
            name: 'PSNR (dB)',
            min: 0
          },
          series: [{
            data: [],
            type: 'line',
            smooth: true,
            lineStyle: {
              color: '#3b82f6',
              width: 2
            },
            itemStyle: {
              color: '#3b82f6'
            },
            areaStyle: {
              color: {
                type: 'linear',
                x: 0,
                y: 0,
                x2: 0,
                y2: 1,
                colorStops: [
                  { offset: 0, color: 'rgba(52, 130, 246, 0.3)' },
                  { offset: 1, color: 'rgba(52, 130, 246, 0.05)' }
                ]
              }
            }
          }],
          grid: {
            left: '10%',
            right: '5%',
            bottom: '15%',
            top: '5%',
            containLabel: true
          }
        });
        
        // 强制调整大小以确保填满容器
        setTimeout(() => {
          this.psnrChartInstance.resize();
        }, 100);
      }
      
      // 初始化 SSIM 图表
      const ssimChartEl = this.$refs.ssimChart;
      if (ssimChartEl) {
        this.ssimChartInstance = echarts.init(ssimChartEl);
        this.ssimChartInstance.setOption({
          tooltip: {
            trigger: 'axis',
            formatter: '{b}: @{c}'
          },
          xAxis: {
            type: 'category',
            name: '',
            data: [],
            axisLabel: {
              rotate: 45
            }
          },
          yAxis: {
            type: 'value',
            name: 'SSIM',
            min: 0,
            max: 1
          },
          series: [{
            data: [],
            type: 'line',
            smooth: true,
            lineStyle: {
              color: '#10b981',
              width: 2
            },
            itemStyle: {
              color: '#10b981'
            },
            areaStyle: {
              color: {
                type: 'linear',
                x: 0,
                y: 0,
                x2: 0,
                y2: 1,
                colorStops: [
                  { offset: 0, color: 'rgba(16, 185, 129, 0.3)' },
                  { offset: 1, color: 'rgba(16, 185, 129, 0.05)' }
                ]
              }
            }
          }],
          grid: {
            left: '10%',
            right: '5%',
            bottom: '15%',
            top: '5%',
            containLabel: true
          }
        });
        
        // 强制调整大小以确保填满容器
        setTimeout(() => {
          this.ssimChartInstance.resize();
        }, 100);
      }
        
      // 初始化 Eval L1 图表
      const evalL1ChartEl = this.$refs.evalL1Chart;
      if (evalL1ChartEl) {
        this.evalL1ChartInstance = echarts.init(evalL1ChartEl);
        this.evalL1ChartInstance.setOption({
          tooltip: {
            trigger: 'axis',
            formatter: '{b}: @{c}'
          },
          xAxis: {
            type: 'category',
            name: '',
            data: [],
            axisLabel: {
              rotate: 45
            }
          },
          yAxis: {
            type: 'value',
            name: 'L1',
            min: 0
          },
          series: [{
            data: [],
            type: 'line',
            smooth: true,
            lineStyle: {
              color: '#f59e0b',
              width: 2
            },
            itemStyle: {
              color: '#f59e0b'
            },
            areaStyle: {
              color: {
                type: 'linear',
                x: 0,
                y: 0,
                x2: 0,
                y2: 1,
                colorStops: [
                  { offset: 0, color: 'rgba(245, 158, 11, 0.3)' },
                  { offset: 1, color: 'rgba(245, 158, 11, 0.05)' }
                ]
              }
            }
          }],
          grid: {
            left: '10%',
            right: '5%',
            bottom: '15%',
            top: '5%',
            containLabel: true
          }
        });
          
        // 强制调整大小以确保填满容器
        setTimeout(() => {
          this.evalL1ChartInstance.resize();
        }, 100);
      }
    },
    
    setupIPCListeners() {
      // 监听训练输出
      window.electronAPI?.onTrainingOutput((data) => {
        this.handleTrainingOutput(data);
      });
      
      // 监听烘焙输出
      window.electronAPI?.onBakingOutput((data) => {
        this.handleBakingOutput(data);
      });
      
      // 监听转换输出
      window.electronAPI?.onConversionOutput((data) => {
        this.handleConversionOutput(data);
      });
      
      // 监听转换完成
      window.electronAPI?.onConversionClose((data) => {
        this.handleConversionClose(data);
      });
      
      // 定期更新预览图片（每 3 秒）
      setInterval(() => {
        if (this.isTraining && this.modelPath) {
          console.log('[定时任务] 尝试更新预览图片...');
          this.updatePreviewImage();
        }
      }, 3000);
    },
    
    // 防抖函数：等待 500ms 无变化后再保存
    debounceSave(func, wait) {
      let timeout;
      return function(...args) {
        clearTimeout(timeout);
        timeout = setTimeout(() => func.apply(this, args), wait);
      };
    },
    
    // 保存项目配置
    async saveProjectConfig() {
      if (!this.currentProjectId) {
        console.log('[保存项目] 无 projectId，跳过保存');
        return;
      }
      
      try {
        const config = {
          projectName: this.projectName,
          outputPath: this.modelPath,
          sourcePath: this.sourcePath,
          iterations: this.iterations,
          resolution: this.resolution,
          evalMode: this.evalMode,
          gamma: this.gamma,
          indirect: this.indirect,
          bound: this.bound,
          occluRes: this.occluRes,
          occlusion: this.occlusion,
          checkpoint: this.checkpoint
        };
        
        const result = await window.electronAPI?.updateProjectConfig(
          this.currentProjectId, 
          config
        );
        
        if (result?.success) {
          console.log(`[保存项目] ✓ 已保存 ${this.currentProjectId}`);
        } else {
          console.error('[保存项目] ✗ 保存失败:', result?.error);
          alert('项目配置保存失败，请检查磁盘权限');
        }
      } catch (error) {
        console.error('[保存项目] 异常:', error);
        alert('项目配置保存失败：' + error.message);
      }
    },
    
    // 创建防抖版本的保存函数（500ms）
    triggerAutoSave() {
      if (this.saveDebounceTimer) {
        clearTimeout(this.saveDebounceTimer);
      }
      
      this.saveDebounceTimer = setTimeout(() => {
        this.saveProjectConfig();
      }, 500);
    },
    
    handleTrainingOutput(data) {
      const timestamp = new Date().toLocaleTimeString();
      
      if (data.type === 'stdout' || data.type === 'stderr') {
        // 解析训练输出，提取关键信息
        const lines = data.data.split('\n');
        lines.forEach(line => {
          if (line.trim()) {
            this.logs.push({
              time: timestamp,
              message: line,
              type: data.type === 'stderr' ? 'error' : 'info'
            });
            
            // 1. 解析 iteration 标记
            // 格式：=== TRAINING_ITERATION 100 ===
            const iterMatch = line.match(/===\s*TRAINING_ITERATION\s+(\d+)\s*===/);
            if (iterMatch) {
              this.currentIteration = parseInt(iterMatch[1]);
              console.log('[解析] 检测到迭代开始:', this.currentIteration);
              return;
            }
            
            // 2. 解析 Loss 值 - 放宽匹配条件，不要求严格行首行尾
            // 格式：LOSS_VALUE: 0.1234567
            const lossMatch = line.match(/LOSS_VALUE:\s*([0-9.]+)/);
            if (lossMatch && this.currentIteration > 0) {
              const loss = parseFloat(lossMatch[1]);
              console.log(`[解析] Loss=${loss}, iteration=${this.currentIteration}`);
              this.updateChartData(this.currentIteration, loss);
              return;
            }
            
            // 3. 解析 PSNR 值 - 放宽匹配条件，不要求严格行首行尾
            // 格式：PSNR_VALUE: 32.123456
            const psnrMatch = line.match(/PSNR_VALUE:\s*([0-9.]+)/);
            if (psnrMatch && this.currentIteration > 0) {
              const psnr = parseFloat(psnrMatch[1]);
              console.log(`[解析] PSNR=${psnr}, iteration=${this.currentIteration}`);
              this.updatePsnrData(this.currentIteration, psnr);
              return;
            }
            
            // 3.5 解析评估指标 (TEST)
            // 格式：EVAL_TEST_L1: 0.025700
            //      EVAL_TEST_PSNR: 27.366675
            //      EVAL_TEST_SSIM: 0.871772
            const evalTestL1Match = line.match(/EVAL_TEST_L1:\s*([0-9.]+)/);
            const evalTestPsnrMatch = line.match(/EVAL_TEST_PSNR:\s*([0-9.]+)/);
            const evalTestSsimMatch = line.match(/EVAL_TEST_SSIM:\s*([0-9.]+)/);
            if ((evalTestL1Match || evalTestPsnrMatch || evalTestSsimMatch) && this.currentIteration > 0) {
              console.log('[解析] 检测到 TEST 评估指标（每 1000 次迭代）');
              // 这里可以选择是否要显示评估指标，暂时只记录日志
              return;
            }
            
            // 3.6 解析评估指标 (TRAIN)
            // 格式：EVAL_TRAIN_L1: 0.015492
            //      EVAL_TRAIN_PSNR: 31.083937
            //      EVAL_TRAIN_SSIM: 0.922668
            const evalTrainL1Match = line.match(/EVAL_TRAIN_L1:\s*([0-9.]+)/);
            const evalTrainPsnrMatch = line.match(/EVAL_TRAIN_PSNR:\s*([0-9.]+)/);
            const evalTrainSsimMatch = line.match(/EVAL_TRAIN_SSIM:\s*([0-9.]+)/);
            if ((evalTrainL1Match || evalTrainPsnrMatch || evalTrainSsimMatch) && this.currentIteration > 0) {
              console.log('[解析] 检测到 TRAIN 评估指标（每 1000 次迭代）');
              // 这里可以选择是否要显示评估指标，暂时只记录日志
              return;
            }
            
            // 3.7 解析实时训练中的 PSNR 和 SSIM 值（从评估输出中提取）
            // 格式：[ITER 7000] Evaluating test: L1 0.025700 PSNR: 27.366675 SSIM 0.871772
            const evalMatch = line.match(/\[ITER\s+(\d+)\]\s+Evaluating\s+\w+:\s+.*PSNR:\s*([0-9.]+).*SSIM\s+([0-9.]+)/);
            if (evalMatch) {
              const iter = parseInt(evalMatch[1]);
              const psnr = parseFloat(evalMatch[2]);
              const ssim = parseFloat(evalMatch[3]);
              console.log(`[解析] 从评估行解析 PSNR=${psnr}, SSIM=${ssim}, iteration=${iter}`);
              // 同时更新 PSNR 和 SSIM 图表
              this.updatePsnrData(iter, psnr);
              this.updateSsimData(iter, ssim);
              return;
            }
            
            // 4. 解析预览图保存路径 - 放宽匹配条件
            // 格式：PREVIEW_SAVED: /path/to/render_100.png
            const previewMatch = line.match(/PREVIEW_SAVED:\s*(.+)/);
            if (previewMatch) {
              const previewPath = previewMatch[1].trim();
              console.log('[解析] 预览图已保存:', previewPath);
              console.log('[解析] 模型输出目录:', this.modelPath);
              // 立即更新预览图（延迟一点确保文件已写入）
              setTimeout(() => {
                console.log('[定时任务] 检测到 PREVIEW_SAVED，立即更新预览图...');
                this.updatePreviewImage();
              }, 300);
              return;
            }
            
            // 5. 旧的兼容格式（备用）
            // 格式：[ITER 1234]
            const oldIterMatch = line.match(/\[ITER\s+(\d+)\]/);
            if (oldIterMatch) {
              this.currentIteration = parseInt(oldIterMatch[1]);
              console.log('[解析][旧格式] iteration:', this.currentIteration);
            }
          }
        });
        
        // 滚动日志底部
        this.$nextTick(() => {
          if (this.$refs.logContainer) {
            this.$refs.logContainer.scrollTop = this.$refs.logContainer.scrollHeight;
          }
        });
      } else if (data.type === 'eval-update') {
        // 处理评估更新（包含 Eval L1、PSNR、SSIM）
        console.log('[处理评估更新] 收到数据:', data.data);
              
        if (data.data.evalL1 !== undefined && data.data.evalL1 !== null) {
          console.log(`[Eval L1] 更新 - iter: ${data.data.iter}, value: ${data.data.evalL1}, type: ${data.data.evalL1Type}`);
          this.updateEvalL1Data(data.data.iter, data.data.evalL1);
        }
      } else if (data.type === 'close') {
        this.isTraining = false;
        this.addLog(`训练进程结束，退出代码：${data.code}`, 'warning');
      }
    },
    
    handleBakingOutput(data) {
      const timestamp = new Date().toLocaleTimeString();
      
      if (data.type === 'stdout' || data.type === 'stderr') {
        // 解析烘焙输出
        const lines = data.data.split('\n');
        lines.forEach(line => {
          if (line.trim()) {
            this.bakingLogs.push({
              time: timestamp,
              message: line,
              type: data.type === 'stderr' ? 'error' : 'info'
            });
            
            // 尝试解析进度
            const progressMatch = line.match(/(\d+)%/);
            if (progressMatch) {
              this.bakingProgress = parseInt(progressMatch[1]);
            }
          }
        });
        
        // 滚动到底部
        this.$nextTick(() => {
          if (this.$refs.bakingLogContainer) {
            this.$refs.bakingLogContainer.scrollTop = this.$refs.bakingLogContainer.scrollHeight;
          }
        });
      } else if (data.type === 'close') {
        this.isBaking = false;
        this.bakingStatus = data.code === 0 ? 'completed' : 'error';
        this.addBakingLog(`烘焙进程结束，退出代码：${data.code}`, 'warning');
      }
    },
    
    handleConversionOutput(data) {
      if (data.type === 'stdout' || data.type === 'stderr') {
        // 分割多行输出，逐行添加
        const lines = data.data.split('\n');
        lines.forEach(line => {
          if (line.trim()) {
            this.addConversionLog(line, data.type === 'stderr' ? 'error' : 'info');
          }
        });
        this.scrollToConversionLogBottom();
      }
    },
    
    handleConversionClose(data) {
      console.log('转换进程退出，代码:', data.code);
      this.isConverting = false;
      this.isStopping = false;
      
      if (data.code === 0) {
        this.needsConversion = false;
        this.addConversionLog('数据集转换完成', 'success');
        this.addLog('数据集转换成功完成', 'success');
        alert('数据集转换完成，可以开始训练了！');
      } else {
        this.addConversionLog(`转换失败，退出代码：${data.code}`, 'error');
        this.addLog(`数据集转换失败：退出代码 ${data.code}`, 'error');
        alert(`转换失败，退出代码：${data.code}`);
      }
    },
    
    updateChartData(iteration, loss) {
      if (!this.lossChartInstance) {
        console.warn('Loss 图表实例未初始化');
        return;
      }
      
      // 确保 iteration 是数字
      const iterNum = parseInt(iteration) || 0;
      const lossValue = parseFloat(loss);
      
      if (isNaN(lossValue)) {
        console.warn('Loss 值无效:', loss);
        return;
      }
      
      // 静默更新，减少日志输出以提升性能
      try {
        // 添加数据点
        const option = this.lossChartInstance.getOption();
        const xData = option.xAxis && option.xAxis[0] ? (option.xAxis[0].data || []) : [];
        const seriesData = option.series && option.series[0] ? (option.series[0].data || []) : [];
        
        // 避免重复
        const iterStr = iterNum.toString();
        if (!xData.includes(iterStr)) {
          xData.push(iterStr);
          seriesData.push(lossValue);
          
          this.lossChartInstance.setOption({
            xAxis: { data: xData },
            series: [{ data: seriesData }]
          });
        }
      } catch (error) {
        console.error('更新 Loss 图表失败:', error);
      }
    },
    
    updatePsnrData(iteration, psnr) {
      if (!this.psnrChartInstance) {
        console.warn('PSNR 图表实例未初始化');
        return;
      }
      
      // 确保 iteration 是数字
      const iterNum = parseInt(iteration) || 0;
      const psnrValue = parseFloat(psnr);
      
      if (isNaN(psnrValue)) {
        console.warn('PSNR 值无效:', psnr);
        return;
      }
      
      // 静默更新，减少日志输出以提升性能
      try {
        // 添加数据点
        const option = this.psnrChartInstance.getOption();
        const xData = option.xAxis && option.xAxis[0] ? (option.xAxis[0].data || []) : [];
        const seriesData = option.series && option.series[0] ? (option.series[0].data || []) : [];
        
        // 避免重复
        const iterStr = iterNum.toString();
        if (!xData.includes(iterStr)) {
          xData.push(iterStr);
          seriesData.push(psnrValue);
          
          this.psnrChartInstance.setOption({
            xAxis: { data: xData },
            series: [{ data: seriesData }]
          });
        }
      } catch (error) {
        console.error('更新 PSNR 图表失败:', error);
      }
    },
    
    updateSsimData(iteration, ssim) {
      if (!this.ssimChartInstance) {
        console.warn('SSIM 图表实例未初始化');
        return;
      }
      
      // 确保 iteration 是数字
      const iterNum = parseInt(iteration) || 0;
      const ssimValue = parseFloat(ssim);
      
      if (isNaN(ssimValue)) {
        console.warn('SSIM 值无效:', ssim);
        return;
      }
      
      // 静默更新，减少日志输出以提升性能
      try {
        // 添加数据点
        const option = this.ssimChartInstance.getOption();
        const xData = option.xAxis && option.xAxis[0] ? (option.xAxis[0].data || []) : [];
        const seriesData = option.series && option.series[0] ? (option.series[0].data || []) : [];
        
        // 避免重复
        const iterStr = iterNum.toString();
        if (!xData.includes(iterStr)) {
          xData.push(iterStr);
          seriesData.push(ssimValue);
          
          this.ssimChartInstance.setOption({
            xAxis: { data: xData },
            series: [{ data: seriesData }]
          });
        }
      } catch (error) {
        console.error('更新 SSIM 图表失败:', error);
      }
    },
    
    updateEvalL1Data(iteration, evalL1) {
      if (!this.evalL1ChartInstance) {
        console.warn('Eval L1 图表实例未初始化');
        return;
      }
      
      // 确保 iteration 是数字
      const iterNum = parseInt(iteration) || 0;
      const evalL1Value = parseFloat(evalL1);
      
      if (isNaN(evalL1Value)) {
        console.warn('Eval L1 值无效:', evalL1);
        return;
      }
      
      // 静默更新，减少日志输出以提升性能
      try {
        // 添加数据点
        const option = this.evalL1ChartInstance.getOption();
        const xData = option.xAxis && option.xAxis[0] ? (option.xAxis[0].data || []) : [];
        const seriesData = option.series && option.series[0] ? (option.series[0].data || []) : [];
        
        // 避免重复
        const iterStr = iterNum.toString();
        if (!xData.includes(iterStr)) {
          xData.push(iterStr);
          seriesData.push(evalL1Value);
          
          this.evalL1ChartInstance.setOption({
            xAxis: { data: xData },
            series: [{ data: seriesData }]
          });
        }
      } catch (error) {
        console.error('更新 Eval L1 图表失败:', error);
      }
    },
    
    async updatePreviewImage() {
      if (!this.modelPath) {
        console.log('[预览] 模型路径为空，跳过更新');
        return;
      }
      
      console.log('[预览] 开始检查渲染图像，模型路径:', this.modelPath);
      
      try {
        const result = await window.electronAPI?.getLatestRenderedImage(this.modelPath);
        
        if (result && result.success && result.imageBase64) {
          // 直接使用 Base64 数据，不添加时间戳参数（避免解析失败）
          const imageUrl = result.imageBase64;
          
          console.log('[预览] ✓ 找到最新渲染图:', result.imagePath);
          console.log('[预览] Base64 图片大小:', (imageUrl.length / 1024).toFixed(2), 'KB');
          console.log('[预览] Base64 前缀:', imageUrl.substring(0, 50));
          
          // 创建 Image 对象预加载，确保图片可以正常显示
          const img = new Image();
          img.onload = () => {
            console.log('[预览] ✓ 图片预加载成功，准备更新界面');
            console.log('[预览] 当前 iteration:', this.currentIteration);
            
            // 直接赋值，Vue 2 会自动响应式更新
            this.previewImage = imageUrl;
            
            console.log('[预览] ✓ 界面已更新，previewImage 已设置');
          };
          img.onerror = (err) => {
            console.error('[预览] ✗ 图片预加载失败:', err);
            console.error('[预览] Base64 数据:', imageUrl.substring(0, 50) + '...');
            // 即使预加载失败也尝试直接赋值
            this.previewImage = imageUrl;
          };
          img.src = imageUrl;
        } else {
          // 没有找到预览图是正常的，可能训练刚开始
          console.log('[预览] 未找到渲染图像（可能是训练初期）');
          if (result?.error) {
            console.log('[预览] 错误信息:', result.error);
          }
          this.previewImage = null; // 明确设置为 null
        }
      } catch (error) {
        console.error('[预览] 更新失败:', error);
        console.error('[预览] 错误堆栈:', error.stack);
      }
    },
    
    addLog(message, type = 'info') {
      this.logs.push({
        time: new Date().toLocaleTimeString(),
        message,
        type
      });
      
      // 保持日志数量在合理范围内
      if (this.logs.length > 1000) {
        this.logs = this.logs.slice(-500);
      }
      
      this.$nextTick(() => {
        if (this.$refs.logContainer) {
          this.$refs.logContainer.scrollTop = this.$refs.logContainer.scrollHeight;
        }
      });
    },
    
    addBakingLog(message, type = 'info') {
      this.bakingLogs.push({
        time: new Date().toLocaleTimeString(),
        message,
        type
      });
      
      // 保持日志数量在合理范围内
      if (this.bakingLogs.length > 500) {
        this.bakingLogs = this.bakingLogs.slice(-200);
      }
      
      this.$nextTick(() => {
        if (this.$refs.bakingLogContainer) {
          this.$refs.bakingLogContainer.scrollTop = this.$refs.bakingLogContainer.scrollHeight;
        }
      });
    },
    
    async startStage1() {
      if (this.isTraining) {
        alert('训练正在进行中！');
        return;
      }
      
      // 启动前再次验证环境
      try {
        const envCheck = await window.electronAPI?.checkEnvironment();
        if (!envCheck?.success || !envCheck?.valid) {
          const errorMsg = envCheck?.error || 'Python 环境未就绪';
          alert(`环境检查失败：${errorMsg}\n\n请先安装所需依赖后再试。`);
          this.$router.push('/environment');
          return;
        }
      } catch (error) {
        console.error('环境检查异常:', error);
        alert('环境检查失败，请先配置 Python 环境。');
        this.$router.push('/environment');
        return;
      }
      
      try {
        this.isTraining = true;
        this.currentIteration = 0;
        this.lossData = [];
        this.psnrData = [];
        this.logs = [];
        this.bakingStatus = 'idle';
        
        // 如果用户未填写项目名称，生成默认名称
        const finalProjectName = this.projectName.trim() || this.generateDefaultProjectName();
        
        const config = {
          modelPath: this.modelPath,
          sourcePath: this.sourcePath,
          iterations: this.iterations,
          eval: this.evalMode,
          resolution: this.resolution,
          imageSubdir: this.imageSubdir,
          gamma: false,
          indirect: false,
          checkpoint: null,
          projectName: finalProjectName // 新增：项目名称
        };
        
        const result = await window.electronAPI?.startTraining(config);
        
        if (!result?.success) {
          throw new Error(result?.error || '启动训练失败');
        }
        
        this.addLog(`Stage1 训练已启动 - 项目：${finalProjectName}`, 'success');
      } catch (error) {
        console.error('启动 Stage1 失败:', error);
        this.addLog(`启动 Stage1 失败：${error.message}`, 'error');
        this.isTraining = false;
      }
    },
    
    async startBaking() {
      if (this.isBaking) {
        alert('Baking 正在进行中！');
        return;
      }
      
      if (!this.checkpoint) {
        alert('请指定检查点文件！');
        return;
      }
      
      // 启动前验证环境
      try {
        const envCheck = await window.electronAPI?.checkEnvironment();
        if (!envCheck?.success || !envCheck?.valid) {
          const errorMsg = envCheck?.error || 'Python 环境未就绪';
          alert(`环境检查失败：${errorMsg}\n\n请先安装所需依赖后再试。`);
          this.$router.push('/environment');
          return;
        }
      } catch (error) {
        console.error('环境检查异常:', error);
        alert('环境检查失败，请先配置 Python 环境。');
        this.$router.push('/environment');
        return;
      }
      
      try {
        this.isBaking = true;
        this.bakingStatus = 'running';
        this.bakingProgress = 0;
        this.bakingLogs = [];
        
        const config = {
          modelPath: this.modelPath,
          checkpoint: this.checkpoint,
          bound: this.bound,
          occluRes: this.occluRes,
          occlusion: this.occlusion
        };
        
        const result = await window.electronAPI?.startBaking(config);
        
        if (!result?.success) {
          throw new Error(result?.error || '启动烘焙失败');
        }
        
        this.addBakingLog('Baking 已启动', 'success');
      } catch (error) {
        console.error('启动 Baking 失败:', error);
        this.addBakingLog(`启动 Baking 失败：${error.message}`, 'error');
        this.isBaking = false;
        this.bakingStatus = 'error';
      }
    },
    
    async startStage2() {
      if (this.isTraining) {
        alert('训练正在进行中！');
        return;
      }
      
      if (!this.checkpoint) {
        alert('请指定 Stage1 的检查点文件！');
        return;
      }
      
      // 启动前验证环境
      try {
        const envCheck = await window.electronAPI?.checkEnvironment();
        if (!envCheck?.success || !envCheck?.valid) {
          const errorMsg = envCheck?.error || 'Python 环境未就绪';
          alert(`环境检查失败：${errorMsg}\n\n请先安装所需依赖后再试。`);
          this.$router.push('/environment');
          return;
        }
      } catch (error) {
        console.error('环境检查异常:', error);
        alert('环境检查失败，请先配置 Python 环境。');
        this.$router.push('/environment');
        return;
      }
      
      try {
        this.isTraining = true;
        this.currentIteration = 30000; // Stage2 从 30000 开始
        this.logs = [];
        
        // 如果用户未填写项目名称，生成默认名称
        const finalProjectName = this.projectName.trim() || this.generateDefaultProjectName();
        
        const config = {
          modelPath: this.modelPath,
          sourcePath: this.sourcePath,
          iterations: 35000,
          eval: this.evalMode,
          resolution: this.resolution,
          imageSubdir: this.imageSubdir,
          gamma: this.gamma,
          indirect: this.indirect,
          checkpoint: this.checkpoint,
          projectName: finalProjectName // 新增：项目名称
        };
        
        const result = await window.electronAPI?.startTraining(config);
        
        if (!result?.success) {
          throw new Error(result?.error || '启动训练失败');
        }
        
        this.addLog(`Stage2 训练已启动 - 项目：${finalProjectName}`, 'success');
      } catch (error) {
        console.error('启动 Stage2 失败:', error);
        this.addLog(`启动 Stage2 失败：${error.message}`, 'error');
        this.isTraining = false;
      }
    },
    
    showConversionDialog() {
      // 自动显示转换提示，通过 needsConversion 控制
      this.needsConversion = true;
    },
    
    async startConversion() {
      if (this.isConverting) {
        alert('转换正在进行中！');
        return;
      }
      
      try {
        this.isConverting = true;
        this.isStopping = false;
        this.conversionLogs = [];
        this.conversionProgress = 0;
        this.addLog('开始运行 COLMAP 进行数据集转换...', 'info');
        this.addConversionLog('========================================', 'info');
        this.addConversionLog('启动 COLMAP 三维重建流程', 'success');
        this.addConversionLog('========================================', 'info');
        
        // 启动转换
        const result = await window.electronAPI?.convertDataset({
          sourcePath: this.sourcePath,
          resize: this.resolution > 1
        });
        
        // 检查是否是用户主动取消
        if (result?.cancelled) {
          this.addLog('数据集转换已被用户取消', 'warning');
          this.isConverting = false;
          this.isStopping = false;
          return; // 正常退出，不显示错误
        }
        
        if (!result?.success) {
          throw new Error(result?.error || '转换失败');
        }
        
      } catch (error) {
        // 忽略用户取消的情况
        if (error.message.includes('取消') || error.message.includes('cancelled')) {
          console.log('用户取消了转换操作');
          this.isConverting = false;
          this.isStopping = false;
          return;
        }
        
        console.error('数据集转换失败:', error);
        this.addConversionLog(`错误：${error.message}`, 'error');
        this.addLog(`数据集转换失败：${error.message}`, 'error');
        this.isConverting = false;
        this.isStopping = false;
        alert(`转换失败：${error.message}`);
      }
    },
    
    async stopConversion() {
      if (!this.isConverting) return;
      
      try {
        this.isStopping = true;
        this.addConversionLog('正在停止转换进程...', 'warning');
        
        // 通知后端停止转换进程
        const result = await window.electronAPI?.stopConversion();
        
        if (result?.success) {
          this.addConversionLog('转换进程已停止', 'warning');
          this.isConverting = false;
          this.isStopping = false;
          this.needsConversion = true; // 保持提示，允许重新尝试
        } else {
          throw new Error('停止转换失败');
        }
      } catch (error) {
        console.error('停止转换失败:', error);
        this.addConversionLog(`停止失败：${error.message}`, 'error');
        this.isStopping = false;
      }
    },
    
    addConversionLog(message, type = 'info') {
      const now = new Date();
      const time = `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}:${now.getSeconds().toString().padStart(2, '0')}`;
      this.conversionLogs.push({ time, message, type });
      
      // 限制日志数量
      if (this.conversionLogs.length > 100) {
        this.conversionLogs.shift();
      }
    },
    
    scrollToConversionLogBottom() {
      this.$nextTick(() => {
        if (this.$refs.conversionLogContainer) {
          this.$refs.conversionLogContainer.scrollTop = this.$refs.conversionLogContainer.scrollHeight;
        }
      });
    },
    
    async stopTraining() {
      console.log('[停止操作] 开始执行停止流程');
      
      try {
        // 停止训练进程
        if (this.isTraining) {
          console.log('[停止操作] 正在停止训练进程...');
          try {
            const result = await window.electronAPI?.stopTraining();
            console.log('[停止操作] 训练进程停止结果:', result);
            
            if (result?.success) {
              this.addLog('训练进程已成功停止', 'warning');
            } else {
              console.warn('[停止操作] 训练进程停止失败:', result?.error);
              this.addLog(`训练进程停止失败：${result?.error || '未知错误'}`, 'error');
            }
          } catch (ipcError) {
            console.error('[停止操作] 停止训练进程 IPC 调用失败:', ipcError);
            this.addLog(`停止训练进程通信失败：${ipcError.message}`, 'error');
          }
          
          // 无论是否成功，都更新本地状态
          this.isTraining = false;
          this.addLog('训练状态已更新为已停止', 'warning');
        }
        
        // 停止烘焙进程
        if (this.isBaking) {
          console.log('[停止操作] 正在停止烘焙进程...');
          try {
            const result = await window.electronAPI?.stopBaking();
            console.log('[停止操作] 烘焙进程停止结果:', result);
            
            if (result?.success) {
              this.addBakingLog('烘焙进程已成功停止', 'warning');
            } else {
              console.warn('[停止操作] 烘焙进程停止失败:', result?.error);
              this.addBakingLog(`烘焙进程停止失败：${result?.error || '未知错误'}`, 'error');
            }
          } catch (ipcError) {
            console.error('[停止操作] 停止烘焙进程 IPC 调用失败:', ipcError);
            this.addBakingLog(`停止烘焙进程通信失败：${ipcError.message}`, 'error');
          }
          
          // 无论是否成功，都更新本地状态
          this.isBaking = false;
          this.bakingStatus = 'error';
          this.addBakingLog('烘焙状态已更新为已停止', 'warning');
        }
        
        // 强制更新 UI
        this.$forceUpdate();
        console.log('[停止操作] 停止流程完成');
        
      } catch (error) {
        console.error('[停止操作] 发生异常:', error);
        // 即使出错也强制更新状态
        this.isTraining = false;
        this.isBaking = false;
        this.bakingStatus = 'error';
        this.addLog(`停止操作完成（可能未完全停止）`, 'warning');
        this.$forceUpdate();
      }
    },
    
    selectFolder: async function(model) {
      console.log('开始选择文件夹，类型:', model);
      
      // 检查 electronAPI 是否存在
      if (!window.electronAPI) {
        console.error('electronAPI 未定义');
        alert('系统接口异常，请重启应用');
        return;
      }
      
      // 检查 selectDirectory 方法是否存在
      if (typeof window.electronAPI.selectDirectory !== 'function') {
        console.error('selectDirectory 方法不存在');
        alert('文件夹选择功能不可用');
        return;
      }
      
      try {
        console.log('调用 selectDirectory...');
        const result = await window.electronAPI.selectDirectory();
        console.log('选择结果:', result);
        
        if (result && !result.canceled && result.filePaths && result.filePaths.length > 0) {
          const selectedPath = result.filePaths[0];
          console.log('选中的路径:', selectedPath);
          
          if (model === 'modelPath') {
            this.modelPath = selectedPath;
            // 自动更新检查点路径为输出目录下的 chkpnt30000.pth
            const checkpointName = selectedPath.endsWith('/') || selectedPath.endsWith('\\') 
              ? 'chkpnt30000.pth' 
              : (selectedPath.includes('\\') ? '\\chkpnt30000.pth' : '/chkpnt30000.pth');
            this.checkpoint = selectedPath + checkpointName;
            this.addLog(`输出路径已设置，检查点路径自动更新为：${this.checkpoint}`, 'info');
            // 触发自动保存
            this.triggerAutoSave();
          } else if (model === 'sourcePath') {
            this.sourcePath = selectedPath;
            // 自动检查数据集格式
            await this.checkDatasetFormat(selectedPath);
            // 触发自动保存
            this.triggerAutoSave();
          } else if (model === 'checkpoint') {
            this.checkpoint = selectedPath;
            // 触发自动保存
            this.triggerAutoSave();
          }
        } else if (result && result.canceled) {
          console.log('用户取消了选择');
        } else {
          console.warn('无效的选择结果');
        }
      } catch (error) {
        console.error('选择文件夹异常:', error);
        alert(`无法打开文件夹选择对话框：${error.message}`);
      }
    },
    
    selectFile: async function(model) {
      console.log('开始选择文件，类型:', model);
      
      // 检查 electronAPI 是否存在
      if (!window.electronAPI) {
        console.error('electronAPI 未定义');
        alert('系统接口异常，请重启应用');
        return;
      }
      
      // 检查 selectFile 方法是否存在
      if (typeof window.electronAPI.selectFile !== 'function') {
        console.error('selectFile 方法不存在');
        alert('文件选择功能不可用');
        return;
      }
      
      try {
        console.log('调用 selectFile...');
        const result = await window.electronAPI.selectFile({
          filters: [
            { name: 'Python Checkpoint', extensions: ['pth'] },
            { name: 'All Files', extensions: ['*'] }
          ]
        });
        console.log('文件选择结果:', result);
        
        if (result && !result.canceled && result.filePaths && result.filePaths.length > 0) {
          this.checkpoint = result.filePaths[0];
          console.log('选中的文件:', this.checkpoint);
          // 选择文件后触发自动保存
          this.triggerAutoSave();
        } else if (result && result.canceled) {
          console.log('用户取消了选择');
        } else {
          console.warn('无效的选择结果');
        }
      } catch (error) {
        console.error('选择文件异常:', error);
        alert(`无法打开文件选择对话框：${error.message}`);
      }
    },
    
    async checkDatasetFormat(sourcePath) {
      try {
        this.addLog('正在检查数据集格式...', 'info');
        const result = await window.electronAPI?.checkDatasetFormat(sourcePath);
        
        if (result && result.success) {
          this.datasetFormat = result.format;
          this.needsConversion = result.needsConversion;
          
          if (result.format === 'tensoir') {
            this.addLog('✓ 检测到 TensoIR-Synthetic 数据集格式', 'success');
          } else if (result.format === 'mipnerf360') {
            this.addLog('✓ 检测到 Mip-NeRF 360 数据集格式', 'success');
            // 自动设置图片子目录
            if (result.isOutdoor) {
              this.addLog('检测到室外场景，将使用 images_4 目录', 'info');
            } else {
              this.addLog('检测到室内场景，将使用 images_2 目录', 'info');
            }
          } else if (result.format === 'custom' && result.needsConversion) {
            this.addLog('⚠ 数据集格式不符合规范，需要进行转换', 'warning');
            this.showConversionDialog();
          } else {
            this.addLog('✓ 数据集格式检查通过', 'success');
          }
        } else {
          this.addLog(`数据集检查失败：${result?.error || '未知错误'}`, 'error');
        }
      } catch (error) {
        console.error('数据集检查失败:', error);
        this.addLog(`数据集检查异常：${error.message}`, 'error');
      }
    },
  }
}
</script>

<style scoped>
.train-container {
  height: 100%;
  background-color: #f8fafc;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.train-content {
  flex: 1;
  display: flex;
  overflow: hidden;
}

.params-panel {
  width: 22rem;
  background: white;
  border-right: 1px solid #e2e8f0;
  padding: 1.5rem;
  overflow-y: auto;
}

.panel-title {
  font-size: 1.125rem;
  font-weight: bold;
  color: #1e293b;
  margin-bottom: 1.5rem;
}

.params-form {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.form-label {
  font-size: 0.875rem;
  font-weight: 500;
  color: #334155;
}

.input-group {
  display: flex;
  gap: 0.5rem;
}

.path-input {
  flex: 1;
  background-color: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 0.5rem;
  padding: 0.5rem 0.75rem;
  font-size: 0.75rem;
}

.browse-btn {
  background-color: #f1f5f9;
  padding: 0.5rem;
  border-radius: 0.5rem;
  color: #475569;
  border: none;
  cursor: pointer;
  transition: all 0.2s;
}

.browse-btn:hover {
  background-color: #e2e8f0;
}

.number-input,
.text-input {
  width: 100%;
  background-color: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 0.5rem;
  padding: 0.5rem 0.75rem;
  font-size: 0.875rem;
}

.form-section {
  margin-top: 0.5rem;
  padding-top: 1rem;
  border-top: 1px solid #f1f5f9;
}

.section-title {
  font-size: 0.875rem;
  font-weight: 600;
  color: #475569;
  margin-bottom: 0.75rem;
}

.checkbox-group {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.875rem;
  color: #475569;
  cursor: pointer;
}

.checkbox-label input[type="checkbox"] {
  width: 1rem;
  height: 1rem;
  cursor: pointer;
}

.actions-section {
  padding-top: 1.5rem;
  border-top: 1px solid #e2e8f0;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.start-btn,
.baking-btn {
  width: 100%;
  color: white;
  padding: 0.75rem;
  border-radius: 0.75rem;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  border: none;
  cursor: pointer;
  transition: all 0.2s;
  font-size: 0.938rem;
}

.start-btn:disabled,
.baking-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.start-btn {
  background-color: #7e22ce;
}

.start-btn:hover:not(:disabled) {
  background-color: #6b21a8;
}

.baking-btn {
  background-color: #ea580c;
}

.baking-btn:hover:not(:disabled) {
  background-color: #c2410c;
}

.stage2-btn {
  background-color: #059669;
}

.stage2-btn:hover:not(:disabled) {
  background-color: #047857;
}

.control-buttons {
  display: flex;
  gap: 0.5rem;
}

.stop-btn {
  padding: 0.625rem;
  border-radius: 0.5rem;
  font-size: 0.875rem;
  font-weight: 500;
  border: none;
  cursor: pointer;
  transition: all 0.2s;
  background-color: #fee2e2;
  color: #991b1b;
}

.stop-btn:hover:not(:disabled) {
  background-color: #fecaca;
}

.monitoring-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 1.5rem;
  overflow-y: auto;
  gap: 1.5rem;
}

.tabs-header {
  display: flex;
  gap: 0.5rem;
  border-bottom: 2px solid #e2e8f0;
  padding-bottom: 0.5rem;
}

.tab-button {
  padding: 0.5rem 1.5rem;
  background: transparent;
  border: none;
  border-radius: 0.5rem 0.5rem 0 0;
  font-size: 0.938rem;
  font-weight: 500;
  color: #64748b;
  cursor: pointer;
  transition: all 0.2s;
}

.tab-button:hover {
  background-color: #f1f5f9;
  color: #1e293b;
}

.tab-button.active {
  background-color: #7e22ce;
  color: white;
}

.tab-content {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.charts-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);  /* 默认 2 列，会被 JS 动态覆盖 */
  grid-template-rows: auto;
  gap: 1.5rem;
  width: 100%;
  min-width: 0;  /* 允许收缩到更小尺寸 */
  transition: grid-template-columns 0.3s ease;  /* 平滑过渡 */
}

/* 确保图表卡片在网格中正确填充 */
.charts-grid .chart-card {
  min-width: 0;  /* 防止内容溢出 */
  min-height: 300px;  /* 最小高度确保图表可见 */
}

.chart-card {
  background: white;
  padding: 1rem;
  border-radius: 1rem;
  border: 1px solid #e2e8f0;
  box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
  width: 100%;
  height: 100%;
  min-height: 300px;  /* 最小高度确保图表可见 */
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
}

.chart-title,
.preview-title,
.log-title {
  font-size: 0.875rem;
  font-weight: bold;
  color: #1e293b;
  margin-bottom: 1rem;
}

.chart-container {
  height: calc(100% - 40px);  /* 减去标题和边距的高度 */
  min-height: 240px;  /* 确保最小高度 */
  width: 100%;
  flex: 1;  /* 占据剩余空间 */
  position: relative;  /* 确保 ECharts 正确定位 */
}

.preview-card {
  background: white;
  border-radius: 1rem;
  border: 1px solid #e2e8f0;
  box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
  padding: 1.5rem;
}

.preview-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}

.refresh-preview-btn {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 1rem;
  background-color: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 0.5rem;
  color: #64748b;
  font-size: 0.875rem;
  cursor: pointer;
  transition: all 0.2s;
}

.refresh-preview-btn:hover:not(:disabled) {
  background-color: #f1f5f9;
  color: #1e293b;
}

.refresh-preview-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.refresh-preview-btn .iconify {
  font-size: 1rem;
}

.refresh-preview-btn .iconify.spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.preview-title {
  font-size: 1.125rem;
  font-weight: bold;
  color: #1e293b;
  margin: 0;
}

.preview-container {
  height: 20rem;
  background-color: #0f172a;
  border-radius: 0.75rem;
  position: relative;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
  min-width: 0; /* 防止 flex 子项溢出 */
}

.preview-image {
  width: 100%;
  height: 100%;
  object-fit: contain;
  display: block; /* 确保图片是块级元素 */
  max-width: 100%; /* 确保不超过容器 */
  max-height: 100%; /* 确保不超过容器 */
}

.preview-placeholder {
  color: #64748b;
  font-size: 0.875rem;
  text-align: center;
  padding: 1rem;
}

.iteration-overlay {
  position: absolute;
  top: 1rem;
  left: 1rem;
  background-color: rgba(0, 0, 0, 0.7);
  backdrop-filter: blur(4px);
  color: white;
  font-size: 0.75rem;
  padding: 0.375rem 0.75rem;
  border-radius: 0.5rem;
  font-weight: 500;
}

.log-card {
  background: white;
  border-radius: 1rem;
  border: 1px solid #e2e8f0;
  box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
  padding: 1rem;
  display: flex;
  flex-direction: column;
  min-height: 12rem;
}

.log-container {
  flex: 1;
  max-height: 20rem;
  overflow-y: auto;
  background-color: #f8fafc;
  border-radius: 0.5rem;
  padding: 0.75rem;
  font-family: 'Courier New', monospace;
  font-size: 0.75rem;
  line-height: 1.5;
}

.log-line {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 0.25rem;
  padding: 0.25rem;
  border-radius: 0.25rem;
}

.log-line.info {
  background-color: transparent;
  color: #334155;
}

.log-line.error {
  background-color: #fee2e2;
  color: #991b1b;
}

.log-line.success {
  background-color: #dcfce7;
  color: #166534;
}

.log-line.warning {
  background-color: #fef3c7;
  color: #92400e;
}

.log-time {
  color: #94a3b8;
  font-size: 0.625rem;
  white-space: nowrap;
}

.log-message {
  flex: 1;
  word-break: break-all;
}

.baking-status {
  background: white;
  padding: 1rem;
  border-radius: 1rem;
  border: 1px solid #e2e8f0;
  box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.status-item {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.status-label {
  font-size: 0.875rem;
  font-weight: 500;
  color: #64748b;
  min-width: 4rem;
}

.status-value {
  font-size: 0.875rem;
  font-weight: 600;
  padding: 0.25rem 0.75rem;
  border-radius: 0.5rem;
}

.status-value.idle {
  background-color: #f1f5f9;
  color: #475569;
}

.status-value.running {
  background-color: #dbeafe;
  color: #1e40af;
}

.status-value.completed {
  background-color: #dcfce7;
  color: #166534;
}

.status-value.error {
  background-color: #fee2e2;
  color: #991b1b;
}

.progress-bar {
  flex: 1;
  height: 0.5rem;
  background-color: #e2e8f0;
  border-radius: 9999px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #7e22ce, #a855f7);
  transition: width 0.3s ease;
}

.progress-text {
  font-size: 0.875rem;
  font-weight: 600;
  color: #1e293b;
  min-width: 3rem;
  text-align: right;
}

.conversion-alert {
  margin-top: 1rem;
  padding: 1rem;
  background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%);
  border-radius: 0.75rem;
  border: 1px solid #fbbf24;
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.alert-icon {
  flex-shrink: 0;
  width: 2rem;
  height: 2rem;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: #fbbf24;
  border-radius: 50%;
  color: white;
}

.alert-content {
  flex: 1;
}

.alert-title {
  font-size: 0.875rem;
  font-weight: 600;
  color: #92400e;
  margin-bottom: 0.25rem;
}

.alert-text {
  font-size: 0.75rem;
  color: #78350f;
  line-height: 1.4;
}

.convert-btn {
  flex-shrink: 0;
  padding: 0.5rem 1rem;
  background-color: #f59e0b;
  color: white;
  border: none;
  border-radius: 0.5rem;
  font-size: 0.875rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  gap: 0.375rem;
}

.convert-btn:hover:not(:disabled) {
  background-color: #d97706;
}

.select-input {
  width: 100%;
  background-color: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 0.5rem;
  padding: 0.5rem 0.75rem;
  font-size: 0.875rem;
  cursor: pointer;
}

.help-text {
  display: flex;
  align-items: center;
  gap: 0.375rem;
  margin-top: 0.375rem;
  font-size: 0.75rem;
  color: #64748b;
}

/* 数据集转换等待动画弹窗 */
.conversion-modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
  backdrop-filter: blur(4px);
}

.conversion-modal {
  background: white;
  border-radius: 1rem;
  box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04);
  width: 90%;
  max-width: 800px;
  max-height: 80vh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  animation: modalSlideIn 0.3s ease-out;
}

@keyframes modalSlideIn {
  from {
    opacity: 0;
    transform: translateY(-20px) scale(0.95);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

.modal-header {
  padding: 1.5rem;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  display: flex;
  align-items: center;
  gap: 1rem;
}

.modal-title {
  font-size: 1.25rem;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin: 0;
}

.modal-body {
  padding: 2rem;
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
  overflow-y: auto;
}

/* 加载动画 */
.loading-animation {
  position: relative;
  width: 80px;
  height: 80px;
  margin: 0 auto;
}

.spinner-ring {
  position: absolute;
  width: 100%;
  height: 100%;
  border: 3px solid transparent;
  border-top-color: #667eea;
  border-radius: 50%;
  animation: spin 1.2s cubic-bezier(0.5, 0, 0.5, 1) infinite;
}

.spinner-ring:nth-child(1) {
  animation-delay: -0.45s;
  border-top-color: #667eea;
}

.spinner-ring:nth-child(2) {
  width: 70%;
  height: 70%;
  top: 15%;
  left: 15%;
  animation-delay: -0.3s;
  border-top-color: #764ba2;
}

.spinner-ring:nth-child(3) {
  width: 40%;
  height: 40%;
  top: 30%;
  left: 30%;
  animation-delay: -0.15s;
  border-top-color: #f59e0b;
}

@keyframes spin {
  0% {
    transform: rotate(0deg);
  }
  100% {
    transform: rotate(360deg);
  }
}

/* 进度提示 */
.progress-info {
  text-align: center;
}

.loading-text {
  font-size: 1.125rem;
  font-weight: 600;
  color: #1e293b;
  margin-bottom: 0.5rem;
}

.loading-subtext {
  font-size: 0.875rem;
  color: #64748b;
  margin: 0;
}

/* 转换日志 */
.conversion-log-container {
  background: #f8fafc;
  border-radius: 0.75rem;
  border: 1px solid #e2e8f0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  max-height: 300px;
}

.log-header {
  padding: 0.75rem 1rem;
  background: #f1f5f9;
  border-bottom: 1px solid #e2e8f0;
  font-size: 0.875rem;
  font-weight: 600;
  color: #475569;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.log-output {
  flex: 1;
  max-height: 250px;
  overflow-y: auto;
  padding: 1rem;
  font-family: 'Courier New', monospace;
  font-size: 0.75rem;
  line-height: 1.6;
}

.log-output .log-line {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 0.375rem;
  padding: 0.375rem;
  border-radius: 0.25rem;
}

.log-output .log-line.info {
  background-color: transparent;
  color: #334155;
}

.log-output .log-line.error {
  background-color: #fee2e2;
  color: #991b1b;
}

.log-output .log-line.success {
  background-color: #dcfce7;
  color: #166534;
}

.log-output .log-line.warning {
  background-color: #fef3c7;
  color: #92400e;
}

.log-output .log-time {
  color: #94a3b8;
  font-size: 0.625rem;
  white-space: nowrap;
}

.log-output .log-message {
  flex: 1;
  word-break: break-all;
}

.modal-footer {
  padding: 1rem 1.5rem;
  background: #f8fafc;
  border-top: 1px solid #e2e8f0;
  display: flex;
  justify-content: flex-end;
}

.cancel-btn {
  padding: 0.625rem 1.25rem;
  background-color: #ef4444;
  color: white;
  border: none;
  border-radius: 0.5rem;
  font-size: 0.875rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.cancel-btn:hover:not(:disabled) {
  background-color: #dc2626;
}

.cancel-btn:disabled {
  background-color: #fca5a5;
  cursor: not-allowed;
  opacity: 0.7;
}

/* 旋转图标动画 */
.spin-icon {
  animation: spinIcon 2s linear infinite;
}

@keyframes spinIcon {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}
</style>
