@echo off
chcp 65001 > nul
title Git同步到Gitee

echo ========================================
echo    Git 同步到 Gitee
echo ========================================
echo.

:: 检查是否在Git仓库中
git rev-parse --git-dir > nul 2>&1
if errorlevel 1 (
    echo [错误] 当前目录不是Git仓库！
    echo 请确保在项目根目录运行此脚本
    pause
    exit /b 1
)

:: 显示当前状态
echo [1/5] 检查文件状态...
git status --short
echo.

:: 添加所有变更
echo [2/5] 添加所有变更到暂存区...
git add .
if errorlevel 1 (
    echo [错误] git add 失败
    pause
    exit /b 1
)
echo 添加完成
echo.

:: 检查是否有变更需要提交
git diff --cached --quiet
if errorlevel 1 (
    goto :has_changes
) else (
    echo [提示] 没有需要提交的变更，跳过提交步骤
    goto :skip_commit
)

:has_changes
:: 获取提交信息
set /p commit_msg="请输入提交信息（直接回车使用默认信息）: "
if "%commit_msg%"=="" set commit_msg=同步代码更新

:: 提交变更
echo [3/5] 提交变更...
git commit -m "%commit_msg%"
if errorlevel 1 (
    echo [错误] git commit 失败
    pause
    exit /b 1
)
echo 提交成功
echo.

:skip_commit
:: 拉取远程更新
echo [4/5] 拉取远程最新代码...
git pull origin master --no-rebase
if errorlevel 1 (
    echo [警告] git pull 失败，尝试强制拉取...
    git fetch origin
    git reset --hard origin/master
    echo 已强制同步到远程版本
)
echo 拉取完成
echo.

:: 推送到远程
echo [5/5] 推送到 Gitee...
git push origin master
if errorlevel 1 (
    echo [错误] git push 失败
    echo 请检查网络连接和Gitee认证信息
    pause
    exit /b 1
)
echo.

echo ========================================
echo    同步完成！ 🎉
echo ========================================
echo.
echo 查看仓库: https://gitee.com/sapfans126/express_quant
echo.

pause