<template>
  <section class="progress-container">
    <div class="progress-content">
      <div class="dashboard-section">
        <div class="dashboard-grid">
          <div class="gpu-monitor-card">
            <div class="card-header">
              <h3 class="card-title">GPU监控</h3>
              <div class="gpu-stats">
                <div class="stat-item">
                  <span class="stat-label">使用率:</span>
                  <span class="stat-value">{{ currentGpuData.utilization }}%</span>
                </div>
                <div class="stat-item">
                  <span class="stat-label">显存:</span>
                  <span class="stat-value">{{ Math.round((currentGpuData.memoryUsed / currentGpuData.memoryTotal) * 100) }}%</span>
                </div>
                <div class="stat-item">
                  <span class="stat-label">温度:</span>
                  <span class="stat-value">{{ currentGpuData.temperature }}°C</span>
                </div>
              </div>
            </div>
            <div v-if="refreshStatus === '错误'" class="error-display">
              <div class="error-icon">⚠️</div>
              <div class="error-message">GPU监控数据获取失败</div>
              <div class="error-detail">{{ gpuModel }}</div>
              <div class="error-hint">请检查硬件连接或重启应用程序</div>
            </div>
            <div v-show="refreshStatus !== '错误'" id="gpu-chart" class="chart-container"></div>
            <div class="gpu-info">
              <div class="gpu-selector-container">
                <div 
                  class="gpu-model-display" 
                  @click="toggleGpuList"
                  :class="{ 'active': showGpuList }"
                >
                  <span class="gpu-model-text">{{ gpuModel }}</span>
                  <span class="dropdown-arrow" :class="{ 'rotated': showGpuList }">▼</span>
                </div>
                <div v-show="showGpuList" class="gpu-dropdown-list">
                  <div 
                    v-for="(gpu, index) in availableGpus" 
                    :key="index"
                    class="gpu-dropdown-item"
                    :class="{ 'selected': selectedGpuIndex === index }"
                    @click="selectGpuFromList(index)"
                  >
                    <div class="gpu-item-content">
                      <div class="gpu-item-details">
                        <div class="gpu-item-name">{{ gpu.vendor }} {{ gpu.model }}</div>
                      </div>
                    </div>
                  </div>
                  <div v-if="availableGpus.length === 0" class="no-gpus-item">
                    <div class="no-gpus-text">未检测到可用GPU设备</div>
                  </div>
                </div>
              </div>
            </div>
          </div>
          <div class="queue-card">
            <h3 class="card-title">渲染队列</h3>
            <div class="queue-list">
              <!-- 动态项目列表 -->
              <div 
                v-for="(project, index) in projectQueue" 
                :key="project.projectId"
                class="queue-item"
                :class="{ active: project.status === 'training', [getStatusClass(project.status)]: true }"
                @click="resumeProject(project)"
              >
                <div class="progress-bar-indicator" v-if="project.status === 'training'"></div>
                <div class="indicator-placeholder" v-else></div>
                <div class="item-content">
                  <div class="item-header">
                    <span class="task-name">{{ project.name }}</span>
                    <span :class="['status-badge', getStatusClass(project.status)]">
                      {{ getStatusText(project.status) }}
                    </span>
                  </div>
                  <div class="item-details">
                    <span class="detail-text">阶段：{{ project.stage === 'stage1' ? 'Stage1' : project.stage === 'baking' ? 'Baking' : 'Stage2' }}</span>
                    <span class="detail-separator">|</span>
                    <span class="detail-text">迭代：{{ project.currentIteration || 0 }}</span>
                    <span class="detail-separator" v-if="project.lastModified">|</span>
                    <span class="detail-time" v-if="project.lastModified">更新：{{ formatLastModified(project.lastModified) }}</span>
                  </div>
                  <div class="progress-track" v-if="project.status === 'training'">
                    <div class="progress-fill" :style="{ width: getProgressPercent(project) + '%' }"></div>
                  </div>
                  <div class="progress-track empty" v-else></div>
                </div>
              </div>
              
              <!-- 空队列提示 -->
              <div v-if="projectQueue.length === 0" class="no-projects">
                <div class="no-projects-icon">📋</div>
                <div class="no-projects-text">暂无训练项目</div>
                <div class="no-projects-hint">前往训练页面创建新项目</div>
              </div>
            </div>
          </div>
        </div>
      </div>
      <div class="logs-section">
        <div class="logs-card">
          <h3 class="card-title">训练日志</h3>
          <div class="logs-container">
            <div v-for="(log, idx) in trainingLogs" :key="idx" class="log-entry">{{ log }}</div>
            <div class="cursor-blink">_</div>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>

<script>
import * as echarts from 'echarts';

