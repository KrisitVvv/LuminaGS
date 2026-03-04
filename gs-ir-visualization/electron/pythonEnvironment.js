const { spawn } = require('child_process');
const fs = require('fs').promises;
const path = require('path');
const os = require('os');

class PythonEnvironmentManager {
  constructor() {
    this.pythonPath = null;
    this.condaPath = null;
    this.envName = 'gsir';
    this.envPath = null;
    this.isInitialized = false;
    this.installationProcess = null; // 当前安装进程
    this.cleanupInProgress = false;
  }

  // 检测系统 Python 和 Conda
  async detectPythonAndConda() {
    console.log('[DEBUG] 开始检测 Python 和 Conda...');
        
    const results = {
      python: null,
      conda: null,
      availableEnvs: []
    };
    
    // 检测 Conda
    try {
      console.log('[DEBUG] 开始检测 Conda...');
      const condaPath = await this.findExecutable('conda');
      console.log('[DEBUG] Conda 检测结果:', condaPath);
          
      if (condaPath) {
        results.conda = condaPath;
        this.condaPath = condaPath;
            
        // 获取所有 conda 环境
        console.log('[DEBUG] 开始获取 conda 环境列表...');
        const envs = await this.getCondaEnvironments();
        console.log('[DEBUG] 获取到的环境列表:', envs);
            
        // 检查是否有 gsir 环境
        const gsirEnv = envs.find(env => env.includes('gsir') || env.endsWith('envs\\gsir'));
        console.log('[DEBUG] 查找 gsir 环境:', gsirEnv);
            
        if (gsirEnv) {
          console.log('[DEBUG] 找到 gsir 环境:', gsirEnv);
          // 验证环境是否有效
          const isValid = await this.checkEnvironmentExists(gsirEnv);
          console.log('[DEBUG] gsir 环境有效性:', isValid);
              
          if (isValid) {
            // 验证环境依赖
            const validation = await this.validateEnvironment();
            console.log('[DEBUG] 环境依赖验证结果:', validation);
                
            if (validation.valid) {
              console.log('[DEBUG] ✓ 找到有效的 gsir 环境');
              this.isInitialized = true;
              this.envPath = gsirEnv;
              results.availableEnvs = [gsirEnv];
              return results; // 已有有效环境，直接返回
            }
          }
        }
            
        results.availableEnvs = envs;
      } else {
        console.warn('[DEBUG] 未找到 Conda');
      }
    } catch (error) {
      console.error('[DEBUG] 检测 Conda 失败:', error);
    }
    
    // 检测系统 Python
    try {
      console.log('[DEBUG] 开始检测 Python...');
      const pythonPath = await this.findExecutable('python');
      console.log('[DEBUG] Python 检测结果:', pythonPath);
          
      if (pythonPath) {
        results.python = pythonPath;
      }
    } catch (error) {
      console.error('[DEBUG] 检测 Python 失败:', error);
    }
    
    console.log('[DEBUG] 最终检测结果:', results);
    return results;
  }
  async findExecutable(name) {
    const platform = process.platform;
    const pathsToCheck = process.env.PATH.split(path.delimiter);
    
    for (const dir of pathsToCheck) {
      const executablePath = path.join(dir, platform === 'win32' ? `${name}.exe` : name);
      try {
        await fs.access(executablePath);
        return executablePath;
      } catch {
        continue;
      }
    }
    
    return null;
  }

