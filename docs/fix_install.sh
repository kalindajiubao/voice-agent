#!/bin/bash
# 修复 Fish Speech 安装

cd /root/voice-service/fish-speech
source venv/bin/activate

echo "重新安装 Fish Speech..."

# 方式1: 用 pip 安装
pip install -e .

# 方式2: 如果方式1失败，直接安装 release 版本
# pip install fish-speech

echo "检查安装..."
python -c "import fish_speech; print('✓ fish_speech 安装成功')"
python -c "from fish_speech.webui import main; print('✓ webui 模块可用')"
