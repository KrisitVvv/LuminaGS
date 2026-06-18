@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo ========================================
echo   环境一键安装
echo ========================================
echo.

REM 检查是否在正确的目录
if not exist "environment.yml" (
    echo [错误] 请在 GS-IR 目录下运行此脚本
    pause
    exit /b 1
)

echo [步骤 1/6] 创建 Conda 环境...
echo.
call conda env create --file environment.yml -y
if errorlevel 1 (
    echo [警告] Conda 环境创建可能已存在或失败，继续执行...
)
echo.

echo [步骤 2/6] 激活环境并安装 kornia...
echo.
call conda activate gsir
if errorlevel 1 (
    echo [错误] 无法激活 Conda 环境
    pause
    exit /b 1
)

pip install kornia
if errorlevel 1 (
    echo [错误] kornia 安装失败
    pause
    exit /b 1
)
echo.

echo [步骤 3/6] 卸载 CPU 版本 PyTorch...
echo.
pip uninstall -y torch torchvision torchaudio
if errorlevel 1 (
    echo [警告] 卸载 PyTorch 时出现问题，继续执行...
)
echo.

echo [步骤 4/6] 安装 GPU 版本 PyTorch (CUDA 11.6)...
echo.
pip install torch==1.13.1+cu116 torchvision==0.14.1+cu116 --extra-index-url https://download.pytorch.org/whl/cu116
if errorlevel 1 (
    echo [错误] GPU 版本 PyTorch 安装失败
    pause
    exit /b 1
)
echo.

echo [步骤 5/6] 安装本地扩展模块...
echo.

REM 安装 gs-ir 模块
echo [5.1/4] 安装 gs-ir 模块...
if exist "gs-ir\setup.py" (
    cd gs-ir
    python setup.py develop
    if errorlevel 1 (
        echo [错误] gs-ir 安装失败
        cd ..
        pause
        exit /b 1
    )
    cd ..
) else (
    echo [错误] 未找到 gs-ir\setup.py
    pause
    exit /b 1
)

REM 安装 nvdiffrast 模块
echo [3.2/4] 安装 nvdiffrast 模块...
if exist "submodules\nvdiffrast" (
    cd submodules
    pip install ./nvdiffrast --no-build-isolation
    if errorlevel 1 (
        echo [错误] nvdiffrast 安装失败
        cd ..
        pause
        exit /b 1
    )
    cd ..
) else (
    echo [错误] 未找到 submodules\nvdiffrast
    pause
    exit /b 1
)

REM 安装 simple-knn 模块
echo [3.3/4] 安装 simple-knn 模块...
if exist "submodules\simple-knn" (
    cd submodules
    pip install ./simple-knn
    if errorlevel 1 (
        echo [错误] simple-knn 安装失败
        cd ..
        pause
        exit /b 1
    )
    cd ..
) else (
    echo [错误] 未找到 submodules\simple-knn
    pause
    exit /b 1
)

REM 安装 diff-gaussian-rasterization 模块
echo [3.4/4] 安装 diff-gaussian-rasterization 模块...
if exist "submodules\diff-gaussian-rasterization" (
    cd submodules
    pip install ./diff-gaussian-rasterization --no-build-isolation
    if errorlevel 1 (
        echo [错误] diff-gaussian-rasterization 安装失败
        cd ..
        pause
        exit /b 1
    )
    cd ..
) else (
    echo [错误] 未找到 submodules\diff-gaussian-rasterization
    pause
    exit /b 1
)
echo.

echo [步骤 6/6] 验证安装...
echo.
python -c "import torch; print(f'PyTorch 版本：{torch.__version__}'); print(f'CUDA 可用：{torch.cuda.is_available()}'); import nvdiffrast; print('nvdiffrast 导入成功'); import simple_knn; print('simple_knn 导入成功'); from diff_gaussian_rasterization import GaussianRasterizationSettings; print('diff-gaussian-rasterization 导入成功')"
if errorlevel 1 (
    echo [错误] 验证失败
    pause
    exit /b 1
)
echo.

echo ========================================
echo   安装完成！
echo ========================================
pause
