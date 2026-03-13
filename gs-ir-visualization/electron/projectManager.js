const fs = require('fs').promises;
const path = require('path');

class ProjectManager {
  constructor() {
    // 项目数据目录
    this.projectsDir = path.join(__dirname, '.projects');
    this.projectsFile = path.join(this.projectsDir, 'projects.json');
    this.projects = [];
    
    // 初始化项目目录和文件
    this.initialize();
  }
  
  // 初始化项目存储
  async initialize() {
    try {
      // 创建项目目录
      await fs.mkdir(this.projectsDir, { recursive: true });
      
      // 检查 projects.json 是否存在
      try {
        await fs.access(this.projectsFile);
        const content = await fs.readFile(this.projectsFile, 'utf8');
        this.projects = JSON.parse(content);
        console.log(`[ProjectManager] 已加载 ${this.projects.length} 个项目`);
      } catch (err) {
        // 文件不存在，创建空数组
        this.projects = [];
        await this.saveProjects();
        console.log('[ProjectManager] 创建新的 projects.json');
      }
    } catch (error) {
      console.error('[ProjectManager] 初始化失败:', error);
      this.projects = [];
    }
  }
  
  // 保存项目列表到文件（带重试机制）
  async saveProjects() {
    const maxRetries = 3;
    let lastError = null;
    
    for (let attempt = 1; attempt <= maxRetries; attempt++) {
      try {
        // 1. 先写入临时文件
        const tempFile = this.projectsFile + '.tmp';
        const content = JSON.stringify(this.projects, null, 2);
        await fs.writeFile(tempFile, content, 'utf8');
        
        // 2. 验证临时文件
        await fs.access(tempFile);
        const verifyContent = await fs.readFile(tempFile, 'utf8');
        JSON.parse(verifyContent); // 验证 JSON 格式
        
        // 3. 删除旧文件（如果存在）
        try {
          await fs.unlink(this.projectsFile);
        } catch (err) {
          // 文件不存在也没关系
        }
        
        // 4. 重命名临时文件为正式文件（原子操作）
        await fs.rename(tempFile, this.projectsFile);
        
        console.log(`[ProjectManager] ✓ projects.json 保存成功（尝试 ${attempt}/${maxRetries}）`);
        return;
      } catch (error) {
        lastError = error;
        console.warn(`[ProjectManager] ⚠ 保存失败（尝试 ${attempt}/${maxRetries}）:`, error.message);
        
        // 清理临时文件（如果存在）
        try {
          await fs.unlink(this.projectsFile + '.tmp');
        } catch (cleanupErr) {
          // 忽略清理错误
        }
        
        // 等待一小段时间后重试
        if (attempt < maxRetries) {
          await new Promise(resolve => setTimeout(resolve, 100 * attempt));
        }
      }
    }
    
    // 所有重试都失败，抛出错误
    console.error('[ProjectManager] ✗ 保存 projects.json 失败:', lastError.message);
    throw lastError;
  }
  
  // 生成项目 ID（时间戳 + 随机数）
  generateProjectId(name) {
    const now = new Date();
    const timestamp = `${now.getFullYear()}${String(now.getMonth() + 1).padStart(2, '0')}${String(now.getDate()).padStart(2, '0')}_${String(now.getHours()).padStart(2, '0')}${String(now.getMinutes()).padStart(2, '0')}`;
    const randomId = Math.random().toString(36).substring(2, 5);
    const sanitizedName = name ? name.replace(/[^a-zA-Z0-9\u4e00-\u9fa5]/g, '_').substring(0, 20) : 'project';
    return `${sanitizedName}_${timestamp}_${randomId}`;
  }
  
