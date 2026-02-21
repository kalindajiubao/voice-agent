#!/bin/bash
# 完整下载 Fish Speech 模型

cd /root/voice-service/fish-speech
source venv/bin/activate

mkdir -p checkpoints/fish-speech-1.5
cd checkpoints/fish-speech-1.5

echo "使用 hf-mirror 下载模型..."
export HF_ENDPOINT=https://hf-mirror.com

# 下载主要文件
huggingface-cli download fishaudio/fish-speech-1.5 \
    --local-dir . \
    --local-dir-use-symlinks False

echo ""
echo "下载完成，检查文件:"
ls -lh
