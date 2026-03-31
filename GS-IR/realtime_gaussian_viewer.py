#
# 实时高斯模型查看器
# 基于 light_move.py 的渲染逻辑，支持交互式视角控制
#

import os
import sys
from argparse import ArgumentParser
from typing import Dict, List, Optional, Tuple, Union

import cv2
import numpy as np
import torch
import torch.nn.functional as F
from tqdm import tqdm

from arguments import GroupParams, ModelParams, PipelineParams, get_combined_args
from gaussian_renderer import GaussianModel, render
from scene import Scene, Camera
from utils.graphics_utils import getProjectionMatrix


class RealtimeViewer:
    def __init__(
        self,
        model_path: str,
        checkpoint: str,
        dataset: GroupParams,
        pipeline: GroupParams,
        resolution_scale: float = 1.0,
    ):
        """
        初始化实时查看器
        
        Args:
            model_path: 模型路径
            checkpoint: checkpoint 文件路径
            dataset: 数据集参数
            pipeline: 流水线参数
            resolution_scale: 分辨率缩放比例（降低可提高帧率）
        """
        print("[RealtimeViewer] 正在加载高斯模型...")
        self.gaussians = GaussianModel(dataset.sh_degree)
        self.scene = Scene(dataset, self.gaussians, shuffle=False)
        
        print(f"[RealtimeViewer] 正在加载 checkpoint: {checkpoint}")
        checkpoint_data = torch.load(checkpoint)
        if isinstance(checkpoint_data, Tuple):
            model_params = checkpoint_data[0]
        elif isinstance(checkpoint_data, Dict):
            model_params = checkpoint_data["gaussians"]
        else:
            raise TypeError("Unsupported checkpoint format")
        
        self.gaussians.restore(model_params)
        print("[RealtimeViewer] 模型加载完成")
        
        # 获取参考相机
        self.views = self.scene.getTrainCameras()
        if len(self.views) == 0:
            raise ValueError("No cameras found in the scene")
        
        self.ref_view = self.views[0]
        self.H = int(self.ref_view.image_height * resolution_scale)
        self.W = int(self.ref_view.image_width * resolution_scale)
        
        # 当前视角参数
        self.current_view_idx = 0
        self.yaw = 0.0      # 偏航角（左右旋转）
        self.pitch = 0.0    # 俯仰角（上下旋转）
        self.radius = 1.0   # 半径缩放
        
        # 光源参数
        self.light_position = torch.tensor([0.0, 0.0, 5.0], dtype=torch.float32).cuda()
        self.light_intensity = torch.tensor([100.0, 100.0, 100.0], dtype=torch.float32).cuda()
        self.enable_pbr = False  # 是否启用 PBR 重光照
        
        # 设置 OpenCV 窗口
        self.window_name = "LuminaGS - Realtime Viewer"
        cv2.namedWindow(self.window_name, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(self.window_name, self.W, self.H)
        
        # 鼠标交互
        self.mouse_last_x = -1
        self.mouse_last_y = -1
        self.mouse_pressed = False
        self.mouse_right_pressed = False  # 右键按下状态
        self.auto_rotate = False
        
        cv2.setMouseCallback(self.window_name, self._mouse_callback)
        
        # 键盘交互
        self.key_delay = 1  # 毫秒
        self.running = True
        
        print("[RealtimeViewer] 初始化完成，按 Q 退出，R 重置视角，空格切换自动旋转")
    
    def _mouse_callback(self, event, x, y, flags, param):
        """处理鼠标事件"""
        if event == cv2.EVENT_LBUTTONDOWN:
            self.mouse_pressed = True
            self.mouse_last_x = x
            self.mouse_last_y = y
        elif event == cv2.EVENT_LBUTTONUP:
            self.mouse_pressed = False
            self.mouse_last_x = -1
            self.mouse_last_y = -1
        elif event == cv2.EVENT_RBUTTONDOWN:
            self.mouse_right_pressed = True
            self.mouse_last_x = x
            self.mouse_last_y = y
        elif event == cv2.EVENT_RBUTTONUP:
            self.mouse_right_pressed = False
            self.mouse_last_x = -1
            self.mouse_last_y = -1
        elif event == cv2.EVENT_MOUSEMOVE and self.mouse_pressed:
            if self.mouse_last_x >= 0 and self.mouse_last_y >= 0:
                dx = x - self.mouse_last_x
                dy = y - self.mouse_last_y
                
                # 更新视角角度
                self.yaw += dx * 0.5  # 水平移动控制左右旋转
                self.pitch += dy * 0.5  # 垂直移动控制上下旋转
                
                # 限制俯仰角范围
                self.pitch = np.clip(self.pitch, -89, 89)
                
                self.mouse_last_x = x
                self.mouse_last_y = y
        elif event == cv2.EVENT_MOUSEMOVE and self.mouse_right_pressed:
            if self.mouse_last_x >= 0 and self.mouse_last_y >= 0:
                dx = x - self.mouse_last_x
                dy = y - self.mouse_last_y
                
                # 获取当前 c2w 矩阵
                current_c2w = self._get_current_c2w()
                
                # 提取右向量（X 轴）和上向量（Y 轴）
                right_vec = current_c2w[:3, 0]  # 相机坐标系的 X 轴
                up_vec = current_c2w[:3, 1]     # 相机坐标系的 Y 轴
                
                # 计算平移量（根据屏幕移动方向和距离）
                move_speed = 0.01 * self.radius  # 移动速度与当前距离成正比
                translate = -right_vec * dx * move_speed + up_vec * dy * move_speed
                
                # 更新相机位置
                current_c2w[:3, 3] += translate
                
                # 将更新后的位置保存回参考视角
                ref_c2w = torch.inverse(self.views[self.current_view_idx].world_view_transform.T)
                ref_c2w[:3, 3] = current_c2w[:3, 3]
                
                self.mouse_last_x = x
                self.mouse_last_y = y
        elif event == cv2.EVENT_MOUSEWHEEL:
            # 滚轮缩放：检测滚动方向
            # flags 的高 16 位表示滚动量，正数表示向上滚动，负数表示向下滚动
            delta = (flags >> 16) & 0xFFFF
            
            # 处理有符号数：如果 delta > 32767，说明是负数（向下滚动）
            if delta > 32767:
                delta = delta - 65536  # 转换为负数
            
            if delta > 0:
                # 向上滚动 - 拉近视角（缩小距离）
                self.radius *= 0.9
            else:
                # 向下滚动 - 拉远视角（放大距离）
                self.radius *= 1.1
    
    def _get_current_c2w(self) -> torch.Tensor:
        """
        根据当前视角参数计算相机外参（c2w）
        
        Returns:
            4x4 的 c2w 矩阵
        """
        # 获取参考视角的 c2w
        ref_c2w = torch.inverse(self.views[self.current_view_idx].world_view_transform.T)
        
        # 应用用户控制的旋转
        yaw_rad = np.deg2rad(self.yaw)
        pitch_rad = np.deg2rad(self.pitch)
        
        # 绕 Y 轴旋转（yaw）
        rot_y = torch.tensor([
            [np.cos(yaw_rad), 0, np.sin(yaw_rad), 0],
            [0, 1, 0, 0],
            [-np.sin(yaw_rad), 0, np.cos(yaw_rad), 0],
            [0, 0, 0, 1]
        ], dtype=torch.float32).cuda()
        
        # 绕 X 轴旋转（pitch）
        rot_x = torch.tensor([
            [1, 0, 0, 0],
            [0, np.cos(pitch_rad), -np.sin(pitch_rad), 0],
            [0, np.sin(pitch_rad), np.cos(pitch_rad), 0],
            [0, 0, 0, 1]
        ], dtype=torch.float32).cuda()
        
        # 组合旋转
        rotation = rot_y @ rot_x
        
        # 应用旋转到参考 c2w
        current_c2w = ref_c2w @ rotation
        current_c2w[:3, 3] *= self.radius  # 应用距离缩放
        
        return current_c2w
    
    def _create_camera_from_c2w(self, c2w: torch.Tensor) -> Camera:
        """
        从 c2w 矩阵创建虚拟相机
        
        Args:
            c2w: 4x4 的相机外参矩阵
            
        Returns:
            Camera 对象
        """
        # 提取 R 和 T
        R = c2w[:3, :3].T.cpu().numpy()  # 注意转置
        T = c2w[:3, 3].cpu().numpy()
        
        # 创建虚拟图像（用于占位）
        dummy_image = torch.ones((3, self.H, self.W), dtype=torch.float32).cuda()
        
        # 创建相机
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
        """
        应用 PBR 重光照效果
        
        Args:
            rendering_result: 渲染结果字典
            c2w: 当前相机的 c2w 矩阵
            
        Returns:
            重新打光后的 RGB 图像 [3, H, W]
        """
        # 提取 PBR 材质参数
        albedo_map = rendering_result["albedo_map"]  # [3, H, W]
        roughness_map = rendering_result["roughness_map"]  # [1, H, W]
        metallic_map = rendering_result["metallic_map"]  # [1, H, W]
        normal_map = rendering_result["normal_map"]  # [3, H, W]
        depth_map = rendering_result["depth_map"]  # [1, H, W]
        normal_mask = rendering_result["normal_mask"]  # [1, H, W]
        
        # 计算视线方向
        canonical_rays = self._get_canonical_rays()
        view_dirs = -(
            (F.normalize(canonical_rays[:, None, :], p=2, dim=-1) * c2w[None, :3, :3])
            .sum(dim=-1)
            .reshape(self.H, self.W, 3)
        )  # [H, W, 3]
        
        # 计算 3D 点位置
        norm = torch.norm(canonical_rays, p=2, dim=-1).reshape(self.H, self.W, 1)
        points = (
            -view_dirs.reshape(-1, 3) * norm.reshape(-1, 1) * depth_map.reshape(-1, 1) + c2w[:3, 3]
        ).contiguous().reshape(self.H, self.W, 3)  # [H, W, 3]
        
        # 应用 PBR 着色
        pbr_result = self._light_pbr_shading(
            light_position=self.light_position,
            light_intensity=self.light_intensity,
            points=points,
            normals=normal_map.permute(1, 2, 0),  # [H, W, 3]
            view_dirs=view_dirs,
            mask=normal_mask.permute(1, 2, 0),  # [H, W, 1]
            albedo=albedo_map.permute(1, 2, 0),  # [H, W, 3]
            roughness=roughness_map.permute(1, 2, 0),  # [H, W, 1]
            metallic=metallic_map.permute(1, 2, 0),  # [H, W, 1]
            linear=False,
        )
        
        return pbr_result["render_rgb"].permute(2, 0, 1)  # [3, H, W]
    
    def _get_canonical_rays(self) -> torch.Tensor:
        """获取标准光线"""
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
        """
        PBR 着色函数（基于 Cook-Torrance BRDF）
        """
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
    
    def render_current_view(self) -> np.ndarray:
        """
        渲染当前视角的图像
        
        Returns:
            BGR 格式的 numpy 数组（OpenCV 格式）
        """
        # 获取当前 c2w
        c2w = self._get_current_c2w()
        
        # 创建虚拟相机
        viewpoint_camera = self._create_camera_from_c2w(c2w)
        
        # 简单的 pipeline 配置
        class SimplePipe:
            debug = False
            convert_SHs_python = False
            compute_cov3D_python = False
        
        pipe = SimplePipe()
        
        # 执行渲染
        rendering_result = render(
            viewpoint_camera=viewpoint_camera,
            pc=self.gaussians,
            pipe=pipe,
            bg_color=torch.tensor([0.0, 0.0, 0.0], dtype=torch.float32).cuda(),
            inference=True,
            pad_normal=True,
            derive_normal=True,
        )
        
        if self.enable_pbr:
            # 使用 PBR 重光照
            render_rgb = self._apply_pbr_relighting(rendering_result, c2w)
        else:
            # 使用原始渲染结果
            render_rgb = rendering_result["render"]  # [3, H, W]
        
        # 转换为 0-255 的 numpy 数组
        render_rgb = render_rgb.detach().permute(1, 2, 0).clamp(0.0, 1.0).cpu().numpy()
        render_rgb = (render_rgb * 255).astype(np.uint8)
        
        # RGB 转 BGR（OpenCV 格式）
        render_bgr = cv2.cvtColor(render_rgb, cv2.COLOR_RGB2BGR)
        
        return render_bgr
    
    def show_fps(self, image: np.ndarray, fps: float) -> np.ndarray:
        """在图像上显示 FPS"""
        text = f"FPS: {fps:.1f}"
        cv2.putText(image, text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        
        info_text = f"View: {self.current_view_idx} | Yaw: {self.yaw:.1f}° | Pitch: {self.pitch:.1f}° | Radius: {self.radius:.2f}"
        cv2.putText(image, info_text, (10, self.H - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 1)
        
        return image
    
    def run(self):
        """运行实时查看器主循环"""
        print("[RealtimeViewer] 启动渲染循环...")
        
        frame_count = 0
        start_time = cv2.getTickCount()
        fps = 0.0
        
        while self.running:
            # 自动旋转
            if self.auto_rotate:
                self.yaw += 0.3
            
            # 渲染当前帧
            frame = self.render_current_view()
            
            # 计算 FPS
            frame_count += 1
            current_time = cv2.getTickCount()
            elapsed_time = (current_time - start_time) / cv2.getTickFrequency()
            if elapsed_time >= 1.0:
                fps = frame_count / elapsed_time
                frame_count = 0
                start_time = current_time
            
            # 显示 FPS
            frame = self.show_fps(frame, fps)
            
            # 显示图像
            cv2.imshow(self.window_name, frame)
            
            # 处理键盘输入
            key = cv2.waitKey(self.key_delay) & 0xFF
            if key == ord('q') or key == ord('Q'):
                self.running = False
            elif key == ord('r') or key == ord('R'):
                # 重置视角
                self.yaw = 0.0
                self.pitch = 0.0
                self.radius = 1.0
            elif key == ord(' '):
                # 切换自动旋转
                self.auto_rotate = not self.auto_rotate
                print(f"[RealtimeViewer] 自动旋转：{'开启' if self.auto_rotate else '关闭'}")
            elif key == ord('w') or key == ord('W'):
                self.current_view_idx = (self.current_view_idx + 1) % len(self.views)
                print(f"[RealtimeViewer] 切换到视角 {self.current_view_idx}")
            elif key == ord('s') or key == ord('S'):
                self.current_view_idx = (self.current_view_idx - 1) % len(self.views)
                print(f"[RealtimeViewer] 切换到视角 {self.current_view_idx}")
            elif key == ord('a') or key == ord('A'):
                self.radius *= 0.9
            elif key == ord('d') or key == ord('D'):
                self.radius /= 0.9
            elif key == ord('p') or key == ord('P'):
                # 切换 PBR 重光照
                self.enable_pbr = not self.enable_pbr
                print(f"[RealtimeViewer] PBR 重光照：{'开启' if self.enable_pbr else '关闭'}")
            elif key == ord('1'):
                # 光源上移
                self.light_position[1] += 0.5
            elif key == ord('2'):
                # 光源下移
                self.light_position[1] -= 0.5
            elif key == ord('3'):
                # 光源左移
                self.light_position[0] -= 0.5
            elif key == ord('4'):
                # 光源右移
                self.light_position[0] += 0.5
            elif key == ord('5'):
                # 光源前移
                self.light_position[2] += 0.5
            elif key == ord('6'):
                # 光源后移
                self.light_position[2] -= 0.5
            elif key == 27:  # ESC
                self.running = False
        
        cv2.destroyAllWindows()
        print("[RealtimeViewer] 查看器已关闭")


def main():
    # 设置命令行参数解析器
    parser = ArgumentParser(description="实时高斯模型查看器")
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
    
    # 创建并运行查看器
    viewer = RealtimeViewer(
        model_path=model_path,
        checkpoint=args.checkpoint,
        dataset=model.extract(args),
        pipeline=pipeline.extract(args),
        resolution_scale=args.resolution_scale,
    )
    
    viewer.run()


if __name__ == "__main__":
    main()
