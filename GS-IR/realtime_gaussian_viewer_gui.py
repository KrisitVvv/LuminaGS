#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
实时高斯模型查看器 - GUI 版本
基于 EditorPage.vue 的布局设计，使用 Tkinter 实现正常交互界面
"""

import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import json
import numpy as np
import torch
from typing import Dict, List, Optional, Tuple
from argparse import ArgumentParser

from arguments import GroupParams, ModelParams, PipelineParams, get_combined_args
from gaussian_renderer import GaussianModel, render
from scene import Scene, Camera
from utils.graphics_utils import getProjectionMatrix
from diff_gaussian_rasterization import _C


class RealtimeViewerGUI:
    def __init__(self, root: tk.Tk, model_path: str, checkpoint: str, dataset: GroupParams, pipeline: GroupParams, resolution_scale: float = 1.0):
        self.root = root
        self.root.title("LuminaGS - Realtime Viewer")
        self.root.geometry("1400x800")
        self.root.minsize(1200, 800)
        
        # 模型数据
        self.model_path = model_path
        self.checkpoint = checkpoint
        self.dataset = dataset
        self.pipeline = pipeline
        
        # 配置文件路径
        self.config_dir = os.path.join(model_path, '.luminags')
        self.config_file = os.path.join(self.config_dir, 'config.json')
        
        # 加载高斯模型
        print("[RealtimeViewer] 正在加载高斯模型...", flush=True)
        self.gaussians = GaussianModel(dataset.sh_degree)
        self.scene = Scene(dataset, self.gaussians, shuffle=False)
        
        print(f"[RealtimeViewer] 正在加载 checkpoint: {checkpoint}", flush=True)
        checkpoint_data = torch.load(checkpoint)
        if isinstance(checkpoint_data, Tuple):
            model_params = checkpoint_data[0]
        elif isinstance(checkpoint_data, Dict):
            model_params = checkpoint_data["gaussians"]
        else:
            raise TypeError("Unsupported checkpoint format")
        
        self.gaussians.restore(model_params)
        print("[RealtimeViewer] 模型加载完成", flush=True)
        
        # ✅ 写入就绪信号文件（Electron 可以检测）
        ready_signal_path = os.path.join(model_path, '.luminags', 'gui_ready.signal')
        try:
            os.makedirs(os.path.dirname(ready_signal_path), exist_ok=True)
            with open(ready_signal_path, 'w', encoding='utf-8') as f:
                f.write(f'GUI_READY|{os.getpid()}|{model_path}\n')
            print(f"[RealtimeViewer] ✓ 就绪信号已写入：{ready_signal_path}", flush=True)
        except Exception as e:
            print(f"[RealtimeViewer] 写入信号文件失败：{e}", flush=True)
        
        # 获取参考相机
        self.views = self.scene.getTrainCameras()
        if len(self.views) == 0:
            raise ValueError("No cameras found in the scene")
        
        self.ref_view = self.views[0]
        self.H = int(self.ref_view.image_height * resolution_scale)
        self.W = int(self.ref_view.image_width * resolution_scale)
        
        # 场景统计
        self.vertex_count = len(self.gaussians.get_xyz)
        self.face_count = self.vertex_count // 2
        
        # 相机参数（球坐标系）
        self.camera_center = torch.zeros(3)
        self.distance = 5.0
        self.yaw = 0.0
        self.pitch = 0.0
        
        # 光源参数（初始化为场景前方）
        # 计算场景的边界框来确定合适的光源位置
        try:
            xyz = self.gaussians.get_xyz
            min_bound = xyz.min(dim=0)[0]
            max_bound = xyz.max(dim=0)[0]
            scene_center = (min_bound + max_bound) / 2
            scene_size = max_bound - min_bound
            max_dim = scene_size.max().item()
            
            # 将光源放在场景中心的右上方前方
            light_offset = max_dim * 1.5
            self.light_position = torch.tensor([
                scene_center[0].item() + light_offset,
                scene_center[1].item() + light_offset,
                scene_center[2].item() + light_offset
            ], dtype=torch.float32)
            print(f"[RealtimeViewer] 光源初始位置：{self.light_position.cpu().numpy()}")
        except:
            # 如果无法计算，使用默认位置
            self.light_position = torch.tensor([5.0, 5.0, 5.0], dtype=torch.float32)
        
        # 光照强度将在 _build_gui 后初始化
        self.enable_pbr = False
        
        # PBR 设置
        self.pbr_settings = {
            'metallic': False,
            'indirect': False,
            'tone_mapping': False,
            'gamma_correction': False,
            'shadow': True,
        }
        
        # 渲染质量模式
        self.quality_mode = "standard"  # "standard" 或 "high_quality"
        self.shadow_threshold = 2.0  # 阴影阈值，对应 light_move.py 中的 threshold 参数
        
        # 深度立方体贴图缓存（避免每帧重新计算）
        self.depth_cubemap_cache = None
        self.last_light_position = None
        
        # ✅ 显存检测与分辨率自适应
        self.vram_gb = self._get_gpu_vram_gb()
        print(f"[RealtimeViewer] 检测到显存: {self.vram_gb:.1f} GB")
        
        if self.vram_gb < 4.0:
            # 显存不足4GB，禁用高质量模式
            self.cubemap_resolution = 0  # 标记为不可用
            self.high_quality_disabled = True
            print("[警告] 显存不足4GB，已禁用高质量阴影模式")
        elif self.vram_gb < 12.0:
            # 显存4-12GB，使用中等分辨率
            self.cubemap_resolution = 512
            self.high_quality_disabled = False
            print(f"[提示] 显存4-12GB，立方体贴图分辨率设为512")
        else:
            # 显存>=12GB，使用高分辨率
            self.cubemap_resolution = 1024
            self.high_quality_disabled = False
            print(f"[提示] 显存充足(>=12GB)，立方体贴图分辨率设为1024")
        
        # 视图控制
        self.show_wireframe = False
        self.show_light_gizmo = True
        self.auto_rotate = False
        
        # ✅ 光源动画状态
        self.light_animation_playing = False  # 是否正在播放
        self.light_animation_frame = 0  # 当前帧
        self.light_animation_total_frames = 480  # 总帧数（与 light_move.py 一致）
        self.light_animation_fps = 24  # 动画 FPS
        self.light_trajectory = None  # 光源轨迹
        
        # 渲染状态
        self.rendering = False
        self.render_thread = None
        self.current_frame = None
        self.fps = 0.0
        
        # 鼠标交互状态
        self.mouse_last_x = -1
        self.mouse_last_y = -1
        self.mouse_left_pressed = False
        self.mouse_right_pressed = False
        
        # 就绪信号文件路径（用于退出时清理）
        self.ready_signal_path = os.path.join(model_path, '.luminags', 'gui_ready.signal')
        
        # ✅ 性能优化：缓存背景色张量
        self.bg_color = torch.tensor([0.0, 0.0, 0.0], dtype=torch.float32).cuda()
        
        # 加载用户配置
        print("[RealtimeViewer] 正在加载用户配置...", flush=True)
        self.user_config = self._load_user_config()
        
        # 构建 GUI
        self._build_gui()
        
        # 初始化光照强度（在 GUI 构建后）
        self.light_intensity = torch.tensor([self.light_r_var.get(), self.light_g_var.get(), self.light_b_var.get()], dtype=torch.float32).cuda()
        
        # 应用用户配置（如果有）
        if self.user_config:
            print("[RealtimeViewer] 应用保存的用户配置...", flush=True)
            self._apply_user_config()
        
        # 启动渲染循环
        self._start_render_loop()
    
    def _get_gpu_vram_gb(self) -> float:
        """获取GPU显存大小（GB）"""
        try:
            import torch
            if torch.cuda.is_available():
                # 获取总显存（字节）并转换为GB
                total_memory = torch.cuda.get_device_properties(0).total_memory
                return total_memory / (1024 ** 3)
            else:
                print("[警告] CUDA不可用，默认认为显存不足")
                return 0.0
        except Exception as e:
            print(f"[警告] 无法检测显存: {e}，默认为0GB")
            return 0.0
    
    def _build_gui(self):
        """构建主界面"""
        # 主容器（占据剩余空间）
        main_frame = ttk.Frame(self.root, padding="5")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 右侧：属性面板（先打包右侧，固定宽度）
        right_panel = self._create_properties_panel(main_frame)
        right_panel.pack(side=tk.RIGHT, fill=tk.Y, padx=(5, 0))
        
        # 左侧：视口区域（后打包左侧，占据剩余空间）
        left_frame = ttk.Frame(main_frame)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # FPS 信息栏（先打包在底部）
        info_frame = ttk.Frame(left_frame)
        info_frame.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.fps_label = ttk.Label(info_frame, text="FPS: 0.0", font=("Arial", 10, "bold"), foreground="#00ff00")
        self.fps_label.pack(side=tk.LEFT, padx=5, pady=2)
        
        # ✅ 播放按钮（光源自动移动）
        self.play_button = ttk.Button(info_frame, text="▶ 播放", command=self._toggle_light_animation, width=8)
        self.play_button.pack(side=tk.LEFT, padx=5, pady=2)
        
        # 图像显示标签（后打包，占据剩余空间）
        self.viewport_label = ttk.Label(left_frame, background="#1a1a1a")
        self.viewport_label.pack(fill=tk.BOTH, expand=True)
        
        # 绑定鼠标事件
        self.viewport_label.bind("<Button-1>", self._on_mouse_down)
        self.viewport_label.bind("<ButtonRelease-1>", self._on_mouse_up)
        self.viewport_label.bind("<B1-Motion>", self._on_mouse_drag)
        self.viewport_label.bind("<Button-3>", self._on_right_mouse_down)
        self.viewport_label.bind("<ButtonRelease-3>", self._on_right_mouse_up)
        self.viewport_label.bind("<B3-Motion>", self._on_right_mouse_drag)
        self.viewport_label.bind("<MouseWheel>", self._on_mouse_wheel)
    
    # ========== 鼠标事件处理方法 ==========
    
    def _on_mouse_down(self, event):
        """左键按下"""
        self.mouse_left_pressed = True
        self.mouse_last_x = event.x
        self.mouse_last_y = event.y
    
    def _on_mouse_up(self, event):
        """左键释放"""
        self.mouse_left_pressed = False
        self.mouse_last_x = -1
        self.mouse_last_y = -1
    
    def _on_mouse_drag(self, event):
        """左键拖动 - 旋转视角"""
        if self.mouse_left_pressed and self.mouse_last_x >= 0:
            dx = event.x - self.mouse_last_x
            dy = event.y - self.mouse_last_y
            
            self.yaw -= dx * 0.5
            self.pitch += dy * 0.5
            self.pitch = max(-89, min(89, self.pitch))
            
            self.mouse_last_x = event.x
            self.mouse_last_y = event.y
    
    def _on_right_mouse_down(self, event):
        """右键按下"""
        self.mouse_right_pressed = True
        self.mouse_last_x = event.x
        self.mouse_last_y = event.y
    
    def _on_right_mouse_up(self, event):
        """右键释放"""
        self.mouse_right_pressed = False
        self.mouse_last_x = -1
        self.mouse_last_y = -1
    
    def _on_right_mouse_drag(self, event):
        """右键拖动 - 平移相机"""
        if self.mouse_right_pressed and self.mouse_last_x >= 0:
            dx = event.x - self.mouse_last_x
            dy = event.y - self.mouse_last_y
            
            move_speed = 0.01 * self.distance
            self.camera_center[0] -= dx * move_speed
            self.camera_center[1] += dy * move_speed
            
            self.mouse_last_x = event.x
            self.mouse_last_y = event.y
    
    def _on_mouse_wheel(self, event):
        """滚轮缩放"""
        if event.delta > 0:
            self.distance *= 0.95
            self.distance = max(self.distance, 0.1)
        else:
            self.distance *= 1.05
            self.distance = min(self.distance, 100.0)
    
    def _create_properties_panel(self, parent) -> ttk.Frame:
        """创建右侧属性面板（带滚动）"""
        # 创建主容器
        panel = ttk.Frame(parent, width=320)
        panel.pack_propagate(False)
        
        # 创建Canvas和Scrollbar
        canvas = tk.Canvas(panel, highlightthickness=0, width=300)
        scrollbar = ttk.Scrollbar(panel, orient="vertical", command=canvas.yview)
        
        # 创建可滚动的框架
        scrollable_frame = ttk.Frame(canvas)
        
        # 配置滚动区域
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        # 在Canvas中创建窗口，并设置宽度
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw", width=300)
        
        # 配置Canvas的滚动命令
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # 绑定鼠标滚轮事件（仅在Canvas上）
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        
        canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", _on_mousewheel))
        canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))
        
        # 打包Canvas和Scrollbar
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # ========== 以下内容添加到 scrollable_frame 中 ==========
        
        # 视图控制（从工具栏移过来）
        view_group = ttk.LabelFrame(scrollable_frame, text="视图控制", padding="10")
        view_group.pack(fill=tk.X, pady=5)
        
        ttk.Button(view_group, text="重置视角", command=self._reset_view).pack(pady=5, padx=10, fill=tk.X)
        
        # 💾 配置保存功能
        config_group = ttk.LabelFrame(scrollable_frame, text="配置管理", padding="10")
        config_group.pack(fill=tk.X, pady=5)
        
        ttk.Button(config_group, text="💾 保存当前配置", command=self._save_user_config, style='Accent.TButton').pack(pady=8, padx=10, fill=tk.X)
        
        # 渲染模式（从工具栏移过来）
        render_group = ttk.LabelFrame(scrollable_frame, text="渲染模式", padding="10")
        render_group.pack(fill=tk.X, pady=5)
        
        self.render_mode_var = tk.StringVar(value="normal")
        ttk.Radiobutton(render_group, text="普通模式", variable=self.render_mode_var, value="normal",
                       command=self._toggle_render_mode).pack(anchor=tk.W, padx=10)
        ttk.Radiobutton(render_group, text="标准重光照", variable=self.render_mode_var, value="standard_relight",
                       command=self._toggle_render_mode).pack(anchor=tk.W, padx=10)
        ttk.Radiobutton(render_group, text="增强重光照", variable=self.render_mode_var, value="enhanced_relight",
                       command=self._toggle_render_mode).pack(anchor=tk.W, padx=10)
        
        # 截图功能
        screenshot_group = ttk.Frame(scrollable_frame, padding="10")
        screenshot_group.pack(fill=tk.X, pady=5)
        
        ttk.Button(screenshot_group, text="📸 保存截图", command=self._save_screenshot).pack(pady=5, padx=10, fill=tk.X)
        
        # 光源控制
        light_group = ttk.LabelFrame(scrollable_frame, text="光源控制", padding="10")
        light_group.pack(fill=tk.X, pady=5)
        
        ttk.Label(light_group, text="位置 X:").pack(anchor=tk.W)
        self.light_x_var = tk.DoubleVar(value=0.0)
        ttk.Scale(light_group, from_=-20, to=20, variable=self.light_x_var, 
                  command=self._update_light_position).pack(fill=tk.X)
        
        ttk.Label(light_group, text="位置 Y:").pack(anchor=tk.W)
        self.light_y_var = tk.DoubleVar(value=0.0)
        ttk.Scale(light_group, from_=-20, to=20, variable=self.light_y_var,
                  command=self._update_light_position).pack(fill=tk.X)
        
        ttk.Label(light_group, text="位置 Z:").pack(anchor=tk.W)
        self.light_z_var = tk.DoubleVar(value=5.0)
        ttk.Scale(light_group, from_=0, to=40, variable=self.light_z_var,
                  command=self._update_light_position).pack(fill=tk.X)
        
        # 光照强度控制
        intensity_group = ttk.LabelFrame(scrollable_frame, text="光照强度控制", padding="10")
        intensity_group.pack(fill=tk.X, pady=5)
        
        # 整体强度控制
        ttk.Label(intensity_group, text="整体强度:").pack(anchor=tk.W)
        self.light_master_var = tk.DoubleVar(value=100.0)
        self.master_scale = ttk.Scale(intensity_group, from_=0, to=500, variable=self.light_master_var,
                  command=self._update_light_master_intensity)
        self.master_scale.pack(fill=tk.X)
        
        ttk.Separator(intensity_group, orient='horizontal').pack(fill=tk.X, pady=5)
        
        ttk.Label(intensity_group, text="R 强度:").pack(anchor=tk.W)
        self.light_r_var = tk.DoubleVar(value=100.0)
        ttk.Scale(intensity_group, from_=0, to=500, variable=self.light_r_var,
                  command=self._update_light_intensity).pack(fill=tk.X)
        
        ttk.Label(intensity_group, text="G 强度:").pack(anchor=tk.W)
        self.light_g_var = tk.DoubleVar(value=100.0)
        ttk.Scale(intensity_group, from_=0, to=500, variable=self.light_g_var,
                  command=self._update_light_intensity).pack(fill=tk.X)
        
        ttk.Label(intensity_group, text="B 强度:").pack(anchor=tk.W)
        self.light_b_var = tk.DoubleVar(value=100.0)
        ttk.Scale(intensity_group, from_=0, to=500, variable=self.light_b_var,
                  command=self._update_light_intensity).pack(fill=tk.X)
        
        # PBR 设置
        pbr_group = ttk.LabelFrame(scrollable_frame, text="PBR 设置", padding="10")
        pbr_group.pack(fill=tk.X, pady=5)
        
        self.metallic_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(pbr_group, text="Metallic", variable=self.metallic_var,
                       command=self._update_pbr_settings).pack(anchor=tk.W)
        
        self.indirect_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(pbr_group, text="Indirect Lighting", variable=self.indirect_var,
                       command=self._update_pbr_settings).pack(anchor=tk.W)
        
        self.shadow_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(pbr_group, text="Shadow", variable=self.shadow_var,
                       command=self._update_pbr_settings).pack(anchor=tk.W)
        
        # 场景统计
        stats_group = ttk.LabelFrame(scrollable_frame, text="场景统计", padding="10")
        stats_group.pack(fill=tk.X, pady=5)
        
        self.stats_label = ttk.Label(stats_group, 
                                     text=f"Vertices: {self.vertex_count:,}\nFaces: {self.face_count:,}",
                                     justify=tk.LEFT)
        self.stats_label.pack(anchor=tk.W)
        
        return panel
    
    
    def _start_render_loop(self):
        """启动渲染循环"""
        self.rendering = True
        
        def render_loop():
            frame_count = 0
            start_time = torch.cuda.Event(enable_timing=True)
            end_time = torch.cuda.Event(enable_timing=True)
            start_time.record()
            
            while self.rendering:
                try:
                    # 渲染当前帧
                    frame = self._render_current_view()
                    self.current_frame = frame
                    
                    # 计算 FPS
                    frame_count += 1
                    end_time.record()
                    torch.cuda.synchronize()
                    elapsed_ms = start_time.elapsed_time(end_time) / 1000.0
                    if elapsed_ms >= 1.0:
                        self.fps = frame_count / elapsed_ms
                        frame_count = 0
                        start_time.record()
                    
                    # 更新 UI（在主线程中）
                    self.root.after(0, self._update_display)
                    
                except Exception as e:
                    print(f"[渲染错误] {e}")
                    import traceback
                    traceback.print_exc()
                
                # 控制帧率
                time.sleep(0.016)  # ~60 FPS
        
        self.render_thread = threading.Thread(target=render_loop, daemon=True)
        self.render_thread.start()
    
    def _render_current_view(self) -> np.ndarray:
        """渲染当前视角"""
        c2w = self._get_current_c2w()
        viewpoint_camera = self._create_camera_from_c2w(c2w)
        
        class SimplePipe:
            debug = False
            convert_SHs_python = False
            compute_cov3D_python = False
        
        pipe = SimplePipe()
        
        # ✅ 性能优化：根据模式决定是否计算法线等PBR数据
        if self.enable_pbr:
            rendering_result = render(
                viewpoint_camera=viewpoint_camera,
                pc=self.gaussians,
                pipe=pipe,
                bg_color=self.bg_color,
                inference=True,
                pad_normal=True,
                derive_normal=True,
            )
            render_rgb = self._apply_pbr_relighting(rendering_result, c2w)
        else:
            # 标准模式：禁用不必要的法线计算，提升性能
            rendering_result = render(
                viewpoint_camera=viewpoint_camera,
                pc=self.gaussians,
                pipe=pipe,
                bg_color=self.bg_color,
                inference=True,
                pad_normal=False,   # ✅ 关闭法线填充
                derive_normal=False, # ✅ 关闭法线推导
            )
            render_rgb = rendering_result["render"]
        
        # 转换为 numpy 数组
        render_rgb = render_rgb.detach().permute(1, 2, 0).clamp(0.0, 1.0).cpu().numpy()
        render_rgb = (render_rgb * 255).astype(np.uint8)
        
        return render_rgb
    
    def _update_display(self):
        """更新显示"""
        if self.current_frame is not None:
            # 这里需要将 numpy 数组转换为 PhotoImage
            # 由于 Tkinter 不支持直接显示 numpy，需要使用 PIL
            try:
                from PIL import Image, ImageTk, ImageDraw
                image = Image.fromarray(self.current_frame)
                image = image.resize((self.viewport_label.winfo_width(), 
                                     self.viewport_label.winfo_height()), 
                                    Image.Resampling.LANCZOS)
                
                # 在图像上绘制光源标识
                if self.show_light_gizmo and self.enable_pbr:
                    draw = ImageDraw.Draw(image)
                    # 计算光源在屏幕上的投影位置
                    light_screen_pos = self._project_light_to_screen(image.width, image.height)
                    if light_screen_pos is not None:
                        lx, ly = light_screen_pos
                        # 绘制光源中心点（黄色圆圈）
                        radius = 8
                        draw.ellipse([lx-radius, ly-radius, lx+radius, ly+radius], 
                                   outline='yellow', width=2)
                        draw.ellipse([lx-3, ly-3, lx+3, ly+3], fill='yellow')
                        # 绘制十字准星
                        cross_size = 15
                        draw.line([lx-cross_size, ly, lx+cross_size, ly], fill='yellow', width=1)
                        draw.line([lx, ly-cross_size, lx, ly+cross_size], fill='yellow', width=1)
                
                photo = ImageTk.PhotoImage(image)
                self.viewport_label.configure(image=photo)
                self.viewport_label.image = photo  # 保持引用
                
                # 更新 FPS 信息
                self.fps_label.config(text=f"FPS: {self.fps:.1f}")
                
            except Exception as e:
                print(f"[显示错误] {e}")
    
    def _project_light_to_screen(self, screen_width: int, screen_height: int):
        """将光源位置投影到屏幕坐标"""
        try:
            import torch.nn.functional as F
            
            # 获取当前相机矩阵
            c2w = self._get_current_c2w().cuda()  # ✅ 确保在 CUDA 上
            w2c = torch.inverse(c2w)
            
            # 光源位置（世界坐标）
            light_pos_world = self.light_position.cuda()
            
            # 转换到相机坐标系
            light_pos_cam = w2c[:3, :3] @ light_pos_world + w2c[:3, 3]
            
            # 检查光源是否在相机前方
            if light_pos_cam[2] <= 0:
                return None
            
            # 获取相机内参
            tan_fovx = np.tan(self.ref_view.FoVx * 0.5)
            tan_fovy = np.tan(self.ref_view.FoVy * 0.5)
            focal_x = screen_width / (2.0 * tan_fovx)
            focal_y = screen_height / (2.0 * tan_fovy)
            
            # 透视投影
            x_ndc = (light_pos_cam[0] / light_pos_cam[2]) * focal_x / (screen_width / 2)
            y_ndc = -(light_pos_cam[1] / light_pos_cam[2]) * focal_y / (screen_height / 2)  # Y轴翻转
            
            # 转换到屏幕坐标
            screen_x = (x_ndc + 1.0) * screen_width / 2
            screen_y = (y_ndc + 1.0) * screen_height / 2
            
            # 检查是否在屏幕范围内
            if 0 <= screen_x <= screen_width and 0 <= screen_y <= screen_height:
                return (int(screen_x), int(screen_y))
            else:
                return None
        except Exception as e:
            print(f"[投影错误] {e}")
            return None
    
    def _get_current_c2w(self) -> torch.Tensor:
        """计算相机外参"""
        import torch.nn.functional as F
        
        yaw_rad = np.deg2rad(self.yaw)
        pitch_rad = np.deg2rad(self.pitch)
        
        cam_x = self.distance * np.cos(pitch_rad) * np.sin(yaw_rad)
        cam_y = self.distance * np.sin(pitch_rad)
        cam_z = self.distance * np.cos(pitch_rad) * np.cos(yaw_rad)
        
        camera_position = self.camera_center + torch.tensor([cam_x, cam_y, cam_z], dtype=torch.float32)
        
        forward = F.normalize(self.camera_center - camera_position, p=2, dim=0)
        right = F.normalize(torch.cross(forward, torch.tensor([0, 1, 0], dtype=torch.float32)), p=2, dim=0)
        up = F.normalize(torch.cross(right, forward), p=2, dim=0)
        
        R = torch.stack([right, up, -forward], dim=0)
        
        c2w = torch.eye(4, dtype=torch.float32)
        c2w[:3, :3] = R.t()
        c2w[:3, 3] = camera_position
        
        return c2w
    
    def _create_camera_from_c2w(self, c2w: torch.Tensor) -> Camera:
        """从 c2w 创建虚拟相机"""
        R = c2w[:3, :3].T.cpu().numpy()
        T = c2w[:3, 3].cpu().numpy()
        
        dummy_image = torch.ones((3, self.H, self.W), dtype=torch.float32).cuda()
        
        camera = Camera(
            colmap_id=999,
            R=R,
            T=T,
            FoVx=self.ref_view.FoVx,
            FoVy=self.ref_view.FoVy,
            image=dummy_image,
            gt_alpha_mask=None,
            image_name="realtime_view",
            uid=999
        )
        
        return camera
    
    def _apply_pbr_relighting(self, rendering_result: Dict, c2w: torch.Tensor) -> torch.Tensor:
        """应用 PBR 重光照（包含直接光照和间接光照）"""
        import torch.nn.functional as F
        
        # 确保 c2w 在 CUDA 上
        c2w = c2w.cuda()
        
        # 提取 PBR 材质参数
        albedo_map = rendering_result["albedo_map"]  # [3, H, W]
        roughness_map = rendering_result["roughness_map"]  # [1, H, W]
        metallic_map_from_checkpoint = rendering_result["metallic_map"]  # [1, H, W]
        normal_map = rendering_result["normal_map"]  # [3, H, W]
        depth_map = rendering_result["depth_map"]  # [1, H, W]
        normal_mask = rendering_result["normal_mask"]  # [1, H, W]
        
        # ✅ 根据用户设置动态调整 PBR 参数
        use_metallic = self.pbr_settings.get('metallic', False)
        use_shadow = self.pbr_settings.get('shadow', True)
        use_indirect = self.pbr_settings.get('indirect', False)
        
        # 如果未启用 Metallic，则使用固定值（非金属）
        if not use_metallic:
            metallic_map = torch.zeros_like(metallic_map_from_checkpoint)
        else:
            metallic_map = metallic_map_from_checkpoint
        
        # 计算视线方向（世界坐标系）
        canonical_rays = self._get_canonical_rays()  # [H*W, 3]
        
        # 将相机坐标系的光线转换到世界坐标系
        world_rays = (c2w[:3, :3] @ canonical_rays.T).T  # [H*W, 3]
        world_rays = F.normalize(world_rays, p=2, dim=-1)
        
        view_dirs = -world_rays.reshape(self.H, self.W, 3)  # [H, W, 3]
        
        # 计算 3D 点位置（世界坐标）
        norm = torch.norm(canonical_rays, p=2, dim=-1).reshape(self.H, self.W, 1)
        cam_pos_world = c2w[:3, 3]  # 相机位置
        points = (
            cam_pos_world + world_rays.reshape(-1, 3) * norm.reshape(-1, 1) * depth_map.reshape(-1, 1)
        ).contiguous().reshape(self.H, self.W, 3)  # [H, W, 3] 世界坐标
        
        # 确保光源位置在世界坐标系中（不随相机变化）
        light_pos_world = self.light_position.cuda()
        
        # ✅ 1. 计算直接光照（Direct Lighting）
        if use_shadow:
            if self.quality_mode == "high_quality":
                # 高质量模式：使用基于深度贴图的阴影
                shadow_map = self._calculate_high_quality_shadows(
                    light_pos=light_pos_world,
                    points=points,
                    normal_map=normal_map.permute(1, 2, 0),
                    depth_map=depth_map.permute(1, 2, 0)
                )
                
                # 应用阴影到PBR着色
                direct_result = self._light_pbr_shading_with_shadow_map(
                    light_position=light_pos_world,
                    light_intensity=self.light_intensity,
                    points=points,
                    normals=normal_map.permute(1, 2, 0),
                    view_dirs=view_dirs,
                    mask=normal_mask.permute(1, 2, 0),
                    albedo=albedo_map.permute(1, 2, 0),
                    roughness=roughness_map.permute(1, 2, 0),
                    metallic=metallic_map.permute(1, 2, 0),
                    shadow_map=shadow_map,
                    linear=False,
                )
            else:
                # 标准模式：使用带距离衰减的PBR阴影（无遮挡检测）
                direct_result = self._light_pbr_shading(
                    light_position=light_pos_world,
                    light_intensity=self.light_intensity,
                    points=points,
                    normals=normal_map.permute(1, 2, 0),
                    view_dirs=view_dirs,
                    mask=normal_mask.permute(1, 2, 0),
                    albedo=albedo_map.permute(1, 2, 0),
                    roughness=roughness_map.permute(1, 2, 0),
                    metallic=metallic_map.permute(1, 2, 0),
                    linear=False,
                )
        else:
            # 禁用阴影：使用均匀光照
            direct_result = self._light_pbr_shading_no_shadow(
                light_position=light_pos_world,
                light_intensity=self.light_intensity,
                points=points,
                normals=normal_map.permute(1, 2, 0),
                view_dirs=view_dirs,
                mask=normal_mask.permute(1, 2, 0),
                albedo=albedo_map.permute(1, 2, 0),
                roughness=roughness_map.permute(1, 2, 0),
                metallic=metallic_map.permute(1, 2, 0),
                linear=False,
            )
        
        render_rgb = direct_result["render_rgb"]  # [H, W, 3]
        
        # ✅ 2. 计算间接光照（Indirect Lighting）
        if use_indirect:
            indirect_lighting = self._compute_indirect_lighting(
                points=points,
                normals=normal_map.permute(1, 2, 0),
                view_dirs=view_dirs,
                albedo=albedo_map.permute(1, 2, 0),
                roughness=roughness_map.permute(1, 2, 0),
                metallic=metallic_map.permute(1, 2, 0),
                mask=normal_mask.permute(1, 2, 0),
            )
            
            # 混合直接光照和间接光照
            render_rgb = render_rgb + indirect_lighting
            render_rgb = torch.clamp(render_rgb, 0.0, 1.0)
        
        return render_rgb.permute(2, 0, 1)  # [3, H, W]
    
    def _get_canonical_rays(self) -> torch.Tensor:
        """获取标准光线"""
        import numpy as np
        import torch.nn.functional as F
        
        tan_fovx = np.tan(self.ref_view.FoVx * 0.5)
        tan_fovy = np.tan(self.ref_view.FoVy * 0.5)
        
        cen_x = self.W / 2
        cen_y = self.H / 2
        focal_x = self.W / (2.0 * tan_fovx)
        focal_y = self.H / (2.0 * tan_fovy)
        
        x, y = torch.meshgrid(
            torch.arange(self.W, dtype=torch.float32, device='cuda'),
            torch.arange(self.H, dtype=torch.float32, device='cuda'),
            indexing="xy",
        )
        x = x.flatten()  # [H * W]
        y = y.flatten()  # [H * W]
        camera_dirs = F.pad(
            torch.stack(
                [
                    (x - cen_x + 0.5) / focal_x,
                    (y - cen_y + 0.5) / focal_y,
                ],
                dim=-1,
            ),
            (0, 1),
            value=1.0,
        )  # [H * W, 3]
        
        return camera_dirs
    
    def _saturate_dot(self, a: torch.Tensor, b: torch.Tensor) -> torch.Tensor:
        """饱和点积"""
        return (a * b).sum(dim=-1, keepdim=True).clamp(min=0.0, max=1.0)
    
    def _distribution_ggx(self, normals: torch.Tensor, half_dirs: torch.Tensor, roughness: torch.Tensor) -> torch.Tensor:
        """GGX 法线分布函数"""
        a = roughness * roughness
        a2 = a * a
        NoH = self._saturate_dot(normals, half_dirs)
        NoH2 = NoH * NoH
        
        nom = a2
        denom = (NoH2 * (a2 - 1.0) + 1.0)
        denom = np.pi * denom * denom
        
        return nom / denom
    
    def _geometry_schlick_ggx(self, NoV: torch.Tensor, roughness: torch.Tensor) -> torch.Tensor:
        """Schlick-GGX 几何函数"""
        r = roughness + 1.0
        k = (r * r) / 8.0
        nom = NoV
        denom = NoV * (1.0 - k) + k
        
        return nom / denom
    
    def _geometry_smith(self, normals: torch.Tensor, view_dirs: torch.Tensor, light_dirs: torch.Tensor, roughness: torch.Tensor) -> torch.Tensor:
        """Smith 几何函数"""
        NoV = self._saturate_dot(normals, view_dirs)
        NoL = self._saturate_dot(normals, light_dirs)
        ggx2 = self._geometry_schlick_ggx(NoV, roughness)
        ggx1 = self._geometry_schlick_ggx(NoL, roughness)
        
        return ggx1 * ggx2
    
    def _fresnel_schlick(self, HoV: torch.Tensor, F0: torch.Tensor) -> torch.Tensor:
        """Fresnel-Schlick 函数"""
        return F0 + (1.0 - F0) * torch.pow((1.0 - HoV).clamp(0.0, 1.0), 5)
    
    def _light_pbr_shading(
        self,
        light_position: torch.Tensor,
        light_intensity: torch.Tensor,
        points: torch.Tensor,
        normals: torch.Tensor,
        view_dirs: torch.Tensor,
        albedo: torch.Tensor,
        roughness: torch.Tensor,
        mask: torch.Tensor,
        metallic: Optional[torch.Tensor] = None,
        linear: bool = False,
    ) -> Dict:
        """PBR 着色函数（标准模式：带距离衰减，无遮挡检测）"""
        import torch.nn.functional as F
        
        # 准备向量
        light_dirs = F.normalize(light_position - points, p=2, dim=-1)  # [H, W, 3]
        half_dirs = (light_dirs + view_dirs) / 2.0  # [H, W, 3]
        distance = torch.norm(light_position - points, p=2, dim=-1, keepdim=True)  # [H, W, 1]
        
        # ✅ 标准模式：使用距离衰减模拟基本光照变化
        attenuation = 1.0 / torch.pow(distance, 2)  # [H, W, 1]
        radiance = light_intensity * attenuation  # [H, W, 3]
        
        if metallic is None:
            F0 = torch.ones_like(albedo) * 0.04  # [H, W, 3]
        else:
            F0 = (1.0 - metallic) * 0.04 + albedo * metallic  # [H, W, 3]
        
        # Cook-Torrance BRDF
        NoV = self._saturate_dot(normals, view_dirs)  # [H, W, 1]
        NoL = self._saturate_dot(normals, light_dirs)  # [H, W, 1]
        HoV = self._saturate_dot(half_dirs, view_dirs)  # [H, W, 1]
        NDF = self._distribution_ggx(normals=normals, half_dirs=half_dirs, roughness=roughness)  # [H, W, 1]
        G = self._geometry_smith(normals=normals, view_dirs=view_dirs, light_dirs=light_dirs, roughness=roughness)  # [H, W, 1]
        fresnel = self._fresnel_schlick(HoV=HoV, F0=F0)  # [H, W, 3]
        
        numerator = NDF * G * fresnel  # [H, W, 3]
        denominator = 4.0 * NoV * NoL + 1e-4  # [H, W, 1]
        specular = numerator / denominator  # [H, W, 3]
        
        kd = 1.0 - fresnel  # [H, W, 3]
        if metallic is not None:
            kd *= (1.0 - metallic)
        
        render_rgb = (kd * albedo / np.pi + specular) * radiance * NoL
        
        background = torch.zeros_like(normals)
        render_rgb = torch.where(mask, render_rgb, background)
        
        return {"render_rgb": render_rgb}
    
    def _light_pbr_shading_with_shadow_map(
        self,
        light_position: torch.Tensor,
        light_intensity: torch.Tensor,
        points: torch.Tensor,
        normals: torch.Tensor,
        view_dirs: torch.Tensor,
        albedo: torch.Tensor,
        roughness: torch.Tensor,
        mask: torch.Tensor,
        shadow_map: torch.Tensor,
        metallic: Optional[torch.Tensor] = None,
        linear: bool = False,
    ) -> Dict:
        """PBR 着色函数（使用阴影贴图）"""
        import torch.nn.functional as F
        
        # 准备向量
        light_dirs = F.normalize(light_position - points, p=2, dim=-1)  # [H, W, 3]
        half_dirs = (light_dirs + view_dirs) / 2.0  # [H, W, 3]
        distance = torch.norm(light_position - points, p=2, dim=-1, keepdim=True)  # [H, W, 1]
        attenuation = 1.0 / torch.pow(distance, 2)  # [H, W, 1]
        radiance = light_intensity * attenuation  # [H, W, 3]
        
        if metallic is None:
            F0 = torch.ones_like(albedo) * 0.04  # [H, W, 3]
        else:
            F0 = (1.0 - metallic) * 0.04 + albedo * metallic  # [H, W, 3]
        
        # Cook-Torrance BRDF
        NoV = self._saturate_dot(normals, view_dirs)  # [H, W, 1]
        NoL = self._saturate_dot(normals, light_dirs)  # [H, W, 1]
        HoV = self._saturate_dot(half_dirs, view_dirs)  # [H, W, 1]
        NDF = self._distribution_ggx(normals=normals, half_dirs=half_dirs, roughness=roughness)  # [H, W, 1]
        G = self._geometry_smith(normals=normals, view_dirs=view_dirs, light_dirs=light_dirs, roughness=roughness)  # [H, W, 1]
        fresnel = self._fresnel_schlick(HoV=HoV, F0=F0)  # [H, W, 3]
        
        numerator = NDF * G * fresnel  # [H, W, 3]
        denominator = 4.0 * NoV * NoL + 1e-4  # [H, W, 1]
        specular = numerator / denominator  # [H, W, 3]
        
        kd = 1.0 - fresnel  # [H, W, 3]
        if metallic is not None:
            kd *= (1.0 - metallic)
        
        # ✅ 与 light_move.py 一致的阴影应用方式
        render_rgb = (kd * albedo / np.pi + specular) * radiance * NoL
        
        # ✅ 应用软阴影：使用 shadow_map 作为遮罩因子
        # shadow_map=0 (受光) → 100% 亮度
        # shadow_map=1 (完全阴影) → 20% 亮度
        # shadow_map=0.5 (半影) → 60% 亮度
        shadow_factor = 1.0 - shadow_map * 0.8  # 阴影区域保留 20% 环境光
        render_rgb = render_rgb * shadow_factor
        
        background = torch.zeros_like(normals)
        render_rgb = torch.where(mask, render_rgb, background)
        
        return {"render_rgb": render_rgb}
    
    def _light_pbr_shading_no_shadow(
        self,
        light_position: torch.Tensor,
        light_intensity: torch.Tensor,
        points: torch.Tensor,
        normals: torch.Tensor,
        view_dirs: torch.Tensor,
        albedo: torch.Tensor,
        roughness: torch.Tensor,
        mask: torch.Tensor,
        metallic: Optional[torch.Tensor] = None,
        linear: bool = False,
    ) -> Dict:
        """PBR 着色函数（禁用阴影 - 移除距离衰减）"""
        import torch.nn.functional as F
        
        # 准备向量
        light_dirs = F.normalize(light_position - points, p=2, dim=-1)  # [H, W, 3]
        half_dirs = (light_dirs + view_dirs) / 2.0  # [H, W, 3]
        
        # ✅ 禁用阴影：不使用距离衰减，所有点接收相同光照强度
        radiance = light_intensity.expand_as(points)  # [H, W, 3] 均匀光照
        
        if metallic is None:
            F0 = torch.ones_like(albedo) * 0.04  # [H, W, 3]
        else:
            F0 = (1.0 - metallic) * 0.04 + albedo * metallic  # [H, W, 3]
        
        # Cook-Torrance BRDF
        NoV = self._saturate_dot(normals, view_dirs)  # [H, W, 1]
        NoL = self._saturate_dot(normals, light_dirs)  # [H, W, 1]
        HoV = self._saturate_dot(half_dirs, view_dirs)  # [H, W, 1]
        NDF = self._distribution_ggx(normals=normals, half_dirs=half_dirs, roughness=roughness)  # [H, W, 1]
        G = self._geometry_smith(normals=normals, view_dirs=view_dirs, light_dirs=light_dirs, roughness=roughness)  # [H, W, 1]
        fresnel = self._fresnel_schlick(HoV=HoV, F0=F0)  # [H, W, 3]
        
        numerator = NDF * G * fresnel  # [H, W, 3]
        denominator = 4.0 * NoV * NoL + 1e-4  # [H, W, 1]
        specular = numerator / denominator  # [H, W, 3]
        
        kd = 1.0 - fresnel  # [H, W, 3]
        if metallic is not None:
            kd *= (1.0 - metallic)
        
        render_rgb = (kd * albedo / np.pi + specular) * radiance * NoL
        
        background = torch.zeros_like(normals)
        render_rgb = torch.where(mask, render_rgb, background)
        
        return {"render_rgb": render_rgb}
    
    def _generate_depth_cubemap(self, light_pos: torch.Tensor, resolution: int = None) -> torch.Tensor:
        """生成光源视角的深度立方体贴图（模仿 light_move.py 的实现）"""
        if resolution is None:
            resolution = self.cubemap_resolution
        
        import torch.nn.functional as F
        
        # 获取规范光线（用于深度归一化）
        canonical_rays = self._get_canonical_rays_cubemap(resolution)
        norm = torch.norm(canonical_rays, p=2, dim=-1).reshape(resolution, resolution, 1)
        
        bg_color = torch.zeros([3, resolution, resolution], device="cuda")
        
        # 6个方向的旋转矩阵（与 light_move.py 保持一致）
        rotations = [
            torch.tensor([
                [0.0, 0.0, 1.0, 0.0],
                [0.0, -1.0, 0.0, 0.0],
                [-1.0, 0.0, 0.0, 0.0],
                [0.0, 0.0, 0.0, 1.0],
            ]).cuda(),  # +X: lookAt([0,0,0], [-1,0,0], [0,-1,0])
            torch.tensor([
                [0.0, 0.0, -1.0, 0.0],
                [0.0, -1.0, 0.0, 0.0],
                [1.0, 0.0, 0.0, 0.0],
                [0.0, 0.0, 0.0, 1.0],
            ]).cuda(),  # -X: lookAt([0,0,0], [1,0,0], [0,-1,0])
            torch.tensor([
                [1.0, 0.0, 0.0, 0.0],
                [0.0, 0.0, 1.0, 0.0],
                [0.0, 1.0, 0.0, 0.0],
                [0.0, 0.0, 0.0, 1.0],
            ]).cuda(),  # +Y: lookAt([0,0,0], [0,-1,0], [0,0,-1])
            torch.tensor([
                [1.0, 0.0, 0.0, 0.0],
                [0.0, 0.0, -1.0, 0.0],
                [0.0, -1.0, 0.0, 0.0],
                [0.0, 0.0, 0.0, 1.0],
            ]).cuda(),  # -Y: lookAt([0,0,0], [0,1,0], [0,0,1])
            torch.tensor([
                [1.0, 0.0, 0.0, 0.0],
                [0.0, -1.0, 0.0, 0.0],
                [0.0, 0.0, 1.0, 0.0],
                [0.0, 0.0, 0.0, 1.0],
            ]).cuda(),  # +Z: lookAt([0,0,0], [0,0,-1], [0,1,0])
            torch.tensor([
                [-1.0, 0.0, 0.0, 0.0],
                [0.0, -1.0, 0.0, 0.0],
                [0.0, 0.0, -1.0, 0.0],
                [0.0, 0.0, 0.0, 1.0],
            ]).cuda(),  # -Z: lookAt([0,0,0], [0,0,1], [0,-1,0])
        ]
        
        zfar = 100.0
        znear = 0.01
        projection_matrix = (
            getProjectionMatrix(znear=znear, zfar=zfar, fovX=np.pi * 0.5, fovY=np.pi * 0.5)
            .transpose(0, 1)
            .cuda()
        )
        
        depth_cubemap = []
        
        # 准备高斯数据（只计算一次）
        xyz = self.gaussians.get_xyz.detach().cuda()
        opacity = self.gaussians.get_opacity.detach().cuda()
        scaling = self.gaussians.get_scaling.detach().cuda()
        rotation_gs = self.gaussians.get_rotation.detach().cuda()
        features = self.gaussians.get_features.detach().cuda()
        if len(features.shape) >= 2:
            features = features[:, 0]
        if len(features.shape) == 1:
            features = features.unsqueeze(-1).repeat(1, 3)
        
        empty_tensor = torch.Tensor([]).cuda()
        
        for r_idx, rot_matrix in enumerate(rotations):
            c2w = rot_matrix.clone()
            c2w[:3, 3] = light_pos
            w2c = torch.inverse(c2w)
            T = w2c[:3, 3]
            R = w2c[:3, :3].T
            world_view_transform = self._getWorld2ViewTorch(R, T).transpose(0, 1)
            full_proj_transform = (
                world_view_transform.unsqueeze(0).bmm(projection_matrix.unsqueeze(0))
            ).squeeze(0)
            camera_center = world_view_transform.inverse()[3, :3]
            
            # 构造渲染参数
            input_args = (
                bg_color,
                xyz,
                empty_tensor,
                opacity,
                scaling,
                rotation_gs,
                empty_tensor,
                features,
                camera_center,
                world_view_transform,
                full_proj_transform,
                1.0,   # scale_modifier
                1.0,   # tanfovx
                1.0,   # tanfovy
                resolution,  # image_height
                resolution,  # image_width
                self.gaussians.active_sh_degree,
                False,  # prefiltered
                False,  # argmax_depth
            )
            
            # 调用底层 CUDA 渲染函数
            (num_rendered, rendered_image, opacity_map, radii, depth_map) = _C.lite_rasterize_gaussians(*input_args)
            depth_cubemap.append(depth_map.permute(1, 2, 0))  # [H, W, 1]
        
        return torch.stack(depth_cubemap)  # [6, H, W, 1]
    
    def _calculate_high_quality_shadows(self, 
                                      light_pos: torch.Tensor, 
                                      points: torch.Tensor, 
                                      normal_map: torch.Tensor,
                                      depth_map: torch.Tensor) -> torch.Tensor:
        """基于深度立方体贴图计算高质量阴影（模仿 light_move.py）"""
        import torch.nn.functional as F
        
        H, W = points.shape[:2]
        
        # ✅ 检查是否被禁用
        if self.high_quality_disabled or self.cubemap_resolution == 0:
            print("[警告] 高质量阴影已被禁用（显存不足），返回无阴影")
            return torch.zeros((H, W, 1), device=light_pos.device)
        
        # 检查是否需要重新生成立方体贴图
        if (self.depth_cubemap_cache is None or 
            self.last_light_position is None or
            not torch.allclose(self.last_light_position, light_pos, atol=0.01)):
            
            print(f"[RealtimeViewer] 正在生成立方体贴图（分辨率: {self.cubemap_resolution}）...")
            self.depth_cubemap_cache = self._generate_depth_cubemap(light_pos, self.cubemap_resolution)
            self.last_light_position = light_pos.clone()
            print("[RealtimeViewer] 立方体贴图生成完成")
        
        depth_cubemap = self.depth_cubemap_cache
        
        # 计算从点到光源的方向和距离
        to_light = (light_pos[None, None, :] - points).reshape(H, W, 3)  # [H, W, 3]
        distance_to_light = torch.norm(to_light, p=2, dim=-1, keepdim=True)  # [H, W, 1]
        query_dirs = F.normalize(-to_light, p=2, dim=-1)  # [H, W, 3] 指向光源的方向
        
        # 使用 nvdiffrast 进行立方体贴图采样（如果可用）
        try:
            import nvdiffrast.torch as dr
            closest_depth = dr.texture(
                depth_cubemap[None, ...],  # [1, 6, H, W, 1]
                query_dirs[None, ...].contiguous(),  # [1, H, W, 3]
                filter_mode="linear",
                boundary_mode="cube",
            )[0]  # [H, W, 1]
            
            # ✅ 关键修复：将深度转换为欧氏距离
            # 立方体贴图中的深度是沿光线方向的距离，需要乘以光线长度的归一化因子
            # 对于 fov=90° 的立方体贴图，规范光线的长度在不同位置不同
            # 我们需要将采样的深度值转换为真实的欧氏距离
            
            # 计算采样方向的规范光线长度
            # 对于立方体贴图，每个像素对应一个方向向量
            # 深度值表示沿该方向的距离，所以欧氏距离 = 深度 * |direction|
            # 但由于我们使用的是归一化的 query_dirs，|direction| = 1
            # 所以 closest_depth 应该已经是欧氏距离了
            
            # ✅ 但实际上，_C.lite_rasterize_gaussians 返回的可能是 Z 深度
            # 需要将其转换为欧氏距离：euclidean_distance = z_depth / cos(theta)
            # 其中 theta 是光线与相机前向轴的夹角
            
            # 简化方案：直接使用 norm 因子进行转换
            # 获取当前面的规范光线长度
            resolution = depth_cubemap.shape[1]
            canonical_rays = self._get_canonical_rays_cubemap(resolution)  # [H*W, 3]
            ray_lengths = torch.norm(canonical_rays, p=2, dim=-1).reshape(resolution, resolution, 1)  # [H, W, 1]
            
            # 但问题是，我们不知道采样的是哪个面...
            # 更简单的方法：直接使用 distance_to_light 作为参考，调整阈值
            
        except ImportError:
            # 如果没有 nvdiffrast，使用简化的最近邻采样
            print("[警告] nvdiffrast 不可用，使用简化阴影计算")
            closest_depth = self._simple_cubemap_sampling(depth_cubemap, query_dirs)
        
        # 使用阈值判断阴影（与 light_move.py 一致）
        threshold = self.shadow_threshold
        
        # ✅ 关键修复：需要同时考虑 closest_depth 是否为有效值
        # 如果 closest_depth 接近 0，说明这个方向没有物体，不应该有阴影
        min_depth = 0.1  # 最小有效深度
        valid_occlusion = (closest_depth > min_depth) & (distance_to_light - threshold > closest_depth)
        shadow_raw = valid_occlusion.float()
        
        # ✅ 应用简单的 box filter 平滑阴影（减少噪点）
        if shadow_raw.shape[0] >= 3 and shadow_raw.shape[1] >= 3:
            import torch.nn.functional as F
            shadow_padded = F.pad(shadow_raw.permute(2, 0, 1).unsqueeze(0), (1, 1, 1, 1), mode='reflect')
            kernel = torch.ones(1, 1, 3, 3, device=shadow_raw.device) / 9.0
            shadow_smooth = F.conv2d(shadow_padded, kernel).squeeze(0).permute(1, 2, 0)
            shadow = shadow_smooth
        else:
            shadow = shadow_raw
        
        return shadow
    
    def _getWorld2ViewTorch(self, R: torch.Tensor, t: torch.Tensor) -> torch.Tensor:
        """构建世界到相机变换矩阵（与 light_move.py 一致）"""
        Rt = torch.zeros((4, 4), device=R.device)
        Rt[:3, :3] = R[:3, :3].T
        Rt[:3, 3] = t
        Rt[3, 3] = 1.0
        return Rt
    
    def _get_canonical_rays_cubemap(self, resolution: int) -> torch.Tensor:
        """获取立方体贴图的规范光线"""
        import torch.nn.functional as F
        
        cen_x = resolution / 2
        cen_y = resolution / 2
        focal_x = resolution / 2.0  # tan_fovx = 1.0
        focal_y = resolution / 2.0  # tan_fovy = 1.0
        
        x, y = torch.meshgrid(
            torch.arange(resolution, dtype=torch.float32, device='cuda'),
            torch.arange(resolution, dtype=torch.float32, device='cuda'),
            indexing="xy",
        )
        x = x.flatten()
        y = y.flatten()
        camera_dirs = F.pad(
            torch.stack(
                [
                    (x - cen_x + 0.5) / focal_x,
                    (y - cen_y + 0.5) / focal_y,
                ],
                dim=-1,
            ),
            (0, 1),
            value=1.0,
        )
        return camera_dirs
    
    def _simple_cubemap_sampling(self, depth_cubemap: torch.Tensor, query_dirs: torch.Tensor) -> torch.Tensor:
        """简化的立方体贴图采样（当 nvdiffrast 不可用时）"""
        import torch.nn.functional as F
        
        H, W = query_dirs.shape[:2]
        res = depth_cubemap.shape[1]  # 立方体贴图分辨率
        
        # 将方向向量转换为立方体面索引和 UV 坐标
        dirs = query_dirs.reshape(-1, 3)  # [HW, 3]
        abs_dirs = torch.abs(dirs)
        
        # 确定主轴线
        max_axis = torch.argmax(abs_dirs, dim=1)  # [HW]
        signs = torch.sign(dirs)
        
        # 计算面索引 (0:+X, 1:-X, 2:+Y, 3:-Y, 4:+Z, 5:-Z)
        face_indices = torch.where(max_axis == 0, 
                                   torch.where(signs[:, 0] > 0, 0, 1),
                                   torch.where(max_axis == 1,
                                              torch.where(signs[:, 1] > 0, 2, 3),
                                              torch.where(signs[:, 2] > 0, 4, 5)))
        
        # 计算 UV 坐标
        st = torch.zeros_like(dirs)
        for i in range(6):
            mask = face_indices == i
            if not mask.any():
                continue
            
            if i == 0:  # +X
                st[mask] = torch.stack([-dirs[mask, 2], -dirs[mask, 1]], dim=1) / abs_dirs[mask, 0:1]
            elif i == 1:  # -X
                st[mask] = torch.stack([dirs[mask, 2], -dirs[mask, 1]], dim=1) / abs_dirs[mask, 0:1]
            elif i == 2:  # +Y
                st[mask] = torch.stack([dirs[mask, 0], dirs[mask, 2]], dim=1) / abs_dirs[mask, 1:2]
            elif i == 3:  # -Y
                st[mask] = torch.stack([dirs[mask, 0], -dirs[mask, 2]], dim=1) / abs_dirs[mask, 1:2]
            elif i == 4:  # +Z
                st[mask] = torch.stack([dirs[mask, 0], -dirs[mask, 1]], dim=1) / abs_dirs[mask, 2:3]
            elif i == 5:  # -Z
                st[mask] = torch.stack([-dirs[mask, 0], -dirs[mask, 1]], dim=1) / abs_dirs[mask, 2:3]
        
        # 转换到纹理坐标 [0, 1]
        uv = (st[:, :2] + 1.0) / 2.0  # [HW, 2]
        uv = uv.clamp(0.0, 1.0)
        
        # 采样每个面的深度图
        sampled_depths = torch.zeros(H * W, 1, device=depth_cubemap.device)
        for i in range(6):
            mask = face_indices == i
            if not mask.any():
                continue
            
            face_depth = depth_cubemap[i]  # [res, res, 1]
            face_uv = uv[mask]  # [N, 2]
            
            # 双线性插值采样
            u = face_uv[:, 0] * (res - 1)
            v = face_uv[:, 1] * (res - 1)
            
            u0 = torch.floor(u).long().clamp(0, res - 2)
            v0 = torch.floor(v).long().clamp(0, res - 2)
            u1 = u0 + 1
            v1 = v0 + 1
            
            fu = (u - u0.float()).unsqueeze(1)
            fv = (v - v0.float()).unsqueeze(1)
            
            d00 = face_depth[v0, u0]
            d01 = face_depth[v0, u1]
            d10 = face_depth[v1, u0]
            d11 = face_depth[v1, u1]
            
            d0 = d00 * (1 - fu) + d01 * fu
            d1 = d10 * (1 - fu) + d11 * fu
            sampled_depths[mask] = d0 * (1 - fv) + d1 * fv
        
        return sampled_depths.reshape(H, W, 1)
    
    def _compute_indirect_lighting(
        self,
        points: torch.Tensor,  # [H, W, 3]
        normals: torch.Tensor,  # [H, W, 3]
        view_dirs: torch.Tensor,  # [H, W, 3]
        albedo: torch.Tensor,  # [H, W, 3]
        roughness: torch.Tensor,  # [H, W, 1]
        metallic: torch.Tensor,  # [H, W, 1]
        mask: torch.Tensor,  # [H, W, 1]
    ) -> torch.Tensor:
        """计算间接光照（环境光遮蔽 + 漫反射）"""
        import numpy as np
        
        # ✅ 简化版间接光照模型：
        # 1. 使用环境光遮蔽（AO）模拟全局阴影
        # 2. 使用固定环境光颜色模拟天空光
        
        # 环境光参数
        ambient_intensity = torch.tensor([0.1, 0.1, 0.15], dtype=torch.float32).cuda()  # 偏冷的环境光
        sky_intensity = torch.tensor([0.05, 0.06, 0.08], dtype=torch.float32).cuda()  # 天空光
        
        # 计算法线与天顶方向的点积（模拟天空光角度衰减）
        up_vector = torch.tensor([0.0, 1.0, 0.0], dtype=torch.float32).cuda()
        NoUp = (normals * up_vector).sum(dim=-1, keepdim=True).clamp(0.0, 1.0)  # [H, W, 1]
        
        # 基础环境光
        indirect_diffuse = ambient_intensity.expand_as(albedo)
        
        # 添加天空光贡献（法线朝上的表面接收更多天空光）
        indirect_diffuse = indirect_diffuse + sky_intensity * NoUp
        
        # ✅ 粗糙度影响：粗糙表面散射更多环境光
        roughness_factor = 1.0 - roughness * 0.5  # 光滑表面反射更强，漫反射更弱
        
        # ✅ Metallic 影响：金属表面几乎没有漫反射间接光
        kd = (1.0 - metallic) * roughness_factor
        
        # 最终间接漫反射
        indirect_diffuse = indirect_diffuse * kd * albedo / np.pi
        
        # ✅ 简单 AO 近似：基于深度变化率
        # 深度梯度大的地方（边缘）AO 更强
        depth_z = points[..., 2:3]  # [H, W, 1]
        depth_dx = torch.abs(torch.gradient(depth_z, dim=1)[0])  # [H, W, 1]
        depth_dy = torch.abs(torch.gradient(depth_z, dim=0)[0])  # [H, W, 1]
        depth_gradient = depth_dx + depth_dy
        ao_factor = 1.0 / (1.0 + depth_gradient * 0.5)  # 梯度越大，AO 越强
        ao_factor = ao_factor.clamp(0.3, 1.0)  # 限制范围
        
        indirect_diffuse = indirect_diffuse * ao_factor
        
        # 应用遮罩
        background = torch.zeros_like(indirect_diffuse)
        indirect_diffuse = torch.where(mask, indirect_diffuse, background)
        
        return indirect_diffuse
    
    # ========== 事件处理方法 ==========
    
    def _load_user_config(self) -> Optional[Dict]:
        """加载用户配置文件"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                print(f"[RealtimeViewer] [OK] 已加载配置文件：{self.config_file}")
                return config
            else:
                print(f"[RealtimeViewer] [INFO] 配置文件不存在，使用默认设置")
                return None
        except Exception as e:
            print(f"[RealtimeViewer] [WARN] 加载配置失败：{e}")
            return None
    
    def _save_user_config(self):
        """保存用户配置文件"""
        try:
            # 确保目录存在
            os.makedirs(self.config_dir, exist_ok=True)
            
            # 收集当前配置
            config = {
                'light_position': {
                    'x': float(self.light_x_var.get()),
                    'y': float(self.light_y_var.get()),
                    'z': float(self.light_z_var.get())
                },
                'light_intensity': {
                    'r': float(self.light_r_var.get()),
                    'g': float(self.light_g_var.get()),
                    'b': float(self.light_b_var.get()),
                    'master': float(self.light_master_var.get())
                },
                'render_mode': self.render_mode_var.get(),
                'pbr_settings': {
                    'metallic': self.metallic_var.get(),
                    'indirect': self.indirect_var.get(),
                    'shadow': self.shadow_var.get()
                },
                'camera': {
                    'distance': float(self.distance),
                    'yaw': float(self.yaw),
                    'pitch': float(self.pitch),
                    'center_x': float(self.camera_center[0].item()),
                    'center_y': float(self.camera_center[1].item()),
                    'center_z': float(self.camera_center[2].item())
                }
            }
            
            # 保存到文件
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            
            print(f"[RealtimeViewer] [OK] 配置已保存：{self.config_file}")
            messagebox.showinfo("成功", f"配置已保存至:\n{self.config_file}")
        except Exception as e:
            print(f"[RealtimeViewer] [ERROR] 保存配置失败：{e}")
            messagebox.showerror("错误", f"保存配置失败:\n{str(e)}")
    
    def _apply_user_config(self):
        """应用用户配置"""
        try:
            # 光源位置
            if 'light_position' in self.user_config:
                light_pos = self.user_config['light_position']
                self.light_x_var.set(light_pos.get('x', 0.0))
                self.light_y_var.set(light_pos.get('y', 0.0))
                self.light_z_var.set(light_pos.get('z', 5.0))
                self._update_light_position()
            
            # 光照强度
            if 'light_intensity' in self.user_config:
                light_intensity = self.user_config['light_intensity']
                self.light_r_var.set(light_intensity.get('r', 100.0))
                self.light_g_var.set(light_intensity.get('g', 100.0))
                self.light_b_var.set(light_intensity.get('b', 100.0))
                self.light_master_var.set(light_intensity.get('master', 100.0))
                self._update_light_intensity()
            
            # 渲染模式
            if 'render_mode' in self.user_config:
                self.render_mode_var.set(self.user_config['render_mode'])
                self._toggle_render_mode()
            
            # PBR 设置
            if 'pbr_settings' in self.user_config:
                pbr = self.user_config['pbr_settings']
                self.metallic_var.set(pbr.get('metallic', False))
                self.indirect_var.set(pbr.get('indirect', False))
                self.shadow_var.set(pbr.get('shadow', True))
                self._update_pbr_settings()
            
            # 相机视角
            if 'camera' in self.user_config:
                camera = self.user_config['camera']
                self.distance = float(camera.get('distance', 5.0))
                self.yaw = float(camera.get('yaw', 0.0))
                self.pitch = float(camera.get('pitch', 0.0))
                self.camera_center = torch.tensor([
                    float(camera.get('center_x', 0.0)),
                    float(camera.get('center_y', 0.0)),
                    float(camera.get('center_z', 0.0))
                ], dtype=torch.float32)
            
            print("[RealtimeViewer] [OK] 用户配置已应用")
        except Exception as e:
            print(f"[RealtimeViewer] [WARN] 应用配置失败：{e}")
    def _reset_view(self):
        """重置视角"""
        self.camera_center = torch.zeros(3)
        self.yaw = 0.0
        self.pitch = 0.0
        self.distance = 5.0
        print("[RealtimeViewer] 视角已重置")
    
    def _toggle_auto_rotate(self):
        """切换自动旋转"""
        self.auto_rotate = not self.auto_rotate
        print(f"[RealtimeViewer] 自动旋转：{'开启' if self.auto_rotate else '关闭'}")
    
    def _prev_view(self):
        """切换到上一个相机视角"""
        if len(self.views) > 1:
            current_idx = self.views.index(self.ref_view)
            new_idx = (current_idx - 1) % len(self.views)
            self.ref_view = self.views[new_idx]
            print(f"[RealtimeViewer] 切换到视角 {new_idx}")
    
    def _next_view(self):
        """切换到下一个相机视角"""
        if len(self.views) > 1:
            current_idx = self.views.index(self.ref_view)
            new_idx = (current_idx + 1) % len(self.views)
            self.ref_view = self.views[new_idx]
            print(f"[RealtimeViewer] 切换到视角 {new_idx}")
    
    def _toggle_pbr(self):
        """切换 PBR"""
        self.enable_pbr = not self.enable_pbr
        print(f"[RealtimeViewer] PBR: {'开启' if self.enable_pbr else '关闭'}")
    
    def _update_light_position(self, val=None):
        """更新光源位置"""
        self.light_position = torch.tensor([
            self.light_x_var.get(),
            self.light_y_var.get(),
            self.light_z_var.get()
        ], dtype=torch.float32)
        print(f"[RealtimeViewer] 光源位置：{self.light_position.cpu().numpy()}")
    
    def _update_light_intensity(self, val=None):
        """更新光照强度"""
        self.light_intensity = torch.tensor([
            self.light_r_var.get(),
            self.light_g_var.get(),
            self.light_b_var.get()
        ], dtype=torch.float32).cuda()
        
        # 检查RGB三个通道是否一致
        r_val = self.light_r_var.get()
        g_val = self.light_g_var.get()
        b_val = self.light_b_var.get()
        
        if abs(r_val - g_val) < 0.01 and abs(g_val - b_val) < 0.01 and abs(r_val - b_val) < 0.01:
            # RGB一致，启用整体强度控制并同步值
            self.light_master_var.set(r_val)
            self.master_scale.config(state='normal')
        else:
            # RGB不一致，禁用整体强度控制
            self.master_scale.config(state='disabled')
        
        print(f"[RealtimeViewer] 光照强度：{self.light_intensity.cpu().numpy()}")
    
    def _update_light_master_intensity(self, val=None):
        """更新整体光照强度（同步调整RGB三个通道）"""
        master_value = self.light_master_var.get()
        # 同步更新三个通道的值
        self.light_r_var.set(master_value)
        self.light_g_var.set(master_value)
        self.light_b_var.set(master_value)
        # 更新光照强度
        self.light_intensity = torch.tensor([master_value, master_value, master_value], dtype=torch.float32).cuda()
        print(f"[RealtimeViewer] 整体光照强度：{master_value}")
    
    def _toggle_render_mode(self):
        """切换渲染模式"""
        mode = self.render_mode_var.get()
        
        if mode == "normal":
            # 普通模式：不开启重光照
            self.enable_pbr = False
            self.quality_mode = "standard"
            print("[渲染模式] 普通模式（无PBR）")
            
        elif mode == "standard_relight":
            # 标准重光照：启用PBR，使用标准阴影（距离衰减）
            self.enable_pbr = True
            self.quality_mode = "standard"
            print("[渲染模式] 标准重光照（PBR + 标准阴影）")
            
        elif mode == "enhanced_relight":
            # 增强重光照：启用PBR，使用高质量阴影（深度立方体贴图）
            self.enable_pbr = True
            self.quality_mode = "high_quality"
            print("[渲染模式] 增强重光照（PBR + 高质量阴影）")
    
    def _update_pbr_settings(self):
        """更新 PBR 设置"""
        self.pbr_settings['metallic'] = self.metallic_var.get()
        self.pbr_settings['indirect'] = self.indirect_var.get()
        self.pbr_settings['shadow'] = self.shadow_var.get()
        
        # ✅ 如果任意 PBR 选项被勾选，自动切换到标准重光照模式
        if any([self.metallic_var.get(), self.indirect_var.get(), self.shadow_var.get()]):
            if not self.enable_pbr:
                self.enable_pbr = True
                self.quality_mode = "standard"
                self.render_mode_var.set("standard_relight")  # 同步更新渲染模式
                print(f"[RealtimeViewer] ✓ 自动启用标准重光照模式")
        else:
            # 如果所有选项都未勾选，可以关闭 PBR（可选）
            # self.enable_pbr = False
            # self.render_mode_var.set("normal")
            pass
        
        print(f"[RealtimeViewer] PBR 设置更新：{self.pbr_settings}")
    
    def _save_screenshot(self):
        """保存截图"""
        if self.current_frame is not None:
            from PIL import Image
            import datetime
            
            image = Image.fromarray(self.current_frame)
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"screenshot_{timestamp}.png"
            image.save(filename)
            messagebox.showinfo("成功", f"截图已保存：{filename}")
        else:
            messagebox.showwarning("警告", "暂无可保存的图像")
    
    # ========== 光源动画方法 ==========
    
    def _toggle_light_animation(self):
        """切换光源动画播放状态"""
        self.light_animation_playing = not self.light_animation_playing
        
        if self.light_animation_playing:
            self.play_button.config(text="⏸ 暂停")
            print("[光源动画] ▶ 开始播放")
            
            # 如果轨迹未生成，先生成
            if self.light_trajectory is None:
                self._generate_light_trajectory()
            
            # 启动动画更新
            self._update_light_animation()
        else:
            self.play_button.config(text="▶ 播放")
            print("[光源动画] ⏸ 暂停")
    
    def _generate_light_trajectory(self):
        """生成光源运动轨迹（模仿 light_move.py）"""
        try:
            from utils.camera_utils import trajectory_from_c2ws
            import numpy as np
            
            print("[光源动画] 正在生成轨迹...")
            
            # 获取相机视图作为参考
            views = self.scene.getTrainCameras()
            if len(views) == 0:
                print("[错误] 没有可用的相机视图")
                return
            
            # 使用所有训练相机生成轨迹
            c2ws = []
            for view in views:
                c2w = torch.inverse(view.world_view_transform.T).cpu().numpy()  # [4, 4]
                c2ws.append(c2w)
            
            # 插值生成平滑轨迹
            frames = self.light_animation_total_frames
            c2ws_inter = trajectory_from_c2ws(c2ws=c2ws, frames=frames)
            
            # 提取光源位置（c2w 的平移部分）
            self.light_trajectory = []
            
            # ✅ 计算场景中心，用于生成环绕光源轨迹
            all_positions = np.array([c2w[:3, 3] for c2w in c2ws_inter])
            scene_center = np.mean(all_positions, axis=0)  # [3]
            avg_distance = np.mean(np.linalg.norm(all_positions - scene_center, axis=1))  # 平均距离
            
            print(f"  场景中心: {scene_center}")
            print(f"  平均距离: {avg_distance:.2f}")
            
            for frame_idx, c2w in enumerate(c2ws_inter):
                # 基础位置：相机位置
                base_pos = c2w[:3, 3].copy()
                
                # ✅ 方案1：直接使用相机位置（与 light_move.py 一致）
                # light_pos = base_pos
                
                # ✅ 方案2：让光源围绕场景做圆周运动（Z轴固定为10）
                angle = (frame_idx / len(c2ws_inter)) * 2 * np.pi
                radius = avg_distance * 0.8  # 半径为平均距离的 80%
                light_pos = scene_center.copy()
                light_pos[0] += radius * np.cos(angle)  # X 轴圆周
                light_pos[1] += avg_distance * 0.3  # Y 轴稍微抬高
                light_pos[2] = 10.0  # ✅ Z 轴固定为 10
                
                self.light_trajectory.append(torch.from_numpy(light_pos).float())
            
            # ✅ 调试：输出前几帧的光源位置
            print(f"[光源动画] ✓ 轨迹生成完成：{len(self.light_trajectory)} 帧")
            if len(self.light_trajectory) > 0:
                first_pos = self.light_trajectory[0]
                mid_idx = len(self.light_trajectory) // 2
                mid_pos = self.light_trajectory[mid_idx]
                print(f"  第1帧位置: X={first_pos[0]:.2f}, Y={first_pos[1]:.2f}, Z={first_pos[2]:.2f}")
                print(f"  第{mid_idx}帧位置: X={mid_pos[0]:.2f}, Y={mid_pos[1]:.2f}, Z={mid_pos[2]:.2f}")
            
        except Exception as e:
            print(f"[错误] 轨迹生成失败：{e}")
            import traceback
            traceback.print_exc()
    
    def _update_light_animation(self):
        """更新光源动画（递归调用）"""
        if not self.light_animation_playing or self.light_trajectory is None:
            return
        
        # 获取当前帧的光源位置
        frame_idx = self.light_animation_frame % len(self.light_trajectory)
        light_pos = self.light_trajectory[frame_idx].cuda()
        
        # 更新光源位置变量
        self.light_position = light_pos
        self.light_x_var.set(light_pos[0].item())
        self.light_y_var.set(light_pos[1].item())
        self.light_z_var.set(light_pos[2].item())
        
        # 清除立方体贴图缓存（因为光源位置变了）
        self.depth_cubemap_cache = None
        self.last_light_position = None
        
        # 更新帧计数
        self.light_animation_frame += 1
        
        # 循环播放
        if self.light_animation_frame >= len(self.light_trajectory):
            self.light_animation_frame = 0
        
        # 定时更新（根据动画 FPS）
        interval_ms = int(1000.0 / self.light_animation_fps)
        self.root.after(interval_ms, self._update_light_animation)
    
    def _on_close(self):
        """关闭窗口"""
        self.rendering = False
        if self.render_thread:
            self.render_thread.join(timeout=2.0)
        
        # 删除就绪信号文件
        try:
            if os.path.exists(self.ready_signal_path):
                os.remove(self.ready_signal_path)
                print(f"[RealtimeViewer] ✓ 已清理信号文件：{self.ready_signal_path}")
        except Exception as e:
            print(f"[RealtimeViewer] 清理信号文件失败：{e}")
        
        self.root.quit()
        self.root.destroy()


