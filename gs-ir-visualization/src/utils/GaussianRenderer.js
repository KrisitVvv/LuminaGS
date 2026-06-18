/**
 * Gaussian Splatting 渲染器
 * 负责将高斯模型渲染到 Three.js 场景
 */

import * as THREE from 'three';
import { GaussianLoader } from './GaussianLoader.js';
import { GaussianGeometry } from './GaussianGeometry.js';

export class GaussianRenderer {
  constructor(scene, camera) {
    this.scene = scene;
    this.camera = camera;
    
    // 加载器和几何生成器
    this.loader = new GaussianLoader();
    this.geometryGenerator = new GaussianGeometry();
    
    // 高斯网格引用
    this.gaussianMesh = null;
    
    // 状态
    this.isLoaded = false;
    this.checkpointPath = null;
    this.numGaussians = 0;
    
    // 渲染设置
    this.settings = {
      showGizmos: false,
      displayMode: 'ellipsoids', // 'ellipsoids' | 'points'
      maxGaussians: 1000000, // 性能限制
      renderMode: 'frontend', // 'frontend' | 'backend' | 'hybrid'
      lodEnabled: false,
      shadowCaching: true
    };
    
    // 性能监控
    this.performanceMetrics = {
      fps: 0,
      renderTime: 0,
      lastFrameTime: 0
    };
  }

  /**
   * 从球谐系数计算颜色（支持高阶 SH）
   * @param {Object} gaussianData - 高斯数据
   * @returns {Float32Array} RGB 颜色数组
   */
  computeColorsFromSH(gaussianData) {
    const numGaussians = gaussianData.xyz.length;
    const colors = new Float32Array(numGaussians * 3);
    
    // 如果只有 DC 分量，直接返回
    if (!gaussianData.features_rest || gaussianData.sh_degree <= 1) {
      for (let i = 0; i < numGaussians; i++) {
        colors[i * 3 + 0] = Math.max(0, Math.min(1, gaussianData.features_dc[i][0]));
        colors[i * 3 + 1] = Math.max(0, Math.min(1, gaussianData.features_dc[i][1]));
        colors[i * 3 + 2] = Math.max(0, Math.min(1, gaussianData.features_dc[i][2]));
      }
      return colors;
    }
    
    // TODO: 实现高阶球谐函数插值
    // 目前仍仅使用 DC 分量，预留接口供后续扩展
    console.log('[GaussianRenderer] 检测到高阶 SH 系数，当前版本仅使用 DC 分量');
    for (let i = 0; i < numGaussians; i++) {
      colors[i * 3 + 0] = Math.max(0, Math.min(1, gaussianData.features_dc[i][0]));
      colors[i * 3 + 1] = Math.max(0, Math.min(1, gaussianData.features_dc[i][1]));
      colors[i * 3 + 2] = Math.max(0, Math.min(1, gaussianData.features_dc[i][2]));
    }
    
    return colors;
  }

  /**
   * 加载并渲染高斯模型
   * @param {string} checkpointPath - .pth 文件路径
   * @returns {Promise<Object>} 加载结果
   */
  async loadModel(checkpointPath) {
    try {
      console.log('[GaussianRenderer] 开始加载高斯模型:', checkpointPath);
      
      // 1. 清理旧模型
      if (this.gaussianMesh) {
        this.removeModel();
      }
      
      // 2. 加载高斯数据
      const loadResult = await this.loader.loadCheckpoint(checkpointPath);
      
      if (!loadResult.success) {
        throw new Error(loadResult.error || '加载失败');
      }
      
      const gaussianData = loadResult.data;
      
      // 3. 检查高斯数量
      if (gaussianData.num_gaussians > this.settings.maxGaussians) {
        console.warn(`[GaussianRenderer] ⚠️ 高斯数量 ${gaussianData.num_gaussians} 超过限制 ${this.settings.maxGaussians}，可能影响性能`);
      }
      
      // 4. 准备实例化数据（转换为 Typed Array）
      const instanceData = {
        positions: new Float32Array(gaussianData.xyz.flat()),
        rotations: new Float32Array(gaussianData.rotation.map(r => [r[1], r[2], r[3], r[0]]).flat()), // [w,x,y,z] -> [x,y,z,w]
        scalings: new Float32Array(gaussianData.scaling.flat()),
        colors: this.computeColorsFromSH(gaussianData), // 使用球谐函数计算颜色
        // 应用 sigmoid 函数将 log(opacity) 转换为实际透明度
        opacities: new Float32Array(gaussianData.opacity.map(o => 1 / (1 + Math.exp(-o[0]))))
      };
      
      console.log('[GaussianRenderer] 数据准备完成:');
      console.log('  - 位置数组长度:', instanceData.positions.length);
      console.log('  - 旋转数组长度:', instanceData.rotations.length);
      console.log('  - 缩放数组长度:', instanceData.scalings.length);
      console.log('  - 颜色数组长度:', instanceData.colors.length);
      console.log('  - 透明度数组长度:', instanceData.opacities.length);
      
      // 5. 创建实例化网格
      this.gaussianMesh = this.geometryGenerator.createInstancedMesh(instanceData);
      
      // 6. 添加到场景
      if (this.gaussianMesh) {
        this.scene.add(this.gaussianMesh);
        console.log('[GaussianRenderer] ✓ 高斯模型已添加到场景');
        
        this.isLoaded = true;
        this.checkpointPath = checkpointPath;
        this.numGaussians = gaussianData.num_gaussians;
        
        return {
          success: true,
          numGaussians: this.numGaussians,
          message: `成功加载 ${this.numGaussians.toLocaleString()} 个高斯椭球`
        };
      } else {
        throw new Error('创建实例化网格失败');
      }
    } catch (error) {
      console.error('[GaussianRenderer] ❌ 加载高斯模型失败:', error);
      return {
        success: false,
        error: error.message
      };
    }
  }

