@echo off
title 短线选股系统
echo ========================================
echo   📈 短线选股系统 - 启动中...
echo ========================================
echo.

echo [1/2] 启动后端服务 (port 8000)...
start "后端" cmd /c "cd /d %~dp0backend && python main.py"

timeout /t 3 /nobreak >nul

echo [2/2] 启动前端服务 (port 3000)...
start "前端" cmd /c "cd /d %~dp0frontend && npm run dev"

echo.
echo ========================================
echo   ✅ 启动完成！
echo   前端访问: http://localhost:3000
echo   后端API:  http://localhost:8000
echo ========================================
echo.
echo 关闭本窗口不会关闭后端和前端服务。
echo 请关闭两个服务窗口来停止系统。
pause
