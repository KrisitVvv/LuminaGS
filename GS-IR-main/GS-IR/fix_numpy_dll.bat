@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo ========================================
echo   修复 NumPy DLL 加载问题
echo ========================================
echo.

REM 检查是否在正确的目录
if not exist "environment.yml" (
    echo [错误] 请在 GS-IR 目录下运行此脚本
    pause
    exit /b 1
)

echo [步骤 1/4] 激活 Conda 环境...
echo.
call conda activate gsir
if errorlevel 1 (
    echo [错误] 无法激活 Conda 环境
    pause
    exit /b 1
)

echo [步骤 2/4] 卸载现有 NumPy...
echo.
pip uninstall -y numpy
if errorlevel 1 (
    echo [警告] 卸载 NumPy 时出现问题，继续执行...
)
echo.

echo [步骤 3/4] 清理 pip 缓存...
echo.
pip cache purge
echo.

echo [步骤 4/4] 重新安装 NumPy...
echo.
pip install numpy==1.21.6 --no-cache-dir
if errorlevel 1 (
    echo [错误] NumPy 安装失败
    pause
    exit /b 1
)
echo.

echo ========================================
echo   验证安装...
echo ========================================
echo.

python -c "import numpy; print('NumPy 版本:', numpy.__version__); import torch; print('PyTorch 版本:', torch.__version__); import torchvision; print('Torchvision 版本:', torchvision.__version__)"
if errorlevel 1 (
    echo [错误] 验证失败
    pause
    exit /b 1
)

echo.
echo ========================================
echo   修复完成！
echo ========================================
echo.
pause
