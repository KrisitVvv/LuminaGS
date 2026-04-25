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

import json
import os
import sys
from pathlib import Path
from typing import Dict, List, NamedTuple, Optional, Tuple

import numpy as np
import torch
from PIL import Image
from plyfile import PlyData, PlyElement

from scene.colmap_loader import (
    qvec2rotmat,
    read_extrinsics_binary,
    read_extrinsics_text,
    read_intrinsics_binary,
    read_intrinsics_text,
    read_points3D_binary,
    read_points3D_text,
)
from scene.gaussian_model import BasicPointCloud
from utils.graphics_utils import focal2fov, fov2focal, getWorld2View2
from utils.sh_utils import SH2RGB


class CameraInfo(NamedTuple):
    uid: int
    R: np.ndarray
    T: np.ndarray
    FovY: float
    FovX: float
    image: Image.Image
    image_path: str
    image_name: str
    width: int
    height: int
    gt_normal: torch.Tensor = None
    da3_normal_conf: torch.Tensor = None
    da3_depth: torch.Tensor = None


class SceneInfo(NamedTuple):
    point_cloud: Optional[BasicPointCloud]
    train_cameras: List
    test_cameras: List
    nerf_normalization: Dict
    ply_path: str


def getNerfppNorm(cam_info: List[CameraInfo]) -> Dict:
    def get_center_and_diag(cam_centers: List[np.ndarray]) -> Tuple[np.ndarray, np.ndarray]:
        cam_centers = np.hstack(cam_centers)
        avg_cam_center = np.mean(cam_centers, axis=1, keepdims=True)
        center = avg_cam_center
        dist = np.linalg.norm(cam_centers - center, axis=0, keepdims=True)
        diagonal = np.max(dist)
        return center.flatten(), diagonal

    cam_centers = []

    for cam in cam_info:
        W2C = getWorld2View2(cam.R, cam.T)
        C2W = np.linalg.inv(W2C)
        cam_centers.append(C2W[:3, 3:4])

    center, diagonal = get_center_and_diag(cam_centers)
    radius = diagonal * 1.1

    translate = -center

    return {"translate": translate, "radius": radius}


def readColmapCameras(
    cam_extrinsics: Dict, cam_intrinsics: Dict, images_folder: str
) -> List[CameraInfo]:
    cam_infos = []
    for idx, key in enumerate(cam_extrinsics):
        sys.stdout.write("\r")
        # the exact output you're looking for:
        sys.stdout.write(f"Reading camera {idx + 1}/{len(cam_extrinsics)}")
        sys.stdout.flush()

        extr = cam_extrinsics[key]
        intr = cam_intrinsics[extr.camera_id]
        height = intr.height
        width = intr.width

        uid = intr.id
        R = np.transpose(qvec2rotmat(extr.qvec))
        T = np.array(extr.tvec)

        if intr.model == "SIMPLE_PINHOLE":
            focal_length_x = intr.params[0]
            FovY = focal2fov(focal_length_x, height)
            FovX = focal2fov(focal_length_x, width)
        elif intr.model == "PINHOLE":
            focal_length_x = intr.params[0]
            focal_length_y = intr.params[1]
            FovY = focal2fov(focal_length_y, height)
            FovX = focal2fov(focal_length_x, width)
        else:
            assert (
                False
            ), "Colmap camera model not handled: only undistorted datasets (PINHOLE or SIMPLE_PINHOLE cameras) supported!"

        image_path = os.path.join(images_folder, os.path.basename(extr.name))
        image_name = os.path.basename(image_path).split(".")[0]
        image = Image.open(image_path)

        cam_info = CameraInfo(
            uid=uid,
            R=R,
            T=T,
            FovY=FovY,
            FovX=FovX,
            image=image,
            image_path=image_path,
            image_name=image_name,
            width=width,
            height=height,
        )
        cam_infos.append(cam_info)
    sys.stdout.write("\n")
    return cam_infos