  // 获取 Conda 环境列表
  async getCondaEnvironments() {
    if (!this.condaPath) return [];

    console.log('[DEBUG] 使用 conda 路径:', this.condaPath);

    return new Promise((resolve) => {
      const child = process.platform === 'win32'
        ? spawn('cmd.exe', ['/c', this.condaPath, 'env', 'list', '--json'])
        : spawn(this.condaPath, ['env', 'list', '--json']);

      let output = '';
      let errorOutput = '';
      
      child.stdout.on('data', (data) => {
        const msg = data.toString();
        output += msg;
        console.log('[DEBUG] conda env list stdout:', msg.substring(0, 200));
      });

      child.stderr.on('data', (data) => {
        errorOutput += data.toString();
        console.error('[DEBUG] conda env list stderr:', data.toString());
      });

      child.on('close', (code) => {
        console.log(`[DEBUG] conda env list 退出代码：${code}`);
        if (code === 0) {
          try {
            const envs = JSON.parse(output);
            console.log('[DEBUG] 解析到的环境列表:', envs.envs);
            resolve(envs.envs || []);
          } catch (parseError) {
            console.error('[DEBUG] JSON 解析失败:', parseError);
            console.error('[DEBUG] 原始输出:', output);
            resolve([]);
          }
        } else {
          console.error('[DEBUG] conda env list 失败，错误输出:', errorOutput);
          resolve([]);
        }
      });
    });
  }

  // 检查指定环境是否存在
  async checkEnvironmentExists(envPath) {
    console.log(`[DEBUG] 检查环境是否存在：${envPath}`);
    try {
      const pythonExe = process.platform === 'win32' 
        ? path.join(envPath, 'python.exe')
        : path.join(envPath, 'bin', 'python');
      
      console.log(`[DEBUG] 检查 Python 路径：${pythonExe}`);
      
      await fs.access(pythonExe);
      console.log(`[DEBUG] 环境存在：${envPath}`);
      this.envPath = envPath;
      this.pythonPath = pythonExe;  // 确保设置 pythonPath
      console.log(`[DEBUG] 已设置 pythonPath: ${this.pythonPath}`);
      return true;
    } catch (error) {
      console.error(`[DEBUG] 环境不存在或无法访问：${envPath}`, error.message);
      return false;
    }
  }

