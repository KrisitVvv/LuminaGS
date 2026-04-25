import os, json
import cv2
import torch
import numpy as np
import matplotlib.pyplot as plt
import torch.nn.functional as F

def load_gt_normal_png(filepath):
    img = cv2.imread(filepath, cv2.IMREAD_UNCHANGED)
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    normal = (img.astype(np.float32) / 255.0) * 2.0 - 1.0
    normal_tensor = torch.from_numpy(normal).permute(2, 0, 1) 
    return F.normalize(normal_tensor, p=2, dim=0)

def load_da3_normal_npy(filepath):
    normal_np = np.load(filepath).astype(np.float32)
    normal_tensor = torch.from_numpy(normal_np).permute(2, 0, 1)
    return F.normalize(normal_tensor, p=2, dim=0)

def calculate_angular_error(n1, n2, mask=None):
    dot_product = torch.sum(n1 * n2, dim=0)
    dot_product = torch.clamp(dot_product, -1.0, 1.0)
    angle_deg = torch.acos(dot_product) * (180.0 / np.pi)
    if mask is not None:
        return angle_deg[mask].mean().item(), angle_deg
    return angle_deg.mean().item(), angle_deg

def main():
    TARGET_VIEW = "train_000"
    DATASET_ROOT = "datasets/TensoIR/lego"
    TRANSFORMS_PATH = os.path.join(DATASET_ROOT, "transforms_train.json")
    
    alpha_mask_path = f"{DATASET_ROOT}/{TARGET_VIEW}/rgba.png" 
    gt_normal_path = f"{DATASET_ROOT}/{TARGET_VIEW}/normal.png"
    da3_normal_path = f"{DATASET_ROOT}/da3_normal/{TARGET_VIEW}/rgba.npy" 
    
    print(f"[*] 加载 {TARGET_VIEW} 数据集进行法线质量校验...")
    
    # 1. 加载外参 R_c2w (修复核心：必须知道相机在世界的朝向)
    with open(TRANSFORMS_PATH, 'r') as f:
        transforms = json.load(f)
        
    c2w = None
    for frame in transforms['frames']:
        if TARGET_VIEW in frame['file_path']:
            c2w = np.array(frame['transform_matrix'])
            break
            
    if c2w is None:
        raise ValueError(f"[!] 找不到 {TARGET_VIEW} 的外参！")
        
    R_c2w = torch.from_numpy(c2w[:3, :3]).float() # [3, 3]
    
    # 2. 加载数据
    gt_normal_w = load_gt_normal_png(gt_normal_path) # [3, H, W] (World Space)
    da3_normal_c = load_da3_normal_npy(da3_normal_path) # [3, H, W] (Camera Space)
    
    rgba = cv2.imread(alpha_mask_path, cv2.IMREAD_UNCHANGED)
    mask = torch.from_numpy(rgba[:, :, 3] / 255.0) > 0.5 # [H, W]

    # 3. 遍历翻转测试 (完全模拟 train.py 的 C2W 转换行为)
    best_mae = float('inf')
    best_error_map = None
    best_name = ""
    best_da3_w = None
    
    flips = [
        (1, 1, 1, "+X,+Y,+Z (Baseline)"), (-1, 1, 1, "-X,+Y,+Z"), (1, -1, 1, "+X,-Y,+Z"), (1, 1, -1, "+X,+Y,-Z"),
        (-1, -1, 1, "-X,-Y,+Z"), (-1, 1, -1, "-X,+Y,-Z"), (1, -1, -1, "+X,-Y,-Z (Flip YZ)"), (-1, -1, -1, "-X,-Y,-Z")
    ]
    
    print("[*] 自动寻找最佳坐标系对齐 (结合 C2W 旋转至世界坐标系)...")
    for fx, fy, fz, name in flips:
        # a. 在相机空间翻转
        test_n_c = da3_normal_c.clone()
        test_n_c[0] *= fx
        test_n_c[1] *= fy
        test_n_c[2] *= fz
        
        # b. 转换到世界坐标系 N_world = R_c2w * N_cam
        test_n_c_hwc = test_n_c.permute(1, 2, 0) # [H, W, 3]
        test_n_w_hwc = torch.matmul(test_n_c_hwc, R_c2w.T) # [H, W, 3]
        test_n_w = test_n_w_hwc.permute(2, 0, 1) # [3, H, W]
        test_n_w = F.normalize(test_n_w, p=2, dim=0)
        
        # c. 与 GT World Normal 计算误差
        mae, error_map = calculate_angular_error(gt_normal_w, test_n_w, mask)
        if mae < best_mae:
            best_mae = mae
            best_error_map = error_map
            best_name = name
            best_da3_w = test_n_w

    print(f"\n======================================")
    print(f"✅ 最佳坐标轴映射: {best_name}")
    print(f"🔥 DA3 真实物理精度 (MAE): {best_mae:.4f} 度")
    print(f"======================================\n")

    # 4. 可视化
    vis_gt = ((gt_normal_w.permute(1, 2, 0).numpy() + 1.0) / 2.0)
    vis_da3 = ((best_da3_w.permute(1, 2, 0).numpy() + 1.0) / 2.0)
    
    mask_np = mask.numpy()
    vis_gt[~mask_np] = 0
    vis_da3[~mask_np] = 0
    error_vis = best_error_map.numpy()
    error_vis[~mask_np] = 0

    fig, axes = plt.subplots(1, 3, figsize=(18, 6))
    axes[0].imshow(vis_gt)
    axes[0].set_title(f"GT World Normal ({TARGET_VIEW})")
    axes[0].axis('off')
    
    axes[1].imshow(vis_da3)
    axes[1].set_title(f"DA3 World Normal (Align: {best_name})")
    axes[1].axis('off')
    
    im = axes[2].imshow(error_vis, cmap='jet', vmin=0, vmax=45) 
    axes[2].set_title(f"Geometric Error (MAE: {best_mae:.2f}°)")
    axes[2].axis('off')
    fig.colorbar(im, ax=axes[2], fraction=0.046, pad=0.04)
    
    plt.tight_layout()
    plt.savefig("prior_validation_result.png", dpi=200)
    print("[*] 高清校验图已保存！")

if __name__ == "__main__":
    main()