def fetchPly(path: str) -> BasicPointCloud:
    plydata = PlyData.read(path)
    vertices = plydata["vertex"]
    positions = np.vstack([vertices["x"], vertices["y"], vertices["z"]]).T
    colors = np.vstack([vertices["red"], vertices["green"], vertices["blue"]]).T / 255.0
    normals = np.vstack([vertices["nx"], vertices["ny"], vertices["nz"]]).T
    return BasicPointCloud(points=positions, colors=colors, normals=normals)


def storePly(path: str, xyz: np.ndarray, rgb: np.ndarray) -> None:
    # Define the dtype for the structured array
    dtype = [
        ("x", "f4"),
        ("y", "f4"),
        ("z", "f4"),
        ("nx", "f4"),
        ("ny", "f4"),
        ("nz", "f4"),
        ("red", "u1"),
        ("green", "u1"),
        ("blue", "u1"),
    ]

    normals = np.zeros_like(xyz)

    elements = np.empty(xyz.shape[0], dtype=dtype)
    attributes = np.concatenate((xyz, normals, rgb), axis=1)
    elements[:] = list(map(tuple, attributes))

    # Create the PlyData object and write to file
    vertex_element = PlyElement.describe(elements, "vertex")
    ply_data = PlyData([vertex_element])
    ply_data.write(path)


def readColmapSceneInfo(path: str, images: str, eval: bool, llffhold: int = 8) -> SceneInfo:
    try:
        cameras_extrinsic_file = os.path.join(path, "sparse/0", "images.bin")
        cameras_intrinsic_file = os.path.join(path, "sparse/0", "cameras.bin")
        cam_extrinsics = read_extrinsics_binary(cameras_extrinsic_file)
        cam_intrinsics = read_intrinsics_binary(cameras_intrinsic_file)
    except:
        cameras_extrinsic_file = os.path.join(path, "sparse/0", "images.txt")
        cameras_intrinsic_file = os.path.join(path, "sparse/0", "cameras.txt")
        cam_extrinsics = read_extrinsics_text(cameras_extrinsic_file)
        cam_intrinsics = read_intrinsics_text(cameras_intrinsic_file)

    reading_dir = "images" if images == None else images
    cam_infos_unsorted = readColmapCameras(
        cam_extrinsics=cam_extrinsics,
        cam_intrinsics=cam_intrinsics,
        images_folder=os.path.join(path, reading_dir),
    )
    cam_infos = sorted(cam_infos_unsorted.copy(), key=lambda x: x.image_name)

    if eval:
        train_cam_infos = [c for idx, c in enumerate(cam_infos) if idx % llffhold != 0]
        test_cam_infos = [c for idx, c in enumerate(cam_infos) if idx % llffhold == 0]
    else:
        train_cam_infos = cam_infos
        test_cam_infos = []

    nerf_normalization = getNerfppNorm(train_cam_infos)

    ply_path = os.path.join(path, "sparse/0/points3D.ply")
    bin_path = os.path.join(path, "sparse/0/points3D.bin")
    txt_path = os.path.join(path, "sparse/0/points3D.txt")
    if not os.path.exists(ply_path):
        print("Converting point3d.bin to .ply, will happen only the first time you open the scene.")
        try:
            xyz, rgb, _ = read_points3D_binary(bin_path)
        except:
            xyz, rgb, _ = read_points3D_text(txt_path)
        storePly(ply_path, xyz, rgb)
    try:
        pcd = fetchPly(ply_path)
    except:
        pcd = None

    scene_info = SceneInfo(
        point_cloud=pcd,
        train_cameras=train_cam_infos,
        test_cameras=test_cam_infos,
        nerf_normalization=nerf_normalization,
        ply_path=ply_path,
    )
    return scene_info


