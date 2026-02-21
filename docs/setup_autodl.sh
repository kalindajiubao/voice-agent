#!/bin/bash
# AutoDL 部署脚本 - Fish Speech + GPT-SoVITS
# 使用方法：在 AutoDL 实例中运行 bash setup_autodl.sh

set -e

echo "=== AutoDL 语音合成服务部署脚本 ==="
echo ""

# 检查是否在 AutoDL 环境中
if [ ! -d "/root/autodl-tmp" ]; then
    echo "警告：未检测到 AutoDL 环境，继续执行..."
fi

# 1. 安装基础依赖
echo "[1/6] 安装基础依赖..."
apt-get update -qq
apt-get install -y -qq git wget ffmpeg libsndfile1

# 2. 创建工作目录
WORK_DIR="/root/voice-service"
mkdir -p $WORK_DIR
cd $WORK_DIR

# 3. 部署 Fish Speech
echo "[2/6] 部署 Fish Speech..."
if [ ! -d "fish-speech" ]; then
    git clone --depth 1 https://github.com/fishaudio/fish-speech.git
fi
cd fish-speech

# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 安装依赖
pip install -q -e .
pip install -q gradio fastapi uvicorn

# 4. 下载模型
echo "[3/6] 下载 Fish Speech 模型..."
mkdir -p checkpoints
python -c "
from huggingface_hub import snapshot_download
import os
os.makedirs('checkpoints/fish-speech-1.5', exist_ok=True)
snapshot_download('fishaudio/fish-speech-1.5', local_dir='checkpoints/fish-speech-1.5')
" || echo "模型下载失败，请手动下载"

# 5. 创建 API 启动脚本
echo "[4/6] 创建启动脚本..."
cat > start_api.sh << 'EOF'
#!/bin/bash
cd /root/voice-service/fish-speech
source venv/bin/activate

# 启动 API 服务
python -m fish_speech.webui \
    --llama-checkpoint-path checkpoints/fish-speech-1.5 \
    --decoder-checkpoint-path checkpoints/fish-speech-1.5/firefly-gan-vq-fsq-8x1024-21hz-generator.pth \
    --device cuda \
    --server-name 0.0.0.0 \
    --server-port 7860
EOF
chmod +x start_api.sh

# 6. 创建 systemd 服务（可选）
echo "[5/6] 创建系统服务..."
cat > /etc/systemd/system/voice-tts.service << EOF
[Unit]
Description=Voice TTS Service
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/voice-service/fish-speech
ExecStart=/bin/bash /root/voice-service/fish-speech/start_api.sh
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# 7. 创建测试脚本
echo "[6/6] 创建测试脚本..."
cat > test_api.py << 'EOF'
#!/usr/bin/env python3
"""测试 TTS API"""
import requests
import json

BASE_URL = "http://localhost:7860"

def test_tts():
    """测试文字转语音"""
    data = {
        "text": "(happy) 你好，这是一个测试！",
        "temperature": 0.7,
        "top_p": 0.7
    }
    
    response = requests.post(f"{BASE_URL}/tts", json=data)
    if response.status_code == 200:
        with open("test_output.wav", "wb") as f:
            f.write(response.content)
        print("✓ TTS 测试成功，保存为 test_output.wav")
    else:
        print(f"✗ TTS 测试失败: {response.status_code}")

def test_clone():
    """测试音色克隆"""
    # 上传参考音频进行克隆
    with open("reference.wav", "rb") as f:
        files = {"reference_audio": f}
        data = {"text": "(angry) 这是克隆的音色！"}
        response = requests.post(f"{BASE_URL}/tts", files=files, data=data)
        
    if response.status_code == 200:
        with open("cloned_output.wav", "wb") as f:
            f.write(response.content)
        print("✓ 克隆测试成功，保存为 cloned_output.wav")
    else:
        print(f"✗ 克隆测试失败: {response.status_code}")

if __name__ == "__main__":
    print("测试 TTS API...")
    test_tts()
EOF
chmod +x test_api.py

echo ""
echo "=== 部署完成 ==="
echo ""
echo "启动服务:"
echo "  cd /root/voice-service/fish-speech"
echo "  bash start_api.sh"
echo ""
echo "API 地址:"
echo "  http://<你的AutoDL-IP>:7860"
echo ""
echo "测试服务:"
echo "  python test_api.py"
echo ""
echo "查看日志:"
echo "  tail -f /root/voice-service/fish-speech/webui.log"
