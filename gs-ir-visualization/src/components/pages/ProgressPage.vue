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
              <!-- 项目列表 -->
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
      trainingLogs: [],
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
      showGpuList: false,
      availableGpus: [],
      selectedGpuIndex: -1,
      selectedGpuIdentifier: '',
      chartTimeData: [],
      utilizationData: [],
      memoryData: [],
      maxDataPoints: 10,
      projectQueue: [],
      queueRefreshTimer: null, 
      latestRenderedImage: null,
      renderedImageLoading: false,
      renderedImagePath: null
    }
  },
  mounted() {
    this.$nextTick(() => {
      this.initChart();
      this.startGpuMonitoring();
      this.loadProjectQueue();
      this.queueRefreshTimer = setInterval(() => {
        this.loadProjectQueue();
      }, 5000);
        
      const resizeObserver = new ResizeObserver(entries => {
        for (let entry of entries) {
          if (entry.target.id === 'gpu-chart' && this.gpuChart) {
            // 防抖
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
        this.resizeObserver = resizeObserver;
      }
    });
      
    document.addEventListener('click', this.handleDocumentClick);
      
    if (window.electronAPI?.onTrainingQueueUpdate) {
      window.electronAPI.onTrainingQueueUpdate((data) => {
        console.log('[队列更新] 收到队列更新:', data);
        this.loadProjectQueue();
      });
    }
    
    // 监听训练输出
    if (window.electronAPI?.onTrainingOutput) {
      window.electronAPI.onTrainingOutput((data) => {
        if (data && data.output) {
          this.addTrainingLog(data.output);
        }
      });
    }
    
    // 监听烘焙输出
    if (window.electronAPI?.onBakingOutput) {
      window.electronAPI.onBakingOutput((data) => {
        if (data && data.output) {
          this.addTrainingLog(data.output);
        }
      });
    }
  },
  
  beforeUnmount() {
    if (this.gpuMonitorTimer) {
      clearInterval(this.gpuMonitorTimer);
    }
    if (this.queueRefreshTimer) {
      clearInterval(this.queueRefreshTimer);
    }
    if (this.gpuChart) {
      this.gpuChart.dispose();
    }
    // 断开 ResizeObserver
    if (this.resizeObserver) {
      this.resizeObserver.disconnect();
    }
    // 清理定时器
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
        
        // 创建GPU标识
        this.selectedGpuIdentifier = `${selectedGpu.vendor}|${selectedGpu.model}|${selectedGpu.vram}`;
        this.selectedGpuIndex = index;
        this.gpuModel = `${selectedGpu.vendor} ${selectedGpu.model}`;
        
        console.log(`用户选择GPU[${index}]: ${this.gpuModel}`);
        console.log(`GPU标识符: ${this.selectedGpuIdentifier}`);
        
        try {
          // 通知主进程
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
        this.restartGpuMonitoring();
        this.showGpuList = false;
      }
    },

    restartGpuMonitoring() {
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
      
      this.startGpuMonitoring();
    },
    
    // 获取可用GPU列表
    async fetchAvailableGpus() {
      try {
        if (window.electronAPI && window.electronAPI.getAllGpus) {
          const result = await window.electronAPI.getAllGpus();
          if (result.success) {
            // 前端过滤
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
                !gpu.vram || gpu.vram < 32; 
              
              return !isInvalid;
            });
            
            console.log('检测到的GPU设备:');
            filteredGpus.forEach((gpu, index) => {
              console.log(`${index}: ${gpu.vendor} ${gpu.model} (${gpu.vram}MB)`);
            });
            if (this.selectedGpuIdentifier) {
              const selectedIndex = filteredGpus.findIndex(gpu => 
                `${gpu.vendor}|${gpu.model}|${gpu.vram}` === this.selectedGpuIdentifier
              );
              
              if (selectedIndex !== -1) {
                this.selectedGpuIndex = selectedIndex;
                console.log(`保持选中GPU: ${filteredGpus[selectedIndex].vendor} ${filteredGpus[selectedIndex].model}`);
              } else {
                console.log('选中的GPU已不存在，重新选择...');
                this.availableGpus = filteredGpus;
                this.setDefaultNvidiaGpu();
                return;
              }
            }
            
            this.availableGpus = filteredGpus;
            
            // 设置默认选择
            if (this.selectedGpuIndex === -1 && this.availableGpus.length > 0) {
              this.setDefaultNvidiaGpu();
            }
            
            // 显示当前GPU
            if (this.availableGpus.length === 0 && window.electronAPI.getGpuInfo) {
              const currentGpu = await window.electronAPI.getGpuInfo();
              if (currentGpu.success) {
                const gpu = currentGpu.data;
                const modelName = (gpu.model || '').toLowerCase();
                const vendorName = (gpu.vendor || '').toLowerCase();
                
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
    
    // 默认选择NVIDIA显卡
    setDefaultNvidiaGpu() {
      if (this.availableGpus.length > 0) {
        const nvidiaIndex = this.availableGpus.findIndex(gpu => 
          gpu.vendor && gpu.vendor.toLowerCase().includes('nvidia')
        );
        
        if (nvidiaIndex !== -1) {
          this.selectedGpuIndex = nvidiaIndex;
          const nvidiaGpu = this.availableGpus[nvidiaIndex];
          this.selectedGpuIdentifier = `${nvidiaGpu.vendor}|${nvidiaGpu.model}|${nvidiaGpu.vram}`;
          this.gpuModel = `${nvidiaGpu.vendor} ${nvidiaGpu.model}`;
          console.log(`默认选择NVIDIA显卡: ${this.gpuModel}`);
        } else {
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
          left: '8%',
          right: '8%',
          top: '10%',
          bottom: '10%',
          containLabel: true
        },
        xAxis: {
          type: 'category',
          boundaryGap: false,
          data: this.chartTimeData,
          axisLine: {
            lineStyle: {
              color: '#e2e8f0'
            }
          },
          axisLabel: {
            color: '#64748b',
            fontSize: 12,
            interval: 0,
            rotate: 45
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
            yAxisIndex: 0,
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
      window.addEventListener('resize', this.handleResize);
      
      this.$nextTick(() => {
        if (this.gpuChart) {
          this.gpuChart.resize();
        }
      });
    },

    // 窗口变化
    handleResize() {
      if (this.gpuChart) {
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
    //处理错误
    handleGpuError(errorMessage) {
      this.refreshStatus = '错误';
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
      
      if (this.selectedGpuIndex === -1) {
        this.gpuModel = displayMessage;
      }
      
      console.error('GPU监控错误:', errorMessage);
      
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
        if (!window.electronAPI || !window.electronAPI.getGpuUsage) {
          throw new Error('Electron API不可用，请确保在Electron环境中运行');
        }
        // 获取GPU使用率
        const usageResult = await window.electronAPI.getGpuUsage();
        if (!usageResult.success) {
          throw new Error(usageResult.error || '获取GPU使用率数据失败');
        }
        const gpuData = usageResult.data;
        
        // 数据验证
        const validatedData = {
          utilization: Math.max(0, Math.min(100, gpuData.utilization || 0)),
          memoryUsed: Math.max(0, gpuData.memoryUsed || 0),
          memoryTotal: Math.max(1, gpuData.memoryTotal || 8192 * 1024 * 1024),
          temperature: Math.max(0, gpuData.temperature || 0),
          power: Math.max(0, gpuData.power || 0),
          fanSpeed: Math.max(0, Math.min(100, gpuData.fanSpeed || 0))
        };
        if (validatedData.memoryUsed > validatedData.memoryTotal) {
          validatedData.memoryUsed = validatedData.memoryTotal;
        }
        this.currentGpuData = validatedData;
        
        // 更新GPU型号信息
        await this.updateGpuModelWithoutChangingSelection();
        this.addToChartData(validatedData);
        this.updateChart();
        this.refreshStatus = '就绪';
        const currentGpuName = this.gpuModel.toLowerCase();
        if (currentGpuName.includes('intel')) {
          console.log(`Intel集成显卡数据获取成功: ${validatedData.utilization}% (基于CPU负载推算)`);
        } else if (currentGpuName.includes('amd')) {
          console.log(`AMD集成显卡数据获取成功: ${validatedData.utilization}% (基于系统负载推算)`);
        } else if (currentGpuName.includes('nvidia')) {
          console.log(`NVIDIA独立显卡数据获取成功: ${validatedData.utilization}% (直接硬件读取)`);
        } else {
          console.log(`GPU数据获取成功: ${validatedData.utilization}%`);
        }
        
      } catch (error) {
        console.error('获取GPU数据失败:', error);
        this.handleGpuError(error.message);
      }
    },

    // 更新GPU型号信息
    async updateGpuModelWithoutChangingSelection() {
      try {
        if (window.electronAPI.getGpuInfo) {
          const infoResult = await window.electronAPI.getGpuInfo();
          if (infoResult.success) {
            const currentGpuInfo = `${infoResult.data.vendor} ${infoResult.data.model}`;
            if (this.selectedGpuIndex === -1) {
              this.gpuModel = currentGpuInfo;
              console.log(`自动更新GPU型号: ${currentGpuInfo}`);
            } else {
              const displayedGpu = this.gpuModel;
              if (displayedGpu !== currentGpuInfo) {
                console.warn(`警告: 显示的GPU(${displayedGpu})与系统报告的GPU(${currentGpuInfo})不一致`);
                console.warn(`当前选中索引: ${this.selectedGpuIndex}`);
              } else {
                console.log(`GPU一致性验证通过: ${currentGpuInfo}`);
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
      
      // 添加数据点
      this.chartTimeData.push(timeString);
      this.utilizationData.push(data.utilization);
      
      let memoryPercentage = 0;
      if (data.memoryTotal > 0) {
        memoryPercentage = Math.round((data.memoryUsed / data.memoryTotal) * 100);
      }
      memoryPercentage = Math.max(0, Math.min(100, memoryPercentage));
      this.memoryData.push(memoryPercentage);
      if (this.chartTimeData.length > this.maxDataPoints) {
        this.chartTimeData.shift();
        this.utilizationData.shift();
        this.memoryData.shift();
      }
      while (this.chartTimeData.length < this.maxDataPoints) {
        this.chartTimeData.unshift('');
        this.utilizationData.unshift(null);
        this.memoryData.unshift(null);
      }
    },

    // 更新图表显示
    updateChart() {
      if (this.gpuChart) {
        const fixedTimeData = [...this.chartTimeData];
        const fixedUtilizationData = [...this.utilizationData];
        const fixedMemoryData = [...this.memoryData];
        while (fixedTimeData.length < this.maxDataPoints) {
          fixedTimeData.unshift('');
          fixedUtilizationData.unshift(null);
          fixedMemoryData.unshift(null);
        }
        
        this.gpuChart.setOption({
          xAxis: {
            data: fixedTimeData.slice(-this.maxDataPoints) // 限制数据点
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
    
    // 添加训练日志
    addTrainingLog(logText) {
      if (!logText) return;
      this.trainingLogs.push(logText);
      if (this.trainingLogs.length > 100) {
        this.trainingLogs.shift();
      }
      this.$nextTick(() => {
        const logsContainer = document.querySelector('.logs-container');
        if (logsContainer) {
          logsContainer.scrollTop = logsContainer.scrollHeight;
        }
      });
    },
    
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
            // 显示正在训练或等待中的项目
            this.projectQueue = (result.data || []).filter(project => 
              project.status !== 'completed'
            );
            console.log('[项目队列] 已加载', this.projectQueue.length, '个项目（已过滤已完成）');
          }
        } else {
          console.warn('[项目队列] getProjectList API 不可用');
          // 使用模拟数据测试
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
        baking: 'Baking 中',
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
        baking: 'status-baking',
        paused: 'status-paused',
        completed: 'status-completed',
        error: 'status-error',
        disconnected: 'status-disconnected'
      };
      return classMap[status] || '';
    },
    
    async resumeProject(project) {
      console.log('[恢复项目] 准备恢复:', project);
      
      try {
        if (project.outputPath) {
          await this.loadLatestRenderedImage(project.outputPath);
        }
        const query = {
          resumeProjectId: project.projectId
        };
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
    
    // 计算进度
    getProgressPercent(project) {
      if (!project.currentIteration || !project.totalIterations) {
        return 0;
      }
      return Math.min(100, Math.round((project.currentIteration / project.totalIterations) * 100));
    },
    
    // 加载图像
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
          const imageUrl = result.imageBase64;
          
          console.log('[渲染图] 找到最新渲染图:', result.imagePath);
          console.log('[渲染图] Base64 图片大小:', (imageUrl.length / 1024).toFixed(2), 'KB');
          
          // 预加载图片
          const img = new Image();
          img.onload = () => {
            this.latestRenderedImage = imageUrl;
            this.renderedImagePath = result.imagePath;
            console.log('[渲染图] 图片加载成功');
          };
          img.onerror = (err) => {
            console.error('[渲染图] 图片加载失败:', err);
            this.latestRenderedImage = null;
          };
          img.src = imageUrl;
        } else {
          console.log('[渲染图] 未找到渲染图像');
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
  min-height: 32rem;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 1rem;
  flex-shrink: 0;
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
  flex: 1; 
  min-height: 20rem;
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
  flex-shrink: 0; 
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

.status-baking {
  background-color: #ffedd5;
  color: #9a3412;
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
</style>