export default {
  name: 'ProgressPage',
  data() {
    return {
      renderProgress: 65,
      trainingLogs: [
        '[INFO] 初始化 Gaussian Splatting 模型',
        '[INFO] 加载训练数据集: urban_scene',
        '[INFO] 设置学习率: 0.001',
        '[INFO] 开始第 12500 次迭代',
        '[DEBUG] 当前 PSNR: 28.4 dB',
        '[DEBUG] Loss: 0.0234',
        '[INFO] VRAM 使用率: 85%'
      ],
      // GPU监控数据
      gpuChart: null,
      gpuMonitorTimer: null,
      resizeTimer: null,
      resizeObserver: null,
      gpuModel: '检测中...',
      refreshStatus: '就绪',
      currentGpuData: {
        utilization: 0,
        memoryUsed: 0,
        memoryTotal: 8192,
        temperature: 0
      },
      // 显卡选择相关数据
      showGpuList: false, // 控制下拉列表显示
      availableGpus: [], // 可用的GPU列表
      selectedGpuIndex: -1, // 当前选择的GPU索引，-1表示未选择
      selectedGpuIdentifier: '', // 选中GPU的唯一标识符
      // 图表数据存储
      chartTimeData: [],
      utilizationData: [],
      memoryData: [],
      maxDataPoints: 10, // 最多显示 10 个数据点
          
      // 项目队列数据
      projectQueue: [], // 所有项目的列表
      queueRefreshTimer: null, // 定时刷新队列的定时器
      
      // 渲染预览相关
      latestRenderedImage: null, // 最新渲染图的 Base64 数据
      renderedImageLoading: false, // 加载状态
      renderedImagePath: null // 渲染图路径
    }
  },
  mounted() {
    // 确保 DOM 完全渲染后再初始化图表
    this.$nextTick(() => {
      this.initChart();
      this.startGpuMonitoring();
      this.updateTrainingLogs();
        
      // 加载项目队列
      this.loadProjectQueue();
        
      // 定时刷新项目队列（每 5 秒）
      this.queueRefreshTimer = setInterval(() => {
        this.loadProjectQueue();
      }, 5000);
        
      // 添加额外的 resize 监听确保图表适应
      const resizeObserver = new ResizeObserver(entries => {
        for (let entry of entries) {
          if (entry.target.id === 'gpu-chart' && this.gpuChart) {
            // 使用防抖避免频繁重绘
            clearTimeout(this.resizeTimer);
            this.resizeTimer = setTimeout(() => {
              this.gpuChart.resize();
            }, 150);
          }
        }
      });
        
      const chartContainer = document.getElementById('gpu-chart');
      if (chartContainer) {
        resizeObserver.observe(chartContainer);
        // 保存观察器引用以便清理
        this.resizeObserver = resizeObserver;
      }
    });
      
    // 点击其他地方关闭下拉列表
    document.addEventListener('click', this.handleDocumentClick);
      
    // 监听队列更新事件
    if (window.electronAPI?.onTrainingQueueUpdate) {
      window.electronAPI.onTrainingQueueUpdate((data) => {
        console.log('[队列更新] 收到队列更新:', data);
        this.loadProjectQueue();
      });
    }
  },
  
  beforeUnmount() {
    // 清理定时器
    if (this.gpuMonitorTimer) {
      clearInterval(this.gpuMonitorTimer);
    }
    if (this.queueRefreshTimer) {
      clearInterval(this.queueRefreshTimer);
    }
    // 销毁图表实例
    if (this.gpuChart) {
      this.gpuChart.dispose();
    }
    // 断开 ResizeObserver
    if (this.resizeObserver) {
      this.resizeObserver.disconnect();
    }
    // 清理 resize 定时器
    if (this.resizeTimer) {
      clearTimeout(this.resizeTimer);
    }
    // 移除事件监听器
    document.removeEventListener('click', this.handleDocumentClick);
  },
  methods: {
    // 切换GPU列表显示
    toggleGpuList() {
      this.showGpuList = !this.showGpuList;
      if (this.showGpuList) {
        this.fetchAvailableGpus();
      }
    },
    
    // 从列表中选择GPU
    async selectGpuFromList(index) {
      if (index < this.availableGpus.length) {
        const selectedGpu = this.availableGpus[index];
        
        // 创建GPU唯一标识符（厂商+型号+显存）
        this.selectedGpuIdentifier = `${selectedGpu.vendor}|${selectedGpu.model}|${selectedGpu.vram}`;
        this.selectedGpuIndex = index;
        this.gpuModel = `${selectedGpu.vendor} ${selectedGpu.model}`;
        
        console.log(`用户选择GPU[${index}]: ${this.gpuModel}`);
        console.log(`GPU标识符: ${this.selectedGpuIdentifier}`);
        
        try {
          // 通知主进程设置选中的GPU索引
          if (window.electronAPI.setSelectedGpuIndex) {
            const setResult = await window.electronAPI.setSelectedGpuIndex(index);
            if (setResult.success) {
              console.log(`成功设置主进程GPU索引为: ${index}`);
            } else {
              console.error('设置GPU索引失败:', setResult.error);
            }
          }
        } catch (error) {
          console.error('调用setSelectedGpuIndex失败:', error);
        }
        
        // 重新开始监控
        this.restartGpuMonitoring();
        
        // 关闭下拉列表
        this.showGpuList = false;
      }
    },
    
    // 重新开始GPU监控
    restartGpuMonitoring() {
      // 清理现有定时器
      if (this.gpuMonitorTimer) {
        clearInterval(this.gpuMonitorTimer);
      }
      
      // 重置数据
      this.chartTimeData = [];
      this.utilizationData = [];
      this.memoryData = [];
      this.currentGpuData = {
        utilization: 0,
        memoryUsed: 0,
        memoryTotal: 8192,
        temperature: 0
      };
      
      // 重新开始监控
      this.startGpuMonitoring();
    },
    
    // 获取可用GPU列表
    async fetchAvailableGpus() {
      try {
        if (window.electronAPI && window.electronAPI.getAllGpus) {
          const result = await window.electronAPI.getAllGpus();
          if (result.success) {
            // 前端再做一次过滤确保安全
            const filteredGpus = result.data.filter(gpu => {
              const modelName = (gpu.model || '').toLowerCase();
              const vendorName = (gpu.vendor || '').toLowerCase();
              
              // 前端过滤条件
              const isInvalid = 
                modelName.includes('virtual') || 
                modelName.includes('todesk') ||
                modelName.includes('remote') ||
                modelName.includes('display') ||
                modelName.includes('adapter') ||
                modelName.includes('generic') ||
                modelName.includes('microsoft') ||
                modelName.includes('basic') ||
                modelName.includes('software') ||
                modelName.includes('render') ||
                modelName.includes('mirror') ||
                modelName.includes('dummy') ||
                modelName.includes('null') ||
                modelName.includes('headless') ||
                vendorName.includes('microsoft') ||
                vendorName.includes('virtual') ||
                vendorName.includes('todesk') ||
                vendorName.includes('remote') ||
                !gpu.vram || gpu.vram < 32; // 至少32MB显存
              
              return !isInvalid;
            });
            
            console.log('检测到的GPU设备:');
            filteredGpus.forEach((gpu, index) => {
              console.log(`${index}: ${gpu.vendor} ${gpu.model} (${gpu.vram}MB)`);
            });
            
            // 检查当前选中的GPU是否还在列表中
            if (this.selectedGpuIdentifier) {
              const selectedIndex = filteredGpus.findIndex(gpu => 
                `${gpu.vendor}|${gpu.model}|${gpu.vram}` === this.selectedGpuIdentifier
              );
              
              if (selectedIndex !== -1) {
                // 选中的GPU仍在列表中，保持选择
                this.selectedGpuIndex = selectedIndex;
                console.log(`保持选中GPU: ${filteredGpus[selectedIndex].vendor} ${filteredGpus[selectedIndex].model}`);
              } else {
                // 选中的GPU不在列表中，需要重新选择
                console.log('选中的GPU已不存在，重新选择...');
                this.availableGpus = filteredGpus;
                this.setDefaultNvidiaGpu();
                return; // 避免重复设置
              }
            }
            
            this.availableGpus = filteredGpus;
            
            // 如果没有选中的GPU且列表不为空，设置默认选择
            if (this.selectedGpuIndex === -1 && this.availableGpus.length > 0) {
              this.setDefaultNvidiaGpu();
            }
            
            // 如果没有可用GPU，至少显示当前GPU
            if (this.availableGpus.length === 0 && window.electronAPI.getGpuInfo) {
              const currentGpu = await window.electronAPI.getGpuInfo();
              if (currentGpu.success) {
                const gpu = currentGpu.data;
                const modelName = (gpu.model || '').toLowerCase();
                const vendorName = (gpu.vendor || '').toLowerCase();
                
                // 检查当前GPU是否有效
                const isCurrentGpuValid = !(
                  modelName.includes('virtual') || 
                  modelName.includes('todesk') ||
                  modelName.includes('remote') ||
                  modelName.includes('display') ||
                  vendorName.includes('microsoft') ||
                  vendorName.includes('virtual') ||
                  vendorName.includes('todesk')
                );
                
                if (isCurrentGpuValid) {
                  this.availableGpus = [gpu];
                  this.selectedGpuIndex = 0;
                  this.selectedGpuIdentifier = `${gpu.vendor}|${gpu.model}|${gpu.vram || 0}`;
                  this.gpuModel = `${gpu.vendor} ${gpu.model}`;
                }
              }
            }
          }
        }
      } catch (error) {
        console.error('获取GPU列表失败:', error);
        this.availableGpus = [];
      }
    },
    
    // 设置默认选择NVIDIA显卡
    setDefaultNvidiaGpu() {
      if (this.availableGpus.length > 0) {
        // 查找第一个NVIDIA显卡
        const nvidiaIndex = this.availableGpus.findIndex(gpu => 
          gpu.vendor && gpu.vendor.toLowerCase().includes('nvidia')
        );
        
        if (nvidiaIndex !== -1) {
          // 找到NVIDIA显卡，设置为默认选择
          this.selectedGpuIndex = nvidiaIndex;
          const nvidiaGpu = this.availableGpus[nvidiaIndex];
          this.selectedGpuIdentifier = `${nvidiaGpu.vendor}|${nvidiaGpu.model}|${nvidiaGpu.vram}`;
          this.gpuModel = `${nvidiaGpu.vendor} ${nvidiaGpu.model}`;
          console.log(`默认选择NVIDIA显卡: ${this.gpuModel}`);
        } else {
          // 没有找到NVIDIA显卡，选择第一个可用的
          this.selectedGpuIndex = 0;
          const firstGpu = this.availableGpus[0];
          this.selectedGpuIdentifier = `${firstGpu.vendor}|${firstGpu.model}|${firstGpu.vram}`;
          this.gpuModel = `${firstGpu.vendor} ${firstGpu.model}`;
          console.log(`未找到NVIDIA显卡，选择第一个可用显卡: ${this.gpuModel}`);
        }
        this.restartGpuMonitoring();
      }
    },
    
    formatMemory(bytes) {
      if (!bytes) return '未知';
      const mb = bytes / (1024 * 1024);
      if (mb >= 1024) {
        return `${(mb / 1024).toFixed(1)}GB`;
      }
      return `${Math.round(mb)}MB`;
    },

    initChart() {
      const chartDom = document.getElementById('gpu-chart');
      if (!chartDom) return;
      chartDom.style.width = '100%';
      chartDom.style.height = '100%';
      if (this.gpuChart) {
        this.gpuChart.dispose();
      }
      this.gpuChart = echarts.init(chartDom);
      const option = {
        animation: false,
        tooltip: {
          trigger: 'axis',
          backgroundColor: 'rgba(255, 255, 255, 0.9)',
          borderColor: '#e2e8f0',
          borderWidth: 1,
          textStyle: {
            color: '#1e293b'
          },
          formatter: (params) => {
            let result = `${params[0].axisValue}<br/>`;
            params.forEach(param => {
              const seriesName = param.seriesName;
              const value = param.value;
              const color = param.color;
              result += `<span style="display:inline-block;margin-right:5px;border-radius:10px;width:9px;height:9px;background-color:${color}"></span>`;
              result += `${seriesName}: ${value}%<br/>`;
            });
            return result;
          }
        },
        legend: {
          data: ['GPU使用率', '显存使用率'],
          bottom: 10,
          textStyle: {
            color: '#64748b'
          }
        },
        grid: {
          left: '8%',    // 增加左边距确保Y轴标签完整显示
          right: '8%',   // 增加右边距
          top: '10%',    // 增加上边距
          bottom: '10%', // 增加下边距确保X轴标签和图例完整显示
          containLabel: true
        },
        xAxis: {
          type: 'category',
          boundaryGap: false, // 从最左侧开始绘制
          data: this.chartTimeData,
          axisLine: {
            lineStyle: {
              color: '#e2e8f0'
            }
          },
          axisLabel: {
            color: '#64748b',
            fontSize: 12,
            interval: 0, // 显示所有标签
            rotate: 45   // 旋转标签避免重叠
          }
        },
        yAxis: [
          {
            type: 'value',
            name: '使用率(%)',
            position: 'left',
            min: 0,
            max: 100,
            axisLine: {
              show: false
            },
            axisLabel: {
              color: '#64748b',
              formatter: '{value}%'
            },
            splitLine: {
              lineStyle: {
                type: 'dashed',
                color: '#f1f5f9'
              }
            }
          }
          // 移除右侧Y轴配置
        ],
        series: [
          {
            name: 'GPU使用率',
            type: 'line',
            yAxisIndex: 0,
            smooth: true,
            data: this.utilizationData,
            itemStyle: {
              color: '#8b5cf6'
            },
            lineStyle: {
              width: 2
            },
            areaStyle: {
              color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [{
                  offset: 0,
                  color: 'rgba(139, 92, 246, 0.3)'
                },
                {
                  offset: 1,
                  color: 'rgba(139, 92, 246, 0.05)'
                }
              ])
            },
            showSymbol: false
          },
          {
            name: '显存使用率',
            type: 'line',
            yAxisIndex: 0,  // 改为使用左侧Y轴
            smooth: true,
            data: this.memoryData,
            itemStyle: {
              color: '#0ea5e9'
            },
            lineStyle: {
              width: 2
            },
            areaStyle: {
              color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [{
                  offset: 0,
                  color: 'rgba(14, 165, 233, 0.3)'
                },
                {
                  offset: 1,
                  color: 'rgba(14, 165, 233, 0.05)'
                }
              ])
            },
            showSymbol: false
          }
        ]
      };

      this.gpuChart.setOption(option);

      // 监听窗口大小变化
      window.addEventListener('resize', this.handleResize);
      
      // 确保图表正确渲染
      this.$nextTick(() => {
        if (this.gpuChart) {
          this.gpuChart.resize();
        }
      });
    },

    // 处理窗口大小变化
    handleResize() {
      if (this.gpuChart) {
        // 添加轻微延迟确保DOM更新完成
        setTimeout(() => {
          this.gpuChart.resize();
        }, 100);
      }
    },

    startGpuMonitoring() {
      this.fetchGpuData();
      this.gpuMonitorTimer = setInterval(() => {
        this.fetchGpuData();
      }, 2000);
    },

    // 处理GPU数据获取错误
    handleGpuError(errorMessage) {
      this.refreshStatus = '错误';
      
      // 分析错误类型并提供针对性提示
      let displayMessage = '数据获取失败';
      let hintText = '';
      
      if (errorMessage.includes('集成显卡') || errorMessage.includes('Intel') || errorMessage.includes('AMD')) {
        displayMessage = '集成显卡监控';
        hintText = '集成显卡数据有限，显示模拟数据';
      } else if (errorMessage.includes('未检测到')) {
        displayMessage = '未检测到GPU';
        hintText = '请检查硬件连接或驱动程序';
      } else if (errorMessage.includes('API不可用')) {
        displayMessage = 'API连接失败';
        hintText = '请重启应用程序';
      } else {
        hintText = '请检查硬件状态';
      }
      
      // 只在没有用户选择时更新GPU型号
      if (this.selectedGpuIndex === -1) {
        this.gpuModel = displayMessage;
      }
      
      console.error('GPU监控错误:', errorMessage);
      
      // 显示错误信息
      if (this.gpuChart) {
        this.gpuChart.setOption({
          title: {
            text: displayMessage,
            subtext: hintText,
            left: 'center',
            top: 'center',
            textStyle: {
              color: '#ef4444',
              fontSize: 16,
              fontWeight: 'bold'
            },
            subtextStyle: {
              color: '#64748b',
              fontSize: 12
            }
          },
          series: [
            {
              data: []
            },
            {
              data: []
            }
          ]
        });
      }
    },

    // 获取GPU数据
    async fetchGpuData() {
      try {
        this.refreshStatus = '刷新中...';
        
        // 检查Electron API是否可用
        if (!window.electronAPI || !window.electronAPI.getGpuUsage) {
          throw new Error('Electron API不可用，请确保在Electron环境中运行');
        }
        
        // 获取GPU使用率数据
        const usageResult = await window.electronAPI.getGpuUsage();
        
        if (!usageResult.success) {
          throw new Error(usageResult.error || '获取GPU使用率数据失败');
        }
        
        const gpuData = usageResult.data;
        
        // 严格的数据验证和边界检查
        const validatedData = {
          utilization: Math.max(0, Math.min(100, gpuData.utilization || 0)),
          memoryUsed: Math.max(0, gpuData.memoryUsed || 0),
          memoryTotal: Math.max(1, gpuData.memoryTotal || 8192 * 1024 * 1024), // 默认8GB转为字节
          temperature: Math.max(0, gpuData.temperature || 0),
          power: Math.max(0, gpuData.power || 0),
          fanSpeed: Math.max(0, Math.min(100, gpuData.fanSpeed || 0))
        };
        
        // 确保显存使用不超过总显存
        if (validatedData.memoryUsed > validatedData.memoryTotal) {
          validatedData.memoryUsed = validatedData.memoryTotal;
        }
        
        // 更新当前数据显示
        this.currentGpuData = validatedData;
        
        // 更新GPU型号信息（但不改变用户选择）
        await this.updateGpuModelWithoutChangingSelection();
        
        // 添加到图表数据
        this.addToChartData(validatedData);
        
        // 更新图表
        this.updateChart();
        
        this.refreshStatus = '就绪';
        
        // 为不同类型的GPU提供不同的日志信息
        const currentGpuName = this.gpuModel.toLowerCase();
        if (currentGpuName.includes('intel')) {
          console.log(`✓ Intel集成显卡数据获取成功: ${validatedData.utilization}% (基于CPU负载推算)`);
        } else if (currentGpuName.includes('amd')) {
          console.log(`✓ AMD集成显卡数据获取成功: ${validatedData.utilization}% (基于系统负载推算)`);
        } else if (currentGpuName.includes('nvidia')) {
          console.log(`✓ NVIDIA独立显卡数据获取成功: ${validatedData.utilization}% (直接硬件读取)`);
        } else {
          console.log(`✓ GPU数据获取成功: ${validatedData.utilization}%`);
        }
        
      } catch (error) {
        console.error('获取GPU数据失败:', error);
        this.handleGpuError(error.message);
      }
    },

    // 更新GPU型号信息但不改变用户选择
    async updateGpuModelWithoutChangingSelection() {
      try {
        if (window.electronAPI.getGpuInfo) {
          const infoResult = await window.electronAPI.getGpuInfo();
          if (infoResult.success) {
            const currentGpuInfo = `${infoResult.data.vendor} ${infoResult.data.model}`;
            
            // 只在没有用户选择时更新GPU型号
            if (this.selectedGpuIndex === -1) {
              this.gpuModel = currentGpuInfo;
              console.log(`自动更新GPU型号: ${currentGpuInfo}`);
            } else {
              // 有用户选择时，验证当前显示的GPU是否与系统报告的一致
              const displayedGpu = this.gpuModel;
              if (displayedGpu !== currentGpuInfo) {
                console.warn(`警告: 显示的GPU(${displayedGpu})与系统报告的GPU(${currentGpuInfo})不一致`);
                console.warn(`当前选中索引: ${this.selectedGpuIndex}`);
                // 不自动更改用户选择，但记录不一致情况
              } else {
                console.log(`✓ GPU一致性验证通过: ${currentGpuInfo}`);
              }
            }
          } else {
            if (this.selectedGpuIndex === -1) {
              this.gpuModel = '信息获取失败';
            }
          }
        }
      } catch (error) {
        console.warn('获取GPU型号信息失败:', error);
        if (this.selectedGpuIndex === -1) {
          this.gpuModel = '信息获取失败';
        }
      }
    },

    // 添加数据到图表
    addToChartData(data) {
      const now = new Date();
      const timeString = `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}:${now.getSeconds().toString().padStart(2, '0')}`;
      
      // 添加新数据点
      this.chartTimeData.push(timeString);
      this.utilizationData.push(data.utilization);
      
      // 将显存使用量转换为百分比，使用字节单位进行计算
      let memoryPercentage = 0;
      if (data.memoryTotal > 0) {
        memoryPercentage = Math.round((data.memoryUsed / data.memoryTotal) * 100);
      }
      
      // 确保百分比在合理范围内（0-100%）
      memoryPercentage = Math.max(0, Math.min(100, memoryPercentage));
      this.memoryData.push(memoryPercentage);
      
      // 保持数据点数量不超过最大值
      if (this.chartTimeData.length > this.maxDataPoints) {
        this.chartTimeData.shift();
        this.utilizationData.shift();
        this.memoryData.shift();
      }
      
      // 确保数组长度固定为maxDataPoints，不足时用null填充
      while (this.chartTimeData.length < this.maxDataPoints) {
        this.chartTimeData.unshift('');
        this.utilizationData.unshift(null);
        this.memoryData.unshift(null);
      }
    },

    // 更新图表显示
    updateChart() {
      if (this.gpuChart) {
        // 确保数据数组长度固定，不足时用null填充
        const fixedTimeData = [...this.chartTimeData];
        const fixedUtilizationData = [...this.utilizationData];
        const fixedMemoryData = [...this.memoryData];
        
        // 补充到固定长度
        while (fixedTimeData.length < this.maxDataPoints) {
          fixedTimeData.unshift('');
          fixedUtilizationData.unshift(null);
          fixedMemoryData.unshift(null);
        }
        
        this.gpuChart.setOption({
          xAxis: {
            data: fixedTimeData.slice(-this.maxDataPoints) // 只显示最新的maxDataPoints个数据点
          },
          yAxis: [
            {
              name: '使用率 (%)',
              max: 100,
              min: 0,
              axisLabel: {
                formatter: '{value}%'
              }
            }
          ],
          series: [
            {
              name: 'GPU使用率',
              data: fixedUtilizationData.slice(-this.maxDataPoints)
            },
            {
              name: '显存使用率',
              data: fixedMemoryData.slice(-this.maxDataPoints)
            }
          ]
        });
      }
    },

    // 更新训练日志
    updateTrainingLogs() {
      setInterval(() => {
        const timestamp = new Date().toISOString().slice(0, 19).replace('T', ' ');
        
        // 根据当前GPU状态生成相关日志
        const logs = [
          `[${timestamp}] Iteration ${Math.floor(10000 + Math.random() * 20000)} | Loss: ${(0.001 + Math.random() * 0.01).toFixed(4)} | PSNR: ${(25 + Math.random() * 10).toFixed(2)}dB`,
          `[${timestamp}] GPU状态 - 使用率: ${this.currentGpuData.utilization}% | 显存: ${Math.round((this.currentGpuData.memoryUsed / (1024 * 1024)).toFixed(1))}MB/${Math.round((this.currentGpuData.memoryTotal / (1024 * 1024)).toFixed(1))}MB (${Math.round((this.currentGpuData.memoryUsed / this.currentGpuData.memoryTotal) * 100)}%)`,
          `[${timestamp}] 系统监控 - 温度: ${this.currentGpuData.temperature}°C | 功耗: ${Math.round(this.currentGpuData.power)}W | 风扇: ${this.currentGpuData.fanSpeed}%`
        ];
        
        // 添加新日志并保持数组长度
        this.trainingLogs.push(logs[Math.floor(Math.random() * logs.length)]);
        if (this.trainingLogs.length > 20) {
          this.trainingLogs.shift();
        }
      }, 3000);
    },
    
    // 处理文档点击事件，用于关闭下拉列表
    handleDocumentClick(event) {
      const selectorContainer = document.querySelector('.gpu-selector-container');
      if (selectorContainer && !selectorContainer.contains(event.target)) {
        this.showGpuList = false;
      }
    },
    
    // 加载项目队列
    async loadProjectQueue() {
      try {
        if (window.electronAPI?.getProjectList) {
          const result = await window.electronAPI.getProjectList();
          if (result.success) {
            this.projectQueue = result.data || [];
            console.log('[项目队列] 已加载', this.projectQueue.length, '个项目');
          }
        } else {
          console.warn('[项目队列] getProjectList API 不可用');
          // 使用模拟数据（开发测试用）
          this.projectQueue = [
            {
              projectId: 'project_20250405_1430_abc',
              name: 'Lego Scene Training',
              outputPath: 'E:/outputs/lego/',
              lastModified: new Date().toISOString(),
              status: 'training',
              currentIteration: 18700,
              stage: 'stage1'
            }
          ];
        }
      } catch (error) {
        console.error('[项目队列] 加载失败:', error);
        this.projectQueue = [];
      }
    },
    
    // 获取状态文本
    getStatusText(status) {
      const statusMap = {
        waiting: '等待中',
        training: '训练中',
        paused: '已暂停',
        completed: '已完成',
        error: '错误',
        disconnected: '已断开'
      };
      return statusMap[status] || status;
    },
    
    // 获取状态样式类
    getStatusClass(status) {
      const classMap = {
        waiting: 'status-waiting',
        training: 'status-training',
        paused: 'status-paused',
        completed: 'status-completed',
        error: 'status-error',
        disconnected: 'status-disconnected'
      };
      return classMap[status] || '';
    },
    
    // 点击项目项，恢复到训练页面
    async resumeProject(project) {
      console.log('[恢复项目] 准备恢复:', project);
      
      try {
        // 先尝试加载最新渲染图（用于后续显示）
        if (project.outputPath) {
          await this.loadLatestRenderedImage(project.outputPath);
        }
        
        // 跳转到 TrainPage 并传递 projectId 和渲染图信息
        const query = {
          resumeProjectId: project.projectId
        };
        
        // 如果有渲染图，也传递过去
        if (this.latestRenderedImage) {
          query.initialPreviewImage = this.latestRenderedImage;
        }
        
        this.$router.push({
          path: '/train',
          query
        });
      } catch (error) {
        console.error('[恢复项目] 跳转失败:', error);
        alert('恢复项目失败：' + error.message);
      }
    },
    
    // 格式化最后修改时间
    formatLastModified(isoString) {
      if (!isoString) return '';
      const date = new Date(isoString);
      const now = new Date();
      const diffMs = now - date;
      const diffMinutes = Math.floor(diffMs / 60000);
      const diffHours = Math.floor(diffMs / 3600000);
      const diffDays = Math.floor(diffMs / 86400000);
      
      if (diffMinutes < 1) {
        return '刚刚';
      } else if (diffMinutes < 60) {
        return `${diffMinutes}分钟前`;
      } else if (diffHours < 24) {
        return `${diffHours}小时前`;
      } else if (diffDays < 7) {
        return `${diffDays}天前`;
      } else {
        return date.toLocaleDateString('zh-CN');
      }
    },
    
    // 计算进度百分比
    getProgressPercent(project) {
      if (!project.currentIteration || !project.totalIterations) {
        return 0;
      }
      return Math.min(100, Math.round((project.currentIteration / project.totalIterations) * 100));
    },
    
    // 加载最新渲染图像
    async loadLatestRenderedImage(modelPath) {
      if (!modelPath) {
        console.log('[渲染图] 模型路径为空，跳过加载');
        return;
      }
      
      this.renderedImageLoading = true;
      this.latestRenderedImage = null;
      this.renderedImagePath = null;
      
      try {
        const result = await window.electronAPI?.getLatestRenderedImage(modelPath);
        
        if (result && result.success && result.imageBase64) {
          // 直接使用 Base64 数据，不添加时间戳参数（避免解析失败）
          const imageUrl = result.imageBase64;
          
          console.log('[渲染图] 找到最新渲染图:', result.imagePath);
          console.log('[渲染图] Base64 图片大小:', (imageUrl.length / 1024).toFixed(2), 'KB');
          
          // 预加载图片
          const img = new Image();
          img.onload = () => {
            this.latestRenderedImage = imageUrl;
            this.renderedImagePath = result.imagePath;
            console.log('[渲染图] ✓ 图片加载成功');
          };
          img.onerror = (err) => {
            console.error('[渲染图] ✗ 图片加载失败:', err);
            this.latestRenderedImage = null;
          };
          img.src = imageUrl;
        } else {
          // 没有找到渲染图（可能是训练初期）
          console.log('[渲染图] 未找到渲染图像（可能是训练初期）');
          if (result?.error) {
            console.log('[渲染图] 错误信息:', result.error);
          }
          this.latestRenderedImage = null;
        }
      } catch (error) {
        console.error('[渲染图] 加载失败:', error);
        this.latestRenderedImage = null;
      } finally {
        this.renderedImageLoading = false;
      }
    },
  }
}
</script>

