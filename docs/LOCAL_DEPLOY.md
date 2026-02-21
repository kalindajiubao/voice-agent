# 本地部署完整指南

## 环境要求

- Python 3.10+
- 能访问互联网
- 无需 GPU（TTS 服务在 AutoDL）

---

## 步骤

### 1. 克隆代码

```bash
git clone https://github.com/kalindajiubao/voice-agent.git
cd voice-agent/backend
```

### 2. 创建虚拟环境

```bash
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 创建环境变量文件

```bash
cat > .env << 'EOF'
AUTODL_BASE_URL=https://u894940-9373-577c3325.bjb1.seetacloud.com:8443
KIMI_API_KEY=sk-bIuttceNU7FJIPujOS6wo3fVel7DKJkWVhux2Gw72jOj9F0S
EOF
```

### 5. 启动后端服务

```bash
python main_complete.py
```

看到以下输出表示成功：
```
INFO:     Started server process [xxx]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### 6. 打开前端

```bash
# 方法1: 直接用浏览器打开文件
open ../frontend/index.html  # macOS
xdg-open ../frontend/index.html  # Linux
start ../frontend/index.html  # Windows

# 方法2: 用 Python 启动简单服务器
cd ../frontend
python -m http.server 3000
# 然后访问 http://localhost:3000
```

### 7. 测试

1. 浏览器打开前端页面
2. 选择「预设音色」模式
3. 输入文本：「你好，很高兴见到你」
4. 点击「智能分析」
5. 点击「开始合成」
6. 试听音频

---

## 常见问题

### Q: pip 安装慢
```bash
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### Q: 端口被占用
```bash
# 修改启动端口
export PORT=8001
python main_complete.py
```

### Q: 前端无法连接后端
检查：
1. 后端是否运行（`curl http://localhost:8000`）
2. 前端代码里的 API 地址是否正确

### Q: HTTPS 证书错误
已配置 `verify=False`，如仍报错，更新代码：
```bash
git pull
```

---

## 目录结构

```
voice-agent/
├── backend/
│   ├── main_complete.py      # 主程序
│   ├── requirements.txt      # 依赖
│   ├── .env                  # 环境变量（自己创建）
│   └── venv/                 # 虚拟环境
├── frontend/
│   └── index.html            # 前端页面
└── docs/
    └── LOCAL_DEPLOY.md       # 本文件
```

---

## 启动命令总结

```bash
cd voice-agent/backend
source venv/bin/activate
python main_complete.py
```

然后打开 `frontend/index.html` 即可使用。
