#!/bin/bash
# 安装 Fish Speech 所有依赖

cd /root/voice-service/fish-speech
source venv/bin/activate

echo "安装核心依赖..."
pip install fastapi uvicorn gradio

pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

pip install transformers accelerate bitsandbytes

pip install einops omegaconf hydra-core

pip install vector-quantize-pytorch

pip install sentencepiece

echo "安装 Fish Speech 依赖..."
pip install -r requirements.txt 2>/dev/null || echo "requirements.txt 不存在，跳过"

echo "✓ 依赖安装完成"
