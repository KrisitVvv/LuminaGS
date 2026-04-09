<template>
  <section class="editor-container">
    <div class="top-bar">
      <div class="menu-section">
        <div class="logo">
          <span class="iconify" data-icon="solar:3d-cube-bold"></span>
          <span class="app-name">LuminaGS</span>
          <span class="version-tag">v2.0</span>
        </div>
        <div class="menu-items">
          <div class="menu-item" @click="showDropdown = showDropdown === 'file' ? null : 'file'">
            File
            <div v-if="showDropdown === 'file'" class="dropdown-menu">
              <div class="dropdown-item" @click="importModel">
                <span class="iconify" data-icon="solar:upload-bold"></span>
                Import Model
              </div>
              <div class="dropdown-item" @click="exportModel">
                <span class="iconify" data-icon="solar:download-bold"></span>
                Export Model
              </div>
              <div class="dropdown-divider"></div>
              <div class="dropdown-item" @click="saveProject">
                <span class="iconify" data-icon="solar:disk-bold"></span>
                Save Project
              </div>
            </div>
          </div>
          <div class="menu-item" @click="showDropdown = showDropdown === 'edit' ? null : 'edit'">
            Edit
            <div v-if="showDropdown === 'edit'" class="dropdown-menu">
              <div class="dropdown-item" @click="undo">
                <span class="iconify" data-icon="solar:undo-bold"></span>
                Undo
              </div>
              <div class="dropdown-item" @click="redo">
                <span class="iconify" data-icon="solar:redo-bold"></span>
                Redo
              </div>
            </div>
          </div>
          <div class="menu-item" @click="showDropdown = showDropdown === 'render' ? null : 'render'">
            Render
            <div v-if="showDropdown === 'render'" class="dropdown-menu">
              <div class="dropdown-item" @click="startRender">
                <span class="iconify" data-icon="solar:camera-bold"></span>
                Start Rendering
              </div>
              <div class="dropdown-item" @click="toggleRealtime">
                <span class="iconify" :data-icon="realtimeEnabled ? 'solar:pause-circle-bold' : 'solar:play-circle-bold'"></span>
                {{ realtimeEnabled ? 'Pause' : 'Resume' }} Real-time
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="workspace-tabs">
        <div 
          class="workspace-tab" 
          :class="{ active: currentWorkspace === 'layout' }"
          @click="currentWorkspace = 'layout'"
        >
          Layout
        </div>
        <div 
          class="workspace-tab" 
          :class="{ active: currentWorkspace === 'modeling' }"
          @click="currentWorkspace = 'modeling'"
        >
          Modeling
        </div>
        <div 
          class="workspace-tab" 
          :class="{ active: currentWorkspace === 'sculpting' }"
          @click="currentWorkspace = 'sculpting'"
        >
          Sculpting
        </div>
        <div 
          class="workspace-tab" 
          :class="{ active: currentWorkspace === 'uv_editing' }"
          @click="currentWorkspace = 'uv_editing'"
        >
          UV Editing
        </div>
        <div 
          class="workspace-tab" 
          :class="{ active: currentWorkspace === 'lighting' }"
          @click="currentWorkspace = 'lighting'"
        >
          Lighting
        </div>
      </div>

      <div class="scene-controls">
        <select v-model="activeScene" class="scene-select">
          <option value="scene1">Main Scene</option>
          <option value="scene2">Scene 2</option>
        </select>
        <div class="view-layer-toggle">
          <span class="iconify" data-icon="solar:eye-bold"></span>
          View Layer
        </div>
        <div class="filter-buttons">
          <button class="filter-btn" :class="{ active: wireframeMode }" @click="toggleWireframe">
            <span class="iconify" data-icon="solar:grid-bold"></span>
          </button>
          <button class="filter-btn" :class="{ active: showLightGizmo }" @click="toggleLightGizmo">
            <span class="iconify" data-icon="solar:bulb-bold"></span>
          </button>
        </div>
      </div>
      
      <div class="window-controls-wrapper">
        <div class="window-control-btn" @click.stop="minimizeWindow" title="Minimize">
          <img :src="'/src/drawable/minimizing.png'" class="window-btn-icon">
        </div>
        <div class="window-control-btn" @click.stop="maximizeRestoreWindow" v-if="!isMaximized" title="Maximize">
          <img :src="'/src/drawable/maximizing.png'" class="window-btn-icon">
        </div>
        <div class="window-control-btn" @click.stop="maximizeRestoreWindow" v-else title="Restore">
          <img :src="'/src/drawable/recover.png'" class="window-btn-icon">
        </div>
        <div class="window-control-btn" @click.stop="closeWindow" title="Close">
          <img :src="'/src/drawable/close.png'" class="window-btn-icon">
        </div>
      </div>
    </div>
    <div class="main-content">
      <div class="toolbar-left">
        <div class="tool-group">
          <button 
            class="tool-button" 
            :class="{ active: transformMode === 'select' }"
            @click="transformMode = 'select'"
            title="Select (Q)"
          >
            <span class="iconify" data-icon="solar:cursor-bold"></span>
          </button>
          <button 
            class="tool-button" 
            :class="{ active: transformMode === 'move' }"
            @click="transformMode = 'move'"
            title="Move (G)"
          >
            <span class="iconify" data-icon="solar:move-bold"></span>
          </button>
          <button 
            class="tool-button" 
            :class="{ active: transformMode === 'rotate' }"
            @click="transformMode = 'rotate'"
            title="Rotate (R)"
          >
            <span class="iconify" data-icon="solar:rotate-bold"></span>
          </button>
          <button 
            class="tool-button" 
            :class="{ active: transformMode === 'scale' }"
            @click="transformMode = 'scale'"
            title="Scale (S)"
          >
            <span class="iconify" data-icon="solar:scale-bold"></span>
          </button>
        </div>
        
        <div class="tool-separator"></div>
        
        <div class="tool-group">
          <button class="tool-button" title="Add Light">
            <span class="iconify" data-icon="solar:bulb-bold"></span>
          </button>
          <button class="tool-button" title="Add Camera">
            <span class="iconify" data-icon="solar:camera-bold"></span>
          </button>
        </div>

        <div class="tool-separator"></div>

        <div class="tool-group">
          <button class="tool-button" title="Material">
            <span class="iconify" data-icon="solar:palette-bold"></span>
          </button>
          <button class="tool-button" title="Measure">
            <span class="iconify" data-icon="solar:ruler-bold"></span>
          </button>
        </div>

        <div class="mode-switcher">
          <select v-model="objectMode" class="mode-select">
            <option value="object">Object Mode</option>
            <option value="edit">Edit Mode</option>
            <option value="sculpt">Sculpt Mode</option>
          </select>
        </div>
      </div>

      <!-- 3. 中央 3D 视图主窗口 (Viewport) -->
      <div class="viewport-container">
        <div class="viewport-header">
          <div class="viewport-info">
            <span class="viewport-label">{{ currentWorkspace }}</span>
            <span class="viewport-stats">Vertices: {{ vertexCount.toLocaleString() }} | Faces: {{ faceCount.toLocaleString() }}</span>
          </div>
          <div class="viewport-controls">
            <button class="control-btn" @click="resetView" title="Reset View">
              <span class="iconify" data-icon="solar:refresh-bold"></span>
            </button>
            <button class="control-btn" @click="toggleFullscreen" title="Fullscreen">
              <span class="iconify" data-icon="solar:maximize-bold"></span>
            </button>
          </div>
        </div>
        
        <div class="viewport" ref="viewportRef">
          <!-- Three.js 渲染画布 -->
          <canvas ref="canvasRef" class="viewport-canvas"></canvas>
          
          <!-- 视图立方体 -->
          <div class="view-cube">
            <div class="cube-face front">Front</div>
            <div class="cube-face right">Right</div>
            <div class="cube-face top">Top</div>
          </div>
          
          <!-- 坐标轴指示器 -->
          <div class="axis-indicator">
            <div class="axis-x">X</div>
            <div class="axis-y">Y</div>
            <div class="axis-z">Z</div>
          </div>
        </div>

        <!-- 底部时间轴/播放控制 -->
        <div class="timeline">
          <div class="timeline-controls">
            <button class="timeline-btn" @click="playAnimation">
              <span class="iconify" data-icon="solar:play-bold"></span>
            </button>
            <button class="timeline-btn" @click="pauseAnimation">
              <span class="iconify" data-icon="solar:pause-bold"></span>
            </button>
            <button class="timeline-btn" @click="stopAnimation">
              <span class="iconify" data-icon="solar:stop-bold"></span>
            </button>
          </div>
          <div class="timeline-slider">
            <input 
              type="range" 
              v-model="currentFrame" 
              min="1" 
              :max="totalFrames" 
              class="timeline-range"
            >
            <div class="frame-display">
              <span>{{ currentFrame }} / {{ totalFrames }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 4. 右侧属性与场景管理区 (Right Panels) -->
      <div class="right-panel">
        <!-- 上方：大纲视图 (Outliner) -->
        <div class="outliner">
          <div class="panel-header">
            <span class="panel-title">Outliner</span>
            <div class="panel-actions">
              <button class="icon-btn" title="Add New">
                <span class="iconify" data-icon="solar:add-bold"></span>
              </button>
            </div>
          </div>
          <div class="outliner-content">
            <div class="outliner-item">
              <span class="iconify item-icon scene-icon" data-icon="solar:folder-bold"></span>
              <span class="item-name">Scene Collection</span>
              <div class="item-actions">
                <span class="iconify action-icon" data-icon="solar:eye-bold"></span>
                <span class="iconify action-icon" data-icon="solar:lock-bold"></span>
              </div>
            </div>
            <div class="outliner-item child-item">
              <span class="iconify item-icon light-icon" data-icon="solar:bulb-bold"></span>
              <span class="item-name">Light</span>
              <div class="item-actions">
                <span class="iconify action-icon" data-icon="solar:eye-bold"></span>
              </div>
            </div>
            <div class="outliner-item child-item">
              <span class="iconify item-icon camera-icon" data-icon="solar:camera-bold"></span>
              <span class="item-name">Camera</span>
              <div class="item-actions">
                <span class="iconify action-icon" data-icon="solar:eye-bold"></span>
              </div>
            </div>
            <div class="outliner-item child-item" :class="{ selected: selectedObject === 'Cube' }" @click="selectedObject = 'Cube'">
              <span class="iconify item-icon mesh-icon" data-icon="solar:cube-bold"></span>
              <span class="item-name">Cube</span>
              <div class="item-actions">
                <span class="iconify action-icon" data-icon="solar:eye-bold"></span>
              </div>
            </div>
          </div>
        </div>

        <!-- 下方：属性编辑器 (Properties) -->
        <div class="properties-editor">
          <div class="properties-tabs">
            <div 
              class="property-tab" 
              :class="{ active: activePropertyTab === 'transform' }"
              @click="activePropertyTab = 'transform'"
            >
              <span class="iconify" data-icon="solar:move-bold"></span>
            </div>
            <div 
              class="property-tab" 
              :class="{ active: activePropertyTab === 'material' }"
              @click="activePropertyTab = 'material'"
            >
              <span class="iconify" data-icon="solar:palette-bold"></span>
            </div>
            <div 
              class="property-tab" 
              :class="{ active: activePropertyTab === 'light' }"
              @click="activePropertyTab = 'light'"
            >
              <span class="iconify" data-icon="solar:bulb-bold"></span>
            </div>
            <div 
              class="property-tab" 
              :class="{ active: activePropertyTab === 'render' }"
              @click="activePropertyTab = 'render'"
            >
              <span class="iconify" data-icon="solar:camera-bold"></span>
            </div>
            <div 
              class="property-tab" 
              :class="{ active: activePropertyTab === 'pbr' }"
              @click="activePropertyTab = 'pbr'"
            >
              <span class="iconify" data-icon="solar:palette-bold"></span>
            </div>
          </div>

          <div class="properties-content">
            <!-- Transform 属性 -->
            <div v-if="activePropertyTab === 'transform'" class="property-section">
              <div class="property-group">
                <div class="group-header">Location</div>
                <div class="property-row">
                  <label class="axis-label axis-x">X</label>
                  <input type="number" v-model.number="transform.location.x" class="number-input">
                </div>
                <div class="property-row">
                  <label class="axis-label axis-y">Y</label>
                  <input type="number" v-model.number="transform.location.y" class="number-input">
                </div>
                <div class="property-row">
                  <label class="axis-label axis-z">Z</label>
                  <input type="number" v-model.number="transform.location.z" class="number-input">
                </div>
              </div>

              <div class="property-group">
                <div class="group-header">Rotation</div>
                <div class="property-row">
                  <label class="axis-label axis-x">X</label>
                  <input type="number" v-model.number="transform.rotation.x" class="number-input">
                </div>
                <div class="property-row">
                  <label class="axis-label axis-y">Y</label>
                  <input type="number" v-model.number="transform.rotation.y" class="number-input">
                </div>
                <div class="property-row">
                  <label class="axis-label axis-z">Z</label>
                  <input type="number" v-model.number="transform.rotation.z" class="number-input">
                </div>
              </div>

              <div class="property-group">
                <div class="group-header">Scale</div>
                <div class="property-row">
                  <label class="axis-label axis-x">X</label>
                  <input type="number" v-model.number="transform.scale.x" class="number-input" step="0.1">
                </div>
                <div class="property-row">
                  <label class="axis-label axis-y">Y</label>
                  <input type="number" v-model.number="transform.scale.y" class="number-input" step="0.1">
                </div>
                <div class="property-row">
                  <label class="axis-label axis-z">Z</label>
                  <input type="number" v-model.number="transform.scale.z" class="number-input" step="0.1">
                </div>
              </div>
            </div>

            <!-- Light 属性 -->
            <div v-if="activePropertyTab === 'light'" class="property-section">
              <div class="property-group">
                <div class="group-header">Light Type</div>
                <select v-model="light.type" class="property-select">
                  <option value="point">Point Light</option>
                  <option value="directional">Directional Light</option>
                  <option value="spot">Spot Light</option>
                </select>
              </div>

              <div class="property-group">
                <div class="group-header">Color & Intensity</div>
                <div class="property-row color-row">
                  <label class="color-label">Color</label>
                  <input type="color" v-model="light.color" class="color-picker">
                </div>
                <div class="property-row">
                  <label class="property-label">Intensity</label>
                  <input type="range" v-model.number="light.intensity" min="0" max="100" class="slider-input">
                  <span class="value-display">{{ light.intensity.toFixed(1) }}</span>
                </div>
              </div>

              <div class="property-group">
                <div class="group-header">Range</div>
                <div class="property-row">
                  <label class="property-label">Radius</label>
                  <input type="range" v-model.number="light.radius" min="0.1" max="50" class="slider-input">
                  <span class="value-display">{{ light.radius.toFixed(2) }} m</span>
                </div>
                <div class="property-row">
                  <label class="property-label">Falloff</label>
                  <input type="range" v-model.number="light.falloff" min="0" max="2" step="0.1" class="slider-input">
                  <span class="value-display">{{ light.falloff.toFixed(1) }}</span>
                </div>
              </div>

              <div class="property-group">
                <div class="group-header">Shadow</div>
                <div class="toggle-row">
                  <label class="toggle-label">Cast Shadow</label>
                  <label class="switch">
                    <input type="checkbox" v-model="light.castShadow">
                    <span class="slider-toggle"></span>
                  </label>
                </div>
                <div class="property-row">
                  <label class="property-label">Shadow Bias</label>
                  <input type="range" v-model.number="light.shadowBias" min="0" max="0.1" step="0.001" class="slider-input">
                  <span class="value-display">{{ light.shadowBias.toFixed(4) }}</span>
                </div>
              </div>
            </div>

            <!-- Material 属性 -->
            <div v-if="activePropertyTab === 'material'" class="property-section">
              <div class="property-group">
                <div class="group-header">Base Color</div>
                <div class="property-row color-row">
                  <input type="color" v-model="material.baseColor" class="color-picker">
                </div>
              </div>

              <div class="property-group">
                <div class="group-header">Metallic</div>
                <div class="property-row">
                  <input type="range" v-model.number="material.metallic" min="0" max="1" step="0.01" class="slider-input">
                  <span class="value-display">{{ material.metallic.toFixed(2) }}</span>
                </div>
              </div>

              <div class="property-group">
                <div class="group-header">Roughness</div>
                <div class="property-row">
                  <input type="range" v-model.number="material.roughness" min="0" max="1" step="0.01" class="slider-input">
                  <span class="value-display">{{ material.roughness.toFixed(2) }}</span>
                </div>
              </div>
            </div>

            <!-- Render 属性 -->
            <div v-if="activePropertyTab === 'render'" class="property-section">
              <div class="property-group">
                <div class="group-header">Resolution</div>
                <div class="property-row">
                  <label class="property-label">Width</label>
                  <input type="number" v-model.number="render.resolution.width" class="number-input">
                </div>
                <div class="property-row">
                  <label class="property-label">Height</label>
                  <input type="number" v-model.number="render.resolution.height" class="number-input">
                </div>
              </div>

              <div class="property-group">
                <div class="group-header">Samples</div>
                <div class="property-row">
                  <input type="range" v-model.number="render.samples" min="1" max="512" class="slider-input">
                  <span class="value-display">{{ render.samples }}</span>
                </div>
              </div>

              <div class="toggle-row">
                <label class="toggle-label">SSGI</label>
                <label class="switch">
                  <input type="checkbox" v-model="render.ssgiEnabled">
                  <span class="slider-toggle"></span>
                </label>
              </div>
              <div class="toggle-row">
                <label class="toggle-label">DoF</label>
                <label class="switch">
                  <input type="checkbox" v-model="render.dofEnabled">
                  <span class="slider-toggle"></span>
                </label>
              </div>
            </div>
            
            <!-- PBR 设置 -->
            <div v-if="activePropertyTab === 'pbr'" class="property-section">
              <div class="property-group">
                <div class="group-header">渲染模式</div>
                <select v-model="renderMode" class="property-select">
                  <option value="frontend">前端预览 (快速)</option>
                  <option value="backend">后端 PBR (高质量)</option>
                  <option value="hybrid">混合模式 (智能)</option>
                </select>
              </div>
              
              <div class="property-group">
                <div class="group-header">PBR 渲染选项</div>
                
                <div class="toggle-row">
                  <label class="toggle-label">Metallic Material</label>
                  <label class="switch">
                    <input type="checkbox" v-model="pbrSettings.metallic">
                    <span class="slider-toggle"></span>
                  </label>
                </div>
                
                <div class="toggle-row">
                  <label class="toggle-label">Indirect Lighting</label>
                  <label class="switch">
                    <input type="checkbox" v-model="pbrSettings.indirect">
                    <span class="slider-toggle"></span>
                  </label>
                </div>
                
                <div class="toggle-row">
                  <label class="toggle-label">Tone Mapping</label>
                  <label class="switch">
                    <input type="checkbox" v-model="pbrSettings.toneMapping">
                    <span class="slider-toggle"></span>
                  </label>
                </div>
                
                <div class="toggle-row">
                  <label class="toggle-label">Gamma Correction</label>
                  <label class="switch">
                    <input type="checkbox" v-model="pbrSettings.gammaCorrection">
                    <span class="slider-toggle"></span>
                  </label>
                </div>
                
                <div class="toggle-row">
                  <label class="toggle-label">Real-time Shadow</label>
                  <label class="switch">
                    <input type="checkbox" v-model="pbrSettings.shadow">
                    <span class="slider-toggle"></span>
                  </label>
                </div>
              </div>
              
              <div class="property-group">
                <div class="group-header">性能监控</div>
                <div class="info-row">
                  <span>FPS:</span>
                  <span>{{ fps.toFixed(1) }}</span>
                </div>
                <div class="info-row">
                  <span>渲染耗时:</span>
                  <span>{{ renderTime.toFixed(2) }}ms</span>
                </div>
                <div class="info-row">
                  <span>高斯数量:</span>
                  <span>{{ vertexCount.toLocaleString() }}</span>
                </div>
              </div>
              
              <div class="toggle-row">
                <label class="toggle-label">LOD 细节层级</label>
                <label class="switch">
                  <input type="checkbox" v-model="lodEnabled">
                  <span class="slider-toggle"></span>
                </label>
              </div>
              
              <div class="property-group">
                <div class="group-header">光源控制</div>
                <div class="property-row">
                  <label class="property-label">Position X</label>
                  <input type="number" v-model.number="lightPosition.x" class="number-input" step="0.1">
                </div>
                <div class="property-row">
                  <label class="property-label">Position Y</label>
                  <input type="number" v-model.number="lightPosition.y" class="number-input" step="0.1">
                </div>
                <div class="property-row">
                  <label class="property-label">Position Z</label>
                  <input type="number" v-model.number="lightPosition.z" class="number-input" step="0.1">
                </div>
              </div>
              
              <div class="property-group">
                <div class="group-header">光源强度 (RGB)</div>
                <div class="property-row">
                  <label class="property-label">R</label>
                  <input type="range" v-model.number="lightIntensity.r" min="0" max="200" class="slider-input">
                  <span class="value-display">{{ lightIntensity.r.toFixed(1) }}</span>
                </div>
                <div class="property-row">
                  <label class="property-label">G</label>
                  <input type="range" v-model.number="lightIntensity.g" min="0" max="200" class="slider-input">
                  <span class="value-display">{{ lightIntensity.g.toFixed(1) }}</span>
                </div>
                <div class="property-row">
                  <label class="property-label">B</label>
                  <input type="range" v-model.number="lightIntensity.b" min="0" max="200" class="slider-input">
                  <span class="value-display">{{ lightIntensity.b.toFixed(1) }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>

<script>
import { RouterLink } from 'vue-router'
import { markRaw } from 'vue'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { GaussianRenderer } from '@/utils/GaussianRenderer.js'

export default {
  name: 'EditorPage',
  components: {
    RouterLink
  },
  data() {
    return {
      // 顶部栏状态
      showDropdown: null,
      currentWorkspace: 'layout',
      activeScene: 'scene1',
      wireframeMode: false,
      showLightGizmo: true,
      realtimeEnabled: true,
      
      // 左侧工具栏
      transformMode: 'select',
      objectMode: 'object',
      
      // 场景统计
      vertexCount: 0,
      faceCount: 0,
      
      // 时间轴
      currentFrame: 1,
      totalFrames: 250,
      isPlaying: false,
      
      // 右侧面板
      selectedObject: 'GaussianModel',
      activePropertyTab: 'transform',
      
      // Transform 属性
      transform: {
        location: { x: 0, y: 0, z: 0 },
        rotation: { x: 0, y: 0, z: 0 },
        scale: { x: 1, y: 1, z: 1 }
      },
      
      // Light 属性
      light: {
        type: 'point',
        color: '#ffffff',
        intensity: 80,
        radius: 5.0,
        falloff: 1.0,
        castShadow: true,
        shadowBias: 0.0001,
        position: { x: 5, y: 5, z: 5 }
      },
      
      // Material 属性
      material: {
        baseColor: '#808080',
        metallic: 0.0,
        roughness: 0.5
      },
      
      // Render 属性
      render: {
        resolution: { width: 1920, height: 1080 },
        samples: 64,
        ssgiEnabled: true,
        dofEnabled: false
      },
      
      // PBR 设置对象
      pbrSettings: {
        metallic: false,
        indirect: false,
        toneMapping: false,
        gammaCorrection: false,
        roughnessOffset: 0.0,
        shadow: true  // 默认启用阴影
      },
      
      // Three.js 相关
      scene: null,
      camera: null,
      renderer: null,
      controls: null,  // 添加轨道控制器
      lightObject: null,
      cubeMesh: null,  // 保留用于兼容，但不再使用
      gaussianRenderer: null,  // 新增：高斯渲染器
      animationId: null,
      
      // 渲染模式
      renderMode: 'frontend', // 'frontend' | 'backend' | 'hybrid'
      lastRenderTime: 0,
      screenQuad: null,
      
      // 性能监控
      fps: 0,
      renderTime: 0,
      lodEnabled: false,
      
      // 项目数据
      projectId: null,
      outputPath: null,
      checkpointFile: null,
      projectData: null,
      loadingCheckpoint: false,
      
      // PBR 服务相关
      pbrServiceProcess: null,
      renderLoopActive: false,
      
      // PBR 参数
      metallic: false,
      indirect: false,
      toneMapping: false,
      gammaCorrection: false,
      shadow: true,  // 阴影开关
      
      // 光源控制
      lightPosition: { x: 5, y: 5, z: 5 },
      lightIntensity: { r: 100, g: 100, b: 100 },
      lightColor: '#ffffff',
      autoRotateLight: false,
      showLightControl: true,
      showPBRSettings: true,
      
      // 渲染模式
      renderMode: 'pbr', // 'pbr', 'albedo', 'normal', 'depth'
      
      // 相机状态
      cameraPosition: { x: 0, y: 0, z: 0 },
      cameraRotation: { x: 0, y: 0 },
      
      // 加载状态
      loading: false,
      loadingText: '',
      checkpointLoaded: false,
      checkpointPath: '',
      
      // 窗口状态
      isMaximized: true
    }
  },
  computed: {
    selectedModel() {
      return this.models.find(model => model.id === this.activeModel)
    },
    currentProject() {
      const projectId = this.$route.params.projectId
      return this.projectData[projectId]
    }
  },
  methods: {
    // 窗口控制方法
    minimizeWindow() {
      console.log('[EditorPage] 点击最小化按钮');
      if (window.electronAPI?.minimizeWindow) {
        window.electronAPI.minimizeWindow();
        console.log('[EditorPage] ✓ 已调用最小化 API');
      } else {
        console.error('[EditorPage] ❌ electronAPI.minimizeWindow 不存在');
      }
    },
    
    maximizeRestoreWindow() {
      console.log('[EditorPage] 点击最大化/恢复按钮，当前状态:', this.isMaximized);
      if (!window.electronAPI) {
        console.error('[EditorPage] ❌ window.electronAPI 不存在');
        return;
      }
      
      if (this.isMaximized) {
        window.electronAPI.restoreWindow();
        this.isMaximized = false;
        console.log('[EditorPage] ✓ 已调用恢复窗口 API');
      } else {
        window.electronAPI.maximizeWindow();
        this.isMaximized = true;
        console.log('[EditorPage] ✓ 已调用最大化窗口 API');
      }
    },
    
    closeWindow() {
      console.log('[EditorPage] 点击关闭按钮');
      if (window.electronAPI?.closeWindow) {
        window.electronAPI.closeWindow();
        console.log('[EditorPage] ✓ 已调用关闭窗口 API');
      } else {
        console.error('[EditorPage] ❌ electronAPI.closeWindow 不存在');
      }
    },
    
    // 监听窗口状态变化
    setupWindowListeners() {
      // 监听来自 Electron 主进程的消息
      window.electronAPI?.onWindowMaximized?.(() => {
        this.isMaximized = true;
        console.log('[EditorPage] ✓ 窗口已最大化');
      });
      
      window.electronAPI?.onWindowRestored?.(() => {
        this.isMaximized = false;
        console.log('[EditorPage] ✓ 窗口已恢复');
      });
    },
    
    // 加载项目数据和 checkpoint
    async loadProjectData() {
      this.projectId = this.$route.params.projectId;
      this.outputPath = this.$route.query.outputPath;
      this.checkpointFile = this.$route.query.checkpoint || 'chkpnt40000.pth';
      
      console.log('[EditorPage] 加载项目数据:', {
        projectId: this.projectId,
        outputPath: this.outputPath,
        checkpointFile: this.checkpointFile
      });
      
      if (!this.projectId) {
        console.warn('[EditorPage] 缺少项目 ID');
        return;
      }
      
      try {
        // 获取项目信息
        const projectResult = await window.electronAPI?.getProjectConfig(this.projectId);
        if (projectResult?.success) {
          this.projectData = projectResult.data;
          console.log('[EditorPage] ✓ 项目数据加载成功:', this.projectData);
        } else {
          console.warn('[EditorPage] ⚠️ 项目数据加载失败:', projectResult?.error);
        }
        
        // 启动 PBR 渲染服务并加载 checkpoint
        await this.startPBRService();
        await this.loadCheckpoint();
      } catch (error) {
        console.error('[EditorPage] ❌ 加载项目数据失败:', error);
      }
    },
    
    // 启动 PBR 渲染服务
    async startPBRService() {
      console.log('[EditorPage] 🚀 启动 PBR 渲染服务...');
      
      try {
        // 检查服务是否已在运行
        try {
          const healthResponse = await fetch('http://localhost:5000/api/health');
          if (healthResponse.ok) {
            console.log('[EditorPage] ✓ PBR 服务已在运行');
            return;
          }
        } catch (err) {
          // 服务未运行，继续启动
        }
        
        // 通过 Electron API 启动 Python 服务（带 conda 环境）
        // 使用绝对路径指向 GS-IR/pbr_render_service.py
        const workspacePath = localStorage.getItem('workspacePath') || '';
        const servicePath = workspacePath ? 
          `${workspacePath}/../GS-IR/pbr_render_service.py`.replace(/\\/g, '/') : 
          'E:/GraduationProject/LuminaGS/GS-IR/pbr_render_service.py';
        const serviceCwd = workspacePath ? 
          `${workspacePath}/../GS-IR`.replace(/\\/g, '/') : 
          'E:/GraduationProject/LuminaGS/GS-IR';
        
        console.log('[EditorPage] 启动服务脚本:', servicePath);
        console.log('[EditorPage] 工作目录:', serviceCwd);
        console.log('[EditorPage] 使用 conda 环境：gsir');
        
        // 使用 Electron API 启动带 conda 环境的 Python 服务
        const result = await window.electronAPI?.startPythonService({
          script: servicePath,
          envName: 'gsir',
          cwd: serviceCwd
        });
        
        if (result?.success) {
          console.log('[EditorPage] ✓ PBR 服务启动成功，PID:', result.pid);
          
          // 等待服务启动
          await new Promise(resolve => setTimeout(resolve, 3000));
          console.log('[EditorPage] ✓ PBR 服务已就绪');
        } else {
          throw new Error(result?.error || 'Failed to start PBR service');
        }
        
      } catch (error) {
        console.error('[EditorPage] ❌ 启动 PBR 服务失败:', error);
        throw error;
      }
    },
    
    // 加载 checkpoint 文件（统一版本）
    async loadCheckpoint() {
      if (!this.outputPath || !this.checkpointFile) {
        console.warn('[EditorPage] 缺少输出路径或 checkpoint 文件名')
        return
      }
              
      this.loading = true
      this.loadingText = '正在加载 Checkpoint...'
      const checkpointPath = `${this.outputPath}/${this.checkpointFile}`
              
      console.log('[EditorPage] 🔄 开始加载 checkpoint:', checkpointPath)
              
      try {
        // 1. 检查 checkpoint 文件是否存在
        const checkResult = await window.electronAPI?.checkFileExists(checkpointPath)
        if (!checkResult?.exists) {
          throw new Error('Checkpoint 文件不存在')
        }
                  
        // 2. 调用 PBR 服务加载 checkpoint
        console.log('[EditorPage] 🔄 调用 PBR 服务加载 checkpoint...')
        const loadResponse = await fetch('http://localhost:5000/api/load_checkpoint', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            checkpoint_path: checkpointPath
          })
        })
                  
        if (!loadResponse.ok) {
          throw new Error(`HTTP ${loadResponse.status}: ${await loadResponse.text()}`)
        }
                  
        const loadResult = await loadResponse.json()
        console.log('[EditorPage] ✓ Checkpoint 加载成功:', loadResult)
                  
        // 更新场景统计
        this.vertexCount = loadResult.num_gaussians || 0
        this.faceCount = Math.floor(this.vertexCount * 0.6)
                  
        // 标记为已加载
        this.checkpointLoaded = true
        this.checkpointPath = checkpointPath
                  
        // 3. 初始化 Three.js 场景并加载高斯模型
        console.log('[EditorPage] 🎨 初始化 Three.js 场景和高斯渲染器...')
        await this.initThreeJS()
                  
        // 4. 开始实时渲染循环（保留用于后续 PBR 功能）
        this.startRealtimeRender()
                  
        this.loadingText = 'Checkpoint 加载完成'
        setTimeout(() => {
          this.loading = false
        }, 1000)
                  
      } catch (error) {
        console.error('[EditorPage] ❌ 加载 checkpoint 失败:', error)
        this.loadingText = `加载失败：${error.message}`
        setTimeout(() => {
          this.loading = false
        }, 2000)
      }
    },
    
    // 启动实时 PBR 渲染循环
    startRealtimeRender() {
      if (this.renderLoopActive) return
      
      // 检查 Three.js 对象是否已初始化
      if (!this.camera || !this.scene || !this.renderer) {
        console.warn('[EditorPage] Three.js 对象未初始化，无法启动实时渲染');
        return;
      }
      
      this.renderLoopActive = true
      console.log('[EditorPage] 🎬 启动实时 PBR 渲染循环（带阴影）')
      
      // 节流控制（避免过于频繁的请求）
      let lastRenderTime = 0
      const RENDER_INTERVAL = 100  // 最小渲染间隔（毫秒）
      
      const renderLoop = async () => {
        if (!this.renderLoopActive) return
        
        try {
          const currentTime = Date.now()
          
          // 节流检查：如果距离上次渲染时间太短，跳过本次渲染
          if (currentTime - lastRenderTime < RENDER_INTERVAL) {
            requestAnimationFrame(renderLoop)
            return
          }
          
          // 从当前相机位姿渲染 - 使用 clone() 避免代理问题
          const viewpoint = this.camera.matrixWorld.clone().toArray()
          
          // 更新相机状态
          this.updateCameraState()
          
          // 调用后端 PBR 渲染服务（带阴影参数）
          const renderResponse = await fetch('http://localhost:5000/api/render_pbr', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              viewpoint: viewpoint,
              light_position: [this.lightPosition.x, this.lightPosition.y, this.lightPosition.z],
              light_intensity: [this.lightIntensity.r, this.lightIntensity.g, this.lightIntensity.b],
              metallic: this.pbrSettings.metallic,
              indirect: this.pbrSettings.indirect,
              tone: this.pbrSettings.toneMapping,
              gamma: this.pbrSettings.gammaCorrection,
              shadow: this.pbrSettings.shadow  // 传递阴影开关参数
            })
          })
          
          if (renderResponse.ok) {
            const result = await renderResponse.json()
            
            // 将渲染结果作为纹理应用到 Three.js 场景中的平面
            if (result.image_base64 && this.cubeMesh) {
              const texture = new THREE.TextureLoader().load(
                `data:image/png;base64,${result.image_base64}`
              )
              texture.colorSpace = THREE.SRGBColorSpace
              texture.minFilter = THREE.LinearFilter
              texture.magFilter = THREE.LinearFilter
              
              // 更新材质
              this.cubeMesh.material.map = texture
              this.cubeMesh.material.needsUpdate = true
              
              // 记录渲染信息
              if (result.shadow_generated !== undefined) {
                console.log(`[EditorPage] ✓ PBR 渲染完成 | 分辨率：${result.width}x${result.height} | 阴影：${result.shadow_generated ? '✓' : '✗'}`)
              } else {
                console.log(`[EditorPage] ✓ PBR 渲染完成 | 分辨率：${result.width}x${result.height}`)
              }
              
              lastRenderTime = currentTime
            }
          } else {
            console.error('[EditorPage] ❌ 渲染响应失败:', renderResponse.status)
          }
        } catch (error) {
          console.error('[EditorPage] ❌ 实时渲染失败:', error)
        }
        
        // 继续下一帧渲染
        requestAnimationFrame(renderLoop)
      }
      
      renderLoop()
    },
    
    // 停止实时渲染
    stopRealtimeRender() {
      this.renderLoopActive = false;
      console.log('[EditorPage] ⏹️ 停止实时 PBR 渲染循环');
    },
    
    // 菜单操作
    importModel() {
      console.log('导入模型')
      this.showDropdown = null
    },
    exportModel() {
      console.log('导出模型')
      this.showDropdown = null
    },
    saveProject() {
      console.log('保存项目')
      this.showDropdown = null
    },
    undo() {
      console.log('撤销')
      this.showDropdown = null
    },
    redo() {
      console.log('重做')
      this.showDropdown = null
    },
    startRender() {
      console.log('开始渲染')
      this.showDropdown = null
    },
    toggleRealtime() {
      this.realtimeEnabled = !this.realtimeEnabled
      this.showDropdown = null
    },
    
    // 视图控制
    toggleWireframe() {
      this.wireframeMode = !this.wireframeMode
      if (this.cubeMesh) {
        this.cubeMesh.material.wireframe = this.wireframeMode
      }
    },
    toggleLightGizmo() {
      this.showLightGizmo = !this.showLightGizmo
      if (this.lightObject) {
        this.lightObject.visible = this.showLightGizmo
      }
    },
    resetView() {
      if (this.camera && this.controls) {
        // 重置相机位置
        this.camera.position.set(5, 5, 5)
        this.camera.lookAt(0, 0, 0)
        
        // 重置控制器
        this.controls.target.set(0, 0, 0)
        this.controls.update()
        
        console.log('[EditorPage] ✓ 视角已重置')
      }
    },
    toggleFullscreen() {
      const viewport = this.$refs.viewportRef
      if (!document.fullscreenElement) {
        viewport.requestFullscreen().catch(err => {
          console.error(`无法进入全屏模式：${err}`)
        })
      } else {
        document.exitFullscreen()
      }
    },
    
    // 动画控制
    playAnimation() {
      this.isPlaying = true
      this.animate()
    },
    pauseAnimation() {
      this.isPlaying = false
    },
    stopAnimation() {
      this.isPlaying = false
      this.currentFrame = 1
    },
    animate() {
      this.animationId = requestAnimationFrame(() => this.animate())
      
      // 更新轨道控制器（必须在 render 之前调用）
      if (this.controls) {
        this.controls.update()
      }
      
      // 更新性能监控
      this.updatePerformanceMetrics()
      
      // 根据渲染模式选择渲染方式
      if (this.renderMode === 'backend' && this.realtimeEnabled) {
        this.renderPBRBackend()
      } else {
        this.renderScene()
      }
    },
    
    // 启动渲染循环
    startRenderLoop() {
      this.isPlaying = true;
      console.log('[EditorPage] ▶️ 渲染循环已启动');
      this.animate();
    },
    renderScene() {
      if (this.renderer && this.scene && this.camera) {
        // 前端模式下隐藏屏幕四边形
        if (this.screenQuad) {
          this.screenQuad.visible = false;
        }
        
        // 更新高斯实例矩阵
        if (this.gaussianRenderer && this.gaussianRenderer.gaussianMesh) {
          const mesh = this.gaussianRenderer.gaussianMesh;
          mesh.instanceMatrix.needsUpdate = true;
          
          // 更新 PBR shader uniforms
          const material = mesh.material;
          if (material.uniforms) {
            // 更新自定义 uniforms
            material.uniforms.lightPosition.value.set(
              this.lightPosition.x,
              this.lightPosition.y,
              this.lightPosition.z
            );
            material.uniforms.lightIntensity.value.set(
              this.lightIntensity.r / 100,
              this.lightIntensity.g / 100,
              this.lightIntensity.b / 100
            );
            material.uniforms.metallic.value = this.pbrSettings.metallic ? 1.0 : 0.0;
            material.uniforms.roughness.value = 0.5;
          }
        }
        
        this.renderer.render(this.scene, this.camera)
      } else {
        console.warn('[EditorPage] ⚠️ 渲染器、场景或相机未初始化');
      }
    },
    
    /**
     * 创建屏幕四边形（用于后端渲染模式）
     */
    createScreenQuad() {
      const geometry = new THREE.PlaneGeometry(2, 2);
      const material = new THREE.MeshBasicMaterial({
        map: null,
        depthWrite: false,
        depthTest: false,
        visible: false // 默认隐藏，仅在后端模式显示
      });
      
      this.screenQuad = new THREE.Mesh(geometry, material);
      this.screenQuad.frustumCulled = false; // 避免被裁剪
      this.screenQuad.renderOrder = 999; // 最后渲染
      this.scene.add(this.screenQuad);
      console.log('[EditorPage] ✓ 屏幕四边形已创建');
    },
    
    /**
     * 后端 PBR 渲染
     */
    async renderPBRBackend() {
      // 节流控制
      const now = Date.now();
      if (now - this.lastRenderTime < 100) return;
      
      try {
        // 获取当前相机位姿
        const viewpoint = this.camera.matrixWorld.clone().toArray();
        
        // 调用后端 PBR 渲染
        const response = await fetch('http://localhost:5000/api/render_pbr', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            viewpoint: viewpoint,
            light_position: [this.lightPosition.x, this.lightPosition.y, this.lightPosition.z],
            light_intensity: [this.lightIntensity.r, this.lightIntensity.g, this.lightIntensity.b],
            metallic: this.pbrSettings.metallic,
            indirect: this.pbrSettings.indirect,
            tone: this.pbrSettings.toneMapping,
            gamma: this.pbrSettings.gammaCorrection,
            shadow: this.pbrSettings.shadow
          })
        });
        
        if (response.ok) {
          const result = await response.json();
          
          // 将渲染结果作为纹理更新
          if (result.image_base64 && this.screenQuad) {
            const texture = new THREE.TextureLoader().load(
              `data:image/png;base64,${result.image_base64}`
            );
            texture.colorSpace = THREE.SRGBColorSpace;
            texture.minFilter = THREE.LinearFilter;
            texture.magFilter = THREE.LinearFilter;
            texture.needsUpdate = true;
            
            this.screenQuad.material.map = texture;
            this.screenQuad.material.visible = true;
            this.screenQuad.material.needsUpdate = true;
            
            // 记录渲染信息
            console.log(`[EditorPage] ✓ PBR 渲染完成 | ${result.width}x${result.height}`);
            
            this.lastRenderTime = now;
          }
        } else {
          console.error('[EditorPage] ❌ 渲染响应失败:', response.status);
        }
      } catch (error) {
        console.error('[EditorPage] ❌ PBR 后端渲染失败:', error);
      }
    },
    async initThreeJS() {
      console.log('[EditorPage] 开始初始化 Three.js 场景...');
      
      // 检查 DOM 元素是否存在
      if (!this.$refs.viewportRef || !this.$refs.canvasRef) {
        console.error('[EditorPage] ❌ DOM 元素未准备好:');
        console.log('  - viewportRef:', this.$refs.viewportRef);
        console.log('  - canvasRef:', this.$refs.canvasRef);
        return;
      }
      
      console.log('[EditorPage] ✓ DOM 元素已准备好');
      console.log('[EditorPage]   viewportRef 尺寸:', 
        this.$refs.viewportRef.clientWidth, 'x', this.$refs.viewportRef.clientHeight);
      
      try {
        // 1. 创建 Three.js 基础场景
        this.scene = new THREE.Scene();
        this.scene.background = new THREE.Color(0x1a1a1a);
        
        // 2. 创建相机
        const width = this.$refs.viewportRef.clientWidth;
        const height = this.$refs.viewportRef.clientHeight;
        this.camera = new THREE.PerspectiveCamera(
          75,
          width / height,
          0.1,
          1000
        );
        this.camera.position.set(5, 5, 5);
        
        // 3. 创建渲染器
        this.renderer = new THREE.WebGLRenderer({
          canvas: this.$refs.canvasRef,
          antialias: true,
          powerPreference: 'high-performance'
        });
        this.renderer.setSize(width, height);
        this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
        
        // 4. 初始化轨道控制器
        this.controls = new OrbitControls(this.camera, this.$refs.canvasRef);
        this.controls.enableDamping = true;
        this.controls.dampingFactor = 0.05;
        this.controls.target.set(0, 0, 0);
        
        // 5. 创建高斯渲染器
        this.gaussianRenderer = new GaussianRenderer(this.scene, this.camera);
        
        // 6. 创建屏幕四边形（用于后端渲染模式）
        this.createScreenQuad();
        
        // 7. 如果有 checkpoint，加载高斯模型
        if (this.checkpointPath) {
          console.log('[EditorPage] 📥 开始加载高斯模型:', this.checkpointPath);
          const loadResult = await this.gaussianRenderer.loadModel(this.checkpointPath);
          
          if (loadResult.success) {
            console.log('[EditorPage] ✓ 高斯模型加载成功:', loadResult.numGaussians);
            
            // 8. 自动调整相机视角
            this.gaussianRenderer.fitCameraToBounds();
            
            // 更新 UI 统计
            this.vertexCount = loadResult.numGaussians;
            this.faceCount = Math.floor(loadResult.numGaussians * 0.6);
          } else {
            console.error('[EditorPage] ❌ 高斯模型加载失败:', loadResult.error);
          }
        } else {
          console.warn('[EditorPage] ⚠️ 没有 checkpointPath，跳过模型加载');
        }
        
        // 9. 启动渲染循环
        this.startRenderLoop();
        
      } catch (error) {
        console.error('[EditorPage] ❌ 初始化 Three.js 失败:', error);
      }
    },
    
    // 更新光照属性（同步到 PBR 服务）
    async updateLightProperties() {
      if (!this.lightObject) return;
          
      // 更新 Three.js 光源
      this.lightObject.color = new THREE.Color(this.light.color);
      this.lightObject.intensity = this.light.intensity;
      this.lightObject.distance = this.light.radius;
      this.lightObject.castShadow = this.light.castShadow;
          
      // 同步位置
      this.lightObject.position.set(
        this.light.position.x,
        this.light.position.y,
        this.light.position.z
      );
          
      // 同步全局光照参数
      this.lightPosition = { ...this.light.position };
      this.lightIntensity = {
        r: this.light.intensity,
        g: this.light.intensity,
        b: this.light.intensity
      };
          
      // 通知 PBR 服务更新光照参数
      try {
        await fetch('http://localhost:5000/api/update_light', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            position: [this.light.position.x, this.light.position.y, this.light.position.z],
            intensity: [this.light.intensity, this.light.intensity, this.light.intensity],
            color: [1, 1, 1] // 颜色已通过 color 属性设置
          })
        });
        console.log('[EditorPage] ✓ 光照参数已同步到 PBR 服务');
      } catch (error) {
        console.error('[EditorPage] ❌ 更新光照失败:', error);
      }
    },
    updateMaterialProperties() {
      if (!this.cubeMesh) return
      
      this.cubeMesh.material.color = new THREE.Color(this.material.baseColor)
      this.cubeMesh.material.metalness = this.material.metallic
      this.cubeMesh.material.roughness = this.material.roughness
    },
    handleResize() {
      if (this.camera && this.renderer && this.$refs.viewportRef) {
        const width = this.$refs.viewportRef.clientWidth;
        const height = this.$refs.viewportRef.clientHeight;
        
        // 避免除以 0
        if (width === 0 || height === 0) {
          console.warn('[EditorPage] ⚠️ 视口尺寸为 0，跳过 resize');
          return;
        }
        
        this.camera.aspect = width / height;
        this.camera.updateProjectionMatrix();
        
        this.renderer.setSize(width, height);
        console.log('[EditorPage] 📐 窗口大小已调整:', width, 'x', height);
      }
    },
        
    // ========== 新增 PBR 功能方法 ==========
        
    // 切换光源控制面板
    toggleLightControl() {
      this.showLightControl = !this.showLightControl
    },
        
    // 切换 PBR 设置面板
    togglePBRSettings() {
      this.showPBRSettings = !this.showPBRSettings
    },
        
    // 设置渲染模式
    setRenderMode(mode) {
      this.renderMode = mode
      console.log('[EditorPage] 切换渲染模式:', mode)
    },
        
    // 更新光源（从 UI 控件调用）
    async updateLight() {
      if (!this.checkpointLoaded) {
        console.warn('[EditorPage] ⚠️ Checkpoint 未加载，无法更新光源');
        return;
      }
          
      try {
        await fetch('http://localhost:5000/api/update_light', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            position: [this.lightPosition.x, this.lightPosition.y, this.lightPosition.z],
            intensity: [this.lightIntensity.r, this.lightIntensity.g, this.lightIntensity.b],
            color: [1, 1, 1]
          })
        })
            
        // 同步更新 Three.js 光源
        if (this.lightObject) {
          this.lightObject.position.copy(new THREE.Vector3(
            this.lightPosition.x,
            this.lightPosition.y,
            this.lightPosition.z
          ))
          this.lightObject.intensity = (this.lightIntensity.r + this.lightIntensity.g + this.lightIntensity.b) / 3
        }
        console.log('[EditorPage] ✓ 光源已更新');
      } catch (error) {
        console.error('[EditorPage] ❌ 更新光源失败:', error)
      }
    },
        
    // 更新 PBR 设置
    async updatePBRSettings() {
      if (!this.checkpointLoaded) {
        console.warn('[EditorPage] ⚠️ Checkpoint 未加载，无法更新 PBR 设置');
        return;
      }
          
      console.log('[EditorPage] 更新 PBR 设置:', {
        metallic: this.pbrSettings.metallic,
        indirect: this.pbrSettings.indirect,
        toneMapping: this.pbrSettings.toneMapping,
        gammaCorrection: this.pbrSettings.gammaCorrection,
        shadow: this.pbrSettings.shadow
      })
          
      // 同步到本地参数
      this.metallic = this.pbrSettings.metallic;
      this.indirect = this.pbrSettings.indirect;
      this.toneMapping = this.pbrSettings.toneMapping;
      this.gammaCorrection = this.pbrSettings.gammaCorrection;
      this.shadow = this.pbrSettings.shadow;
          
      // PBR 服务会在下次渲染循环中自动应用这些参数
      console.log('[EditorPage] ✓ PBR 设置已更新，将在下次渲染中应用');
    },
    
    // 更新性能监控
    updatePerformanceMetrics() {
      if (this.gaussianRenderer) {
        const metrics = this.gaussianRenderer.getPerformanceMetrics();
        this.fps = parseFloat(metrics.fps);
        this.renderTime = parseFloat(metrics.renderTime);
      }
    },
    
    // 更新 LOD
    updateLOD() {
      if (this.gaussianRenderer && this.camera) {
        this.gaussianRenderer.enableLOD(this.lodEnabled);
      }
    },
        
    // 切换自动旋转光源
    toggleAutoRotate() {
      if (this.autoRotateLight) {
        this.startAutoRotate()
      } else {
        this.stopAutoRotate()
      }
    },
        
    // 开始自动旋转光源
    startAutoRotate() {
      const rotateInterval = () => {
        if (!this.autoRotateLight) return
            
        const time = Date.now() * 0.001
        this.lightPosition.x = Math.sin(time) * 5
        this.lightPosition.y = Math.cos(time * 0.7) * 5
        this.lightPosition.z = Math.sin(time * 0.5) * 5
            
        this.updateLight()
        requestAnimationFrame(rotateInterval)
      }
          
      rotateInterval()
    },
        
    // 停止自动旋转光源
    stopAutoRotate() {
      // 只需将 autoRotateLight 设为 false，requestAnimationFrame 会自动停止
    },
        
    // 更新相机状态
    updateCameraState() {
      if (this.camera) {
        this.cameraPosition = {
          x: this.camera.position.x,
          y: this.camera.position.y,
          z: this.camera.position.z
        }
            
        // 计算欧拉角
        const euler = new THREE.Euler(
          this.camera.rotation.x,
          this.camera.rotation.y,
          this.camera.rotation.z,
          'YXZ'
        )
        this.cameraRotation = {
          x: THREE.MathUtils.radToDeg(euler.x),
          y: THREE.MathUtils.radToDeg(euler.y)
        }
      }
    },
        
    // 加载 Checkpoint 的增强版本
    async loadCheckpoint() {
      if (!this.outputPath || !this.checkpointFile) {
        console.warn('[EditorPage] 缺少输出路径或 checkpoint 文件名')
        return
      }
          
      this.loading = true
      this.loadingText = '正在加载 Checkpoint...'
      const checkpointPath = `${this.outputPath}/${this.checkpointFile}`
          
      console.log('[EditorPage] 🔄 开始加载 checkpoint:', checkpointPath)
          
      try {
        // 1. 检查 checkpoint 文件是否存在
        const checkResult = await window.electronAPI?.checkFileExists(checkpointPath)
        if (!checkResult?.exists) {
          throw new Error('Checkpoint 文件不存在')
        }
            
        // 2. 调用 PBR 服务加载 checkpoint
        console.log('[EditorPage] 🔄 调用 PBR 服务加载 checkpoint...')
        const loadResponse = await fetch('http://localhost:5000/api/load_checkpoint', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            checkpoint_path: checkpointPath
          })
        })
            
        if (!loadResponse.ok) {
          throw new Error(`HTTP ${loadResponse.status}: ${await loadResponse.text()}`)
        }
            
        const loadResult = await loadResponse.json()
        console.log('[EditorPage] ✓ Checkpoint 加载成功:', loadResult)
            
        // 更新场景统计
        this.vertexCount = loadResult.num_gaussians || 0
        this.faceCount = Math.floor(this.vertexCount * 0.6)
            
        // 标记为已加载
        this.checkpointLoaded = true
        this.checkpointPath = checkpointPath
            
        // 初始化 Three.js 场景（如果有 checkpoint）
        this.initThreeJS()
            
        // 开始实时渲染循环
        this.startRealtimeRender()
            
        this.loadingText = 'Checkpoint 加载完成'
        setTimeout(() => {
          this.loading = false
        }, 1000)
            
      } catch (error) {
        console.error('[EditorPage] ❌ 加载 checkpoint 失败:', error)
        this.loadingText = `加载失败：${error.message}`
        setTimeout(() => {
          this.loading = false
        }, 2000)
      }
    },
  },
  mounted() {
    const projectId = this.$route.params.projectId
    if (projectId) {
      console.log('加载项目:', projectId)
    }
    
    // 设置窗口状态监听器
    this.setupWindowListeners();
    
    // 加载项目数据和 checkpoint
    this.loadProjectData();
    
    // 注意：initThreeJS 会在 loadCheckpoint 成功后调用
    // 这里不需要重复调用
    
    // 监听窗口大小变化
    window.addEventListener('resize', this.handleResize)
  },
  beforeUnmount() {
    // 停止实时渲染
    this.stopRealtimeRender();
    
    // 停止动画循环
    if (this.animationId) {
      cancelAnimationFrame(this.animationId);
      this.animationId = null;
    }
    
    // 通过 Electron API 停止 Python 服务
    window.electronAPI?.stopPythonService().then(() => {
      console.log('[EditorPage] ✓ Python 服务已通过 API 停止');
    }).catch(err => {
      console.warn('[EditorPage] ⚠️ 停止 Python 服务失败:', err);
    });
    
    // 清理轨道控制器
    if (this.controls) {
      this.controls.dispose();
      this.controls = null;
      console.log('[EditorPage] ✓ 轨道控制器已清理');
    }
    
    // 清理渲染器
    if (this.renderer) {
      this.renderer.dispose();
      this.renderer = null;
      console.log('[EditorPage] ✓ 渲染器已清理');
    }
    
    // 清理场景中的物体
    if (this.scene) {
      this.scene.traverse((object) => {
        if (object.geometry) {
          object.geometry.dispose();
        }
        if (object.material) {
          if (Array.isArray(object.material)) {
            object.material.forEach(material => material.dispose());
          } else {
            object.material.dispose();
          }
        }
        if (object.texture) {
          object.texture.dispose();
        }
      });
      this.scene = null;
      console.log('[EditorPage] ✓ 场景已清理');
    }
    
    // 清理高斯渲染器
    if (this.gaussianRenderer) {
      this.gaussianRenderer.dispose();
      this.gaussianRenderer = null;
      console.log('[EditorPage] ✓ 高斯渲染器已清理');
    }
    
    // 清理相机
    if (this.camera) {
      this.camera = null;
    }
    
    // 清理网格引用
    if (this.cubeMesh) {
      this.cubeMesh = null;
    }
    
    // 清理光源
    if (this.lightObject) {
      this.lightObject = null;
    }
    
    // 移除窗口大小监听
    window.removeEventListener('resize', this.handleResize);
    
    console.log('[EditorPage] ✓ 所有资源已清理完成');
  },
  watch: {
    '$route'(to) {
      const projectId = to.params.projectId
      if (projectId) {
        console.log('切换到项目:', projectId)
      }
    },
    light: {
      handler() {
        this.updateLightProperties()
      },
      deep: true
    },
    material: {
      handler() {
        this.updateMaterialProperties()
      },
      deep: true
    },
    // 监听 PBR 设置变化
    'pbrSettings.metallic': function(newVal) {
      if (this.checkpointLoaded) {
        console.log('[EditorPage] Metallic 设置为:', newVal);
        this.updatePBRSettings();
      }
    },
    'pbrSettings.indirect': function(newVal) {
      if (this.checkpointLoaded) {
        console.log('[EditorPage] Indirect 设置为:', newVal);
        this.updatePBRSettings();
      }
    },
    'pbrSettings.toneMapping': function(newVal) {
      if (this.checkpointLoaded) {
        console.log('[EditorPage] ToneMapping 设置为:', newVal);
        this.updatePBRSettings();
      }
    },
    'pbrSettings.gammaCorrection': function(newVal) {
      if (this.checkpointLoaded) {
        console.log('[EditorPage] GammaCorrection 设置为:', newVal);
        this.updatePBRSettings();
      }
    },
    'pbrSettings.shadow': function(newVal) {
      if (this.checkpointLoaded) {
        console.log('[EditorPage] Shadow 设置为:', newVal ? '✓' : '✗');
        this.updatePBRSettings();
      }
    },
    // 监听渲染模式变化
    renderMode: function(newVal) {
      console.log('[EditorPage] 渲染模式切换为:', newVal);
      if (this.gaussianRenderer) {
        this.gaussianRenderer.setRenderMode(newVal);
      }
    },
    // 监听 LOD 变化
    lodEnabled: function(newVal) {
      this.updateLOD();
    },
    // 监听光源位置变化（从属性面板）
    lightPosition: {
      handler(newVal) {
        if (this.checkpointLoaded && this.lightObject) {
          this.lightObject.position.set(newVal.x, newVal.y, newVal.z);
          this.updateLight();
        }
      },
      deep: true
    }
  }
}
</script>

