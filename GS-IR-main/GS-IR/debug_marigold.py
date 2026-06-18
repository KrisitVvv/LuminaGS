import os
os.environ["OPENCV_IO_ENABLE_OPENEXR"] = "1"
import imageio.v2 as iio
import numpy as np

gt_dir = "/home/zengkun/LuminaGS/GS-IR-main/GS-IR/datasets/TensoIR/lego"
view_name = "train_000"

da3_dir = "/home/zengkun/LuminaGS/GS-IR-main/GS-IR/datasets/TensoIR/lego/marigold_normal/normals_npy"

gt_norm_path = os.path.join(gt_dir, view_name, "normal.exr")
da3_norm_path = os.path.join(da3_dir, f"{view_name}_rgba_normals.npy")
rgba_path = os.path.join(gt_dir, view_name, "rgba.png")

print("GT exists:", os.path.exists(gt_norm_path))
print("Marigold exists:", os.path.exists(da3_norm_path))
print("RGBA exists:", os.path.exists(rgba_path))

if os.path.exists(da3_norm_path):
    arr = np.load(da3_norm_path)
    print("Marigold shape:", arr.shape)
