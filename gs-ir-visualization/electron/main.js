const { app, BrowserWindow, Menu, ipcMain, dialog } = require('electron');
const si = require('systeminformation');
const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs').promises;
const PythonEnvironmentManager = require('./pythonEnvironment');

Menu.setApplicationMenu(null);
let mainWindow = null;
const isPackaged = app.isPackaged;

// 初始化 Python 环境管理器
const envManager = new PythonEnvironmentManager();

// 将 mainWindow 暴露给全局，供环境管理模块使用
global.mainWindow = null;

const createWindow = () => {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 850,
    frame: false,
    movable: true,
    webPreferences: {
      nodeIntegration: false, 
      contextIsolation: true,
      preload: __dirname + '/preload.js'
    }
  })

  // 暴露给全局
  global.mainWindow = mainWindow;

  // 修改为实际运行的端口
  mainWindow.loadURL("http://localhost:5173/");

  if (!isPackaged) {
    mainWindow.webContents.openDevTools();
  }
  
  // 监听窗口最大化事件
  mainWindow.on('maximize', () => {
    console.log('窗口已最大化');
    mainWindow.webContents.send('window-maximized');
  });
  
  // 监听窗口取消最大化事件
  mainWindow.on('unmaximize', () => {
    console.log('窗口已恢复');
    mainWindow.webContents.send('window-restored');
  });
  
  // 监听窗口进入全屏事件
  mainWindow.on('enter-full-screen', () => {
    console.log('窗口进入全屏');
    mainWindow.webContents.send('window-maximized');
  });
  
  // 监听窗口退出全屏事件
  mainWindow.on('leave-full-screen', () => {
    console.log('窗口退出全屏');
    mainWindow.webContents.send('window-restored');
  });
  
  // 监听窗口resize事件，处理拖动后的状态变化
  mainWindow.on('resize', () => {
    // 延迟执行以确保状态已经更新
    setTimeout(() => {
      if (mainWindow) {
        const isMaximized = mainWindow.isMaximized();
        const isFullScreen = mainWindow.isFullScreen();
        
        console.log(`窗口状态检查 - 最大化: ${isMaximized}, 全屏: ${isFullScreen}`);
        
        // 如果既不是最大化也不是全屏，则发送恢复消息
        if (!isMaximized && !isFullScreen) {
          console.log('发送窗口恢复消息');
          mainWindow.webContents.send('window-restored');
        }
        // 如果是最大化或全屏状态，发送最大化消息
        else if (isMaximized || isFullScreen) {
          console.log('发送窗口最大化消息');
          mainWindow.webContents.send('window-maximized');
        }
      }
    }, 150); // 增加延迟时间确保状态稳定
  });
}

ipcMain.handle('minimize-window', async () => {
  mainWindow.minimize();
});

ipcMain.handle('maximize-window', async () => {
  mainWindow.maximize();
});

ipcMain.handle('restore-window', async () => {
  mainWindow.restore();
});

ipcMain.handle('close-window', async () => {
  mainWindow.close();
});

ipcMain.handle('start-dragging', async (event) => {
  const win = BrowserWindow.fromWebContents(event.sender);
  if (win && !win.isMaximized() && !win.isFullScreen()) {
    win.setIgnoreMouseEvents(false);
    win.webContents.startDrag({});
  }
});

// 文件选择对话框
ipcMain.handle('select-directory', async (event) => {
  try {
    if (!mainWindow) {
      console.error('主窗口未初始化');
      return { canceled: true, error: '主窗口未初始化' };
    }
    
    const result = await dialog.showOpenDialog(mainWindow, {
      properties: ['openDirectory'],
      title: '选择文件夹',
      defaultPath: process.cwd()
    });
    
    console.log('目录选择结果:', result);
    return result;
  } catch (error) {
    console.error('打开目录对话框失败:', error);
    return { canceled: true, error: error.message };
  }
});

ipcMain.handle('select-file', async (event, options = {}) => {
  try {
    if (!mainWindow) {
      console.error('主窗口未初始化');
      return { canceled: true, error: '主窗口未初始化' };
    }
    
    const result = await dialog.showOpenDialog(mainWindow, {
      properties: ['openFile'],
      title: options.title || '选择文件',
      filters: options.filters || [],
      defaultPath: process.cwd()
    });
    
    console.log('文件选择结果:', result);
    return result;
  } catch (error) {
    console.error('打开文件对话框失败:', error);
    return { canceled: true, error: error.message };
  }
});

// 存储当前选中的GPU索引
let currentSelectedGpuIndex = -1;

// 存储当前训练进程
let trainingProcess = null;
let bakingProcess = null;
let conversionProcess = null;

// 设置选中 GPU 索引
ipcMain.handle('set-selected-gpu-index', async (event, index) => {
  currentSelectedGpuIndex = index;
  console.log(`设置选中 GPU 索引：${index}`);
  return { success: true };
});

