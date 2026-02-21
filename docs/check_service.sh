#!/bin/bash
# 检查服务状态

echo "检查 7860 端口..."
netstat -tlnp | grep 7860 || ss -tlnp | grep 7860

echo ""
echo "检查 Fish Speech 进程..."
ps aux | grep api_server | grep -v grep

echo ""
echo "检查日志..."
tail -20 /root/voice-service/fish-speech/*.log 2>/dev/null || echo "无日志文件"
