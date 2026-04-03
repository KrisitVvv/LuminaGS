const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  // 系统信息相关 API
  getPlatform: () => ipcRenderer.invoke('get-platform'),
  // ✅ 新增：将本地文件路径转换为可访问的 URL
  convertFilePath: (filePath) => ipcRenderer.invoke('convert-file-path', filePath),
  minimizeWindow: () => ipcRenderer.invoke('minimize-window'),
  maximizeWindow: () => ipcRenderer.invoke('maximize-window'),
  restoreWindow: () => ipcRenderer.invoke('restore-window'),
  closeWindow: () => ipcRenderer.invoke('close-window'),
  // ✅ 新增：打开 Editor 专用窗口
  openEditorWindow: (config) => ipcRenderer.invoke('open-editor-window', config),
  // 添加窗口移动相关 API
  startDragging: () => ipcRenderer.invoke('start-dragging'),
  // GPU 监控相关 API
  getGpuInfo: () => ipcRenderer.invoke('get-gpu-info'),
  getGpuUsage: () => ipcRenderer.invoke('get-gpu-usage'),
  // 新增：获取所有 GPU 设备
  getAllGpus: () => ipcRenderer.invoke('get-all-gpus'),
  // 新增：设置选中 GPU 索引
  setSelectedGpuIndex: (index) => ipcRenderer.invoke('set-selected-gpu-index', index),
  // Python 环境管理相关 API
  detectPythonConda: () => ipcRenderer.invoke('detect-python-conda'),
  checkEnvironment: () => ipcRenderer.invoke('check-environment'),
  createEnvironment: (config) => ipcRenderer.invoke('create-environment', config),
  runInstallScript: (config) => ipcRenderer.invoke('run-install-script', config),
  getEnvironmentInfo: () => ipcRenderer.invoke('get-environment-info'),
  // 监听环境事件
  onEnvironmentNeeded: (callback) => {
    ipcRenderer.on('environment-needed', (event, data) => callback(data));
  },
  onEnvironmentProgress: (callback) => {
    ipcRenderer.on('environment-progress', (event, data) => callback(data));
  },
  // 监听退出确认
  onConfirmQuit: (callback) => {
    ipcRenderer.on('confirm-quit', (event, data) => callback(data));
  },
  // 训练相关 API
  startTraining: (config) => ipcRenderer.invoke('start-training', config),
  startBaking: (config) => ipcRenderer.invoke('start-baking', config),
  stopTraining: () => ipcRenderer.invoke('stop-training'),
  stopBaking: () => ipcRenderer.invoke('stop-baking'),
  stopInstallation: () => ipcRenderer.invoke('stop-installation'),
  confirmQuitApp: (choice) => ipcRenderer.invoke('confirm-quit-app', choice),
  // 文件和目录选择
  selectDirectory: () => ipcRenderer.invoke('select-directory'),
  selectFile: (options) => ipcRenderer.invoke('select-file', options),
  // ✅ 新增：检查文件夹是否为空
  checkFolderEmpty: (folderPath) => ipcRenderer.invoke('check-folder-empty', folderPath),
  // ✅ 新增：检查文件是否存在
  checkFileExists: (filePath) => ipcRenderer.invoke('check-file-exists', filePath),
  // 数据集管理
  checkDatasetFormat: (sourcePath) => ipcRenderer.invoke('check-dataset-format', sourcePath),
  convertDataset: (config) => ipcRenderer.invoke('convert-dataset', config),
  stopConversion: () => ipcRenderer.invoke('stop-conversion'),
  // 监听转换输出
  onConversionOutput: (callback) => {
    ipcRenderer.on('conversion-output', (event, data) => callback(data));
  },
  onConversionClose: (callback) => {
    ipcRenderer.on('conversion-close', (event, data) => callback(data));
  },
  // 获取最新渲染图像
  getLatestRenderedImage: (modelPath) => ipcRenderer.invoke('get-latest-rendered-image', modelPath),
  // 监听训练和烘焙输出
  onTrainingOutput: (callback) => {
    ipcRenderer.on('training-output', (event, data) => callback(data));
  },
  onBakingOutput: (callback) => {
    ipcRenderer.on('baking-output', (event, data) => callback(data));
  },
  // 项目管理相关 API
  getProjectList: () => ipcRenderer.invoke('get-project-list'),
  getProjectDetail: (projectId) => ipcRenderer.invoke('get-project-detail', projectId),
  getQueueStatus: () => ipcRenderer.invoke('get-queue-status'),
  onTrainingQueueUpdate: (callback) => {
    ipcRenderer.on('training-queue-update', (event, data) => callback(data));
  },
  // 更新项目配置（实时自动保存）
  updateProjectConfig: (projectId, config) => ipcRenderer.invoke('update-project-config', { projectId, config }),
  // 更新项目阶段
  updateProjectStage: (projectId, stage) => ipcRenderer.invoke('update-project-stage', { projectId, stage }),
  // 同步 sourcePath 字段到 projects.json
  syncSourcePathToProjects: () => ipcRenderer.invoke('sync-source-path-to-projects'),
  // ✅ 新增：检查训练是否完成
  checkTrainingCompletion: (projectId) => ipcRenderer.invoke('check-training-completion', projectId),
  // 监听训练完成事件
  onTrainingCompleted: (callback) => {
    ipcRenderer.on('training-completed', (event, data) => callback(data));
  },
  // ✅ 新增：获取项目配置
  getProjectConfig: (projectId) => ipcRenderer.invoke('get-project-config', projectId),
  // 删除项目输出目录
  deleteOutputDirectory: (outputPath) => ipcRenderer.invoke('delete-output-directory', outputPath),
  // 删除项目及其输出
  deleteProjectAndOutput: (projectId, outputPath) => ipcRenderer.invoke('delete-project-and-output', { projectId, outputPath }),
  // 保存训练完成的项目到项目列表
  saveToProjectsList: (data) => ipcRenderer.invoke('save-to-projects-list', data),
  // 启动 Python 脚本（使用 conda 环境）
  spawnPythonProcess: (config) => ipcRenderer.invoke('spawn-python-process', config),
  // 启动 Python 服务（带 conda 环境）
  startPythonService: (config) => ipcRenderer.invoke('start-python-service', config),
  // 停止 Python 服务
  stopPythonService: () => ipcRenderer.invoke('stop-python-service')
});

// 监听窗口状态变化
ipcRenderer.on('window-maximized', () => {
  window.dispatchEvent(new CustomEvent('window-maximized'));
});

ipcRenderer.on('window-restored', () => {
  window.dispatchEvent(new CustomEvent('window-restored'));
});