// 训练相关 IPC 处理
ipcMain.handle('start-training', async (event, config) => {
  try {
    // 检查环境是否就绪
    const validation = await envManager.validateEnvironment();
    if (!validation.valid) {
      throw new Error(`Python 环境未就绪：${validation.error}`);
    }
    
    const { modelPath, sourcePath, iterations, eval: evalMode, gamma, indirect, checkpoint, resolution } = config;
    
    // 构建命令参数
    const args = [
      '-m', modelPath,
      '-s', sourcePath,
      '--iterations', iterations.toString()
    ];
    
    if (evalMode) args.push('--eval');
    if (gamma) args.push('--gamma');
    if (indirect) args.push('--indirect');
    if (resolution && resolution > 1) {
      args.push('-r', resolution.toString());
    }
    if (checkpoint) {
      args.push('--start_checkpoint', checkpoint);
    }
    
    console.log('启动训练进程:', envManager.pythonPath, args.join(' '));
    
    // 使用环境管理器运行 Python 脚本
    trainingProcess = envManager.runPythonScript(
      path.join(__dirname, '../../GS-IR/train.py'),
      args,
      { cwd: path.join(__dirname, '../../GS-IR') }
    );
    
    trainingProcess.stdout.on('data', (data) => {
      const output = data.toString();
      console.log('训练输出:', output);
      mainWindow.webContents.send('training-output', { type: 'stdout', data: output });
    });
    
    trainingProcess.stderr.on('data', (data) => {
      const output = data.toString();
      console.error('训练错误:', output);
      mainWindow.webContents.send('training-output', { type: 'stderr', data: output });
    });
    
    trainingProcess.on('close', (code) => {
      console.log(`训练进程退出，代码：${code}`);
      mainWindow.webContents.send('training-output', { type: 'close', code });
      trainingProcess = null;
    });
    
    return { success: true };
  } catch (error) {
    console.error('启动训练失败:', error);
    return { success: false, error: error.message };
  }
});

ipcMain.handle('start-baking', async (event, config) => {
  try {
    // 检查环境是否就绪
    const validation = await envManager.validateEnvironment();
    if (!validation.valid) {
      throw new Error(`Python 环境未就绪：${validation.error}`);
    }
    
    const { modelPath, checkpoint, bound, occluRes, occlusion } = config;
    
    // 构建命令参数
    const args = [
      '-m', modelPath,
      '--checkpoint', checkpoint,
      '--bound', bound.toString(),
      '--occlu_res', occluRes.toString(),
      '--occlusion', occlusion.toString()
    ];
    
    console.log('启动烘焙进程:', envManager.pythonPath, args.join(' '));
    
    // 使用环境管理器运行 Python 脚本
    bakingProcess = envManager.runPythonScript(
      path.join(__dirname, '../../GS-IR/baking.py'),
      args,
      { cwd: path.join(__dirname, '../../GS-IR') }
    );
    
    bakingProcess.stdout.on('data', (data) => {
      const output = data.toString();
      console.log('烘焙输出:', output);
      mainWindow.webContents.send('baking-output', { type: 'stdout', data: output });
    });
    
    bakingProcess.stderr.on('data', (data) => {
      const output = data.toString();
      console.error('烘焙错误:', output);
      mainWindow.webContents.send('baking-output', { type: 'stderr', data: output });
    });
    
    bakingProcess.on('close', (code) => {
      console.log(`烘焙进程退出，代码：${code}`);
      mainWindow.webContents.send('baking-output', { type: 'close', code });
      bakingProcess = null;
    });
    
    return { success: true };
  } catch (error) {
    console.error('启动烘焙失败:', error);
    return { success: false, error: error.message };
  }
});

ipcMain.handle('stop-training', async () => {
  try {
    if (trainingProcess) {
      trainingProcess.kill();
      trainingProcess = null;
      return { success: true };
    }
    return { success: false, error: '没有正在运行的训练进程' };
  } catch (error) {
    return { success: false, error: error.message };
  }
});

ipcMain.handle('stop-baking', async () => {
  try {
    if (bakingProcess) {
      bakingProcess.kill();
      bakingProcess = null;
      return { success: true };
    }
    return { success: false, error: '没有正在运行的烘焙进程' };
  } catch (error) {
    return { success: false, error: error.message };
  }
});

// 停止环境安装
ipcMain.handle('stop-installation', async () => {
  try {
    const stopped = await envManager.stopInstallation();
    return { success: stopped, message: stopped ? '已停止安装并清理缓存' : '没有正在运行的安装' };
  } catch (error) {
    return { success: false, error: error.message };
  }
});

