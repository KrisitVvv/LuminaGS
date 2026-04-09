const fs = require('fs').promises;
const path = require('path');

class ProjectManager {
  constructor() {
    this.projectsDir = path.join(__dirname, '.projects');
    this.projectsFile = path.join(this.projectsDir, 'projects.json');
    this.projects = [];
    this.initialize();
  }
  
  async initialize() {
    try {
      await fs.mkdir(this.projectsDir, { recursive: true });
      try {
        await fs.access(this.projectsFile);
        const content = await fs.readFile(this.projectsFile, 'utf8');
        this.projects = JSON.parse(content);
        console.log(`[ProjectManager] 已加载 ${this.projects.length} 个项目`);
      } catch (err) {
        this.projects = [];
        await this.saveProjects();
        console.log('[ProjectManager] 创建新的 projects.json');
      }
    } catch (error) {
      console.error('[ProjectManager] 初始化失败:', error);
      this.projects = [];
    }
  }
  
  async saveProjects() {
    const maxRetries = 3;
    let lastError = null;
    
    for (let attempt = 1; attempt <= maxRetries; attempt++) {
      try {
        const tempFile = this.projectsFile + '.tmp';
        const content = JSON.stringify(this.projects, null, 2);
        await fs.writeFile(tempFile, content, 'utf8');
        await fs.access(tempFile);
        const verifyContent = await fs.readFile(tempFile, 'utf8');
        JSON.parse(verifyContent); 
        try {
          await fs.unlink(this.projectsFile);
        } catch (err) {
        }
        await fs.rename(tempFile, this.projectsFile);
        
        console.log(`[ProjectManager] ✓ projects.json 保存成功（尝试 ${attempt}/${maxRetries}）`);
        return;
      } catch (error) {
        lastError = error;
        console.warn(`[ProjectManager] ⚠ 保存失败（尝试 ${attempt}/${maxRetries}）:`, error.message);
        try {
          await fs.unlink(this.projectsFile + '.tmp');
        } catch (cleanupErr) {
        }
        if (attempt < maxRetries) {
          await new Promise(resolve => setTimeout(resolve, 100 * attempt));
        }
      }
    }
    console.error('[ProjectManager] ✗ 保存 projects.json 失败:', lastError.message);
    throw lastError;
  }
  
  // Generate a project ID
  generateProjectId(name) {
    const now = new Date();
    const timestamp = `${now.getFullYear()}${String(now.getMonth() + 1).padStart(2, '0')}${String(now.getDate()).padStart(2, '0')}_${String(now.getHours()).padStart(2, '0')}${String(now.getMinutes()).padStart(2, '0')}`;
    const randomId = Math.random().toString(36).substring(2, 5);
    const sanitizedName = name ? name.replace(/[^a-zA-Z0-9\u4e00-\u9fa5]/g, '_').substring(0, 20) : 'project';
    return `${sanitizedName}_${timestamp}_${randomId}`;
  }
  
