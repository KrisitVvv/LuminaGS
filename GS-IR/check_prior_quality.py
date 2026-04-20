import os
import cv2
import torch
import numpy as np
import matplotlib.pyplot as plt
import torch.nn.functional as F

def load_gt_normal_png(filepath):
    """读取 Ground Truth 的 PNG 格式法线图并转换到 [-1, 1]"""
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"[!] 找不到 GT 法线文件: {filepath}")
    img = cv2.imread(filepath, cv2.IMREAD_UNCHANGED)
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    
    # 将 [0, 255] 映射到 [-1.0, 1.0]
    normal = (img.astype(np.float32) / 255.0) * 2.0 - 1.0
    normal_tensor = torch.from_numpy(normal).permute(2, 0, 1) # [3, H, W]
    return F.normalize(normal_tensor, p=2, dim=0)

def load_da3_normal_npy(filepath):
    """读取 DA3 生成的高精度 .npy 格式法线阵列"""
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"[!] 找不到 DA3 .npy 文件: {filepath}")
    
    # 你的预处理脚本保存的 shape 是 [H, W, 3]
    normal_np = np.load(filepath).astype(np.float32)
    normal_tensor = torch.from_numpy(normal_np).permute(2, 0, 1) # 转换为 [3, H, W]
    
    # 强制进行一次 L2 归一化确保物理正确
    return F.normalize(normal_tensor, p=2, dim=0)

def calculate_angular_error(n1, n2, mask=None):
    """计算两组法线的角度误差 (MAE, 单位：度)"""
    dot_product = torch.sum(n1 * n2, dim=0)
    dot_product = torch.clamp(dot_product, -1.0, 1.0)
    
    angle_rad = torch.acos(dot_product)
    angle_deg = angle_rad * (180.0 / np.pi)
    
    if mask is not None:
        valid_angles = angle_deg[mask]
        mae = valid_angles.mean().item()
        return mae, angle_deg
    else:
        return angle_deg.mean().item(), angle_deg

def main():
    # ================= 极其关键的路径映射 =================
    # 1. 原图的 Mask (用于过滤背景)
    alpha_mask_path = "datasets/TensoIR/lego/test_000/rgba.png" 
    
    # 2. 原始的物理真值 (Ground Truth) 法线图
    gt_normal_path = "datasets/TensoIR/lego/test_000/normal.png"
    
    # 3. DA3 预处理生成的法线 (因为是根据 rgba.png 推理的，所以叫 rgba.npy)
    da3_normal_path = "datasets/TensoIR/lego/da3_normal/test_000/rgba.npy" 
    # ======================================================

    print("[*] 加载 Ground Truth 与 DA3 数据...")
    gt_normal = load_gt_normal_png(gt_normal_path)
    da3_normal = load_da3_normal_npy(da3_normal_path)

    # ================= 新增：动态对齐分辨率 =================
    if da3_normal.shape[1:] != gt_normal.shape[1:]:
        print(f"[*] 检测到分辨率不匹配: GT {gt_normal.shape[1:]} vs DA3 {da3_normal.shape[1:]}")
        print("[*] 正在将 DA3 法线插值放大至原始分辨率...")
        da3_normal = da3_normal.unsqueeze(0) # [1, 3, H, W]
        # 使用双线性插值平滑放大
        da3_normal = F.interpolate(da3_normal, size=gt_normal.shape[1:], mode='bilinear', align_corners=False)
        da3_normal = da3_normal.squeeze(0)   # [3, H, W]
        # 放大后必须重新 L2 归一化，保证向量长度为 1
        da3_normal = F.normalize(da3_normal, p=2, dim=0)
    # ========================================================
    
    # 加载 Mask (仅评估 Lego 实体区域)
    rgba = cv2.imread(alpha_mask_path, cv2.IMREAD_UNCHANGED)
    mask = torch.from_numpy(rgba[:, :, 3] / 255.0) > 0.5 # [H, W]

    # === [坐标系诊断区] ===
    # 你可以在这里测试不同的翻转，看哪种与 GT 最接近
    # 例如：如果下面输出的误差高达 90度/180度，尝试解开这行的注释
    # da3_normal[1:3, ...] *= -1.0 
    # =====================

    print("[*] 计算 MAE...")
    mae, error_map = calculate_angular_error(gt_normal, da3_normal, mask)
    print(f"\n======================================")
    print(f"🔥 DA3 先验自身的绝对 MAE: {mae:.4f} 度")
    print(f"======================================\n")

    print("[*] 生成可视化对比图...")
    vis_gt = ((gt_normal.permute(1, 2, 0).numpy() + 1.0) / 2.0)
    vis_da3 = ((da3_normal.permute(1, 2, 0).numpy() + 1.0) / 2.0)
    
    mask_np = mask.numpy()
    vis_gt[~mask_np] = 0
    vis_da3[~mask_np] = 0
    
    error_vis = error_map.numpy()
    error_vis[~mask_np] = 0

    fig, axes = plt.subplots(1, 3, figsize=(18, 6))
    
    axes[0].imshow(vis_gt)
    axes[0].set_title("Ground Truth Normal")
    axes[0].axis('off')
    
    axes[1].imshow(vis_da3)
    axes[1].set_title("DA3 Derived Normal (.npy)")
    axes[1].axis('off')
    
    im = axes[2].imshow(error_vis, cmap='jet', vmin=0, vmax=45) 
    axes[2].set_title(f"Error Heatmap (MAE: {mae:.2f}°)")
    axes[2].axis('off')
    fig.colorbar(im, ax=axes[2], fraction=0.046, pad=0.04, label="Error (Degrees)")
    
    plt.tight_layout()
    save_path = "prior_validation_result.png"
    plt.savefig(save_path, dpi=200)
    print(f"[*] 可视化结果已完美保存至: {save_path}")

if __name__ == "__main__":
    main()