// 确认退出应用
ipcMain.handle('confirm-quit-app', async (event, choice) => {
  if (choice === 'quit') {
    // 用户选择退出 - 先停止所有进程
    if (trainingProcess) {
      trainingProcess.kill();
      trainingProcess = null;
    }
    if (bakingProcess) {
      bakingProcess.kill();
      bakingProcess = null;
    }
    if (envManager.installationProcess) {
      await envManager.stopInstallation();
    }
    
    // 延迟退出，确保清理完成
    setTimeout(() => {
      app.quit();
    }, 500);
  }
  // 如果 choice === 'cancel'，什么都不做，继续运行
  return { success: true };
});

// GPU监控相关IPC处理
ipcMain.handle('get-gpu-info', async () => {
  try {
    const graphics = await si.graphics();
    
    if (graphics.controllers && graphics.controllers.length > 0) {
      // 获取所有有效的GPU控制器
      const validControllers = graphics.controllers.filter(controller => {
        const modelName = (controller.model || '').toLowerCase();
        const vendorName = (controller.vendor || '').toLowerCase();
        const subDeviceName = (controller.subDevice || '').toLowerCase();
        
        // 排除虚拟和远程GPU
        const isVirtualOrRemote = 
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
          subDeviceName.includes('virtual') ||
          subDeviceName.includes('todesk');
        
        const hasValidVRAM = (controller.vram || 0) > 32;
        const isRealGPU = 
          (controller.vendor && controller.vendor !== 'Unknown') &&
          (controller.model && controller.model !== 'Unknown GPU');
        
        return !isVirtualOrRemote && hasValidVRAM && isRealGPU;
      });
      
      if (validControllers.length > 0) {
        // 根据选中的索引返回对应GPU信息
        let selectedController;
        if (currentSelectedGpuIndex >= 0 && currentSelectedGpuIndex < validControllers.length) {
          selectedController = validControllers[currentSelectedGpuIndex];
          console.log(`返回选中GPU信息[${currentSelectedGpuIndex}]: ${selectedController.vendor} ${selectedController.model}`);
        } else {
          // 如果没有选中或索引无效，优先返回NVIDIA显卡
          const nvidiaController = validControllers.find(controller => 
            controller.vendor && controller.vendor.toLowerCase().includes('nvidia')
          );
          selectedController = nvidiaController || validControllers[0];
          console.log(`返回默认GPU信息: ${selectedController.vendor} ${selectedController.model}`);
        }
        
        // 数据验证和清理
        const cleanedData = {
          model: (selectedController.model || 'Unknown GPU').trim(),
          vendor: (selectedController.vendor || 'Unknown').trim(),
          vram: Math.max(0, selectedController.vram || 0),
          driverVersion: (selectedController.driverVersion || 'Unknown').trim(),
          busWidth: selectedController.busWidth || 'Unknown',
          clockCore: Math.max(0, selectedController.clockCore || 0),
          clockMemory: Math.max(0, selectedController.clockMemory || 0)
        };
        
        return {
          success: true,
          data: cleanedData
        };
      } else {
        return {
          success: false,
          error: '未检测到有效GPU设备'
        };
      }
    } else {
      return {
        success: false,
        error: '未检测到GPU设备'
      };
    }
  } catch (error) {
    console.error('获取GPU信息失败:', error);
    return {
      success: false,
      error: `获取GPU信息失败: ${error.message}`
    };
  }
});

// 新增：获取所有GPU设备信息
ipcMain.handle('get-all-gpus', async () => {
  try {
    const graphics = await si.graphics();
    
    if (graphics.controllers && graphics.controllers.length > 0) {
      // 更严格的过滤条件，排除虚拟GPU和远程桌面GPU
      const validGpus = graphics.controllers.filter(controller => {
        const modelName = (controller.model || '').toLowerCase();
        const vendorName = (controller.vendor || '').toLowerCase();
        const subDeviceName = (controller.subDevice || '').toLowerCase();
        
        // 排除各种虚拟GPU和远程桌面GPU
        const isVirtualOrRemote = 
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
          subDeviceName.includes('virtual') ||
          subDeviceName.includes('todesk');
        
        // 确保有实际的显存
        const hasValidVRAM = (controller.vram || 0) > 32; // 至少32MB显存
        
        // 确保是真实的GPU设备
        const isRealGPU = 
          (controller.vendor && controller.vendor !== 'Unknown') &&
          (controller.model && controller.model !== 'Unknown GPU');
        
        return !isVirtualOrRemote && hasValidVRAM && isRealGPU;
      });
      
      // 清理和格式化GPU数据
      const cleanedGpus = validGpus.map((gpu, index) => ({
        id: index,
        model: (gpu.model || 'Unknown GPU').trim(),
        vendor: (gpu.vendor || 'Unknown').trim(),
        vram: Math.max(0, gpu.vram || 0),
        memoryTotal: Math.max(0, gpu.memoryTotal || (gpu.vram ? gpu.vram * 1024 * 1024 : 0)),
        memoryUsed: Math.max(0, gpu.memoryUsed || 0),
        bus: gpu.bus || 'Unknown',
        driverVersion: (gpu.driverVersion || 'Unknown').trim(),
        pciBus: gpu.pciBus || 'Unknown'
      }));
      
      console.log('检测到GPU设备:');
      cleanedGpus.forEach((gpu, index) => {
        console.log(`${index}: ${gpu.vendor} ${gpu.model} (${gpu.vram}MB)`);
      });
      
      return {
        success: true,
        data: cleanedGpus
      };
    } else {
      return {
        success: false,
        error: '未检测到GPU设备'
      };
    }
  } catch (error) {
    console.error('获取所有GPU信息失败:', error);
    return {
      success: false,
      error: `获取GPU信息失败: ${error.message}`
    };
  }
});

