import os
import cv2
import glob
import argparse
import numpy as np
import json

# MUST SET THIS BEFORE IMPORTING
os.environ["OPENCV_IO_ENABLE_OPENEXR"] = "1"
import imageio.v2 as iio
import torch
import torch.nn.functional as F
import itertools

def get_permutations():
    # 返回所有48种(坐标轴互换 + 翻转)组合
    perms = []
    names = []
    
    orders = list(itertools.permutations([0, 1, 2]))
    for order in orders:
        for sx in [1, -1]:
            for sy in [1, -1]:
                for sz in [1, -1]:
                    name = ""
                    name += f"{'+' if sx==1 else '-'}{['X', 'Y', 'Z'][order[0]]} "
                    name += f"{'+' if sy==1 else '-'}{['X', 'Y', 'Z'][order[1]]} "
                    name += f"{'+' if sz==1 else '-'}{['X', 'Y', 'Z'][order[2]]}"
                    
                    perms.append((order, [sx, sy, sz]))
                    names.append(name.strip())
                    
    return perms, names

def calc_angular_error(n1, n2, mask):
    # n1, n2: [3, H, W]
    # mask: [H, W] bool
    n1_flat = n1[:, mask].transpose(1, 0) # [N, 3]
    n2_flat = n2[:, mask].transpose(1, 0) # [N, 3]
    
    # Cosine similarity
    cos_theta = torch.sum(n1_flat * n2_flat, dim=1)
    # clip以防数值溢出抛出nan
    cos_theta = torch.clamp(cos_theta, -1.0 + 1e-6, 1.0 - 1e-6)
    
    # Angular error in degrees
    angular_error = torch.acos(cos_theta) * (180.0 / np.pi)
    return angular_error

def vis_normal(normal, save_path):
    # normal: [3, H, W] → 转[H,W,3]，并映射到[0,255]
    vis = normal.permute(1,2,0).cpu().numpy()
    vis = (vis + 1) / 2 * 255  # [-1,1] → [0,255]
    vis = vis.astype(np.uint8)
    iio.imwrite(save_path, vis)

