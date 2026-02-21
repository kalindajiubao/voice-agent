#!/bin/bash
# 手动下载 Fish Speech 模型

cd /root/voice-service/fish-speech
source venv/bin/activate

mkdir -p checkpoints/fish-speech-1.5

echo "下载模型文件..."

# 方法1: 使用 huggingface_hub
python3 <> 'PYEOF'
from huggingface_hub import snapshot_download
import os

os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'  # 使用镜像

try:
    snapshot_download(
        repo_id="fishaudio/fish-speech-1.5",
        local_dir="checkpoints/fish-speech-1.5",
        local_dir_use_symlinks=False,
        resume_download=True
    )
    print("✓ 模型下载完成")
except Exception as e:
    print(f"下载失败: {e}")
PYEOF

# 检查文件
echo ""
echo "检查模型文件..."
ls -lh checkpoints/fish-speech-1.5/