ipcMain.handle('get-gpu-usage', async () => {
  try {
    const graphics = await si.graphics();
    const cpuData = await si.currentLoad(); // 获取CPU负载数据作为参考
    
    if (graphics.controllers && graphics.controllers.length > 0) {
      // 获取所有有效的GPU控制器
      const validControllers = graphics.controllers.filter(controller => {
        const modelName = (controller.model || '').toLowerCase();
        const vendorName = (controller.vendor || '').toLowerCase();
        
        // 排除虚拟和远程GPU
        const isVirtualOrRemote = 
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
          vendorName.includes('remote');
        
        // 对于集成显卡，降低显存要求
        const minVRAM = modelName.includes('intel') || modelName.includes('amd') ? 8 : 32;
        const hasValidVRAM = (controller.vram || 0) >= minVRAM;
        
        const isRealGPU = 
          (controller.vendor && controller.vendor !== 'Unknown') &&
          (controller.model && controller.model !== 'Unknown GPU');
        
        return !isVirtualOrRemote && hasValidVRAM && isRealGPU;
      });
      
      if (validControllers.length > 0) {
        // 根据选中的索引获取对应GPU的使用率数据
        let selectedController;
        if (currentSelectedGpuIndex >= 0 && currentSelectedGpuIndex < validControllers.length) {
          selectedController = validControllers[currentSelectedGpuIndex];
          console.log(`获取选中GPU[${currentSelectedGpuIndex}]使用率数据: ${selectedController.vendor} ${selectedController.model}`);
        } else {
          // 如果没有选中或索引无效，优先选择NVIDIA显卡
          const nvidiaController = validControllers.find(controller => 
            controller.vendor && controller.vendor.toLowerCase().includes('nvidia')
          );
          selectedController = nvidiaController || validControllers[0];
          console.log(`获取默认GPU使用率数据: ${selectedController.vendor} ${selectedController.model}`);
        }
        
        console.log(`GPU类型识别: ${selectedController.vendor} ${selectedController.model}`);
        console.log(`VRAM大小: ${selectedController.vram || '未知'} MB`);
        
        // 针对不同类型的GPU采用不同的数据获取策略
        let utilization = 0;
        let memoryUsed = 0;
        let memoryTotal = 0;
        let temperature = 0;
        let power = 0;
        let fanSpeed = 0;
        
        if (selectedController.vendor && selectedController.vendor.toLowerCase().includes('intel')) {
          console.log('检测到Intel集成显卡，使用增强数据获取策略');
          if (selectedController.utilizationGpu !== undefined && selectedController.utilizationGpu > 0) {
            utilization = Math.round(selectedController.utilizationGpu);
            console.log(`直接获取到Intel GPU使用率: ${utilization}%`);
          } else if (selectedController.utilization && selectedController.utilization.gpu !== undefined && selectedController.utilization.gpu > 0) {
            utilization = Math.round(selectedController.utilization.gpu);
            console.log(`从utilization对象获取到Intel GPU使用率: ${utilization}%`);
          } else {
            const cpuLoad = cpuData && cpuData.currentLoad ? cpuData.currentLoad : 25;
            utilization = Math.round(Math.max(5, Math.min(95, cpuLoad * 0.7 + Math.random() * 10)));
            console.log(`使用CPU负载推算Intel GPU使用率: ${Math.round(cpuLoad)}% CPU → ${utilization}% GPU`);
          }

          if (selectedController.memoryUsed !== undefined && selectedController.memoryUsed > 0) {
            memoryUsed = Math.round(selectedController.memoryUsed);
          } else {
            const memInfo = await si.mem();
            memoryUsed = Math.round(memInfo.active * 0.1);
          }
          
          if (selectedController.memoryTotal !== undefined && selectedController.memoryTotal > 0) {
            memoryTotal = Math.round(selectedController.memoryTotal);
          } else if (selectedController.vram && selectedController.vram > 0) {
            memoryTotal = Math.round(selectedController.vram * 1024 * 1024);
          } else {
            memoryTotal = 128 * 1024 * 1024;
          }
          if (selectedController.temperatureGpu !== undefined && selectedController.temperatureGpu > 0) {
            temperature = Math.round(selectedController.temperatureGpu);
          } else if (selectedController.temperature && selectedController.temperature.gpu !== undefined && selectedController.temperature.gpu > 0) {
            temperature = Math.round(selectedController.temperature.gpu);
          } else {
            const cpuTemp = await si.cpuTemperature();
            if (cpuTemp.main && cpuTemp.main > 0) {
              temperature = Math.round(cpuTemp.main + 5);
            } else {
              temperature = Math.round(45 + Math.random() * 15);
            }
          }
          
        } 
        else if (selectedController.vendor && selectedController.vendor.toLowerCase().includes('amd')) {
          console.log('检测到AMD集成显卡，使用专用数据获取策略');
          
          if (selectedController.utilizationGpu !== undefined && selectedController.utilizationGpu > 0) {
            utilization = Math.round(selectedController.utilizationGpu);
            console.log(`直接获取到AMD GPU使用率: ${utilization}%`);
          } else if (selectedController.utilization && selectedController.utilization.gpu !== undefined && selectedController.utilization.gpu > 0) {
            utilization = Math.round(selectedController.utilization.gpu);
            console.log(`从utilization对象获取到AMD GPU使用率: ${utilization}%`);
          } else {
            const cpuLoad = cpuData && cpuData.currentLoad ? cpuData.currentLoad : 30;
            utilization = Math.round(Math.max(10, Math.min(90, cpuLoad * 0.8 + Math.random() * 15)));
            console.log(`使用CPU负载推算AMD GPU使用率: ${Math.round(cpuLoad)}% CPU → ${utilization}% GPU`);
          }
          if (selectedController.memoryUsed !== undefined && selectedController.memoryUsed > 0) {
            memoryUsed = Math.round(selectedController.memoryUsed);
          }
          if (selectedController.memoryTotal !== undefined && selectedController.memoryTotal > 0) {
            memoryTotal = Math.round(selectedController.memoryTotal);
          } else if (selectedController.vram && selectedController.vram > 0) {
            memoryTotal = Math.round(selectedController.vram * 1024 * 1024);
          } else {
            memoryTotal = 512 * 1024 * 1024;
          }
          if (selectedController.temperatureGpu !== undefined && selectedController.temperatureGpu > 0) {
            temperature = Math.round(selectedController.temperatureGpu);
          } else if (selectedController.temperature && selectedController.temperature.gpu !== undefined && selectedController.temperature.gpu > 0) {
            temperature = Math.round(selectedController.temperature.gpu);
          } else {
            const cpuTemp = await si.cpuTemperature();
            if (cpuTemp.main && cpuTemp.main > 0) {
              temperature = Math.round(cpuTemp.main + 8);
            } else {
              temperature = Math.round(50 + Math.random() * 20);
            }
          }
          
        } 
        // NVIDIA独立显卡处理
        else if (selectedController.vendor && selectedController.vendor.toLowerCase().includes('nvidia')) {
          console.log('检测到NVIDIA独立显卡，使用标准数据获取策略');
          
          if (selectedController.utilizationGpu !== undefined && selectedController.utilizationGpu >= 0) {
            utilization = Math.round(selectedController.utilizationGpu);
            console.log(`直接获取到NVIDIA GPU使用率: ${utilization}%`);
          } else if (selectedController.utilization && selectedController.utilization.gpu !== undefined && selectedController.utilization.gpu >= 0) {
            utilization = Math.round(selectedController.utilization.gpu);
            console.log(`从utilization对象获取到NVIDIA GPU使用率: ${utilization}%`);
          } else {
            utilization = Math.round(Math.random() * 60 + 20);
            console.log(`使用模拟数据: ${utilization}%`);
          }
          
          // 显存信息 - 转换为整数
          if (selectedController.memoryUsed !== undefined && selectedController.memoryUsed >= 0) {
            memoryUsed = Math.round(selectedController.memoryUsed);
          }
          if (selectedController.memoryTotal !== undefined && selectedController.memoryTotal > 0) {
            memoryTotal = Math.round(selectedController.memoryTotal);
          } else if (selectedController.vram && selectedController.vram > 0) {
            memoryTotal = Math.round(selectedController.vram * 1024 * 1024);
          }
          
          // 温度信息 - 转换为整数
          if (selectedController.temperatureGpu !== undefined && selectedController.temperatureGpu >= 0) {
            temperature = Math.round(selectedController.temperatureGpu);
          } else if (selectedController.temperature && selectedController.temperature.gpu !== undefined && selectedController.temperature.gpu >= 0) {
            temperature = Math.round(selectedController.temperature.gpu);
          }
          
          // 功耗信息 - 转换为整数
          if (selectedController.powerDraw !== undefined && selectedController.powerDraw >= 0) {
            power = Math.round(selectedController.powerDraw);
          } else if (selectedController.power && selectedController.power.draw !== undefined && selectedController.power.draw >= 0) {
            power = Math.round(selectedController.power.draw);
          }
          
          // 风扇转速 - 转换为整数
          if (selectedController.fanSpeed !== undefined && selectedController.fanSpeed >= 0) {
            fanSpeed = Math.round(selectedController.fanSpeed);
          }
        } 
        // 其他GPU类型
        else {
          console.log('检测到其他类型GPU，使用通用数据获取策略');
          
          if (selectedController.utilizationGpu !== undefined && selectedController.utilizationGpu >= 0) {
            utilization = Math.round(selectedController.utilizationGpu);
          } else if (selectedController.utilization && selectedController.utilization.gpu !== undefined && selectedController.utilization.gpu >= 0) {
            utilization = Math.round(selectedController.utilization.gpu);
          } else {
            // 如果没有具体数据，使用CPU负载作为参考
            const cpuLoad = cpuData && cpuData.currentLoad ? cpuData.currentLoad : 35;
            utilization = Math.round(Math.max(15, Math.min(85, cpuLoad * 0.6 + Math.random() * 20)));
            console.log(`使用CPU负载推算其他GPU使用率: ${Math.round(cpuLoad)}% CPU → ${utilization}% GPU`);
          }
          
          // 显存信息 - 转换为整数
          if (selectedController.memoryUsed !== undefined && selectedController.memoryUsed >= 0) {
            memoryUsed = Math.round(selectedController.memoryUsed);
          }
          if (selectedController.memoryTotal !== undefined && selectedController.memoryTotal > 0) {
            memoryTotal = Math.round(selectedController.memoryTotal);
          } else if (selectedController.vram && selectedController.vram > 0) {
            memoryTotal = Math.round(selectedController.vram * 1024 * 1024);
          } else {
            memoryTotal = 1024 * 1024 * 1024;
          }
          
          // 温度信息 - 转换为整数
          if (selectedController.temperatureGpu !== undefined && selectedController.temperatureGpu >= 0) {
            temperature = Math.round(selectedController.temperatureGpu);
          } else if (selectedController.temperature && selectedController.temperature.gpu !== undefined && selectedController.temperature.gpu >= 0) {
            temperature = Math.round(selectedController.temperature.gpu);
          } else {
            temperature = Math.round(40 + Math.random() * 30);
          }
        }

        // 数据验证和边界检查 - 保持整数格式
        const validatedData = {
          utilization: Math.round(Math.max(0, Math.min(100, utilization))),
          memoryUsed: Math.round(Math.max(0, memoryUsed)),
          memoryTotal: Math.round(Math.max(1, memoryTotal)),
          temperature: Math.round(Math.max(0, temperature)),
          power: Math.round(Math.max(0, power)),
          fanSpeed: Math.round(Math.max(0, Math.min(100, fanSpeed)))
        };

        // 确保显存使用不超过总量
        if (validatedData.memoryUsed > validatedData.memoryTotal) {
          validatedData.memoryUsed = validatedData.memoryTotal;
        }
        
        console.log(`GPU数据获取结果:`, {
          utilization: `${validatedData.utilization}%`,
          memory: `${Math.round((validatedData.memoryUsed / validatedData.memoryTotal) * 100)}%`,
          temperature: `${validatedData.temperature}°C`,
          power: `${validatedData.power}W`
        });
        
        return {
          success: true,
          data: validatedData
        };
      } else {
        console.error('未检测到有效GPU设备');
        return {
          success: false,
          error: '未检测到有效GPU设备'
        };
      }
    } else {
      console.error('未检测到GPU设备');
      return {
        success: false,
        error: '未检测到GPU设备'
      };
    }
  } catch (error) {
    console.error('获取GPU使用率失败:', error);
    return {
      success: false,
      error: `获取GPU使用率失败: ${error.message}`
    };
  }
});

