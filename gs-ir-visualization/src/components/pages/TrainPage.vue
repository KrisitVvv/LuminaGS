<template>
  <section class="train-container">
    <div class="train-content">
      <!-- 左侧参数设置 -->
      <div class="params-panel">
        <h3 class="panel-title">训练参数</h3>
        <div class="params-form">
          <div class="form-group">
            <label class="form-label">输出路径 (-m)</label>
            <div class="input-group">
              <input class="path-input" v-model="modelPath" placeholder="outputs/lego/">
              <button class="browse-btn" @click="selectFolder('modelPath')"><span class="iconify" data-icon="solar:folder-linear"></span></button>
            </div>
          </div>
          
          <div class="form-group">
            <label class="form-label">数据集路径 (-s)</label>
            <div class="input-group">
              <input class="path-input" v-model="sourcePath" placeholder="datasets/TensoIR/lego/">
              <button class="browse-btn" @click="selectFolder('sourcePath')"><span class="iconify" data-icon="solar:folder-linear"></span></button>
            </div>
          </div>
          
          <div class="form-group">
            <label class="form-label">训练轮次 (Iterations)</label>
            <input class="number-input" type="number" v-model.number="iterations">
          </div>
          
          <div class="form-group">
            <label class="form-label">Baking 检查点</label>
            <div class="input-group">
              <input class="path-input" v-model="checkpoint" placeholder="outputs/lego/chkpnt30000.pth">
              <button class="browse-btn" @click="selectFile('checkpoint')"><span class="iconify" data-icon="solar:file-linear"></span></button>
            </div>
          </div>
          
          <div class="form-section">
            <h4 class="section-title">Stage1 参数</h4>
            <div class="checkbox-group">
              <label class="checkbox-label">
                <input type="checkbox" v-model="evalMode">
                <span>评估模式 (--eval)</span>
              </label>
            </div>
            <div class="form-group" style="margin-top: 0.75rem;">
              <label class="form-label">分辨率压缩 (-r)</label>
              <select class="select-input" v-model.number="resolution">
                <option :value="1">原始分辨率 (1/1)</option>
                <option :value="2">1/2 分辨率</option>
                <option :value="4">1/4 分辨率</option>
                <option :value="8">1/8 分辨率</option>
              </select>
            </div>
          </div>
          
          <div class="form-section">
            <h4 class="section-title">Baking 参数</h4>
            <div class="form-group">
              <label class="form-label">Bound</label>
              <input class="number-input" type="number" step="0.1" v-model.number="bound">
            </div>
            <div class="form-group">
              <label class="form-label">Occlusion Resolution</label>
              <input class="number-input" type="number" v-model.number="occluRes">
            </div>
            <div class="form-group">
              <label class="form-label">Occlusion Threshold</label>
              <input class="number-input" type="number" step="0.01" v-model.number="occlusion">
            </div>
          </div>
          
          <div class="form-section">
            <h4 class="section-title">Stage2 参数</h4>
            <div class="checkbox-group">
              <label class="checkbox-label">
                <input type="checkbox" v-model="gamma">
                <span>Gamma 校正 (--gamma)</span>
              </label>
              <label class="checkbox-label">
                <input type="checkbox" v-model="indirect">
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
              <button class="pause-btn" @click="pauseTraining" :disabled="!isTraining">暂停</button>
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
              <button class="convert-btn" @click="startConversion">
                <span class="iconify" data-icon="solar:refresh-linear"></span> 开始转换
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
          </div>
          
          <div class="preview-card">
            <h4 class="preview-title">动态迭代预览</h4>
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
  </section>
</template>

<script>
import * as echarts from 'echarts';

