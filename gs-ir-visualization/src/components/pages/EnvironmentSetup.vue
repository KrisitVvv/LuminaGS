<template>
  <section class="env-setup-container">
    <div class="env-setup-content">
      <div class="info-panel">
        <h3 class="panel-title">Python 环境配置</h3>
        
        <div v-if="detectionStatus === 'detecting'" class="status-message">
          <span class="iconify loading-icon" data-icon="line-md:loading-loop"></span>
          <span>正在检测系统环境...</span>
        </div>
        
        <div v-else-if="detectionStatus === 'completed'" class="detection-result">
          <div class="result-item" :class="{ success: hasConda, error: !hasConda }">
            <span class="iconify" :data-icon="hasConda ? 'solar:check-circle-bold' : 'solar:close-circle-bold'"></span>
            <span>Conda: {{ hasConda ? '已检测到' : '未检测到' }}</span>
          </div>
          
          <div class="result-item" :class="{ success: hasPython, error: !hasPython }">
            <span class="iconify" :data-icon="hasConda ? 'solar:check-circle-bold' : 'solar:close-circle-bold'"></span>
            <span>Python: {{ hasPython ? '已检测到' : '未检测到' }}</span>
          </div>
          
          <div class="result-item" :class="{ success: envValid, error: !envValid }">
            <span class="iconify" :data-icon="envValid ? 'solar:check-circle-bold' : 'solar:close-circle-bold'"></span>
            <span>Python依赖环境：{{ envValid ? '就绪' : '需要安装' }}</span>
          </div>
        </div>
        
        <div v-if="envValid" class="success-message">
          <span class="iconify success-icon" data-icon="solar:check-circle-bold"></span>
          <div>
            <h4>环境已就绪！</h4>
            <p>您现在可以开始使用训练功能了</p>
          </div>
        </div>
        
        <div v-else class="setup-guide">
          <p class="guide-text">
            LuminaGS需要Python环境和特定的依赖包。我们将为您自动安装所有必需组件。
          </p>
          
          <div class="installation-steps">
            <div class="step">
              <span class="step-number">1</span>
              <span class="step-text">下载并安装 Anaconda（如果尚未安装）</span>
            </div>
            <div class="step">
              <span class="step-number">2</span>
              <span class="step-text">创建 conda 环境并安装依赖</span>
            </div>
            <div class="step">
              <span class="step-number">3</span>
              <span class="step-text">验证环境并完成设置</span>
            </div>
          </div>
          
          <div class="download-links">
            <a href="https://docs.conda.io/en/latest/miniconda.html" target="_blank" class="download-link">
              <span class="iconify" data-icon="solar:download-linear"></span>
              下载Anaconda
            </a>
          </div>
        </div>
      </div>
      
      <div class="action-panel">
        <div v-if="!envValid && hasConda && !isInstalling" class="install-section">
          <h4 class="section-title">一键安装环境</h4>
          <div class="install-options">
            <div class="option-card" :class="{ selected: installMode === 'auto' }" @click="installMode = 'auto'">
              <div class="option-header">
                <input type="radio" id="auto-install" value="auto" v-model="installMode" checked>
                <label for="auto-install">自动安装（推荐）</label>
              </div>
              <p class="option-desc">自动创建 conda 环境并安装所有依赖，无需手动操作，适合大多数用户</p>
            </div>
            
            <div class="option-card" :class="{ selected: installMode === 'manual' }" @click="installMode = 'manual'">
              <div class="option-header">
                <input type="radio" id="manual-install" value="manual" v-model="installMode">
                <label for="manual-install">手动安装</label>
              </div>
              <p class="option-desc">查看命令行指令，手动在终端执行安装，适合有经验的用户或自动安装失败时</p>
            </div>
          </div>
          
          <div v-if="installMode === 'manual'" class="manual-instructions">
            <div class="manual-header">
              <span class="iconify manual-icon" data-icon="solar:terminal-linear"></span>
              <h5 class="instruction-title">手动安装指南</h5>
            </div>
            
            <div class="steps-scroll-container">
              <div class="steps-content-wrapper">
                <div class="step-row">
                  <div class="step-num">1</div>
                  <div class="step-content">
                    <span class="step-text">打开终端（PowerShell 或 CMD）</span>
                  </div>
                </div>
                
                <div class="step-row">
                  <div class="step-num">2</div>
                  <div class="step-content">
                    <span class="step-label">进入项目目录：</span>
                    <code class="command-code">cd e:\GraduationProject\LuminaGS\GS-IR</code>
                  </div>
                </div>
                
                <div class="step-row">
                  <div class="step-num">3</div>
                  <div class="step-content">
                    <span class="step-label">执行安装命令：</span>
                    <code class="command-code">conda env create -f environment.yml</code>
                  </div>
                </div>
                
                <div class="step-row">
                  <div class="step-num">4</div>
                  <div class="step-content">
                    <span class="step-text">等待安装完成（约 10-30 分钟）</span>
                  </div>
                </div>
                
                <div class="step-row">
                  <div class="step-num">5</div>
                  <div class="step-content">
                    <span class="step-label">验证环境：</span>
                    <code class="command-code inline">conda activate gsir</code>
                  </div>
                </div>
                
                <div class="step-row success-row">
                  <div class="step-num success">✓</div>
                  <div class="step-content">
                    <span class="step-text success-text">重启应用即可使用</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
          
          <button 
            v-if="installMode !== 'manual'" 
            class="install-btn" 
            @click="startInstallation"
            :disabled="isInstalling"
          >
            <span v-if="!isInstalling" class="iconify" data-icon="solar:download-linear"></span>
            <span v-else class="iconify loading-icon" data-icon="line-md:loading-loop"></span>
            {{ isInstalling ? '安装中...' : '开始安装' }}
          </button>
          
          <button 
            v-if="isInstalling"
            class="stop-installation-btn"
            @click="stopInstallation"
          >
            <span class="iconify" data-icon="solar:stop-circle-bold"></span>
            停止安装并清理缓存
          </button>
        </div>
        <div v-if="isInstalling || installationProgress.length > 0" class="progress-section">
          <h4 class="section-title">安装进度</h4>
          <div v-if="currentStage" class="stage-indicator">
            <span class="iconify stage-icon" data-icon="line-md:loading-loop"></span>
            <span class="stage-text">{{ currentStage }}</span>
          </div>
          
          <div class="progress-bar-container">
            <div class="progress-bar">
              <div class="progress-fill" :style="{ width: installationProgressPercent + '%' }"></div>
            </div>
            <span class="progress-percent">{{ installationProgressPercent.toFixed(1) }}%</span>
          </div>
          
          <div class="progress-details">
            <div class="detail-item">
              <span class="detail-label">已用时间：</span>
              <span class="detail-value">{{ elapsedTime }}</span>
            </div>
            <div class="detail-item">
              <span class="detail-label">估计剩余：</span>
              <span class="detail-value">{{ estimatedRemaining }}</span>
            </div>
          </div>
          
          <div class="progress-log" ref="progressLog">
            <div v-for="(log, index) in installationProgress" :key="index" 
                 class="log-line" :class="log.type">
              <span class="log-icon iconify" 
                    :data-icon="getLogIcon(log.type)">
              </span>
              <span class="log-text">{{ log.message }}</span>
            </div>
          </div>
        </div>
        
        <div v-if="installationComplete" class="complete-section">
          <div class="complete-message">
            <span class="iconify complete-icon" data-icon="solar:check-circle-bold"></span>
            <h4>安装完成！</h4>
            <p>Python 环境已成功安装并配置</p>
          </div>
          
          <button class="continue-btn" @click="goToTrainPage">
            <span class="iconify" data-icon="solar:arrow-right-linear"></span>
            开始使用训练功能
          </button>
        </div>
        
        <div v-if="!hasConda" class="no-conda-warning">
          <div class="warning-box">
            <span class="iconify warning-icon" data-icon="solar:danger-triangle-bold"></span>
            <h4>未检测到 Conda</h4>
            <p>请先安装 Miniconda 或 Anaconda，然后重启应用</p>
            
            <div class="conda-install-guide">
              <h5>快速安装指南：</h5>
              <ol>
                <li>访问 <a href="https://docs.conda.io/en/latest/miniconda.html" target="_blank">Miniconda 下载页面</a></li>
                <li>下载 Windows 版本（64 位）</li>
                <li>运行安装程序</li>
                <li><strong>重要：</strong>勾选 "Add to PATH" 选项</li>
                <li>完成安装后重启本应用</li>
              </ol>
            </div>
            
            <button class="retry-btn" @click="redetect">
              <span class="iconify" data-icon="solar:refresh-linear"></span>
              重新检测
            </button>
          </div>
        </div>
      </div>
    </div>
    
    <div v-if="showQuitConfirm" class="modal-overlay">
      <div class="modal-dialog">
        <div class="modal-header">
          <span class="iconify warning-icon" data-icon="solar:danger-triangle-bold"></span>
          <h3>确认退出</h3>
        </div>
        
        <div class="modal-body">
          <p>检测到有以下进程正在运行：</p>
          <ul class="process-list">
            <li v-if="quitProcesses.hasTraining" class="process-item">
              <span class="iconify" data-icon="solar:play-circle-bold"></span>
              训练任务正在进行
            </li>
            <li v-if="quitProcesses.hasBaking" class="process-item">
              <span class="iconify" data-icon="solar:cookie-linear"></span>
              Baking 任务正在进行
            </li>
            <li v-if="quitProcesses.hasInstallation" class="process-item">
              <span class="iconify" data-icon="solar:download-linear"></span>
              环境安装正在进行
            </li>
          </ul>
          <p class="warning-text">
            ⚠️ 退出将会停止这些进程，可能导致数据丢失或安装失败！
          </p>
        </div>
        
        <div class="modal-footer">
          <button class="btn-cancel" @click="handleQuitChoice('cancel')">
            取消
          </button>
          <button class="btn-quit" @click="handleQuitChoice('quit')">
            <span class="iconify" data-icon="solar:logout-linear"></span>
            确认退出
          </button>
        </div>
      </div>
    </div>
  </section>