<style scoped>
/* Editor 独立窗口模式 - 占满整个屏幕 */
.editor-container {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  width: 100vw;
  height: 100vh;
  display: flex;
  flex-direction: column;
  background-color: #1e1e1e;
  color: #e0e0e0;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  overflow: hidden;
}

/* 确保在独立窗口中没有父容器的 padding/margin 干扰 */
:deep(*) {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

/* ========== 1. 顶部全局栏 (Top Bar) ========== */
.top-bar {
  height: 42px;
  min-height: 42px;
  background: #2d2d2d;
  border-bottom: 1px solid #3a3a3a;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 12px;
  user-select: none;
}

/* 窗口控制按钮容器 */
.window-controls-container {
  display: flex;
  align-items: center;
  gap: 8px;
}

/* 窗口控制按钮外层包装器 - 长方形背景 */
.window-controls-wrapper {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  border-radius: 6px;
  padding: 4px 4px 4px 0px;
  margin-left: auto;
  gap: 4px;
}

/* 单个窗口控制按钮 - 独立 view */
.window-control-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 38px;                            /* 固定宽度 */
  height: 26px;                           /* 固定高度 */
  border-radius: 4px;                     /* 圆角 */
  cursor: pointer;
  transition: all 0.2s ease;              /* 平滑过渡 */
}