export default {
  name: 'TrainPage',
  data() {
    return {
      // 训练参数
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
      
      // 图表数据
      lossData: [],
      psnrData: [],
      
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
            
      // 数据集格式
      datasetFormat: 'unknown', // unknown, tensoir, mipnerf360, custom
      needsConversion: false,
      conversionProgress: 0,
      isConverting: false,
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
  mounted() {
    this.initCharts();
    this.setupIPCListeners();
    window.addEventListener('resize', this.handleResize);
  },
  beforeUnmount() {
    if (this.lossChartInstance) {
      this.lossChartInstance.dispose();
    }
    if (this.psnrChartInstance) {
      this.psnrChartInstance.dispose();
    }
    window.removeEventListener('resize', this.handleResize);
  },
  methods: {
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
            name: 'Iteration',
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
            name: 'Iteration',
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
            
            // 尝试解析 iteration 和 loss
            const lossMatch = line.match(/Loss:\s*([0-9.]+)/);
            if (lossMatch) {
              const loss = parseFloat(lossMatch[1]);
              this.updateChartData(this.currentIteration, loss);
            }
            
            // 尝试解析 PSNR
            const psnrMatch = line.match(/PSNR\s*([0-9.]+)/);
            if (psnrMatch) {
              const psnr = parseFloat(psnrMatch[1]);
              this.updatePsnrData(this.currentIteration, psnr);
            }
            
            // 尝试解析 iteration
            const iterMatch = line.match(/\[ITER\s*(\d+)\]/);
            if (iterMatch) {
              this.currentIteration = parseInt(iterMatch[1]);
            }
          }
        });
        
        // 滚动到底部
        this.$nextTick(() => {
          if (this.$refs.logContainer) {
            this.$refs.logContainer.scrollTop = this.$refs.logContainer.scrollHeight;
          }
        });
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
    
    updateChartData(iteration, loss) {
      if (!this.lossChartInstance) return;
      
      // 添加数据点
      const option = this.lossChartInstance.getOption();
      const xData = option.xAxis[0].data || [];
      const seriesData = option.series[0].data || [];
      
      // 避免重复
      if (!xData.includes(iteration.toString())) {
        xData.push(iteration.toString());
        seriesData.push(loss);
        
        this.lossChartInstance.setOption({
          xAxis: { data: xData },
          series: [{ data: seriesData }]
        });
      }
    },
    
    updatePsnrData(iteration, psnr) {
      if (!this.psnrChartInstance) return;
      
      // 添加数据点
      const option = this.psnrChartInstance.getOption();
      const xData = option.xAxis[0].data || [];
      const seriesData = option.series[0].data || [];
      
      // 避免重复
      if (!xData.includes(iteration.toString())) {
        xData.push(iteration.toString());
        seriesData.push(psnr);
        
        this.psnrChartInstance.setOption({
          xAxis: { data: xData },
          series: [{ data: seriesData }]
        });
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
        
        const config = {
          modelPath: this.modelPath,
          sourcePath: this.sourcePath,
          iterations: this.iterations,
          eval: this.evalMode,
          resolution: this.resolution,
          gamma: false,
          indirect: false,
          checkpoint: null
        };
        
        const result = await window.electronAPI?.startTraining(config);
        
        if (!result?.success) {
          throw new Error(result?.error || '启动训练失败');
        }
        
        this.addLog('Stage1 训练已启动', 'success');
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
        
        const config = {
          modelPath: this.modelPath,
          sourcePath: this.sourcePath,
          iterations: 35000,
          eval: this.evalMode,
          gamma: this.gamma,
          indirect: this.indirect,
          checkpoint: this.checkpoint
        };
        
        const result = await window.electronAPI?.startTraining(config);
        
        if (!result?.success) {
          throw new Error(result?.error || '启动训练失败');
        }
        
        this.addLog('Stage2 训练已启动', 'success');
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
        this.conversionProgress = 0;
        this.addLog('开始转换数据集...', 'info');
        
        const result = await window.electronAPI?.convertDataset({
          sourcePath: this.sourcePath,
          resize: this.resolution > 1
        });
        
        if (!result?.success) {
          throw new Error(result?.error || '转换失败');
        }
        
        this.needsConversion = false;
        this.addLog('✓ 数据集转换完成', 'success');
        alert('数据集转换完成，可以开始训练了！');
      } catch (error) {
        console.error('数据集转换失败:', error);
        this.addLog(`数据集转换失败：${error.message}`, 'error');
        alert(`转换失败：${error.message}`);
      } finally {
        this.isConverting = false;
      }
    },
    
    async pauseTraining() {
      // TODO: 实现暂停功能（需要修改 Python 脚本支持暂停）
      this.addLog('暂停功能暂未实现', 'warning');
    },
    
    async stopTraining() {
      try {
        if (this.isTraining) {
          await window.electronAPI?.stopTraining();
          this.isTraining = false;
          this.addLog('训练已停止', 'warning');
        }
        
        if (this.isBaking) {
          await window.electronAPI?.stopBaking();
          this.isBaking = false;
          this.bakingStatus = 'error';
          this.addBakingLog('烘焙已停止', 'warning');
        }
      } catch (error) {
        console.error('停止训练失败:', error);
        this.addLog(`停止训练失败：${error.message}`, 'error');
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
          } else if (model === 'sourcePath') {
            this.sourcePath = selectedPath;
            // 自动检查数据集格式
            await this.checkDatasetFormat(selectedPath);
          } else if (model === 'checkpoint') {
            this.checkpoint = selectedPath;
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
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.5rem;
}

.pause-btn,
.stop-btn {
  padding: 0.625rem;
  border-radius: 0.5rem;
  font-size: 0.875rem;
  font-weight: 500;
  border: none;
  cursor: pointer;
  transition: all 0.2s;
}

.pause-btn {
  background-color: #fef3c7;
  color: #92400e;
}

.pause-btn:hover:not(:disabled) {
  background-color: #fde68a;
}

.stop-btn {
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
  grid-template-columns: 1fr 1fr;
  gap: 1.5rem;
}

.chart-card {
  background: white;
  padding: 1rem;
  border-radius: 1rem;
  border: 1px solid #e2e8f0;
  box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
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
  height: 16rem;
  width: 100%;
}

.preview-card {
  background: white;
  border-radius: 1rem;
  border: 1px solid #e2e8f0;
  box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
  padding: 1rem;
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
}

.preview-image {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.preview-placeholder {
  color: #64748b;
  font-size: 0.875rem;
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
</style>