def readCamerasFromTransforms(
    path: str, 
    transformsfile: str, 
    white_background: bool, 
    extension: str = ".png",
    use_da3_normal: bool = False,
    da3_normal_root: str = ""
) -> List[CameraInfo]:
    cam_infos = []

    with open(os.path.join(path, transformsfile)) as json_file:
        contents = json.load(json_file)

    fovx = contents["camera_angle_x"]
    frames = contents["frames"]
    for idx, frame in enumerate(frames):
        cam_name = os.path.join(path, frame["file_path"] + extension)

        # NeRF 'transform_matrix' is a camera-to-world transform
        c2w = np.array(frame["transform_matrix"])
        # change from OpenGL/Blender camera axes (Y up, Z back) to COLMAP (Y down, Z forward)
        c2w[:3, 1:3] *= -1

        # get the world-to-camera transform and set R, T
        w2c = np.linalg.inv(c2w)
        R = np.transpose(w2c[:3, :3])  # R is stored transposed due to 'glm' in CUDA code
        T = w2c[:3, 3]

        image_path = os.path.join(path, cam_name)
        image_name = Path(cam_name).stem
        image = Image.open(image_path)

        # im_data = np.array(image.convert("RGBA"))

        # bg = np.array([1, 1, 1]) if white_background else np.array([0, 0, 0])

        # norm_data = im_data / 255.0
        # arr = norm_data[:, :, :3] * norm_data[:, :, 3:4] + bg * (1 - norm_data[:, :, 3:4])
        # image = Image.fromarray(np.array(arr * 255.0, dtype=np.byte), "RGB")

        fovy = focal2fov(fov2focal(fovx, image.size[0]), image.size[1])
        FovY = fovy
        FovX = fovx

        os.environ["OPENCV_IO_ENABLE_OPENEXR"] = "1"
        import imageio.v3 as iio
        import torch.nn.functional as F
        
        if use_da3_normal:
            # === 核心修正：适配 Marigold 的独立文件夹结构 ===
            # 在脚本中传入的 da3_normal_root 应该是 "marigold_final" 的路径
            rel_path = os.path.relpath(image_path, path)
            rel_dir = os.path.dirname(rel_path)

            # 1. 拼接法线路径：marigold_final/normals_npy/train_000_rgba_normals.npy
            normal_path = os.path.join(da3_normal_root, "normals_npy", f"{image_name}_rgba_normals.npy")

            # 2. 拼接置信度路径：marigold_final/conf_npy/train_000_rgba_conf.npy
            conf_path = os.path.join(da3_normal_root, "conf_npy", f"{image_name}_rgba_conf.npy")

            # 3. 深度路径（如果需要，假设存放在 depth_npy 下）
            depth_path = os.path.join(da3_normal_root, "depth_npy", f"{image_name}_rgba_depth.npy")
            # 如果没有专门的 depth_npy，保留原来的 fallback 逻辑
            if not os.path.exists(depth_path):
                 depth_path = os.path.join(da3_normal_root, rel_dir, "depth.npy")
        else:
            view_dir = os.path.dirname(image_path)
            normal_path = os.path.join(view_dir, "normal.exr")
            conf_path = os.path.join(view_dir, "conf.exr")
            depth_path = os.path.join(view_dir, "depth.exr")
            
        if os.path.exists(normal_path):
            if normal_path.endswith(".exr"):
                # imageio 读取 EXR 天然就是最纯正的 RGB 顺序和 FP32 精度，绝不乱转通道！
                normal_data = iio.imread(normal_path)  # 形状为 [H, W, 3] 或 [H, W, 4]
            elif normal_path.endswith(".npy"):
                normal_data = np.load(normal_path, mmap_mode="r")
            else:
                normal_data = None
                
            if normal_data is not None:
                # 防御性编程：如果是 RGBA (4通道)，只取前 3 个通道 (RGB)
                if normal_data.shape[-1] == 4:
                    normal_data = normal_data[:, :, :3]
                gt_normal = torch.from_numpy(normal_data).permute(2, 0, 1).float() # 保证 [3, H, W]
                # 确保法线归一化 (无论是否是 DA3，保持物理意义正确)
                gt_normal = F.normalize(gt_normal, p=2, dim=0, eps=1e-6)
            else:
                gt_normal = None
        else:
            gt_normal = None
            
        # 加载DA3置信度图
        da3_normal_conf = None
        if os.path.exists(conf_path):
            if conf_path.endswith(".exr"):
                conf_data = iio.imread(conf_path)
            elif conf_path.endswith(".npy"):
                conf_data = np.load(conf_path, mmap_mode="r")
            else:
                conf_data = None
            
            if conf_data is not None:
                if len(conf_data.shape) == 3:
                    conf_data = conf_data[:, :, 0]  # 取单通道
                da3_normal_conf = torch.from_numpy(conf_data).unsqueeze(0).float()  # [1, H, W]

        # 加载DA3深度图
        da3_depth = None
        if os.path.exists(depth_path):
            if depth_path.endswith(".exr"):
                depth_data = iio.imread(depth_path)
            elif depth_path.endswith(".npy"):
                depth_data = np.load(depth_path, mmap_mode="r")
            else:
                depth_data = None
                
            if depth_data is not None:
                if len(depth_data.shape) == 3:
                    depth_data = depth_data[:, :, 0]  # 取单通道
                da3_depth = torch.from_numpy(depth_data).unsqueeze(0).float()  # [1, H, W]

        cam_infos.append(
            CameraInfo(
                uid=idx,
                R=R,
                T=T,
                FovY=FovY,
                FovX=FovX,
                image=image,
                image_path=image_path,
                image_name=image_name,
                width=image.size[0],
                height=image.size[1],
                gt_normal=gt_normal,
                da3_normal_conf=da3_normal_conf,
                da3_depth=da3_depth,
            )
        )

    return cam_infos