  // 创建新项目
  async createProject(config) {
    try {
      const {
        projectName,
        outputPath,
        sourcePath,
        stage = 'stage1',
        totalIterations = 30000,
        resolution = 1,
        evalMode = true,
        gamma = false,
        indirect = false,
        bound = 1.5,
        occluRes = 128,
        occlusion = 0.01,
        checkpoint = null  // 新增：检查点路径
      } = config;
      
      // 生成项目 ID
      const projectId = this.generateProjectId(projectName);
      const startTime = new Date().toISOString();
      
      // 创建.luminags 目录
      const luminagsDir = path.join(outputPath, '.luminags');
      await fs.mkdir(luminagsDir, { recursive: true });
      
      // 创建项目配置文件
      const projectConfig = {
        projectId,
        name: projectName || `Project_${projectId}`,
        outputPath,
        sourcePath,
        startTime,
        lastModified: startTime,
        status: 'waiting', // waiting, training, paused, completed, error, disconnected
        stage, // stage1, baking, stage2
        currentIteration: 0,
        totalIterations,
        checkpoint, // 新增：检查点路径
        config: {
          resolution,
          evalMode,
          gamma,
          indirect,
          bound,
          occluRes,
          occlusion
        },
        metrics: {
          lossHistory: [],
          psnrHistory: [],
          ssimHistory: [],
          evalL1History: []  // 新增：评估 L1 历史
        },
        previewImagePath: null,
        logFile: path.join(luminagsDir, 'training.log')
      };
      
      // 保存项目配置
      const configFile = path.join(luminagsDir, `${projectId}.json`);
      await fs.writeFile(
        configFile,
        JSON.stringify(projectConfig, null, 2),
        'utf8'
      );
      
      // 添加到全局项目列表
      const projectIndex = {
        projectId,
        name: projectName || `Project_${projectId}`,
        outputPath,
        lastModified: startTime,
        status: 'waiting',
        currentIteration: 0,
        configFile,
        stage
      };
      
      this.projects.push(projectIndex);
      await this.saveProjects();
      
      console.log(`[ProjectManager] 创建新项目：${projectId}, 名称：${projectName || '未命名'}`);
      
      return {
        success: true,
        projectId,
        configFile
      };
    } catch (error) {
      console.error('[ProjectManager] 创建项目失败:', error);
      return { success: false, error: error.message };
    }
  }
  
  // 更新项目阶段 (baking 专用)
  async updateProjectStage(projectId, stage) {
 try {
  const projectIndex = this.projects.find(p => p.projectId === projectId);
   if (!projectIndex) {
 console.error(`[ProjectManager] 项目不存在：${projectId}`);
   return { success: false, error: '项目不存在' };
  }
  
  // 读取配置文件
 const configContent = await fs.readFile(projectIndex.configFile, 'utf8');
  const projectConfig = JSON.parse(configContent);
  
  // 更新阶段
 projectConfig.stage = stage;
 projectIndex.stage = stage;
 projectConfig.lastModified = new Date().toISOString();
 projectIndex.lastModified = projectConfig.lastModified;
  
  // 保存
 await fs.writeFile(
  projectIndex.configFile,
   JSON.stringify(projectConfig, null, 2),
   'utf8'
  );
  
  await this.saveProjects();
  
 console.log(`[ProjectManager] 项目 ${projectId} 阶段已更新为 ${stage}`);
  return { success: true };
 } catch (error) {
console.error('[ProjectManager] 更新项目阶段失败:', error);
  return { success: false, error: error.message };
}
  }
  
