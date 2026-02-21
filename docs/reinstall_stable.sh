#!/bin/bash
# 安装稳定版 Fish Speech

cd /root/voice-service
rm -rf fish-speech

# 克隆稳定版本
git clone --depth 1 --branch v1.5.0 https://github.com/fishaudio/fish-speech.git
cd fish-speech

# 创建新环境
python3 -m venv venv
source venv/bin/activate

# 安装依赖
pip install torch==2.4.0 torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

pip install -e .

# 下载模型
mkdir -p checkpoints
python -c "
from huggingface_hub import snapshot_download
import os
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'
snapshot_download('fishaudio/fish-speech-1.5', local_dir='checkpoints/fish-speech-1.5', local_dir_use_symlinks=False)
"

echo "✓ 安装完成"