def readNerfSyntheticInfo(
    path: str, 
    white_background: bool, 
    eval: bool, 
    extension: str = ".png",
    use_da3_normal: bool = False,
    da3_normal_root: str = ""
) -> SceneInfo:
    print("Reading Training Transforms")
    train_cam_infos = readCamerasFromTransforms(
        path, "transforms_train.json", white_background, extension,
        use_da3_normal=use_da3_normal,
        da3_normal_root=da3_normal_root
    )
    print("Reading Test Transforms")
    test_cam_infos = readCamerasFromTransforms(
        path, "transforms_test.json", white_background, extension,
        # 评估阶段固定使用数据集自带 GT normal/conf/depth（view_dir 下的 .exr）
        # 避免测试集被 Marigold 伪真值覆盖，确保 angle error 热力图基于真实 GT。
        use_da3_normal=False,
        da3_normal_root=da3_normal_root
    )

    if not eval:
        train_cam_infos.extend(test_cam_infos)
        test_cam_infos = []

    nerf_normalization = getNerfppNorm(train_cam_infos)

    ply_path = os.path.join(path, "points3d.ply")
    if not os.path.exists(ply_path):
        # Since this data set has no colmap data, we start with random points
        num_pts = 100_000
        print(f"Generating random point cloud ({num_pts})...")

        # We create random points inside the bounds of the synthetic Blender scenes
        xyz = np.random.random((num_pts, 3)) * 2.6 - 1.3
        shs = np.random.random((num_pts, 3)) / 255.0
        pcd = BasicPointCloud(points=xyz, colors=SH2RGB(shs), normals=np.zeros((num_pts, 3)))

        storePly(ply_path, xyz, SH2RGB(shs) * 255)
    try:
        pcd = fetchPly(ply_path)
    except:
        pcd = None

    scene_info = SceneInfo(
        point_cloud=pcd,
        train_cameras=train_cam_infos,
        test_cameras=test_cam_infos,
        nerf_normalization=nerf_normalization,
        ply_path=ply_path,
    )
    return scene_info


sceneLoadTypeCallbacks = {"Colmap": readColmapSceneInfo, "Blender": readNerfSyntheticInfo}