def main():
    # 设置命令行参数解析器
    parser = ArgumentParser(description="实时高斯模型查看器 (GUI 版本)")
    model = ModelParams(parser, sentinel=True)
    pipeline = PipelineParams(parser)
    parser.add_argument("--checkpoint", type=str, default=None, help="Checkpoint 文件路径")
    parser.add_argument("--resolution_scale", type=float, default=1.0, help="分辨率缩放（0.5=半分辨率，2.0=双倍分辨率）")
    args = get_combined_args(parser)
    args.eval = False
    
    # 检查 checkpoint 是否存在
    if not os.path.exists(args.checkpoint):
        print(f"[错误] Checkpoint 文件不存在：{args.checkpoint}")
        sys.exit(1)
    
    model_path = os.path.dirname(args.checkpoint)
    print(f"[RealtimeViewer] 正在加载模型：{model_path}")
    
    # 创建 Tkinter 窗口
    root = tk.Tk()
    
    # 创建并运行查看器
    viewer = RealtimeViewerGUI(
        root=root,
        model_path=model_path,
        checkpoint=args.checkpoint,
        dataset=model.extract(args),
        pipeline=pipeline.extract(args),
        resolution_scale=args.resolution_scale,
    )
    
    # 启动主循环
    root.mainloop()


if __name__ == "__main__":
    main()
