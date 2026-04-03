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


class RealtimeViewerGUI:
    def __init__(self, root: tk.Tk, model_path: str, checkpoint: str, dataset: GroupParams, pipeline: GroupParams, resolution_scale: float = 1.0):
        self.root = root
        self.root.title("LuminaGS - Realtime Viewer")
        self.root.geometry("1400x900")
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
        print("[RealtimeViewer] 模型加载完成", flush=True)  # ⭐ 关键信号！
        
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
        
        self.light_intensity = torch.tensor([100.0, 100.0, 100.0], dtype=torch.float32).cuda()
        self.enable_pbr = False
        
        # PBR 设置
        self.pbr_settings = {
            'metallic': False,
            'indirect': False,
            'tone_mapping': False,
            'gamma_correction': False,
            'shadow': True,
        }
        
        # 视图控制
        self.show_wireframe = False
        self.show_light_gizmo = True
        self.auto_rotate = False
        
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
        
        # 加载用户配置
        print("[RealtimeViewer] 正在加载用户配置...", flush=True)
        self.user_config = self._load_user_config()
        
        # 构建 GUI
        self._build_gui()
        
        # 应用用户配置（如果有）
        if self.user_config:
            print("[RealtimeViewer] 应用保存的用户配置...", flush=True)
            self._apply_user_config()
        
        # 启动渲染循环
        self._start_render_loop()
    
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
        """创建右侧属性面板"""
        panel = ttk.Frame(parent, width=300)
        panel.pack_propagate(False)
        
        # 视图控制（从工具栏移过来）
        view_group = ttk.LabelFrame(panel, text="视图控制", padding="10")
        view_group.pack(fill=tk.X, pady=5)
        
        ttk.Button(view_group, text="重置视角", command=self._reset_view).pack(pady=5, padx=10, fill=tk.X)
        
        # 💾 配置保存功能
        config_group = ttk.LabelFrame(panel, text="配置管理", padding="10")
        config_group.pack(fill=tk.X, pady=10)
        
        ttk.Button(config_group, text="💾 保存当前配置", command=self._save_user_config, style='Accent.TButton').pack(pady=8, padx=10, fill=tk.X)
        ttk.Label(config_group, text="保存光源、渲染模式等设置", font=("Arial", 8), foreground="#666666").pack(anchor=tk.CENTER)
        
        # 渲染模式（从工具栏移过来）
        render_group = ttk.LabelFrame(panel, text="渲染模式", padding="10")
        render_group.pack(fill=tk.X, pady=5)
        
        self.render_mode_var = tk.StringVar(value="normal")
        ttk.Radiobutton(render_group, text="普通", variable=self.render_mode_var, value="normal",
                       command=self._toggle_render_mode).pack(anchor=tk.W, padx=10)
        ttk.Radiobutton(render_group, text="重光照", variable=self.render_mode_var, value="relight",
                       command=self._toggle_render_mode).pack(anchor=tk.W, padx=10)
        
        # 截图功能
        screenshot_group = ttk.Frame(panel, padding="10")
        screenshot_group.pack(fill=tk.X, pady=5)
        
        ttk.Button(screenshot_group, text="📸 保存截图", command=self._save_screenshot).pack(pady=5, padx=10, fill=tk.X)
        
        # 光源控制
        light_group = ttk.LabelFrame(panel, text="光源控制", padding="10")
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
        
        # PBR 设置
        pbr_group = ttk.LabelFrame(panel, text="PBR 设置", padding="10")
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
        stats_group = ttk.LabelFrame(panel, text="场景统计", padding="10")
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
        
        rendering_result = render(
            viewpoint_camera=viewpoint_camera,
            pc=self.gaussians,
            pipe=pipe,
            bg_color=torch.tensor([0.0, 0.0, 0.0], dtype=torch.float32).cuda(),
            inference=True,
            pad_normal=True,
            derive_normal=True,
        )
        
        # 根据渲染模式选择处理方式
        if self.enable_pbr:
            render_rgb = self._apply_pbr_relighting(rendering_result, c2w)
        else:
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
                from PIL import Image, ImageTk
                image = Image.fromarray(self.current_frame)
                image = image.resize((self.viewport_label.winfo_width(), 
                                     self.viewport_label.winfo_height()), 
                                    Image.Resampling.LANCZOS)
                photo = ImageTk.PhotoImage(image)
                self.viewport_label.configure(image=photo)
                self.viewport_label.image = photo  # 保持引用
                
                # 更新 FPS 信息
                self.fps_label.config(text=f"FPS: {self.fps:.1f}")
                
            except Exception as e:
                print(f"[显示错误] {e}")
    
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
        """应用 PBR 重光照"""
        import torch.nn.functional as F
        
        # 确保 c2w 在 CUDA 上
        c2w = c2w.cuda()
        
        # 提取 PBR 材质参数
        albedo_map = rendering_result["albedo_map"]  # [3, H, W]
        roughness_map = rendering_result["roughness_map"]  # [1, H, W]
        metallic_map = rendering_result["metallic_map"]  # [1, H, W]
        normal_map = rendering_result["normal_map"]  # [3, H, W]
        depth_map = rendering_result["depth_map"]  # [1, H, W]
        normal_mask = rendering_result["normal_mask"]  # [1, H, W]
        
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
        pbr_result = self._light_pbr_shading(
            light_position=light_pos_world,
            light_intensity=self.light_intensity,
            points=points,
            normals=normal_map.permute(1, 2, 0),
            view_dirs=view_dirs,
            mask=normal_mask.permute(1, 2, 0),
            albedo=albedo_map.permute(1, 2, 0),
            roughness=roughness_map.permute(1, 2, 0),  # [H, W, 1]
            metallic=metallic_map.permute(1, 2, 0),  # [H, W, 1]
            linear=False,
        )
        
        return pbr_result["render_rgb"].permute(2, 0, 1)  # [3, H, W]
    
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
        """PBR 着色函数（基于 Cook-Torrance BRDF）"""
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
        
        render_rgb = (kd * albedo / np.pi + specular) * radiance * NoL
        
        background = torch.zeros_like(normals)
        render_rgb = torch.where(mask, render_rgb, background)
        
        return {"render_rgb": render_rgb}
    
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
                'render_mode': self.render_mode_var.get(),
                'pbr_settings': {
                    'metallic': self.metallic_var.get(),
                    'indirect': self.indirect_var.get(),
                    'shadow': self.shadow_var.get()
                },
                'distance': float(self.distance),
                'yaw': float(self.yaw),
                'pitch': float(self.pitch)
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
            if 'distance' in self.user_config:
                self.distance = float(self.user_config['distance'])
            if 'yaw' in self.user_config:
                self.yaw = float(self.user_config['yaw'])
            if 'pitch' in self.user_config:
                self.pitch = float(self.user_config['pitch'])
            
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
    
    def _toggle_render_mode(self):
        """切换渲染模式"""
        mode = self.render_mode_var.get()
        if mode == "normal":
            self.enable_pbr = False
            print(f"[渲染模式] 普通渲染")
        elif mode == "relight":
            self.enable_pbr = True
            print(f"[渲染模式] 重光照渲染")
    
    def _update_pbr_settings(self):
        """更新 PBR 设置"""
        self.pbr_settings['metallic'] = self.metallic_var.get()
        self.pbr_settings['indirect'] = self.indirect_var.get()
        self.pbr_settings['shadow'] = self.shadow_var.get()
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
    
    
    def _on_close(self):
        """关闭窗口"""
        self.rendering = False
        if self.render_thread:
            self.render_thread.join(timeout=2.0)
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
