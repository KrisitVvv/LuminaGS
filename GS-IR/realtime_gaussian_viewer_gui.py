#!/usr/bin/env python
# -*- coding: utf-8 -*-
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
        
        # model datas
        self.model_path = model_path
        self.checkpoint = checkpoint
        self.dataset = dataset
        self.pipeline = pipeline
        
        # filePath
        self.config_dir = os.path.join(model_path, '.luminags')
        self.config_file = os.path.join(self.config_dir, 'config.json')
        
        # load gaussian model
        print("[RealtimeViewer] Loading gaussian model...", flush=True)
        self.gaussians = GaussianModel(dataset.sh_degree)
        self.scene = Scene(dataset, self.gaussians, shuffle=False)
        
        print(f"[RealtimeViewer] Loading checkpoint: {checkpoint}", flush=True)
        checkpoint_data = torch.load(checkpoint)
        if isinstance(checkpoint_data, Tuple):
            model_params = checkpoint_data[0]
        elif isinstance(checkpoint_data, Dict):
            model_params = checkpoint_data["gaussians"]
        else:
            raise TypeError("Unsupported checkpoint format")
        
        self.gaussians.restore(model_params)
        print("[RealtimeViewer] Model loaded", flush=True)
        ready_signal_path = os.path.join(model_path, '.luminags', 'gui_ready.signal')
        try:
            os.makedirs(os.path.dirname(ready_signal_path), exist_ok=True)
            with open(ready_signal_path, 'w', encoding='utf-8') as f:
                f.write(f'GUI_READY|{os.getpid()}|{model_path}\n')
        except Exception as e:
            print(f"[RealtimeViewer] Failed to write signal file: {e}", flush=True)
        
        # get views 
        self.views = self.scene.getTrainCameras()
        if len(self.views) == 0:
            raise ValueError("No cameras found in the scene")
        
        self.ref_view = self.views[0]
        self.H = int(self.ref_view.image_height * resolution_scale)
        self.W = int(self.ref_view.image_width * resolution_scale)
        
        self.vertex_count = len(self.gaussians.get_xyz)
        self.face_count = self.vertex_count // 2
        
        # camera parameters
        self.camera_center = torch.zeros(3)
        self.distance = 5.0
        self.yaw = 0.0
        self.pitch = 0.0
        try:
            xyz = self.gaussians.get_xyz
            min_bound = xyz.min(dim=0)[0]
            max_bound = xyz.max(dim=0)[0]
            scene_center = (min_bound + max_bound) / 2
            scene_size = max_bound - min_bound
            max_dim = scene_size.max().item()
            light_offset = max_dim * 1.5
            self.light_position = torch.tensor([
                scene_center[0].item() + light_offset,
                scene_center[1].item() + light_offset,
                scene_center[2].item() + light_offset
            ], dtype=torch.float32)
            print(f"[RealtimeViewer] Light position initialized: {self.light_position.cpu().numpy()}")
        except:
            self.light_position = torch.tensor([5.0, 5.0, 5.0], dtype=torch.float32)
        self.enable_pbr = False
        
        # PBR settings
        self.pbr_settings = {
            'metallic': False,
            'indirect': False,
            'tone_mapping': False,
            'gamma_correction': False,
            'shadow': True,
        }
        
        # rendering quality mode
        self.quality_mode = "standard" # self.quality_mode = "high_quality"
        self.shadow_threshold = 2.0  # shadow threshold
        
        # depth_cubemap_cache
        self.depth_cubemap_cache = None
        self.last_light_position = None
        
        # VRAM detection and resolution adaptation
        self.vram_gb = self._get_gpu_vram_gb()
        print(f"[RealtimeViewer] Detected VRAM: {self.vram_gb:.1f} GB")
        
        if self.vram_gb < 4.0:
            self.cubemap_resolution = 0
            self.high_quality_disabled = True
            print("[Warning] Less than 4GB VRAM, high-quality shadow mode disabled")
        elif self.vram_gb < 12.0:
            self.cubemap_resolution = 512
            self.high_quality_disabled = False
            print(f"[Tip] 4-12GB VRAM, cubemap resolution set to 512")
        else:
            self.cubemap_resolution = 1024
            self.high_quality_disabled = False
            print(f"[Tip] Sufficient VRAM (>=12GB), cubemap resolution set to 1024")
        
        # view control
        self.show_wireframe = False
        self.show_light_gizmo = True
        self.auto_rotate = False
        
        # Light animation status
        self.light_animation_playing = False
        self.light_animation_frame = 0
        self.light_animation_total_frames = 480
        self.light_animation_fps = 30
        self.light_trajectory = None
        
        # rendering status
        self.rendering = False
        self.render_thread = None
        self.current_frame = None
        self.fps = 0.0
        
        # mouse interaction status
        self.mouse_last_x = -1
        self.mouse_last_y = -1
        self.mouse_left_pressed = False
        self.mouse_right_pressed = False
        
        self.ready_signal_path = os.path.join(model_path, '.luminags', 'gui_ready.signal')
        
        # Cache the background color tensor
        self.bg_color = torch.tensor([0.0, 0.0, 0.0], dtype=torch.float32).cuda()
        
        print("[RealtimeViewer] Loading user configuration...", flush=True)
        self.user_config = self._load_user_config()
        self._build_gui()
        
        # Initialize light intensity
        self.light_intensity = torch.tensor([self.light_r_var.get(), self.light_g_var.get(), self.light_b_var.get()], dtype=torch.float32).cuda()
        
        if self.user_config:
            print("[RealtimeViewer] Apply user configuration...", flush=True)
            self._apply_user_config()
        self._start_render_loop()
    
    def _get_gpu_vram_gb(self) -> float:
        """Get GPU VRAM size in GB"""
        try:
            import torch
            if torch.cuda.is_available():
                total_memory = torch.cuda.get_device_properties(0).total_memory
                return total_memory / (1024 ** 3)
            else:
                print("[Warning] CUDA is not available, assuming insufficient VRAM")
                return 0.0
        except Exception as e:
            print(f"[Warning] Failed to detect VRAM: {e}, assuming 0GB")
            return 0.0
    
    def _build_gui(self):
        # Main container
        main_frame = ttk.Frame(self.root, padding="5")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Right panel: properties panel
        right_panel = self._create_properties_panel(main_frame)
        right_panel.pack(side=tk.RIGHT, fill=tk.Y, padx=(5, 0))
        
        # Left frame: viewport area    
        left_frame = ttk.Frame(main_frame)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # FPS info bar
        info_frame = ttk.Frame(left_frame)
        info_frame.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.fps_label = ttk.Label(info_frame, text="FPS: 0.0", font=("Arial", 10, "bold"), foreground="#00ff00")
        self.fps_label.pack(side=tk.LEFT, padx=5, pady=2)
        
        # Play button 
        self.play_button = ttk.Button(info_frame, text="▶ 播放", command=self._toggle_light_animation, width=8)
        self.play_button.pack(side=tk.LEFT, padx=5, pady=2)
        
        # Image display label
        self.viewport_label = ttk.Label(left_frame, background="#1a1a1a")
        self.viewport_label.pack(fill=tk.BOTH, expand=True)
        
        # Mouse events
        self.viewport_label.bind("<Button-1>", self._on_mouse_down)
        self.viewport_label.bind("<ButtonRelease-1>", self._on_mouse_up)
        self.viewport_label.bind("<B1-Motion>", self._on_mouse_drag)
        self.viewport_label.bind("<Button-3>", self._on_right_mouse_down)
        self.viewport_label.bind("<ButtonRelease-3>", self._on_right_mouse_up)
        self.viewport_label.bind("<B3-Motion>", self._on_right_mouse_drag)
        self.viewport_label.bind("<MouseWheel>", self._on_mouse_wheel)
    def _on_mouse_down(self, event):
        self.mouse_left_pressed = True
        self.mouse_last_x = event.x
        self.mouse_last_y = event.y
    
    def _on_mouse_up(self, event):
        self.mouse_left_pressed = False
        self.mouse_last_x = -1
        self.mouse_last_y = -1
    
    def _on_mouse_drag(self, event):
        if self.mouse_left_pressed and self.mouse_last_x >= 0:
            dx = event.x - self.mouse_last_x
            dy = event.y - self.mouse_last_y
            
            self.yaw -= dx * 0.5
            self.pitch += dy * 0.5
            self.pitch = max(-89, min(89, self.pitch))
            
            self.mouse_last_x = event.x
            self.mouse_last_y = event.y
    
    def _on_right_mouse_down(self, event):
        self.mouse_right_pressed = True
        self.mouse_last_x = event.x
        self.mouse_last_y = event.y
    
    def _on_right_mouse_up(self, event):
        self.mouse_right_pressed = False
        self.mouse_last_x = -1
        self.mouse_last_y = -1
    
    def _on_right_mouse_drag(self, event):
        if self.mouse_right_pressed and self.mouse_last_x >= 0:
            dx = event.x - self.mouse_last_x
            dy = event.y - self.mouse_last_y
            move_speed = 0.01 * self.distance
            self.camera_center[0] -= dx * move_speed
            self.camera_center[1] += dy * move_speed
            self.mouse_last_x = event.x
            self.mouse_last_y = event.y
    
    def _on_mouse_wheel(self, event):
        if event.delta > 0:
            self.distance *= 0.95
            self.distance = max(self.distance, 0.1)
        else:
            self.distance *= 1.05
            self.distance = min(self.distance, 100.0)
    
    def _create_properties_panel(self, parent) -> ttk.Frame:
        panel = ttk.Frame(parent, width=320)
        panel.pack_propagate(False)
        # Create Canvas and Scrollbar
        canvas = tk.Canvas(panel, highlightthickness=0, width=300)
        scrollbar = ttk.Scrollbar(panel, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        # Create window in Canvas and set width
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw", width=300)
        canvas.configure(yscrollcommand=scrollbar.set)
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", _on_mousewheel))
        canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))
        
        # Pack Canvas and Scrollbar
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # View control
        view_group = ttk.LabelFrame(scrollable_frame, text="视图控制", padding="10")
        view_group.pack(fill=tk.X, pady=5)
        ttk.Button(view_group, text="重置视角", command=self._reset_view).pack(pady=5, padx=10, fill=tk.X)
        
        # Configuration management
        config_group = ttk.LabelFrame(scrollable_frame, text="配置管理", padding="10")
        config_group.pack(fill=tk.X, pady=5)
        ttk.Button(config_group, text="💾 保存当前配置", command=self._save_user_config, style='Accent.TButton').pack(pady=8, padx=10, fill=tk.X)
        
        # Rendering mode
        render_group = ttk.LabelFrame(scrollable_frame, text="渲染模式", padding="10")
        render_group.pack(fill=tk.X, pady=5)
        self.render_mode_var = tk.StringVar(value="normal")
        ttk.Radiobutton(render_group, text="普通模式", variable=self.render_mode_var, value="normal",
                       command=self._toggle_render_mode).pack(anchor=tk.W, padx=10)
        ttk.Radiobutton(render_group, text="标准重光照", variable=self.render_mode_var, value="standard_relight",
                       command=self._toggle_render_mode).pack(anchor=tk.W, padx=10)
        ttk.Radiobutton(render_group, text="增强重光照", variable=self.render_mode_var, value="enhanced_relight",
                       command=self._toggle_render_mode).pack(anchor=tk.W, padx=10)
        
        # Screenshot functionality
        screenshot_group = ttk.Frame(scrollable_frame, padding="10")
        screenshot_group.pack(fill=tk.X, pady=5)
        ttk.Button(screenshot_group, text="📸 保存截图", command=self._save_screenshot).pack(pady=5, padx=10, fill=tk.X)
        
        # Light source control
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
        
        # Light intensity control
        intensity_group = ttk.LabelFrame(scrollable_frame, text="光照强度控制", padding="10")
        intensity_group.pack(fill=tk.X, pady=5)
        # Overall intensity control
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
        
        # PBR settings
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
        
        # Shadow threshold control (only shown in enhanced relight mode)
        self.threshold_frame = ttk.Frame(scrollable_frame, padding=(10, 0))
        ttk.Label(self.threshold_frame, text="阴影阈值:").pack(anchor=tk.W)
        self.shadow_threshold_var = tk.DoubleVar(value=2.0)
        self.threshold_scale = ttk.Scale(self.threshold_frame, from_=0.01, to=20.0, variable=self.shadow_threshold_var,
                  command=self._update_shadow_threshold)
        self.threshold_scale.pack(fill=tk.X)
        # Initially hidden
        self.threshold_frame.pack_forget()
        
        stats_group = ttk.LabelFrame(scrollable_frame, text="场景统计", padding="10")
        stats_group.pack(fill=tk.X, pady=5)
        self.stats_label = ttk.Label(stats_group, 
                                     text=f"Vertices: {self.vertex_count:,}\nFaces: {self.face_count:,}",
                                     justify=tk.LEFT)
        self.stats_label.pack(anchor=tk.W)
        return panel
    
    def _start_render_loop(self):
        self.rendering = True
        def render_loop():
            frame_count = 0
            start_time = torch.cuda.Event(enable_timing=True)
            end_time = torch.cuda.Event(enable_timing=True)
            start_time.record()
            while self.rendering:
                try:
                    frame = self._render_current_view()
                    self.current_frame = frame
                    # Calculate FPS
                    frame_count += 1
                    end_time.record()
                    torch.cuda.synchronize()
                    elapsed_ms = start_time.elapsed_time(end_time) / 1000.0
                    if elapsed_ms >= 1.0:
                        self.fps = frame_count / elapsed_ms
                        frame_count = 0
                        start_time.record()
                    self.root.after(0, self._update_display)
                    
                except Exception as e:
                    print(f"[渲染错误] {e}")
                    import traceback
                    traceback.print_exc()
                # Control frame rate
                time.sleep(0.016)
        
        self.render_thread = threading.Thread(target=render_loop, daemon=True)
        self.render_thread.start()
    
    def _render_current_view(self) -> np.ndarray:
        c2w = self._get_current_c2w()
        viewpoint_camera = self._create_camera_from_c2w(c2w)
        class SimplePipe:
            debug = False
            convert_SHs_python = False
            compute_cov3D_python = False
        pipe = SimplePipe()
        
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
            rendering_result = render(
                viewpoint_camera=viewpoint_camera,
                pc=self.gaussians,
                pipe=pipe,
                bg_color=self.bg_color,
                inference=True,
                pad_normal=False,
                derive_normal=False,
            )
            render_rgb = rendering_result["render"]
        
        # Convert to numpy array
        render_rgb = render_rgb.detach().permute(1, 2, 0).clamp(0.0, 1.0).cpu().numpy()
        render_rgb = (render_rgb * 255).astype(np.uint8)
        
        return render_rgb
    
    def _update_display(self):
        if self.current_frame is not None:
            # Convert numpy array to PhotoImage
            try:
                from PIL import Image, ImageTk, ImageDraw
                image = Image.fromarray(self.current_frame)
                image = image.resize((self.viewport_label.winfo_width(), 
                                     self.viewport_label.winfo_height()), 
                                    Image.Resampling.LANCZOS)
                
                # Draw light source indicator on the image
                if self.show_light_gizmo and self.enable_pbr:
                    draw = ImageDraw.Draw(image)
                    light_screen_pos = self._project_light_to_screen(image.width, image.height)
                    if light_screen_pos is not None:
                        lx, ly = light_screen_pos
                        radius = 8
                        draw.ellipse([lx-radius, ly-radius, lx+radius, ly+radius], 
                                   outline='yellow', width=2)
                        draw.ellipse([lx-3, ly-3, lx+3, ly+3], fill='yellow')
                        cross_size = 15
                        draw.line([lx-cross_size, ly, lx+cross_size, ly], fill='yellow', width=1)
                        draw.line([lx, ly-cross_size, lx, ly+cross_size], fill='yellow', width=1)
                
                photo = ImageTk.PhotoImage(image)
                self.viewport_label.configure(image=photo)
                self.viewport_label.image = photo 
                # Update FPS information
                self.fps_label.config(text=f"FPS: {self.fps:.1f}")
                
            except Exception as e:
                print(f"[Display Error] {e}")
    
    def _project_light_to_screen(self, screen_width: int, screen_height: int):
        try:
            import torch.nn.functional as F
            
            # Get the current camera matrix
            c2w = self._get_current_c2w().cuda()
            w2c = torch.inverse(c2w)
            # Light position to camera coordinates
            light_pos_world = self.light_position.cuda()
            light_pos_cam = w2c[:3, :3] @ light_pos_world + w2c[:3, 3]
            # Check if the light source is in front of the camera
            if light_pos_cam[2] <= 0:
                return None
            
            # Get the camera intrinsics
            tan_fovx = np.tan(self.ref_view.FoVx * 0.5)
            tan_fovy = np.tan(self.ref_view.FoVy * 0.5)
            focal_x = screen_width / (2.0 * tan_fovx)
            focal_y = screen_height / (2.0 * tan_fovy)
            
            # Perspective projection
            x_ndc = (light_pos_cam[0] / light_pos_cam[2]) * focal_x / (screen_width / 2)
            y_ndc = -(light_pos_cam[1] / light_pos_cam[2]) * focal_y / (screen_height / 2)
            
            # Convert to screen coordinates
            screen_x = (x_ndc + 1.0) * screen_width / 2
            screen_y = (y_ndc + 1.0) * screen_height / 2
            if 0 <= screen_x <= screen_width and 0 <= screen_y <= screen_height:
                return (int(screen_x), int(screen_y))
            else:
                return None
        except Exception as e:
            print(f"[Projection Error] {e}")
            return None
    
    def _get_current_c2w(self) -> torch.Tensor:
        """Compute the camera extrinsics"""
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
        """Create a virtual camera"""
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
        """Apply PBR relighting"""
        import torch.nn.functional as F
        c2w = c2w.cuda()
        
        # Extract PBR material parameters
        albedo_map = rendering_result["albedo_map"]  # [3, H, W]
        roughness_map = rendering_result["roughness_map"]  # [1, H, W]
        metallic_map_from_checkpoint = rendering_result["metallic_map"]  # [1, H, W]
        normal_map = rendering_result["normal_map"]  # [3, H, W]
        depth_map = rendering_result["depth_map"]  # [1, H, W]
        normal_mask = rendering_result["normal_mask"]  # [1, H, W]
        
        # Adjust PBR parameters based on user settings
        use_metallic = self.pbr_settings.get('metallic', False)
        use_shadow = self.pbr_settings.get('shadow', True)
        use_indirect = self.pbr_settings.get('indirect', False)
        
        # If metallic is not enabled, use a fixed value
        if not use_metallic:
            metallic_map = torch.zeros_like(metallic_map_from_checkpoint)
        else:
            metallic_map = metallic_map_from_checkpoint
        
        canonical_rays = self._get_canonical_rays()  # [H*W, 3]
        world_rays = (c2w[:3, :3] @ canonical_rays.T).T  # [H*W, 3]
        world_rays = F.normalize(world_rays, p=2, dim=-1)
        view_dirs = -world_rays.reshape(self.H, self.W, 3)  # [H, W, 3]
        
        # Calculate 3D point positions
        norm = torch.norm(canonical_rays, p=2, dim=-1).reshape(self.H, self.W, 1)
        cam_pos_world = c2w[:3, 3]
        points = (
            cam_pos_world + world_rays.reshape(-1, 3) * norm.reshape(-1, 1) * depth_map.reshape(-1, 1)
        ).contiguous().reshape(self.H, self.W, 3)  # [H, W, 3]
        light_pos_world = self.light_position.cuda()
        
        # Calculate direct lighting
        if use_shadow:
            if self.quality_mode == "high_quality":
                # High quality mode: use depth map based shadows
                shadow_map = self._calculate_high_quality_shadows(
                    light_pos=light_pos_world,
                    points=points,
                    normal_map=normal_map.permute(1, 2, 0),
                    depth_map=depth_map.permute(1, 2, 0)
                )
                
                # Apply shadows to PBR shading
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
                # Standard mode: use distance attenuation PBR shadow
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
            # Disable shadows: use uniform lighting
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
        
        # Calculate indirect lighting
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
            
            # Mix direct and indirect lighting
            render_rgb = render_rgb + indirect_lighting
            render_rgb = torch.clamp(render_rgb, 0.0, 1.0)
        
        return render_rgb.permute(2, 0, 1)  # [3, H, W]
    
    def _get_canonical_rays(self) -> torch.Tensor:
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
        """Saturated dot product"""
        return (a * b).sum(dim=-1, keepdim=True).clamp(min=0.0, max=1.0)
    
    def _distribution_ggx(self, normals: torch.Tensor, half_dirs: torch.Tensor, roughness: torch.Tensor) -> torch.Tensor:
        """GGX Normal Distribution Function"""
        a = roughness * roughness
        a2 = a * a
        NoH = self._saturate_dot(normals, half_dirs)
        NoH2 = NoH * NoH
        
        nom = a2
        denom = (NoH2 * (a2 - 1.0) + 1.0)
        denom = np.pi * denom * denom
        
        return nom / denom
    
    def _geometry_schlick_ggx(self, NoV: torch.Tensor, roughness: torch.Tensor) -> torch.Tensor:
        """Schlick-GGX Geometry Function"""
        r = roughness + 1.0
        k = (r * r) / 8.0
        nom = NoV
        denom = NoV * (1.0 - k) + k
        
        return nom / denom
    
    def _geometry_smith(self, normals: torch.Tensor, view_dirs: torch.Tensor, light_dirs: torch.Tensor, roughness: torch.Tensor) -> torch.Tensor:
        """Smith Geometry Function"""
        NoV = self._saturate_dot(normals, view_dirs)
        NoL = self._saturate_dot(normals, light_dirs)
        ggx2 = self._geometry_schlick_ggx(NoV, roughness)
        ggx1 = self._geometry_schlick_ggx(NoL, roughness)
        
        return ggx1 * ggx2
    
    def _fresnel_schlick(self, HoV: torch.Tensor, F0: torch.Tensor) -> torch.Tensor:
        """Fresnel-Schlick Function"""
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
        """PBR Shading Function"""
        import torch.nn.functional as F
        light_dirs = F.normalize(light_position - points, p=2, dim=-1)  # [H, W, 3]
        half_dirs = (light_dirs + view_dirs) / 2.0  # [H, W, 3]
        distance = torch.norm(light_position - points, p=2, dim=-1, keepdim=True)  # [H, W, 1]
        
        # Standard mode: use distance attenuation to simulate basic light changes
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
        """PBR Shading Function"""
        import torch.nn.functional as F
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
        
        # Apply shadows to PBR shading
        render_rgb = (kd * albedo / np.pi + specular) * radiance * NoL
        
        # Apply soft shadows using shadow_map as mask factor
        shadow_factor = 1.0 - shadow_map * 0.8
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
        """PBR Shading Function (Disable Shadows - Remove Distance Attenuation)"""
        import torch.nn.functional as F
        light_dirs = F.normalize(light_position - points, p=2, dim=-1)  # [H, W, 3]
        half_dirs = (light_dirs + view_dirs) / 2.0  # [H, W, 3]
        radiance = light_intensity.expand_as(points)  # [H, W, 3] 
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
        """Generate depth cubemap from light perspective"""
        if resolution is None:
            resolution = self.cubemap_resolution
        
        import torch.nn.functional as F
        
        # Get normalized rays (for depth normalization)
        canonical_rays = self._get_canonical_rays_cubemap(resolution)
        norm = torch.norm(canonical_rays, p=2, dim=-1).reshape(resolution, resolution, 1)
        
        bg_color = torch.zeros([3, resolution, resolution], device="cuda")
        
        # 6 rotation matrices
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
        # Prepare Gaussian data
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
            
            # Construct rendering parameters
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
            (num_rendered, rendered_image, opacity_map, radii, depth_map) = _C.lite_rasterize_gaussians(*input_args)
            depth_cubemap.append(depth_map.permute(1, 2, 0))  # [H, W, 1]
        return torch.stack(depth_cubemap)  # [6, H, W, 1]
    
    def _calculate_high_quality_shadows(self, 
                                      light_pos: torch.Tensor, 
                                      points: torch.Tensor, 
                                      normal_map: torch.Tensor,
                                      depth_map: torch.Tensor) -> torch.Tensor:
        """Calculate high-quality shadows using depth cubemap"""
        import torch.nn.functional as F
        
        H, W = points.shape[:2]
        
        # Check if high-quality shadows are disabled or cubemap resolution is 0
        if self.high_quality_disabled or self.cubemap_resolution == 0:
            print("[Warning] High-quality shadows are disabled (insufficient VRAM), returning no shadows")
            return torch.zeros((H, W, 1), device=light_pos.device)
        
        # Check if cubemap needs to be re-generated
        if (self.depth_cubemap_cache is None or 
            self.last_light_position is None or
            not torch.allclose(self.last_light_position, light_pos, atol=0.01)):
            
            print(f"[RealtimeViewer] Generating cubemap (resolution: {self.cubemap_resolution})...")
            self.depth_cubemap_cache = self._generate_depth_cubemap(light_pos, self.cubemap_resolution)
            self.last_light_position = light_pos.clone()
            print("[RealtimeViewer] Cubemap generation completed")
        
        depth_cubemap = self.depth_cubemap_cache
        
        # Calculate direction and distance to light source
        to_light = (light_pos[None, None, :] - points).reshape(H, W, 3)  # [H, W, 3]
        distance_to_light = torch.norm(to_light, p=2, dim=-1, keepdim=True)  # [H, W, 1]
        query_dirs = F.normalize(-to_light, p=2, dim=-1)  # [H, W, 3]
        
        # Use nvdiffrast for cubemap sampling
        try:
            import nvdiffrast.torch as dr
            closest_depth = dr.texture(
                depth_cubemap[None, ...],  # [1, 6, H, W, 1]
                query_dirs[None, ...].contiguous(),  # [1, H, W, 3]
                filter_mode="linear",
                boundary_mode="cube",
            )[0]  # [H, W, 1]
            
            # Convert depth to Euclidean distance
            # The depth in the cubemap is along the ray direction, need to multiply by the normalized ray length factor
            # For fov=90° cubemap, the normalized ray length is different at different positions
            # We need to convert the sampled depth values to the actual Euclidean distances
            # Calculate the normalized ray length for the sampled direction 
            # For cube maps, each pixel corresponds to a direction vector 
            # The depth value indicates the distance along the direction, so the Euclidean distance = depth * |direction|
            # But since we are using normalized query_dirs, |direction| = 1
            
            # Simplified scheme: directly use the norm factor for conversion
            # Get the normalized ray length for the current face
            resolution = depth_cubemap.shape[1]
            canonical_rays = self._get_canonical_rays_cubemap(resolution)  # [H*W, 3]
            ray_lengths = torch.norm(canonical_rays, p=2, dim=-1).reshape(resolution, resolution, 1)  # [H, W, 1]
            
        except ImportError:
            # If nvdiffrast is not available, use simplified nearest neighbor sampling
            print("[Warning] nvdiffrast is unavailable, using simplified shadow calculation")
            closest_depth = self._simple_cubemap_sampling(depth_cubemap, query_dirs)
        
        threshold = self.shadow_threshold
        min_depth = 0.1  # Minimum effective depth
        valid_occlusion = (closest_depth > min_depth) & (distance_to_light - threshold > closest_depth)
        shadow_raw = valid_occlusion.float()
        
        # Apply simple box filter to smooth shadow
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
        """Construct world to view transformation matrix"""
        Rt = torch.zeros((4, 4), device=R.device)
        Rt[:3, :3] = R[:3, :3].T
        Rt[:3, 3] = t
        Rt[3, 3] = 1.0
        return Rt
    
    def _get_canonical_rays_cubemap(self, resolution: int) -> torch.Tensor:
        """Get canonical rays for cubemap"""
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
        """Simplified cubemap sampling"""
        import torch.nn.functional as F
        
        H, W = query_dirs.shape[:2]
        res = depth_cubemap.shape[1]
        
        # Convert direction vectors to cube face index and UV coordinates
        dirs = query_dirs.reshape(-1, 3)  # [HW, 3]
        abs_dirs = torch.abs(dirs)
        max_axis = torch.argmax(abs_dirs, dim=1)  # [HW]
        signs = torch.sign(dirs)
        # Computational plane index (0:+X, 1:-X, 2:+Y, 3:-Y, 4:+Z, 5:-Z)
        face_indices = torch.where(max_axis == 0, 
                                   torch.where(signs[:, 0] > 0, 0, 1),
                                   torch.where(max_axis == 1,
                                              torch.where(signs[:, 1] > 0, 2, 3),
                                              torch.where(signs[:, 2] > 0, 4, 5)))
        
        # Calculate UV coordinates
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
        
        uv = (st[:, :2] + 1.0) / 2.0  # [HW, 2]
        uv = uv.clamp(0.0, 1.0)
        
        # Sample depths for each face
        sampled_depths = torch.zeros(H * W, 1, device=depth_cubemap.device)
        for i in range(6):
            mask = face_indices == i
            if not mask.any():
                continue
            
            face_depth = depth_cubemap[i]  # [res, res, 1]
            face_uv = uv[mask]  # [N, 2]
            
            # Bilinear interpolation sampling
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
        """Compute indirect lighting (ambient occlusion + diffuse)"""
        import numpy as np
        # 1. Use ambient occlusion (AO) to simulate global shadow
        # 2. Use fixed sky color to simulate sky light
        
        ambient_intensity = torch.tensor([0.1, 0.1, 0.15], dtype=torch.float32).cuda()
        sky_intensity = torch.tensor([0.05, 0.06, 0.08], dtype=torch.float32).cuda()
        
        # Calculate dot product of normals and up vector
        up_vector = torch.tensor([0.0, 1.0, 0.0], dtype=torch.float32).cuda()
        NoUp = (normals * up_vector).sum(dim=-1, keepdim=True).clamp(0.0, 1.0)  # [H, W, 1]
        
        indirect_diffuse = ambient_intensity.expand_as(albedo)
        indirect_diffuse = indirect_diffuse + sky_intensity * NoUp
        roughness_factor = 1.0 - roughness * 0.5
        
        # Metallic affects: metal surfaces have little diffuse indirect light
        kd = (1.0 - metallic) * roughness_factor
        
        # Final indirect diffuse
        indirect_diffuse = indirect_diffuse * kd * albedo / np.pi
        
        # Simple AO approximation: based on depth gradient
        # Depth gradient large places (edges) have stronger AO  
        depth_z = points[..., 2:3]  # [H, W, 1]
        depth_dx = torch.abs(torch.gradient(depth_z, dim=1)[0])  # [H, W, 1]
        depth_dy = torch.abs(torch.gradient(depth_z, dim=0)[0])  # [H, W, 1]
        depth_gradient = depth_dx + depth_dy
        ao_factor = 1.0 / (1.0 + depth_gradient * 0.5) 
        ao_factor = ao_factor.clamp(0.3, 1.0)
        
        indirect_diffuse = indirect_diffuse * ao_factor
        background = torch.zeros_like(indirect_diffuse)
        indirect_diffuse = torch.where(mask, indirect_diffuse, background)
        return indirect_diffuse
    
    def _load_user_config(self) -> Optional[Dict]:
        """Load user config file"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                print(f"[RealtimeViewer] [OK] Config file loaded: {self.config_file}")
                return config
            else:
                print(f"[RealtimeViewer] [INFO] Config file does not exist, using default settings")
                return None
        except Exception as e:
            print(f"[RealtimeViewer] [WARN] Failed to load config: {e}")
            return None
    
    def _save_user_config(self):
        """Save user config file"""
        try:
            os.makedirs(self.config_dir, exist_ok=True)
            # Collect current config
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
            
            # Save to file
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            
            print(f"[RealtimeViewer] [OK] Config saved: {self.config_file}")
            messagebox.showinfo("Success", f"Config saved to:\n{self.config_file}")
        except Exception as e:
            print(f"[RealtimeViewer] [ERROR] Failed to save config: {e}")
            messagebox.showerror("Error", f"Failed to save config:\n{str(e)}")
    
    def _apply_user_config(self):
        """Apply user config"""
        try:
            # Light position
            if 'light_position' in self.user_config:
                light_pos = self.user_config['light_position']
                self.light_x_var.set(light_pos.get('x', 0.0))
                self.light_y_var.set(light_pos.get('y', 0.0))
                self.light_z_var.set(light_pos.get('z', 5.0))
                self._update_light_position()
            
            # Light intensity
            if 'light_intensity' in self.user_config:
                light_intensity = self.user_config['light_intensity']
                self.light_r_var.set(light_intensity.get('r', 100.0))
                self.light_g_var.set(light_intensity.get('g', 100.0))
                self.light_b_var.set(light_intensity.get('b', 100.0))
                self.light_master_var.set(light_intensity.get('master', 100.0))
                self._update_light_intensity()
            
            # Render mode 
            if 'render_mode' in self.user_config:
                self.render_mode_var.set(self.user_config['render_mode'])
                self._toggle_render_mode()
            
            # PBR settings
            if 'pbr_settings' in self.user_config:
                pbr = self.user_config['pbr_settings']
                self.metallic_var.set(pbr.get('metallic', False))
                self.indirect_var.set(pbr.get('indirect', False))
                self.shadow_var.set(pbr.get('shadow', True))
                self._update_pbr_settings()
            
            # Camera perspective
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
            
            print("[RealtimeViewer] [OK] User config applied")
        except Exception as e:
            print(f"[RealtimeViewer] [WARN] Failed to apply config: {e}")
    def _reset_view(self):
        """Reset view"""
        self.camera_center = torch.zeros(3)
        self.yaw = 0.0
        self.pitch = 0.0
        self.distance = 5.0
        print("[RealtimeViewer] View reset")
    
    def _toggle_auto_rotate(self):
        """Toggle auto rotate"""
        self.auto_rotate = not self.auto_rotate
        print(f"[RealtimeViewer] Auto rotate: {'Enabled' if self.auto_rotate else 'Disabled'}")
    
    def _prev_view(self):
        """Switch to previous view"""
        if len(self.views) > 1:
            current_idx = self.views.index(self.ref_view)
            new_idx = (current_idx - 1) % len(self.views)
            self.ref_view = self.views[new_idx]
            print(f"[RealtimeViewer] Switched to view {new_idx}")
    
    def _next_view(self):
        if len(self.views) > 1:
            current_idx = self.views.index(self.ref_view)
            new_idx = (current_idx + 1) % len(self.views)
            self.ref_view = self.views[new_idx]
            print(f"[RealtimeViewer] Switched to view {new_idx}")
    
    def _toggle_pbr(self):
        """Toggle PBR"""
        self.enable_pbr = not self.enable_pbr
        print(f"[RealtimeViewer] PBR: {'Enabled' if self.enable_pbr else 'Disabled'}")
    
    def _update_light_position(self, val=None):
        """Update light position"""
        self.light_position = torch.tensor([
            self.light_x_var.get(),
            self.light_y_var.get(),
            self.light_z_var.get()
        ], dtype=torch.float32)
        print(f"[RealtimeViewer] 光源位置：{self.light_position.cpu().numpy()}")
    
    def _update_light_intensity(self, val=None):
        """Update light intensity"""
        self.light_intensity = torch.tensor([
            self.light_r_var.get(),
            self.light_g_var.get(),
            self.light_b_var.get()
        ], dtype=torch.float32).cuda()
        
        # Check if RGB three channels are the same
        r_val = self.light_r_var.get()
        g_val = self.light_g_var.get()
        b_val = self.light_b_var.get()
        
        if abs(r_val - g_val) < 0.01 and abs(g_val - b_val) < 0.01 and abs(r_val - b_val) < 0.01:
            # RGB are the same, enable master intensity control and sync values
            self.light_master_var.set(r_val)
            self.master_scale.config(state='normal')
        else:
            self.master_scale.config(state='disabled')
        
        print(f"[RealtimeViewer] Light intensity: {self.light_intensity.cpu().numpy()}")
    
    def _update_light_master_intensity(self, val=None):
        """Update overall light intensity (sync adjust RGB three channels)"""
        master_value = self.light_master_var.get()
        self.light_r_var.set(master_value)
        self.light_g_var.set(master_value)
        self.light_b_var.set(master_value)
        self.light_intensity = torch.tensor([master_value, master_value, master_value], dtype=torch.float32).cuda()
        print(f"[RealtimeViewer] Overall light intensity: {master_value}")
    
    def _toggle_render_mode(self):
        """Toggle render mode"""
        mode = self.render_mode_var.get()
        
        if mode == "normal":
            # Normal mode: disable relight
            self.enable_pbr = False
            self.quality_mode = "standard"
            self.threshold_frame.pack_forget()
            print("[Render Mode] Normal mode (no PBR)")
            
        elif mode == "standard_relight":
            # Standard relight: enable PBR, use standard shadow (distance attenuation)
            self.enable_pbr = True
            self.quality_mode = "standard"
            self.threshold_frame.pack_forget()
            print("[Render Mode] Standard relight (PBR + Standard Shadow)")
            
        elif mode == "enhanced_relight":
            # Enhanced relight: enable PBR, use high-quality shadow (depth cubemap)
            self.enable_pbr = True
            self.quality_mode = "high_quality"
            self.threshold_frame.pack(fill=tk.X, pady=(5, 0))
            print("[Render Mode] Enhanced relight (PBR + High-Quality Shadow)")
    
    def _update_pbr_settings(self):
        """Update PBR settings"""
        self.pbr_settings['metallic'] = self.metallic_var.get()
        self.pbr_settings['indirect'] = self.indirect_var.get()
        self.pbr_settings['shadow'] = self.shadow_var.get()
        
        # If any PBR option is checked, automatically switch to standard relight mode
        if any([self.metallic_var.get(), self.indirect_var.get(), self.shadow_var.get()]):
            if not self.enable_pbr:
                self.enable_pbr = True
                self.quality_mode = "standard"
                self.render_mode_var.set("standard_relight")
        else:
            pass
        
        print(f"[RealtimeViewer] PBR settings updated: {self.pbr_settings}")
    
    def _update_shadow_threshold(self, val=None):
        """Update shadow threshold"""
        self.shadow_threshold = float(self.shadow_threshold_var.get())
        print(f"[RealtimeViewer] Shadow threshold: {self.shadow_threshold}")
    
    def _save_screenshot(self):
        """Save screenshot"""
        if self.current_frame is not None:
            from PIL import Image
            import datetime
            
            image = Image.fromarray(self.current_frame)
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"screenshot_{timestamp}.png"
            image.save(filename)
            messagebox.showinfo("Success", f"Screenshot saved: {filename}")
        else:
            messagebox.showwarning("Warning", "No image to save")
    
    def _toggle_light_animation(self):
        """Toggle light animation playback state"""
        self.light_animation_playing = not self.light_animation_playing
        
        if self.light_animation_playing:
            self.play_button.config(text="⏸ 暂停")
            print("[Light Animation] Started playing")
            
            if self.light_trajectory is None:
                self._generate_light_trajectory()
            
            # Start animation update
            self._update_light_animation()
        else:
            self.play_button.config(text="▶ 播放")
            print("[Light Animation] Paused")
    
    def _generate_light_trajectory(self):
        """Generate light trajectory"""
        try:
            from utils.camera_utils import trajectory_from_c2ws
            import numpy as np
            
            # Get camera views as reference
            views = self.scene.getTrainCameras()
            if len(views) == 0:
                print("[Error] No available camera views")
            c2ws = []
            for view in views:
                c2w = torch.inverse(view.world_view_transform.T).cpu().numpy()  # [4, 4]
                c2ws.append(c2w)
            
            # Interpolate to generate smooth trajectory
            frames = self.light_animation_total_frames
            c2ws_inter = trajectory_from_c2ws(c2ws=c2ws, frames=frames)
            
            # Extract light positions
            self.light_trajectory = []
                
            # Calculate scene center
            all_positions = np.array([c2w[:3, 3] for c2w in c2ws_inter])
            scene_center = np.mean(all_positions, axis=0)  # [3]
            avg_distance = np.mean(np.linalg.norm(all_positions - scene_center, axis=1))  # 平均距离
            
            print(f"  场景中心: {scene_center}")
            print(f"  平均距离: {avg_distance:.2f}")
            
            for frame_idx, c2w in enumerate(c2ws_inter):
                base_pos = c2w[:3, 3].copy()
                angle = (frame_idx / len(c2ws_inter)) * 2 * np.pi
                radius = avg_distance * 0.8  
                light_pos = scene_center.copy()
                light_pos[0] += radius * np.cos(angle)
                light_pos[1] += avg_distance * 0.3 
                light_pos[2] = 10.0
                
                self.light_trajectory.append(torch.from_numpy(light_pos).float())
            print(f"[Light Animation] Trajectory generated: {len(self.light_trajectory)} frames")
            if len(self.light_trajectory) > 0:
                first_pos = self.light_trajectory[0]
                mid_idx = len(self.light_trajectory) // 2
                mid_pos = self.light_trajectory[mid_idx]
                print(f"  First frame position: X={first_pos[0]:.2f}, Y={first_pos[1]:.2f}, Z={first_pos[2]:.2f}")
                print(f"  Middle frame position: X={mid_pos[0]:.2f}, Y={mid_pos[1]:.2f}, Z={mid_pos[2]:.2f}")
            
        except Exception as e:
            print(f"[Error] Light trajectory generation failed: {e}")
            import traceback
            traceback.print_exc()
    
    def _update_light_animation(self):
        """Update light animation (recursive call)"""
        if not self.light_animation_playing or self.light_trajectory is None:
            return
        
        # Get current frame's light position
        frame_idx = self.light_animation_frame % len(self.light_trajectory)
        light_pos = self.light_trajectory[frame_idx].cuda()
        
        # Update light position variables
        self.light_position = light_pos
        self.light_x_var.set(light_pos[0].item())
        self.light_y_var.set(light_pos[1].item())
        self.light_z_var.set(light_pos[2].item())
        
        # Clear cube map cache
        self.depth_cubemap_cache = None
        self.last_light_position = None

        self.light_animation_frame += 1
        
        # Loop playback
        if self.light_animation_frame >= len(self.light_trajectory):
            self.light_animation_frame = 0
        interval_ms = int(1000.0 / self.light_animation_fps)
        self.root.after(interval_ms, self._update_light_animation)
    
    def _on_close(self):
        self.rendering = False
        if self.render_thread:
            self.render_thread.join(timeout=2.0)
        
        try:
            if os.path.exists(self.ready_signal_path):
                os.remove(self.ready_signal_path)
                print(f"[RealtimeViewer] Removed signal file: {self.ready_signal_path}")
        except Exception as e:
            print(f"[RealtimeViewer] Failed to remove signal file: {e}")
        
        self.root.quit()
        self.root.destroy()


def main():
    # Set up command line argument parser
    parser = ArgumentParser(description="实时高斯模型查看器 (GUI 版本)")
    model = ModelParams(parser, sentinel=True)
    pipeline = PipelineParams(parser)
    parser.add_argument("--checkpoint", type=str, default=None, help="Checkpoint 文件路径")
    parser.add_argument("--resolution_scale", type=float, default=1.0, help="分辨率缩放（0.5=半分辨率，2.0=双倍分辨率）")
    args = get_combined_args(parser)
    args.eval = False
    
    if not os.path.exists(args.checkpoint):
        print(f"[Error] Checkpoint file does not exist: {args.checkpoint}")
        sys.exit(1)
    
    model_path = os.path.dirname(args.checkpoint)
    print(f"[RealtimeViewer] Loading model: {model_path}")
    
    # Create Tkinter window
    root = tk.Tk()
    
    # Create and run viewer
    viewer = RealtimeViewerGUI(
        root=root,
        model_path=model_path,
        checkpoint=args.checkpoint,
        dataset=model.extract(args),
        pipeline=pipeline.extract(args),
        resolution_scale=args.resolution_scale,
    )
    # Start main loop
    root.mainloop()


if __name__ == "__main__":
    main()
