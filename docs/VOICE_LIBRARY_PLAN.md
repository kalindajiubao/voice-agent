# 预设音色库方案

## 目标
收集不同音色类型的参考音频（wav），让用户可以试听选择后再合成。

## 推荐数据源

### 1. LibriTTS 数据集（推荐）
- **特点**: 多说话人英语语料库，约585小时，24kHz采样率
- **说话人**: 1000+ 不同说话人，男女都有
- **下载**: https://www.openslr.org/60/
- **适用**: 英文音色克隆

### 2. AIShell-3 数据集（中文推荐）
- **特点**: 多说话人中文语料库
- **说话人**: 200+ 不同说话人
- **下载**: https://www.openslr.org/93/
- **适用**: 中文音色克隆

### 3. LJSpeech 数据集
- **特点**: 单一女性说话人，13,100条音频
- **说话人**: Linda Johnson（欧美女性）
- **下载**: https://keithito.com/LJ-Speech-Dataset
- **适用**: 基础测试

### 4. 魔搭社区 ModelScope
- **网址**: https://modelscope.cn/
- **特点**: 中文社区，有大量预训练音色
- **搜索关键词**: 语音合成、音色、TTS

## 音色分类建议

| 类别 | 子类别 | 数量 |
|------|--------|------|
| 中文女声 | 温柔、活泼、成熟、甜美 | 4-6个 |
| 中文男声 | 沉稳、年轻、磁性、阳光 | 4-6个 |
| 英文女声 | Warm, Professional, Friendly, Energetic | 4-6个 |
| 英文男声 | Deep, Clear, Friendly, Authoritative | 4-6个 |

## 实施步骤

1. **下载数据集样本**
   ```bash
   # 从 LibriTTS 选取不同说话人样本
   # 从 AIShell-3 选取中文样本
   ```

2. **音频预处理**
   - 裁剪为 5-10 秒片段
   - 统一转换为 16kHz 或 24kHz WAV
   - 标注音色类型

3. **上传到项目**
   ```
   voice-agent/
   └── assets/
       └── voices/
           ├── zh_female_gentle.wav
           ├── zh_female_lively.wav
           ├── zh_male_mature.wav
           ├── en_female_warm.wav
           └── ...
   ```

4. **更新后端配置**
   ```python
   DEFAULT_VOICES = {
       "zh_female_gentle": {
           "name": "温柔女声",
           "desc": "适合讲故事、客服",
           "reference_audio": "assets/voices/zh_female_gentle.wav",
           "default_params": {"speed": 1.0, "emotion_tag": "(soft)"}
       },
       # ... 更多音色
   }
   ```

## 快速获取样本的方法

### 方法1: 从 Hugging Face 下载
许多 TTS 项目提供示例音频：
- https://huggingface.co/spaces/fishaudio/fish-speech-1
- https://huggingface.co/spaces/coqui/xtts

### 方法2: 使用 Edge-TTS 生成
用 Edge-TTS 生成不同音色的样本作为参考：
```python
import edge_tts

voices = [
    "zh-CN-XiaoxiaoNeural",  # 中文女声
    "zh-CN-YunxiNeural",     # 中文男声
    "en-US-AriaNeural",      # 英文女声
    "en-US-GuyNeural",       # 英文男声
]
```

### 方法3: 录制自己的样本
录制 5-10 秒不同风格的语音作为参考。

## 前端交互设计

```
[预设音色] 按钮
    ↓
弹出音色选择面板
┌─────────────────────────────────┐
│  中文女声  中文男声  英文女声  英文男声  │
├─────────────────────────────────┤
│  ○ 温柔女声  [▶播放]            │
│  ○ 活泼女声  [▶播放]            │
│  ○ 成熟女声  [▶播放]            │
├─────────────────────────────────┤
│  [确认选择]                     │
└─────────────────────────────────┘
```

## 下一步

1. 我帮你下载并处理一些样本音频？
2. 或者先用 Edge-TTS 生成一批参考音频作为 MVP？
3. 还是直接集成第三方音色库 API？

需要我执行哪个方案？