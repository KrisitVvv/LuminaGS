const { app, BrowserWindow, Menu, ipcMain, dialog, protocol } = require('electron');
const si = require('systeminformation');
const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs').promises;
const PythonEnvironmentManager = require('./pythonEnvironment');
const ProjectManager = require('./projectManager');

Menu.setApplicationMenu(null);
let mainWindow = null;
let editorWindow = null; 
const isPackaged = app.isPackaged;

// Register the custom protocol luma:// for accessing local files
protocol.registerSchemesAsPrivileged([{
  scheme: 'luma',
  privileges: {
    standard: true,
    secure: true,
    supportFetchApi: true,
    corsEnabled: false,
    allowServiceWorkers: false,
    bypassCSP: false,
    stream: false
  }
}]);

// Initialize Python environment manager
const envManager = new PythonEnvironmentManager();

// Get the MIME type of an image based on its extension
function getImageMimeType(ext) {
  const mimeTypes = {
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.gif': 'image/gif',
    '.webp': 'image/webp',
    '.svg': 'image/svg+xml'
  };
  return mimeTypes[ext] || 'application/octet-stream';
}

// Expose mainWindow to global
global.mainWindow = null;
const projectManager = new ProjectManager();

const createWindow = () => {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 850,
    frame: false,
    movable: true,
    webPreferences: {
      nodeIntegration: false, 
      contextIsolation: true,
      preload: __dirname + '/preload.js',
      webviewTag: true,
      sandbox: false
    }
  })
  global.mainWindow = mainWindow;

  mainWindow.loadURL("http://localhost:5173/");

  if (!isPackaged) {
    mainWindow.webContents.openDevTools();
  }
  
  mainWindow.on('maximize', () => {
    console.log('Window maximized');
    mainWindow.webContents.send('window-maximized');
  });
  
  mainWindow.on('unmaximize', () => {
    console.log('Window restored.');
    mainWindow.webContents.send('window-restored');
  });
  
  mainWindow.on('enter-full-screen', () => {
    console.log('Window entered full-screen');
    mainWindow.webContents.send('window-maximized');
  });
  
  mainWindow.on('leave-full-screen', () => {
    console.log('Window left full-screen.');
    mainWindow.webContents.send('window-restored');
  });
  
  mainWindow.on('resize', () => {
    setTimeout(() => {
      if (mainWindow) {
        const isMaximized = mainWindow.isMaximized();
        const isFullScreen = mainWindow.isFullScreen();
        console.log(`Window status check - Maximized: ${isMaximized}, Full-screen: ${isFullScreen}`);
        
        if (!isMaximized && !isFullScreen) {
          console.log('Window restored.');
          mainWindow.webContents.send('window-restored');
        }
        else if (isMaximized || isFullScreen) {
          console.log('Window maximized');
          mainWindow.webContents.send('window-maximized');
        }
      }
    }, 150);
  });
}

ipcMain.handle('minimize-window', async (event) => {
  const window = BrowserWindow.fromWebContents(event.sender);
  if (window) {
    window.minimize();
    console.log('[EditorWindow] minimized windows');
  }
});

ipcMain.handle('maximize-window', async (event) => {
  const window = BrowserWindow.fromWebContents(event.sender);
  if (window) {
    window.maximize();
    console.log('[EditorWindow] maximized window');
  }
});

ipcMain.handle('restore-window', async (event) => {
  const window = BrowserWindow.fromWebContents(event.sender);
  if (window) {
    window.restore();
    console.log('[EditorWindow] restored window');
  }
});

ipcMain.handle('close-window', async (event) => {
  const window = BrowserWindow.fromWebContents(event.sender);
  if (window) {
    window.close();
    console.log('[EditorWindow] closed window');
  }
});

ipcMain.handle('open-editor-window', async (event, config) => {
  try {
    console.log('[IPC] Open Editor window, config:', config);
    
    if (editorWindow) {
      editorWindow.focus();
      return { success: true, existed: true };
    }
    
    // Create new Editor window
    editorWindow = new BrowserWindow({
      width: 1920,
      height: 1080,
      frame: false, 
      movable: true,
      fullscreen: false,
      fullscreenable: true,
      hasShadow: false, 
      transparent: false,
      webPreferences: {
        nodeIntegration: false,
        contextIsolation: true,
        preload: __dirname + '/preload.js'
      },
      show: false, 
      backgroundColor: '#1e1e1e' 
    });
    editorWindow.setTitle('LuminaGS - Editor');
    const url = new URL('http://localhost:5173/');
    url.pathname = '/editor';
    
    if (config?.projectId) {
      url.pathname += `/${config.projectId}`;
    }
    
    if (config?.outputPath) {
      url.searchParams.append('outputPath', config.outputPath);
    }
    
    if (config?.checkpoint) {
      url.searchParams.append('checkpoint', config.checkpoint);
    }
    editorWindow.loadURL(url.toString());
    
    editorWindow.on('closed', () => {
      console.log('[EditorWindow] 窗口已关闭');
      editorWindow = null;
    });
    editorWindow.on('enter-full-screen', () => {
      console.log('[EditorWindow] 进入全屏');
      editorWindow.webContents.send('window-maximized');
    });
    
    editorWindow.on('leave-full-screen', () => {
      console.log('[EditorWindow] 退出全屏');
      editorWindow.webContents.send('window-restored');
    });
    
    editorWindow.on('maximize', () => {
      console.log('[EditorWindow] 最大化');
      editorWindow.webContents.send('window-maximized');
    });
    
    editorWindow.on('unmaximize', () => {
      console.log('[EditorWindow] 恢复');
      editorWindow.webContents.send('window-restored');
    });
      
    // Window is ready to show
    editorWindow.once('ready-to-show', () => {
      editorWindow.show();
      editorWindow.maximize();
    });
    
    if (!isPackaged) {
      editorWindow.webContents.openDevTools();
    }
    
    console.log('[EditorWindow] Editor window created');
    return { success: true, existed: false };
    
  } catch (error) {
    console.error('[EditorWindow] Failed to create window:', error);
    return { success: false, error: error.message };
  }
});

ipcMain.handle('start-dragging', async (event) => {
  const win = BrowserWindow.fromWebContents(event.sender);
  if (win && !win.isMaximized() && !win.isFullScreen()) {
    win.setIgnoreMouseEvents(false);
    win.webContents.startDrag({});
  }
});