  // 更新项目状态
  async updateProject(projectId, data) {
    try {
      // 查找项目
      const projectIndex = this.projects.find(p => p.projectId === projectId);
      if (!projectIndex) {
        console.error(`[ProjectManager] 项目不存在：${projectId}`);
        return { success: false, error: '项目不存在' };
      }
      
      // 读取项目配置文件
      let configContent;
      try {
        configContent = await fs.readFile(projectIndex.configFile, 'utf8');
        console.log(`[ProjectManager] ✓ 成功读取配置文件：${projectIndex.configFile}`);
      } catch (readError) {
        console.error(`[ProjectManager] ✗ 读取配置文件失败：${projectIndex.configFile}`);
        console.error(`[ProjectManager] 错误详情:`, readError.message);
        throw new Error(`无法读取项目配置文件：${readError.message}`);
      }
      
      // 验证 JSON 格式
      let projectConfig;
      try {
        projectConfig = JSON.parse(configContent);
        console.log(`[ProjectManager] ✓ JSON 解析成功`);
      } catch (parseError) {
        console.error(`[ProjectManager] ✗ JSON 解析失败`);
        console.error(`[ProjectManager] 文件内容预览:`, configContent.substring(0, 200));
        console.error(`[ProjectManager] 解析错误:`, parseError.message);
        
        // 尝试修复：提取第一个完整的 JSON 对象
        console.log(`[ProjectManager] 尝试自动修复 JSON...`);
        let braceCount = 0;
        let endIndex = -1;
        
        for (let i = 0; i < configContent.length; i++) {
          if (configContent[i] === '{') braceCount++;
          if (configContent[i] === '}') braceCount--;
          
          if (braceCount === 0 && configContent[i] === '}') {
            endIndex = i + 1;
            break;
          }
        }
        
        if (endIndex !== -1) {
          const jsonStr = configContent.substring(0, endIndex);
          try {
            projectConfig = JSON.parse(jsonStr);
            console.log(`[ProjectManager] ✓ JSON 修复成功`);
          } catch (fixError) {
            console.error(`[ProjectManager] ✗ JSON 修复失败`);
            throw new Error(`项目配置文件损坏且无法修复：${parseError.message}`);
          }
        } else {
          throw new Error(`项目配置文件严重损坏：${parseError.message}`);
        }
      }
      
      // 更新数据
      const {
        status,
        currentIteration,
        loss,
        psnr,
        ssim,
        evalL1,  // 新增：评估 L1
        evalL1Type,  // 新增：评估类型
        previewPath,
        stage
      } = data;
      
      if (status) projectConfig.status = status;
      if (currentIteration !== undefined) {
        projectConfig.currentIteration = currentIteration;
        projectIndex.currentIteration = currentIteration;
      }
      if (stage) {
        projectConfig.stage = stage;
        projectIndex.stage = stage;
      }
      
      // 更新指标历史（Loss 和 Eval L1 独立存储）
      
      // 1. 常规训练 Loss 存储（每 100 次迭代）
      if (loss !== undefined && loss !== null && currentIteration) {
        // 检查是否已存在该迭代的 Loss 记录
        const existingLossIndex = projectConfig.metrics.lossHistory.findIndex(
          item => item.iteration === currentIteration
        );
        
        if (existingLossIndex !== -1) {
          // 如果已存在，更新值（保留最新值）
          projectConfig.metrics.lossHistory[existingLossIndex].value = loss;
        } else {
          // 如果是新迭代，添加记录
          projectConfig.metrics.lossHistory.push({
            iteration: currentIteration,
            value: loss
          });
        }
      }
      
      // 2. PSNR 和 SSIM 只在有有效值时才保存（避免 null 值污染数据）
      if (psnr !== undefined && psnr !== null && currentIteration) {
        // 检查是否已存在该迭代的 PSNR 记录
        const existingPsnrIndex = projectConfig.metrics.psnrHistory.findIndex(
          item => item.iteration === currentIteration
        );
        
        if (existingPsnrIndex !== -1) {
          // 如果已存在，更新值
          projectConfig.metrics.psnrHistory[existingPsnrIndex].value = psnr;
        } else {
          // 如果是新迭代，添加记录
          projectConfig.metrics.psnrHistory.push({
            iteration: currentIteration,
            value: psnr
          });
        }
      }
      
      if (ssim !== undefined && ssim !== null && currentIteration) {
        // 检查是否已存在该迭代的 SSIM 记录
        const existingSsimIndex = projectConfig.metrics.ssimHistory.findIndex(
          item => item.iteration === currentIteration
        );
        
        if (existingSsimIndex !== -1) {
          // 如果已存在，更新值
          projectConfig.metrics.ssimHistory[existingSsimIndex].value = ssim;
        } else {
          // 如果是新迭代，添加记录
          projectConfig.metrics.ssimHistory.push({
            iteration: currentIteration,
            value: ssim
          });
        }
      }
      
      // 新增：评估 L1 存储（独立于常规 Loss）
      if (evalL1 !== undefined && evalL1 !== null && currentIteration) {
        const existingEvalL1Index = projectConfig.metrics.evalL1History.findIndex(
          item => item.iteration === currentIteration
        );
        
        if (existingEvalL1Index !== -1) {
          // 如果已存在，更新值
          projectConfig.metrics.evalL1History[existingEvalL1Index].value = evalL1;
          projectConfig.metrics.evalL1History[existingEvalL1Index].type = evalL1Type || 'unknown';
        } else {
          // 如果是新迭代，添加记录
          projectConfig.metrics.evalL1History.push({
            iteration: currentIteration,
            value: evalL1,
            type: evalL1Type || 'unknown'
          });
        }
        
        console.log(`[Metrics] ✓ Eval L1 已保存 - iter: ${currentIteration}, value: ${evalL1}, type: ${evalL1Type || 'unknown'}`);
      }
      
      // 更新预览图路径
      if (previewPath) {
        projectConfig.previewImagePath = previewPath;
      }
      
      // 更新时间
      projectConfig.lastModified = new Date().toISOString();
      projectIndex.lastModified = projectConfig.lastModified;
      
      // 保存回文件
      console.log(`[ProjectManager] 开始写入项目配置：${projectIndex.configFile}`);
      try {
        const content = JSON.stringify(projectConfig, null, 2);
        await fs.writeFile(
          projectIndex.configFile,
          content,
          'utf8'
        );
        console.log(`[ProjectManager] ✓ 项目配置已更新：${projectIndex.configFile}`);
        
        // 验证写入的文件是否有效
        await fs.access(projectIndex.configFile);
        const verifyContent = await fs.readFile(projectIndex.configFile, 'utf8');
        JSON.parse(verifyContent); // 如果能解析成功说明文件完好
        console.log(`[ProjectManager] ✓ 文件验证通过`);
      } catch (writeError) {
        console.error(`[ProjectManager] 写入项目配置失败：${writeError.message}`);
        console.error(`[ProjectManager] 错误堆栈:`, writeError.stack);
        throw writeError;
      }
      
      // 保存全局索引
      await this.saveProjects();
      
      return { success: true };
    } catch (error) {
      console.error('[ProjectManager] 更新项目失败:', error);
      return { success: false, error: error.message };
    }
  }
  