<style scoped>
.progress-container {
  height: 100%;
  background-color: #f8fafc;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.progress-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 1.5rem;
  overflow-y: auto;
  gap: 1.5rem;
}

.dashboard-section {
  flex-shrink: 0;
}

.dashboard-grid {
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: 1.5rem;
}

.card-title {
  font-size: 1.125rem;
  font-weight: bold;
  color: #1e293b;
  margin-bottom: 1rem;
}

.gpu-monitor-card {
  background: white;
  padding: 1.5rem;
  border-radius: 1rem;
  border: 1px solid #e2e8f0;
  box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 32rem; /* 确保最小高度 */
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 1rem;
  flex-shrink: 0; /* 防止头部被压缩 */
}

.gpu-stats {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  font-size: 0.875rem;
}

.stat-item {
  display: flex;
  gap: 0.5rem;
}

.stat-label {
  color: #64748b;
  font-weight: 500;
}

.stat-value {
  color: #1e293b;
  font-weight: 600;
}

.chart-container {
  width: 100%;
  flex: 1; /* 占据剩余空间 */
  min-height: 20rem; /* 最小高度确保图表可见 */
  position: relative;
}

.gpu-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 1rem;
  padding-top: 1rem;
  border-top: 1px solid #e2e8f0;
  font-size: 0.875rem;
  flex-shrink: 0; /* 防止底部信息被压缩 */
}

