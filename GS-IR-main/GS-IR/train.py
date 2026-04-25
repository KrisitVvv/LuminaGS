import os
os.environ["PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION"] = "python"
import sys
import uuid
from argparse import ArgumentParser, Namespace
from random import randint
from typing import Dict, List, Optional, Tuple, Union

import kornia
import numpy as np
import nvdiffrast.torch as dr
import torch
import torch.nn.functional as F
import torchvision.transforms as T
from tqdm import tqdm, trange

from arguments import GroupParams, ModelParams, OptimizationParams, PipelineParams
from gaussian_renderer import render
from gs_ir import recon_occlusion, IrradianceVolumes
from pbr import CubemapLight, get_brdf_lut, pbr_shading
from scene import GaussianModel, Scene, Camera
from utils.general_utils import safe_state
from utils.image_utils import psnr, turbo_cmap, normal_angle_error_map, save_angle_error_heatmap
from utils.loss_utils import l1_loss, ssim

try:
    from torch.utils.tensorboard import SummaryWriter

    TENSORBOARD_FOUND = True
except ImportError:
    TENSORBOARD_FOUND = False


def get_tv_loss(
    gt_image: torch.Tensor,  # [3, H, W]
    prediction: torch.Tensor,  # [C, H, W]
    pad: int = 1,
    step: int = 1,
) -> torch.Tensor:
    if pad > 1:
        gt_image = F.avg_pool2d(gt_image, pad, pad)
        prediction = F.avg_pool2d(prediction, pad, pad)
    rgb_grad_h = torch.exp(
        -(gt_image[:, 1:, :] - gt_image[:, :-1, :]).abs().mean(dim=0, keepdim=True)
    )  # [1, H-1, W]
    rgb_grad_w = torch.exp(
        -(gt_image[:, :, 1:] - gt_image[:, :, :-1]).abs().mean(dim=0, keepdim=True)
    )  # [1, H-1, W]
    tv_h = torch.pow(prediction[:, 1:, :] - prediction[:, :-1, :], 2)  # [C, H-1, W]
    tv_w = torch.pow(prediction[:, :, 1:] - prediction[:, :, :-1], 2)  # [C, H, W-1]
    tv_loss = (tv_h * rgb_grad_h).mean() + (tv_w * rgb_grad_w).mean()

    if step > 1:
        for s in range(2, step + 1):
            rgb_grad_h = torch.exp(
                -(gt_image[:, s:, :] - gt_image[:, :-s, :]).abs().mean(dim=0, keepdim=True)
            )  # [1, H-1, W]
            rgb_grad_w = torch.exp(
                -(gt_image[:, :, s:] - gt_image[:, :, :-s]).abs().mean(dim=0, keepdim=True)
            )  # [1, H-1, W]
            tv_h = torch.pow(prediction[:, s:, :] - prediction[:, :-s, :], 2)  # [C, H-1, W]
            tv_w = torch.pow(prediction[:, :, s:] - prediction[:, :, :-s], 2)  # [C, H, W-1]
            tv_loss += (tv_h * rgb_grad_h).mean() + (tv_w * rgb_grad_w).mean()

    return tv_loss


def get_perfect_adaptive_tv_loss(
    gt_image: torch.Tensor,        # [3, H, W] 输入RGB图像
    prediction: torch.Tensor,      # [3, H, W] 预测法线图
    base_tv_weight: float = 1.0,   # 【保持默认1.0，因为normal_tv已经是0.3】
    detail_min_weight: float = 0.02, # 【从0.05降到0.02，进一步保留微小凸点】
    flat_max_weight: float = 1.0,  # 平坦区域的最大TV权重
    detail_threshold: float = 0.015, # 【从0.02降到0.015，更多区域被识别为细节】
    transition_smoothness: float = 0.005, # 过渡区域的平滑度
) -> torch.Tensor:
    """
    完美自适应TV损失（最终修正版）：
    1. 自动识别细节区域 vs 平坦区域
    2. 细节区域：TV权重很小，保留细节
    3. 平坦区域：TV权重很大，抑制噪点
    4. 过渡区域：平滑过渡，无明显边界
    5. 【关键修正】删除重复的exp(-rgb_grad)权重，让自适应权重完全主导
    """
    # 1. 计算RGB图像的梯度（用于判断细节）
    rgb_grad_h = gt_image[:, 1:, :] - gt_image[:, :-1, :]  # [3, H-1, W]
    rgb_grad_h = rgb_grad_h.abs().mean(dim=0, keepdim=True)  # [1, H-1, W]
    
    rgb_grad_w = gt_image[:, :, 1:] - gt_image[:, :, :-1]  # [3, H, W-1]
    rgb_grad_w = rgb_grad_w.abs().mean(dim=0, keepdim=True)  # [1, H, W-1]
    
    # 2. 自动识别细节区域 vs 平坦区域 (Sigmoid平滑过渡)
    adaptive_weight_h = torch.sigmoid(-(rgb_grad_h - detail_threshold) / transition_smoothness)
    adaptive_weight_h = detail_min_weight + (flat_max_weight - detail_min_weight) * adaptive_weight_h
    
    adaptive_weight_w = torch.sigmoid(-(rgb_grad_w - detail_threshold) / transition_smoothness)
    adaptive_weight_w = detail_min_weight + (flat_max_weight - detail_min_weight) * adaptive_weight_w
    
    # 4. 计算预测法线的梯度
    tv_h = torch.pow(prediction[:, 1:, :] - prediction[:, :-1, :], 2)  # [3, H-1, W]
    tv_w = torch.pow(prediction[:, :, 1:] - prediction[:, :, :-1], 2)  # [3, H, W-1]
    
    # 5. 【关键修正】仅保留自适应权重 × base_tv_weight
    final_weight_h = adaptive_weight_h * base_tv_weight
    final_weight_w = adaptive_weight_w * base_tv_weight
    
    tv_loss = (tv_h * final_weight_h).mean() + (tv_w * final_weight_w).mean()
    return tv_loss


def save_adaptive_weight_map(
    adaptive_weight_h: torch.Tensor,  # [1, H-1, W]
    adaptive_weight_w: torch.Tensor,  # [1, H, W-1]
    save_path: str = "adaptive_weight_vis.png"
):
    """
    保存自适应权重图，用于调试：
    - 蓝色：细节区域（权重小）
    - 红色：平坦区域（权重大）
    """
    import matplotlib.pyplot as plt
    H, W = adaptive_weight_h.shape[1] + 1, adaptive_weight_h.shape[2]
    weight_map = torch.zeros((1, H, W), device=adaptive_weight_h.device)
    weight_map[:, :-1, :] = adaptive_weight_h
    weight_map[:, :, :-1] = torch.max(weight_map[:, :, :-1], adaptive_weight_w)
    weight_map = (weight_map - weight_map.min()) / (weight_map.max() - weight_map.min() + 1e-6)
    weight_map_np = weight_map.squeeze().cpu().numpy()
    
    plt.imshow(weight_map_np, cmap='jet')
    plt.colorbar(label='Adaptive TV Weight')
    plt.savefig(save_path)
    plt.close()


