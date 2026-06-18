/**
 * Gaussian Splatting 几何体生成器
 * 使用 InstancedMesh 创建 3D 椭球表示高斯分布
 */

import * as THREE from 'three';

export class GaussianGeometry {
  constructor() {
    // 基础球体几何（用于实例化）
    this.baseGeometry = null;
    // 实例数量
    this.instanceCount = 0;
    // 实例化网格
    this.instancedMesh = null;
  }

  /**
   * 创建高斯椭球实例化网格
   * @param {Object} gaussianData - 高斯参数
   * @returns {THREE.InstancedMesh} 实例化网格
   */
  createInstancedMesh(gaussianData) {
    const { positions, rotations, scalings, colors, opacities } = gaussianData;
    const numGaussians = positions.length / 3;
    
    console.log('[GaussianGeometry] 开始创建实例化网格，高斯数量:', numGaussians);

    // 1. 创建基础球体几何（低多边形以提高性能）
    // 注意：这里使用 8x8 的细分，在质量和性能间平衡
    this.baseGeometry = new THREE.SphereGeometry(1, 8, 8);

    // 2. 创建自定义 Shader 材质
    const material = new THREE.ShaderMaterial({
      vertexShader: `
        precision highp float;
              
        uniform mat4 modelViewMatrix;
        uniform mat4 projectionMatrix;
        uniform mat4 modelMatrix;
              
        attribute vec3 translation;
        attribute vec4 rotation;
        attribute vec3 scale;
        attribute vec3 color;
        attribute float opacity;
              
        varying vec3 vColor;
        varying float vOpacity;
        varying vec3 vNormal;
        varying vec3 vWorldPosition;
        varying vec2 vUV;
        varying vec3 vViewPosition;
              
        void main() {
          vColor = color;
          vOpacity = opacity;
          vNormal = normal;
          vUV = uv;
                
          // 从四元数构建旋转矩阵
          vec3 qv = rotation.xyz;
          float qw = rotation.w;
          mat3 rotMatrix = mat3(
            1.0 - 2.0 * (qv.y * qv.y + qv.z * qv.z),
            2.0 * (qv.x * qv.y + qv.z * qw),
            2.0 * (qv.x * qv.z - qv.y * qw),
            2.0 * (qv.x * qv.y - qv.z * qw),
            1.0 - 2.0 * (qv.x * qv.x + qv.z * qv.z),
            2.0 * (qv.y * qv.z + qv.x * qw),
            2.0 * (qv.x * qv.z + qv.y * qw),
            2.0 * (qv.y * qv.z - qv.x * qw),
            1.0 - 2.0 * (qv.x * qv.x + qv.y * qv.y)
          );
                
          // 应用变换：缩放 -> 旋转 -> 平移
          vec3 transformedPosition = position * scale;
          transformedPosition = rotMatrix * transformedPosition;
          transformedPosition += translation;
                
          vec4 mvPosition = modelViewMatrix * vec4(transformedPosition, 1.0);
          gl_Position = projectionMatrix * mvPosition;
                
          vWorldPosition = (modelMatrix * vec4(transformedPosition, 1.0)).xyz;
          vViewPosition = -mvPosition.xyz;
        }
      `,
      fragmentShader: `
        precision highp float;
              
        uniform vec3 lightPosition;
        uniform vec3 lightIntensity;
        uniform float metallic;
        uniform float roughness;
              
        varying vec3 vColor;
        varying float vOpacity;
        varying vec3 vNormal;
        varying vec3 vWorldPosition;
        varying vec2 vUV;
        varying vec3 vViewPosition;
              
        #define PI 3.14159265359
        #define EPSILON 1e-4
              
        // 高斯密度函数
        float computeGaussianDensity(vec2 uv) {
          vec2 centerCoord = uv - 0.5;
          float r2 = dot(centerCoord, centerCoord) * 4.0;
          return exp(-3.0 * r2);
        }
              
        // Distribution GGX (NDF)
        float DistributionGGX(vec3 N, vec3 H, float roughness) {
          float a = roughness * roughness;
          float a2 = a * a;
          float NdotH = max(dot(N, H), 0.0);
          float NdotH2 = NdotH * NdotH;
          
          float nom = a2;
          float denom = (NdotH2 * (a2 - 1.0) + 1.0);
          denom = PI * denom * denom;
          
          return nom / max(denom, EPSILON);
        }
              
        // Geometry Smith
        float GeometrySmith(vec3 N, vec3 V, vec3 L, float roughness) {
          float r = roughness + 1.0;
          float k = (r * r) / 8.0;
          
          float NdotV = max(dot(N, V), 0.0);
          float NdotL = max(dot(N, L), 0.0);
          
          float ggx2 = NdotV / (NdotV * (1.0 - k) + k);
          float ggx1 = NdotL / (NdotL * (1.0 - k) + k);
          
          return ggx1 * ggx2;
        }
              
        // Fresnel Schlick
        vec3 fresnelSchlick(float cosTheta, vec3 F0) {
          return F0 + (1.0 - F0) * pow(clamp(1.0 - cosTheta, 0.0, 1.0), 5.0);
        }
              
        // Tone Mapping (ACES)
        vec3 acesFilm(vec3 x) {
          const float a = 2.51;
          const float b = 0.03;
          const float c = 2.43;
          const float d = 0.59;
          const float e = 0.14;
          return clamp((x * (a * x + b)) / (x * (c * x + d) + e), 0.0, 1.0);
        }
              
        void main() {
          // 计算高斯密度
          float gaussian = computeGaussianDensity(vUV);
          if (gaussian < 0.01) discard;
                
          // PBR Cook-Torrance BRDF
          vec3 N = normalize(vNormal);
          vec3 V = normalize(vViewPosition);
          vec3 L = normalize(lightPosition - vWorldPosition);
          vec3 H = normalize(V + L);
          
          // 距离衰减
          float distanceToLight = length(lightPosition - vWorldPosition);
          float attenuation = 1.0 / (distanceToLight * distanceToLight + 1.0);
          vec3 radiance = lightIntensity * attenuation;
          
          // F0 - 基础反射率
          vec3 F0 = vec3(0.04);
          F0 = mix(F0, vColor, metallic);
          
          // Cook-Torrance BRDF 分量
          float NDF = DistributionGGX(N, H, roughness);
          float G = GeometrySmith(N, V, L, roughness);
          vec3 F = fresnelSchlick(max(dot(H, V), 0.0), F0);
          
          // 镜面反射
          vec3 numerator = NDF * G * F;
          float denominator = 4.0 * max(dot(N, V), EPSILON) * max(dot(N, L), EPSILON) + EPSILON;
          vec3 specular = numerator / denominator;
          
          // 漫反射
          vec3 kS = F;
          vec3 kD = 1.0 - kS;
          kD *= 1.0 - metallic;
          
          float NdotL = max(dot(N, L), 0.0);
          vec3 diffuse = (kD * vColor / PI) * radiance * NdotL;
          
          // 最终颜色 = 漫反射 + 镜面反射
          vec3 color = diffuse + specular;
          
          // 应用高斯密度
          color *= gaussian;
          
          // ACES Tone Mapping
          color = acesFilm(color);
          
          // Gamma 校正
          color = pow(color, vec3(1.0 / 2.2));
          
          // 最终透明度
          float finalAlpha = vOpacity * gaussian * 0.9;
          
          gl_FragColor = vec4(color, finalAlpha);
        }
      `,
      transparent: true,
      depthWrite: false,
      depthTest: true,
      blending: THREE.AdditiveBlending,
      side: THREE.DoubleSide,
      uniforms: {
        lightPosition: { value: new THREE.Vector3(5, 5, 5) },
        lightIntensity: { value: new THREE.Vector3(1, 1, 1) },
        metallic: { value: 0.0 },
        roughness: { value: 0.5 }
      }
    });

    // 3. 创建实例化网格
    this.instancedMesh = new THREE.InstancedMesh(
      this.baseGeometry,
      material,
      numGaussians
    );

    // 4. 设置实例属性
    const dummy = new THREE.Object3D();
    
    for (let i = 0; i < numGaussians; i++) {
      // 位置
      dummy.position.set(
        positions[i * 3 + 0],
        positions[i * 3 + 1],
        positions[i * 3 + 2]
      );
      
      // 旋转（四元数）
      dummy.quaternion.set(
        rotations[i * 4 + 0],
        rotations[i * 4 + 1],
        rotations[i * 4 + 2],
        rotations[i * 4 + 3]
      );
      
      // 缩放
      dummy.scale.set(
        scalings[i * 3 + 0],
        scalings[i * 3 + 1],
        scalings[i * 3 + 2]
      );
      
      dummy.updateMatrix();
      this.instancedMesh.setMatrixAt(i, dummy.matrix);
    }

    // 5. 设置颜色属性
    const colorAttribute = new THREE.InstancedBufferAttribute(colors, 3);
    this.instancedMesh.geometry.setAttribute('color', colorAttribute);

    // 6. 设置透明度属性
    const opacityAttribute = new THREE.InstancedBufferAttribute(opacities, 1);
    this.instancedMesh.geometry.setAttribute('opacity', opacityAttribute);

    // 7. 设置位移属性（与 matrix 分开，用于 shader）
    const translationAttribute = new THREE.InstancedBufferAttribute(positions, 3);
    this.instancedMesh.geometry.setAttribute('translation', translationAttribute);

    // 8. 设置旋转属性
    const rotationAttribute = new THREE.InstancedBufferAttribute(rotations, 4);
    this.instancedMesh.geometry.setAttribute('rotation', rotationAttribute);

    // 9. 设置缩放属性
    const scalingAttribute = new THREE.InstancedBufferAttribute(scalings, 3);
    this.instancedMesh.geometry.setAttribute('scale', scalingAttribute);

    this.instanceCount = numGaussians;
    
    console.log('[GaussianGeometry] ✓ 实例化网格创建完成');
    console.log('  - 实例数量:', numGaussians);
    console.log('  - 材质:', material);
    
    return this.instancedMesh;
  }

  /**
   * 更新实例属性（用于动态更新）
   * @param {number} index - 实例索引
   * @param {Object} data - 新数据
   */
  updateInstance(index, data) {
    if (!this.instancedMesh || index >= this.instanceCount) return;

    const dummy = new THREE.Object3D();
    
    dummy.position.set(data.x, data.y, data.z);
    dummy.quaternion.set(data.rX, data.rY, data.rZ, data.rW);
    dummy.scale.set(data.sX, data.sY, data.sZ);
    dummy.updateMatrix();
    
    this.instancedMesh.setMatrixAt(index, dummy.matrix);
    this.instancedMesh.instanceMatrix.needsUpdate = true;
  }

  /**
   * 获取实例数量
   * @returns {number} 实例数量
   */
  getInstanceCount() {
    return this.instanceCount;
  }

  /**
   * 清理资源
   */
  dispose() {
    if (this.instancedMesh) {
      this.instancedMesh.geometry.dispose();
      this.instancedMesh.material.dispose();
      this.instancedMesh = null;
    }
    
    if (this.baseGeometry) {
      this.baseGeometry.dispose();
      this.baseGeometry = null;
    }
    
    this.instanceCount = 0;
  }
}
