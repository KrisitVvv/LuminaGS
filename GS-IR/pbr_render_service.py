"""
PBR 渲染服务 - 为 Electron 前端提供实时 PBR 渲染能力
支持加载 .pth checkpoint 并执行实时 PBR 着色计算
"""

import os
import sys
import json
import math  # 添加 math 模块用于三角函数计算
import torch
import torch.nn.functional as F
import numpy as np
from typing import Dict, List, Optional, Tuple
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import cv2
import base64
from io import BytesIO
from PIL import Image

# 添加 GS-IR 到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../GS-IR'))

from gaussian_renderer import GaussianModel, render
from gs_ir import IrradianceVolumes
from pbr import CubemapLight, get_brdf_lut, pbr_shading
from scene import Scene
from utils.image_utils import turbo_cmap
import nvdiffrast.torch as dr
from diff_gaussian_rasterization import _C
from utils.graphics_utils import getProjectionMatrix


app = Flask(__name__)
# 配置 CORS，允许所有来源和所有方法
CORS(app, resources={r"/api/*": {"origins": "*", "methods": ["GET", "POST", "OPTIONS"]}})

def saturate_dot(a: torch.Tensor, b: torch.Tensor) -> torch.Tensor:
    """安全的点积，确保结果在 [0, 1] 范围"""
    return (a * b).sum(dim=-1, keepdim=True).clamp(min=0.0, max=1.0)


def DistributionGGX(
    normals: torch.Tensor,
    half_dirs: torch.Tensor,
    roughness: torch.Tensor,
) -> torch.Tensor:
    """GGX 法线分布函数"""
    a = roughness * roughness
    a2 = a * a
    NoH = saturate_dot(normals, half_dirs)
    NoH2 = NoH * NoH
    
    nom = a2
    denom = (NoH2 * (a2 - 1.0) + 1.0)
    denom = np.pi * denom * denom
    
    return nom / denom


def GeometrySchlickGGX(
    NoV: torch.Tensor,
    roughness: torch.Tensor,
) -> torch.Tensor:
    """GGX 几何遮挡项（Schlick 近似）"""
    r = roughness + 1.0
    k = (r * r) / 8.0
    nom = NoV
    denom = NoV * (1.0 - k) + k
    
    return nom / denom


def GeometrySmith(
    normals: torch.Tensor,
    view_dirs: torch.Tensor,
    light_dirs: torch.Tensor,
    roughness: torch.Tensor,
) -> torch.Tensor:
    """Smith 几何遮挡（双向）"""
    NoV = saturate_dot(normals, view_dirs)
    NoL = saturate_dot(normals, light_dirs)
    ggx2 = GeometrySchlickGGX(NoV, roughness)
    ggx1 = GeometrySchlickGGX(NoL, roughness)
    
    return ggx1 * ggx2


def fresnelSchlick(
    HoV: torch.Tensor,
    F0: torch.Tensor,
) -> torch.Tensor:
    """Schlick 菲涅尔近似"""
    return F0 + (1.0 - F0) * torch.pow((1.0 - HoV).clamp(0.0, 1.0), 5)