def get_masked_tv_loss(
    mask: torch.Tensor,  # [1, H, W]
    gt_image: torch.Tensor,  # [3, H, W]
    prediction: torch.Tensor,  # [C, H, W]
    erosion: bool = False,
) -> torch.Tensor:
    rgb_grad_h = torch.exp(
        -(gt_image[:, 1:, :] - gt_image[:, :-1, :]).abs().mean(dim=0, keepdim=True)
    )  # [1, H-1, W]
    rgb_grad_w = torch.exp(
        -(gt_image[:, :, 1:] - gt_image[:, :, :-1]).abs().mean(dim=0, keepdim=True)
    )  # [1, H-1, W]
    tv_h = torch.pow(prediction[:, 1:, :] - prediction[:, :-1, :], 2)  # [C, H-1, W]
    tv_w = torch.pow(prediction[:, :, 1:] - prediction[:, :, :-1], 2)  # [C, H, W-1]

    # erode mask
    mask = mask.float()
    if erosion:
        kernel = mask.new_ones([7, 7])
        mask = kornia.morphology.erosion(mask[None, ...], kernel)[0]
    mask_h = mask[:, 1:, :] * mask[:, :-1, :]  # [1, H-1, W]
    mask_w = mask[:, :, 1:] * mask[:, :, :-1]  # [1, H, W-1]

    tv_loss = (tv_h * rgb_grad_h * mask_h).mean() + (tv_w * rgb_grad_w * mask_w).mean()

    return tv_loss


def get_envmap_dirs(res: List[int] = [512, 1024]) -> torch.Tensor:
    gy, gx = torch.meshgrid(
        torch.linspace(0.0 + 1.0 / res[0], 1.0 - 1.0 / res[0], res[0], device="cuda"),
        torch.linspace(-1.0 + 1.0 / res[1], 1.0 - 1.0 / res[1], res[1], device="cuda"),
        indexing="ij",
    )

    sintheta, costheta = torch.sin(gy * np.pi), torch.cos(gy * np.pi)
    sinphi, cosphi = torch.sin(gx * np.pi), torch.cos(gx * np.pi)

    reflvec = torch.stack((sintheta * sinphi, costheta, -sintheta * cosphi), dim=-1)  # [H, W, 3]
    return reflvec


def resize_tensorboard_img(
    img: torch.Tensor,  # [C, H, W]
    max_res: int = 800,
) -> torch.Tensor:
    _, H, W = img.shape
    ratio = min(max_res / H, max_res / W)
    target_size = (int(H * ratio), int(W * ratio))
    transform = T.Resize(size=target_size)
    img = transform(img)  # [C, H', W']
    return img