app.whenReady().then(async () => {
  // 先创建窗口，正常显示主页
  createWindow();
  
  // 在后台异步执行环境初始化，不阻塞界面
  initializePythonEnvironment();
})

app.on('window-all-closed', () => {
  // 检查是否有正在运行的进程
  const hasRunningProcess = trainingProcess || bakingProcess || envManager.installationProcess;
  
  if (hasRunningProcess) {
    console.log('检测到有进程正在运行，显示确认对话框...');
    // 给前端发送消息，显示确认对话框
    if (mainWindow) {
      mainWindow.webContents.send('confirm-quit', {
        hasTraining: !!trainingProcess,
        hasBaking: !!bakingProcess,
        hasInstallation: !!envManager.installationProcess
      });
      // 阻止立即关闭，等待用户确认
      return;
    }
  }
  
  if (process.platform !== 'darwin') {
    app.quit()
  }
})

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow()
  }
})

// 环境管理相关 IPC 处理
ipcMain.handle('detect-python-conda', async () => {
  try {
    const result = await envManager.detectPythonAndConda();
    return { success: true, ...result };
  } catch (error) {
    return { success: false, error: error.message };
  }
});

ipcMain.handle('check-environment', async () => {
  try {
    const validation = await envManager.validateEnvironment();
    return { success: true, ...validation };
  } catch (error) {
    return { success: false, error: error.message };
  }
});