  // 获取所有项目
  getAllProjects() {
    return [...this.projects];
  }
  
  // 加载单个项目详情
  async loadProject(projectId) {
    try {
      console.log(`[ProjectManager] 开始加载项目：${projectId}`);
      const projectIndex = this.projects.find(p => p.projectId === projectId);
      if (!projectIndex) {
        console.error(`[ProjectManager] 项目不存在：${projectId}`);
        return { success: false, error: '项目不存在' };
      }
      
      console.log(`[ProjectManager] 找到项目索引，配置文件路径：${projectIndex.configFile}`);
      
      // 读取详细配置
      const configContent = await fs.readFile(projectIndex.configFile, 'utf8');
      const projectConfig = JSON.parse(configContent);
      
      console.log(`[ProjectManager] ✓ 项目加载成功：${projectId}`);
      
      return {
        success: true,
        data: projectConfig
      };
    } catch (error) {
      console.error('[ProjectManager] 加载项目失败:', error);
      return { success: false, error: error.message };
    }
  }
  
  // 扫描本地所有项目
  async scanProjects() {
    try {
      console.log('[ProjectManager] 开始扫描项目...');
      
      // 遍历所有项目输出目录
      const validProjects = [];
      
      for (const project of this.projects) {
        try {
          // 检查配置文件是否存在
          await fs.access(project.configFile);
          
          // 读取配置
          const configContent = await fs.readFile(project.configFile, 'utf8');
          const projectConfig = JSON.parse(configContent);
          
          // ✅ 重要：从配置文件中同步最新状态到 projects.json
          // 包括 status、stage、currentIteration 等字段
          if (projectConfig.status) {
            project.status = projectConfig.status;
          }
          if (projectConfig.stage) {
            project.stage = projectConfig.stage;
          }
          if (projectConfig.currentIteration !== undefined) {
            project.currentIteration = projectConfig.currentIteration;
          }
          if (projectConfig.lastModified) {
            project.lastModified = projectConfig.lastModified;
          }
          if (projectConfig.thumbnailPath) {
            project.thumbnailPath = projectConfig.thumbnailPath;
          }
          
          console.log(`[ProjectManager] ✓ 已同步项目 ${project.projectId} 状态：${project.status}, stage: ${project.stage}`);
          
          validProjects.push(project);
        } catch (err) {
          console.warn(`[ProjectManager] 项目配置文件不存在或损坏：${project.projectId}`);
          // 标记为错误状态
          project.status = 'error';
        }
      }
      
      // 保存更新后的状态
      await this.saveProjects();
      
      console.log(`[ProjectManager] 扫描完成，找到 ${validProjects.length} 个有效项目`);
      return validProjects;
    } catch (error) {
      console.error('[ProjectManager] 扫描项目失败:', error);
      return this.projects;
    }
  }
  