  // 创建 Conda 环境
  async createEnvironment(ymlPath, envName = 'gsir') {
    if (!this.condaPath) {
      throw new Error('未找到 Conda');
    }

    const envDir = path.join(os.homedir(), '.miniconda3', 'envs', envName);
    this.envPath = envDir;
    this.pythonPath = process.platform === 'win32'
      ? path.join(envDir, 'python.exe')
      : path.join(envDir, 'bin', 'python');

    return new Promise((resolve, reject) => {
      const args = [
        'env', 'create',
        '-n', envName,
        '-f', ymlPath,
        '-y'
      ];

      console.log('创建 Conda 环境:', this.condaPath, args.join(' '));

      // 发送开始安装的消息
      if (global.mainWindow) {
        global.mainWindow.webContents.send('environment-progress', {
          type: 'info',
          data: `开始创建 conda 环境：${envName}...`
        });
      }

      const child = process.platform === 'win32'
        ? spawn('cmd.exe', ['/c', this.condaPath, ...args], {
            env: { ...process.env, PYTHONUTF8: '1' }
          })
        : spawn(this.condaPath, args, {
            env: { ...process.env, PYTHONUTF8: '1' }
          });

      // 保存当前安装进程引用
      this.installationProcess = child;

      let output = '';
      let errorOutput = '';
      let hasError = false;

      child.stdout.on('data', (data) => {
        const msg = data.toString();
        output += msg;
              
        // 实时解析输出，提取进度信息
        if (global.mainWindow) {
          // 先移除所有的退格符组合（\b\b\ 等）
          const cleanedMsg = msg.replace(/\x08+/g, '');
                
          // 过滤加载动画字符（\ | / - 以及带退格符的版本）
          const loadingAnimationPatterns = [
            /^\s*[\\|\/-]\s*$/,      // 单独的加载字符
            /^\s*[\\|\/-]\s+\d+%/ ,  // 加载字符 + 百分比
            /^\s*\.\.\.*\s*$/,       // 省略号
            /^[\x08\s]+$/,           // 纯退格符和空白
          ];
                
          const isAnimation = loadingAnimationPatterns.some(pattern => pattern.test(cleanedMsg.trim()));
                
          if (!isAnimation) {
            // 发送清理后的输出（过滤动画和退格符）
            global.mainWindow.webContents.send('environment-progress', {
              type: 'stdout',
              data: cleanedMsg
            });
          }
          
          // 解析进度百分比并发送 info 消息
          const progressPatterns = [
            /\[(\d+)%\]/,
            /Progress:\s*(\d+)%/i,
            /Completed:\s*(\d+)%/i,
            /Extracting:\s*(\d+)%/i
          ];
          
          for (const pattern of progressPatterns) {
            const match = msg.match(pattern);
            if (match) {
              const percent = parseInt(match[1]);
              global.mainWindow.webContents.send('environment-progress', {
                type: 'info',
                data: `当前进度：${percent}%`
              });
              break;
            }
          }
          
          // 检测关键阶段并发送提示
          if (msg.includes('Solving environment')) {
            global.mainWindow.webContents.send('environment-progress', {
              type: 'info',
              data: '正在解决环境依赖...'
            });
          } else if (msg.includes('Preparing transaction')) {
            global.mainWindow.webContents.send('environment-progress', {
              type: 'info',
              data: '正在准备事务...'
            });
          } else if (msg.includes('Verifying transaction')) {
            global.mainWindow.webContents.send('environment-progress', {
              type: 'info',
              data: '正在验证事务...'
            });
          } else if (msg.includes('Downloading and Extracting')) {
            global.mainWindow.webContents.send('environment-progress', {
              type: 'info',
              data: '正在下载并提取包...'
            });
          } else if (msg.includes('Installing')) {
            global.mainWindow.webContents.send('environment-progress', {
              type: 'info',
              data: '正在安装包...'
            });
          } else if (msg.includes('Linking packages')) {
            global.mainWindow.webContents.send('environment-progress', {
              type: 'info',
              data: '正在链接包...'
            });
          }
        }
      });

      child.stderr.on('data', (data) => {
        const msg = data.toString();
              
        // 先移除所有的退格符组合
        const cleanedMsg = msg.replace(/\x08+/g, '');
              
        // 过滤加载动画字符
        const loadingAnimationPatterns = [
          /^\s*[\\|\/-]\s*$/,      // 单独的加载字符
          /^\s*[\\|\/-]\s+\d+%/ ,  // 加载字符 + 百分比
          /^\s*\.\.\.*\s*$/,       // 省略号
          /^[\x08\s]+$/,           // 纯退格符和空白
        ];
              
        const isAnimation = loadingAnimationPatterns.some(pattern => pattern.test(cleanedMsg.trim()));
              
        if (!isAnimation) {
          // 过滤 conda 版本更新警告，这不是错误
          const updateWarningPatterns = [
            /\[1\]\s*==> WARNING: A newer version of conda exists\. <==/i,
            /current version:/i,
            /latest version:/i,
            /Please update conda by running/i,
            /\$ conda update/i
          ];
                
          // 检查是否是版本更新警告
          const isUpdateWarning = updateWarningPatterns.some(pattern => pattern.test(cleanedMsg));
                
          if (!isUpdateWarning) {
            // 只有非警告信息才计为错误
            errorOutput += cleanedMsg;
            hasError = true;
                  
            if (global.mainWindow) {
              global.mainWindow.webContents.send('environment-progress', {
                type: 'stderr',
                data: cleanedMsg
              });
            }
          } else {
            // 版本更新警告作为普通信息发送
            if (global.mainWindow) {
              global.mainWindow.webContents.send('environment-progress', {
                type: 'info',
                data: `[conda 提示] ${cleanedMsg.trim()}`
              });
            }
          }
        }
        // 如果是加载动画，直接忽略不发送
      });

      child.on('close', async (code) => {
        // 清除进程引用
        this.installationProcess = null;
        
        if (code === 0 && !hasError) {
          this.isInitialized = true;
          resolve({ success: true, envPath: envDir });
        } else {
          // 安装失败，清理缓存
          console.log(`安装失败 (代码：${code})，开始清理缓存...`);
          try {
            await this.cleanupInstallationCache(envName);
          } catch (cleanupError) {
            console.error('清理缓存失败:', cleanupError);
          }
          reject(new Error(`创建环境失败，退出代码：${code}${errorOutput ? ': ' + errorOutput.trim() : ''}`));
        }
      });
      
      // 错误处理
      child.on('error', async (err) => {
        this.installationProcess = null;
        console.error('安装进程错误:', err);
        try {
          await this.cleanupInstallationCache(envName);
        } catch (cleanupError) {
          console.error('清理缓存失败:', cleanupError);
        }
        reject(err);
      });
    });
  }

