#!/bin/bash
# 测试 AutoDL Fish Speech 服务

URL="https://u894940-9373-577c3325.bjb1.seetacloud.com:8443"

echo "========================================"
echo "  测试 Fish Speech 服务"
echo "  URL: $URL"
echo "========================================"
echo ""

# 测试1: 健康检查
echo "[测试1] 健康检查..."
curl -k -s $URL > /dev/null
if [ $? -eq 0 ]; then
    echo "✓ 服务可连接"
else
    echo "✗ 连接失败"
    exit 1
fi

# 测试2: TTS 合成
echo ""
echo "[测试2] TTS 合成..."
curl -k -s -X POST "$URL/v1/tts" \
    -H "Content-Type: application/json" \
    -d '{"text": "你好，这是测试", "reference_id": "default"}' \
    --output test_output.wav

if [ -f "test_output.wav" ] && [ -s "test_output.wav" ]; then
    echo "✓ 合成成功，文件大小: $(ls -lh test_output.wav | awk '{print $5}')"
    echo "  文件: test_output.wav"
else
    echo "✗ 合成失败"
fi

# 测试3: 带情感标签
echo ""
echo "[测试3] 情感合成..."
curl -k -s -X POST "$URL/v1/tts" \
    -H "Content-Type: application/json" \
    -d '{"text": "(happy) 很高兴见到你", "reference_id": "default"}' \
    --output test_happy.wav

if [ -f "test_happy.wav" ] && [ -s "test_happy.wav" ]; then
    echo "✓ 情感合成成功，文件大小: $(ls -lh test_happy.wav | awk '{print $5}')"
else
    echo "✗ 情感合成失败"
fi

echo ""
echo "========================================"
echo "  测试完成"
echo "========================================"
