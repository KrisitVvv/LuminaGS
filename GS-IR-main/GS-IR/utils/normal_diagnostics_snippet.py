# === 法线坐标系翻转诊断测试代码备份 ===
# 此段代码用于快速测试预测法线与GT法线之间真正的坐标变化情况。
# 当你引入了新的数据集或新视角的GT法线时，可以将此段代码放在 10000 步左右的迭代分支中运行。
# 它可以帮你在一瞬间找到哪种轴翻转能让预测法线和GT法线实现最小余弦损失。
import torch
import torch.nn.functional as F

"""
# 把这段代码粘贴进 train.py 的相应迭代条件内（例如 if iteration == 10000:）
if hasattr(viewpoint_cam, "gt_normal") and viewpoint_cam.gt_normal is not None:
    orig_gt_normal_map = viewpoint_cam.gt_normal.cuda()
    orig_gt_normal_map = F.normalize(orig_gt_normal_map, p=2, dim=0, eps=1e-6)
    mask = (viewpoint_cam.gt_alpha_mask.cuda() > 0.5).squeeze(0)
    
    normal_map_norm = F.normalize(normal_map, p=2, dim=0, eps=1e-6)
    pred_normal_masked = normal_map_norm[:, mask]

    print(f"\n[DEBUG] --- Iteration {iteration} Normal Coordinate Diagnostics ---")
    
    # (A) 纯基准 (未翻转)
    gt_pure = orig_gt_normal_map[:, mask]
    loss_pure = (1.0 - torch.clamp(torch.sum(pred_normal_masked * gt_pure, dim=0), -1.0, 1.0)).mean().item()
    print(f"[DEBUG] Baseline (No flip): {loss_pure:.4f}")
    
    # (B) 翻转X轴
    gt_x = orig_gt_normal_map.clone()
    gt_x[0] = -gt_x[0]
    loss_x = (1.0 - torch.clamp(torch.sum(pred_normal_masked * gt_x[:, mask], dim=0), -1.0, 1.0)).mean().item()
    print(f"[DEBUG] Flip X axis:      {loss_x:.4f}")
    
    # (C) 翻转Y轴
    gt_y = orig_gt_normal_map.clone()
    gt_y[1] = -gt_y[1]
    loss_y = (1.0 - torch.clamp(torch.sum(pred_normal_masked * gt_y[:, mask], dim=0), -1.0, 1.0)).mean().item()
    print(f"[DEBUG] Flip Y axis:      {loss_y:.4f}")
    
    # (D) 翻转Z轴
    gt_z = orig_gt_normal_map.clone()
    gt_z[2] = -gt_z[2]
    loss_z = (1.0 - torch.clamp(torch.sum(pred_normal_masked * gt_z[:, mask], dim=0), -1.0, 1.0)).mean().item()
    print(f"[DEBUG] Flip Z axis:      {loss_z:.4f}")
    
    # (E) 翻转X和Y轴
    gt_xy = orig_gt_normal_map.clone()
    gt_xy[0] = -gt_xy[0]
    gt_xy[1] = -gt_xy[1]
    loss_xy = (1.0 - torch.clamp(torch.sum(pred_normal_masked * gt_xy[:, mask], dim=0), -1.0, 1.0)).mean().item()
    print(f"[DEBUG] Flip X and Y:     {loss_xy:.4f}")

    # (F) 翻转X和Z轴
    gt_xz = orig_gt_normal_map.clone()
    gt_xz[0] = -gt_xz[0]
    gt_xz[2] = -gt_xz[2]
    loss_xz = (1.0 - torch.clamp(torch.sum(pred_normal_masked * gt_xz[:, mask], dim=0), -1.0, 1.0)).mean().item()
    print(f"[DEBUG] Flip X and Z:     {loss_xz:.4f}")
    
    # (G) 翻转Y和Z轴
    gt_yz = orig_gt_normal_map.clone()
    gt_yz[1] = -gt_yz[1]
    gt_yz[2] = -gt_yz[2]
    loss_yz = (1.0 - torch.clamp(torch.sum(pred_normal_masked * gt_yz[:, mask], dim=0), -1.0, 1.0)).mean().item()
    print(f"[DEBUG] Flip Y and Z:     {loss_yz:.4f}")

    # (H) 全局取反
    gt_inv = -orig_gt_normal_map.clone()
    loss_inv = (1.0 - torch.clamp(torch.sum(pred_normal_masked * gt_inv[:, mask], dim=0), -1.0, 1.0)).mean().item()
    print(f"[DEBUG] Invert all (-X,-Y,-Z): {loss_inv:.4f}")
    
    print("[DEBUG] ---------------------------------------------------------\n")
"""