  // Create a new project
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
        checkpoint = null
      } = config;
      
      const projectId = this.generateProjectId(projectName);
      const startTime = new Date().toISOString();
      
      // Create .luminags directory
      const luminagsDir = path.join(outputPath, '.luminags');
      await fs.mkdir(luminagsDir, { recursive: true });
      
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
        checkpoint, 
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
          evalL1History: []
        },
        previewImagePath: null,
        logFile: path.join(luminagsDir, 'training.log')
      };
      
      // Save project configuration
      const configFile = path.join(luminagsDir, `${projectId}.json`);
      await fs.writeFile(
        configFile,
        JSON.stringify(projectConfig, null, 2),
        'utf8'
      );
      
      // Add to global project list
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
      console.log(`[ProjectManager] Created new project: ${projectId}, name: ${projectName || 'Untitled'}`);
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
  
  // Sync sourcePath field to projects.json
  async syncSourcePathToProjects() {
    try {
      let syncCount = 0;
      let updatedCount = 0;
      
      console.log('[ProjectManager] 🔍 开始同步 sourcePath 字段...');
      
      for (const project of this.projects) {
        syncCount++;
        
        // Check if sourcePath already exists
        if (project.sourcePath) {
          console.log(`[ProjectManager] ⏭️ 跳过（已有 sourcePath）: ${project.projectId}`);
          continue;
        }
        
        // Read detailed config file to get sourcePath
        try {
          const configContent = await fs.readFile(project.configFile, 'utf8');
          const projectConfig = JSON.parse(configContent);
          
          if (projectConfig.sourcePath) {
            // Sync sourcePath to projects.json
            project.sourcePath = projectConfig.sourcePath;
            updatedCount++;
            
            console.log(`[ProjectManager] Successfully synced sourcePath: ${project.projectId} -> ${projectConfig.sourcePath}`);
          } else {
            console.warn(`[ProjectManager] 配置文件中缺少 sourcePath: ${project.projectId}`);
          }
        } catch (readError) {
          console.error(`[ProjectManager] Failed to read config file: ${project.configFile}`, readError.message);
        }
      }
      
      if (updatedCount > 0) {
        await this.saveProjects();
        console.log(`[ProjectManager] Sync completed! Total: ${syncCount} projects, updated: ${updatedCount} projects`);
        return {
          success: true,
          message: `同步完成！总计 ${syncCount} 个项目，已更新 ${updatedCount} 个`,
          total: syncCount,
          updated: updatedCount
        };
      } else {
        console.log(`[ProjectManager] No sync needed, all projects have sourcePath fields`);
        return {
          success: true,
          message: '无需同步，所有项目已有 sourcePath 字段',
          total: syncCount,
          updated: 0
        };
      }
    } catch (error) {
      console.error('[ProjectManager] Failed to sync sourcePath:', error);
      return { success: false, error: error.message };
    }
  }
  
  async updateProjectStage(projectId, stage) {
 try {
  const projectIndex = this.projects.find(p => p.projectId === projectId);
   if (!projectIndex) {
        console.error(`[ProjectManager] Project does not exist: ${projectId}`);
	return { success: false, error: '项目不存在' };
  }
  
 const configContent = await fs.readFile(projectIndex.configFile, 'utf8');
 const projectConfig = JSON.parse(configContent);
 projectConfig.stage = stage;
 projectIndex.stage = stage;
 projectConfig.lastModified = new Date().toISOString();
 projectIndex.lastModified = projectConfig.lastModified;
 await fs.writeFile(
  projectIndex.configFile,
   JSON.stringify(projectConfig, null, 2),
   'utf8'
  );
  await this.saveProjects();
 
 console.log(`[ProjectManager] Project ${projectId} stage updated to ${stage}`);
  return { success: true };
 } catch (error) {
console.error('[ProjectManager] 更新项目阶段失败:', error);
  return { success: false, error: error.message };
}
  }
  async updateProject(projectId, data) {
    try {
      const projectIndex = this.projects.find(p => p.projectId === projectId);
      if (!projectIndex) {
        console.error(`[ProjectManager] 项目不存在：${projectId}`);
        return { success: false, error: '项目不存在' };
      }
      let configContent;
      try {
        configContent = await fs.readFile(projectIndex.configFile, 'utf8');
        console.log(`[ProjectManager] ✓ 成功读取配置文件：${projectIndex.configFile}`);
      } catch (readError) {
        console.error(`[ProjectManager] ✗ 读取配置文件失败：${projectIndex.configFile}`);
        console.error(`[ProjectManager] 错误详情:`, readError.message);
        throw new Error(`无法读取项目配置文件：${readError.message}`);
      }
      let projectConfig;
      try {
        projectConfig = JSON.parse(configContent);
        console.log(`[ProjectManager] JSON 解析成功`);
      } catch (parseError) {
        console.error(`[ProjectManager] JSON 解析失败`);
        console.error(`[ProjectManager] 文件内容预览:`, configContent.substring(0, 200));
        console.error(`[ProjectManager] 解析错误:`, parseError.message);
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
            console.log(`[ProjectManager] JSON 修复成功`);
          } catch (fixError) {
            console.error(`[ProjectManager] JSON 修复失败`);
            throw new Error(`项目配置文件损坏且无法修复：${parseError.message}`);
          }
        } else {
          throw new Error(`项目配置文件严重损坏：${parseError.message}`);
        }
      }
      
      const {
        status,
        currentIteration,
        loss,
        psnr,
        ssim,
        evalL1,
        evalL1Type,
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
      
      if (loss !== undefined && loss !== null && currentIteration) {
        // Check whether the Loss record of this iteration already exists
        const existingLossIndex = projectConfig.metrics.lossHistory.findIndex(
          item => item.iteration === currentIteration
        );
        
        if (existingLossIndex !== -1) {
          // If it exists, update the value
          projectConfig.metrics.lossHistory[existingLossIndex].value = loss;
        } else {
          // If it's a new iteration, add the record
          projectConfig.metrics.lossHistory.push({
            iteration: currentIteration,
            value: loss
          });
        }
      }
      
      // 2. PSNR and SSIM only save when there are valid values
      if (psnr !== undefined && psnr !== null && currentIteration) {
        const existingPsnrIndex = projectConfig.metrics.psnrHistory.findIndex(
          item => item.iteration === currentIteration
        );
        
        if (existingPsnrIndex !== -1) {
          projectConfig.metrics.psnrHistory[existingPsnrIndex].value = psnr;
        } else {
          projectConfig.metrics.psnrHistory.push({
            iteration: currentIteration,
            value: psnr
          });
        }
      }
      if (ssim !== undefined && ssim !== null && currentIteration) {
        const existingSsimIndex = projectConfig.metrics.ssimHistory.findIndex(
          item => item.iteration === currentIteration
        );
        
        if (existingSsimIndex !== -1) {
          projectConfig.metrics.ssimHistory[existingSsimIndex].value = ssim;
        } else {
          projectConfig.metrics.ssimHistory.push({
            iteration: currentIteration,
            value: ssim
          });
        }
      }
      // Eval L1 only save when there are valid values
      if (evalL1 !== undefined && evalL1 !== null && currentIteration) {
        const existingEvalL1Index = projectConfig.metrics.evalL1History.findIndex(
          item => item.iteration === currentIteration
        );
        
        if (existingEvalL1Index !== -1) {
          projectConfig.metrics.evalL1History[existingEvalL1Index].value = evalL1;
          projectConfig.metrics.evalL1History[existingEvalL1Index].type = evalL1Type || 'unknown';
        } else {
          projectConfig.metrics.evalL1History.push({
            iteration: currentIteration,
            value: evalL1,
            type: evalL1Type || 'unknown'
          });
        }
        
        console.log(`[Metrics] Eval L1 已保存 - iter: ${currentIteration}, value: ${evalL1}, type: ${evalL1Type || 'unknown'}`);
      }
      
      if (previewPath) {
        projectConfig.previewImagePath = previewPath;
      }
      
      projectConfig.lastModified = new Date().toISOString();
      projectIndex.lastModified = projectConfig.lastModified;
      console.log(`[ProjectManager] 开始写入项目配置：${projectIndex.configFile}`);
      try {
        const content = JSON.stringify(projectConfig, null, 2);
        await fs.writeFile(
          projectIndex.configFile,
          content,
          'utf8'
        );
        console.log(`[ProjectManager] 配置已更新：${projectIndex.configFile}`);
        await fs.access(projectIndex.configFile);
        const verifyContent = await fs.readFile(projectIndex.configFile, 'utf8');
        JSON.parse(verifyContent); 
        console.log(`[ProjectManager] ✓ 文件验证通过`);
      } catch (writeError) {
        console.error(`[ProjectManager] 写入项目配置失败：${writeError.message}`);
        console.error(`[ProjectManager] 错误堆栈:`, writeError.stack);
        throw writeError;
      }
      await this.saveProjects();
      return { success: true };
    } catch (error) {
      console.error('[ProjectManager] 更新项目失败:', error);
      return { success: false, error: error.message };
    }
  }
  
  getAllProjects() {
    return [...this.projects];
  }
  
  async loadProject(projectId) {
    try {
      console.log(`[ProjectManager] 开始加载项目：${projectId}`);
      const projectIndex = this.projects.find(p => p.projectId === projectId);
      if (!projectIndex) {
        console.error(`[ProjectManager] 项目不存在：${projectId}`);
        return { success: false, error: '项目不存在' };
      }
      
      console.log(`[ProjectManager] 找到项目索引，配置文件路径：${projectIndex.configFile}`);
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
  
  async scanProjects() {
    try {
      console.log('[ProjectManager] 开始扫描项目...');
      const validProjects = [];
      for (const project of this.projects) {
        try {
          await fs.access(project.configFile)
          const configContent = await fs.readFile(project.configFile, 'utf8');
          const projectConfig = JSON.parse(configContent);
          // Sync latest status from config file to projects.json
          // Including status, stage, currentIteration, etc.
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
          
          console.log(`[ProjectManager] 已同步项目 ${project.projectId} 状态：${project.status}, stage: ${project.stage}`);
          
          validProjects.push(project);
        } catch (err) {
          console.warn(`[ProjectManager] 项目配置文件不存在或损坏：${project.projectId}`);
          project.status = 'error';
        }
      }
      await this.saveProjects();
      
      console.log(`[ProjectManager] 扫描完成，找到 ${validProjects.length} 个有效项目`);
      return validProjects;
    } catch (error) {
      console.error('[ProjectManager] 扫描项目失败:', error);
      return this.projects;
    }
  }
  
  // Delete Item
  async deleteProject(projectId) {
    try {
      const index = this.projects.findIndex(p => p.projectId === projectId);
      if (index === -1) {
        return { success: false, error: '项目不存在' };
      }
      
      const project = this.projects[index];
      
      // Delete config file
      try {
        await fs.unlink(project.configFile);
      } catch (err) {
        console.warn(`[ProjectManager] 删除配置文件失败：${err.message}`);
      }
      
      // Remove from list
      this.projects.splice(index, 1);
      await this.saveProjects();
      
      console.log(`[ProjectManager] 已删除项目：${projectId}`);
      return { success: true };
    } catch (error) {
      console.error('[ProjectManager] 删除项目失败:', error);
      return { success: false, error: error.message };
    }
  }
  
  // Update Project Status
  async updateProjectStatus(projectId, status) {
    const projectIndex = this.projects.find(p => p.projectId === projectId);
    if (projectIndex) {
      projectIndex.status = status;
      projectIndex.lastModified = new Date().toISOString();
      await this.saveProjects();
      
      // Update config file simultaneously 
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
  
  // Update Project Configuration
  async updateProjectConfig(projectId, configUpdates) {
    try {
      console.log(`[ProjectManager] 开始更新项目配置：${projectId}`);
      console.log(`[ProjectManager] 更新内容:`, JSON.stringify(configUpdates, null, 2));
      const projectIndex = this.projects.find(p => p.projectId === projectId);
      if (!projectIndex) {
        console.error(`[ProjectManager] 项目不存在：${projectId}`);
        return { success: false, error: '项目不存在' };
      }
      console.log(`[ProjectManager] 找到项目，配置文件路径：${projectIndex.configFile}`);
      let configContent;
      try {
        configContent = await fs.readFile(projectIndex.configFile, 'utf8');
        console.log(`[ProjectManager] 成功读取配置文件`);
      } catch (readError) {
        console.error(`[ProjectManager] 读取配置文件失败:`, readError.message);
        throw new Error(`无法读取项目配置文件：${readError.message}`);
      }
      let projectConfig;
      try {
        projectConfig = JSON.parse(configContent);
        console.log(`[ProjectManager] ✓ JSON 解析成功`);
      } catch (parseError) {
        console.error(`[ProjectManager] ✗ JSON 解析失败：${parseError.message}`);
        console.error(`[ProjectManager] 文件内容预览:`, configContent.substring(0, 200));

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
            console.log(`[ProjectManager] JSON 修复成功`);
          } catch (fixError) {
            throw new Error(`JSON 损坏且无法修复：${parseError.message}`);
          }
        } else {
          throw new Error(`JSON 严重损坏，无法恢复：${parseError.message}`);
        }
      }
      
      console.log(`[ProjectManager] 原始配置:`, JSON.stringify(projectConfig.config, null, 2));
      
      // Merge config updates
     const { 
        projectName, outputPath, sourcePath, iterations,
        resolution, evalMode, gamma, indirect,
        bound, occluRes, occlusion, checkpoint,
       bakingStatus, bakingProgress, bakingLogs,
       isTraining, isBaking, currentIteration
      } = configUpdates;
     if (projectName !== undefined) {
        projectConfig.name = projectName;
        projectIndex.name = projectName;
      }
     if (outputPath !== undefined) projectConfig.outputPath = outputPath;
     if (sourcePath !== undefined) projectConfig.sourcePath = sourcePath;
     if (checkpoint !== undefined) projectConfig.checkpoint = checkpoint;
     if (iterations !== undefined) projectConfig.totalIterations = iterations;
           
      if (isTraining !== undefined) {
        projectConfig.status = isTraining ? 'training' : projectConfig.status;
      }
      if (isBaking !== undefined) {
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
           
     if (bakingStatus !== undefined) {
        projectConfig.bakingStatus = bakingStatus;
        if (bakingStatus === 'running') {
          projectConfig.stage = 'baking';
          projectIndex.stage = 'baking';
        }
      }
     if (bakingProgress !== undefined) projectConfig.bakingProgress = bakingProgress;
     if (bakingLogs !== undefined) {
        projectConfig.bakingLogs = Array.isArray(bakingLogs) ? bakingLogs.slice(-200) : [];
      }
      
      if (resolution !== undefined) projectConfig.config.resolution = resolution;
      if (evalMode !== undefined) projectConfig.config.evalMode = evalMode;
      if (gamma !== undefined) projectConfig.config.gamma = gamma;
      if (indirect !== undefined) projectConfig.config.indirect = indirect;
      if (bound !== undefined) projectConfig.config.bound = bound;
      if (occluRes !== undefined) projectConfig.config.occluRes = occluRes;
      if (occlusion !== undefined) projectConfig.config.occlusion = occlusion;
      
      // Update timestamp
      projectConfig.lastModified = new Date().toISOString();
      projectIndex.lastModified = projectConfig.lastModified;
      
      // Write back to file
      console.log(`[ProjectManager] 开始写入配置文件：${projectIndex.configFile}`);
      try {
        const content = JSON.stringify(projectConfig, null, 2);
        await fs.writeFile(
          projectIndex.configFile,
          content,
          'utf8'
        );
        console.log(`[ProjectManager] 配置文件已更新：${projectIndex.configFile}`);
        await fs.access(projectIndex.configFile);
        const verifyContent = await fs.readFile(projectIndex.configFile, 'utf8');
        JSON.parse(verifyContent); 
        console.log(`[ProjectManager] 文件验证成功`);
      } catch (writeError) {
        console.error(`[ProjectManager] 写入配置文件失败：${writeError.message}`);
        console.error(`[ProjectManager] 错误堆栈:`, writeError.stack);
        throw writeError;
      }
      
      // Update global index
      await this.saveProjects();
      
      console.log(`[ProjectManager] 项目配置已保存：${projectId}`);
      return { success: true };
    } catch(error) {
     console.error(`[ProjectManager] 更新项目配置失败:`, error);
      return { success: false, error: error.message };
    }
  }
  
  // Check Training Completion
  async checkTrainingCompletion(projectId) {
    try {
      const projectIndex = this.projects.find(p => p.projectId === projectId);
      if (!projectIndex) {
        console.error(`[ProjectManager] 项目不存在：${projectId}`);
        return { success: false, error: '项目不存在' };
      }
      const configContent = await fs.readFile(projectIndex.configFile, 'utf8');
      const projectConfig = JSON.parse(configContent);
      
      const outputPath = projectConfig.outputPath;
      const checkpointFile = path.join(outputPath, 'chkpnt40000.pth');
      
      try {
        await fs.access(checkpointFile);
        console.log(`[ProjectManager] 检测到完成标记文件：${checkpointFile}`);
        
        projectConfig.status = 'completed';
        projectIndex.status = 'completed';
        projectConfig.lastModified = new Date().toISOString();
        projectIndex.lastModified = projectConfig.lastModified;
        
        // Write back to file
        await fs.writeFile(
          projectIndex.configFile,
          JSON.stringify(projectConfig, null, 2),
          'utf8'
        );
        
        await this.saveProjects();
        
        console.log(`[ProjectManager] 项目 ${projectId} 状态已更新为 completed`);
        return { success: true, completed: true };
      } catch (err) {
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
