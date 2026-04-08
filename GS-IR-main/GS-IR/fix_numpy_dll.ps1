#requires -Version 5.0

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  修复 NumPy DLL 加载问题" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 检查是否在正确的目录
if (-not (Test-Path "environment.yml")) {
    Write-Host "[错误] 请在 GS-IR 目录下运行此脚本" -ForegroundColor Red
    Start-Sleep -Seconds 2
    exit 1
}

Write-Host "[步骤 1/4] 激活 Conda 环境..." -ForegroundColor Yellow
Write-Host ""

$condaEnvPath = "$env:USERPROFILE\.miniconda3\envs\gsir"
if (Test-Path "E:\conda\envs\gsir") {
    $condaEnvPath = "E:\conda\envs\gsir"
}

$pythonExe = Join-Path $condaEnvPath "python.exe"
$pipExe = Join-Path $condaEnvPath "Scripts\pip.exe"

if (-not (Test-Path $pythonExe)) {
    Write-Host "[错误] 找不到 Python: $pythonExe" -ForegroundColor Red
    Start-Sleep -Seconds 2
    exit 1
}

Write-Host "使用 Python: $pythonExe" -ForegroundColor Green
Write-Host ""

Write-Host "[步骤 2/4] 卸载现有 NumPy..." -ForegroundColor Yellow
Write-Host ""
& $pipExe uninstall -y numpy
Write-Host ""

Write-Host "[步骤 3/4] 清理 pip 缓存..." -ForegroundColor Yellow
Write-Host ""
& $pipExe cache purge
Write-Host ""

Write-Host "[步骤 4/4] 重新安装 NumPy..." -ForegroundColor Yellow
Write-Host ""
& $pipExe install numpy==1.21.6 --no-cache-dir
if ($LASTEXITCODE -ne 0) {
    Write-Host "[错误] NumPy 安装失败" -ForegroundColor Red
    Start-Sleep -Seconds 2
    exit 1
}
Write-Host ""

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  验证安装..." -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

& $pythonExe -c "import numpy; print('NumPy 版本:', numpy.__version__); import torch; print('PyTorch 版本:', torch.__version__); import torchvision; print('Torchvision 版本:', torchvision.__version__)"
if ($LASTEXITCODE -ne 0) {
    Write-Host "[错误] 验证失败" -ForegroundColor Red
    Start-Sleep -Seconds 2
    exit 1
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  修复完成！" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""

Start-Sleep -Seconds 2