  /**
   * 从场景中移除高斯模型
   */
  removeModel() {
    if (this.gaussianMesh) {
      this.scene.remove(this.gaussianMesh);
      this.geometryGenerator.dispose();
      this.loader.dispose();
      this.gaussianMesh = null;
      this.isLoaded = false;
      this.numGaussians = 0;
      console.log('[GaussianRenderer] ✓ 模型已移除');
    }
  }

  /**
   * 更新渲染设置
   * @param {Object} newSettings - 新设置
   */
  updateSettings(newSettings) {
    this.settings = { ...this.settings, ...newSettings };
    
    // 如果切换显示模式，需要重新加载
    if (newSettings.displayMode && this.isLoaded) {
      this.loadModel(this.checkpointPath);
    }
  }

  /**
   * 获取高斯数量
   * @returns {number} 高斯数量
   */
  getNumGaussians() {
    return this.numGaussians;
  }

  /**
   * 检查是否已加载
   * @returns {boolean} 是否已加载
   */
  getIsLoaded() {
    return this.isLoaded;
  }

  /**
   * 获取边界框
   * @returns {Object|null} 边界框信息
   */
  getBoundingBox() {
    if (!this.gaussianMesh) return null;
    
    const positions = this.loader.getPositions();
    if (!positions) return null;
    
    let minX = Infinity, minY = Infinity, minZ = Infinity;
    let maxX = -Infinity, maxY = -Infinity, maxZ = -Infinity;
    
    for (let i = 0; i < positions.length / 3; i++) {
      const x = positions[i * 3];
      const y = positions[i * 3 + 1];
      const z = positions[i * 3 + 2];
      
      minX = Math.min(minX, x);
      minY = Math.min(minY, y);
      minZ = Math.min(minZ, z);
      maxX = Math.max(maxX, x);
      maxY = Math.max(maxY, y);
      maxZ = Math.max(maxZ, z);
    }
    
    return {
      min: { x: minX, y: minY, z: minZ },
      max: { x: maxX, y: maxY, z: maxZ },
      center: {
        x: (minX + maxX) / 2,
        y: (minY + maxY) / 2,
        z: (minZ + maxZ) / 2
      },
      size: {
        x: maxX - minX,
        y: maxY - minY,
        z: maxZ - minZ
      }
    };
  }

  /**
   * 自动调整相机视角以包含整个模型
   */
  fitCameraToBounds() {
    const bounds = this.getBoundingBox();
    if (!bounds || !this.camera) return;
    
    const size = bounds.size;
    const center = bounds.center;
    const maxDim = Math.max(size.x, size.y, size.z);
    
    // 计算合适的相机距离
    const fov = this.camera.fov * (Math.PI / 180);
    const distance = maxDim / (2 * Math.tan(fov / 2)) * 1.5; // 1.5 倍余量
    
    // 设置相机位置（在对角线方向）
    this.camera.position.set(
      center.x + distance,
      center.y + distance * 0.5,
      center.z + distance
    );
    
    // 看向中心
    this.camera.lookAt(center.x, center.y, center.z);
    
    console.log('[GaussianRenderer] 📷 相机已调整到最佳视角');
    console.log('  - 模型尺寸:', size.x.toFixed(2), 'x', size.y.toFixed(2), 'x', size.z.toFixed(2));
    console.log('  - 模型中心:', center.x.toFixed(2), ',', center.y.toFixed(2), ',', center.z.toFixed(2));
    console.log('  - 相机距离:', distance.toFixed(2));
  }

  /**
   * 清理资源
   */
  dispose() {
    this.removeModel();
    this.scene = null;
    this.camera = null;
  }
  
  /**
   * 设置渲染模式
   * @param {string} mode - 'frontend' | 'backend' | 'hybrid'
   */
  setRenderMode(mode) {
    this.settings.renderMode = mode;
    console.log('[GaussianRenderer] 渲染模式已设置为:', mode);
  }
  
  /**
   * 启用/禁用 LOD
   * @param {boolean} enabled
   */
  enableLOD(enabled) {
    this.settings.lodEnabled = enabled;
    console.log('[GaussianRenderer] LOD 已', enabled ? '启用' : '禁用');
  }
  
  /**
   * 启用/禁用阴影缓存
   * @param {boolean} enabled
   */
  enableShadowCaching(enabled) {
    this.settings.shadowCaching = enabled;
    console.log('[GaussianRenderer] 阴影缓存已', enabled ? '启用' : '禁用');
  }
  
  /**
   * 获取性能指标
   * @returns {Object} FPS、渲染耗时等
   */
  getPerformanceMetrics() {
    const now = performance.now();
    const deltaTime = now - this.performanceMetrics.lastFrameTime;
    
    this.performanceMetrics.fps = 1000 / deltaTime;
    this.performanceMetrics.renderTime = deltaTime;
    this.performanceMetrics.lastFrameTime = now;
    
    return {
      fps: this.performanceMetrics.fps.toFixed(1),
      renderTime: this.performanceMetrics.renderTime.toFixed(2),
      gaussianCount: this.numGaussians
    };
  }
}