/* Hover 效果：背景高亮 */
.window-control-btn:hover {
  background-color: rgba(255, 255, 255, 0.15);  /* 白色半透明背景 */
}

/* Active 效果：按下时 */
.window-control-btn:active {
  transform: scale(0.95);                 /* 轻微缩小 */
  background-color: rgba(255, 255, 255, 0.2);  /* 更亮的背景 */
}

.window-btn-icon {
  width: 0.9rem;    /* 从 1rem 调整为 0.9rem */
  height: 0.9rem;   /* 从 1rem 调整为 0.9rem */
  margin: 0.4rem;   /* 从 0.5rem 调整为 0.4rem */
  cursor: pointer;
  opacity: 0.7;
  transition: all 0.2s ease;
  /* 将图标变为白色 */
  filter: brightness(0) invert(1);
}

.menu-section {
  display: flex;
  align-items: center;
  gap: 16px;
}

.logo {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  font-size: 14px;
  color: #ffffff;
}

.logo .iconify {
  font-size: 20px;
  color: #7e22ce;
}

.version-tag {
  font-size: 10px;
  color: #888;
  background: #3a3a3a;
  padding: 2px 6px;
  border-radius: 4px;
}

.menu-items {
  display: flex;
  gap: 4px;
}

.menu-item {
  position: relative;
  padding: 6px 12px;
  font-size: 13px;
  color: #e0e0e0;
  cursor: pointer;
  border-radius: 4px;
  transition: all 0.2s ease;
}

