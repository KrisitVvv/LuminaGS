import os
os.environ["OPENCV_IO_ENABLE_OPENEXR"] = "1"
import imageio.v2 as iio

gt_dir = "/home/zengkun/LuminaGS/GS-IR-main/GS-IR/datasets/TensoIR/lego"
view_name = "test_000"

da3_dir = "/home/zengkun/LuminaGS/GS-IR-main/GS-IR/datasets/TensoIR/lego/da3_normal"

gt_norm_path = os.path.join(gt_dir, view_name, "normal.exr")
da3_norm_path = os.path.join(da3_dir, view_name, "normal.npy")
rgba_path = os.path.join(gt_dir, view_name, "rgba.png")

print("GT exists:", os.path.exists(gt_norm_path))
print("DA3 exists:", os.path.exists(da3_norm_path))
print("RGBA exists:", os.path.exists(rgba_path))

