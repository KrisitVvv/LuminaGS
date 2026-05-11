#Requires -RunAsAdministrator
# LuminaGS 环境一键安装脚本 (PowerShell 版本)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host " 环境一键安装" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 检查是否在正确的目录
if (-not (Test-Path "environment.yml")) {
    Write-Host "[错误] 请在 GS-IR 目录下运行此脚本" -ForegroundColor Red
    Read-Host "按回车键退出"
    exit 1
}

# 步骤 1: 创建 Conda 环境
Write-Host "[步骤 1/6] 创建 Conda 环境..." -ForegroundColor Green
Write-Host ""
conda env create --file environment.yml -y
if ($LASTEXITCODE -ne 0) {
    Write-Host "[警告] Conda 环境创建可能已存在或失败，继续执行..." -ForegroundColor Yellow
}
Write-Host ""

# 步骤 2: 激活环境并安装 kornia
Write-Host "[步骤 2/6] 激活环境并安装 kornia..." -ForegroundColor Green
Write-Host ""
$env:CONDA_DEFAULT_ENV = "gsir"
pip install kornia
if ($LASTEXITCODE -ne 0) {
    Write-Host "[错误] kornia 安装失败" -ForegroundColor Red
    Read-Host "按回车键退出"
    exit 1
}
Write-Host ""

# 步骤 3: 卸载 CPU 版本 PyTorch
Write-Host "[步骤 3/6] 卸载 CPU 版本 PyTorch..." -ForegroundColor Green
Write-Host ""
pip uninstall -y torch torchvision torchaudio
if ($LASTEXITCODE -ne 0) {
    Write-Host "[警告] 卸载 PyTorch 时出现问题，继续执行..." -ForegroundColor Yellow
}
Write-Host ""

# 步骤 4: 安装 GPU 版本 PyTorch (CUDA 11.6)
Write-Host "[步骤 4/6] 安装 GPU 版本 PyTorch (CUDA 11.6)..." -ForegroundColor Green
Write-Host ""
pip install torch==1.13.1+cu116 torchvision==0.14.1+cu116 --extra-index-url https://download.pytorch.org/whl/cu116
if ($LASTEXITCODE -ne 0) {
    Write-Host "[错误] GPU 版本 PyTorch 安装失败" -ForegroundColor Red
    Read-Host "按回车键退出"
    exit 1
}
Write-Host ""

# 步骤 5: 安装本地扩展模块
Write-Host "[步骤 5/6] 安装本地扩展模块..." -ForegroundColor Green
Write-Host ""

# 安装 gs-ir 模块
Write-Host "[5.1/4] 安装 gs-ir 模块..." -ForegroundColor Cyan
if (Test-Path "gs-ir\setup.py") {
    Set-Location "gs-ir"
    python setup.py develop
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[错误] gs-ir 安装失败" -ForegroundColor Red
        Set-Location ".."
        Read-Host "按回车键退出"
        exit 1
    }
    Set-Location ".."
} else {
    Write-Host "[错误] 未找到 gs-ir\setup.py" -ForegroundColor Red
    Read-Host "按回车键退出"
    exit 1
}

# 安装 nvdiffrast 模块
Write-Host "[3.2/4] 安装 nvdiffrast 模块..." -ForegroundColor Cyan
if (Test-Path "submodules\nvdiffrast") {
    Set-Location "submodules"
    pip install ./nvdiffrast --no-build-isolation
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[错误] nvdiffrast 安装失败" -ForegroundColor Red
        Set-Location ".."
        Read-Host "按回车键退出"
        exit 1
    }
    Set-Location ".."
} else {
    Write-Host "[错误] 未找到 submodules\nvdiffrast" -ForegroundColor Red
    Read-Host "按回车键退出"
    exit 1
}

# 安装 simple-knn 模块
Write-Host "[3.3/4] 安装 simple-knn 模块..." -ForegroundColor Cyan
if (Test-Path "submodules\simple-knn") {
    Set-Location "submodules"
    pip install ./simple-knn
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[错误] simple-knn 安装失败" -ForegroundColor Red
        Set-Location ".."
        Read-Host "按回车键退出"
        exit 1
    }
    Set-Location ".."
} else {
    Write-Host "[错误] 未找到 submodules\simple-knn" -ForegroundColor Red
    Read-Host "按回车键退出"
    exit 1
}

# 安装 diff-gaussian-rasterization 模块
Write-Host "[3.4/4] 安装 diff-gaussian-rasterization 模块..." -ForegroundColor Cyan
if (Test-Path "submodules\diff-gaussian-rasterization") {
    Set-Location "submodules"
    pip install ./diff-gaussian-rasterization --no-build-isolation
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[错误] diff-gaussian-rasterization 安装失败" -ForegroundColor Red
        Set-Location ".."
        Read-Host "按回车键退出"
        exit 1
    }
    Set-Location ".."
} else {
    Write-Host "[错误] 未找到 submodules\diff-gaussian-rasterization" -ForegroundColor Red
    Read-Host "按回车键退出"
    exit 1
}
Write-Host ""

# 步骤 6: 验证安装
Write-Host "[步骤 6/6] 验证安装..." -ForegroundColor Green
Write-Host ""
$testScript = @"
import torch
print(f'PyTorch 版本：{torch.__version__}')
print(f'CUDA 可用：{torch.cuda.is_available()}')
import nvdiffrast
print('nvdiffrast 导入成功')
import simple_knn
print('simple_knn 导入成功')
from diff_gaussian_rasterization import GaussianRasterizationSettings
print('diff-gaussian-rasterization 导入成功')
"@

python -c $testScript
if ($LASTEXITCODE -ne 0) {
    Write-Host "[错误] 验证失败" -ForegroundColor Red
    Read-Host "按回车键退出"
    exit 1
}
Write-Host ""

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  安装完成！" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "请使用以下命令激活环境:" -ForegroundColor Yellow
Write-Host "  conda activate 3dgs-view" -ForegroundColor White
Write-Host ""
Read-Host "按回车键退出"