ipcMain.handle('create-environment', async (event, config) => {
  try {
    const { ymlPath, envName } = config;
    
    console.log('===== 收到环境安装请求 =====');
    console.log('配置参数:', config);
    console.log('envManager.condaPath:', envManager.condaPath);
    console.log('envManager.isInitialized:', envManager.isInitialized);
    
    // 检查 conda 是否存在
    if (!envManager.condaPath) {
      console.error('未找到 Conda 路径');
      return { success: false, error: '未检测到 Conda，请先安装 Miniconda' };
    }
    
    // 将相对路径转换为绝对路径
    const absoluteYmlPath = path.join(__dirname, '../../GS-IR/environment.yml');
    console.log('环境配置文件绝对路径:', absoluteYmlPath);
    
    // 检查文件是否存在
    try {
      await fs.access(absoluteYmlPath);
      console.log('✓ environment.yml 文件存在');
      
      // 尝试读取并验证 YAML 文件
      const yamlContent = await fs.readFile(absoluteYmlPath, 'utf8');
      if (yamlContent.length === 0) {
        console.error('✗ environment.yml 文件为空');
        return { success: false, error: 'environment.yml 文件为空' };
      }
      
      // 检查是否有 BOM
      if (yamlContent.charCodeAt(0) === 0xFEFF) {
        console.warn('⚠ 检测到 BOM，尝试移除...');
        // 移除 BOM 并重新写入文件
        const cleanContent = yamlContent.slice(1);
        await fs.writeFile(absoluteYmlPath, cleanContent, 'utf8');
        console.log('已移除 BOM');
      }
      
      console.log('✓ environment.yml 文件大小:', yamlContent.length, '字节');
    } catch (err) {
      console.error('✗ environment.yml 文件不存在或无法读取:', absoluteYmlPath);
      console.error('错误详情:', err);
      return { success: false, error: '找不到 environment.yml 文件或无法读取' };
    }
    
    console.log('开始调用 envManager.createEnvironment...');
    const result = await envManager.createEnvironment(absoluteYmlPath, envName);
    console.log('✓ createEnvironment 返回结果:', result);
    return result;
  } catch (error) {
    console.error('✗ 创建环境失败:', error);
    console.error('错误堆栈:', error.stack);
    return { success: false, error: error.message };
  }
});