def load_data(gt_dir, da3_normal_dir, da3_depth_dir, view_name, conf_thresh, depth_grad_thresh):
    # 1. 加载GT Normal
    gt_norm_path = os.path.join(gt_dir, view_name, "normal.exr")
    if not os.path.exists(gt_norm_path): return None, None, None
    gt_norm = cv2.imread(gt_norm_path, cv2.IMREAD_UNCHANGED) # Reads as BGRA / BGR
    if gt_norm is None: return None, None, None
    if gt_norm.shape[-1] == 4:
        gt_norm = cv2.cvtColor(gt_norm, cv2.COLOR_BGRA2RGBA)
    else:
        gt_norm = cv2.cvtColor(gt_norm, cv2.COLOR_BGR2RGB)
        
    gt_norm = gt_norm[:, :, :3]
    gt_norm = torch.from_numpy(gt_norm).float()
    # DO NOT map from [0, 1] to [-1, 1] anymore because cv2 reads float32 natively!
    gt_norm = gt_norm.permute(2, 0, 1)
    gt_norm = F.normalize(gt_norm, p=2, dim=0, eps=1e-6)
    
    # 2. GT Alpha mask
    rgba_path = os.path.join(gt_dir, view_name, "rgba.png")
    if not os.path.exists(rgba_path): return None, None, None
    rgba = iio.imread(rgba_path)
    alpha = torch.from_numpy(rgba[:, :, 3]).float() / 255.0
    mask = alpha > 0.5
    
    # 3. 加载目标 Normal (支持DA3与Marigold格式)
    da3_norm_path = os.path.join(da3_normal_dir, view_name, "normal.npy")
    if not os.path.exists(da3_norm_path): da3_norm_path = os.path.join(da3_normal_dir, view_name, "normal.exr")
    if not os.path.exists(da3_norm_path): da3_norm_path = os.path.join(da3_normal_dir, f"{view_name}_rgba_normals.npy")
    if not os.path.exists(da3_norm_path): return None, None, None
    if da3_norm_path.endswith(".npy"):
        da3_norm = np.load(da3_norm_path)
        da3_norm = torch.from_numpy(da3_norm).float()
        if da3_norm.shape[0] != 3:
            da3_norm = da3_norm.permute(2, 0, 1) # Assumes H, W, 3 -> 3, H, W
    else:
        da3_norm = iio.imread(da3_norm_path)
        if da3_norm.shape[-1] == 4: da3_norm = da3_norm[:, :, :3]
        da3_norm = torch.from_numpy(da3_norm).float().permute(2, 0, 1)
        
    da3_norm = F.normalize(da3_norm, p=2, dim=0, eps=1e-6)
    
    # 4. 质量筛选
    final_mask = mask.clone()
    
    # ✅ 启用置信度筛选（适配Metric3D的conf_npy目录结构）
    # 自动从normals_npy的上级目录查找conf_npy文件夹
    conf_dir = os.path.join(os.path.dirname(da3_normal_dir), "conf_npy")
    conf_path = os.path.join(conf_dir, f"{view_name}_rgba_conf.npy")
    if not os.path.exists(conf_path):
        # 兼容旧格式（view_name/conf.npy）
        conf_path = os.path.join(da3_normal_dir, view_name, "conf.npy")
    if not os.path.exists(conf_path):
        conf_path = os.path.join(da3_normal_dir, view_name, "conf.exr")
    
    if os.path.exists(conf_path):
        if conf_path.endswith(".npy"):
            conf = np.load(conf_path)
        else:
            conf = iio.imread(conf_path)
        if len(conf.shape) == 3:
            conf = conf[:, :, 0]
        conf_mask = torch.from_numpy(conf).float() > conf_thresh
        final_mask = final_mask & conf_mask
        print(f"视角{view_name} - 置信度筛选后有效像素数: {final_mask.sum().item()}")
    
    print(f"视角{view_name} - GT法线shape: {gt_norm.shape}, 数值范围: [{gt_norm.min():.2f}, {gt_norm.max():.2f}]")
    print(f"视角{view_name} - 预测法线shape: {da3_norm.shape}, 数值范围: [{da3_norm.min():.2f}, {da3_norm.max():.2f}]")
    print(f"视角{view_name} - 最终有效像素数: {final_mask.sum().item()}")
    
    # 强制把 da3_norm 修正成一致的维度以确保绘制图片与后续误差计算一致
    if da3_norm.shape[0] != 3:
        if da3_norm.shape[1] == 3:
            da3_norm = da3_norm.permute(1, 2, 0)
        elif da3_norm.shape[2] == 3:
            da3_norm = da3_norm.permute(2, 0, 1)
    return gt_norm, da3_norm, final_mask

