@echo off
echo === ComfyUI 3D查看器插件快速测试 ===
echo.

REM 检查Python是否可用
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python未找到，请确保Python已安装并在PATH中
    pause
    exit /b 1
)

echo ✅ Python已找到
echo.

REM 运行测试脚本
python test_plugin.py

echo.
echo === 测试完成 ===
echo.
echo 如果测试显示文件不存在，请：
echo 1. 确保ve2.html文件在ComfyUI目录中
echo 2. 或在节点的viewer_path参数中指定完整路径
echo.
pause

