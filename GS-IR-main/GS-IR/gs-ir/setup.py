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

from setuptools import setup
from torch.utils.cpp_extension import CUDAExtension, BuildExtension
import os
import suppress_warnings

os.path.dirname(os.path.abspath(__file__))

setup(
    name="gs_ir",
    packages=["gs_ir"],
    ext_modules=[
        CUDAExtension(
            name="gs_ir._C",
            sources=[
                "src/bindings.cpp",
                "src/irradiance_kernel.cu",
                "src/occlusion_kernel.cu",
            ],
            extra_compile_args={
            'nvcc': [
                '-allow-unsupported-compiler',  # 核心：跳过VS版本检查
                '--expt-relaxed-constexpr',
                '-I', '.',
                '-Xcompiler', '/MD',  # 适配Windows运行时
                '-Xcompiler', '/wd4819',  # 忽略编码警告
                '-Xcompiler', '/wd4251',  # 忽略dll接口警告
                '-Xcompiler', '/wd4244',  # 忽略类型转换警告
                '-Xcompiler', '/wd4267',  # 忽略尺寸转换警告
                '-Xcompiler', '/wd4275',  # 忽略非dll接口警告
                '-Xcompiler', '/wd4018',  # 忽略符号比较警告
                '-Xcompiler', '/wd4190',  # 忽略C链接警告
		        '-Xcompiler=/wd4624',  # 抑制析构函数删除警告
                '-Xcompiler=/wd4005',  # 抑制宏重定义警告
                '-Xcompiler=/wd4067',  # 抑制预处理器指令警告
                '-Xcompiler=/wd4805',
                '-Xcompiler', '/EHsc',     # 设置异常处理模型
            ]
        }
        )
    ],
    cmdclass={"build_ext": BuildExtension},
)
