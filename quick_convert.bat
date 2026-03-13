@echo off
REM ========================================
REM 快速调用 convert.py 脚本
REM 用法：quick_convert.bat <目标文件夹路径>
REM ========================================

if "%~1"=="" (
    echo 错误：请提供目标文件夹路径
    echo 用法：%~nx0 ^<目标文件夹路径^>
    echo 示例：%~nx0 E:\YourDataFolder
    pause
    exit /b 1
)

set SCRIPT_DIR=%~dp0tools\gaussian-splatting
set TARGET_PATH=%~f1

echo ============================================================
echo 运行 COLMAP 数据集转换
echo ============================================================
echo 脚本路径：%SCRIPT_DIR%\convert.py
echo 目标路径：%TARGET_PATH%
echo ============================================================
echo.

cd /d "%SCRIPT_DIR%"
python convert.py -s "%TARGET_PATH%"

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ============================================================
    echo ✓ 转换完成！
    echo ============================================================
) else (
    echo.
    echo ============================================================
    echo ✗ 转换失败，退出代码：%ERRORLEVEL%
    echo ============================================================
)

pause