</template>

<script>
export default {
  name: 'EnvironmentSetup',
  data() {
    return {
      detectionStatus: 'detecting', // detecting, completed
      hasConda: false,
      hasPython: false,
      envValid: false,
      installMode: 'auto', // auto, manual
      isInstalling: false,
      installationProgress: [],
      installationProgressPercent: 0,
      installationComplete: false,
      showQuitConfirm: false,
      quitProcesses: { hasTraining: false, hasBaking: false, hasInstallation: false },
      currentStage: '',
      startTime: null,
      elapsedTime: '00:00',
      estimatedRemaining: '计算中...'
    }
  },
  mounted() {
    this.detectEnvironment();
    this.setupListeners();
    this.setupQuitListener();
    this.setupEnvironmentNeededListener();
  },
  methods: {
    async detectEnvironment() {
      this.detectionStatus = 'detecting';
      
      try {
        const result = await window.electronAPI?.detectPythonConda();
        
        if (result?.success) {
          this.hasConda = !!result.conda;
          this.hasPython = !!result.python;
          
          console.log('===== 环境检测结果 =====');
          console.log('hasConda:', this.hasConda);
          console.log('hasPython:', this.hasPython);
          console.log('condaPath:', result.conda);
          console.log('pythonPath:', result.python);
          
          const envCheck = await window.electronAPI?.checkEnvironment();
          this.envValid = envCheck?.success && envCheck?.valid;
          
          console.log('envValid:', this.envValid);
          console.log('========================');
          
          if (!this.hasConda) {
            console.warn('未检测到 Conda！');
            alert('⚠️ 未检测到 Conda！\n\n请先安装 Miniconda 或 Anaconda，然后重启应用。\n\n下载地址：https://docs.conda.io/en/latest/miniconda.html');
          }
        } else {
          console.error('环境检测失败:', result);
        }
      } catch (error) {
        console.error('环境检测异常:', error);
      } finally {
        this.detectionStatus = 'completed';
      }
    },
    
    setupListeners() {
      console.log('===== 设置进度监听器 =====');
      window.electronAPI?.onEnvironmentProgress((data) => {
        console.log('收到进度更新:', data);
        
        this.installationProgress.push({
          type: data.type,
          message: data.data.trim()
        });
        if (data.type === 'stdout') {
          const output = data.data;
          const downloadPatterns = [
            /Downloading\s+.*?\s+(\d+)K/i,
            /\[(\d+)%\]/,
            /Progress:\s*(\d+)%/i,
            /Completed:\s*(\d+)%/i
          ];
          
          for (const pattern of downloadPatterns) {
            const match = output.match(pattern);
            if (match) {
              const progress = parseInt(match[1]);
              const estimatedPercent = Math.min(Math.floor(progress / 3096), 90);
              if (estimatedPercent > this.installationProgressPercent) {
                this.installationProgressPercent = estimatedPercent;
              }
              break;
            }
          }
          
          // 解析提取进度
          const extractMatch = output.match(/Extracting:\s+(\d+)%/i);
          if (extractMatch) {
            const progress = parseInt(extractMatch[1]);
            this.installationProgressPercent = Math.min(60 + Math.floor(progress * 0.3), 95);
          }
          
          // 检测关键阶段并更新当前阶段提示
          if (output.includes('Solving environment')) {
            this.currentStage = '正在解决环境依赖...';
            this.installationProgressPercent = 10;
          } else if (output.includes('Preparing transaction')) {
            this.currentStage = '正在准备事务...';
            this.installationProgressPercent = Math.max(this.installationProgressPercent, 15);
          } else if (output.includes('Verifying transaction')) {
            this.currentStage = '正在验证事务...';
            this.installationProgressPercent = Math.max(this.installationProgressPercent, 25);
          } else if (output.includes('Downloading and Extracting Packages')) {
            this.currentStage = '正在下载并提取包...';
            this.installationProgressPercent = Math.max(this.installationProgressPercent, 30);
          } else if (output.includes('Installing dependencies')) {
            this.currentStage = '正在安装包...';
            this.installationProgressPercent = Math.max(this.installationProgressPercent, 70);
          } else if (output.includes('Linking packages')) {
            this.currentStage = '正在链接包...';
            this.installationProgressPercent = Math.max(this.installationProgressPercent, 80);
          } else if (output.includes('done') || output.includes('complete') || output.includes('finished')) {
            this.currentStage = '即将完成...';
            this.installationProgressPercent = Math.max(this.installationProgressPercent, 95);
          }
          
          // 平滑增加进度
          if (this.installationProgressPercent < 95 && !output.includes('%')) {
            this.installationProgressPercent = Math.min(
              this.installationProgressPercent + 0.3,
              95
            );
          }
        } else if (data.type === 'info') {
          // info 类型的消息也显示进度
          if (data.data.includes('开始')) {
            this.currentStage = '正在初始化...';
            this.installationProgressPercent = 5;
          } else if (data.data.includes('创建 conda 环境')) {
            this.currentStage = '正在创建环境...';
            this.installationProgressPercent = 10;
          } else if (data.data.includes('当前进度')) {
            // 从 info 消息中提取进度百分比
            const percentMatch = data.data.match(/(\d+)%/);
            if (percentMatch) {
              const progress = parseInt(percentMatch[1]);
              if (progress > this.installationProgressPercent) {
                this.installationProgressPercent = progress;
              }
            }
          } else if (data.data.includes('正在')) {
            // 更新阶段提示
            this.currentStage = data.data.replace('当前进度：', '').replace(/\d+%/, '').trim();
          }
        } else if (data.type === 'stderr') {
          // 错误输出也显示在进度中
          if (data.data.includes('ERROR') || data.data.includes('failed')) {
            this.currentStage = '遇到错误，请检查日志...';
            // 保持当前进度或略微降低
            this.installationProgressPercent = Math.max(this.installationProgressPercent - 5, 0);
          }
        }
        this.$nextTick(() => {
          const logContainer = this.$refs.progressLog;
          if (logContainer) {
            logContainer.scrollTop = logContainer.scrollHeight;
          }
        });
      });
    },
    
    setupQuitListener() {
      window.electronAPI?.onConfirmQuit((data) => {
        this.quitProcesses = data;
        this.showQuitConfirm = true;
      });
    },
    
    setupEnvironmentNeededListener() {
      window.electronAPI?.onEnvironmentNeeded((data) => {
        console.log('收到环境安装需求:', data);
        this.hasConda = data.hasConda || false;
        this.hasPython = data.hasPython || false;
        this.envValid = false;
        this.detectionStatus = 'completed';
        if (this.$route.path !== '/environment') {
          this.$router.push('/environment');
        }
      });
    },
    
    async startInstallation() {
      if (this.isInstalling) return;
      
      console.log('===== 开始点击安装 =====');
      console.log('当前 hasConda:', this.hasConda);
      console.log('当前 envValid:', this.envValid);

      if (!this.hasConda) {
        console.error('未检测到 Conda，无法安装');
        alert('未检测到 Conda，请先安装 Miniconda 或 Anaconda');
        return;
      }
      
      this.isInstalling = true;
      this.installationProgress = [];
      this.installationProgressPercent = 0;
      this.currentStage = '正在初始化...';
      this.startTime = new Date();
      this.elapsedTime = '00:00';
      this.estimatedRemaining = '计算中...';
      this.startTimer();
      
      try {
        console.log('开始安装环境...');
        console.log('当前状态:', {
          isInstalling: this.isInstalling,
          progressLength: this.installationProgress.length,
          progressPercent: this.installationProgressPercent
        });
        
        const scriptPath = '../../../GS-IR/install_environment.bat';
        
        console.log('调用 runInstallScript API, 参数:', { scriptPath, mode: this.installMode });
        
        // 检查 electronAPI
        if (!window.electronAPI) {
          throw new Error('electronAPI 不可用，请检查 preload.js 配置');
        }
        
        if (!window.electronAPI.runInstallScript) {
          throw new Error('runInstallScript API 不存在');
        }
        
        const result = await window.electronAPI.runInstallScript({
          scriptPath,
          mode: this.installMode // 'auto' 或 'manual'
        });
        
        console.log('安装结果:', result);
        console.log('安装后状态:', {
          isInstalling: this.isInstalling,
          progressLength: this.installationProgress.length,
          progressPercent: this.installationProgressPercent
        });
        
        if (result?.success) {
          this.installationComplete = true;
          this.envValid = true;
          this.installationProgressPercent = 100;
          this.currentStage = '安装完成！';
          this.stopTimer();
        } else {
          const errorMsg = result?.error || '安装失败';
          console.error('安装失败:', errorMsg);
          this.installationProgress.push({
            type: 'error',
            message: `安装失败：${errorMsg}`
          });
          this.currentStage = '安装失败';
          this.stopTimer();
          throw new Error(errorMsg);
        }
      } catch (error) {
        console.error('安装异常:', error);
        this.installationProgress.push({
          type: 'error',
          message: `安装失败：${error.message}`
        });
        this.currentStage = '安装失败';
        this.stopTimer();
      } finally {
        this.isInstalling = false;
      }
    },
    
    async stopInstallation() {
      try {
        const result = await window.electronAPI?.stopInstallation();
        if (result?.success) {
          this.installationProgress.push({
            type: 'warning',
            message: '已停止安装并清理缓存'
          });
          this.isInstalling = false;
        }
      } catch (error) {
        console.error('停止安装失败:', error);
      }
    },
    
    handleQuitChoice(choice) {
      // choice: 'quit' 或 'cancel'
      window.electronAPI?.confirmQuitApp(choice);
      this.showQuitConfirm = false;
    },
    
    redetect() {
      this.detectEnvironment();
    },
    
    goToTrainPage() {
      this.$router.push('/train');
    },
    
    testDebug() {
      console.log('===== 调试模式测试 =====');
      console.log('1. window.electronAPI:', window.electronAPI ? '存在' : '不存在');
      console.log('2. window.electronAPI.createEnvironment:', window.electronAPI?.createEnvironment ? '存在' : '不存在');
      console.log('3. hasConda:', this.hasConda);
      console.log('4. envValid:', this.envValid);
      console.log('5. installMode:', this.installMode);
      console.log('6. isInstalling:', this.isInstalling);
      
      if (!this.hasConda) {
        alert('问题：hasConda 为 false\n\n原因：未检测到 Conda\n\n解决方案：请先安装 Miniconda');
      } else if (!window.electronAPI) {
        alert('问题：electronAPI 不存在\n\n原因：preload.js 未正确加载');
      } else if (!window.electronAPI.createEnvironment) {
        alert('问题：createEnvironment API 不存在\n\n原因：IPC 处理器未注册');
      } else {
        alert('所有检查通过！\n\nh asConda: true\nelectronAPI: 存在\n可以尝试点击“开始安装”按钮');
      }
    },
    
    startTimer() {
      this.stopTimer();
      this.timerInterval = setInterval(() => {
        if (this.startTime) {
          const now = new Date();
          const diff = Math.floor((now - this.startTime) / 1000);
          
          const minutes = Math.floor(diff / 60);
          const seconds = diff % 60;
          this.elapsedTime = `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
          
          // 估算剩余时间
          if (this.installationProgressPercent > 5 && this.installationProgressPercent < 95) {
            const elapsedSeconds = diff;
            const percentPerSecond = this.installationProgressPercent / elapsedSeconds;
            const remainingPercent = 100 - this.installationProgressPercent;
            const remainingSeconds = Math.floor(remainingPercent / percentPerSecond);
            
            if (remainingSeconds > 0) {
              const remMinutes = Math.floor(remainingSeconds / 60);
              const remSeconds = remainingSeconds % 60;
              this.estimatedRemaining = `${remMinutes}分${remSeconds}秒`;
            } else {
              this.estimatedRemaining = '即将完成...';
            }
          } else if (this.installationProgressPercent >= 95) {
            this.estimatedRemaining = '即将完成...';
          }
        }
      }, 1000);
    },
    
    stopTimer() {
      if (this.timerInterval) {
        clearInterval(this.timerInterval);
        this.timerInterval = null;
      }
    },
    
    getLogIcon(type) {
      const icons = {
        'stdout': 'solar:information-circle-bold',
        'stderr': 'solar:danger-circle-bold',
        'error': 'solar:close-circle-bold',
        'info': 'solar:check-circle-bold',
        'warning': 'solar:alert-triangle-bold'
      };
      return icons[type] || 'solar:information-circle-bold';
    }
  },
  beforeUnmount() {
    this.stopTimer();
  }
}
</script>

<style scoped>
.env-setup-container {
  height: 100%;
  background-color: #f8fafc;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 2rem;
}

.env-setup-content {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 2rem;
  max-width: 1200px;
  width: 100%;
}

.info-panel,
.action-panel {
  background: white;
  border-radius: 1rem;
  padding: 2rem;
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
}

.panel-title {
  font-size: 1.5rem;
  font-weight: bold;
  color: #1e293b;
  margin-bottom: 2rem;
}

.status-message {
  display: flex;
  align-items: center;
  gap: 1rem;
  color: #64748b;
  font-size: 1rem;
}

.loading-icon {
  font-size: 1.5rem;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.detection-result {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.result-item {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.75rem;
  border-radius: 0.5rem;
  font-size: 0.938rem;
}

.result-item.success {
  background-color: #dcfce7;
  color: #166534;
}

.result-item.error {
  background-color: #fee2e2;
  color: #991b1b;
}

.iconify {
  font-size: 1.25rem;
}

.success-message {
  display: flex;
  align-items: center;
  gap: 1.5rem;
  padding: 2rem;
  background-color: #dcfce7;
  border-radius: 1rem;
  margin-top: 2rem;
}

.success-icon {
  font-size: 3rem;
  color: #16a34a;
}

.success-message h4 {
  font-size: 1.25rem;
  color: #166534;
  margin: 0 0 0.25rem 0;
}

.success-message p {
  color: #15803d;
  margin: 0;
}

.setup-guide h4 {
  font-size: 1.125rem;
  color: #1e293b;
  margin-bottom: 1rem;
}

.guide-text {
  color: #475569;
  line-height: 1.6;
  margin-bottom: 1.5rem;
}

.installation-steps {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  margin-bottom: 1.5rem;
}

.step {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.step-number {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 2rem;
  height: 2rem;
  background-color: #7e22ce;
  color: white;
  border-radius: 50%;
  font-weight: bold;
  font-size: 0.875rem;
}

.step-text {
  color: #475569;
  font-size: 0.938rem;
}

.download-links {
  margin-top: 1rem;
}

.download-link {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  color: #7e22ce;
  text-decoration: none;
  font-weight: 500;
  padding: 0.5rem 1rem;
  border: 1px solid #e2e8f0;
  border-radius: 0.5rem;
  transition: all 0.2s;
}

.download-link:hover {
  background-color: #f3e8ff;
  border-color: #d8b4fe;
}

.section-title {
  font-size: 1.125rem;
  font-weight: bold;
  color: #1e293b;
  margin-bottom: 1.5rem;
}

.install-options {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  margin-bottom: 1.5rem;
}

.option-card {
  border: 2px solid #e2e8f0;
  border-radius: 0.75rem;
  padding: 1rem;
  cursor: pointer;
  transition: all 0.2s;
}

.option-card:hover {
  border-color: #d8b4fe;
  background-color: #faf5ff;
}

.option-card.selected {
  border-color: #7e22ce;
  background-color: #f3e8ff;
  box-shadow: 0 0 0 3px rgba(126, 34, 204, 0.1);
}

.option-header {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-bottom: 0.5rem;
}

.option-header input[type="radio"] {
  width: 1.25rem;
  height: 1.25rem;
  cursor: pointer;
}

.option-header label {
  font-weight: 600;
  color: #1e293b;
  cursor: pointer;
}

.option-desc {
  color: #64748b;
  font-size: 0.875rem;
  margin: 0;
}

.install-btn {
  width: 100%;
  background-color: #7e22ce;
  color: white;
  padding: 1rem;
  border-radius: 0.75rem;
  font-weight: 600;
  font-size: 1rem;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.75rem;
  border: none;
  cursor: pointer;
  transition: all 0.2s;
}

.install-btn:hover:not(:disabled) {
  background-color: #6b21a8;
}

.install-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.progress-section {
  margin-top: 2rem;
}

.stage-indicator {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 1rem;
  background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%);
  border-radius: 0.75rem;
  margin-bottom: 1rem;
  border: 1px solid #bae6fd;
}

.stage-icon {
  font-size: 1.25rem;
  color: #0284c7;
  animation: spin 1.5s linear infinite;
}

.stage-text {
  font-size: 0.938rem;
  font-weight: 600;
  color: #0c4a6e;
}

.progress-bar-container {
  display: flex;
  align-items: center;
  gap: 1rem;
  margin-bottom: 1rem;
}

.progress-bar {
  flex: 1;
  height: 1rem;
  background-color: #e2e8f0;
  border-radius: 9999px;
  overflow: hidden;
  box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.1);
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #7e22ce, #a855f7, #c084fc);
  background-size: 200% 100%;
  transition: width 0.3s ease;
  animation: shimmer 2s linear infinite;
  box-shadow: 0 0 10px rgba(168, 85, 247, 0.5);
}

@keyframes shimmer {
  0% {
    background-position: 200% 0;
  }
  100% {
    background-position: -200% 0;
  }
}

.progress-percent {
  font-weight: 700;
  color: #1e293b;
  min-width: 4rem;
  text-align: right;
  font-size: 1rem;
  font-family: 'Courier New', monospace;
}

.progress-details {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.75rem;
  margin-bottom: 1rem;
  padding: 0.75rem;
  background-color: #f8fafc;
  border-radius: 0.5rem;
}

.detail-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.detail-label {
  color: #64748b;
  font-size: 0.875rem;
  font-weight: 500;
}

.detail-value {
  color: #1e293b;
  font-size: 0.875rem;
  font-weight: 600;
  font-family: 'Courier New', monospace;
}

.progress-log {
  max-height: 20rem;
  overflow-y: auto;
  background-color: #1e293b;
  border-radius: 0.5rem;
  padding: 0.75rem;
  font-family: 'Courier New', monospace;
  font-size: 0.75rem;
  color: #e2e8f0;
  box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.2);
  border: 1px solid #334155;
}

.log-line {
  display: flex;
  align-items: flex-start;
  gap: 0.5rem;
  margin-bottom: 0.25rem;
  padding: 0.25rem;
  line-height: 1.4;
}

.log-line.error {
  color: #fca5a5;
  background-color: rgba(239, 68, 68, 0.1);
  border-left: 3px solid #ef4444;
  padding-left: 0.5rem;
}

.log-line.info {
  color: #86efac;
  background-color: rgba(34, 197, 94, 0.1);
  border-left: 3px solid #22c55e;
  padding-left: 0.5rem;
}

.log-line.warning {
  color: #fcd34d;
  background-color: rgba(245, 158, 11, 0.1);
  border-left: 3px solid #f59e0b;
  padding-left: 0.5rem;
}

.log-line.stdout {
  color: #93c5fd;
  border-left: 3px solid #3b82f6;
  padding-left: 0.5rem;
}

.log-icon {
  font-size: 1rem;
  flex-shrink: 0;
  margin-top: 0.125rem;
}

.log-text {
  flex: 1;
  word-break: break-all;
  white-space: pre-wrap;
}

.complete-section {
  margin-top: 2rem;
  text-align: center;
}

.complete-message {
  padding: 2rem;
  background-color: #dcfce7;
  border-radius: 1rem;
  margin-bottom: 1.5rem;
}

.complete-icon {
  font-size: 4rem;
  color: #16a34a;
  display: block;
  margin-bottom: 1rem;
}

.complete-message h4 {
  font-size: 1.5rem;
  color: #166534;
  margin: 0 0 0.5rem 0;
}

.complete-message p {
  color: #15803d;
  margin: 0;
}

.continue-btn {
  width: 100%;
  background-color: #059669;
  color: white;
  padding: 1rem;
  border-radius: 0.75rem;
  font-weight: 600;
  font-size: 1rem;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.75rem;
  border: none;
  cursor: pointer;
  transition: all 0.2s;
}

.continue-btn:hover {
  background-color: #047857;
}

.no-conda-warning {
  margin-top: 2rem;
}

.warning-box {
  padding: 1.5rem;
  background-color: #fef3c7;
  border-left: 4px solid #f59e0b;
  border-radius: 0.5rem;
}

.warning-box h4 {
  color: #92400e;
  margin: 0 0 0.5rem 0;
  font-size: 1.125rem;
}

.warning-box p {
  color: #78350f;
  margin: 0 0 1rem 0;
}

.warning-icon {
  font-size: 2rem;
  color: #f59e0b;
  display: block;
  margin-bottom: 0.5rem;
}

.retry-btn {
  background-color: #f59e0b;
  color: white;
  padding: 0.5rem 1rem;
  border-radius: 0.5rem;
  border: none;
  font-weight: 500;
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  cursor: pointer;
  transition: all 0.2s;
}

.retry-btn:hover {
  background-color: #d97706;
}

.conda-install-guide {
  background: white;
  padding: 1rem;
  border-radius: 0.5rem;
  margin: 1rem 0;
  border: 1px solid #fcd34d;
}

.conda-install-guide h5 {
  color: #92400e;
  margin: 0 0 0.75rem 0;
  font-size: 1rem;
  font-weight: 600;
}

.conda-install-guide ol {
  margin: 0;
  padding-left: 1.5rem;
  color: #78350f;
  line-height: 1.8;
}

.conda-install-guide li {
  margin-bottom: 0.5rem;
}

.conda-install-guide a {
  color: #7e22ce;
  text-decoration: none;
  font-weight: 500;
}

.conda-install-guide a:hover {
  text-decoration: underline;
}

.conda-install-guide strong {
  color: #dc2626;
  font-weight: 600;
}

.manual-instructions {
  margin-top: 1.5rem;
  background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
  border-radius: 0.75rem;
  border: 1px solid #e2e8f0;
  overflow: hidden;
}

.manual-header {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 1rem 1.25rem;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
}

.manual-icon {
  font-size: 1.25rem;
}

.instruction-title {
  font-size: 1rem;
  font-weight: 600;
  margin: 0;
}

.steps-scroll-container {
  max-height: 320px;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 0 1.25rem;
  scrollbar-width: thin;
  scrollbar-color: #cbd5e1 transparent;
}

.steps-scroll-container::-webkit-scrollbar {
  width: 8px;
}

.steps-scroll-container::-webkit-scrollbar-track {
  background: transparent;
  margin: 0.5rem 0;
  border-radius: 4px;
}

.steps-scroll-container::-webkit-scrollbar-thumb {
  background: linear-gradient(180deg, #cbd5e1 0%, #94a3b8 100%);
  border-radius: 4px;
  transition: background 0.2s;
}

.steps-scroll-container::-webkit-scrollbar-thumb:hover {
  background: linear-gradient(180deg, #94a3b8 0%, #64748b 100%);
}

.steps-content-wrapper {
  padding: 1.25rem 0;
}

.step-row {
  display: flex;
  align-items: flex-start;
  gap: 1rem;
  margin-bottom: 1rem;
}

.step-row:last-child {
  margin-bottom: 0;
}

.step-num {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 2rem;
  height: 2rem;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border-radius: 50%;
  font-weight: bold;
  font-size: 0.875rem;
}

.step-num.success {
  background: linear-gradient(135deg, #10b981 0%, #059669 100%);
}

.step-content {
  flex: 1;
  min-width: 0;
}

.step-text {
  color: #475569;
  font-size: 0.938rem;
  line-height: 1.5;
}

.step-label {
  display: block;
  color: #64748b;
  font-size: 0.875rem;
  margin-bottom: 0.375rem;
}

.command-code {
  display: block;
  background-color: #1e293b;
  color: #e2e8f0;
  padding: 0.625rem 0.875rem;
  border-radius: 0.5rem;
  font-family: 'Courier New', monospace;
  font-size: 0.875rem;
  border-left: 3px solid #667eea;
  word-break: break-all;
}

.command-code.inline {
  display: inline-block;
  padding: 0.25rem 0.5rem;
  margin-left: 0.5rem;
}

.success-row .step-text {
  color: #16a34a;
  font-weight: 600;
}

.success-text {
  color: #16a34a;
  font-weight: 600;
}

.info-box {
  display: flex;
  gap: 0.75rem;
  padding: 1rem;
  margin-top: 1rem;
  background-color: #eff6ff;
  border-radius: 0.5rem;
  border: 1px solid #bfdbfe;
}

.info-icon {
  flex-shrink: 0;
}

.info-icon .iconify {
  font-size: 1.25rem;
  color: #3b82f6;
}

.info-content {
  flex: 1;
  color: #1e40af;
  font-size: 0.875rem;
  line-height: 1.6;
}

.info-content strong {
  display: block;
  margin-bottom: 0.25rem;
  color: #1e3a8a;
}

.info-list {
  margin: 0;
  padding-left: 1.25rem;
}

.info-list li {
  margin-bottom: 0.25rem;
  color: #3b82f6;
}

.stop-installation-btn {
  width: 100%;
  margin-top: 0.75rem;
  background-color: #fee2e2;
  color: #991b1b;
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
}

.stop-installation-btn:hover {
  background-color: #fecaca;
}

.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
}

.modal-dialog {
  background: white;
  border-radius: 1rem;
  max-width: 500px;
  width: 90%;
  box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1);
  animation: slideIn 0.3s ease-out;
}

@keyframes slideIn {
  from {
    opacity: 0;
    transform: translateY(-20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.modal-header {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 1.5rem;
  border-bottom: 1px solid #e2e8f0;
}

.warning-icon {
  font-size: 2rem;
  color: #f59e0b;
}

.modal-header h3 {
  font-size: 1.25rem;
  font-weight: bold;
  color: #1e293b;
  margin: 0;
}

.modal-body {
  padding: 1.5rem;
}

.modal-body p {
  color: #475569;
  margin: 0 0 1rem 0;
}

.process-list {
  list-style: none;
  padding: 0;
  margin: 0 0 1rem 0;
}

.process-item {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.75rem;
  background-color: #f8fafc;
  border-radius: 0.5rem;
  margin-bottom: 0.5rem;
  color: #334155;
}

.process-item .iconify {
  color: #7e22ce;
}

.warning-text {
  background-color: #fef3c7;
  padding: 1rem;
  border-left: 4px solid #f59e0b;
  border-radius: 0.5rem;
  color: #92400e;
  font-weight: 500;
}

.modal-footer {
  display: flex;
  gap: 1rem;
  padding: 1.5rem;
  border-top: 1px solid #e2e8f0;
}

.btn-cancel,
.btn-quit {
  flex: 1;
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
}

.btn-cancel {
  background-color: #f1f5f9;
  color: #475569;
}

.btn-cancel:hover {
  background-color: #e2e8f0;
}

.btn-quit {
  background-color: #ef4444;
  color: white;
}

.btn-quit:hover {
  background-color: #dc2626;
}
</style>