def get_canonical_rays(H: int, W: int, tan_fovx: float, tan_fovy: float) -> torch.Tensor:
    """获取标准相机射线"""
    cen_x = W / 2
    cen_y = H / 2
    focal_x = W / (2.0 * tan_fovx)
    focal_y = H / (2.0 * tan_fovy)
    
    x, y = torch.meshgrid(
        torch.arange(W),
        torch.arange(H),
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
    return camera_dirs.cuda()


def getWorld2ViewTorch(R: torch.Tensor, t: torch.Tensor) -> torch.Tensor:
    """构造世界到视图的变换矩阵"""
    Rt = torch.zeros((4, 4), device=R.device)
    Rt[:3, :3] = R[:3, :3].T
    Rt[:3, 3] = t
    Rt[3, 3] = 1.0
    return Rt


def get_depth_cubemap(
    gaussians: GaussianModel, position: torch.Tensor, res: int = 512
) -> torch.Tensor:
    """
    从光源位置生成深度立方体贴图
    
    Args:
        gaussians: 高斯模型
        position: 光源位置 [3]
        res: 每个面的分辨率（默认 512 以降低实时开销）
    
    Returns:
        depth_cubemap: [6, res, res, 1]
    """
    canonical_rays = get_canonical_rays(H=res, W=res, tan_fovx=1.0, tan_fovy=1.0)
    norm = torch.norm(canonical_rays, p=2, dim=-1).reshape(res, res, 1)
    
    bg_color = torch.zeros([3, res, res], device="cuda")
    
    # 6 个方向的旋转矩阵
    rotations = [
        torch.tensor([[0.0, 0.0, 1.0, 0.0], [0.0, -1.0, 0.0, 0.0], [-1.0, 0.0, 0.0, 0.0], [0.0, 0.0, 0.0, 1.0]]).cuda(),
        torch.tensor([[0.0, 0.0, -1.0, 0.0], [0.0, -1.0, 0.0, 0.0], [1.0, 0.0, 0.0, 0.0], [0.0, 0.0, 0.0, 1.0]]).cuda(),
        torch.tensor([[1.0, 0.0, 0.0, 0.0], [0.0, 0.0, 1.0, 0.0], [0.0, 1.0, 0.0, 0.0], [0.0, 0.0, 0.0, 1.0]]).cuda(),
        torch.tensor([[1.0, 0.0, 0.0, 0.0], [0.0, 0.0, -1.0, 0.0], [0.0, -1.0, 0.0, 0.0], [0.0, 0.0, 0.0, 1.0]]).cuda(),
        torch.tensor([[1.0, 0.0, 0.0, 0.0], [0.0, -1.0, 0.0, 0.0], [0.0, 0.0, 1.0, 0.0], [0.0, 0.0, 0.0, 1.0]]).cuda(),
        torch.tensor([[-1.0, 0.0, 0.0, 0.0], [0.0, -1.0, 0.0, 0.0], [0.0, 0.0, -1.0, 0.0], [0.0, 0.0, 0.0, 1.0]]).cuda(),
    ]
    
    zfar = 100.0
    znear = 0.01
    projection_matrix = getProjectionMatrix(znear=znear, zfar=zfar, fovX=np.pi * 0.5, fovY=np.pi * 0.5).transpose(0, 1).cuda()
    
    depth_cubemap = []
    for rotation in rotations:
        c2w = rotation.clone()
        c2w[:3, 3] = position
        w2c = torch.inverse(c2w)
        T = w2c[:3, 3]
        R = w2c[:3, :3].T
        world_view_transform = getWorld2ViewTorch(R, T).transpose(0, 1)
        full_proj_transform = (world_view_transform.unsqueeze(0).bmm(projection_matrix.unsqueeze(0))).squeeze(0)
        camera_center = world_view_transform.inverse()[3, :3]
        
        # 准备高斯参数
        xyz = gaussians.get_xyz.detach().cuda()
        opacity = gaussians.get_opacity.detach().cuda()
        scaling = gaussians.get_scaling.detach().cuda()
        rotation_feat = gaussians.get_rotation.detach().cuda()
        features = gaussians.get_features.detach().cuda()
        if len(features.shape) >= 2:
            features = features[:, 0]
        if len(features.shape) == 1:
            features = features.unsqueeze(-1).repeat(1, 3)
        
        empty_tensor = torch.Tensor([]).cuda()
        
        input_args = (
            bg_color, xyz, empty_tensor, opacity, scaling, rotation_feat,
            empty_tensor, features, camera_center, world_view_transform,
            full_proj_transform, 1.0, 1.0, 1.0, res, res,
            gaussians.active_sh_degree, False, False
        )
        
        (_, _, _, _, depth_map) = _C.lite_rasterize_gaussians(*input_args)
        depth_cubemap.append(depth_map.permute(1, 2, 0))
    
    return torch.stack(depth_cubemap)

# 深度立方体贴图缓存（性能优化）
depth_cubemap_cache = None
last_light_position = None


def load_checkpoint(checkpoint_path: str) -> Dict:
    """加载 .pth checkpoint 文件"""
    global current_checkpoint, gaussians, scene, cubemap, irradiance_volumes, brdf_lut, canonical_rays
    
    print(f"[PBR Service] 开始加载 checkpoint: {checkpoint_path}")
    
    # 从 checkpoint 路径推导 model_path
    model_path = os.path.dirname(checkpoint_path)
    print(f"[PBR Service] Model path: {model_path}")
    
    # 初始化高斯模型
    gaussians = GaussianModel(sh_degree=4)
    
    # 对于 PBR 渲染服务，我们不需要完整的 Scene 对象
    # 只需要创建一个简单的命名空间来保存必要信息
    class SimpleNamespace:
        def __init__(self, model_path):
            self.model_path = model_path
            self.cameras_extent = 1.0  # 默认值
            
        def get_canonical_rays(self):
            # 这个方法会在 render() 中被调用，返回 None
            # 实际的 rays 会在 render 函数中根据相机参数计算
            return None
    
    scene = SimpleNamespace(model_path)
    print("[PBR Service] ✓ 使用简化版 Scene 对象")
    
    # 初始化光照组件
    cubemap = CubemapLight(base_res=256).cuda()
    aabb = torch.tensor([-1.5, -1.5, -1.5, 1.5, 1.5, 1.5]).cuda()
    irradiance_volumes = IrradianceVolumes(aabb=aabb).cuda()
    
    # 加载 checkpoint
    checkpoint = torch.load(checkpoint_path, map_location='cuda')
    
    # 恢复高斯参数
    model_params = checkpoint["gaussians"]
    gaussians.restore(model_params)
    
    # 恢复光照参数
    if "cubemap" in checkpoint:
        cubemap.load_state_dict(checkpoint["cubemap"])
    
    if "irradiance_volumes" in checkpoint:
        irradiance_volumes.load_state_dict(checkpoint["irradiance_volumes"])
    
    # 构建光照 MIP
    cubemap.build_mips()
    
    # 加载 BRDF LUT
    brdf_lut = get_brdf_lut().cuda()
    
    # 尝试加载 occlusion volumes
    occlusion_path = os.path.join(os.path.dirname(checkpoint_path), "occlusion_volumes.pth")
    if os.path.exists(occlusion_path):
        occlusion_volumes = torch.load(occlusion_path)
        print(f"[PBR Service] ✓ 已加载 occlusion volumes")
    else:
        occlusion_volumes = None
        print(f"[PBR Service] ⚠ 未找到 occlusion volumes")
    
    current_checkpoint = checkpoint_path
    print(f"[PBR Service] ✓ Checkpoint 加载完成")
    
    return {
        "success": True,
        "message": "Checkpoint loaded successfully",
        "num_gaussians": gaussians.get_xyz.shape[0],
        "sh_degree": gaussians.active_sh_degree
    }


def encode_image_to_base64(image: np.ndarray) -> str:
    """将 numpy 图像数组转换为 base64 字符串"""
    _, buffer = cv2.imencode('.png', image)
    return base64.b64encode(buffer).decode('utf-8')


def linear_to_srgb(linear):
    """线性空间转 sRGB"""
    if isinstance(linear, torch.Tensor):
        eps = torch.finfo(torch.float32).eps
        srgb0 = 323 / 25 * linear
        srgb1 = (211 * torch.clamp(linear, min=eps) ** (5 / 12) - 11) / 200
        return torch.where(linear <= 0.0031308, srgb0, srgb1)
    elif isinstance(linear, np.ndarray):
        eps = np.finfo(np.float32).eps
        srgb0 = 323 / 25 * linear
        srgb1 = (211 * np.maximum(eps, linear) ** (5 / 12) - 11) / 200
        return np.where(linear <= 0.0031308, srgb0, srgb1)
    else:
        raise NotImplementedError


def light_pbr_shading_with_shadow(
    light_position: torch.Tensor,
    light_intensity: torch.Tensor,
    points: torch.Tensor,
    normals: torch.Tensor,
    view_dirs: torch.Tensor,
    albedo: torch.Tensor,
    roughness: torch.Tensor,
    mask: torch.Tensor,
    gaussians: GaussianModel,
    linear: bool = False,
    metallic: Optional[torch.Tensor] = None,
    shadow_enabled: bool = True,
    background: Optional[torch.Tensor] = None,
) -> Dict:
    """
    带实时阴影的 PBR 着色函数（集成 light_move.py 核心算法）
    
    Args:
        light_position: 光源位置 [3]
        light_intensity: 光源强度 [3]
        points: 3D 点位置 [H, W, 3]
        normals: 法线 [H, W, 3]
        view_dirs: 视线方向 [H, W, 3]
        albedo: 反照率 [H, W, 3]
        roughness: 粗糙度 [H, W, 1]
        mask: 有效掩码 [H, W, 1]
        gaussians: 高斯模型（用于深度立方体贴图生成）
        linear: 是否应用 sRGB 转换
        metallic: 金属度贴图（可选）[H, W, 1]
        shadow_enabled: 是否启用阴影
        background: 背景颜色（可选）
    
    Returns:
        render_rgb: 渲染结果 [H, W, 3] 或 [3, H, W]（取决于 linear 参数）
    """
    global depth_cubemap_cache, last_light_position
    
    H, W, _ = points.shape
    
    # 计算光源方向和衰减
    light_dirs = F.normalize(light_position - points, p=2, dim=-1)
    half_dirs = (light_dirs + view_dirs) / 2.0
    distance = torch.norm(light_position - points, p=2, dim=-1, keepdim=True)
    attenuation = 1.0 / torch.pow(distance, 2)
    radiance = light_intensity * attenuation
    
    # 计算基础反射率 F0
    if metallic is None:
        F0 = torch.ones_like(albedo) * 0.04
    else:
        F0 = (1.0 - metallic) * 0.04 + albedo * metallic
    
    # Cook-Torrance BRDF
    NoV = saturate_dot(normals, view_dirs)
    NoL = saturate_dot(normals, light_dirs)
    HoV = saturate_dot(half_dirs, view_dirs)
    NDF = DistributionGGX(normals=normals, half_dirs=half_dirs, roughness=roughness)
    G = GeometrySmith(normals=normals, view_dirs=view_dirs, light_dirs=light_dirs, roughness=roughness)
    fresnel = fresnelSchlick(HoV=HoV, F0=F0)
    
    numerator = NDF * G * fresnel
    denominator = 4.0 * NoV * NoL + 1e-4
    specular = numerator / denominator
    
    kd = 1.0 - fresnel
    if metallic is not None:
        kd *= (1.0 - metallic)
    
    render_rgb = (kd * albedo / np.pi + specular) * radiance * NoL
    render_rgb = torch.where(mask, render_rgb, torch.zeros_like(render_rgb) if background is None else background)
    
    # ========== 核心阴影计算 ==========
    if shadow_enabled:
        # 检查是否需要重新生成深度立方体贴图
        regenerate = True
        if depth_cubemap_cache is not None and last_light_position is not None:
            # 如果光源移动距离小于阈值，复用缓存
            dist = torch.norm(light_position - last_light_position).item()
            if dist < 0.01:
                regenerate = False
        
        if regenerate:
            print(f"[PBR Service] 生成深度立方体贴图...")
            depth_cubemap = get_depth_cubemap(gaussians=gaussians, position=light_position, res=512)
            depth_cubemap_cache = depth_cubemap
            last_light_position = light_position.clone()
        else:
            depth_cubemap = depth_cubemap_cache
        
        # 查询从点到光源方向的深度
        to_light = F.normalize(light_position - points, p=2, dim=-1)
        closest_depth = dr.texture(
            depth_cubemap[None, ...],
            to_light[None, ...].contiguous(),
            filter_mode="linear",
            boundary_mode="cube",
        )[0]
        
        # 阴影判断：如果点到光源的距离大于最近遮挡物距离 + 阈值，则在阴影中
        threshold = 2.0
        shadow = (distance - threshold > closest_depth).float()
        
        # 应用阴影：阴影区域亮度降低到 20%
        render_rgb = torch.where(shadow == 0.0, render_rgb, render_rgb * 0.2)
    
    # sRGB 转换
    if linear:
        render_rgb = linear_to_srgb(render_rgb.squeeze())
    
    return {"render_rgb": render_rgb}


@app.route('/api/health', methods=['GET'])
def health_check():
    """健康检查接口"""
    return jsonify({
        "status": "ok",
        "service": "PBR Render Service",
        "loaded": current_checkpoint is not None
    })


@app.route('/api/get_gaussian_data', methods=['POST'])
def api_get_gaussian_data():
    """
    获取高斯模型数据（用于前端 3D 加载）
    参数:
        - checkpoint_path: .pth 文件路径
    返回:
        - xyz: [N, 3] 位置
        - rotation: [N, 4] 四元数 [w, x, y, z]
        - scaling: [N, 3] 缩放
        - opacity: [N, 1] 不透明度
        - features: [N, 3] 颜色（SH 第 0 阶）
        - sh_degree: int 球谐阶数
        - num_gaussians: int 高斯数量
    """
    try:
        data = request.json
        checkpoint_path = data.get('checkpoint_path')
        
        if not checkpoint_path:
            return jsonify({"error": "Missing checkpoint_path"}), 400
        
        # 如果尚未加载，则加载 checkpoint
        if current_checkpoint != checkpoint_path:
            print(f"[PBR Service] 加载 checkpoint 以获取高斯数据：{checkpoint_path}")
            load_checkpoint(checkpoint_path)
        
        # 提取高斯参数
        xyz = gaussians.get_xyz.detach().cpu().numpy().tolist()  # [N, 3]
        rotation = gaussians.get_rotation.detach().cpu().numpy().tolist()  # [N, 4] (w, x, y, z)
        scaling = gaussians.get_scaling.detach().cpu().numpy().tolist()  # [N, 3]
        opacity = gaussians.get_opacity.detach().cpu().numpy().tolist()  # [N, 1]
        
        # 获取 SH 第 0 阶作为基础颜色
        features_dc = gaussians.get_features[:, 0].detach().cpu().numpy()  # [N, 3]
        
        print(f"[PBR Service] ✓ 返回高斯数据：{len(xyz)} 个高斯")
        
        return jsonify({
            "success": True,
            "xyz": xyz,
            "rotation": rotation,
            "scaling": scaling,
            "opacity": opacity,
            "features": features_dc.tolist(),
            "sh_degree": gaussians.active_sh_degree,
            "num_gaussians": len(xyz)
        })
    
    except Exception as e:
        print(f"[PBR Service] ❌ 获取高斯数据失败：{e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route('/api/load_checkpoint', methods=['POST'])
def api_load_checkpoint():
    """加载 checkpoint 文件"""
    try:
        data = request.json
        checkpoint_path = data.get('checkpoint_path')
        
        if not checkpoint_path:
            return jsonify({"error": "Missing checkpoint_path"}), 400
        
        result = load_checkpoint(checkpoint_path)
        return jsonify(result)
    
    except Exception as e:
        print(f"[PBR Service] 加载 checkpoint 失败：{e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/render_pbr', methods=['POST'])
def api_render_pbr():
    """
    执行 PBR 渲染（带实时阴影）
    参数:
        - viewpoint: 相机位姿 (c2w 4x4 矩阵)
        - light_position: 光源位置 [x, y, z]
        - light_intensity: 光源强度 [r, g, b]
        - metallic: 是否启用金属材质
        - indirect: 是否启用间接光照
        - shadow: 是否启用实时阴影（默认 True）
        - tone: 色调映射
        - gamma: Gamma 校正
    """
    try:
        data = request.json
        
        # 检查是否已加载 checkpoint
        if current_checkpoint is None:
            return jsonify({"error": "No checkpoint loaded"}), 400
        
        # 解析参数
        viewpoint = torch.tensor(data['viewpoint'], dtype=torch.float32).cuda()
        
        # 处理 viewpoint 可能是 1D 或 2D 的情况
        if viewpoint.dim() == 1:
            if viewpoint.shape[0] == 16:
                c2w = viewpoint.reshape(4, 4)
            else:
                return jsonify({"error": f"Invalid viewpoint shape: {viewpoint.shape}"}), 400
        elif viewpoint.dim() == 2:
            c2w = viewpoint
        else:
            return jsonify({"error": f"Invalid viewpoint dimensions: {viewpoint.dim()}"}), 400
        
        light_position = torch.tensor(data.get('light_position', [0, 0, 0]), dtype=torch.float32).cuda()
        light_intensity = torch.tensor(data.get('light_intensity', [100, 100, 100]), dtype=torch.float32).cuda()
        metallic_flag = data.get('metallic', False)
        indirect_flag = data.get('indirect', False)
        shadow_enabled = data.get('shadow', True)  # 默认启用阴影
        tone_flag = data.get('tone', False)
        gamma_flag = data.get('gamma', False)
        
        # 获取相机参数
        H, W = 512, 512
        fov_x = np.pi / 2
        fov_y = np.pi / 2
        
        # 构造虚拟相机
        from scene.cameras import Camera
        dummy_image = torch.ones((3, H, W), dtype=torch.float32).cuda()
        
        viewpoint_camera = Camera(
            colmap_id=0,
            R=c2w[:3, :3].T.cpu().numpy(),
            T=c2w[:3, 3].cpu().numpy(),
            FoVx=fov_x,
            FoVy=fov_y,
            image=dummy_image,
            gt_alpha_mask=None,
            image_name="render_view",
            uid=0
        )
        
        # 渲染高斯场景
        class SimplePipe:
            debug = False
            convert_SHs_python = False
            compute_cov3D_python = False
        
        pipe = SimplePipe()
        
        rendering_result = render(
            viewpoint_camera=viewpoint_camera,
            pc=gaussians,
            pipe=pipe,
            bg_color=torch.tensor([0, 0, 0], dtype=torch.float32).cuda(),
            inference=True,
            derive_normal=True,
            pad_normal=True
        )
        
        # 提取渲染结果
        albedo_map = rendering_result["albedo_map"]
        roughness_map = rendering_result["roughness_map"]
        metallic_map = rendering_result["metallic_map"]
        normal_map = rendering_result["normal_map"]
        depth_map = rendering_result["depth_map"]
        normal_mask = rendering_result["normal_mask"]
        
        # 计算视线方向
        y, x = torch.meshgrid(
            torch.arange(0, H, dtype=torch.float32, device='cuda'),
            torch.arange(0, W, dtype=torch.float32, device='cuda'),
            indexing='ij'
        )
        pixel_x = (x / W - 0.5) * 2
        pixel_y = (y / H - 0.5) * 2
        focal_x = W / (2 * math.tan(viewpoint_camera.FoVx * 0.5))
        focal_y = H / (2 * math.tan(viewpoint_camera.FoVy * 0.5))
        camera_dirs = torch.stack([
            pixel_x * focal_x,
            -pixel_y * focal_y,
            -torch.ones_like(pixel_x)
        ], dim=-1).reshape(-1, 3)
        canonical_rays = torch.nn.functional.normalize(camera_dirs, p=2, dim=-1)
        view_dirs = -(
            (torch.nn.functional.normalize(canonical_rays[:, None, :], p=2, dim=-1) * c2w[None, :3, :3])
            .sum(dim=-1)
            .reshape(H, W, 3)
        )
        
        # 计算 3D 点位置
        norm = torch.norm(canonical_rays, p=2, dim=-1).reshape(H, W, 1)
        points = (
            -view_dirs.reshape(-1, 3) * norm.reshape(-1, 1) * depth_map.reshape(-1, 1) + c2w[:3, 3]
        ).contiguous()
        
        # 准备 PBR 参数
        occlusion = torch.ones_like(roughness_map).permute(1, 2, 0)
        irradiance = torch.zeros_like(roughness_map).permute(1, 2, 0)
        
        # 间接光照
        if indirect_flag and occlusion_volumes is not None:
            from gs_ir import recon_occlusion
            occlusion_ids = occlusion_volumes["occlusion_ids"]
            occlusion_coefficients = occlusion_volumes["occlusion_coefficients"]
            bound = occlusion_volumes["bound"]
            occlusion_degree = occlusion_volumes["degree"]
            aabb = torch.tensor([-bound, -bound, -bound, bound, bound, bound]).cuda()
            
            occlusion = recon_occlusion(
                H=H, W=W,
                bound=bound,
                points=points.reshape(-1, 3).contiguous(),
                normals=normal_map.permute(1, 2, 0).reshape(-1, 3).contiguous(),
                occlusion_coefficients=occlusion_coefficients,
                occlusion_ids=occlusion_ids,
                aabb=aabb,
                degree=occlusion_degree
            ).reshape(H, W, 1)
            
            irradiance = irradiance_volumes.query_irradiance(
                points=points.reshape(-1, 3).contiguous(),
                normals=normal_map.permute(1, 2, 0).reshape(-1, 3).contiguous()
            ).reshape(H, W, -1)
        
        # ========== 使用带阴影的 PBR 着色函数 ==========
        pbr_result = light_pbr_shading_with_shadow(
            light_position=light_position,
            light_intensity=light_intensity,
            points=points.reshape(H, W, 3),
            normals=normal_map.permute(1, 2, 0).detach(),
            view_dirs=view_dirs,
            mask=normal_mask.permute(1, 2, 0),
            albedo=albedo_map.permute(1, 2, 0),
            roughness=roughness_map.permute(1, 2, 0),
            metallic=metallic_map.permute(1, 2, 0) if metallic_flag else None,
            gaussians=gaussians,
            linear=False,
            shadow_enabled=shadow_enabled
        )
        
        render_rgb = pbr_result["render_rgb"].permute(2, 0, 1)
        render_rgb = torch.clamp(render_rgb, 0.0, 1.0)
        
        # 转换为 numpy
        render_np = (render_rgb.detach().cpu().numpy().transpose(1, 2, 0) * 255).astype(np.uint8)
        render_bgr = cv2.cvtColor(render_np, cv2.COLOR_RGB2BGR)
        base64_image = encode_image_to_base64(render_bgr)
        
        return jsonify({
            "success": True,
            "image_base64": base64_image,
            "width": W,
            "height": H,
            "shadow_generated": shadow_enabled
        })
    
    except Exception as e:
        print(f"[PBR Service] 渲染失败：{e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route('/api/update_light', methods=['POST'])
def api_update_light():
    """更新光源参数"""
    try:
        data = request.json
        light_position = torch.tensor(data.get('position', [0, 0, 0]), dtype=torch.float32).cuda()
        light_intensity = torch.tensor(data.get('intensity', [100, 100, 100]), dtype=torch.float32).cuda()
        light_color = torch.tensor(data.get('color', [1, 1, 1]), dtype=torch.float32).cuda()
        
        # 这里可以更新全局光照状态
        # 目前先返回成功
        
        return jsonify({
            "success": True,
            "message": "Light updated"
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    print("=" * 60)
    print("PBR 渲染服务启动中...")
    print("=" * 60)
    app.run(host='0.0.0.0', port=5000, debug=False)