.gpu-selector-container {
  position: relative;
  display: inline-block;
}

.gpu-model-display {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 0.75rem;
  background-color: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 0.5rem;
  cursor: pointer;
  transition: all 0.2s;
  min-width: 200px;
  justify-content: space-between;
}

.gpu-model-display:hover {
  background-color: #f1f5f9;
  border-color: #cbd5e1;
}

.gpu-model-display.active {
  border-color: #8b5cf6;
  box-shadow: 0 0 0 3px rgba(139, 92, 246, 0.1);
}

.gpu-model-text {
  color: #64748b;
  font-weight: 500;
  flex: 1;
  text-align: left;
}

.dropdown-arrow {
  color: #94a3b8;
  font-size: 0.75rem;
  transition: transform 0.2s;
}

.dropdown-arrow.rotated {
  transform: rotate(180deg);
}

.gpu-dropdown-list {
  position: absolute;
  top: 100%;
  left: 0;
  right: 0;
  background: white;
  border: 1px solid #e2e8f0;
  border-radius: 0.5rem;
  box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.1);
  margin-top: 0.25rem;
  z-index: 100;
  max-height: 300px;
  overflow-y: auto;
}

.gpu-dropdown-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.75rem;
  cursor: pointer;
  border-bottom: 1px solid #f1f5f9;
  transition: all 0.2s;
}

