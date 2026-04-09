/**
 * Gaussian Splatting 模型加载器
 * 负责解析 .pth checkpoint 文件并提取高斯参数
 */

import * as THREE from 'three';

export class GaussianLoader {
  constructor() {
    this.gaussians = null;
  }

  /**
   * 从后端 API 加载高斯模型数据
   * @param {string} checkpointPath - .pth 文件路径
   * @returns {Promise<Object>} 高斯模型数据
   */
  async loadCheckpoint(checkpointPath) {
    try {
      console.log('[GaussianLoader] 开始加载 checkpoint:', checkpointPath);

      // 调用后端 API 获取高斯参数
      const response = await fetch('http://localhost:5000/api/get_gaussian_data', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          checkpoint_path: checkpointPath 
        })
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      
      if (data.success) {
        console.log('[GaussianLoader] ✓ Checkpoint 加载成功');
        console.log('  - 高斯数量:', data.num_gaussians);
        console.log('  - 球谐阶数:', data.sh_degree);
        
        this.gaussians = {
          xyz: data.xyz,              // [N, 3] 位置
          rotation: data.rotation,    // [N, 4] 四元数
          scaling: data.scaling,      // [N, 3] 缩放
          opacity: data.opacity,      // [N, 1] 不透明度（log 空间）
          features_dc: data.features, // [N, 3] 基础颜色（SH 第 0 阶）
          features_rest: data.features_rest || null, // [N, (sh_degree²-1)*3] 高阶 SH 系数（可选）
          sh_degree: data.sh_degree,
          num_gaussians: data.num_gaussians
        };

        return {
          success: true,
          data: this.gaussians
        };
      } else {
        throw new Error(data.message || '加载失败');
      }
    } catch (error) {
      console.error('[GaussianLoader] ❌ 加载 checkpoint 失败:', error);
      return {
        success: false,
        error: error.message
      };
    }
  }

  /**
   * 获取高斯位置
   * @returns {Float32Array} 位置数组
   */
  getPositions() {
    if (!this.gaussians) return null;
    
    const positions = new Float32Array(this.gaussians.xyz.length * 3);
    for (let i = 0; i < this.gaussians.xyz.length; i++) {
      positions[i * 3 + 0] = this.gaussians.xyz[i][0];
      positions[i * 3 + 1] = this.gaussians.xyz[i][1];
      positions[i * 3 + 2] = this.gaussians.xyz[i][2];
    }
    return positions;
  }

  /**
   * 获取高斯旋转（四元数）
   * @returns {Float32Array} 四元数数组 [x, y, z, w]
   */
  getRotations() {
    if (!this.gaussians) return null;
    
    const rotations = new Float32Array(this.gaussians.rotation.length * 4);
    for (let i = 0; i < this.gaussians.rotation.length; i++) {
      // PyTorch: [w, x, y, z] -> Three.js: [x, y, z, w]
      rotations[i * 4 + 0] = this.gaussians.rotation[i][1];
      rotations[i * 4 + 1] = this.gaussians.rotation[i][2];
      rotations[i * 4 + 2] = this.gaussians.rotation[i][3];
      rotations[i * 4 + 3] = this.gaussians.rotation[i][0];
    }
    return rotations;
  }

  /**
   * 获取高斯缩放
   * @returns {Float32Array} 缩放数组
   */
  getScalings() {
    if (!this.gaussians) return null;
    
    const scalings = new Float32Array(this.gaussians.scaling.length * 3);
    for (let i = 0; i < this.gaussians.scaling.length; i++) {
      scalings[i * 3 + 0] = this.gaussians.scaling[i][0];
      scalings[i * 3 + 1] = this.gaussians.scaling[i][1];
      scalings[i * 3 + 2] = this.gaussians.scaling[i][2];
    }
    return scalings;
  }

  /**
   * 获取高斯不透明度
   * @returns {Float32Array} 不透明度数组
   */
  getOpacities() {
    if (!this.gaussians) return null;
    
    const opacities = new Float32Array(this.gaussians.opacity.length);
    for (let i = 0; i < this.gaussians.opacity.length; i++) {
      opacities[i] = this.gaussians.opacity[i][0];
    }
    return opacities;
  }

  /**
   * 获取高斯颜色（仅使用 SH 第 0 阶）
   * @returns {Float32Array} 颜色数组 [r, g, b]
   */
  getColors() {
    if (!this.gaussians) return null;
    
    const colors = new Float32Array(this.gaussians.features_dc.length * 3);
    for (let i = 0; i < this.gaussians.features_dc.length; i++) {
      // SH 系数转换为 RGB [0, 1]
      colors[i * 3 + 0] = Math.max(0, Math.min(1, this.gaussians.features_dc[i][0]));
      colors[i * 3 + 1] = Math.max(0, Math.min(1, this.gaussians.features_dc[i][1]));
      colors[i * 3 + 2] = Math.max(0, Math.min(1, this.gaussians.features_dc[i][2]));
    }
    return colors;
  }

  /**
   * 获取高斯数量
   * @returns {number} 高斯数量
   */
  getNumGaussians() {
    return this.gaussians ? this.gaussians.num_gaussians : 0;
  }

  /**
   * 清理资源
   */
  dispose() {
    this.gaussians = null;
  }
}