  // 删除项目
  async deleteProject(projectId) {
    try {
      const index = this.projects.findIndex(p => p.projectId === projectId);
      if (index === -1) {
        return { success: false, error: '项目不存在' };
      }
      
      const project = this.projects[index];
      
      // 删除配置文件
      try {
        await fs.unlink(project.configFile);
      } catch (err) {
        console.warn(`[ProjectManager] 删除配置文件失败：${err.message}`);
      }
      
      // 从列表中移除
      this.projects.splice(index, 1);
      await this.saveProjects();
      
      console.log(`[ProjectManager] 已删除项目：${projectId}`);
      return { success: true };
    } catch (error) {
      console.error('[ProjectManager] 删除项目失败:', error);
      return { success: false, error: error.message };
    }
  }
  
  // 更新项目状态（简化版本，用于队列管理）
  async updateProjectStatus(projectId, status) {
    const projectIndex = this.projects.find(p => p.projectId === projectId);
    if (projectIndex) {
      projectIndex.status = status;
      projectIndex.lastModified = new Date().toISOString();
      await this.saveProjects();
      
      // 同时更新配置文件
      try {
        const configContent = await fs.readFile(projectIndex.configFile, 'utf8');
        const projectConfig = JSON.parse(configContent);
        projectConfig.status = status;
        projectConfig.lastModified = projectIndex.lastModified;
        await fs.writeFile(
          projectIndex.configFile,
          JSON.stringify(projectConfig, null, 2),
          'utf8'
        );
      } catch (error) {
        console.error(`[ProjectManager] 更新项目 ${projectId} 状态失败:`, error);
      }
    }
  }
  