.menu-item:hover {
  background: #3a3a3a;
}

.dropdown-menu {
  position: absolute;
  top: 100%;
  left: 0;
  min-width: 200px;
  background: #2d2d2d;
  border: 1px solid #3a3a3a;
  border-radius: 6px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
  z-index: 1000;
  padding: 4px;
  margin-top: 4px;
}

.dropdown-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  font-size: 13px;
  color: #e0e0e0;
  cursor: pointer;
  border-radius: 4px;
  transition: all 0.2s ease;
}

.dropdown-item:hover {
  background: #3a3a3a;
}

.dropdown-divider {
  height: 1px;
  background: #3a3a3a;
  margin: 4px 0;
}

/* 工作区切换 */
.workspace-tabs {
  display: flex;
  gap: 2px;
  background: #252525;
  padding: 4px;
  border-radius: 6px;
}

.workspace-tab {
  padding: 6px 16px;
  font-size: 13px;
  color: #888;
  cursor: pointer;
  border-radius: 4px;
  transition: all 0.2s ease;
}

.workspace-tab:hover {
  color: #e0e0e0;
  background: #3a3a3a;
}

.workspace-tab.active {
  color: #ffffff;
  background: #7e22ce;
}

/* 场景快捷区 */
.scene-controls {
  display: flex;
  align-items: center;
  gap: 12px;
}