  // 使用 pip 安装依赖
  async installPackages(packages) {
    if (!this.pythonPath) {
      throw new Error('Python 路径未设置');
    }

    const pipPath = process.platform === 'win32'
      ? path.join(path.dirname(this.pythonPath), 'pip.exe')
      : path.join(path.dirname(this.pythonPath), 'pip');

    return new Promise((resolve, reject) => {
      const args = ['install', ...packages];
      
      console.log('安装依赖:', pipPath, args.join(' '));

      const child = process.platform === 'win32'
        ? spawn('cmd.exe', ['/c', pipPath, ...args])
        : spawn(pipPath, args);

      let output = '';
      let errorOutput = '';

      child.stdout.on('data', (data) => {
        output += data.toString();
        if (global.mainWindow) {
          global.mainWindow.webContents.send('environment-progress', {
            type: 'stdout',
            data: data.toString()
          });
        }
      });

      child.stderr.on('data', (data) => {
        errorOutput += data.toString();
        if (global.mainWindow) {
          global.mainWindow.webContents.send('environment-progress', {
            type: 'stderr',
            data: data.toString()
          });
        }
      });

      child.on('close', (code) => {
        if (code === 0) {
          resolve({ success: true, output });
        } else {
          reject(new Error(`安装失败，退出代码：${code}`));
        }
      });
    });
  }

