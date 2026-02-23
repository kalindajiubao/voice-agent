# Voice Agent - 智能语音合成工作站

基于 Fish Speech + Kimi 的智能语音合成系统，支持音色克隆、情感控制、自然语言交互修改。

## 功能特性

- 🎙️ **文字转语音**：支持多种情感标签
- 🎭 **音色克隆**：上传 10-30 秒音频即时克隆
- 🤖 **智能分析**：自动分析文本推荐最佳情感
- 💬 **自然语言交互**：说"生气点""粗一点"即可调整

## 系统架构

```
用户前端 (React)
    ↓
FastAPI 后端 (main_complete.py)
    ├── 智能分析 → Kimi API
    ├── 情感理解 → Kimi API
    └── 语音合成 → AutoDL Fish Speech
```

## 快速开始

### 1. 配置环境变量

```bash
export KIMI_API_KEY="your-kimi-api-key"
export AUTODL_BASE_URL="https://your-autodl-instance:8443"
```

### 2. 启动后端

```bash
cd backend
pip install -r requirements.txt
python main_complete.py
```

### 3. 启动前端（可选）

```bash
cd frontend
npm install
npm run dev
```

## 核心 API

| 接口 | 功能 |
|------|------|
| `POST /synthesize/analyze` | 分析文本情感 |
| `POST /synthesize` | 合成语音 |
| `POST /synthesize/feedback` | 反馈调整 |

## 情感标签

`(happy)` `(angry)` `(sad)` `(excited)` `(serious)` `(soft)` `(shouting)` `(whispering)`

## 配置说明

| 变量 | 说明 | 必填 |
|------|------|------|
| `KIMI_API_KEY` | Kimi API 密钥 | 是 |
| `AUTODL_BASE_URL` | Fish Speech 服务地址 | 是 |

## License

MIT