.scene-select {
  padding: 4px 8px;
  background: #3a3a3a;
  border: 1px solid #4a4a4a;
  border-radius: 4px;
  color: #e0e0e0;
  font-size: 13px;
  cursor: pointer;
}

.view-layer-toggle {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 8px;
  background: #3a3a3a;
  border-radius: 4px;
  font-size: 13px;
  cursor: pointer;
}

.filter-buttons {
  display: flex;
  gap: 4px;
}

.filter-btn {
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #3a3a3a;
  border: 1px solid #4a4a4a;
  border-radius: 4px;
  color: #888;
  cursor: pointer;
  transition: all 0.2s ease;
}

.filter-btn:hover {
  background: #4a4a4a;
  color: #e0e0e0;
}

.filter-btn.active {
  background: #7e22ce;
  color: #ffffff;
  border-color: #7e22ce;
}

/* ========== 主体内容区 ========== */
.main-content {
  flex: 1;
  display: flex;
  overflow: hidden;
}

/* ========== 2. 左侧交互工具栏 (Toolbar) ========== */
.toolbar-left {
  width: 56px;
  min-width: 56px;
  background: #2d2d2d;
  border-right: 1px solid #3a3a3a;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 8px 4px;
  gap: 8px;
}

.tool-group {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.tool-button {
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #3a3a3a;
  border: 1px solid #4a4a4a;
  border-radius: 6px;
  color: #888;
  cursor: pointer;
  transition: all 0.2s ease;
}

.tool-button:hover {
  background: #4a4a4a;
  color: #e0e0e0;
}

.tool-button.active {
  background: #7e22ce;
  color: #ffffff;
  border-color: #7e22ce;
}

.tool-separator {
  width: 100%;
  height: 1px;
  background: #3a3a3a;
  margin: 4px 0;
}

.mode-switcher {
  margin-top: auto;
  width: 100%;
  padding: 8px 4px;
}

.mode-select {
  width: 100%;
  padding: 6px;
  background: #3a3a3a;
  border: 1px solid #4a4a4a;
  border-radius: 4px;
  color: #e0e0e0;
  font-size: 12px;
  cursor: pointer;
}

/* ========== 3. 中央 3D 视图主窗口 (Viewport) ========== */
.viewport-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: #1a1a1a;
  overflow: hidden;
}

