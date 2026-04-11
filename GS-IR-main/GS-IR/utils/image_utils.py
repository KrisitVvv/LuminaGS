#
# Copyright (C) 2023, Inria
# GRAPHDECO research group, https://team.inria.fr/graphdeco
# All rights reserved.
#
# This software is free for non-commercial, research and evaluation use
# under the terms of the LICENSE.md file.
#
# For inquiries contact  george.drettakis@inria.fr
#

import numpy as np
import matplotlib.pyplot as plt
import torch


def mse(img1: torch.Tensor, img2: torch.Tensor) -> torch.Tensor:
    return (((img1 - img2)) ** 2).view(img1.shape[0], -1).mean(1, keepdim=True)


def psnr(img1: torch.Tensor, img2: torch.Tensor) -> torch.Tensor:
    mse = (((img1 - img2)) ** 2).view(img1.shape[0], -1).mean(1, keepdim=True)
    return 20 * torch.log10(1.0 / torch.sqrt(mse))

def viridis_cmap(gray: np.ndarray) -> np.ndarray:
    """
    Visualize a single-channel image using matplotlib's viridis color map
    yellow is high value, blue is low
    :param gray: np.ndarray, (H, W) or (H, W, 1) unscaled
    :return: (H, W, 3) float32 in [0, 1]
    """
    colored = plt.cm.viridis(plt.Normalize()(gray.squeeze()))[..., :-1]
    return colored.astype(np.float32)

def turbo_cmap(gray: np.ndarray) -> np.ndarray:
    """
    Visualize a single-channel image using matplotlib's turbo color map
    yellow is high value, blue is low
    :param gray: np.ndarray, (H, W) or (H, W, 1) unscaled
    :return: (H, W, 3) float32 in [0, 1]
    """
    colored = plt.cm.turbo(plt.Normalize()(gray.squeeze()))[..., :-1]
    return colored.astype(np.float32)

import torch.nn.functional as F
from PIL import Image

def normal_angle_error_map(
    pred_normal: torch.Tensor,
    gt_normal: torch.Tensor,
    mask: torch.Tensor,
    max_vis_angle: float = 30.0
) -> np.ndarray:
    pred_normal = F.normalize(pred_normal, p=2, dim=0, eps=1e-6)
    gt_normal = F.normalize(gt_normal, p=2, dim=0, eps=1e-6)
    
    dot_product = torch.sum(pred_normal * gt_normal, dim=0)
    dot_product = torch.clamp(dot_product, -1.0, 1.0)
    angle_error = torch.acos(dot_product) * 180.0 / np.pi
    
    angle_error[~mask] = 0.0
    angle_error = torch.clamp(angle_error, 0.0, max_vis_angle)
    
    return angle_error.cpu().numpy()

def save_angle_error_heatmap(
    angle_error_np: np.ndarray,
    save_path: str,
    colormap: str = "turbo"
) -> None:
    from matplotlib import cm
    import matplotlib.pyplot as plt
    
    normalized_error = angle_error_np / 30.0
    
    if colormap == "turbo":
        cmap = cm.get_cmap("turbo")
    else:
        cmap = cm.get_cmap("jet")
    heatmap = cmap(normalized_error)
    
    heatmap_pil = Image.fromarray((heatmap[:, :, :3] * 255).astype(np.uint8))
    heatmap_pil.save(save_path)
