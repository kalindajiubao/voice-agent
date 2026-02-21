#!/bin/bash
# =============================================================================
# Voice Agent - AutoDL 一键部署脚本
# 使用方法: 在 AutoDL 实例中运行: bash deploy_autodl.sh
# =============================================================================

set -e  # 遇到错误立即退出

echo "========================================"
echo "  Voice Agent - AutoDL 部署脚本"
echo "========================================"
echo ""

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# =============================================================================
# 第1步: 环境检查
# =============================================================================
echo -e "${YELLOW}[1/6] 检查环境...${NC}"

# 检查是否在 AutoDL 环境
if [ ! -d "/root/autodl-tmp" ]; then
    echo -e "${YELLOW}警告: 未检测到 AutoDL 环境，继续执行...${NC}"
fi

# 检查 GPU
if ! which nvidia-smi > /dev/null 2>&1; then
    echo -e "${RED}错误: 未检测到 GPU，请确认实例类型${NC}"
    exit 1
fi

echo -e "${GREEN}✓ GPU 检测正常${NC}"
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader

# 检查 CUDA
if ! which nvcc > /dev/null 2>&1; then
    echo -e "${RED}错误: 未检测到 CUDA${NC}"
    exit 1
fi
echo -e "${GREEN}✓ CUDA 版本: $(nvcc --version | grep release | awk '{print $5}' | cut -d',' -f1)${NC}"

# =============================================================================
# 第2步: 安装系统依赖
# =============================================================================
echo ""
echo -e "${YELLOW}[2/6] 安装系统依赖...${NC}"

apt-get update -qq
apt-get install -y -qq \
    git \
    wget \
    ffmpeg \
    libsndfile1 \
    build-essential \
    python3-dev \
    portaudio19-dev

echo -e "${GREEN}✓ 系统依赖安装完成${NC}"

# =============================================================================
# 第3步: 克隆 Fish Speech
# =============================================================================
echo ""
echo -e "${YELLOW}[3/6] 下载 Fish Speech...${NC}"

WORK_DIR="/root/voice-service"
mkdir -p $WORK_DIR
cd $WORK_DIR

if [ -d "fish-speech" ]; then
    echo "Fish Speech 已存在，更新代码..."
    cd fish-speech
    git pull
else
    git clone --depth 1 https://github.com/fishaudio/fish-speech.git
    cd fish-speech
fi

echo -e "${GREEN}✓ Fish Speech 下载完成${NC}"

# =============================================================================
# 第4步: 创建虚拟环境并安装依赖
# =============================================================================
echo ""
echo -e "${YELLOW}[4/6] 安装 Python 依赖...${NC}"

# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 升级 pip
pip install -q --upgrade pip

# 安装 Fish Speech
pip install -q -e .

# 安装 API 服务依赖
pip install -q fastapi uvicorn gradio

echo -e "${GREEN}✓ Python 依赖安装完成${NC}"

# =============================================================================
# 第5步: 下载模型
# =============================================================================
echo ""
echo -e "${YELLOW}[5/6] 下载模型文件...${NC}"

mkdir -p checkpoints

# 使用 huggingface_hub 下载模型
python3 << 'EOF'
from huggingface_hub import snapshot_download
import os

model_path = "checkpoints/fish-speech-1.5"
os.makedirs(model_path, exist_ok=True)

try:
    print("正在下载 Fish Speech 1.5 模型...")
    snapshot_download(
        repo_id="fishaudio/fish-speech-1.5",
        local_dir=model_path,
        local_dir_use_symlinks=False
    )
    print("模型下载完成!")
except Exception as e:
    print(f"模型下载失败: {e}")
    print("请手动下载模型到 checkpoints/fish-speech-1.5/")
EOF

if [ -f "checkpoints/fish-speech-1.5/model.pth" ]; then
    echo -e "${GREEN}✓ 模型下载完成${NC}"
else
    echo -e "${YELLOW}⚠ 模型可能未完全下载，请检查 checkpoints/ 目录${NC}"
fi

# =============================================================================
# 第6步: 创建启动脚本
# =============================================================================
echo ""
echo -e "${YELLOW}[6/6] 创建启动脚本...${NC}"

# 创建启动脚本
cat > start_service.sh << 'EOF'
#!/bin/bash
cd /root/voice-service/fish-speech
source venv/bin/activate

# 设置环境变量
export CUDA_VISIBLE_DEVICES=0

# 启动 Fish Speech API 服务
echo "启动 Fish Speech 服务..."
echo "服务地址: http://0.0.0.0:7860"
echo ""

python -m fish_speech.webui \
    --llama-checkpoint-path checkpoints/fish-speech-1.5 \
    --decoder-checkpoint-path checkpoints/fish-speech-1.5/firefly-gan-vq-fsq-8x1024-21hz-generator.pth \
    --device cuda \
    --server-name 0.0.0.0 \
    --server-port 7860
EOF

chmod +x start_service.sh

# 创建测试脚本
cat > test_api.py << 'EOF'
#!/usr/bin/env python3
"""测试 Fish Speech API"""
import requests
import sys

BASE_URL = "http://localhost:7860"

def test_health():
    """测试服务是否运行"""
    try:
        response = requests.get(f"{BASE_URL}", timeout=5)
        print(f"✓ 服务状态: {response.status_code}")
        return True
    except:
        print("✗ 服务未启动或无法连接")
        return False

def test_tts():
    """测试文字转语音"""
    print("\n测试 TTS...")
    
    data = {
        "text": "(happy) 你好，这是 Fish Speech 的测试！",
        "temperature": 0.7,
        "top_p": 0.7
    }
    
    try:
        response = requests.post(f"{BASE_URL}/tts", json=data, timeout=60)
        if response.status_code == 200:
            with open("test_output.wav", "wb") as f:
                f.write(response.content)
            print("✓ TTS 测试成功，保存为 test_output.wav")
            return True
        else:
            print(f"✗ TTS 失败: {response.status_code}")
            print(response.text)
            return False
    except Exception as e:
        print(f"✗ 请求失败: {e}")
        return False

if __name__ == "__main__":
    print("=" * 50)
    print("Fish Speech API 测试")
    print("=" * 50)
    
    if not test_health():
        print("\n请先启动服务: bash start_service.sh")
        sys.exit(1)
    
    test_tts()
EOF

chmod +x test_api.py

# 创建 systemd 服务文件（可选）
cat > voice-tts.service << 'EOF'
[Unit]
Description=Voice TTS Service
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/voice-service/fish-speech
ExecStart=/bin/bash /root/voice-service/fish-speech/start_service.sh
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

echo -e "${GREEN}✓ 启动脚本创建完成${NC}"

# =============================================================================
# 部署完成
# =============================================================================
echo ""
echo "========================================"
echo -e "${GREEN}  部署完成!${NC}"
echo "========================================"
echo ""
echo "📁 工作目录: /root/voice-service/fish-speech"
echo ""
echo "🚀 启动服务:"
echo "   cd /root/voice-service/fish-speech"
echo "   bash start_service.sh"
echo ""
echo "🧪 测试服务:"
echo "   python test_api.py"
echo ""
echo "📖 使用说明:"
echo "   1. 启动服务后，在 AutoDL 控制台开放 7860 端口"
echo "   2. 获取对外访问地址"
echo "   3. 在后端代码中设置 AUTODL_BASE_URL"
echo ""
echo "⚠️  注意:"
echo "   - 首次启动需要加载模型，可能需要 1-2 分钟"
echo "   - 确保实例有 GPU (推荐 RTX 3090/4090)"
echo "   - 显存需求: 约 8-12GB"
echo ""