.viewport-header {
  height: 32px;
  min-height: 32px;
  background: #252525;
  border-bottom: 1px solid #3a3a3a;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 12px;
}

.viewport-info {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 12px;
  color: #888;
}

.viewport-label {
  font-weight: 600;
  color: #7e22ce;
}

.viewport-stats {
  color: #666;
}

.viewport-controls {
  display: flex;
  gap: 4px;
}

.control-btn {
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #3a3a3a;
  border: 1px solid #4a4a4a;
  border-radius: 4px;
  color: #888;
  cursor: pointer;
  transition: all 0.2s ease;
}

.control-btn:hover {
  background: #4a4a4a;
  color: #e0e0e0;
}

.viewport {
  flex: 1;
  position: relative;
  overflow: hidden;
}

.viewport-canvas {
  width: 100%;
  height: 100%;
  display: block;
  position: absolute;
  top: 0;
  left: 0;
  z-index: 1;
}

.view-cube {
  position: absolute;
  top: 12px;
  right: 12px;
  width: 80px;
  height: 80px;
  background: rgba(45, 45, 45, 0.8);
  border: 1px solid #3a3a3a;
  border-radius: 8px;
  pointer-events: none;
}

.cube-face {
  position: absolute;
  font-size: 10px;
  color: #888;
  font-weight: 600;
}