  // 验证环境是否满足要求
  async validateEnvironment() {
    console.log('[DEBUG] 开始验证环境...');
    console.log(`[DEBUG] 当前 pythonPath: ${this.pythonPath}`);
    console.log(`[DEBUG] 当前 envPath: ${this.envPath}`);
    console.log(`[DEBUG] 当前 condaPath: ${this.condaPath}`);
      
    if (!this.pythonPath) {
      console.log('[DEBUG] 验证失败：Python 路径未设置');
      // 尝试从 envPath 构建
      if (this.envPath) {
        this.pythonPath = process.platform === 'win32'
          ? path.join(this.envPath, 'python.exe')
          : path.join(this.envPath, 'bin', 'python');
        console.log(`[DEBUG] 已从 envPath 构建 Python 路径：${this.pythonPath}`);
      } else {
        return { valid: false, error: 'Python 未安装' };
      }
    }
  
    try {
      // 检查 Python 版本
      const version = await this.getPythonVersion();
      console.log('[DEBUG] Python 版本:', version);
        
      if (!version) {
        console.log('[DEBUG] 验证失败：无法获取 Python 版本');
        return { valid: false, error: '无法获取 Python 版本' };
      }
  
      // 检查关键依赖
      const requiredPackages = ['torch', 'torchvision', 'kornia'];
      const missingPackages = [];
  
      for (const pkg of requiredPackages) {
        const installed = await this.checkPackageInstalled(pkg);
        console.log(`[DEBUG] 检查包 ${pkg}:`, installed ? '已安装' : '未安装');
        if (!installed) {
          missingPackages.push(pkg);
        }
      }
  
      // 检查本地扩展包
      const localExtensions = ['diff_gaussian_rasterization', 'simple_knn', 'nvdiffrast'];
      const missingExtensions = [];
        
      for (const ext of localExtensions) {
        const installed = await this.checkPackageInstalled(ext);
        console.log(`[DEBUG] 检查本地扩展 ${ext}:`, installed ? '已安装' : '未安装');
        if (!installed) {
          missingExtensions.push(ext);
        }
      }
  
      if (missingPackages.length > 0 || missingExtensions.length > 0) {
        const errorMsg = [];
        if (missingPackages.length > 0) {
          errorMsg.push(`缺少依赖包：${missingPackages.join(', ')}`);
        }
        if (missingExtensions.length > 0) {
          errorMsg.push(`缺少本地扩展：${missingExtensions.join(', ')}`);
        }
              
        console.log('[DEBUG] 验证失败 - 缺少:', errorMsg.join('; '));
        console.log('[DEBUG] 建议：请确认您是否在正确的 conda 环境中运行');
        console.log(`[DEBUG] 当前使用的 Python 路径：${this.pythonPath}`);
              
        // 检查是否是 NumPy DLL 问题
        let suggestion = '';
        if (missingPackages.includes('torch') || missingPackages.includes('torchvision') || missingPackages.includes('kornia')) {
          suggestion = '\n\n检测到 PyTorch/Kornia 导入失败，可能是 NumPy DLL 加载问题。\n' +
            '请运行以下命令修复：\n' +
            '  cd GS-IR\n' +
            '  .\\fix_numpy_dll.bat\n' +
            '或者手动执行：\n' +
            '  pip uninstall -y numpy\n' +
            '  pip cache purge\n' +
            '  pip install numpy==1.21.6 --no-cache-dir';
        }
              
        return {
          valid: false,
          error: errorMsg.join(';') + suggestion,
          missing: missingPackages,
          missingExtensions: missingExtensions,
          hasValidBase: missingPackages.length === 0 && missingExtensions.length === 0
        };
      }
  
      console.log('[DEBUG] ✓ 环境验证通过');
      return { valid: true, pythonVersion: version };
    } catch (error) {
      console.error('[DEBUG] 验证异常:', error.message);
      return { valid: false, error: error.message };
    }
  }

  // 获取 Python 版本
  async getPythonVersion() {
    if (!this.pythonPath) return null;

    return new Promise((resolve) => {
      const child = process.platform === 'win32'
        ? spawn('cmd.exe', ['/c', this.pythonPath, '--version'])
        : spawn(this.pythonPath, ['--version']);

      let output = '';
      child.stdout.on('data', (data) => {
        output += data.toString();
      });

      child.on('close', () => {
        const match = output.match(/Python\s+([\d.]+)/i);
        resolve(match ? match[1] : null);
      });
    });
  }

  // 检查包是否已安装
  async checkPackageInstalled(packageName) {
    if (!this.pythonPath) {
      console.log(`[DEBUG] checkPackageInstalled: pythonPath 未设置，尝试使用 envPath: ${this.envPath}`);
      // 如果 pythonPath 未设置，但 envPath 已设置，尝试构建 Python 路径
      if (this.envPath) {
        this.pythonPath = process.platform === 'win32'
          ? path.join(this.envPath, 'python.exe')
          : path.join(this.envPath, 'bin', 'python');
        console.log(`[DEBUG] 使用构建的 Python 路径：${this.pythonPath}`);
      } else {
        return false;
      }
    }

    return new Promise((resolve) => {
      // Windows 上使用 cmd.exe 避免 shell: true 的参数解析问题
      const args = ['-c', `import ${packageName}; print("ok")`];
      let child;
      
      if (process.platform === 'win32') {
        child = spawn('cmd.exe', ['/c', this.pythonPath, ...args]);
      } else {
        child = spawn(this.pythonPath, args);
      }

      let output = '';
      let errorOutput = '';
      
      child.stdout.on('data', (data) => {
        output += data.toString();
      });

      child.stderr.on('data', (data) => {
        errorOutput += data.toString();
      });

      child.on('close', (code) => {
        const installed = code === 0 && output.trim() === 'ok';
        if (!installed) {
          console.log(`[DEBUG] 包 ${packageName} 检查失败：退出代码=${code}, output="${output.trim()}", stderr="${errorOutput.trim()}"`);
        }
        resolve(installed);
      });
    });
  }