def main():
    parser = argparse.ArgumentParser(description="Evaluate DA3 Normals and test coordinate swaps.")
    parser.add_argument("--gt_dir", type=str, default="/home/zengkun/LuminaGS/GS-IR-main/GS-IR/datasets/TensoIR/lego")
    parser.add_argument("--normal_dir", type=str, default="/home/zengkun/LuminaGS/GS-IR-main/GS-IR/datasets/TensoIR/lego/da3_normal")
    parser.add_argument("--da3_depth_dir", type=str, default="/home/zengkun/LuminaGS/GS-IR-main/GS-IR/datasets/TensoIR/lego/da3_depth")
    parser.add_argument("--conf_thresh", type=float, default=0.7, help="置信度阈值，越高筛选越严格")
    parser.add_argument("--depth_grad_thresh", type=float, default=0.08)
    parser.add_argument("--limit", type=int, default=-1, help="Max views to test (-1 for all)")
    
    # 新增: 控制输出路径的参数
    parser.add_argument("--vis_out_dir", type=str, default="./visualizations", help="预览图的保存文件夹路径")
    args = parser.parse_args()

    # --- 自动生成文件前缀逻辑 ---
    # 提取 Dataset 名字 (如 'lego')
    dataset_name = os.path.basename(os.path.normpath(args.gt_dir))
    
    # 提取 Method 名字 (如 'metric3d')
    normal_path_parts = os.path.normpath(args.normal_dir).split(os.sep)
    ignore_names = ['normals_npy', 'da3_normal', 'normals']
    method_parts = [p for p in reversed(normal_path_parts) if p not in ignore_names]
    # 例如：提取 metric3d_normal_final 中的 'metric3d'
    method_name = method_parts[0].split('_')[0] if method_parts else "unknown"
    
    # 格式化 conf_thresh (10.0 -> 10, 0.7 -> 0.7)
    conf_str = f"{int(args.conf_thresh)}" if args.conf_thresh.is_integer() else f"{args.conf_thresh}"
    
    # 组装前缀
    file_prefix = f"{dataset_name}_{method_name}_conf{conf_str}"
    # ---------------------------

    # 通过 GT 目录获取所有的视角名称 (去除仅包含文件的误判)
    gt_view_dirs = sorted(glob.glob(os.path.join(args.gt_dir, "*_*"))) # e.g. train_000
    view_names = [os.path.basename(v) for v in gt_view_dirs if os.path.isdir(v) and "train" in os.path.basename(v)]
    if args.limit > 0: view_names = view_names[:args.limit]
    
    perms, perm_names = get_permutations()
    all_errors = {i: [] for i in range(len(perms))}
    print(f"评估参数: conf_thresh={args.conf_thresh}, depth_grad_thresh={args.depth_grad_thresh}")
    print(f"寻找视角数: {len(view_names)} (正在处理中，请稍候...)")
    
    # Load transforms
    c2ws = {}
    json_path = os.path.join(args.gt_dir, "transforms_train.json")
    if os.path.exists(json_path):
        with open(json_path, 'r') as f:
            meta = json.load(f)
            for frame in meta["frames"]:
                # frame["file_path"] => "./train_000/rgba"
                vn = frame["file_path"].split("/")[-2]
                c2w = np.array(frame["transform_matrix"])
                # change from OpenGL/Blender camera axes (Y up, Z back) to COLMAP (Y down, Z forward)
                c2w[:3, 1:3] *= -1
                c2ws[vn] = torch.tensor(c2w).float()[:3, :3] # use corrected rotation part only
                
    valid_views = 0
    vis_cache = [] # 缓存前两张图供后续使用最佳变换进行可视化
    
    for vn in view_names:
        gt_norm, da3_norm, final_mask = load_data(args.gt_dir, args.normal_dir, args.da3_depth_dir, vn, args.conf_thresh, args.depth_grad_thresh)
        if gt_norm is None: 
            continue
        if da3_norm is None: 
            continue
        if not final_mask.any(): 
            continue
            
        R = None
        if vn in c2ws:
            R = c2ws[vn] # [3, 3] rotation matrix from cam to world
        if valid_views < 2:
            vis_cache.append((vn, gt_norm.clone(), da3_norm.clone(), R.clone() if R is not None else None))
        
        for i, (perm, name) in enumerate(zip(perms, perm_names)):
            order, mults = perm
            # 重新排列并翻转
            test_norm = da3_norm[list(order), :, :].clone()
            test_norm[0, :, :] *= mults[0]
            test_norm[1, :, :] *= mults[1]
            test_norm[2, :, :] *= mults[2]
            
            if R is not None:
                # 转换到世界坐标系
                H, W = test_norm.shape[1], test_norm.shape[2]
                test_norm_flat = test_norm.view(3, -1)
                test_norm = torch.matmul(R, test_norm_flat).view(3, H, W)
                test_norm = F.normalize(test_norm, p=2, dim=0, eps=1e-6)
            errors = calc_angular_error(gt_norm, test_norm, final_mask)
            all_errors[i].append(errors)
            
        valid_views += 1
        
    if valid_views == 0:
        print("未找到有效的数据对。")
        return
        
    print(f"\n========================== [坐标翻转测试] MAE 误差结果 ({valid_views} 张图) ==========================")
    best_mae = float('inf')
    best_idx = 0
    
    results = []
    for i in range(len(perms)):
        cat_errors = torch.cat(all_errors[i]).numpy()
        mae = np.mean(cat_errors)
        rmse = np.sqrt(np.mean(cat_errors**2))
        if mae < best_mae:
            best_mae = mae
            best_idx = i
        results.append((i, mae, cat_errors))
        
    for i, mae, cat_errors in results:
        marker = "⭐ [最优归属]" if i == best_idx else "    "
        print(f"{marker} 坐标系: {perm_names[i]:<15} | 平均MAE: {mae:6.2f}°")
        
    print(f"\n=========================== [质量筛选后] 最优配置指标统计 ===========================")
    best_errors = results[best_idx][2]
    best_order, best_mults = perms[best_idx]
    
    print(f"✅ 自动搜索完成！模型预测所在坐标系: {perm_names[best_idx]}")
    print(f"平均MAE: {np.mean(best_errors):.2f}°")
    print(f"最小MAE: {np.min(best_errors):.2f}°")
    print(f"最大MAE: {np.max(best_errors):.2f}°")
    
    print(f"\n=========================== [变换汇总] 对齐 GT 所需的完整步骤 ===========================")
    axes_map = {0: 'X_pred', 1: 'Y_pred', 2: 'Z_pred'}
    signs_map = {1: '+', -1: '-'}
    print("若想在 GS-IR 或其他管线中直接使用该预测法线图并完美对齐真值，请执行如下变换：\n")
    print(f"1. 预测图的轴向重排重映射 (将其搬到兼容 COLMAP/OpenCV 的相机系下):")
    print(f"   X_cam = {signs_map[best_mults[0]]} {axes_map[best_order[0]]}")
    print(f"   Y_cam = {signs_map[best_mults[1]]} {axes_map[best_order[1]]}")
    print(f"   Z_cam = {signs_map[best_mults[2]]} {axes_map[best_order[2]]}")
    print("\n2. 相机到世界坐标系的变换 (C2W):")
    print("   设相机外参矩阵为 c2w，需保证先经过 OpenGL(Y向上, Z向后) 到 COLMAP(Y向下, Z向前) 的修正:")
    print("     c2w[:3, 1:3] *= -1")
    print("   取其逆矩阵(W2C)的旋转部分的转置作为最终投影 R 矩阵:")
    print("     w2c = np.linalg.inv(c2w)")
    print("     R = np.transpose(w2c[:3, :3])")
    print("   最终世界系法线 World_normal = R @ [X_cam, Y_cam, Z_cam]^T")
    
    # 自动保存样本重映射对比图至指定文件夹
    if len(vis_cache) > 0:
        os.makedirs(args.vis_out_dir, exist_ok=True) # 确保目标文件夹存在
        
        for vn, gt_norm, da3_norm, R in vis_cache:
            gt_save_name = f"{file_prefix}_{vn}_gt_normal.png"
            vis_normal(gt_norm, os.path.join(args.vis_out_dir, gt_save_name))
            
            # 采用最优计算组合来施加旋转
            vis_norm = da3_norm.clone()
            vis_norm = vis_norm[list(best_order), :, :]
            vis_norm[0, :, :] *= best_mults[0]
            vis_norm[1, :, :] *= best_mults[1]
            vis_norm[2, :, :] *= best_mults[2]
            
            if R is not None:
                H, W = vis_norm.shape[1], vis_norm.shape[2]
                vis_norm = torch.matmul(R, vis_norm.view(3, -1)).view(3, H, W)
                vis_norm = F.normalize(vis_norm, p=2, dim=0, eps=1e-6)
                
            vis_name = perm_names[best_idx].replace(' ', '')
            pred_save_name = f"{file_prefix}_{vn}_pred_normal_world_auto_align_{vis_name}.png"
            vis_normal(vis_norm, os.path.join(args.vis_out_dir, pred_save_name))
            
        print(f"\n[可视化生成] 已将 {len(vis_cache)} 组对比图保存至目录: '{args.vis_out_dir}'")
        print(f"             文件命名前缀为: '{file_prefix}'")

if __name__ == "__main__":
    main()