.cube-face.front {
  bottom: 8px;
  left: 50%;
  transform: translateX(-50%);
}

.cube-face.right {
  right: 8px;
  top: 50%;
  transform: translateY(-50%);
}

.cube-face.top {
  top: 8px;
  left: 50%;
  transform: translateX(-50%);
}

.axis-indicator {
  position: absolute;
  bottom: 12px;
  left: 12px;
  width: 60px;
  height: 60px;
  pointer-events: none;
}

.axis-x, .axis-y, .axis-z {
  position: absolute;
  font-size: 12px;
  font-weight: 700;
  line-height: 1;
  white-space: nowrap;
}

.axis-x {
  color: #ff4444;
  bottom: 0;
  left: 50%;
  transform: translateX(-50%);
}

.axis-y {
  color: #44ff44;
  top: 50%;
  right: 0;
  transform: translateY(-50%);
}

.axis-z {
  color: #4444ff;
  top: 0;
  left: 50%;
  transform: translateX(-50%);
}

.timeline {
  height: 48px;
  min-height: 48px;
  background: #252525;
  border-top: 1px solid #3a3a3a;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 0 12px;
}

.timeline-controls {
  display: flex;
  gap: 4px;
}

.timeline-btn {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #3a3a3a;
  border: 1px solid #4a4a4a;
  border-radius: 4px;
  color: #888;
  cursor: pointer;
  transition: all 0.2s ease;
}