  // 运行 Python 脚本
  runPythonScript(scriptPath, args = [], options = {}) {
    if (!this.pythonPath) {
      throw new Error('Python 环境未初始化');
    }

    const cwd = options.cwd || path.dirname(scriptPath);
    const fullArgs = [scriptPath, ...args];

    console.log('运行 Python 脚本:', this.pythonPath, fullArgs.join(' '));

    const child = process.platform === 'win32'
      ? spawn('cmd.exe', ['/c', this.pythonPath, ...fullArgs], {
          cwd,
          env: { ...process.env }
        })
      : spawn(this.pythonPath, fullArgs, {
          cwd,
          env: { ...process.env }
        });

    return child;
  }

  // 获取环境信息
  getEnvironmentInfo() {
    return {
      pythonPath: this.pythonPath,
      condaPath: this.condaPath,
      envPath: this.envPath,
      envName: this.envName,
      isInitialized: this.isInitialized
    };
  }

  // 清理安装缓存
  async cleanupInstallationCache(envName = 'gsir') {
    if (this.cleanupInProgress) {
      console.log('清理已在进行中，跳过');
      return;
    }

    this.cleanupInProgress = true;
    console.log(`开始清理 ${envName} 环境的缓存...`);

    try {
      const cacheDirs = [
        path.join(os.homedir(), '.miniconda3', 'pkgs'),
        path.join(os.homedir(), '.conda', 'pkgs'),
        path.join(os.tmpdir(), 'conda-*'),
      ];

      // 清理 Conda 包缓存
      for (const cacheDir of cacheDirs) {
        try {
          const exists = await fs.access(cacheDir).then(() => true).catch(() => false);
          if (exists) {
            console.log(`清理缓存目录：${cacheDir}`);
            // 只删除临时文件，保留已安装的包
            const files = await fs.readdir(cacheDir);
            for (const file of files) {
              if (file.endsWith('.tmp') || file.endsWith('.part') || file.startsWith('conda-tmp')) {
                const filePath = path.join(cacheDir, file);
                await fs.unlink(filePath).catch(err => console.error(`删除失败：${filePath}`, err));
              }
            }
          }
        } catch (error) {
          console.error(`清理缓存目录失败 ${cacheDir}:`, error);
        }
      }

      // 清理未完成的下载
      if (this.condaPath) {
        const tempFiles = await this.findTempFiles(envName);
        for (const tempFile of tempFiles) {
          try {
            await fs.unlink(tempFile);
            console.log(`清理临时文件：${tempFile}`);
          } catch (err) {
            console.error(`删除临时文件失败 ${tempFile}:`, err);
          }
        }
      }

      console.log('缓存清理完成');
      
      if (global.mainWindow) {
        global.mainWindow.webContents.send('environment-progress', {
          type: 'info',
          data: '已清理安装缓存，释放磁盘空间'
        });
      }
    } catch (error) {
      console.error('清理缓存时出错:', error);
    } finally {
      this.cleanupInProgress = false;
    }
  }

  // 查找临时文件
  async findTempFiles(envName) {
    const tempFiles = [];
    const searchPaths = [
      os.tmpdir(),
      path.join(os.homedir(), '.miniconda3', 'envs'),
    ];

    for (const searchPath of searchPaths) {
      try {
        const exists = await fs.access(searchPath).then(() => true).catch(() => false);
        if (!exists) continue;

        const files = await fs.readdir(searchPath);
        for (const file of files) {
          if ((file.includes(envName) && file.endsWith('.tmp')) ||
              file.includes('conda-tmp') ||
              file.endsWith('.part')) {
            tempFiles.push(path.join(searchPath, file));
          }
        }
      } catch (error) {
        // 忽略读取错误
      }
    }

    return tempFiles;
  }

