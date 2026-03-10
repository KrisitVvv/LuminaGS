const { app, BrowserWindow, Menu, ipcMain, dialog } = require('electron');
const si = require('systeminformation');
const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs').promises;
const PythonEnvironmentManager = require('./pythonEnvironment');
const ProjectManager = require('./projectManager');

Menu.setApplicationMenu(null);
let mainWindow = null;
const isPackaged = app.isPackaged;

// 初始化 Python 环境管理器
const envManager = new PythonEnvironmentManager();

// 将 mainWindow 暴露给全局，供环境管理模块使用
global.mainWindow = null;

// 初始化项目管理器
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
      // 允许加载本地文件
      webviewTag: true,
      // 允许跨域请求本地文件
      sandbox: false
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

// 存储当前选中的 GPU 索引
let currentSelectedGpuIndex = -1;

// 存储当前训练进程
let trainingProcess = null;
let bakingProcess = null;
let conversionProcess = null;
let conversionCancelled = false; // 标记转换是否被用户取消

// 当前正在训练的项目 ID
let currentTrainingProjectId = null;

// 训练任务队列管理
const trainingQueue = [];
let isTrainingActive = false; // 标记是否有训练正在进行

// 从队列中启动下一个训练任务
async function startNextTrainingTask() {
  if (trainingQueue.length === 0 || isTrainingActive) {
    return;
  }
  
  isTrainingActive = true;
  const nextTask = trainingQueue.shift(); // 获取第一个任务
  
  try {
    console.log('[Queue] 启动队列中的下一个任务:', nextTask.projectName);
    
    // 更新项目状态为训练中
    if (nextTask.projectId) {
      await projectManager.updateProjectStatus(nextTask.projectId, 'training');
      currentTrainingProjectId = nextTask.projectId;
    }
    
    // 通知前端任务开始
    mainWindow.webContents.send('training-queue-update', {
      type: 'task-started',
      projectId: nextTask.projectId,
      projectName: nextTask.projectName
    });
    
    // 执行实际的训练启动逻辑（直接在这里调用原逻辑）
    await startTrainingProcess(nextTask.config, nextTask.projectId);
  } catch (error) {
    console.error('[Queue] 启动队列任务失败:', error);
    if (nextTask.projectId) {
      await projectManager.updateProjectStatus(nextTask.projectId, 'error');
    }
    isTrainingActive = false;
    startNextTrainingTask(); // 尝试启动下一个
  }
}

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
      projectName // 新增：项目名称
    } = config;
    
    // 创建项目（如果提供了项目名称）
    let projectId = null;
    let projectConfigFile = null;
    if (projectName) {
      console.log('[Training] 创建项目:', projectName);
      const projectResult = await projectManager.createProject({
        projectName,
        outputPath: modelPath,
        sourcePath,
        stage: checkpoint ? 'stage2' : 'stage1',
        totalIterations: iterations,
        resolution,
        evalMode,
        gamma,
        indirect,
        bound: config.bound || 1.5,
        occluRes: config.occluRes || 128,
        occlusion: config.occlusion || 0.01,
        checkpoint  // 新增：传递 checkpoint 参数
      });
      
      if (projectResult.success) {
        projectId = projectResult.projectId;
        projectConfigFile = projectResult.configFile;
        currentTrainingProjectId = projectId;
        console.log('[Training] 项目创建成功:', projectId);
      } else {
        console.warn('[Training] 项目创建失败，继续训练:', projectResult.error);
      }
    }
    
    // 实现队列逻辑：如果有训练正在进行，将任务加入队列
    if (isTrainingActive && trainingProcess) {
      console.log('[Queue] 训练正在进行中，将任务加入队列');
      
      // 将任务加入队列
      trainingQueue.push({
        config,
        projectId,
        projectName: projectName || '未命名'
      });
      
      // 更新项目状态为等待中
      if (projectId) {
        await projectManager.updateProjectStatus(projectId, 'waiting');
      }
      
      // 通知前端任务已进入队列
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
        
    // 检查输出目录是否为空
    try {
      const dirExists = await fs.access(modelPath).then(() => true).catch(() => false);
      if (dirExists) {
        const files = await fs.readdir(modelPath);
        if (files.length > 0) {
          // 输出目录非空，需要用户确认
          const result = await dialog.showMessageBox(mainWindow, {
            type: 'warning',
            buttons: ['继续训练', '取消'],
            defaultId: 1,
            title: '输出目录非空',
            message: `输出目录 "${modelPath}" 非空（包含 ${files.length} 个文件）。`,
            detail: '继续训练可能会覆盖现有文件。是否继续？',
          });
          
          if (result.response !== 0) {
            return { success: false, error: '用户取消了训练' };
          }
        }
      }
    } catch (err) {
      // 目录不存在是正常的，不需要处理
      console.log('输出目录不存在，将创建新目录');
    }
    
    // 检查数据集格式是否需要转换
    mainWindow.webContents.send('training-output', { 
      type: 'stdout', 
      data: '\n========== 数据集格式检查 ==========\n' 
    });
    
    // 检查关键目录是否存在
    const sparsePath = path.join(sourcePath, 'sparse/0');
    const imagesPath = path.join(sourcePath, 'images');
    
    const sparseExists = await fs.access(sparsePath).then(() => true).catch(() => false);
    const imagesExists = await fs.access(imagesPath).then(() => true).catch(() => false);
    
    let needsConversion = false;
    
    if (!sparseExists || !imagesExists) {
      needsConversion = true;
      mainWindow.webContents.send('training-output', { 
        type: 'stdout', 
        data: '⚠ 需要运行 convert.py 进行数据集转换\n' 
      });
      
      mainWindow.webContents.send('training-output', { 
        type: 'stdout', 
        data: '开始执行 python convert.py -s ' + sourcePath + '\n\n' 
      });
      
      // 准备转换脚本参数
      const convertScriptPath = path.join(__dirname, '../../tools/gaussian-splatting/convert.py');
      const convertArgs = ['-s', sourcePath];
      
      // 验证脚本文件是否存在
      const scriptExists = await fs.access(convertScriptPath).then(() => true).catch(() => false);
      if (!scriptExists) {
        throw new Error(`找不到转换脚本：${convertScriptPath}`);
      }
      
      mainWindow.webContents.send('training-output', { 
        type: 'stdout', 
        data: `转换脚本：${convertScriptPath}\n` 
      });
      
      // 运行转换脚本 - 只执行 python convert.py -s <filedir>
      const convertProcess = envManager.runPythonScript(convertScriptPath, convertArgs, {
        cwd: path.join(__dirname, '../../tools/gaussian-splatting'),
        env: { ...process.env, PYTHONIOENCODING: 'utf-8' }
      });
      
      // 等待转换完成
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
    
    // 构建命令参数
    const args = [
      '-m', modelPath,
      '-s', sourcePath,
      '--iterations', iterations.toString()
    ];
    
    // 添加图片子目录参数
    if (imageSubdir && imageSubdir !== 'images') {
      args.push('-i', imageSubdir);
    }
    
    if (evalMode) args.push('--eval');
    if (gamma) args.push('--gamma');
    if (indirect) args.push('--indirect');
    
    // 处理分辨率参数
    // 根据实际使用的 imageSubdir 和 resolution 决定 -r 参数
    // - 如果使用 images 目录（原图），-r = resolution（完整的压缩比例）
    // - 如果使用 images_X 目录（已压缩），-r = resolution / X（二次压缩）
    let finalResolutionParam = null;
    if (resolution && resolution > 1) {
      finalResolutionParam = resolution;
          
      // 如果使用了预压缩目录，需要调整 -r 参数
      if (imageSubdir === 'images_2' && resolution === 2) {
        // 1/2 分辨率 + images_2 目录：不需要额外压缩
        finalResolutionParam = 1;
      } else if (imageSubdir === 'images_4') {
        if (resolution === 4) {
          // 1/4 分辨率 + images_4 目录：不需要额外压缩
          finalResolutionParam = 1;
        } else if (resolution === 8) {
          // 1/8 分辨率 + images_4 目录：需要再压缩 2 倍
          finalResolutionParam = 2;
        } else if (resolution === 16) {
          // 1/16 分辨率 + images_4 目录：需要再压缩 4 倍
          finalResolutionParam = 4;
        }
      } else if (imageSubdir === 'images_8') {
        if (resolution === 8) {
          // 1/8 分辨率 + images_8 目录：不需要额外压缩
          finalResolutionParam = 1;
        } else if (resolution === 16) {
          // 1/16 分辨率 + images_8 目录：需要再压缩 2 倍
          finalResolutionParam = 2;
        }
      }
      // 其他情况（使用 images 目录）：finalResolutionParam = resolution
          
      if (finalResolutionParam > 1) {
        args.push('-r', finalResolutionParam.toString());
      }
    }
    
    // 输出调试信息
    console.log(`分辨率设置：目标=${resolution}, imageSubdir="${imageSubdir}", 实际 -r 参数=${finalResolutionParam || '未设置'}`);
    mainWindow.webContents.send('training-output', { 
      type: 'stdout', 
      data: `📊 分辨率配置：目标 1/${resolution} | 使用目录：${imageSubdir} | -r 参数：${finalResolutionParam || '1(不压缩)'}\n` 
    });
    
    if (checkpoint) {
      args.push('--start_checkpoint', checkpoint);
    }
    
    console.log('启动训练进程:', envManager.pythonPath, args.join(' '));
    
    // 标记训练已激活
    isTrainingActive = true;
    
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
      
      // 解析 TRAINING_STATE_UPDATE 消息并更新项目状态
      if (projectId && output.includes('TRAINING_STATE_UPDATE:')) {
        try {
          const jsonMatch = output.match(/TRAINING_STATE_UPDATE:\s*(\{.+\})/);
          if (jsonMatch) {
            const stateData = JSON.parse(jsonMatch[1]);
            console.log('[Training] 解析到状态更新:', stateData);
            
            // 更新项目状态（注意：每 100 次迭代时 psnr/ssim 为 null）
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
      
      // ⚠️ 解析评估数据（每 1000 次迭代）
      // 注意：Python 会输出 test 和 train 两次评估，我们只解析一次
      if (projectId) {
        // 尝试匹配 test 或 train 的评估行
        const evalTestMatch = output.match(/\[ITER\s+(\d+)\]\s+Evaluating\s+test:\s+L1\s+([\d.]+)\s+PSNR:\s*([\d.]+)\s+SSIM\s+([\d.]+)/);
        const evalTrainMatch = output.match(/\[ITER\s+(\d+)\]\s+Evaluating\s+train:\s+L1\s+([\d.]+)\s+PSNR:\s*([\d.]+)\s+SSIM\s+([\d.]+)/);
        
        // 解析 EVAL_TEST_* 和 EVAL_TRAIN_* 指标
        const evalTestL1Match = output.match(/EVAL_TEST_L1:\s*([\d.]+)/);
        const evalTestPsnrMatch = output.match(/EVAL_TEST_PSNR:\s*([\d.]+)/);
        const evalTestSsimMatch = output.match(/EVAL_TEST_SSIM:\s*([\d.]+)/);
        
        const evalTrainL1Match = output.match(/EVAL_TRAIN_L1:\s*([\d.]+)/);
        const evalTrainPsnrMatch = output.match(/EVAL_TRAIN_PSNR:\s*([\d.]+)/);
        const evalTrainSsimMatch = output.match(/EVAL_TRAIN_SSIM:\s*([\d.]+)/);
        
        // ⚠️ 优先使用 train 评估（更准确），如果没有则使用 test 评估
        const evalMatch = evalTrainMatch || evalTestMatch;
        const evalType = evalTrainMatch ? 'train' : (evalTestMatch ? 'test' : null);
        
        if (evalMatch || evalTrainL1Match || evalTestL1Match) {
          const iter = evalMatch ? parseInt(evalMatch[1]) : null;
          const l1 = evalMatch ? parseFloat(evalMatch[2]) : null;
          const psnr = evalMatch ? parseFloat(evalMatch[3]) : null;
          const ssim = evalMatch ? parseFloat(evalMatch[4]) : null;
          
          // 从 EVAL_*_L1 等提取评估 L1（独立指标）
          const evalL1 = evalTrainL1Match ? parseFloat(evalTrainL1Match[1]) : 
                        (evalTestL1Match ? parseFloat(evalTestL1Match[1]) : null);
          const evalPsnr = evalTrainPsnrMatch ? parseFloat(evalTrainPsnrMatch[1]) :
                          (evalTestPsnrMatch ? parseFloat(evalTestPsnrMatch[1]) : null);
          const evalSsim = evalTrainSsimMatch ? parseFloat(evalTrainSsimMatch[1]) :
                          (evalTestSsimMatch ? parseFloat(evalTestSsimMatch[1]) : null);
          
          // ⚠️ 只在第一次解析到时处理（避免重复）
          if (iter !== null && l1 !== null) {
            console.log(`[Training] ✓ 解析到${evalType ? evalType.toUpperCase() : ''}评估数据 - iter: ${iter}, L1: ${l1}, PSNR: ${psnr}, SSIM: ${ssim}`);
            
            // 更新项目状态，包含 PSNR、SSIM 和评估 L1
            // ⚠️ 注意：loss 字段应该已经在 TRAINING_STATE_UPDATE 中设置过了
            // 这里只更新 PSNR、SSIM 和 Eval L1
            const projectUpdateData = {
              currentIteration: iter,
              psnr: psnr,
              ssim: ssim,
              evalL1: evalL1,  // 评估 L1（单独保存）
              evalL1Type: evalType,  // 'test' 或 'train'
              status: 'training'
              // ✅ 注意：不包含 loss 字段，避免覆盖常规训练的 Loss
            };
            
            projectManager.updateProject(projectId, projectUpdateData).then(result => {
              if (result.success) {
                console.log('[Training] ✓ 评估数据已保存');
                
                // 同时发送一个补充的 TRAINING_STATE_UPDATE 给前端
                // ⚠️ 注意：使用闭包中的变量 evalL1 和 l1Type
                mainWindow.webContents.send('training-output', {
                  type: 'eval-update',
                  data: {
                    iter,
                    loss: null,  // ✅ 明确设置为 null，不使用评估 L1
                    psnr,
                    ssim,
                    evalL1: evalL1,  // 评估 L1
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
      
      // 更新项目状态为完成
      if (projectId) {
        const finalStatus = code === 0 ? 'completed' : 'error';
        projectManager.updateProject(projectId, {
          status: finalStatus
        }).then(() => {
          console.log(`[Training] 项目状态已更新为：${finalStatus}`);
          currentTrainingProjectId = null;
          isTrainingActive = false;
          
          // 启动队列中的下一个任务
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
    // 检查环境是否就绪
    const validation = await envManager.validateEnvironment();
    if (!validation.valid) {
      throw new Error(`Python 环境未就绪：${validation.error}`);
    }
    
    const { modelPath, checkpoint, bound, occluRes, occlusion, projectId } = config;
      
    // 如果有 projectId，更新项目阶段为 baking
    if (projectId) {
    try {
        await projectManager.updateProjectStage(projectId, 'baking');
      console.log(`[Baking] 项目 ${projectId} 阶段已更新为 baking`);
      } catch (stageError) {
      console.error('[Baking] 更新项目阶段失败:', stageError);
        // 不阻断后续流程
      }
    }
    
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
    console.log('===== 收到停止训练请求 =====');
    
    if (trainingProcess) {
      const pid = trainingProcess.pid;
      console.log('[停止训练] 当前训练进程 PID:', pid);
      console.log('[停止训练] 进程对象信息:', {
        killed: trainingProcess.killed,
        exitCode: trainingProcess.exitCode,
        signalCode: trainingProcess.signalCode
      });
      
      // Windows 上使用 taskkill 强制终止进程树
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
                // 尝试备用方案：直接 kill
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
              // 尝试备用方案
              try {
                trainingProcess.kill('SIGKILL');
                console.log('[停止训练] 使用 SIGKILL 备用方案成功');
                trainingProcess = null;
                resolve({ success: true, message: '训练进程已通过备用方案停止' });
              } catch (killError) {
                resolve({ success: false, error: err.message });
              }
            });
            
            // 设置超时，防止 taskkill 挂起
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
        // Unix/Linux/macOS 平台
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
    console.log('===== 收到停止烘焙请求 =====');
    
    if (bakingProcess) {
      const pid = bakingProcess.pid;
      console.log('[停止烘焙] 当前烘焙进程 PID:', pid);
      console.log('[停止烘焙] 进程对象信息:', {
        killed: bakingProcess.killed,
        exitCode: bakingProcess.exitCode,
        signalCode: bakingProcess.signalCode
      });
      
      // Windows 上使用 taskkill 强制终止进程树
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
                console.log('[停止烘焙] ✓ 成功终止烘焙进程及其子进程');
                bakingProcess = null;
                resolve({ success: true, message: '烘焙进程已停止' });
              } else {
                console.error('[停止烘焙] ✗ taskkill 失败，代码:', code, stderr);
                // 尝试备用方案：直接 kill
                try {
                  bakingProcess.kill('SIGKILL');
                  console.log('[停止烘焙] 使用 SIGKILL 备用方案成功');
                  bakingProcess = null;
                  resolve({ success: true, message: '烘焙进程已通过备用方案停止' });
                } catch (killError) {
                  console.error('[停止烘焙] ✗ 所有终止方法都失败:', killError);
                  resolve({ success: false, error: `终止进程失败：${stderr || killError.message}` });
                }
              }
            });
            
            taskkill.on('error', (err) => {
              console.error('[taskkill] 进程启动失败:', err);
              // 尝试备用方案
              try {
                bakingProcess.kill('SIGKILL');
                console.log('[停止烘焙] 使用 SIGKILL 备用方案成功');
                bakingProcess = null;
                resolve({ success: true, message: '烘焙进程已通过备用方案停止' });
              } catch (killError) {
                resolve({ success: false, error: err.message });
              }
            });
            
            // 设置超时，防止 taskkill 挂起
            setTimeout(() => {
              console.warn('[停止烘焙] ⚠ taskkill 超时 5 秒，强制清理...');
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
        // Unix/Linux/macOS 平台
        console.log('[停止烘焙] Unix 平台，使用 SIGKILL 信号...');
        bakingProcess.kill('SIGKILL');
        bakingProcess = null;
        console.log('[停止烘焙] ✓ 烘焙进程已停止');
        return { success: true };
      }
    } else {
      console.warn('[停止烘焙] ⚠ 没有正在运行的烘焙进程');
      return { success: false, error: '没有正在运行的烘焙进程' };
    }
  } catch (error) {
    console.error('[停止烘焙] ✗ 发生异常:', error);
    console.error('[停止烘焙] 错误堆栈:', error.stack);
    return { success: false, error: error.message };
  }
});

ipcMain.handle('stop-conversion', async () => {
  try {
    if (conversionProcess) {
      const pid = conversionProcess.pid;
      console.log('正在停止转换进程，PID:', pid);
      
      // Windows 上使用 taskkill 强制终止进程树
      if (process.platform === 'win32') {
        const { spawn } = require('child_process');
        spawn('taskkill', ['/pid', pid.toString(), '/f', '/t']);
      } else {
        conversionProcess.kill('SIGKILL');
      }
      
      conversionCancelled = true; // 标记为用户主动取消
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

// 停止环境安装
ipcMain.handle('stop-installation', async () => {
  try {
    const stopped = await envManager.stopInstallation();
    return { success: stopped, message: stopped ? '已停止安装并清理缓存' : '没有正在运行的安装' };
  } catch (error) {
    return { success: false, error: error.message };
  }
});

// 获取最新渲染图像
ipcMain.handle('get-latest-rendered-image', async (event, modelPath) => {
  try {
    // 检查路径是否存在
    const dirExists = await fs.access(modelPath).then(() => true).catch(() => false);
    if (!dirExists) {
      return { success: false, error: '输出目录不存在' };
    }
    
    // 查找 point 文件夹中的渲染图像
    const pointPath = path.join(modelPath, 'point');
    const pointDirExists = await fs.access(pointPath).then(() => true).catch(() => false);
    
    if (pointDirExists) {
      const files = await fs.readdir(pointPath);
      const pngFiles = files.filter(f => f.endsWith('.png') && !f.includes('depth'));
      
      if (pngFiles.length > 0) {
        // 按修改时间排序，获取最新的图像
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
        
        // 读取文件并转换为 Base64
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

// 更新项目配置（实时自动保存）
ipcMain.handle('update-project-config', async (event, configData) => {
  try {
    const { projectId, config } = configData;
    
    // 验证必填字段
    if (!projectId) {
      return { success: false, error: '缺少 projectId' };
    }
    
    // 调用 ProjectManager 更新配置
    const result = await projectManager.updateProjectConfig(projectId, config);
    
    if (result.success) {
      console.log(`[IPC] 项目配置已更新：${projectId}`);
      // 通知所有窗口配置已更新
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

// 更新项目阶段
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
    
    // 检查是否有 input 子目录，如果没有，创建它并将所有图片移动到 input
    const inputPath = path.join(sourcePath, 'input');
    const inputExists = await fs.access(inputPath).then(() => true).catch(() => false);
    
    if (!inputExists) {
      // 创建 input 目录
      await fs.mkdir(inputPath, { recursive: true });
      console.log('创建 input 目录:', inputPath);
      
      // 获取所有图片文件
      const files = await fs.readdir(sourcePath);
      const imageExtensions = ['.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif'];
      const imageFiles = files.filter(f => 
        imageExtensions.includes(path.extname(f).toLowerCase())
      );
      
      console.log(`找到 ${imageFiles.length} 个图片文件，移动到 input 目录`);
      
      // 移动图片到 input 目录
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
    
    // 直接使用 Python 执行 convert.py 脚本
    const convertScriptPath = path.join(__dirname, '../../tools/gaussian-splatting/convert.py');
    
    // 检查脚本文件是否存在
    const scriptExists = await fs.access(convertScriptPath).then(() => true).catch(() => false);
    if (!scriptExists) {
      return { success: false, error: '找不到转换脚本：' + convertScriptPath };
    }
    
    // 构建命令参数
    const scriptArgs = ['-s', sourcePath];
    if (resize) {
      scriptArgs.push('--resize');
    }
    
    console.log('运行转换脚本:', envManager.pythonPath, convertScriptPath, scriptArgs.join(' '));
    
    // 启动转换进程 - 使用 Python 环境管理器执行
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
    
    // 检查是否是用户主动取消
    if (conversionCancelled) {
      conversionCancelled = false; // 重置标志
      mainWindow.webContents.send('conversion-close', { code: -1 }); // 发送特殊代码表示取消
      conversionProcess = null;
      return { success: true, cancelled: true }; // 返回成功但标记为取消
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

// ==================== 项目管理相关 IPC ====================

// 获取所有项目列表
ipcMain.handle('get-project-list', async () => {
  try {
    const projects = projectManager.getAllProjects();
    // 扫描并更新项目状态
    await projectManager.scanProjects();
    return { success: true, data: projects };
  } catch (error) {
    console.error('[IPC] 获取项目列表失败:', error);
    return { success: false, error: error.message };
  }
});

// 获取单个项目详情
ipcMain.handle('get-project-detail', async (event, projectId) => {
  try {
    const result = await projectManager.loadProject(projectId);
    return result;
  } catch (error) {
    console.error('[IPC] 获取项目详情失败:', error);
    return { success: false, error: error.message };
  }
});

// 获取队列状态
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