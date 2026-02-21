# Voice Agent - 智能语音合成工作站

基于 Fish Speech + Kimi 的智能语音合成系统，支持音色克隆、情感控制、自然语言交互修改。

## 功能特性

- 🎙️ **文字转语音**：支持多种情感标签
- 🎭 **音色克隆**：上传 10-30 秒音频即时克隆
- 🤖 **智能分析**：自动分析文本推荐最佳情感
- 💬 **自然语言交互**：说"生气点""粗一点"即可调整
- 🌐 **Web 界面**：简洁直观的前端操作

## 系统架构

```
用户前端 (React)
    ↓
FastAPI 后端
    ├── 智能分析 → Kimi API
    ├── 情感理解 → Kimi API
    └── 语音合成 → AutoDL Fish Speech
```

## 部署指南

### 1. AutoDL 部署 Fish Speech

1. 访问 [AutoDL](https://www.autodl.com) 注册账号
2. 创建实例：
   - GPU: RTX 3090 (24G)
   - 镜像：选择 "Fish Speech" 或 "PyTorch"
3. 复制实例的 SSH 登录信息
4. 在实例中运行部署脚本：

```bash
# 上传 setup_autodl.sh 到实例
bash setup_autodl.sh

# 启动服务
bash start_api.sh
```

5. 记录实例的公网 IP 和端口（如 `http://123.45.67.89:7860`）

### 2. 部署后端服务

```bash
cd backend

# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
export KIMI_API_KEY="your-kimi-api-key"
export AUTODL_BASE_URL="http://your-autodl-ip:7860"

# 启动服务
python main.py
```

### 3. 部署前端

```bash
cd frontend
npm install
npm run dev
```

## API 接口

### 分析文本情感
```bash
POST /analyze
Content-Type: application/x-www-form-urlencoded

text=恭喜您中奖了！
```

响应：
```json
{
  "scene": "喜庆",
  "emotion": "happy",
  "style": "活泼",
  "suggested_tag": "(happy)",
  "reason": "中奖是喜庆场景，适合用开心语气"
}
```

### 文字转语音
```bash
POST /tts
Content-Type: multipart/form-data

text=你好，这是一个测试
reference_audio: [文件]
auto_emotion: true
```

### 修改语音
```bash
POST /modify
text=你好
user_request=要生气点，声音粗一点
reference_audio: [文件]
```

## 情感标签

| 标签 | 效果 |
|------|------|
| `(happy)` | 开心 |
| `(angry)` | 生气 |
| `(sad)` | 悲伤 |
| `(excited)` | 兴奋 |
| `(serious)` | 严肃 |
| `(soft)` | 温柔 |
| `(shouting)` | 大喊 |
| `(whispering)` | 耳语 |

## 配置说明

### 环境变量

| 变量 | 说明 | 必填 |
|------|------|------|
| `KIMI_API_KEY` | Kimi API 密钥 | 是 |
| `AUTODL_BASE_URL` | AutoDL Fish Speech 地址 | 是 |
| `PORT` | 后端端口 | 否，默认 8000 |

### 获取 Kimi API Key

1. 访问 [Kimi 开放平台](https://platform.moonshot.cn/)
2. 注册账号
3. 创建 API Key

## 费用估算

| 项目 | 费用 |
|------|------|
| AutoDL RTX 3090 | ￥1.2-1.8/小时 |
| Kimi API | 按 token 计费，约￥0.015/千字符 |

## 目录结构

```
voice-agent/
├── backend/          # FastAPI 后端
│   ├── main.py
│   └── requirements.txt
├── frontend/         # React 前端
│   └── src/
├── docs/             # 文档
│   └── setup_autodl.sh
└── README.md
```

## 开发计划

- [x] 后端 API 开发
- [ ] 前端界面开发
- [ ] 音色库管理
- [ ] 批量合成功能
- [ ] 历史记录

## License

MIT