.gpu-dropdown-item:last-child {
  border-bottom: none;
}

.gpu-dropdown-item:hover {
  background-color: #f8fafc;
}

.gpu-dropdown-item.selected {
  background-color: #f5f3ff;
  border-left: 3px solid #8b5cf6;
}

.gpu-item-content {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex: 1;
}


.gpu-item-details {
  display: flex;
  flex-direction: column;
}

.gpu-item-name {
  font-weight: 500;
  color: #1e293b;
  font-size: 0.875rem;
}

.gpu-item-memory {
  font-size: 0.75rem;
  color: #64748b;
}

.selection-check {
  color: #8b5cf6;
  font-weight: bold;
  font-size: 1rem;
  flex-shrink: 0;
}

.no-gpus-item {
  padding: 1rem;
  text-align: center;
  color: #64748b;
}

.no-gpus-text {
  font-size: 0.875rem;
}

/* 项目队列样式 */
.no-projects {
  padding: 2rem;
  text-align: center;
  color: #64748b;
}

.no-projects-icon {
  font-size: 3rem;
  margin-bottom: 1rem;
}

.no-projects-text {
  font-size: 1rem;
  font-weight: 500;
  margin-bottom: 0.5rem;
}

.no-projects-hint {
  font-size: 0.875rem;
  color: #94a3b8;
}