def training(
    dataset: GroupParams,
    opt: GroupParams,
    pipe: GroupParams,
    testing_iterations: List[int],
    saving_iterations: List[int],
    checkpoint_iterations: int,
    checkpoint_path: Optional[str] = None,
    pbr_iteration: int = 30_000,
    debug_from: int = -1,
    metallic: bool = False,
    tone: bool = False,
    gamma: bool = False,
    normal_tv_weight: float = 1.0,
    normal_loss_weight: float = 1.0,
    brdf_tv_weight: float = 1.0,
    env_tv_weight: float = 0.01,
    bound: float = 1.5,
    indirect: bool = False,
    conf_thresh: float = 0.5,
    depth_grad_thresh: float = 0.1,
    normal_loss_pixel_sampling: bool = False,
    normal_loss_sample_cap: int = 10240,
    normal_loss_sample_ratio: float = 0.2,
) -> None:
    first_iter = 0
    gaussians = GaussianModel(dataset.sh_degree)
    scene = Scene(dataset, gaussians)
    gaussians.training_setup(opt)
    tb_writer = prepare_output_and_logger(dataset)

    bg_color = [1, 1, 1] if dataset.white_background else [0, 0, 0]
    background = torch.tensor(bg_color, dtype=torch.float32, device="cuda")

    iter_start = torch.cuda.Event(enable_timing=True)
    iter_end = torch.cuda.Event(enable_timing=True)

    # NOTE: prepare for PBR
    brdf_lut = get_brdf_lut().cuda()
    envmap_dirs = get_envmap_dirs()
    cubemap = CubemapLight(base_res=256).cuda()
    cubemap.train()
    aabb = torch.tensor([-bound, -bound, -bound, bound, bound, bound]).cuda()
    irradiance_volumes = IrradianceVolumes(aabb=aabb).cuda()
    irradiance_volumes.train()
    param_groups = [
        {
            "name": "irradiance_volumes",
            "params": irradiance_volumes.parameters(),
            "lr": opt.opacity_lr,
        },
        {"name": "cubemap", "params": cubemap.parameters(), "lr": opt.opacity_lr},
    ]
    light_optimizer = torch.optim.Adam(param_groups, lr=opt.opacity_lr)

    canonical_rays = scene.get_canonical_rays()

    # load checkpoint
    if checkpoint_path:
        checkpoint = torch.load(checkpoint_path)
        model_params = checkpoint["gaussians"]
        first_iter = checkpoint["iteration"]
        # cubemap_params = checkpoint["cubemap"]
        # light_optimizer_params = checkpoint["light_optimizer"]
        # irradiance_volumes_params = checkpoint["irradiance_volumes"]

        gaussians.restore(model_params, opt)
        # cubemap.load_state_dict(cubemap_params)
        # light_optimizer.load_state_dict(light_optimizer_params)
        print(f"Load checkpoint from {checkpoint_path}")

    # define progress bar
    viewpoint_stack = None
    ema_loss_for_log = 0.0
    progress_bar = trange(first_iter, opt.iterations, desc="Training progress")  # For logging

    occlusion_volumes: Dict = {}
    occlusion_flag = True
    occlusion_ids: torch.Tensor
    occlusion_coefficients: torch.Tensor
    occlusion_degree: int
    bound: float
    aabb: torch.Tensor
    for iteration in range(first_iter + 1, opt.iterations + 1):  # the real iteration (1 shift)
        iter_start.record()

        # Every 1000 its we increase the levels of SH up to a maximum degree
        if iteration % 1000 == 0:
            gaussians.oneupSHdegree()

        # Pick a random Camera
        if not viewpoint_stack:
            viewpoint_stack = scene.getTrainCameras().copy()
        viewpoint_cam = viewpoint_stack.pop(randint(0, len(viewpoint_stack) - 1))
        try:
            c2w = torch.inverse(viewpoint_cam.world_view_transform.T)  # [4, 4]
        except:
            continue

        # Render
        if (iteration - 1) == debug_from:
            pipe.debug = True

        bg = torch.rand((3), device="cuda") if opt.random_background else background

        if iteration <= pbr_iteration:
            background = bg
        else:  # NOTE: black background for PBR
            background = torch.zeros_like(bg)
        rendering_result = render(
            viewpoint_camera=viewpoint_cam,
            pc=gaussians,
            pipe=pipe,
            bg_color=background,
            derive_normal=True,
        )
        image = rendering_result["render"]  # [3, H, W]
        viewspace_point_tensor = rendering_result["viewspace_points"]
        visibility_filter = rendering_result["visibility_filter"]
        radii = rendering_result["radii"]
        depth_map = rendering_result["depth_map"]  # [1, H, W]
        normal_map_from_depth = rendering_result["normal_map_from_depth"]  # [3, H, W]
        normal_map = rendering_result["normal_map"]  # [3, H, W]
        albedo_map = rendering_result["albedo_map"]  # [3, H, W]
        roughness_map = rendering_result["roughness_map"]  # [1, H, W]
        metallic_map = rendering_result["metallic_map"]  # [1, H, W]

        # formulate roughness
        rmax, rmin = 1.0, 0.04
        roughness_map = roughness_map * (rmax - rmin) + rmin

        # NOTE: mask normal map by view direction to avoid skip value
        H, W = viewpoint_cam.image_height, viewpoint_cam.image_width
        view_dirs = -(
            (F.normalize(canonical_rays[:, None, :], p=2, dim=-1) * c2w[None, :3, :3])  # [HW, 3, 3]
            .sum(dim=-1)
            .reshape(H, W, 3)
        )  # [H, W, 3]

        # Loss
        gt_image = viewpoint_cam.original_image.cuda()
        alpha_mask = viewpoint_cam.gt_alpha_mask.cuda()
        gt_image = (gt_image * alpha_mask + background[:, None, None] * (1.0 - alpha_mask)).clamp(0.0, 1.0)
        loss: torch.Tensor
        Ll1 = F.l1_loss(image, gt_image)
        normal_loss = 0.0
        
        # === 插入的法线坐标系诊断测试代码 ===
        if iteration == 10000:
            if hasattr(viewpoint_cam, "gt_normal") and viewpoint_cam.gt_normal is not None:
                orig_gt_normal_map = viewpoint_cam.gt_normal.cuda()
                orig_gt_normal_map = F.normalize(orig_gt_normal_map, p=2, dim=0, eps=1e-6)
                mask_diag = (viewpoint_cam.gt_alpha_mask.cuda() > 0.5).squeeze(0)
                
                normal_map_norm_diag = F.normalize(normal_map, p=2, dim=0, eps=1e-6)
                pred_normal_masked_diag = normal_map_norm_diag[:, mask_diag]

                print(f"\n[DEBUG] --- Iteration {iteration} Normal Coordinate Diagnostics ---")
                
                # (A) 纯基准 (未翻转)
                gt_pure = orig_gt_normal_map[:, mask_diag]
                loss_pure = (1.0 - torch.clamp(torch.sum(pred_normal_masked_diag * gt_pure, dim=0), -1.0, 1.0)).mean().item()
                print(f"[DEBUG] Baseline (No flip): {loss_pure:.4f}")
                
                # (B) 翻转X轴
                gt_x = orig_gt_normal_map.clone()
                gt_x[0] = -gt_x[0]
                loss_x = (1.0 - torch.clamp(torch.sum(pred_normal_masked_diag * gt_x[:, mask_diag], dim=0), -1.0, 1.0)).mean().item()
                print(f"[DEBUG] Flip X axis:      {loss_x:.4f}")
                
                # (C) 翻转Y轴
                gt_y = orig_gt_normal_map.clone()
                gt_y[1] = -gt_y[1]
                loss_y = (1.0 - torch.clamp(torch.sum(pred_normal_masked_diag * gt_y[:, mask_diag], dim=0), -1.0, 1.0)).mean().item()
                print(f"[DEBUG] Flip Y axis:      {loss_y:.4f}")
                
                # (D) 翻转Z轴
                gt_z = orig_gt_normal_map.clone()
                gt_z[2] = -gt_z[2]
                loss_z = (1.0 - torch.clamp(torch.sum(pred_normal_masked_diag * gt_z[:, mask_diag], dim=0), -1.0, 1.0)).mean().item()
                print(f"[DEBUG] Flip Z axis:      {loss_z:.4f}")
                
                # (E) 翻转X和Y轴
                gt_xy = orig_gt_normal_map.clone()
                gt_xy[0] = -gt_xy[0]
                gt_xy[1] = -gt_xy[1]
                loss_xy = (1.0 - torch.clamp(torch.sum(pred_normal_masked_diag * gt_xy[:, mask_diag], dim=0), -1.0, 1.0)).mean().item()
                print(f"[DEBUG] Flip X and Y:     {loss_xy:.4f}")

                # (F) 翻转X和Z轴
                gt_xz = orig_gt_normal_map.clone()
                gt_xz[0] = -gt_xz[0]
                gt_xz[2] = -gt_xz[2]
                loss_xz = (1.0 - torch.clamp(torch.sum(pred_normal_masked_diag * gt_xz[:, mask_diag], dim=0), -1.0, 1.0)).mean().item()
                print(f"[DEBUG] Flip X and Z:     {loss_xz:.4f}")
                
                # (G) 翻转Y和Z轴
                gt_yz = orig_gt_normal_map.clone()
                gt_yz[1] = -gt_yz[1]
                gt_yz[2] = -gt_yz[2]
                loss_yz = (1.0 - torch.clamp(torch.sum(pred_normal_masked_diag * gt_yz[:, mask_diag], dim=0), -1.0, 1.0)).mean().item()
                print(f"[DEBUG] Flip Y and Z:     {loss_yz:.4f}")

                # (H) 全局取反
                gt_inv = -orig_gt_normal_map.clone()
                loss_inv = (1.0 - torch.clamp(torch.sum(pred_normal_masked_diag * gt_inv[:, mask_diag], dim=0), -1.0, 1.0)).mean().item()
                print(f"[DEBUG] Invert all (-X,-Y,-Z): {loss_inv:.4f}")
                
                print("[DEBUG] ---------------------------------------------------------\n")
                
        if iteration <= pbr_iteration:
            loss = (1.0 - opt.lambda_dssim) * Ll1 + opt.lambda_dssim * (1.0 - ssim(image, gt_image))

            normal_map_from_depth = rendering_result["normal_map_from_depth"]
            mask = rendering_result["normal_from_depth_mask"]
            final_mask = mask.clone()  # 初始掩码：深度法线有效区域

            # ==========================================================
            # [Task 2] 提取 Marigold 置信度 (Confidence Mask) 与软权重
            # ==========================================================
            # 假设在数据加载时，conf.npy 已挂载到 viewpoint_cam.da3_normal_conf
            if hasattr(viewpoint_cam, "da3_normal_conf") and viewpoint_cam.da3_normal_conf is not None:
                # Marigold 置信度已经是 [0, 1]
                conf_map = viewpoint_cam.da3_normal_conf.cuda().squeeze(0)  # [H, W]
                # 1. 硬过滤：低于阈值的绝对不信任，避免离谱噪点
                conf_hard_mask = conf_map > conf_thresh
                final_mask = final_mask & conf_hard_mask
                # 2. 软权重：保留下来的点，根据确信程度分配 Loss 权重
                soft_weight = conf_map
            else:
                soft_weight = torch.ones_like(final_mask, dtype=torch.float32)

            # 深度梯度筛选（抑制边缘跳变）
            if hasattr(viewpoint_cam, "da3_depth") and viewpoint_cam.da3_depth is not None:
                depth = viewpoint_cam.da3_depth.cuda()
                depth_grad_h = torch.abs(depth[:, 1:, :] - depth[:, :-1, :])
                depth_grad_w = torch.abs(depth[:, :, 1:] - depth[:, :, :-1])
                depth_grad_mask = torch.ones_like(final_mask)
                depth_grad_mask[1:, :] &= (depth_grad_h.squeeze(0) < depth_grad_thresh)
                depth_grad_mask[:, 1:] &= (depth_grad_w.squeeze(0) < depth_grad_thresh)
                final_mask = final_mask & depth_grad_mask

            # 避免空掩码导致 NaN
            if not torch.any(final_mask):
                final_mask = mask
                soft_weight = torch.ones_like(final_mask, dtype=torch.float32)

            # ==========================================================
            # [Task 2 & 3] 坐标系对齐、双分量 Loss 与 渐进式调度
            # ==========================================================
            if iteration < 5000:
                # 前期（<5000迭代）：纯自监督，防止被先验强行拉扯
                normal_loss = F.l1_loss(normal_map[:, final_mask], normal_map_from_depth[:, final_mask])
            else:
                # 中后期：引入 Marigold 强先验
                self_supervised_loss = F.l1_loss(normal_map[:, final_mask], normal_map_from_depth[:, final_mask])

                if hasattr(viewpoint_cam, "gt_normal") and viewpoint_cam.gt_normal is not None:
                    marigold_normal = viewpoint_cam.gt_normal.cuda().clone()

                    # Marigold 是 +X, -Y, -Z 坐标系，翻转 Y 和 Z 对齐 GS-IR
                    marigold_normal[1, :, :] = -marigold_normal[1, :, :]
                    marigold_normal[2, :, :] = -marigold_normal[2, :, :]
                    marigold_normal = F.normalize(marigold_normal, p=2, dim=0, eps=1e-6)

                    normal_map_norm = F.normalize(normal_map, p=2, dim=0, eps=1e-6)

                    # 提取有效像素
                    pred_normal_masked = normal_map_norm[:, final_mask]  # [3, N]
                    gt_normal_masked = marigold_normal[:, final_mask]  # [3, N]
                    weight_masked = soft_weight[final_mask]  # [N]

                    # OOM 保护：可选随机像素采样，仅在有效像素过多时启用
                    if normal_loss_pixel_sampling and weight_masked.numel() > 0:
                        sample_count = int(weight_masked.numel() * normal_loss_sample_ratio)
                        sample_count = max(1, min(normal_loss_sample_cap, sample_count))
                        if sample_count < weight_masked.numel():
                            sample_idx = torch.randperm(weight_masked.numel(), device=weight_masked.device)[:sample_count]
                            pred_normal_masked = pred_normal_masked[:, sample_idx]
                            gt_normal_masked = gt_normal_masked[:, sample_idx]
                            weight_masked = weight_masked[sample_idx]

                    # GaussianPro 风格 L1 + Cosine 双分量 Loss
                    l1_err = torch.abs(pred_normal_masked - gt_normal_masked).sum(dim=0)  # [N]
                    cos_err = 1.0 - torch.clamp(
                        torch.sum(pred_normal_masked * gt_normal_masked, dim=0), -1.0, 1.0
                    )  # [N]

                    # L1 和 Cosine 权重
                    lambda_l1, lambda_cos = 0.8, 0.2
                    gt_loss = (weight_masked * (lambda_l1 * l1_err + lambda_cos * cos_err)).mean()
                else:
                    gt_loss = self_supervised_loss

                # 渐进式门控调度 (Warm-up)
                if iteration < 15000:
                    # 5000 -> 15000：先验权重从 0 线性增加到 1
                    alpha = (iteration - 5000) / 10000.0
                    normal_loss = (1.0 - alpha) * self_supervised_loss + alpha * gt_loss
                elif iteration < 25000:
                    # 15000 -> 25000：完全由 Marigold 主导
                    normal_loss = gt_loss
                else:
                    # 25000 -> 30000：衰减先验，让 RGB 光度损失接管细节
                    alpha = (30000 - iteration) / 5000.0
                    normal_loss = alpha * gt_loss + (1.0 - alpha) * self_supervised_loss

            loss += normal_loss_weight * normal_loss
            
            # 采用全新的完美自适应 TV 损失（平滑与细节保留并存）
            normal_tv_loss = get_perfect_adaptive_tv_loss(
                gt_image, 
                normal_map, 
                base_tv_weight=1.0,  # 保持1.0，因为--normal_tv已经是0.3
                detail_min_weight=0.02,  # 从0.05降到0.02，进一步保留微小凸点
                flat_max_weight=1.0,
                detail_threshold=0.015,  # 从0.02降到0.015，更多区域被识别为细节
                transition_smoothness=0.005
            )
            loss += normal_tv_loss * normal_tv_weight

            # 【新增】可选可视化调试：每5000步保存自适应权重图
            if iteration % 5000 == 0:
                with torch.no_grad():
                    rgb_grad_h = gt_image[:, 1:, :] - gt_image[:, :-1, :]
                    rgb_grad_h = rgb_grad_h.abs().mean(dim=0, keepdim=True)
                    rgb_grad_w = gt_image[:, :, 1:] - gt_image[:, :, :-1]
                    rgb_grad_w = rgb_grad_w.abs().mean(dim=0, keepdim=True)
                    
                    adaptive_weight_h = torch.sigmoid(-(rgb_grad_h - 0.015) / 0.005)
                    adaptive_weight_h = 0.02 + (1.0 - 0.02) * adaptive_weight_h
                    adaptive_weight_w = torch.sigmoid(-(rgb_grad_w - 0.015) / 0.005)
                    adaptive_weight_w = 0.02 + (1.0 - 0.02) * adaptive_weight_w
                    
                    vis_dir = os.path.join(scene.model_path, "adaptive_weight_vis")
                    os.makedirs(vis_dir, exist_ok=True)
                    save_path = os.path.join(vis_dir, f"iter_{iteration}.png")
                    save_adaptive_weight_map(adaptive_weight_h, adaptive_weight_w, save_path)

        else:  # NOTE: PBR
            # 【取消】暂时恢复原版逻辑，不冻结几何参数
            # if iteration == pbr_iteration + 1:
            #     # 几何参数（决定法线和几何形状）
            #     gaussians._xyz.requires_grad = False
            #     gaussians._rotation.requires_grad = False
            #     gaussians._scaling.requires_grad = False
            #     gaussians._opacity.requires_grad = False
            #     gaussians._features_dc.requires_grad = False
            #     gaussians._features_rest.requires_grad = False
            #     
            #     # BRDF参数（决定材质保底）
            #     gaussians._albedo.requires_grad = True
            #     gaussians._roughness.requires_grad = True
            #     if hasattr(gaussians, '_metallic'):
            #         gaussians._metallic.requires_grad = True
            #         
            #     print(f"\n[ITER {iteration}] 冻结高斯几何参数（法线固定），仅优化BRDF材质和光照")

            if occlusion_flag and indirect:
                filepath = os.path.join(os.path.dirname(checkpoint_path), "occlusion_volumes.pth")
                print(f"begin to load occlusion volumes from {filepath}")
                occlusion_volumes = torch.load(filepath)
                occlusion_ids = occlusion_volumes["occlusion_ids"]
                occlusion_coefficients = occlusion_volumes["occlusion_coefficients"]
                occlusion_degree = occlusion_volumes["degree"]
                bound = occlusion_volumes["bound"]
                aabb = torch.tensor([-bound, -bound, -bound, bound, bound, bound]).cuda()
                occlusion_flag = False
            # recon occlusion
            if indirect:
                points = (
                    (-view_dirs.reshape(-1, 3) * depth_map.reshape(-1, 1) + c2w[:3, 3])
                    .clamp(min=-bound, max=bound)
                    .contiguous()
                )  # [HW, 3]
                occlusion = recon_occlusion(
                    H=H,
                    W=W,
                    bound=bound,
                    points=points,
                    normals=normal_map.permute(1, 2, 0).reshape(-1, 3).contiguous(),
                    occlusion_coefficients=occlusion_coefficients,
                    occlusion_ids=occlusion_ids,
                    aabb=aabb,
                    degree=occlusion_degree,
                ).reshape(H, W, 1)
                irradiance = irradiance_volumes.query_irradiance(
                    points=points.reshape(-1, 3).contiguous(),
                    normals=normal_map.permute(1, 2, 0).reshape(-1, 3).contiguous(),
                ).reshape(H, W, -1)
            else:
                occlusion = torch.ones_like(roughness_map).permute(1, 2, 0)  # [H, W, 1]
                irradiance = torch.zeros_like(roughness_map).permute(1, 2, 0)  # [H, W, 1]

            normal_mask = rendering_result["normal_mask"]  # [1, H, W]
            cubemap.build_mips() # build mip for environment light
            pbr_result = pbr_shading(
                light=cubemap,
                normals=normal_map.permute(1, 2, 0).detach(),  # [H, W, 3]
                view_dirs=view_dirs,
                mask=normal_mask.permute(1, 2, 0),  # [H, W, 1]
                albedo=albedo_map.permute(1, 2, 0),  # [H, W, 3]
                roughness=roughness_map.permute(1, 2, 0),  # [H, W, 1]
                metallic=metallic_map.permute(1, 2, 0) if metallic else None,  # [H, W, 1]
                tone=tone,
                gamma=gamma,
                occlusion=occlusion,
                irradiance=irradiance,
                brdf_lut=brdf_lut,
            )
            render_rgb = pbr_result["render_rgb"].permute(2, 0, 1)  # [3, H, W]
            render_rgb = torch.where(
                normal_mask,
                render_rgb,
                background[:, None, None],
            )
            pbr_render_loss = l1_loss(render_rgb, gt_image)
            loss = pbr_render_loss

            ### BRDF loss
            if (normal_mask == 0).sum() > 0:
                brdf_tv_loss = get_masked_tv_loss(
                    normal_mask,
                    gt_image,  # [3, H, W]
                    torch.cat([albedo_map, roughness_map, metallic_map], dim=0),  # [5, H, W]
                )
            else:
                brdf_tv_loss = get_tv_loss(
                    gt_image,  # [3, H, W]
                    torch.cat([albedo_map, roughness_map, metallic_map], dim=0),  # [5, H, W]
                    pad=1,  # FIXME: 8 for scene
                    step=1,
                )
            loss += brdf_tv_loss * brdf_tv_weight
            lamb_weight = 0.001
            lamb_loss = (1.0 - roughness_map[normal_mask]).mean() + metallic_map[normal_mask].mean()
            loss += lamb_loss * lamb_weight

            #### envmap
            # TV smoothness
            envmap = dr.texture(
                cubemap.base[None, ...],
                envmap_dirs[None, ...].contiguous(),
                filter_mode="linear",
                boundary_mode="cube",
            )[
                0
            ]  # [H, W, 3]
            tv_h1 = torch.pow(envmap[1:, :, :] - envmap[:-1, :, :], 2).mean()
            tv_w1 = torch.pow(envmap[:, 1:, :] - envmap[:, :-1, :], 2).mean()
            env_tv_loss = tv_h1 + tv_w1
            loss += env_tv_loss * env_tv_weight

        loss.backward()

        iter_end.record()

        with torch.no_grad():
            # Progress bar
            ema_loss_for_log = 0.4 * loss.item() + 0.6 * ema_loss_for_log
            if iteration % 10 == 0:
                progress_bar.set_postfix({"Loss": f"{ema_loss_for_log:.{7}f}"})
                progress_bar.update(10)
            if iteration == opt.iterations:
                progress_bar.close()

            # Log and save
            training_report(
                tb_writer=tb_writer,
                iteration=iteration,
                Ll1=Ll1,
                normal_loss=normal_loss,
                loss=loss,
                elapsed=iter_start.elapsed_time(iter_end),
                testing_iterations=testing_iterations,
                scene=scene,
                light=cubemap,
                brdf_lut=brdf_lut,
                canonical_rays=canonical_rays,
                pbr_iteration=pbr_iteration,
                metallic=metallic,
                tone=tone,
                gamma=gamma,
                renderArgs=(pipe, background),
                occlusion_volumes=occlusion_volumes,
                irradiance_volumes=irradiance_volumes,
                indirect=indirect,
            )
            # NOTE: we same .pth instead of point cloud for additional irradiance volumes and cubemap
            # if iteration in saving_iterations:
            #    print(f"\n[ITER {iteration}] Saving Gaussians")
            #    scene.save(iteration)

            # Densification
            if iteration < opt.densify_until_iter:
                # Keep track of max radii in image-space for pruning
                gaussians.max_radii2D[visibility_filter] = torch.max(
                    gaussians.max_radii2D[visibility_filter], radii[visibility_filter]
                )
                gaussians.add_densification_stats(viewspace_point_tensor, visibility_filter)

                if (
                    iteration > opt.densify_from_iter
                    and iteration % opt.densification_interval == 0
                ):
                    size_threshold = 20 if iteration > opt.opacity_reset_interval else None
                    gaussians.densify_and_prune(
                        opt.densify_grad_threshold, 0.005, scene.cameras_extent, size_threshold
                    )

                if iteration % opt.opacity_reset_interval == 0 or (
                    dataset.white_background and iteration == opt.densify_from_iter
                ):
                    gaussians.reset_opacity()

            # Optimizer step
            if iteration < opt.iterations:
                # 恢复原版逻辑：让 PyTorch 自动通过 requires_grad 的 True/False 来只更新材质，不更新几何
                gaussians.optimizer.step()
                gaussians.optimizer.zero_grad(set_to_none=True)
                gaussians.update_learning_rate(iteration)
                
                if iteration >= pbr_iteration:
                    light_optimizer.step()
                    light_optimizer.zero_grad(set_to_none=True)
                    cubemap.clamp_(min=0.0)

            if iteration in checkpoint_iterations:
                print(f"\n[ITER {iteration}] Saving Checkpoint")
                torch.save(
                    {
                        "gaussians": gaussians.capture(),
                        "cubemap": cubemap.state_dict(),
                        "irradiance_volumes": irradiance_volumes.state_dict(),
                        "light_optimizer": light_optimizer.state_dict(),
                        "iteration": iteration,
                    },
                    scene.model_path + "/chkpnt" + str(iteration) + ".pth",
                )


