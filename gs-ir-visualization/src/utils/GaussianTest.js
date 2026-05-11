/**
 * 高斯模型加载测试脚本
 * 用于诊断加载流程中的问题
 */

import * as THREE from 'three';
import { GaussianLoader } from './GaussianLoader.js';
import { GaussianGeometry } from './GaussianGeometry.js';

export async function testGaussianLoading() {
  console.log('🧪 ========== 开始高斯模型加载测试 ==========');
  
  // 测试 1: 检查后端服务是否可用
  console.log('\n📡 测试 1: 检查 PBR 服务状态...');
  try {
    const healthResponse = await fetch('http://localhost:5000/api/health');
    const healthData = await healthResponse.json();
    console.log('✓ PBR 服务状态:', healthData);
  } catch (error) {
    console.error('❌ PBR 服务不可用:', error);
    console.log('💡 请确保已启动 pbr_render_service.py');
    return;
  }
  
  // 测试 2: 尝试获取高斯数据
  console.log('\n📦 测试 2: 获取高斯数据...');
  const testCheckpointPath = prompt('请输入 checkpoint 文件路径:', 'E:/GraduationProject/LuminaGS/output/chkpnt3000.pth');
  if (!testCheckpointPath) {
    console.log('⚠️ 用户取消测试');
    return;
  }
  
  const loader = new GaussianLoader();
  const loadResult = await loader.loadCheckpoint(testCheckpointPath);
  
  if (!loadResult.success) {
    console.error('❌ 加载失败:', loadResult.error);
    return;
  }
  
  console.log('✓ 高斯数据加载成功!');
  console.log('  - 高斯数量:', loadResult.data.num_gaussians);
  console.log('  - SH 阶数:', loadResult.data.sh_degree);
  
  // 测试 3: 创建 Three.js 场景并显示
  console.log('\n🎨 测试 3: 创建 Three.js 场景...');
  
  // 创建简单场景
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x1a1a1a);
  
  const camera = new THREE.PerspectiveCamera(
    75,
    window.innerWidth / window.innerHeight,
    0.1,
    1000
  );
  
  const renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setSize(window.innerWidth, window.innerHeight);
  document.body.appendChild(renderer.domElement);
  
  // 添加坐标轴
  const axesHelper = new THREE.AxesHelper(2);
  scene.add(axesHelper);
  
  // 创建高斯几何体
  const geometryGenerator = new GaussianGeometry();
  const gaussianData = loadResult.data;
  
  const instanceData = {
    positions: gaussianData.xyz.flat(),
    rotations: gaussianData.rotation.map(r => [r[1], r[2], r[3], r[0]]).flat(),
    scalings: gaussianData.scaling.flat(),
    colors: gaussianData.features_dc.flat(),
    opacities: gaussianData.opacity.flat()
  };
  
  console.log('📊 实例数据:');
  console.log('  - 位置:', instanceData.positions.length);
  console.log('  - 旋转:', instanceData.rotations.length);
  console.log('  - 缩放:', instanceData.scalings.length);
  
  const gaussianMesh = geometryGenerator.createInstancedMesh(instanceData);
  scene.add(gaussianMesh);
  
  console.log('✓ 高斯网格已添加到场景');
  
  // 计算边界框
  let minX = Infinity, minY = Infinity, minZ = Infinity;
  let maxX = -Infinity, maxY = -Infinity, maxZ = -Infinity;
  
  for (let i = 0; i < gaussianData.xyz.length; i++) {
    const x = gaussianData.xyz[i][0];
    const y = gaussianData.xyz[i][1];
    const z = gaussianData.xyz[i][2];
    
    minX = Math.min(minX, x);
    minY = Math.min(minY, y);
    minZ = Math.min(minZ, z);
    maxX = Math.max(maxX, x);
    maxY = Math.max(maxY, y);
    maxZ = Math.max(maxZ, z);
  }
  
  const center = {
    x: (minX + maxX) / 2,
    y: (minY + maxY) / 2,
    z: (minZ + maxZ) / 2
  };
  
  const size = {
    x: maxX - minX,
    y: maxY - minY,
    z: maxZ - minZ
  };
  
  console.log('📐 模型边界框:');
  console.log('  - 尺寸:', size.x.toFixed(2), 'x', size.y.toFixed(2), 'x', size.z.toFixed(2));
  console.log('  - 中心:', center.x.toFixed(2), ',', center.y.toFixed(2), ',', center.z.toFixed(2));
  
  // 调整相机位置
  const maxDim = Math.max(size.x, size.y, size.z);
  const fov = camera.fov * (Math.PI / 180);
  const distance = maxDim / (2 * Math.tan(fov / 2)) * 1.5;
  
  camera.position.set(
    center.x + distance,
    center.y + distance * 0.5,
    center.z + distance
  );
  camera.lookAt(center.x, center.y, center.z);
  
  console.log('📷 相机位置:', camera.position);
  
  // 动画循环
  function animate() {
    requestAnimationFrame(animate);
    renderer.render(scene, camera);
  }
  
  animate();
  
  console.log('\n✅ 测试完成！模型应该已经显示在浏览器中。');
  console.log('💡 使用鼠标左键旋转、右键平移、滚轮缩放。');
  console.log('💡 按 F12 打开控制台查看详细日志。');
  
  // 添加清理提示
  setTimeout(() => {
    console.log('\n⚠️ 提示: 刷新页面可清理测试场景。');
  }, 2000);
}

// 自动运行测试（在浏览器控制台中）
if (typeof window !== 'undefined') {
  window.testGaussianLoading = testGaussianLoading;
  console.log('🚀 高斯测试脚本已加载，在控制台输入 testGaussianLoading() 开始测试');
}