.timeline-btn:hover {
  background: #4a4a4a;
  color: #e0e0e0;
}

.timeline-slider {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 12px;
}

.timeline-range {
  flex: 1;
  height: 6px;
  border-radius: 3px;
  background: #3a3a3a;
  outline: none;
  -webkit-appearance: none;
}

.timeline-range::-webkit-slider-thumb {
  -webkit-appearance: none;
  appearance: none;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: #7e22ce;
  cursor: pointer;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
}

.frame-display {
  min-width: 80px;
  text-align: right;
  font-size: 12px;
  color: #888;
}

/* ========== 4. 右侧属性与场景管理区 (Right Panels) ========== */
.right-panel {
  width: 320px;
  min-width: 320px;
  background: #2d2d2d;
  border-left: 1px solid #3a3a3a;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.outliner {
  flex: 1;
  min-height: 200px;
  border-bottom: 1px solid #3a3a3a;
  display: flex;
  flex-direction: column;
}

.panel-header {
  height: 32px;
  min-height: 32px;
  background: #252525;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 12px;
}

.panel-title {
  font-size: 13px;
  font-weight: 600;
  color: #e0e0e0;
}

.panel-actions {
  display: flex;
  gap: 4px;
}

.icon-btn {
  width: 20px;
  height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: none;
  border-radius: 4px;
  color: #888;
  cursor: pointer;
  transition: all 0.2s ease;
}

.icon-btn:hover {
  background: #3a3a3a;
  color: #e0e0e0;
}

.outliner-content {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.outliner-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.outliner-item:hover {
  background: #3a3a3a;
}

.outliner-item.child-item {
  padding-left: 28px;
}

.outliner-item.selected {
  background: #3a3a3a;
  border-left: 2px solid #7e22ce;
}

.item-icon {
  font-size: 16px;
}

.scene-icon { color: #4488ff; }
.light-icon { color: #ffcc00; }
.camera-icon { color: #8888ff; }
.mesh-icon { color: #44ff88; }

.item-name {
  flex: 1;
  font-size: 13px;
  color: #e0e0e0;
}

.item-actions {
  display: flex;
  gap: 4px;
  opacity: 0;
  transition: opacity 0.2s ease;
}

.outliner-item:hover .item-actions {
  opacity: 1;
}

.action-icon {
  font-size: 14px;
  color: #888;
  cursor: pointer;
}

.action-icon:hover {
  color: #e0e0e0;
}

/* 属性编辑器 */
.properties-editor {
  height: 400px;
  min-height: 400px;
  display: flex;
  flex-direction: column;
}

.properties-tabs {
  display: flex;
  gap: 2px;
  background: #252525;
  padding: 4px;
  border-bottom: 1px solid #3a3a3a;
}

.property-tab {
  flex: 1;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #3a3a3a;
  border: 1px solid #4a4a4a;
  border-radius: 4px;
  color: #888;
  cursor: pointer;
  transition: all 0.2s ease;
}

.property-tab:hover {
  background: #4a4a4a;
  color: #e0e0e0;
}

.property-tab.active {
  background: #7e22ce;
  color: #ffffff;
  border-color: #7e22ce;
}

.properties-content {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
}

.property-section {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.property-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.group-header {
  font-size: 12px;
  font-weight: 600;
  color: #888;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.property-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.axis-label {
  min-width: 16px;
  font-size: 11px;
  font-weight: 700;
}

.axis-x { color: #ff4444; }
.axis-y { color: #44ff44; }
.axis-z { color: #4444ff; }

.number-input {
  flex: 1;
  padding: 6px 8px;
  background: #3a3a3a;
  border: 1px solid #4a4a4a;
  border-radius: 4px;
  color: #e0e0e0;
  font-size: 12px;
}

.number-input:focus {
  outline: none;
  border-color: #7e22ce;
}

.color-row {
  justify-content: center;
}

.color-picker {
  width: 100%;
  height: 32px;
  border: 1px solid #4a4a4a;
  border-radius: 4px;
  cursor: pointer;
  background: transparent;
}

.property-label {
  min-width: 80px;
  font-size: 12px;
  color: #aaa;
}

.slider-input {
  flex: 1;
  height: 6px;
  border-radius: 3px;
  background: #3a3a3a;
  outline: none;
  -webkit-appearance: none;
}

.slider-input::-webkit-slider-thumb {
  -webkit-appearance: none;
  appearance: none;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: #7e22ce;
  cursor: pointer;
}

.value-display {
  min-width: 60px;
  text-align: right;
  font-size: 11px;
  color: #888;
}

.property-select {
  width: 100%;
  padding: 6px 8px;
  background: #3a3a3a;
  border: 1px solid #4a4a4a;
  border-radius: 4px;
  color: #e0e0e0;
  font-size: 12px;
  cursor: pointer;
}

.toggle-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px;
  background: #3a3a3a;
  border-radius: 4px;
}

.toggle-label {
  font-size: 12px;
  color: #e0e0e0;
  font-weight: 500;
}

.switch {
  position: relative;
  display: inline-block;
  width: 36px;
  height: 20px;
}

.switch input {
  opacity: 0;
  width: 0;
  height: 0;
}

.slider-toggle {
  position: absolute;
  cursor: pointer;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: #4a4a4a;
  transition: .3s;
  border-radius: 20px;
}

.slider-toggle:before {
  position: absolute;
  content: "";
  height: 16px;
  width: 16px;
  left: 2px;
  bottom: 2px;
  background-color: white;
  transition: .3s;
  border-radius: 50%;
}

input:checked + .slider-toggle {
  background-color: #7e22ce;
}

input:checked + .slider-toggle:before {
  transform: translateX(16px);
}

/* 滚动条样式 */
.outliner-content::-webkit-scrollbar,
.properties-content::-webkit-scrollbar {
  width: 8px;
}

.scrollbar-track {
  background: #2d2d2d;
}

.scrollbar-thumb {
  background: #4a4a4a;
  border-radius: 4px;
}

.scrollbar-thumb:hover {
  background: #5a5a5a;
}

/* ========== PBR 功能新增样式 ========== */

/* 工具栏 */
.toolbar {
  height: 40px;
  background: #2d2d2d;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 12px;
  border-bottom: 1px solid #3a3a3a;
}

.toolbar-left,
.toolbar-right {
  display: flex;
  gap: 8px;
  align-items: center;
}

.status-info {
  color: #4ade80;
  font-size: 13px;
  margin-left: 8px;
}

/* 主容器布局 */
.main-container {
  flex: 1;
  display: flex;
  overflow: hidden;
}

.viewport-container {
  flex: 1;
  position: relative;
}

.canvas-container {
  width: 100%;
  height: 100%;
}

/* 渲染模式切换 */
.render-modes {
  position: absolute;
  bottom: 12px;
  left: 12px;
  display: flex;
  gap: 4px;
  z-index: 10;
}

.mode-btn {
  padding: 6px 12px;
  background: #3a3a3a;
  border: 1px solid #4a4a4a;
  border-radius: 4px;
  color: #888;
  cursor: pointer;
  font-size: 12px;
  transition: all 0.2s ease;
}

.mode-btn:hover {
  background: #4a4a4a;
  color: #e0e0e0;
}

.mode-btn.active {
  background: #7e22ce;
  color: #fff;
  border-color: #7e22ce;
}

/* 控制面板 */
.control-panel {
  width: 300px;
  min-width: 300px;
  background: #2d2d2d;
  border-left: 1px solid #3a3a3a;
  overflow-y: auto;
}

.panel-section {
  padding: 12px;
  border-bottom: 1px solid #3a3a3a;
}

.panel-section h3 {
  font-size: 14px;
  color: #e0e0e0;
  margin-bottom: 12px;
  font-weight: 600;
}

.control-group {
  margin-bottom: 12px;
}

.control-group label {
  display: block;
  font-size: 12px;
  color: #aaa;
  margin-bottom: 4px;
}

.vector3-input {
  display: flex;
  gap: 4px;
}

.vector3-input input {
  flex: 1;
  padding: 6px;
  background: #3a3a3a;
  border: 1px solid #4a4a4a;
  border-radius: 4px;
  color: #e0e0e0;
  font-size: 12px;
}

.vector3-input input:focus {
  outline: none;
  border-color: #7e22ce;
}

.color-picker {
  display: flex;
  align-items: center;
  gap: 8px;
}

.color-picker input[type="color"] {
  width: 40px;
  height: 30px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  background: transparent;
}

.color-picker span {
  font-size: 11px;
  color: #888;
}

.value-label {
  font-size: 11px;
  color: #888;
  margin-left: 8px;
}

.info-row {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: #888;
  padding: 4px 0;
}

.info-row span:first-child {
  font-weight: 500;
}

/* 加载状态 */
.loading-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.7);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  z-index: 9999;
}

.loading-spinner {
  width: 50px;
  height: 50px;
  border: 4px solid #3a3a3a;
  border-top-color: #7e22ce;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.loading-text {
  color: #e0e0e0;
  font-size: 14px;
  margin-top: 16px;
}

/* 按钮样式 */
.btn-primary {
  padding: 6px 12px;
  background: #7e22ce;
  border: none;
  border-radius: 4px;
  color: #fff;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.btn-primary:hover {
  background: #9333ea;
}

.btn-secondary {
  padding: 6px 12px;
  background: #3a3a3a;
  border: 1px solid #4a4a4a;
  border-radius: 4px;
  color: #e0e0e0;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.btn-secondary:hover {
  background: #4a4a4a;
}
</style>