  // 更新项目配置（用于实时自动保存）
  async updateProjectConfig(projectId, configUpdates) {
    try {
      console.log(`[ProjectManager] 开始更新项目配置：${projectId}`);
      console.log(`[ProjectManager] 更新内容:`, JSON.stringify(configUpdates, null, 2));
      
      // 1. 查找项目
      const projectIndex = this.projects.find(p => p.projectId === projectId);
      if (!projectIndex) {
        console.error(`[ProjectManager] 项目不存在：${projectId}`);
        return { success: false, error: '项目不存在' };
      }
      
      console.log(`[ProjectManager] 找到项目，配置文件路径：${projectIndex.configFile}`);
      
      // 2. 读取配置文件
      let configContent;
      try {
        configContent = await fs.readFile(projectIndex.configFile, 'utf8');
        console.log(`[ProjectManager] ✓ 成功读取配置文件`);
      } catch (readError) {
        console.error(`[ProjectManager] ✗ 读取配置文件失败:`, readError.message);
        throw new Error(`无法读取项目配置文件：${readError.message}`);
      }
      
      // 3. 解析 JSON（带错误修复）
      let projectConfig;
      try {
        projectConfig = JSON.parse(configContent);
        console.log(`[ProjectManager] ✓ JSON 解析成功`);
      } catch (parseError) {
        console.error(`[ProjectManager] ✗ JSON 解析失败：${parseError.message}`);
        console.error(`[ProjectManager] 文件内容预览:`, configContent.substring(0, 200));
        
        // 尝试修复
        let braceCount = 0;
        let endIndex = -1;
        
        for (let i = 0; i < configContent.length; i++) {
          if (configContent[i] === '{') braceCount++;
          if (configContent[i] === '}') braceCount--;
          
          if (braceCount === 0 && configContent[i] === '}') {
            endIndex = i + 1;
            break;
          }
        }
        
        if (endIndex !== -1) {
          const jsonStr = configContent.substring(0, endIndex);
          try {
            projectConfig = JSON.parse(jsonStr);
            console.log(`[ProjectManager] ✓ JSON 修复成功`);
          } catch (fixError) {
            throw new Error(`JSON 损坏且无法修复：${parseError.message}`);
          }
        } else {
          throw new Error(`JSON 严重损坏，无法恢复：${parseError.message}`);
        }
      }
      
      console.log(`[ProjectManager] 原始配置:`, JSON.stringify(projectConfig.config, null, 2));
      
      // 3. 合并配置（支持嵌套对象）
     const { 
        projectName, outputPath, sourcePath, iterations,
        resolution, evalMode, gamma, indirect,
        bound, occluRes, occlusion, checkpoint,
        // Baking 状态字段
       bakingStatus, bakingProgress, bakingLogs,
       // 训练状态字段
       isTraining, isBaking, currentIteration
      } = configUpdates;
           
      // 更新顶层字段
     if (projectName !== undefined) projectConfig.name = projectName;
     if (outputPath !== undefined) projectConfig.outputPath = outputPath;
     if (sourcePath !== undefined) projectConfig.sourcePath = sourcePath;
     if (checkpoint !== undefined) projectConfig.checkpoint = checkpoint;
     if (iterations !== undefined) projectConfig.totalIterations = iterations;
           
      // 更新训练状态
      if (isTraining !== undefined) {
        projectConfig.status = isTraining ? 'training' : projectConfig.status;
      }
      if (isBaking !== undefined) {
        // isBaking 为 true 时，设置 baking 状态和阶段
        if (isBaking) {
          projectConfig.status = 'baking';
          projectConfig.stage = 'baking';
          projectIndex.stage = 'baking';
          if (!projectConfig.bakingStatus || projectConfig.bakingStatus === 'idle') {
            projectConfig.bakingStatus = 'running';
          }
        }
      }
      if (currentIteration !== undefined) {
        projectConfig.currentIteration = currentIteration;
        projectIndex.currentIteration = currentIteration;
      }
           
      // 更新 Baking 状态字段
     if (bakingStatus !== undefined) {
        projectConfig.bakingStatus = bakingStatus;
        // 如果 baking 状态是 running，更新项目阶段
        if (bakingStatus === 'running') {
          projectConfig.stage = 'baking';
          projectIndex.stage = 'baking';
        }
      }
     if (bakingProgress !== undefined) projectConfig.bakingProgress = bakingProgress;
     if (bakingLogs !== undefined) {
        // 确保是数组且只保留最近的日志
        projectConfig.bakingLogs = Array.isArray(bakingLogs) ? bakingLogs.slice(-200) : [];
      }
      
      // 更新 config 对象
      if (resolution !== undefined) projectConfig.config.resolution = resolution;
      if (evalMode !== undefined) projectConfig.config.evalMode = evalMode;
      if (gamma !== undefined) projectConfig.config.gamma = gamma;
      if (indirect !== undefined) projectConfig.config.indirect = indirect;
      if (bound !== undefined) projectConfig.config.bound = bound;
      if (occluRes !== undefined) projectConfig.config.occluRes = occluRes;
      if (occlusion !== undefined) projectConfig.config.occlusion = occlusion;
      
      // 4. 更新时间戳
      projectConfig.lastModified = new Date().toISOString();
      projectIndex.lastModified = projectConfig.lastModified;
      
      // 5. 安全写入：直接覆盖原文件（避免原子写入导致文件瞬间消失）
      console.log(`[ProjectManager] 开始写入配置文件：${projectIndex.configFile}`);
      try {
        const content = JSON.stringify(projectConfig, null, 2);
        // 使用同步写入确保数据立即持久化
        await fs.writeFile(
          projectIndex.configFile,
          content,
          'utf8'
        );
        console.log(`[ProjectManager] ✓ 配置文件已更新：${projectIndex.configFile}`);
        
        // 验证文件是否存在且格式正确
        await fs.access(projectIndex.configFile);
        const verifyContent = await fs.readFile(projectIndex.configFile, 'utf8');
        JSON.parse(verifyContent); // 验证 JSON 格式
        console.log(`[ProjectManager] ✓ 文件验证成功`);
      } catch (writeError) {
        console.error(`[ProjectManager] 写入配置文件失败：${writeError.message}`);
        console.error(`[ProjectManager] 错误堆栈:`, writeError.stack);
        throw writeError;
      }
      
      // 6. 更新全局索引
      await this.saveProjects();
      
      console.log(`[ProjectManager] 项目配置已保存：${projectId}`);
      return { success: true };
    } catch(error) {
     console.error(`[ProjectManager] 更新项目配置失败:`, error);
      return { success: false, error: error.message };
    }
  }
  