def prepare_output_and_logger(args: GroupParams) -> Optional[SummaryWriter]:
    if not args.model_path:
        if os.getenv("OAR_JOB_ID"):
            unique_str = os.getenv("OAR_JOB_ID")
        else:
            unique_str = str(uuid.uuid4())
        args.model_path = os.path.join("./output/", unique_str[0:10])

    # Set up output folder
    print(f"Output folder: {args.model_path}")
    os.makedirs(args.model_path, exist_ok=True)
    with open(os.path.join(args.model_path, "cfg_args"), "w") as cfg_log_f:
        cfg_log_f.write(str(Namespace(**vars(args))))

    # Create Tensorboard writer
    tb_writer = None
    if TENSORBOARD_FOUND:
        tb_writer = SummaryWriter(args.model_path)
    else:
        print("Tensorboard not available: not logging progress")
    return tb_writer


def training_report(
    tb_writer: Optional[SummaryWriter],
    iteration: int,
    Ll1: Union[float, torch.Tensor],
    normal_loss: Union[float, torch.Tensor],
    loss: Union[float, torch.Tensor],
    elapsed: float,
    testing_iterations: List[int],
    scene: Scene,
    light: CubemapLight,
    brdf_lut: torch.Tensor,
    canonical_rays: torch.Tensor,
    pbr_iteration: int,
    metallic: bool,
    tone: bool,
    gamma: bool,
    renderArgs: Tuple[GroupParams, torch.Tensor],
    occlusion_volumes: Dict,
    irradiance_volumes: IrradianceVolumes,
    indirect: bool = False,
) -> None:
    if tb_writer:
        tb_writer.add_scalar("train_loss_patches/l1_loss", Ll1, iteration)
        tb_writer.add_scalar("train_loss_patches/normal_loss", normal_loss, iteration)
        tb_writer.add_scalar("train_loss_patches/total_loss", loss, iteration)
        tb_writer.add_scalar("iter_time", elapsed, iteration)

    # Report test and samples of training set
    if iteration in testing_iterations:
        torch.cuda.empty_cache()
        validation_configs = (
            {"name": "test", "cameras": scene.getTestCameras()},
            {
                "name": "train",
                "cameras": [
                    scene.getTrainCameras()[idx % len(scene.getTrainCameras())]
                    for idx in range(5, 30, 5)
                ],
            },
        )

        if iteration > pbr_iteration and indirect:
            occlusion_ids = occlusion_volumes["occlusion_ids"]
            occlusion_coefficients = occlusion_volumes["occlusion_coefficients"]
            bound = occlusion_volumes["bound"]
            occlusion_degree = occlusion_volumes["degree"]
            aabb = torch.tensor([-bound, -bound, -bound, bound, bound, bound]).cuda()

        pipe, background = renderArgs
        for config in validation_configs:
            if config["cameras"] and len(config["cameras"]) > 0:
                l1_test = 0.0
                psnr_test = 0.0
                ssim_test = 0.0
                for idx, viewpoint in enumerate(config["cameras"]):
                    viewpoint: Camera
                    render_result = render(
                        viewpoint_camera=viewpoint,
                        pc=scene.gaussians,
                        pipe=pipe,
                        bg_color=background,
                        inference=True,
                        derive_normal=True,
                    )
                    image = torch.clamp(render_result["render"], 0.0, 1.0)
                    depth_map = render_result["depth_map"]
                    depth_img = (
                        torch.from_numpy(
                            turbo_cmap(render_result["depth_map"].cpu().numpy().squeeze())
                        )
                        .to(image.device)
                        .permute(2, 0, 1)
                    )
                    normal_map_from_depth = render_result["normal_map_from_depth"]
                    normal_map = render_result["normal_map"]
                    normal_img = torch.cat([normal_map, normal_map_from_depth], dim=-1)
                    gt_image = viewpoint.original_image.cuda()
                    alpha_mask = viewpoint.gt_alpha_mask.cuda()
                    gt_image = (gt_image * alpha_mask + background[:, None, None] * (1.0 - alpha_mask)).clamp(0.0, 1.0)
                    albedo_map = render_result["albedo_map"]  # [3, H, W]
                    roughness_map = render_result["roughness_map"]  # [1, H, W]
                    metallic_map = render_result["metallic_map"]  # [1, H, W]
                    brdf_map = torch.cat(
                        [
                            albedo_map,
                            torch.tile(roughness_map, (3, 1, 1)),
                            torch.tile(metallic_map, (3, 1, 1)),
                        ],
                        dim=2,
                    )  # [3, H, 3W]
                    # NOTE: PBR record
                    if iteration > pbr_iteration:
                        H, W = viewpoint.image_height, viewpoint.image_width
                        c2w = torch.inverse(viewpoint.world_view_transform.T)  # [4, 4]
                        view_dirs = -(
                            (
                                F.normalize(canonical_rays[:, None, :], p=2, dim=-1)
                                * c2w[None, :3, :3]
                            )  # [HW, 3, 3]
                            .sum(dim=-1)
                            .reshape(H, W, 3)
                        )  # [H, W, 3]
                        normal_mask = render_result["normal_mask"]

                        # recon occlusion
                        if indirect:
                            points = (
                                (-view_dirs.reshape(-1, 3) * depth_map.reshape(-1, 1) + c2w[:3, 3])
                                .clamp(min=-bound, max=bound)
                                .contiguous()
                            )  # [HW, 3]
                            occlusion = recon_occlusion(
                                H=H,
                                W=W,
                                bound=bound,
                                points=points,
                                normals=normal_map.permute(1, 2, 0).reshape(-1, 3).contiguous(),
                                occlusion_coefficients=occlusion_coefficients,
                                occlusion_ids=occlusion_ids,
                                aabb=aabb,
                            ).reshape(H, W, 1)

                            irradiance = irradiance_volumes.query_irradiance(
                                points=points.reshape(-1, 3).contiguous(),
                                normals=normal_map.permute(1, 2, 0).reshape(-1, 3).contiguous(),
                            ).reshape(H, W, -1)
                        else:
                            occlusion = torch.ones_like(roughness_map).permute(1, 2, 0)  # [H, W, 1]
                            irradiance = torch.zeros_like(roughness_map).permute(
                                1, 2, 0
                            )  # [H, W, 1]

                        # build mip for environment light
                        light.build_mips()
                        pbr_result = pbr_shading(
                            light=light,
                            normals=normal_map.permute(1, 2, 0),  # [H, W, 3]
                            view_dirs=view_dirs,
                            mask=normal_mask.permute(1, 2, 0),  # [H, W, 1]
                            albedo=albedo_map.permute(1, 2, 0),  # [H, W, 3]
                            roughness=roughness_map.permute(1, 2, 0),  # [H, W, 1]
                            metallic=metallic_map.permute(1, 2, 0)
                            if metallic
                            else None,  # [H, W, 1]
                            tone=tone,
                            gamma=gamma,
                            brdf_lut=brdf_lut,
                            occlusion=occlusion,
                            irradiance=irradiance,
                        )
                        diffuse_rgb = (
                            pbr_result["diffuse_rgb"].clamp(min=0.0, max=1.0).permute(2, 0, 1)
                        )  # [3, H, W]
                        specular_rgb = (
                            pbr_result["specular_rgb"].clamp(min=0.0, max=1.0).permute(2, 0, 1)
                        )  # [3, H, W]
                        render_rgb = (
                            pbr_result["render_rgb"].clamp(min=0.0, max=1.0).permute(2, 0, 1)
                        )  # [3, H, W]
                        # NOTE: mask render_rgb by depth map
                        background = renderArgs[1]
                        render_rgb = torch.where(
                            normal_mask,
                            render_rgb,
                            background[:, None, None],
                        )
                        diffuse_rgb = torch.where(
                            normal_mask,
                            diffuse_rgb,
                            background[:, None, None],
                        )
                        specular_rgb = torch.where(
                            normal_mask,
                            specular_rgb,
                            background[:, None, None],
                        )
                        pbr_image = torch.cat(
                            [render_rgb, diffuse_rgb, specular_rgb], dim=2
                        )  # [3, H, 3W]
                    else:
                        zero_pad = torch.zeros_like(image)
                        render_rgb = zero_pad
                        pbr_image = torch.cat([zero_pad, zero_pad, zero_pad], dim=2)  # [3, H, 3W]

                    if tb_writer and (idx < 5):
                        tb_writer.add_images(
                            f"{config['name']}_view_{viewpoint.image_name}_{idx}/render",
                            resize_tensorboard_img(image)[None],
                            global_step=iteration,
                        )
                        tb_writer.add_images(
                            f"{config['name']}_view_{viewpoint.image_name}_{idx}/depth",
                            resize_tensorboard_img(depth_img)[None],
                            global_step=iteration,
                        )
                        tb_writer.add_images(
                            f"{config['name']}_view_{viewpoint.image_name}_{idx}/normal",
                            (resize_tensorboard_img(normal_img, 1600)[None] + 1.0) / 2.0,
                            global_step=iteration,
                        )
                        if iteration > pbr_iteration:
                            tb_writer.add_images(
                                f"{config['name']}_view_{viewpoint.image_name}_{idx}/brdf",
                                resize_tensorboard_img(brdf_map, 2400)[None],
                                global_step=iteration,
                            )
                            tb_writer.add_images(
                                f"{config['name']}_view_{viewpoint.image_name}_{idx}/pbr_render",
                                resize_tensorboard_img(pbr_image, 2400)[None],
                                global_step=iteration,
                            )
                            
                        if iteration == testing_iterations[0]:
                            tb_writer.add_images(
                                f"{config['name']}_view_{viewpoint.image_name}_{idx}/ground_truth",
                                resize_tensorboard_img(gt_image)[None],
                                global_step=iteration,
                            )
                    # 法线角度误差可视化：保存图片不依赖 TensorBoard writer
                    if (
                        idx < 5
                        and iteration <= pbr_iteration
                        and hasattr(viewpoint, "gt_normal")
                        and viewpoint.gt_normal is not None
                    ):
                        # 1. 获取数据
                        pred_normal = render_result["normal_map"].cpu()
                        gt_normal = viewpoint.gt_normal.cpu()
                        mask = (viewpoint.gt_alpha_mask > 0.5).squeeze(0).cpu()

                        # 2. 计算角度误差
                        angle_error_np = normal_angle_error_map(pred_normal, gt_normal, mask)

                        # 3. 若可用则写 TensorBoard
                        if tb_writer:
                            angle_error_tensor = torch.from_numpy(angle_error_np)[None, ...]  # [1, H, W]
                            angle_error_tensor = angle_error_tensor / 30.0
                            tb_writer.add_images(
                                f"{config['name']}_view_{viewpoint.image_name}_{idx}/normal_angle_error",
                                angle_error_tensor[None],  # [1, 1, H, W]
                                global_step=iteration,
                                dataformats="NCHW"
                            )

                        # 4. 始终保存到输出目录
                        os.makedirs(os.path.join(scene.model_path, "angle_error_vis"), exist_ok=True)
                        save_path = os.path.join(
                            scene.model_path,
                            "angle_error_vis",
                            f"{config['name']}_view_{viewpoint.image_name}_iter{iteration}.png"
                        )
                        save_angle_error_heatmap(angle_error_np, save_path)
                    if iteration > pbr_iteration:
                        l1_test += F.l1_loss(render_rgb, gt_image).mean().double()
                        psnr_test += psnr(render_rgb, gt_image).mean().double()
                        ssim_test += ssim(render_rgb, gt_image).mean().double()
                    else:
                        l1_test += F.l1_loss(image, gt_image).mean().double()
                        psnr_test += psnr(image, gt_image).mean().double()
                        ssim_test += ssim(image, gt_image).mean().double()
                psnr_test /= len(config["cameras"])
                ssim_test /= len(config["cameras"])
                l1_test /= len(config["cameras"])
                print(
                    f"\n[ITER {iteration}] Evaluating {config['name']}: L1 {l1_test:.6f} PSNR {psnr_test:.6f} SSIM {ssim_test:.6f}"
                )
                if tb_writer:
                    tb_writer.add_scalar(
                        config["name"] + "/loss_viewpoint - l1_loss", l1_test, iteration
                    )
                    tb_writer.add_scalar(
                        config["name"] + "/loss_viewpoint - psnr", psnr_test, iteration
                    )
                    tb_writer.add_scalar(
                        config["name"] + "/loss_viewpoint - ssim", ssim_test, iteration
                    )

        if tb_writer:
            tb_writer.add_histogram(
                "scene/opacity_histogram", scene.gaussians.get_opacity.reshape(-1), iteration
            )
            tb_writer.add_scalar("total_points", scene.gaussians.get_xyz.shape[0], iteration)
        torch.cuda.empty_cache()


