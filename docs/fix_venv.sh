#!/bin/bash
# 修复虚拟环境

cd /root/voice-service/fish-speech

# 删除旧的
rm -rf venv

# 重新创建
python3 -m venv venv --clear

# 激活
source venv/bin/activate

# 升级 pip
pip install --upgrade pip

# 安装依赖
pip install torch==2.4.0 torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
pip install -e .

echo "✓ 虚拟环境修复完成"
