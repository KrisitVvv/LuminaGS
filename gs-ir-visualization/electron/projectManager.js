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
  
  // 保存项目列表到文件
  async saveProjects() {
    try {
      await fs.writeFile(
        this.projectsFile, 
        JSON.stringify(this.projects, null, 2), 
        'utf8'
      );
    } catch (error) {
      console.error('[ProjectManager] 保存 projects.json 失败:', error);
      throw error;
    }
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
      const configContent = await fs.readFile(projectIndex.configFile, 'utf8');
      const projectConfig = JSON.parse(configContent);
      
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
      await fs.writeFile(
        projectIndex.configFile,
        JSON.stringify(projectConfig, null, 2),
        'utf8'
      );
      
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
      const projectIndex = this.projects.find(p => p.projectId === projectId);
      if (!projectIndex) {
        return { success: false, error: '项目不存在' };
      }
      
      // 读取详细配置
      const configContent = await fs.readFile(projectIndex.configFile, 'utf8');
      const projectConfig = JSON.parse(configContent);
      
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
          
          // 检查进程是否还在运行（需要外部提供）
          // 这里只做基本的状态检测
          
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
      // 1. 查找项目
      const projectIndex = this.projects.find(p => p.projectId === projectId);
      if (!projectIndex) {
        console.error(`[ProjectManager] 项目不存在：${projectId}`);
        return { success: false, error: '项目不存在' };
      }
      
      // 2. 读取配置文件
      const configContent = await fs.readFile(projectIndex.configFile, 'utf8');
      const projectConfig = JSON.parse(configContent);
      
      // 3. 合并配置（支持嵌套对象）
      const { 
        projectName, outputPath, sourcePath, iterations,
        resolution, evalMode, gamma, indirect,
        bound, occluRes, occlusion, checkpoint
      } = configUpdates;
      
      // 更新顶层字段
      if (projectName !== undefined) projectConfig.name = projectName;
      if (outputPath !== undefined) projectConfig.outputPath = outputPath;
      if (sourcePath !== undefined) projectConfig.sourcePath = sourcePath;
      if (checkpoint !== undefined) projectConfig.checkpoint = checkpoint;
      if (iterations !== undefined) projectConfig.totalIterations = iterations;
      
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
      
      // 5. 原子写入：先写临时文件，再重命名
      const tempFile = projectIndex.configFile + '.tmp';
      await fs.writeFile(tempFile, JSON.stringify(projectConfig, null, 2), 'utf8');
      await fs.rename(tempFile, projectIndex.configFile);
      
      // 6. 更新全局索引
      await this.saveProjects();
      
      console.log(`[ProjectManager] ✓ 项目配置已保存：${projectId}`);
      return { success: true };
    } catch (error) {
      console.error(`[ProjectManager] 更新项目配置失败:`, error);
      return { success: false, error: error.message };
    }
  }
}

module.exports = ProjectManager;