.queue-item {
  cursor: pointer;
  transition: all 0.2s;
}

.queue-item:hover {
  background-color: #f8fafc;
  transform: translateX(2px);
}

.item-details {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-top: 0.5rem;
  font-size: 0.75rem;
  color: #64748b;
}

.detail-separator {
  color: #cbd5e1;
}

.detail-time {
  color: #94a3b8;
}

.status-badge {
  padding: 0.25rem 0.75rem;
  border-radius: 9999px;
  font-size: 0.75rem;
  font-weight: 500;
}

.status-waiting {
  background-color: #f1f5f9;
  color: #475569;
}

.status-training {
  background-color: #dbeafe;
  color: #1e40af;
}

.status-paused {
  background-color: #fef3c7;
  color: #92400e;
}

.status-completed {
  background-color: #dcfce7;
  color: #166534;
}

.status-error {
  background-color: #fee2e2;
  color: #991b1b;
}

.status-disconnected {
  background-color: #e2e8f0;
  color: #475569;
}

.refresh-status {
  color: #8b5cf6;
  font-weight: 500;
}

.queue-card {
  background: white;
  padding: 1.5rem;
  border-radius: 1rem;
  border: 1px solid #e2e8f0;
  box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
}

.queue-list {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.queue-item {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.progress-bar-indicator {
  width: 0.5rem;
  height: 3rem;
  background-color: #7e22ce;
  border-radius: 9999px;
  flex-shrink: 0;
}

.indicator-placeholder {
  width: 0.5rem;
  height: 3rem;
  background-color: #cbd5e1;
  border-radius: 9999px;
  flex-shrink: 0;
}

.item-content {
  flex: 1;
}

.item-header {
  display: flex;
  justify-content: space-between;
  font-size: 0.875rem;
  margin-bottom: 0.25rem;
}

.task-name {
  font-weight: 500;
  color: #1e293b;
}

.progress-percent {
  color: #7e22ce;
  font-weight: 500;
}

.status-pending {
  color: #94a3b8;
}

.progress-track {
  width: 100%;
  height: 0.375rem;
  background-color: #f1f5f9;
  border-radius: 9999px;
  overflow: hidden;
}

.progress-track.empty {
  background-color: #f1f5f9;
}

.progress-fill {
  height: 100%;
  background-color: #7e22ce;
  border-radius: 9999px;
  transition: width 0.3s ease;
}

.logs-section {
  flex-grow: 1;
  display: flex;
  flex-direction: column;
}

.logs-card {
  background: white;
  padding: 1.5rem;
  border-radius: 1rem;
  border: 1px solid #e2e8f0;
  box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
  display: flex;
  flex-direction: column;
  flex-grow: 1;
}

.logs-container {
  flex: 1;
  background-color: #0f172a;
  border-radius: 0.75rem;
  padding: 1rem;
  font-family: monospace;
  font-size: 0.75rem;
  color: #4ade80;
  line-height: 1.5;
  overflow-y: auto;
}

.log-entry {
  margin-bottom: 0.25rem;
}

.cursor-blink {
  display: inline-block;
  animation: blink 1s infinite;
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}

/* 响应式设计优化 */
@media (max-width: 1024px) {
  .dashboard-grid {
    grid-template-columns: 1fr;
  }
  
  .card-header {
    flex-direction: column;
    gap: 0.5rem;
  }
  
  .gpu-stats {
    flex-direction: row;
    flex-wrap: wrap;
    gap: 1rem;
  }
  
  .modal-content {
    width: 95%;
    margin: 1rem;
  }
  
  .gpu-specs {
    flex-direction: column;
    gap: 0.25rem;
  }
}

@media (max-width: 768px) {
  .progress-content {
    padding: 1rem;
  }
  
  .gpu-monitor-card,
  .queue-card,
  .logs-card {
    padding: 1rem;
  }
  
  .modal-body {
    padding: 1rem;
  }
  
  .modal-header,
  .modal-footer {
    padding: 1rem;
  }
}
</style>

.error-display {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 20rem;
  background-color: #fef2f2;
  border: 2px dashed #fecaca;
  border-radius: 0.5rem;
  color: #ef4444;
  text-align: center;
}

.error-icon {
  font-size: 3rem;
  margin-bottom: 1rem;
}

.error-message {
  font-size: 1.25rem;
  font-weight: 600;
  margin-bottom: 0.5rem;
}

.error-detail {
  font-size: 0.875rem;
  color: #64748b;
  margin-bottom: 0.5rem;
}

.error-hint {
  font-size: 0.75rem;
  color: #94a3b8;
  max-width: 80%;
}

/* GPU选择弹窗样式 */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(0, 0, 0, 0.5);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 1000;
  backdrop-filter: blur(4px);
}

.modal-content {
  background: white;
  border-radius: 1rem;
  box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
  width: 90%;
  max-width: 500px;
  max-height: 80vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1.5rem;
  border-bottom: 1px solid #e2e8f0;
}

.modal-title {
  font-size: 1.25rem;
  font-weight: bold;
  color: #1e293b;
  margin: 0;
}

.modal-close {
  background: none;
  border: none;
  font-size: 1.5rem;
  color: #94a3b8;
  cursor: pointer;
  width: 2rem;
  height: 2rem;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 0.5rem;
  transition: all 0.2s;
}

.modal-close:hover {
  background-color: #f1f5f9;
  color: #1e293b;
}

.modal-body {
  padding: 1.5rem;
  flex: 1;
  overflow-y: auto;
}

.no-gpus {
  text-align: center;
  padding: 2rem;
}

.no-gpus-icon {
  font-size: 3rem;
  margin-bottom: 1rem;
}

.no-gpus p {
  color: #64748b;
  margin: 0.5rem 0;
}

.no-gpus .hint {
  font-size: 0.875rem;
  color: #94a3b8;
}

.gpu-list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.gpu-item {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 1rem;
  border: 2px solid #e2e8f0;
  border-radius: 0.75rem;
  cursor: pointer;
  transition: all 0.2s;
}

.gpu-item:hover {
  border-color: #cbd5e1;
  background-color: #f8fafc;
}

.gpu-item.selected {
  border-color: #8b5cf6;
  background-color: #f5f3ff;
}


.gpu-details {
  flex: 1;
}

.gpu-name {
  font-weight: 600;
  color: #1e293b;
  margin-bottom: 0.25rem;
}

.gpu-specs {
  display: flex;
  gap: 1rem;
  flex-wrap: wrap;
}

.spec {
  font-size: 0.875rem;
  color: #64748b;
}

.selection-indicator {
  color: #8b5cf6;
  font-weight: bold;
  font-size: 1.25rem;
  flex-shrink: 0;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 1rem;
  padding: 1.5rem;
  border-top: 1px solid #e2e8f0;
  background-color: #f8fafc;
}

.btn {
  padding: 0.5rem 1rem;
  border-radius: 0.5rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
  border: none;
  font-size: 0.875rem;
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-secondary {
  background-color: #e2e8f0;
  color: #1e293b;
}

.btn-secondary:hover:not(:disabled) {
  background-color: #cbd5e1;
}

.btn-primary {
  background-color: #8b5cf6;
  color: white;
}

.btn-primary:hover:not(:disabled) {
  background-color: #7e22ce;
}

.gpu-model {
  color: #64748b;
  font-weight: 500;
  cursor: pointer;
  padding: 0.25rem 0.5rem;
  border-radius: 0.25rem;
  transition: all 0.2s;
}

.gpu-model:hover {
  background-color: #f1f5f9;
  color: #8b5cf6;
}