  // 运行安装脚本
  async runInstallScript(scriptPath, mode = 'auto') {
    if (!this.condaPath) {
      throw new Error('未找到 Conda');
    }

    console.log('运行安装脚本:', scriptPath);
    console.log('安装模式:', mode);

    return new Promise((resolve, reject) => {
      // 发送开始安装的消息
      if (global.mainWindow) {
        global.mainWindow.webContents.send('environment-progress', {
          type: 'info',
          data: '开始运行一键安装脚本...'
        });
      }

      // 使用 spawn 运行批处理脚本
      const child = process.platform === 'win32'
        ? spawn('cmd.exe', ['/c', scriptPath], {
            cwd: path.dirname(scriptPath),
            env: { ...process.env, PYTHONUTF8: '1' }
          })
        : spawn(scriptPath, [], {
            cwd: path.dirname(scriptPath),
            env: { ...process.env, PYTHONUTF8: '1' }
          });

      // 保存当前安装进程引用
      this.installationProcess = child;

      let output = '';
      let errorOutput = '';
      let hasError = false;

      child.stdout.on('data', (data) => {
        const msg = data.toString();
        output += msg;
              
        // 实时解析输出，提取进度信息
        if (global.mainWindow) {
          // 先移除所有的退格符组合
          const cleanedMsg = msg.replace(/\x08+/g, '');
                
          // 过滤加载动画字符
          const loadingAnimationPatterns = [
            /^\s*[\\|\/-]\s*$/,      // 单独的加载字符
            /^\s*[\\|\/-]\s+\d+%/ ,  // 加载字符 + 百分比
            /^\s*\.\.\.*\s*$/,       // 省略号
            /^[\x08\s]+$/,           // 纯退格符和空白
          ];
                
          const isAnimation = loadingAnimationPatterns.some(pattern => pattern.test(cleanedMsg.trim()));
                
          if (!isAnimation) {
            // 发送清理后的输出
            global.mainWindow.webContents.send('environment-progress', {
              type: 'stdout',
              data: cleanedMsg
            });
          }
          
          // 解析进度百分比并发送 info 消息
          const progressPatterns = [
            /\[(\d+)%\]/,
            /Progress:\s*(\d+)%/i,
            /Completed:\s*(\d+)%/i,
            /(\d+)%\s*$/ // 匹配行尾的百分比
          ];
          
          for (const pattern of progressPatterns) {
            const match = msg.match(pattern);
            if (match) {
              const percent = parseInt(match[1]);
              global.mainWindow.webContents.send('environment-progress', {
                type: 'info',
                data: `当前进度：${percent}%`
              });
              break;
            }
          }
          
          // 检测关键阶段并发送提示（按照新的安装顺序）
          if (msg.includes('创建 Conda 环境')) {
            global.mainWindow.webContents.send('environment-progress', {
              type: 'info',
              data: '正在创建 Conda 环境...'
            });
          } else if (msg.includes('安装 kornia')) {
            global.mainWindow.webContents.send('environment-progress', {
              type: 'info',
              data: '正在安装 kornia...'
            });
          } else if (msg.includes('卸载 CPU 版本 PyTorch')) {
            global.mainWindow.webContents.send('environment-progress', {
              type: 'info',
              data: '正在卸载 CPU 版 PyTorch...'
            });
          } else if (msg.includes('安装 GPU 版本 PyTorch')) {
            global.mainWindow.webContents.send('environment-progress', {
              type: 'info',
              data: '正在安装 GPU 版 PyTorch (CUDA 11.6)...'
            });
          } else if (msg.includes('安装本地扩展模块')) {
            global.mainWindow.webContents.send('environment-progress', {
              type: 'info',
              data: '正在安装本地扩展模块...'
            });
          } else if (msg.includes('安装 gs-ir 模块')) {
            global.mainWindow.webContents.send('environment-progress', {
              type: 'info',
              data: '正在安装 gs-ir 模块...'
            });
          } else if (msg.includes('安装 nvdiffrast')) {
            global.mainWindow.webContents.send('environment-progress', {
              type: 'info',
              data: '正在安装 nvdiffrast...'
            });
          } else if (msg.includes('安装 simple-knn')) {
            global.mainWindow.webContents.send('environment-progress', {
              type: 'info',
              data: '正在安装 simple-knn...'
            });
          } else if (msg.includes('安装 diff-gaussian-rasterization')) {
            global.mainWindow.webContents.send('environment-progress', {
              type: 'info',
              data: '正在安装 diff-gaussian-rasterization...'
            });
          } else if (msg.includes('验证安装')) {
            global.mainWindow.webContents.send('environment-progress', {
              type: 'info',
              data: '正在验证安装...'
            });
          } else if (msg.includes('安装完成')) {
            global.mainWindow.webContents.send('environment-progress', {
              type: 'info',
              data: '安装完成！'
            });
          }
        }
      });

      child.stderr.on('data', (data) => {
        const msg = data.toString();
              
        // 先移除所有的退格符组合
        const cleanedMsg = msg.replace(/\x08+/g, '');
              
        // 过滤加载动画字符
        const loadingAnimationPatterns = [
          /^\s*[\\|\/-]\s*$/,      // 单独的加载字符
          /^\s*[\\|\/-]\s+\d+%/ ,  // 加载字符 + 百分比
          /^\s*\.\.\.*\s*$/,       // 省略号
          /^[\x08\s]+$/,           // 纯退格符和空白
        ];
              
        const isAnimation = loadingAnimationPatterns.some(pattern => pattern.test(cleanedMsg.trim()));
              
        if (!isAnimation) {
          errorOutput += cleanedMsg;
          hasError = true;
                  
          if (global.mainWindow) {
            global.mainWindow.webContents.send('environment-progress', {
              type: 'stderr',
              data: cleanedMsg
            });
          }
        }
      });

      child.on('close', async (code) => {
        // 清除进程引用
        this.installationProcess = null;
        
        if (code === 0 && !hasError) {
          this.isInitialized = true;
          resolve({ success: true, message: '安装成功' });
        } else {
          // 安装失败，清理缓存
          console.log(`安装失败 (代码：${code})，开始清理缓存...`);
          try {
            await this.cleanupInstallationCache('gsir');
          } catch (cleanupError) {
            console.error('清理缓存失败:', cleanupError);
          }
          reject(new Error(`安装失败，退出代码：${code}${errorOutput ? ': ' + errorOutput.trim() : ''}`));
        }
      });
      
      // 错误处理
      child.on('error', async (err) => {
        this.installationProcess = null;
        console.error('安装进程错误:', err);
        try {
          await this.cleanupInstallationCache('gsir');
        } catch (cleanupError) {
          console.error('清理缓存失败:', cleanupError);
        }
        reject(err);
      });
    });
  }

  // 停止当前安装
  async stopInstallation() {
    if (this.installationProcess) {
      console.log('停止安装进程...');
      
      // Windows 上使用 taskkill 强制终止进程树
      if (process.platform === 'win32') {
        try {
          const pid = this.installationProcess.pid;
          spawn('taskkill', ['/pid', pid.toString(), '/f', '/t']);
        } catch (error) {
          console.error('终止进程失败:', error);
        }
      } else {
        this.installationProcess.kill('SIGKILL');
      }
      
      this.installationProcess = null;
      
      // 延迟一下再清理缓存，确保进程完全退出
      setTimeout(() => {
        this.cleanupInstallationCache();
      }, 1000);
      
      return true;
    }
    return false;
  }
}

module.exports = PythonEnvironmentManager;