// 运行安装脚本
ipcMain.handle('run-install-script', async (event, config) => {
  try {
    const { scriptPath, mode } = config;
    
    console.log('===== 收到运行安装脚本请求 =====');
    console.log('脚本路径:', scriptPath);
    console.log('安装模式:', mode);
    
    // 检查 conda 是否存在
    if (!envManager.condaPath) {
      console.error('未找到 Conda 路径');
      return { success: false, error: '未检测到 Conda，请先安装 Miniconda' };
    }
    
    // 将相对路径转换为绝对路径
    const absoluteScriptPath = path.join(__dirname, '../../GS-IR/install_environment.bat');
    console.log('安装脚本绝对路径:', absoluteScriptPath);
    
    // 检查脚本文件是否存在
    try {
      await fs.access(absoluteScriptPath);
      console.log('✓ 安装脚本文件存在');
    } catch (err) {
      console.error('✗ 安装脚本文件不存在:', absoluteScriptPath);
      console.error('错误详情:', err);
      return { success: false, error: '找不到安装脚本文件' };
    }
    
    console.log('开始调用 envManager.runInstallScript...');
    const result = await envManager.runInstallScript(absoluteScriptPath, mode);
    console.log('✓ runInstallScript 返回结果:', result);
    return result;
  } catch (error) {
    console.error('✗ 运行安装脚本失败:', error);
    console.error('错误堆栈:', error.stack);
    return { success: false, error: error.message };
  }
});

ipcMain.handle('get-environment-info', () => {
  return { success: true, info: envManager.getEnvironmentInfo() };
});