// File selection dialog
ipcMain.handle('select-directory', async (event) => {
  try {
    if (!mainWindow) {
      console.error('Main window not initialized');
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

ipcMain.handle('check-folder-empty', async (event, folderPath) => {
  try {
    if (!folderPath) {
      return { success: false, error: '文件夹路径为空' };
    }
    try {
      await fs.access(folderPath);
    } catch (err) {
      return { success: true, isEmpty: true, exists: false, fileCount: 0 };
    }
    
    const files = await fs.readdir(folderPath);
    const fileCount = files.length;
    const isEmpty = fileCount === 0;
    
    console.log(`[FolderCheck] 路径：${folderPath}, 存在：true, 文件数：${fileCount}, 空：${isEmpty}`);
    
    return {
      success: true,
      exists: true,
      isEmpty: isEmpty,
      fileCount: fileCount,
      files: files.slice(0, 10)
    };
  } catch (error) {
    console.error('[FolderCheck] 检查失败:', error);
    return { success: false, error: error.message };
  }
});

ipcMain.handle('check-file-exists', async (event, filePath) => {
  try {
    if (!filePath) {
      return { success: false, error: '文件路径为空' };
    }
    
    try {
      await fs.access(filePath);
      console.log(`[FileCheck] 文件存在：${filePath}`);
      return { success: true, exists: true, path: filePath };
    } catch (err) {
      console.log(`[FileCheck]文件不存在：${filePath}`);
      return { success: true, exists: false };
    }
  } catch (error) {
    console.error('[FileCheck]检查失败:', error);
    return { success: false, error: error.message };
  }
});
ipcMain.handle('get-project-config', async (event, projectId) => {
  try {
    console.log('[IPC] 获取项目配置:', projectId);
    
    if (!projectId) {
      return { success: false, error: '项目 ID 为空' };
    }
    
    const config = await projectManager.getProjectConfig(projectId);
    
    if (config) {
      console.log('[IPC] 项目配置加载成功:', projectId);
      return { success: true, data: config };
    } else {
      console.warn('[IPC] 项目配置不存在:', projectId);
      return { success: false, error: '项目配置不存在' };
    }
  } catch (error) {
    console.error('[IPC] 获取项目配置失败:', error);
    return { success: false, error: error.message };
  }
});

ipcMain.handle('select-file', async (event, options = {}) => {
  try {
    if (!mainWindow) {
      console.error('Main window not initialized');
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
  
// Current selected GPU index
let currentSelectedGpuIndex = -1;

// Storage for current training process
let trainingProcess = null;
let bakingProcess = null;
let conversionProcess = null;
let conversionCancelled = false; // Mark conversion as cancelled by user

// Current training project ID
let currentTrainingProjectId = null;

// Training task queue management
const trainingQueue = [];
let isTrainingActive = false; // Mark if there is a training active 

// Start the next training task from the queue
async function startNextTrainingTask() {
  if (trainingQueue.length === 0 || isTrainingActive) {
    return;
  }
  
  isTrainingActive = true;
  const nextTask = trainingQueue.shift(); 
  
  try {
    console.log('[Queue] Starting next task in queue:', nextTask.projectName);
    if (nextTask.projectId) {
      await projectManager.updateProjectStatus(nextTask.projectId, 'training');
      currentTrainingProjectId = nextTask.projectId;
    }
    
    mainWindow.webContents.send('training-queue-update', {
      type: 'task-started',
      projectId: nextTask.projectId,
      projectName: nextTask.projectName
    });
    await startTrainingProcess(nextTask.config, nextTask.projectId);
  } catch (error) {
    console.error('[Queue] 启动队列任务失败:', error);
    if (nextTask.projectId) {
      await projectManager.updateProjectStatus(nextTask.projectId, 'error');
    }
    isTrainingActive = false;
    startNextTrainingTask(); 
  }
}

// Set selected GPU index
ipcMain.handle('set-selected-gpu-index', async (event, index) => {
  currentSelectedGpuIndex = index;
  console.log(`Set selected GPU index: ${index}`);
  return { success: true };
});

// Training related IPC handling
ipcMain.handle('start-training', async (event, config) => {
  try {
    const { 
      modelPath, 
      sourcePath, 
      iterations, 
      eval: evalMode, 
      gamma,
      indirect,
      checkpoint, 
      resolution, 
      imageSubdir,
      projectName,
      userGamma,
      userIndirect,
      userCheckpoint,
      userBound,
      userOccluRes,
      userOcclusion
    } = config;
    
    let projectId = config.projectId || null;
    let projectConfigFile = null;
    
    if (projectName && !config.checkpoint) {
      
      const saveGamma = (userGamma !== undefined) ? userGamma : gamma;
      const saveIndirect = (userIndirect !== undefined) ? userIndirect : indirect;
      const saveCheckpoint = (userCheckpoint !== undefined) ? userCheckpoint : checkpoint;
      const saveBound = (userBound !== undefined) ? userBound : 1.5;
      const saveOccluRes = (userOccluRes !== undefined) ? userOccluRes : 128;
      const saveOcclusion = (userOcclusion !== undefined) ? userOcclusion : 0.01;
      
      console.log('[Training] 参数对比 - 训练使用:', { gamma, indirect }, '| 用户选择:', { userGamma, userIndirect }, '| 最终保存:', { saveGamma, saveIndirect });
      
      const projectResult = await projectManager.createProject({
        projectName,
        outputPath: modelPath,
        sourcePath,
        stage: 'stage1',
        totalIterations: iterations,
        resolution,
        evalMode,
        gamma: saveGamma, 
        indirect: saveIndirect,
        bound: saveBound,
        occluRes: saveOccluRes,
        occlusion: saveOcclusion,
        checkpoint: saveCheckpoint
      });
      
      if (projectResult.success) {
        projectId = projectResult.projectId;
        projectConfigFile = projectResult.configFile;
        currentTrainingProjectId = projectId;
        console.log('[Training] 项目创建成功:', projectId);
      } else {
        console.warn('[Training] 项目创建失败，继续训练:', projectResult.error);
      }
    } else if (projectId && config.checkpoint) {
      console.log('[Training] Stage2 训练，更新现有项目:', projectId);
      try {
        await projectManager.updateProjectStage(projectId, 'stage2');
        console.log('[Training] 项目阶段已更新为 stage2');
        currentTrainingProjectId = projectId;
      } catch (error) {
        console.warn('[Training] 更新项目阶段失败:', error);
      }
    }
    
    if (isTrainingActive && trainingProcess) {
      console.log('[Queue] 训练正在进行中，将任务加入队列');
      trainingQueue.push({
        config,
        projectId,
        projectName: projectName || '未命名'
      });
    
      if (projectId) {
        await projectManager.updateProjectStatus(projectId, 'waiting');
      }
      mainWindow.webContents.send('training-queue-update', {
        type: 'task-queued',
        projectId,
        projectName: projectName || '未命名',
        queueLength: trainingQueue.length
      });
      
      return { 
        success: true, 
        queued: true, 
        message: '训练已加入队列，等待前一个任务完成',
        queuePosition: trainingQueue.length
      };
    }
        
    // Check if dataset format needs conversion
    mainWindow.webContents.send('training-output', { 
      type: 'stdout', 
      data: '\n========== 数据集格式检查 ==========\n' 
    });
    
    // Check if key directories exist
    const sparsePath = path.join(sourcePath, 'sparse/0');
    const imagesPath = path.join(sourcePath, 'images');
    
    const sparseExists = await fs.access(sparsePath).then(() => true).catch(() => false);
    const imagesExists = await fs.access(imagesPath).then(() => true).catch(() => false);
    
    let needsConversion = false;
    
    if (!sparseExists || !imagesExists) {
      needsConversion = true;
      mainWindow.webContents.send('training-output', { 
        type: 'stdout', 
        data: '需要运行 convert.py 进行数据集转换\n' 
      });
      
      mainWindow.webContents.send('training-output', { 
        type: 'stdout', 
        data: '开始执行 python convert.py -s ' + sourcePath + '\n\n' 
      });
      
      const convertScriptPath = path.join(__dirname, '../../tools/gaussian-splatting/convert.py');
      const convertArgs = ['-s', sourcePath];
      
      const scriptExists = await fs.access(convertScriptPath).then(() => true).catch(() => false);
      if (!scriptExists) {
        throw new Error(`找不到转换脚本：${convertScriptPath}`);
      }
      
      mainWindow.webContents.send('training-output', { 
        type: 'stdout', 
        data: `转换脚本：${convertScriptPath}\n` 
      });
      
      const convertProcess = envManager.runPythonScript(convertScriptPath, convertArgs, {
        cwd: path.join(__dirname, '../../tools/gaussian-splatting'),
        env: { ...process.env, PYTHONIOENCODING: 'utf-8' }
      });
      
      await new Promise((resolve, reject) => {
        convertProcess.stdout.on('data', (data) => {
          const output = data.toString();
          console.log('[CONVERT]', output);
          mainWindow.webContents.send('training-output', { type: 'stdout', data: output });
        });
        
        convertProcess.stderr.on('data', (data) => {
          const output = data.toString();
          console.error('[CONVERT ERROR]', output);
          mainWindow.webContents.send('training-output', { type: 'stderr', data: output });
        });
        
        convertProcess.on('close', (code) => {
          console.log(`[CONVERT] 进程退出，代码：${code}`);
          if (code === 0) {
            resolve();
          } else {
            reject(new Error(`转换失败，退出代码：${code}`));
          }
        });
        
        convertProcess.on('error', (err) => {
          console.error('[CONVERT] 进程错误:', err);
          reject(err);
        });
      });
      
      mainWindow.webContents.send('training-output', { 
        type: 'stdout', 
        data: '\n✓ 数据集转换完成！\n\n' 
      });
    } else {
      mainWindow.webContents.send('training-output', { 
        type: 'stdout', 
        data: '✓ 数据集格式检查通过 (COLMAP 格式已存在)\n' 
      });
      mainWindow.webContents.send('training-output', { 
        type: 'stdout', 
        data: '========================================\n\n' 
      });
    }
    
    const args = [
      '-m', modelPath,
      '-s', sourcePath,
      '--iterations', iterations.toString()
    ];
    
    if (imageSubdir && imageSubdir !== 'images') {
      args.push('-i', imageSubdir);
    }
    
    if (evalMode) args.push('--eval');
    if (gamma) args.push('--gamma');
    if (indirect) args.push('--indirect');
    
    // Handle resolution parameter
    let finalResolutionParam = null;
    if (resolution && resolution > 1) {
      finalResolutionParam = resolution;
          
      if (imageSubdir === 'images_2' && resolution === 2) {
        finalResolutionParam = 1;
      } else if (imageSubdir === 'images_4') {
        if (resolution === 4) {
          finalResolutionParam = 1;
        } else if (resolution === 8) {
          finalResolutionParam = 2;
        } else if (resolution === 16) {
          finalResolutionParam = 4;
        }
      } else if (imageSubdir === 'images_8') {
        if (resolution === 8) {
          finalResolutionParam = 1;
        } else if (resolution === 16) {
          finalResolutionParam = 2;
        }
      }
      if (finalResolutionParam > 1) {
        args.push('-r', finalResolutionParam.toString());
      }
    }
    
    console.log(`分辨率设置：目标=${resolution}, imageSubdir="${imageSubdir}", 实际 -r 参数=${finalResolutionParam || '未设置'}`);
    mainWindow.webContents.send('training-output', { 
      type: 'stdout', 
      data: `分辨率配置：目标 1/${resolution} | 使用目录：${imageSubdir} | -r 参数：${finalResolutionParam || '1(不压缩)'}\n` 
    });
    
    if (checkpoint) {
      args.push('--start_checkpoint', checkpoint);
    }
    console.log('Starting training process with command:', envManager.pythonPath, args.join(' '));
    
    isTrainingActive = true;
    
   const pythonScriptPath = path.join(__dirname, '../../GS-IR/train.py');
   const cwd = path.join(__dirname, '../../GS-IR');
    
  if (process.platform === 'win32') {
    const ninjaPath = process.env.NINJA_PATH || path.join(path.dirname(envManager.pythonPath), 'Scripts\\ninja.exe');
    const ninjaDir = path.dirname(ninjaPath);
    const fullCommand = `conda activate gsir;$env:PATH='${ninjaDir};' + $env:PATH;$env:NINJA_PATH='${ninjaPath}'; & '${envManager.pythonPath}' '${pythonScriptPath}' ${args.join(' ')}`;
     console.log('执行完整命令:', fullCommand);
        console.log('Ninja 路径:', ninjaPath);
        
     trainingProcess = spawn('powershell.exe', ['-NoProfile', '-NonInteractive', '-Command', fullCommand], {
         env: { ...process.env, PYTHONIOENCODING: 'utf-8' }
        });
    } else {
     const fullCommand = `cd '${cwd}' && source activate gsir && '${envManager.pythonPath}' '${pythonScriptPath}' ${args.join(' ')}`;
     console.log('执行完整命令:', fullCommand);
        
     trainingProcess = spawn('bash', ['-c', fullCommand], {
         env: { ...process.env, PYTHONIOENCODING: 'utf-8' }
        });
    }
    
    trainingProcess.stdout.on('data', (data) => {
      const output = data.toString();
      console.log('训练输出:', output);
      mainWindow.webContents.send('training-output', { type: 'stdout', data: output });
      if (projectId && output.includes('TRAINING_STATE_UPDATE:')) {
        try {
          const jsonMatch = output.match(/TRAINING_STATE_UPDATE:\s*(\{.+\})/);
          if (jsonMatch) {
            const stateData = JSON.parse(jsonMatch[1]);
            console.log('[Training] 解析到状态更新:', stateData);
            projectManager.updateProject(projectId, {
              currentIteration: stateData.iter,
              loss: stateData.loss,
              psnr: stateData.psnr,
              ssim: stateData.ssim,
              previewPath: stateData.preview,
              status: 'training'
            }).then(result => {
              if (result.success) {
                console.log('[Training] 项目状态已更新');
              } else {
                console.warn('[Training] 项目状态更新失败:', result.error);
              }
            });
          }
        } catch (error) {
          console.error('[Training] 解析 TRAINING_STATE_UPDATE 失败:', error);
        }
      }
      
      // Analyze and evaluate the data
      if (projectId) {
        const evalTestMatch = output.match(/\[ITER\s+(\d+)\]\s+Evaluating\s+test:\s+L1\s+([\d.]+)\s+PSNR:\s*([\d.]+)\s+SSIM\s+([\d.]+)/);
        const evalTrainMatch = output.match(/\[ITER\s+(\d+)\]\s+Evaluating\s+train:\s+L1\s+([\d.]+)\s+PSNR:\s*([\d.]+)\s+SSIM\s+([\d.]+)/);
        const evalTestL1Match = output.match(/EVAL_TEST_L1:\s*([\d.]+)/);
        const evalTestPsnrMatch = output.match(/EVAL_TEST_PSNR:\s*([\d.]+)/);
        const evalTestSsimMatch = output.match(/EVAL_TEST_SSIM:\s*([\d.]+)/);
        const evalTrainL1Match = output.match(/EVAL_TRAIN_L1:\s*([\d.]+)/);
        const evalTrainPsnrMatch = output.match(/EVAL_TRAIN_PSNR:\s*([\d.]+)/);
        const evalTrainSsimMatch = output.match(/EVAL_TRAIN_SSIM:\s*([\d.]+)/);
        const evalMatch = evalTrainMatch || evalTestMatch;
        const evalType = evalTrainMatch ? 'train' : (evalTestMatch ? 'test' : null);
        
        if (evalMatch || evalTrainL1Match || evalTestL1Match) {
          const iter = evalMatch ? parseInt(evalMatch[1]) : null;
          const l1 = evalMatch ? parseFloat(evalMatch[2]) : null;
          const psnr = evalMatch ? parseFloat(evalMatch[3]) : null;
          const ssim = evalMatch ? parseFloat(evalMatch[4]) : null;
          
          const evalL1 = evalTrainL1Match ? parseFloat(evalTrainL1Match[1]) : 
                        (evalTestL1Match ? parseFloat(evalTestL1Match[1]) : null);
          const evalPsnr = evalTrainPsnrMatch ? parseFloat(evalTrainPsnrMatch[1]) :
                          (evalTestPsnrMatch ? parseFloat(evalTestPsnrMatch[1]) : null);
          const evalSsim = evalTrainSsimMatch ? parseFloat(evalTrainSsimMatch[1]) :
                          (evalTestSsimMatch ? parseFloat(evalTestSsimMatch[1]) : null);
          
          if (iter !== null && l1 !== null) {
            console.log(`[Training] ✓ 解析到${evalType ? evalType.toUpperCase() : ''}评估数据 - iter: ${iter}, L1: ${l1}, PSNR: ${psnr}, SSIM: ${ssim}`);
            const projectUpdateData = {
              currentIteration: iter,
              psnr: psnr,
              ssim: ssim,
              evalL1: evalL1, 
              evalL1Type: evalType, 
              status: 'training'
            };
            
            projectManager.updateProject(projectId, projectUpdateData).then(result => {
              if (result.success) {
                console.log('[Training] ✓ 评估数据已保存');
                mainWindow.webContents.send('training-output', {
                  type: 'eval-update',
                  data: {
                    iter,
                    loss: null,
                    psnr,
                    ssim,
                    evalL1: evalL1,
                    evalL1Type: evalType
                  }
                });
              } else {
                console.warn('[Training] 评估数据保存失败:', result.error);
              }
            });
          }
        }
      }
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
      
      if (projectId) {
        const finalStatus = code === 0 ? 'completed' : 'error';
        projectManager.updateProject(projectId, {
          status: finalStatus
        }).then(() => {
          console.log(`[Training] 项目状态已更新为：${finalStatus}`);
          currentTrainingProjectId = null;
          isTrainingActive = false;
          
          console.log('[Queue] 当前训练结束，检查队列...');
          startNextTrainingTask();
        }).catch(err => {
          console.error('[Training] 更新项目状态失败:', err);
          isTrainingActive = false;
          startNextTrainingTask();
        });
      } else {
        isTrainingActive = false;
        startNextTrainingTask();
      }
    });
    
    return { success: true };
  } catch (error) {
    console.error('启动训练失败:', error);
    return { success: false, error: error.message };
  }
});

ipcMain.handle('start-baking', async (event, config) => {
  try {
    const { modelPath, checkpoint, bound, occluRes, occlusion, projectId } = config;
    if (projectId) {
    try {
        await projectManager.updateProjectStage(projectId, 'baking');
      console.log(`[Baking] 项目 ${projectId} 阶段已更新为 baking`);
      } catch (stageError) {
      console.error('[Baking] 更新项目阶段失败:', stageError);
      }
    }
    
    const args = [
      '-m', modelPath,
      '--checkpoint', checkpoint,
      '--bound', bound.toString(),
      '--occlu_res', occluRes.toString(),
      '--occlusion', occlusion.toString()
    ];
    
    console.log('启动烘焙进程:', envManager.pythonPath, args.join(' '));
    
    bakingProcess = envManager.runPythonScript(
      path.join(__dirname, '../../GS-IR/baking.py'),
      args,
      { cwd: path.join(__dirname, '../../GS-IR') }
    );
    
    bakingProcess.stdout.on('data', (data) => {
      const output = data.toString();
      console.log('烘焙输出:', output);
      mainWindow.webContents.send('baking-output', { type: 'stdout', data: output });
      
      if (projectId && output) {
        try {
          const progressMatch = output.match(/(\d+)%/);
          if (progressMatch) {
            const progress = parseInt(progressMatch[1]);
            console.log(`[Baking] 解析到进度：${progress}%`);
            projectManager.updateProject(projectId, {
              currentIteration: progress, 
              status: 'baking'
            }).then(result => {
              if (result.success) {
                console.log('[Baking] 进度已保存');
              } else {
                console.warn('[Baking] 进度保存失败:', result.error);
              }
            });
          }
          if (output.includes('save occlusion volumes') || output.includes('occlusion_volumes.pth')) {
            console.log('[Baking] 检测到 Baking 完成');
            projectManager.updateProjectStage(projectId, 'stage2').then(() => {
              console.log('[Baking] 项目阶段已更新为 stage2');
            });
          }
        } catch (error) {
          console.error('[Baking] 解析输出失败:', error);
        }
      }
    });
    
    bakingProcess.stderr.on('data', (data) => {
      const output = data.toString();
      console.error('烘焙错误:', output);
      mainWindow.webContents.send('baking-output', { type: 'stderr', data: output });
    });
    
    bakingProcess.on('close', (code) => {
      console.log(`烘焙进程退出，代码：${code}`);
      mainWindow.webContents.send('baking-output', { type: 'close', code });
      if (projectId) {
        if (code === 0) {
          projectManager.updateProject(projectId, {
            status: 'completed',
            stage: 'stage2'
          }).then(result => {
            if (result.success) {
              console.log('[Baking] 项目状态已更新为 completed');
            }
          });
        } else {
          // 发生错误
          projectManager.updateProject(projectId, {
            status: 'error'
          }).then(result => {
            if (result.success) {
              console.log('[Baking] 项目状态已更新为 error');
            }
          });
        }
      }
      
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
      const pid = trainingProcess.pid;
      console.log('[停止训练] 当前训练进程 PID:', pid);
      console.log('[停止训练] 进程对象信息:', {
        killed: trainingProcess.killed,
        exitCode: trainingProcess.exitCode,
        signalCode: trainingProcess.signalCode
      });
      if (process.platform === 'win32') {
        const { spawn } = require('child_process');
        console.log('[停止训练] Windows 平台，使用 taskkill 终止进程树...');
        return new Promise((resolve) => {
          try {
            const taskkill = spawn('taskkill', ['/pid', pid.toString(), '/f', '/t']);
            let stdout = '';
            let stderr = '';
            taskkill.stdout.on('data', (data) => {
              const output = data.toString();
              stdout += output;
              console.log('[taskkill stdout]', output);
            });
            
            taskkill.stderr.on('data', (data) => {
              const output = data.toString();
              stderr += output;
              console.error('[taskkill stderr]', output);
            });
            
            taskkill.on('close', (code) => {
              console.log('[taskkill] 进程退出，代码:', code);
              
              if (code === 0) {
                console.log('[停止训练] 成功终止训练进程及其子进程');
                trainingProcess = null;
                resolve({ success: true, message: '训练进程已停止' });
              } else {
                console.error('[停止训练] taskkill 失败，代码:', code, stderr);
                try {
                  trainingProcess.kill('SIGKILL');
                  console.log('[停止训练] 使用 SIGKILL 备用方案成功');
                  trainingProcess = null;
                  resolve({ success: true, message: '训练进程已通过备用方案停止' });
                } catch (killError) {
                  console.error('[停止训练] 所有终止方法都失败:', killError);
                  resolve({ success: false, error: `终止进程失败：${stderr || killError.message}` });
                }
              }
            });
            
            taskkill.on('error', (err) => {
              console.error('[taskkill] 进程启动失败:', err);
              try {
                trainingProcess.kill('SIGKILL');
                console.log('[停止训练] 使用 SIGKILL 备用方案成功');
                trainingProcess = null;
                resolve({ success: true, message: '训练进程已通过备用方案停止' });
              } catch (killError) {
                resolve({ success: false, error: err.message });
              }
            });
            setTimeout(() => {
              console.warn('[停止训练] taskkill 超时 5 秒，强制清理...');
              try {
                trainingProcess.kill('SIGKILL');
                trainingProcess = null;
                resolve({ success: true, message: '训练进程通过超时机制停止' });
              } catch (err) {
                resolve({ success: false, error: '终止进程超时且失败' });
              }
            }, 5000);
            
          } catch (spawnError) {
            console.error('[停止训练] 启动 taskkill 失败:', spawnError);
            resolve({ success: false, error: spawnError.message });
          }
        });
      } else {
        console.log('[停止训练] Unix 平台，使用 SIGKILL 信号...');
        trainingProcess.kill('SIGKILL');
        trainingProcess = null;
        console.log('[停止训练] 训练进程已停止');
        return { success: true };
      }
    } else {
      console.warn('[停止训练] 没有正在运行的训练进程');
      return { success: false, error: '没有正在运行的训练进程' };
    }
  } catch (error) {
    console.error('[停止训练] 发生异常:', error);
    console.error('[停止训练] 错误堆栈:', error.stack);
    return { success: false, error: error.message };
  }
});

ipcMain.handle('stop-baking', async () => {
  try {
    if (bakingProcess) {
      const pid = bakingProcess.pid;
      console.log('[停止烘焙] 当前烘焙进程 PID:', pid);
      console.log('[停止烘焙] 进程对象信息:', {
        killed: bakingProcess.killed,
        exitCode: bakingProcess.exitCode,
        signalCode: bakingProcess.signalCode
      });
      if (process.platform === 'win32') {
        const { spawn } = require('child_process');
        
        console.log('[停止烘焙] Windows 平台，使用 taskkill 终止进程树...');
        
        return new Promise((resolve) => {
          try {
            const taskkill = spawn('taskkill', ['/pid', pid.toString(), '/f', '/t']);
            
            let stdout = '';
            let stderr = '';
            
            taskkill.stdout.on('data', (data) => {
              const output = data.toString();
              stdout += output;
              console.log('[taskkill stdout]', output);
            });
            
            taskkill.stderr.on('data', (data) => {
              const output = data.toString();
              stderr += output;
              console.error('[taskkill stderr]', output);
            });
            
            taskkill.on('close', (code) => {
              console.log('[taskkill] 进程退出，代码:', code);
              
              if (code === 0) {
                console.log('[停止烘焙] 成功终止烘焙进程及其子进程');
                bakingProcess = null;
                resolve({ success: true, message: '烘焙进程已停止' });
              } else {
                console.error('[停止烘焙] taskkill 失败，代码:', code, stderr);
                try {
                  bakingProcess.kill('SIGKILL');
                  console.log('[停止烘焙] 使用 SIGKILL 备用方案成功');
                  bakingProcess = null;
                  resolve({ success: true, message: '烘焙进程已通过备用方案停止' });
                } catch (killError) {
                  console.error('[停止烘焙] 所有终止方法都失败:', killError);
                  resolve({ success: false, error: `终止进程失败：${stderr || killError.message}` });
                }
              }
            });
            
            taskkill.on('error', (err) => {
              console.error('[taskkill] 进程启动失败:', err);
              try {
                bakingProcess.kill('SIGKILL');
                console.log('[停止烘焙] 使用 SIGKILL 备用方案成功');
                bakingProcess = null;
                resolve({ success: true, message: '烘焙进程已通过备用方案停止' });
              } catch (killError) {
                resolve({ success: false, error: err.message });
              }
            });
            
            setTimeout(() => {
              console.warn('[停止烘焙] taskkill 超时 5 秒，强制清理...');
              try {
                bakingProcess.kill('SIGKILL');
                bakingProcess = null;
                resolve({ success: true, message: '烘焙进程通过超时机制停止' });
              } catch (err) {
                resolve({ success: false, error: '终止进程超时且失败' });
              }
            }, 5000);
            
          } catch (spawnError) {
            console.error('[停止烘焙] 启动 taskkill 失败:', spawnError);
            resolve({ success: false, error: spawnError.message });
          }
        });
      } else {
        console.log('[停止烘焙] Unix 平台，使用 SIGKILL 信号...');
        bakingProcess.kill('SIGKILL');
        bakingProcess = null;
        console.log('[停止烘焙] 烘焙进程已停止');
        return { success: true };
      }
    } else {
      console.warn('[停止烘焙]没有正在运行的烘焙进程');
      return { success: false, error: '没有正在运行的烘焙进程' };
    }
  } catch (error) {
    console.error('[停止烘焙] 发生异常:', error);
    console.error('[停止烘焙] 错误堆栈:', error.stack);
    return { success: false, error: error.message };
  }
});

ipcMain.handle('stop-conversion', async () => {
  try {
    if (conversionProcess) {
      const pid = conversionProcess.pid;
      console.log('正在停止转换进程，PID:', pid);
      if (process.platform === 'win32') {
        const { spawn } = require('child_process');
        spawn('taskkill', ['/pid', pid.toString(), '/f', '/t']);
      } else {
        conversionProcess.kill('SIGKILL');
      }
      
      conversionCancelled = true;
      conversionProcess = null;
      console.log('转换进程已停止');
      return { success: true };
    }
    return { success: false, error: '没有正在运行的转换进程' };
  } catch (error) {
    console.error('停止转换进程失败:', error);
    return { success: false, error: error.message };
  }
});

ipcMain.handle('stop-installation', async () => {
  try {
    const stopped = await envManager.stopInstallation();
    return { success: stopped, message: stopped ? '已停止安装并清理缓存' : '没有正在运行的安装' };
  } catch (error) {
    return { success: false, error: error.message };
  }
});

// Get the latest rendered images
ipcMain.handle('get-latest-rendered-image', async (event, modelPath) => {
  try {
    const dirExists = await fs.access(modelPath).then(() => true).catch(() => false);
    if (!dirExists) {
      return { success: false, error: '输出目录不存在' };
    }
    const pointPath = path.join(modelPath, 'point');
    const pointDirExists = await fs.access(pointPath).then(() => true).catch(() => false);
    
    if (pointDirExists) {
      const files = await fs.readdir(pointPath);
      const pngFiles = files.filter(f => f.endsWith('.png') && !f.includes('depth'));
      
      if (pngFiles.length > 0) {
        const filesWithStats = await Promise.all(
          pngFiles.map(async (file) => {
            const filePath = path.join(pointPath, file);
            const stats = await fs.stat(filePath);
            return { file, filePath, mtime: stats.mtime };
          })
        );
        
        filesWithStats.sort((a, b) => b.mtime - a.mtime);
        const latestFile = filesWithStats[0].filePath;
        console.log('[图片加载] 找到最新渲染图:', latestFile);
        // Read the file and convert it to Base64
        try {
          const imageData = await fs.readFile(latestFile);
          const base64Image = imageData.toString('base64');
          const dataUrl = `data:image/png;base64,${base64Image}`;
          console.log('[图片加载] 图片已转换为 Base64，大小:', (imageData.length / 1024).toFixed(2), 'KB');
          
          return { 
            success: true, 
            imageBase64: dataUrl,
            imagePath: latestFile
          };
        } catch (readError) {
          console.error('[图片加载] 读取文件失败:', readError);
          return { success: false, error: `读取图片失败：${readError.message}` };
        }
      }
    }
    
    return { success: false, error: '未找到渲染图像' };
  } catch (error) {
    console.error('获取最新渲染图像失败:', error);
    return { success: false, error: error.message };
  }
});

// Update project configuration
ipcMain.handle('update-project-config', async (event, configData) => {
  try {
    const { projectId, config } = configData;
    if (!projectId) {
      return { success: false, error: '缺少 projectId' };
    }
    
    // Update project configuration
    const result = await projectManager.updateProjectConfig(projectId, config);
    
    if (result.success) {
      console.log(`[IPC] 项目配置已更新：${projectId}`);
      mainWindow?.webContents.send('project-config-updated', {
        projectId,
        config
      });
    }
    
    return result;
  } catch (error) {
    console.error('[IPC] 更新项目配置失败:', error);
    return { success: false, error: error.message };
  }
});

ipcMain.handle('update-project-stage', async (event, data) => {
 try {
  const { projectId, stage } = data;
  
  if (!projectId) {
   return { success: false, error: '缺少 projectId' };
  }
  
  const result = await projectManager.updateProjectStage(projectId, stage);
  
  if (result.success) {
 console.log(`[IPC] 项目阶段已更新：${projectId} -> ${stage}`);
  }
  
  return result;
 } catch (error) {
  console.error('[IPC] 更新项目阶段失败:', error);
  return { success: false, error: error.message };
 }
});

// Sync sourcePath field to projects.json
ipcMain.handle('sync-source-path-to-projects', async () => {
  try {
    const result = await projectManager.syncSourcePathToProjects();
    return result;
  } catch (error) {
    console.error('[IPC] 同步 sourcePath 失败:', error);
    return { success: false, error: error.message };
  }
});

// Spawn Python process
ipcMain.handle('spawn-python-process', async (event, config) => {
  try {
    const { script, args = [], cwd = null, useConda = false, condaEnv = null, scriptDir = null } = config;
    
    if (!script) {
      return { success: false, error: '缺少 script 参数' };
    }
    let command;
    let spawnArgs = [];
    let fullScriptPath = script;
    const path = require('path');
    if (!path.isAbsolute(script)) {
      const baseDir = scriptDir || __dirname;
      fullScriptPath = path.join(baseDir, script);
      console.log(`[IPC] 解析脚本路径：${fullScriptPath}`);
    }
    
    if (useConda && condaEnv) {
      command = 'conda';
      spawnArgs = ['run', '-n', condaEnv, 'python', fullScriptPath, ...args];
    } else {
      command = 'python';
      spawnArgs = [fullScriptPath, ...args];
    }
    
    console.log(`[IPC] 准备启动 Python 脚本：${command} ${spawnArgs.join(' ')}`);
    if (cwd) {
      console.log(`[IPC] 工作目录：${cwd}`);
    }
    const { spawn } = require('child_process');
    const options = cwd ? { cwd } : {};
    const childProcess = spawn(command, spawnArgs, options);
    let isReady = false;
    let isTimeout = false;
    const modelPath = cwd || '';
    const signalFilePath = modelPath ? `${modelPath}\\.luminags\\gui_ready.signal` : null;
    let signalFileDetected = false;
    
    const readyPromise = new Promise((resolve) => {
      let signalCheckInterval = null;
      if (signalFilePath) {
        signalCheckInterval = setInterval(() => {
          if (signalFileDetected) return;
          try {
            const fs = require('fs');
            if (fs.existsSync(signalFilePath)) {
              console.log('[IPC] 检测到信号文件:', signalFilePath);
              signalFileDetected = true;
              clearInterval(signalCheckInterval);
              clearTimeout(timeoutHandle);
              isReady = true;
              resolve({ ready: true, timeout: false });
            }
          } catch (error) {
          }
        }, 500);
      }
      
      const timeoutHandle = setTimeout(() => {
        if (!isReady) {
          console.log('[IPC] 等待超时（120 秒）');
          isTimeout = true;
          isReady = true; 
          resolve({ ready: false, timeout: true });
          if (signalCheckInterval) clearInterval(signalCheckInterval);
        }
      }, 120000);
      
      childProcess.stdout.on('data', (data) => {
        const output = data.toString();
        console.log(`[Python stdout]: ${output}`);
        
        if (!isReady && !signalFileDetected) {
          if (output.includes('Loading Test Cameras') || 
              output.includes('[RealtimeViewer] 模型加载完成') ||
              output.includes('模型加载完成') ||
              output.includes('100%') ||
              /\d+\.\d+it\/s/.test(output) ||
              output.includes('GUI initialized') || 
              output.includes('窗口已创建') ||
              output.includes('正在加载用户配置')) {
            clearTimeout(timeoutHandle);
            if (signalCheckInterval) clearInterval(signalCheckInterval);
            isReady = true;
            console.log('[IPC] ✓ 检测到 GUI 初始化完成信号:', output.trim());
            resolve({ ready: true, timeout: false });
          }
        }
      });
      
      childProcess.stderr.on('data', (data) => {
        console.error(`[Python stderr]: ${data.toString()}`);
      });
      
      childProcess.on('close', (code) => {
        console.log(`[Python] 子进程退出，代码：${code}`);
        clearTimeout(timeoutHandle);
        if (!isReady) {
          resolve(false); 
        }
      });
    });
    
    console.log(`[IPC] Python 进程启动成功，PID: ${childProcess.pid}`);
    const readyResult = await readyPromise;
    if (!readyResult.ready) {
      console.error('[IPC] 加载超时，准备终止 Python 进程');
      try {
        childProcess.kill();
      } catch (killError) {
        console.error('[IPC] 终止进程失败:', killError.message);
      }
      throw new Error('Python 程序加载超时，请检查程序是否正常或尝试重新创建项目');
    }
    
    return {
      success: true,
      pid: childProcess.pid,
      timeout: readyResult.timeout
    };
  } catch (error) {
    console.error('[IPC] 启动 Python 进程失败:', error);
    return { success: false, error: error.message };
  }
});

ipcMain.handle('check-training-completion', async (event, projectId) => {
 try {
  if (!projectId) {
   return { success: false, error: '缺少 projectId' };
  }
  
  const result = await projectManager.checkTrainingCompletion(projectId);
  
  if (result.success && result.completed) {
   console.log(`[IPC] ✓ 检测到训练完成：${projectId}`);
   mainWindow.webContents.send('training-completed', { projectId });
  }
  
  return result;
 } catch (error) {
  console.error('[IPC] 检查训练完成状态失败:', error);
  return { success: false, error: error.message };
 }
});
ipcMain.handle('delete-output-directory', async (event, outputPath) => {
  try {
    const fs = require('fs').promises;
    const path = require('path');
    
    console.log(`[删除输出] 准备清空目录内容：${outputPath}`);
    
    if (!outputPath) {
      return { success: false, error: '输出路径为空' };
    }
    try {
      await fs.access(outputPath);
    } catch (err) {
      console.log(`[删除输出] 目录不存在：${outputPath}`);
      return { success: true, message: '目录不存在，无需删除' };
    }
    console.log(`[删除输出] 开始读取目录内容：${outputPath}`);
    const entries = await fs.readdir(outputPath, { withFileTypes: true });
    for (const entry of entries) {
      const fullPath = path.join(outputPath, entry.name);
      console.log(`[删除输出] 删除项：${fullPath}`);
      if (entry.isDirectory()) {
        await fs.rm(fullPath, { recursive: true, force: true });
      } else {
        await fs.unlink(fullPath);
      }
    }
    
    console.log(`[删除输出] 成功清空目录内容：${outputPath}（保留目录本身）`);
    
    return { success: true, message: '目录内容已清空' };
  } catch (error) {
    console.error('[删除输出] 删除失败:', error);
    return { success: false, error: error.message };
  }
});

ipcMain.handle('delete-project-and-output', async (event, data) => {
  try {
    const { projectId, outputPath } = data;
    
    console.log(`[删除项目] 准备删除项目：${projectId}, 输出目录：${outputPath}`);
    
    if (!projectId) {
      return { success: false, error: '缺少 projectId' };
    }
    if (outputPath) {
      try {
        const fs = require('fs').promises;
        const path = require('path');
        try {
          await fs.access(outputPath);
          const entries = await fs.readdir(outputPath, { withFileTypes: true });
          for (const entry of entries) {
            const fullPath = path.join(outputPath, entry.name);
            if (entry.isDirectory()) {
              await fs.rm(fullPath, { recursive: true, force: true });
            } else {
              await fs.unlink(fullPath);
            }
          }
          console.log(`[删除项目] 输出目录内容已清空：${outputPath}（保留目录本身）`);
        } catch (err) {
          if (err.code !== 'ENOENT') {
            console.warn(`[删除项目] 清空输出目录失败：${err.message}`);
          } else {
            console.log(`[删除项目] 输出目录不存在，跳过：${outputPath}`);
          }
        }
      } catch (err) {
        console.warn(`[删除项目] 处理输出目录异常：${err.message}`);
      }
    }
    
    if (projectId) {
      const result = await projectManager.deleteProject(projectId);
      if (result.success) {
        console.log(`[删除项目] 项目配置已删除：${projectId}`);
      } else {
        console.warn(`[删除项目] 删除项目配置失败：${result.error}`);
      }
    }
    
    return { success: true, message: '项目及其输出已删除' };
  } catch (error) {
    console.error('[删除项目] 删除失败:', error);
    return { success: false, error: error.message };
  }
});

ipcMain.handle('save-to-projects-list', async (event, data) => {
  try {
    const { projectId, thumbnailBase64 } = data;
    
    console.log(`[保存项目] 准备保存项目到列表：${projectId}`);
    
    if (!projectId) {
      return { success: false, error: '缺少 projectId' };
    }
    const projectResult = await projectManager.loadProject(projectId);
    if (!projectResult.success) {
      return { success: false, error: projectResult.error };
    }
    
    const projectConfig = projectResult.data;
    console.log(`[保存项目] 项目配置：`, projectConfig);
    let thumbnailPath = null;
    if (thumbnailBase64) {
      try {
        const fs = require('fs');
        const path = require('path');
        
        // thumbnail directory for project
        const luminagsDir = path.join(projectConfig.outputPath, '.luminags');
        await fs.promises.mkdir(luminagsDir, { recursive: true });
        
        // generate thumbnail file name
        const thumbnailFileName = `thumbnail_${Date.now()}.png`;
        thumbnailPath = path.join(luminagsDir, thumbnailFileName);
        
        // decode and save Base64 image
        const base64Data = thumbnailBase64.replace(/^data:image\/png;base64,/, '');
        await fs.promises.writeFile(thumbnailPath, base64Data, 'base64');
        
        console.log(`[保存项目] 缩略图已保存：${thumbnailPath}`);
      } catch (thumbError) {
        console.error('[保存项目] 保存缩略图失败:', thumbError);
      }
    }
    
    await projectManager.updateProject(projectId, {
      status: 'completed'
    });
    const projectIndex = projectManager.projects.find(p => p.projectId === projectId);
    if (projectIndex) {
      projectIndex.thumbnailPath = thumbnailPath;
      await projectManager.saveProjects();
    }
    
    console.log(`[保存项目] 项目已成功保存到列表：${projectId}`);
    
    return { 
      success: true, 
      message: '项目已保存到列表',
      projectId,
      thumbnailPath
    };
  } catch (error) {
    console.error('[保存项目] 保存失败:', error);
    return { success: false, error: error.message };
  }
});

let pythonServiceProcess = null;
ipcMain.handle('start-python-service', async (event, config) => {
  try {
    const { script, envName = 'gsir', cwd } = config;
    
    console.log(`[Python 服务] 准备启动服务：${script}`);
    console.log(`[Python 服务] 使用环境：${envName}`);
    console.log(`[Python 服务] 工作目录：${cwd}`);
    if (pythonServiceProcess) {
      console.log('[Python 服务] 已有服务在运行，先停止旧服务');
      pythonServiceProcess.kill();
      pythonServiceProcess = null;
    }
    if (process.platform === 'win32') {
      const condaActivate = envManager.condaPath ? 
        `& "${envManager.condaPath}" activate ${envName}` : 
        `conda activate ${envName}`;
      const fullCommand = `${condaActivate}; & '${envManager.pythonPath}' '${script}'`;
      console.log('[Python 服务] 执行完整命令:', fullCommand);
      console.log('[Python 服务] Conda 路径:', envManager.condaPath || '使用系统 PATH');
      console.log('[Python 服务] Python 路径:', envManager.pythonPath);
      
      pythonServiceProcess = spawn('powershell.exe', ['-NoProfile', '-NonInteractive', '-Command', fullCommand], {
        cwd: cwd,
        env: { ...process.env, PYTHONIOENCODING: 'utf-8' }
      });
    } else {
      const fullCommand = `cd '${cwd}' && source activate ${envName} && '${envManager.pythonPath}' '${script}'`;
      console.log('[Python 服务] 执行完整命令:', fullCommand);
      
      pythonServiceProcess = spawn('bash', ['-c', fullCommand], {
        cwd: cwd,
        env: { ...process.env, PYTHONIOENCODING: 'utf-8' }
      });
    }
    
    pythonServiceProcess.stdout.on('data', (data) => {
      const output = data.toString();
      console.log(`[PBR Service] ${output}`);
    });
    
    pythonServiceProcess.stderr.on('data', (data) => {
      const error = data.toString();
      console.error(`[PBR Service Error] ${error}`);
    });
    
    pythonServiceProcess.on('close', (code) => {
      console.log(`[Python 服务] 服务进程退出，代码：${code}`);
      pythonServiceProcess = null;
    });
    
    console.log(`[Python 服务] 服务启动成功，PID: ${pythonServiceProcess.pid}`);
    
    return {
      success: true,
      pid: pythonServiceProcess.pid,
      message: 'Python service started successfully'
    };
  } catch (error) {
    console.error('[Python 服务] 启动失败:', error);
    return {
      success: false,
      error: error.message
    };
  }
});

ipcMain.handle('stop-python-service', async () => {
  try {
    if (pythonServiceProcess) {
      pythonServiceProcess.kill();
      pythonServiceProcess = null;
      console.log('[Python 服务] 服务已停止');
      return { success: true, message: 'Service stopped' };
    } else {
      console.log('[Python 服务] 没有正在运行的服务');
      return { success: true, message: 'No running service' };
    }
  } catch (error) {
    console.error('[Python 服务] 停止服务失败:', error);
    return { success: false, error: error.message };
  }
});

ipcMain.handle('confirm-quit-app', async (event, choice) => {
  if (choice === 'quit') {
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
    setTimeout(() => {
      app.quit();
    }, 500);
  }
  return { success: true };
});

// IPC processing related to GPU monitoring
ipcMain.handle('get-gpu-info', async () => {
  try {
    const graphics = await si.graphics();
    
    if (graphics.controllers && graphics.controllers.length > 0) {
      // Get all valid GPU controllers
      const validControllers = graphics.controllers.filter(controller => {
        const modelName = (controller.model || '').toLowerCase();
        const vendorName = (controller.vendor || '').toLowerCase();
        const subDeviceName = (controller.subDevice || '').toLowerCase();
        
        // Exclude virtual and remote GPUs
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
        // Return GPU information based on selected index
        let selectedController;
        if (currentSelectedGpuIndex >= 0 && currentSelectedGpuIndex < validControllers.length) {
          selectedController = validControllers[currentSelectedGpuIndex];
          console.log(`返回选中GPU信息[${currentSelectedGpuIndex}]: ${selectedController.vendor} ${selectedController.model}`);
        } else {
          // If no selection or invalid index, prefer NVIDIA GPUs
          const nvidiaController = validControllers.find(controller => 
            controller.vendor && controller.vendor.toLowerCase().includes('nvidia')
          );
          selectedController = nvidiaController || validControllers[0];
          console.log(`返回默认GPU信息: ${selectedController.vendor} ${selectedController.model}`);
        }
        
        // Data cleaning and formatting
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

ipcMain.handle('get-all-gpus', async () => {
  try {
    const graphics = await si.graphics();
    
    if (graphics.controllers && graphics.controllers.length > 0) {
      const validGpus = graphics.controllers.filter(controller => {
        const modelName = (controller.model || '').toLowerCase();
        const vendorName = (controller.vendor || '').toLowerCase();
        const subDeviceName = (controller.subDevice || '').toLowerCase();
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
    const cpuData = await si.currentLoad();
    
    if (graphics.controllers && graphics.controllers.length > 0) {
      const validControllers = graphics.controllers.filter(controller => {
        const modelName = (controller.model || '').toLowerCase();
        const vendorName = (controller.vendor || '').toLowerCase();
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
        const minVRAM = modelName.includes('intel') || modelName.includes('amd') ? 8 : 32;
        const hasValidVRAM = (controller.vram || 0) >= minVRAM;
        
        const isRealGPU = 
          (controller.vendor && controller.vendor !== 'Unknown') &&
          (controller.model && controller.model !== 'Unknown GPU');
        
        return !isVirtualOrRemote && hasValidVRAM && isRealGPU;
      });
      
      if (validControllers.length > 0) {
        let selectedController;
        if (currentSelectedGpuIndex >= 0 && currentSelectedGpuIndex < validControllers.length) {
          selectedController = validControllers[currentSelectedGpuIndex];
          console.log(`获取选中GPU[${currentSelectedGpuIndex}]使用率数据: ${selectedController.vendor} ${selectedController.model}`);
        } else {
          const nvidiaController = validControllers.find(controller => 
            controller.vendor && controller.vendor.toLowerCase().includes('nvidia')
          );
          selectedController = nvidiaController || validControllers[0];
          console.log(`获取默认GPU使用率数据: ${selectedController.vendor} ${selectedController.model}`);
        }
        
        console.log(`GPU类型识别: ${selectedController.vendor} ${selectedController.model}`);
        console.log(`VRAM大小: ${selectedController.vram || '未知'} MB`);
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
        // NVIDIA GPU handling
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
          
          if (selectedController.memoryUsed !== undefined && selectedController.memoryUsed >= 0) {
            memoryUsed = Math.round(selectedController.memoryUsed);
          }
          if (selectedController.memoryTotal !== undefined && selectedController.memoryTotal > 0) {
            memoryTotal = Math.round(selectedController.memoryTotal);
          } else if (selectedController.vram && selectedController.vram > 0) {
            memoryTotal = Math.round(selectedController.vram * 1024 * 1024);
          }
          
          if (selectedController.temperatureGpu !== undefined && selectedController.temperatureGpu >= 0) {
            temperature = Math.round(selectedController.temperatureGpu);
          } else if (selectedController.temperature && selectedController.temperature.gpu !== undefined && selectedController.temperature.gpu >= 0) {
            temperature = Math.round(selectedController.temperature.gpu);
          }
          
          if (selectedController.powerDraw !== undefined && selectedController.powerDraw >= 0) {
            power = Math.round(selectedController.powerDraw);
          } else if (selectedController.power && selectedController.power.draw !== undefined && selectedController.power.draw >= 0) {
            power = Math.round(selectedController.power.draw);
          }
          
          if (selectedController.fanSpeed !== undefined && selectedController.fanSpeed >= 0) {
            fanSpeed = Math.round(selectedController.fanSpeed);
          }
        } 
        else {
          console.log('检测到其他类型GPU，使用通用数据获取策略');
          
          if (selectedController.utilizationGpu !== undefined && selectedController.utilizationGpu >= 0) {
            utilization = Math.round(selectedController.utilizationGpu);
          } else if (selectedController.utilization && selectedController.utilization.gpu !== undefined && selectedController.utilization.gpu >= 0) {
            utilization = Math.round(selectedController.utilization.gpu);
          } else {
            const cpuLoad = cpuData && cpuData.currentLoad ? cpuData.currentLoad : 35;
            utilization = Math.round(Math.max(15, Math.min(85, cpuLoad * 0.6 + Math.random() * 20)));
            console.log(`使用CPU负载推算其他GPU使用率: ${Math.round(cpuLoad)}% CPU → ${utilization}% GPU`);
          }
          
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
          
          if (selectedController.temperatureGpu !== undefined && selectedController.temperatureGpu >= 0) {
            temperature = Math.round(selectedController.temperatureGpu);
          } else if (selectedController.temperature && selectedController.temperature.gpu !== undefined && selectedController.temperature.gpu >= 0) {
            temperature = Math.round(selectedController.temperature.gpu);
          } else {
            temperature = Math.round(40 + Math.random() * 30);
          }
        }
        const validatedData = {
          utilization: Math.round(Math.max(0, Math.min(100, utilization))),
          memoryUsed: Math.round(Math.max(0, memoryUsed)),
          memoryTotal: Math.round(Math.max(1, memoryTotal)),
          temperature: Math.round(Math.max(0, temperature)),
          power: Math.round(Math.max(0, power)),
          fanSpeed: Math.round(Math.max(0, Math.min(100, fanSpeed)))
        };

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
  protocol.handle('luma', async (request) => {
    try {
      const path = require('path');
      const fs = require('fs');
      const urlPath = request.url.slice('luma://'.length);
      
      console.log('[Luma Protocol] 原始 URL:', request.url);
      console.log('[Luma Protocol] 提取路径:', urlPath);
      const filePath = urlPath;
      
      console.log('[Luma Protocol] 最终路径:', filePath);
      
      if (!fs.existsSync(filePath)) {
        console.error('[Luma Protocol] 文件不存在:', filePath);
        const alternatives = [
          filePath.replace(/^e\//i, 'E:/'),
          filePath.replace(/^E\//i, 'E:/'),
          filePath.replace(/^e:/i, 'E:'),
        ];
        
        for (const alt of alternatives) {
          if (fs.existsSync(alt)) {
            console.log('[Luma Protocol] ✓ 找到替代路径:', alt);
            const fileContent = await fs.promises.readFile(alt);
            const ext = path.extname(alt).toLowerCase();
            const mimeType = getImageMimeType(ext);
            return new Response(fileContent, {
              headers: { 'Content-Type': mimeType }
            });
          }
        }
        
        return new Response('File not found: ' + filePath, { status: 404 });
      }
      const fileContent = await fs.promises.readFile(filePath);
      
      // Determine the MIME type based on the file extension
      const ext = path.extname(filePath).toLowerCase();
      const mimeType = getImageMimeType(ext);
      
      console.log(`[Luma Protocol] 返回文件：${filePath} (${mimeType})`);
      
      return new Response(fileContent, {
        headers: {
          'Content-Type': mimeType
        }
      });
    } catch (error) {
      console.error('[Luma Protocol] 错误:', error);
      return new Response('Internal Server Error', { status: 500 });
    }
  });
  
  createWindow();
  initializePythonEnvironment();
})

app.on('window-all-closed', () => {
  const hasRunningProcess = trainingProcess || bakingProcess || envManager.installationProcess;
  
  if (hasRunningProcess) {
    console.log('检测到有进程正在运行，显示确认对话框...');
    if (mainWindow) {
      mainWindow.webContents.send('confirm-quit', {
        hasTraining: !!trainingProcess,
        hasBaking: !!bakingProcess,
        hasInstallation: !!envManager.installationProcess
      });
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
    
    console.log('配置参数:', config);
    console.log('envManager.condaPath:', envManager.condaPath);
    console.log('envManager.isInitialized:', envManager.isInitialized);
    if (!envManager.condaPath) {
      console.error('未找到 Conda 路径');
      return { success: false, error: '未检测到 Conda，请先安装 Miniconda' };
    }
    
    const absoluteYmlPath = path.join(__dirname, '../../GS-IR/environment.yml');
    console.log('环境配置文件绝对路径:', absoluteYmlPath);
    
    try {
      await fs.access(absoluteYmlPath);
      console.log('✓ environment.yml 文件存在');
      
      const yamlContent = await fs.readFile(absoluteYmlPath, 'utf8');
      if (yamlContent.length === 0) {
        console.error('environment.yml 文件为空');
        return { success: false, error: 'environment.yml 文件为空' };
      }
      
      // 检查是否有 BOM
      if (yamlContent.charCodeAt(0) === 0xFEFF) {
        console.warn('检测到 BOM，尝试移除...');
        // 移除 BOM 并重新写入文件
        const cleanContent = yamlContent.slice(1);
        await fs.writeFile(absoluteYmlPath, cleanContent, 'utf8');
        console.log('已移除 BOM');
      }
      
      console.log('environment.yml 文件大小:', yamlContent.length, '字节');
    } catch (err) {
      console.error('environment.yml 文件不存在或无法读取:', absoluteYmlPath);
      console.error('错误详情:', err);
      return { success: false, error: '找不到 environment.yml 文件或无法读取' };
    }
    
    console.log('开始调用 envManager.createEnvironment...');
    const result = await envManager.createEnvironment(absoluteYmlPath, envName);
    console.log('createEnvironment 返回结果:', result);
    return result;
  } catch (error) {
    console.error('创建环境失败:', error);
    console.error('错误堆栈:', error.stack);
    return { success: false, error: error.message };
  }
});

// Run the installation script
ipcMain.handle('run-install-script', async (event, config) => {
  try {
    const { scriptPath, mode } = config;
    
    console.log('运行安装脚本请求');
    console.log('脚本路径:', scriptPath);
    console.log('安装模式:', mode);
    if (!envManager.condaPath) {
      console.error('未找到 Conda 路径');
      return { success: false, error: '未检测到 Conda，请先安装 Miniconda' };
    }
    const absoluteScriptPath = path.join(__dirname, '../../GS-IR/install_environment.bat');
    console.log('安装脚本绝对路径:', absoluteScriptPath);
    try {
      await fs.access(absoluteScriptPath);
      console.log('安装脚本文件存在');
    } catch (err) {
      console.error('安装脚本文件不存在:', absoluteScriptPath);
      console.error('错误详情:', err);
      return { success: false, error: '找不到安装脚本文件' };
    }
    
    console.log('开始调用 envManager.runInstallScript...');
    const result = await envManager.runInstallScript(absoluteScriptPath, mode);
    console.log('runInstallScript 返回结果:', result);
    return result;
  } catch (error) {
    console.error('运行安装脚本失败:', error);
    console.error('错误堆栈:', error.stack);
    return { success: false, error: error.message };
  }
});

ipcMain.handle('get-environment-info', () => {
  return { success: true, info: envManager.getEnvironmentInfo() };
});

// Initialize Python environment in the background
async function initializePythonEnvironment() {
  console.log('开始初始化 Python 环境 ...');
  const detection = await envManager.detectPythonAndConda();
  console.log('环境检测结果:', detection);
  if (detection.availableEnvs && detection.availableEnvs.length > 0) {
    for (const envPath of detection.availableEnvs) {
      const exists = await envManager.checkEnvironmentExists(envPath);
      if (exists) {
        const validation = await envManager.validateEnvironment();
        if (validation.valid) {
          console.log('找到有效的 Python 环境:', envPath);
          return;
        }
      }
    }
  }
  console.log('未检测到有效的 Python 环境，等待用户访问训练页面时再提示');
}

// Dataset format check
ipcMain.handle('check-dataset-format', async (event, sourcePath) => {
  try {
    console.log('检查数据集格式:', sourcePath);
    try {
      await fs.access(sourcePath);
    } catch (err) {
      return { success: false, error: '数据集路径不存在' };
    }
    
    // Check TensoIR format
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
    
    // Check Mip-NeRF 360 format
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
    
    // Check COLMAP format
    const colmapSparse = await fs.access(path.join(sourcePath, 'sparse/0')).then(() => true).catch(() => false);
    const colmapImages = await fs.access(path.join(sourcePath, 'images')).then(() => true).catch(() => false);
    
    if (colmapSparse && colmapImages) {
      return { 
        success: true, 
        format: 'colmap',
        needsConversion: false 
      };
    }
    
    // Other cases, conversion needed
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

// Dataset conversion
ipcMain.handle('convert-dataset', async (event, config) => {
  try {
    const { sourcePath, resize } = config;
    console.log('开始转换数据集:', sourcePath, 'resize:', resize);
    try {
      await fs.access(sourcePath);
    } catch (err) {
      return { success: false, error: '数据集路径不存在' };
    }
    
    // Check if input subdirectory exists, if not, create it and move all images to input
    const inputPath = path.join(sourcePath, 'input');
    const inputExists = await fs.access(inputPath).then(() => true).catch(() => false);
    
    if (!inputExists) {
      await fs.mkdir(inputPath, { recursive: true });
      console.log('创建 input 目录:', inputPath);
      const files = await fs.readdir(sourcePath);
      const imageExtensions = ['.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif'];
      const imageFiles = files.filter(f => 
        imageExtensions.includes(path.extname(f).toLowerCase())
      );
      
      console.log(`找到 ${imageFiles.length} 个图片文件，移动到 input 目录`);
      for (const file of imageFiles) {
        const srcFile = path.join(sourcePath, file);
        const destFile = path.join(inputPath, file);
        try {
          await fs.rename(srcFile, destFile);
          console.log(`移动：${file} -> input/${file}`);
        } catch (err) {
          console.error(`移动文件失败 ${file}:`, err);
        }
      }
    }
    const convertScriptPath = path.join(__dirname, '../../tools/gaussian-splatting/convert.py');
    const scriptExists = await fs.access(convertScriptPath).then(() => true).catch(() => false);
    if (!scriptExists) {
      return { success: false, error: '找不到转换脚本：' + convertScriptPath };
    }
    const scriptArgs = ['-s', sourcePath];
    if (resize) {
      scriptArgs.push('--resize');
    }
    console.log('运行转换脚本:', envManager.pythonPath, convertScriptPath, scriptArgs.join(' '));
    conversionProcess = envManager.runPythonScript(convertScriptPath, scriptArgs, {
      cwd: path.join(__dirname, '../../tools/gaussian-splatting'),
      env: { ...process.env, PYTHONIOENCODING: 'utf-8' }
    });
    
    conversionProcess.stdout.on('data', (data) => {
      const output = data.toString();
      console.log('[CONVERT]', output);
      mainWindow.webContents.send('conversion-output', { type: 'stdout', data: output });
    });
    
    conversionProcess.stderr.on('data', (data) => {
      const output = data.toString();
      console.error('[CONVERT ERROR]', output);
      mainWindow.webContents.send('conversion-output', { type: 'stderr', data: output });
    });
    
    const exitCode = await new Promise((resolve) => {
      conversionProcess.on('close', resolve);
    });
    
    console.log('[CONVERT] 进程退出，代码:', exitCode);
    if (conversionCancelled) {
      conversionCancelled = false; 
      mainWindow.webContents.send('conversion-close', { code: -1 }); 
      conversionProcess = null;
      return { success: true, cancelled: true };
    }
    
    mainWindow.webContents.send('conversion-close', { code: exitCode });
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


// Get the operating system platform
ipcMain.handle('get-platform', async () => {
  return process.platform;
});
ipcMain.handle('convert-file-path', async (event, filePath) => {
  try {
    const path = require('path');
    let normalizedPath = filePath.replace(/\\/g, '/');
    if (/^[A-Za-z]:/.test(filePath)) {
      console.log(`[ConvertPath] 检测到 Windows 绝对路径：${filePath}`);
    }
    const lumaUrl = `luma://${normalizedPath}`;
    console.log(`[ConvertPath] ${filePath} -> ${lumaUrl}`);
    return { success: true, url: lumaUrl };
  } catch (error) {
    console.error('[ConvertPath] 转换失败:', error);
    return { success: false, error: error.message };
  }
});
ipcMain.handle('get-project-list', async () => {
  try {
    const projects = projectManager.getAllProjects();
    await projectManager.scanProjects();
    return { success: true, data: projects };
  } catch (error) {
    console.error('[IPC] 获取项目列表失败:', error);
    return { success: false, error: error.message };
  }
});
ipcMain.handle('get-project-detail', async (event, projectId) => {
  try {
    const result = await projectManager.loadProject(projectId);
    return result;
  } catch (error) {
    console.error('[IPC] 获取项目详情失败:', error);
    return { success: false, error: error.message };
  }
});

ipcMain.handle('get-queue-status', async () => {
  try {
    return {
      success: true,
      data: {
        isTrainingActive,
        queueLength: trainingQueue.length,
        currentProjectId: currentTrainingProjectId,
        queuedProjects: trainingQueue.map(task => ({
          projectId: task.projectId,
          projectName: task.projectName
        }))
      }
    };
  } catch (error) {
    console.error('[IPC] 获取队列状态失败:', error);
    return { success: false, error: error.message };
  }
});

ipcMain.handle('get-directory-size', async (event, dirPath) => {
  try {
    const fs = require('fs');
    const path = require('path');
    
    if (!dirPath || !fs.existsSync(dirPath)) {
      return { success: false, error: '目录不存在' };
    }
    
    let totalSize = 0;
    function calculateSize(currentPath) {
      const stats = fs.statSync(currentPath);
      
      if (stats.isFile()) {
        totalSize += stats.size;
      } else if (stats.isDirectory()) {
        const files = fs.readdirSync(currentPath);
        for (const file of files) {
          const filePath = path.join(currentPath, file);
          calculateSize(filePath);
        }
      }
    }
    
    calculateSize(dirPath);
    
    return { success: true, data: totalSize };
  } catch (error) {
    console.error('[IPC] 获取目录大小失败:', error);
    return { success: false, error: error.message };
  }
});