  // 检查训练是否完成（检测 chkpnt40000.pth）
  async checkTrainingCompletion(projectId) {
    try {
      const projectIndex = this.projects.find(p => p.projectId === projectId);
      if (!projectIndex) {
        console.error(`[ProjectManager] 项目不存在：${projectId}`);
        return { success: false, error: '项目不存在' };
      }
      
      // 读取配置文件
      const configContent = await fs.readFile(projectIndex.configFile, 'utf8');
      const projectConfig = JSON.parse(configContent);
      
      const outputPath = projectConfig.outputPath;
      const checkpointFile = path.join(outputPath, 'chkpnt40000.pth');
      
      // 检查文件是否存在
      try {
        await fs.access(checkpointFile);
        console.log(`[ProjectManager] ✓ 检测到完成标记文件：${checkpointFile}`);
        
        // 更新项目状态为 completed
        projectConfig.status = 'completed';
        projectIndex.status = 'completed';
        projectConfig.lastModified = new Date().toISOString();
        projectIndex.lastModified = projectConfig.lastModified;
        
        // 保存回文件
        await fs.writeFile(
          projectIndex.configFile,
          JSON.stringify(projectConfig, null, 2),
          'utf8'
        );
        
        await this.saveProjects();
        
        console.log(`[ProjectManager] ✓ 项目 ${projectId} 状态已更新为 completed`);
        return { success: true, completed: true };
      } catch (err) {
        // 文件不存在
        console.log(`[ProjectManager] 完成标记文件不存在：${checkpointFile}`);
        return { success: true, completed: false };
      }
    } catch (error) {
      console.error('[ProjectManager] 检查训练完成状态失败:', error);
      return { success: false, error: error.message };
    }
  }
}

module.exports = ProjectManager;