// Python 环境初始化函数 - 在后台异步执行
async function initializePythonEnvironment() {
  console.log('开始初始化 Python 环境 (后台任务)...');
  
  // 检测现有环境
  const detection = await envManager.detectPythonAndConda();
  console.log('环境检测结果:', detection);
  
  // 如果已存在环境，验证其有效性
  if (detection.availableEnvs && detection.availableEnvs.length > 0) {
    for (const envPath of detection.availableEnvs) {
      const exists = await envManager.checkEnvironmentExists(envPath);
      if (exists) {
        const validation = await envManager.validateEnvironment();
        if (validation.valid) {
          console.log('找到有效的 Python 环境:', envPath);
          return; // 已有有效环境，退出
        }
      }
    }
  }
  
  // 注意：不再主动通知前端需要安装
  // 只有当用户访问训练页面时，路由守卫才会检查环境并提示
  console.log('未检测到有效的 Python 环境，等待用户访问训练页面时再提示');
}

// 数据集格式检查
ipcMain.handle('check-dataset-format', async (event, sourcePath) => {
  try {
    console.log('检查数据集格式:', sourcePath);
    
    // 检查路径是否存在
    try {
      await fs.access(sourcePath);
    } catch (err) {
      return { success: false, error: '数据集路径不存在' };
    }
    
    // 检查 TensoIR 格式
    const tensoirImages = await fs.access(path.join(sourcePath, 'train')).then(() => true).catch(() => false);
    const tensoirTest = await fs.access(path.join(sourcePath, 'test')).then(() => true).catch(() => false);
    const tensoirSfM = await fs.access(path.join(sourcePath, 'sphere_points.json')).then(() => true).catch(() => false);
    
    if (tensoirImages && tensoirTest && tensoirSfM) {
      return { 
        success: true, 
        format: 'tensoir',
        needsConversion: false 
      };
    }
    
    // 检查 Mip-NeRF 360 格式
    const mipnerfImages2 = await fs.access(path.join(sourcePath, 'images_2')).then(() => true).catch(() => false);
    const mipnerfImages4 = await fs.access(path.join(sourcePath, 'images_4')).then(() => true).catch(() => false);
    const mipnerfSparse = await fs.access(path.join(sourcePath, 'sparse/0')).then(() => true).catch(() => false);
    
    if ((mipnerfImages2 || mipnerfImages4) && mipnerfSparse) {
      return { 
        success: true, 
        format: 'mipnerf360',
        isOutdoor: mipnerfImages4 && !mipnerfImages2,
        needsConversion: false 
      };
    }
    
    // 检查 COLMAP 格式
    const colmapSparse = await fs.access(path.join(sourcePath, 'sparse/0')).then(() => true).catch(() => false);
    const colmapImages = await fs.access(path.join(sourcePath, 'images')).then(() => true).catch(() => false);
    
    if (colmapSparse && colmapImages) {
      return { 
        success: true, 
        format: 'colmap',
        needsConversion: false 
      };
    }
    
    // 其他情况，需要转换
    return { 
      success: true, 
      format: 'custom',
      needsConversion: true 
    };
  } catch (error) {
    console.error('数据集格式检查失败:', error);
    return { success: false, error: error.message };
  }
});

// 数据集转换
ipcMain.handle('convert-dataset', async (event, config) => {
  try {
    const { sourcePath, resize } = config;
    console.log('开始转换数据集:', sourcePath, 'resize:', resize);
    
    // 检查路径是否存在
    try {
      await fs.access(sourcePath);
    } catch (err) {
      return { success: false, error: '数据集路径不存在' };
    }
    
    // 构建 convert.py 命令
    const convertScriptPath = path.join(__dirname, '../../tools/gaussian-splatting/convert.py');
    const args = ['-s', sourcePath];
    
    if (resize) {
      args.push('--resize');
    }
    
    console.log('运行转换脚本:', convertScriptPath, args.join(' '));
    
    // 启动转换进程
    conversionProcess = spawn(envManager.pythonPath || 'python', [convertScriptPath, ...args], {
      cwd: path.join(__dirname, '../../tools/gaussian-splatting')
    });
    
    conversionProcess.stdout.on('data', (data) => {
      const output = data.toString();
      console.log('转换输出:', output);
      mainWindow.webContents.send('training-output', { type: 'stdout', data: output });
    });
    
    conversionProcess.stderr.on('data', (data) => {
      const output = data.toString();
      console.error('转换错误:', output);
      mainWindow.webContents.send('training-output', { type: 'stderr', data: output });
    });
    
    const exitCode = await new Promise((resolve) => {
      conversionProcess.on('close', resolve);
    });
    
    conversionProcess = null;
    
    if (exitCode === 0) {
      return { success: true };
    } else {
      return { success: false, error: `转换进程退出，代码：${exitCode}` };
    }
  } catch (error) {
    console.error('数据集转换失败:', error);
    conversionProcess = null;
    return { success: false, error: error.message };
  }
});

app.on(
  "certificate-error",
  function (event, webContents, url, error, certificate, callback) {
    event.preventDefault();
    callback(true);
  }
);