if __name__ == "__main__":
    # Set up command line argument parser
    parser = ArgumentParser(description="Training script parameters")
    lp = ModelParams(parser)
    op = OptimizationParams(parser)
    pp = PipelineParams(parser)
    parser.add_argument("--ip", type=str, default="127.0.0.1")
    parser.add_argument("--port", type=int, default=6009)
    parser.add_argument("--debug_from", type=int, default=-1)
    parser.add_argument("--detect_anomaly", action="store_true", default=False)
    parser.add_argument(
        "--test_iterations",
        nargs="+",
        type=int,
        default=[7_000, 14_000, 16_000, 30_000, 37_000],
    )
    parser.add_argument(
        "--save_iterations",
        nargs="+",
        type=int,
        default=[7_000, 30_000, 37_000],
    )
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--checkpoint_iterations", nargs="+", type=int, default=[30_000])
    parser.add_argument("--start_checkpoint", type=str, default=None, help="The path to the checkpoint to load.")
    parser.add_argument("--pbr_iteration", default=30_000, type=int, help="The iteration to begin the pb.r learning (Deomposition Stage in the paper)")
    parser.add_argument("--normal_tv", default=5.0, type=float, help="The weight of TV loss on predicted normal map.")
    parser.add_argument("--normal_loss_weight", default=1.0, type=float, help="The weight of empirical normal matching loss.")
    parser.add_argument("--brdf_tv", default=1.0, type=float, help="The weight of TV loss on predicted BRDF (material) map.")
    parser.add_argument("--env_tv", default=0.01, type=float, help="The weight of TV loss on Environment Map.")
    parser.add_argument("--bound", default=1.5, type=float, help="The valid bound of occlusion volumes.")
    parser.add_argument("--tone", action="store_true", help="Enable aces film tone mapping.")
    parser.add_argument("--gamma", action="store_true", help="Enable linear_to_sRGB for gamma correction.")
    parser.add_argument("--metallic", action="store_true", help="Enable metallic material reconstruction.")
    parser.add_argument("--indirect", action="store_true", help="Enable indirect diffuse modeling.")
    parser.add_argument("--conf_thresh", default=0.5, type=float, help="DA3 normal confidence threshold")
    parser.add_argument("--depth_grad_thresh", default=0.1, type=float, help="DA3 depth gradient threshold")
    parser.add_argument("--normal_loss_pixel_sampling", action="store_true", help="Enable random pixel sampling for normal loss to reduce VRAM usage.")
    parser.add_argument("--normal_loss_sample_cap", default=10240, type=int, help="Maximum sampled pixels for normal loss when sampling is enabled.")
    parser.add_argument("--normal_loss_sample_ratio", default=0.2, type=float, help="Sampling ratio for valid normal-loss pixels when sampling is enabled.")
    args = parser.parse_args(sys.argv[1:])
    args.test_iterations.append(args.iterations)
    args.save_iterations.append(args.iterations)
    args.checkpoint_iterations.append(args.iterations)

    print("Optimizing " + args.model_path)

    # Initialize system state (RNG)
    safe_state(args.quiet)

    # Start GUI server, configure and run training
    torch.autograd.set_detect_anomaly(args.detect_anomaly)
    training(
        dataset=lp.extract(args),
        opt=op.extract(args),
        pipe=pp.extract(args),
        testing_iterations=args.test_iterations,
        saving_iterations=args.save_iterations,
        checkpoint_iterations=args.checkpoint_iterations,
        checkpoint_path=args.start_checkpoint,
        pbr_iteration=args.pbr_iteration,
        debug_from=args.debug_from,
        metallic=args.metallic,
        tone=args.tone,
        gamma=args.gamma,
        normal_tv_weight=args.normal_tv,
        normal_loss_weight=args.normal_loss_weight,
        brdf_tv_weight=args.brdf_tv,
        env_tv_weight=args.env_tv,
        bound=args.bound,
        indirect=args.indirect,
        conf_thresh=args.conf_thresh,
        depth_grad_thresh=args.depth_grad_thresh,
        normal_loss_pixel_sampling=args.normal_loss_pixel_sampling,
        normal_loss_sample_cap=args.normal_loss_sample_cap,
        normal_loss_sample_ratio=args.normal_loss_sample_ratio,
    )

    # All done
    print("\nTraining complete.")
