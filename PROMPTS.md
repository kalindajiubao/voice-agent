# Voice Agent - 大模型提示词

## 提示词1：文本分析（analyze_text）

**用途**：分析用户输入的文本，确定最佳语音合成参数

**位置**：`backend/main_complete.py` - `LLMService.analyze_text()`

```
分析以下文本，确定最佳语音合成参数。

【Fish Speech 支持的情感标记】（必须从这些中选择，不要自己造词）
基础情感：
- (happy) 开心
- (angry) 生气  
- (sad) 悲伤
- (excited) 兴奋
- (surprised) 惊讶
- (satisfied) 满意
- (delighted) 高兴
- (scared) 害怕
- (worried) 担心
- (upset) 沮丧
- (nervous) 紧张
- (frustrated) 沮丧
- (depressed) 抑郁
- (empathetic) 共情
- (embarrassed) 尴尬
- (disgusted) 厌恶
- (moved) 感动
- (proud) 骄傲
- (relaxed) 放松
- (grateful) 感激
- (confident) 自信
- (interested) 感兴趣
- (curious) 好奇
- (confused) 困惑
- (joyful) 快乐

高级情感：
- (disdainful) 轻蔑
- (unhappy) 不开心
- (anxious) 焦虑
- (hysterical) 歇斯底里
- (indifferent) 冷漠
- (impatient) 不耐烦
- (guilty) 内疚
- (scornful) 轻蔑
- (panicked) 恐慌
- (furious) 愤怒
- (reluctant) 不情愿
- (keen) 渴望
- (disapproving) 不赞成
- (negative) 消极
- (denying) 否认
- (astonished) 震惊
- (serious) 严肃
- (sarcastic) 讽刺
- (conciliative) 安抚
- (comforting) 安慰
- (sincere) 真诚
- (sneering) 嘲笑
- (hesitating) 犹豫
- (yielding) 屈服
- (painful) 痛苦
- (awkward) 尴尬
- (amused) 逗乐

特殊效果：
- (laughing) 笑
- (chuckling) 轻笑
- (sobbing) 啜泣
- (crying loudly) 大哭
- (sighing) 叹息
- (panting) 喘气
- (groaning) 呻吟
- (crowd laughing) 人群笑声
- (background laughter) 背景笑声
- (audience laughing) 观众笑声

语调标记：
- (in a hurry tone) 匆忙语气
- (shouting) 喊叫
- (screaming) 尖叫
- (whispering) 耳语
- (soft tone) 柔和语气

【重要提示】
- 情感标记必须从上面的列表中精确选择，格式为 "(标签名)"
- 不要自己创造新的情感标签
- 如果不确定，使用 "(neutral)" 或留空

【语速调整】
- 1.0 = 正常语速
- > 1.0 = 加快（如 1.2）
- < 1.0 = 减慢（如 0.8）

文本："{text}"

请分析：
1. 场景/场合
2. 最适合的情感标记（必须从上面列表精确选择，格式为 "(标签名)"）
3. 推荐语速（1.0正常, >1加快, <1减慢）
4. 选择理由

输出JSON：
{
    "scene": "场景",
    "emotion": "情感标记（必须从列表中选择）",
    "speed": 1.0,
    "reason": "详细分析理由"
}
```

---

## 提示词2：反馈理解（understand_feedback）

**用途**：理解用户的反馈，确定参数调整方案

**位置**：`backend/main_complete.py` - `LLMService.understand_feedback()`

```
分析用户反馈，确定语音合成参数调整方案。

【当前参数】
- 语速(speed): {current_params.speed}
- 情感标签(emotion_tag): {current_params.emotion_tag}

【Fish Speech 支持的情感标记】（必须从这些中选择，不要自己造词）
基础情感：
- (happy) 开心
- (angry) 生气  
- (sad) 悲伤
- (excited) 兴奋
- (surprised) 惊讶
- (satisfied) 满意
- (delighted) 高兴
- (scared) 害怕
- (worried) 担心
- (upset) 沮丧
- (nervous) 紧张
- (frustrated) 沮丧
- (depressed) 抑郁
- (empathetic) 共情
- (embarrassed) 尴尬
- (disgusted) 厌恶
- (moved) 感动
- (proud) 骄傲
- (relaxed) 放松
- (grateful) 感激
- (confident) 自信
- (interested) 感兴趣
- (curious) 好奇
- (confused) 困惑
- (joyful) 快乐

高级情感：
- (disdainful) 轻蔑
- (unhappy) 不开心
- (anxious) 焦虑
- (hysterical) 歇斯底里
- (indifferent) 冷漠
- (impatient) 不耐烦
- (guilty) 内疚
- (scornful) 轻蔑
- (panicked) 恐慌
- (furious) 愤怒
- (reluctant) 不情愿
- (keen) 渴望
- (disapproving) 不赞成
- (negative) 消极
- (denying) 否认
- (astonished) 震惊
- (serious) 严肃
- (sarcastic) 讽刺
- (conciliative) 安抚
- (comforting) 安慰
- (sincere) 真诚
- (sneering) 嘲笑
- (hesitating) 犹豫
- (yielding) 屈服
- (painful) 痛苦
- (awkward) 尴尬
- (amused) 逗乐

特殊效果：
- (laughing) 笑
- (chuckling) 轻笑
- (sobbing) 啜泣
- (crying loudly) 大哭
- (sighing) 叹息
- (panting) 喘气
- (groaning) 呻吟
- (crowd laughing) 人群笑声
- (background laughter) 背景笑声
- (audience laughing) 观众笑声

语调标记：
- (in a hurry tone) 匆忙语气
- (shouting) 喊叫
- (screaming) 尖叫
- (whispering) 耳语
- (soft tone) 柔和语气

【可用调整工具】
1. adjust_emotion: 调整情感标签
   - 必须从上面的【Fish Speech 支持的情感标记】列表中选择
   - 格式为 "(标签名)"，如 "(happy)", "(serious)"
   - 不要自己创造新的情感标签
   
2. adjust_speed: 调整语速（音频后处理）
   - 范围: 0.5-2.0, 1.0为正常
   - 注意: 这是独立的后处理步骤，不是TTS参数

【重要提示】
- 情感标签必须从上面的列表中精确选择
- 不要自己造词，如果列表中没有合适的，选择最接近的
- 如果不确定，可以不调整情感标签

【用户反馈】
"{feedback}"

请分析：
1. 用户反馈的具体含义
2. 需要调用哪些调整工具
3. 每个工具的具体参数（情感标签必须从列表中选择）
4. 调整理由

输出JSON格式：
{
    "analysis": "详细分析过程...",
    "adjustments": {
        "speed": 1.0,
        "emotion_tag": ""
    },
    "function_calls": [
        {"function": "adjust_emotion", "params": {"tag": "(happy)"}, "reason": "..."},
        {"function": "adjust_speed", "params": {"speed": 0.9}, "reason": "..."}
    ],
    "tips": ["提示1", "提示2"]
}
```

---

## 情感标签分类统计

| 分类 | 数量 | 示例 |
|------|------|------|
| 基础情感 | 24个 | (happy), (angry), (sad) |
| 高级情感 | 26个 | (anxious), (furious), (serious) |
| 特殊效果 | 11个 | (laughing), (sobbing), (sighing) |
| 语调标记 | 5个 | (shouting), (whispering), (soft tone) |
| **总计** | **66个** | - |
