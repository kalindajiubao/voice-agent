from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from typing import Optional, Literal, Dict, Any, List
import httpx
import os
import json
import tempfile
import re
import glob
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()

app = FastAPI(title="Voice Agent - Complete", version="5.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 配置
AUTODL_BASE_URL = os.getenv("AUTODL_BASE_URL", "https://u894940-9373-577c3325.bjb1.seetacloud.com:8443")
KIMI_API_KEY = os.getenv("KIMI_API_KEY", "")
KIMI_BASE_URL = "https://api.moonshot.cn/v1"

# HTTP 客户端配置（不创建全局实例，每次请求新建）
HTTP_TIMEOUT = 60.0
HTTP_VERIFY = False

def create_http_client():
    """创建新的 HTTP 客户端"""
    return httpx.AsyncClient(verify=HTTP_VERIFY, timeout=HTTP_TIMEOUT)

# ==================== 音频处理 ====================

class AudioProcessor:
    """音频后处理 - 调整语速、音调"""
    
    @staticmethod
    def adjust_speed(audio_bytes: bytes, speed: float) -> bytes:
        """
        调整音频语速
        speed: 1.0=正常, >1=加快, <1=减慢
        """
        try:
            from pydub import AudioSegment
            import io
            
            # 检查 ffmpeg 是否可用
            import subprocess
            try:
                result = subprocess.run(['ffmpeg', '-version'], capture_output=True, timeout=5)
                if result.returncode != 0:
                    print(f"[AudioProcessor] 警告: ffmpeg 返回错误码 {result.returncode}")
                    print(f"[AudioProcessor] stderr: {result.stderr.decode()[:200]}")
                    return audio_bytes
                print(f"[AudioProcessor] ffmpeg 检测成功: {result.stdout.decode()[:100]}...")
            except FileNotFoundError:
                print("[AudioProcessor] 警告: ffmpeg 未找到，语速调整功能不可用")
                print("[AudioProcessor] 请安装 ffmpeg: Mac(brew install ffmpeg) / Linux(sudo apt-get install ffmpeg)")
                return audio_bytes
            except Exception as e:
                print(f"[AudioProcessor] ffmpeg 检测失败: {e}")
                return audio_bytes
            
            # 加载音频
            audio = AudioSegment.from_wav(io.BytesIO(audio_bytes))
            original_duration = len(audio) / 1000.0  # 转换为秒
            print(f"[AudioProcessor] 原始音频时长: {original_duration:.2f}s, 帧率: {audio.frame_rate}")
            
            # 调整语速（改变帧率）
            if speed != 1.0:
                # 改变播放速度（同时保持音调）
                new_frame_rate = int(audio.frame_rate * speed)
                print(f"[AudioProcessor] 调整帧率: {audio.frame_rate} -> {new_frame_rate}")
                audio = audio._spawn(audio.raw_data, overrides={'frame_rate': new_frame_rate})
                # 转换回标准帧率
                audio = audio.set_frame_rate(24000)
                new_duration = len(audio) / 1000.0
                print(f"[AudioProcessor] 调整后音频时长: {new_duration:.2f}s")
            
            # 导出
            output = io.BytesIO()
            audio.export(output, format="wav")
            return output.getvalue()
            
        except ImportError:
            print("[AudioProcessor] 警告: 未安装 pydub，跳过语速调整")
            print("[AudioProcessor] 请安装: pip install pydub")
            return audio_bytes
        except Exception as e:
            print(f"[AudioProcessor] 语速调整失败: {e}")
            import traceback
            traceback.print_exc()
            return audio_bytes


# ==================== 预设音色加载 ====================
# 音色配置文件路径
VOICE_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "assets", "voices", "voice_config.json")

def load_voices():
    """从 voice_config.json 加载音色配置"""
    try:
        with open(VOICE_CONFIG_PATH, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        voices = {}
        for voice_id, voice_data in config.items():
            voices[voice_id] = {
                "name": voice_data.get("name", voice_id),
                "desc": voice_data.get("desc", ""),
                "reference_audio": f"assets/voices/{voice_id}.wav",
                "sample_audio": voice_data.get("sample_audio"),  # 示例音频
                "default_params": {
                    "speed": 1.0,
                    "emotion_tag": voice_data.get("emotion_tag", "")
                },
                "voice": voice_data.get("voice", "")
            }
        return voices
    except Exception as e:
        print(f"警告: 无法加载 voice_config.json: {e}，使用默认配置")
        # 兜底默认配置
        return {
            "zh_female_gentle": {
                "name": "温柔女声",
                "desc": "适合讲故事、客服场景",
                "reference_audio": "assets/voices/zh_female_gentle.wav",
                "default_params": {"speed": 1.0, "emotion_tag": ""}
            },
            "zh_female_lively": {
                "name": "活泼女声",
                "desc": "适合短视频、广告",
                "reference_audio": "assets/voices/zh_female_lively.wav",
                "default_params": {"speed": 1.0, "emotion_tag": ""}
            },
            "zh_male_calm": {
                "name": "沉稳男声",
                "desc": "适合商务、正式场合",
                "reference_audio": "assets/voices/zh_male_calm.wav",
                "default_params": {"speed": 1.0, "emotion_tag": ""}
            },
            "zh_male_young": {
                "name": "年轻男声",
                "desc": "适合游戏、动漫",
                "reference_audio": "assets/voices/zh_male_young.wav",
                "default_params": {"speed": 1.0, "emotion_tag": ""}
            },
        }

# 加载音色配置
DEFAULT_VOICES = load_voices()


# ==================== 大模型服务 ====================

class LLMService:
    """大模型服务 - 智能分析和反馈理解"""
    
    @staticmethod
    async def analyze_text(text: str) -> Dict[str, Any]:
        """阶段1: 分析文本确定合成参数"""
        
        if not KIMI_API_KEY:
            return {
                "scene": "通用对话",
                "emotion": "neutral",
                "emotion_tag": "",
                "pitch": 0,
                "speed": 1.0,
                "volume": 1.0,
                "style": "自然",
                "reason": "未配置Kimi API，使用默认参数"
            }
        
        prompt = f"""分析以下文本，确定最佳语音合成参数。

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
{{
    "scene": "场景",
    "emotion": "情感标记，如<|happy|>、<|angry|>、<|sad|>、<|excited|>、<|calm|>、<|surprised|>",
    "speed": 1.0,
    "reason": "详细分析理由"
}}"""

        async with create_http_client() as client:
            response = await client.post(
                f"{KIMI_BASE_URL}/chat/completions",
                headers={"Authorization": f"Bearer {KIMI_API_KEY}"},
                json={
                    "model": "moonshot-v1-8k",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3
                },
                timeout=30.0
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result["choices"][0]["message"]["content"]
                
                try:
                    if "```json" in content:
                        content = content.split("```json")[1].split("```")[0]
                    elif "```" in content:
                        content = content.split("```")[1].split("```")[0]
                    return json.loads(content.strip())
                except:
                    pass
        
        # 默认返回
        return {
            "scene": "通用",
            "emotion": "neutral",
            "emotion_tag": "",
            "pitch": 0,
            "speed": 1.0,
            "volume": 1.0,
            "style": "自然",
            "reason": "使用默认参数"
        }
    
    @staticmethod
    async def understand_feedback(feedback: str, current_params: Dict, audio_count: int) -> Dict[str, Any]:
        """
        阶段2: 理解用户反馈，使用大模型分析并返回调整方案
        
        返回包含:
        - analysis: 大模型分析过程
        - adjustments: 参数调整
        - function_calls: 需要调用的功能列表
        """
        
        # 运行时动态读取环境变量
        kimi_api_key = os.getenv("KIMI_API_KEY", "")
        
        if not kimi_api_key:
            # 备用：规则匹配
            return LLMService._rule_based_feedback(feedback, current_params, audio_count)
        
        prompt = f"""分析用户反馈，确定语音合成参数调整方案。

【当前参数】
- 语速(speed): {current_params.get('speed', 1.0)}
- 情感标签(emotion_tag): {current_params.get('emotion_tag', '无')}

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
{{
    "analysis": "详细分析过程...",
    "adjustments": {{
        "speed": 1.0,
        "emotion_tag": "情感标记，如<|happy|>、<|angry|>、<|sad|>、<|excited|>、<|calm|>、<|surprised|>"
    }},
    "function_calls": [
        {{"function": "adjust_emotion", "params": {{"tag": "<|happy|>"}}, "reason": "..."}},
        {{"function": "adjust_speed", "params": {{"speed": 0.9}}, "reason": "..."}}
    ],
    "tips": ["提示1", "提示2"]
}}"""

        # 使用运行时读取的 kimi_api_key
        async with create_http_client() as client:
            response = await client.post(
                f"{KIMI_BASE_URL}/chat/completions",
                headers={"Authorization": f"Bearer {kimi_api_key}"},
                json={
                    "model": "moonshot-v1-8k",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3
                },
                timeout=30.0
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result["choices"][0]["message"]["content"]
                
                try:
                    if "```json" in content:
                        content = content.split("```json")[1].split("```")[0]
                    elif "```" in content:
                        content = content.split("```")[1].split("```")[0]
                    parsed = json.loads(content.strip())
                    return parsed
                except Exception as e:
                    print(f"解析失败: {e}, 内容: {content}")
        
        # 失败时回退到规则匹配
        return LLMService._rule_based_feedback(feedback, current_params, audio_count)
    
    @staticmethod
    def _rule_based_feedback(feedback: str, current_params: Dict, audio_count: int) -> Dict[str, Any]:
        """基于规则的反馈处理（备用）"""
        fb = feedback.lower()
        adjustments = {}
        function_calls = []
        
        # 语速调整 - 独立的 Function Call
        if any(w in fb for w in ["快", "急", "赶"]):
            new_speed = max(0.5, current_params.get("speed", 1.0) - 0.2)
            adjustments["speed"] = new_speed
            function_calls.append({
                "function": "adjust_speed",
                "params": {"speed": new_speed},
                "reason": "用户反馈语速太快，需要减慢"
            })
        elif any(w in fb for w in ["慢", "缓", "拖"]):
            new_speed = min(2.0, current_params.get("speed", 1.0) + 0.2)
            adjustments["speed"] = new_speed
            function_calls.append({
                "function": "adjust_speed",
                "params": {"speed": new_speed},
                "reason": "用户反馈语速太慢，需要加快"
            })
        
        # 情感调整（去掉音调调整）
        emotion = ""
        if any(w in fb for w in ["开心", "高兴", "活泼"]):
            emotion = "<|happy|>"
        elif any(w in fb for w in ["生气", "愤怒", "严肃"]):
            emotion = "<|angry|>"
        elif any(w in fb for w in ["温柔", "柔和", "软"]):
            emotion = "<|calm|>"
        elif any(w in fb for w in ["悲伤", "难过"]):
            emotion = "<|sad|>"
        elif any(w in fb for w in ["兴奋", "激动"]):
            emotion = "<|excited|>"
        elif any(w in fb for w in ["惊讶", "震惊"]):
            emotion = "<|surprised|>"
        
        if emotion:
            adjustments["emotion_tag"] = emotion
            function_calls.append({
                "function": "adjust_emotion",
                "params": {"tag": emotion},
                "reason": f"根据反馈调整情感为{emotion}"
            })
        
        # 是否需要更多音频
        need_more_audio = audio_count < 2 and any(kw in fb for kw in ["不像", "不像我", "不像本人", "差距", "差很远"])
        
        tips = []
        if need_more_audio:
            tips.append(f"💡 当前仅使用 {audio_count} 段音频克隆，效果可能不够稳定")
            tips.append("💡 建议：再上传 1-2 段不同语调/情感的音频进行融合，可显著提升相似度")
        
        if adjustments:
            tips.append(f"✅ 已根据反馈调整参数")
        
        return {
            "analysis": f"基于规则分析: 识别到关键词 '{fb}'，触发 {len(function_calls)} 个调整",
            "adjustments": adjustments,
            "function_calls": function_calls,
            "need_more_audio": need_more_audio,
            "current_audio_count": audio_count,
            "tips": tips,
            "action": "参数调整" if adjustments else "提示优化"
        }


# ==================== 语音合成服务 ====================

class FishSpeechService:
    """Fish Speech 服务 - 统一后端支持克隆和普通模式"""
    
    @staticmethod
    async def synthesize(
        text: str,
        reference_audio: Optional[bytes] = None,
        reference_id: Optional[str] = None,
        params: Optional[Dict] = None
    ) -> bytes:
        """
        合成语音
        - 有 reference_audio: 克隆模式
        - 有 reference_id: 预设音色模式
        - 都无: 默认音色
        """
        
        # 应用参数（通过文本标签）
        final_text = text
        emotion_tag = ""
        if params:
            if params.get("emotion_tag"):
                emotion_tag = params['emotion_tag']
                # 直接使用 <|emotion|> 格式，不需要转换
                final_text = emotion_tag + " " + final_text
        
        # 过滤旧格式的情感标记 (emotion) 和 <|emotion|> 格式（避免重复）
        final_text = re.sub(r'\(happy\)|\(angry\)|\(sad\)|\(excited\)|\(serious\)|\(soft\)|\(whispering\)|\(shouting\)', '', final_text)
        final_text = re.sub(r'\(disdainful\)|\(unhappy\)|\(anxious\)|\(hysterical\)|\(indifferent\)|\(impatient\)|\(guilty\)|\(scornful\)|\(panicked\)|\(furious\)|\(reluctant\)|\(keen\)|\(disapproving\)|\(negative\)|\(denying\)|\(astonished\)|\(sarcastic\)|\(conciliative\)|\(comforting\)|\(sincere\)|\(sneering\)|\(hesitating\)|\(yielding\)|\(painful\)|\(awkward\)|\(amused\)', '', final_text)
        final_text = re.sub(r'\(laughing\)|\(chuckling\)|\(sobbing\)|\(crying loudly\)|\(sighing\)|\(panting\)|\(groaning\)|\(crowd laughing\)|\(background laughter\)|\(audience laughing\)', '', final_text)
        final_text = re.sub(r'\(in a hurry tone\)|\(screaming\)|\(soft tone\)', '', final_text)
        # 清理多余空格
        final_text = re.sub(r'\s+', ' ', final_text).strip()
        
        # 创建临时客户端
        client = httpx.AsyncClient(verify=False, timeout=60.0)
        
        try:
            if reference_audio:
                # 克隆模式 - 使用上传的音频
                # 转为 base64，使用 references 参数
                import base64
                audio_base64 = base64.b64encode(reference_audio).decode('utf-8')
                
                # 获取情感标签，用于参考音频的 text 字段
                # 注意：情感标签已经通过 final_text 传递，这里不需要重复
                emotion_text = ""
                
                data = {
                    "text": final_text,
                    "temperature": 0.7,
                    "references": [
                        {
                            "audio": audio_base64,
                            "text": ""  # 参考音频的文本描述，不需要情感标签
                        }
                    ]
                }
                
                response = await client.post(
                    f"{AUTODL_BASE_URL}/v1/tts",
                    json=data,
                    timeout=60.0
                )
            elif reference_id:
                # 普通模式 - 使用预设音色（reference_id）
                # 获取音色对应的参考音频路径
                voices = load_voices()
                voice_config = voices.get(reference_id, {})
                ref_audio_path = voice_config.get("reference_audio")
                
                if ref_audio_path:
                    # 尝试多个可能的路径
                    possible_paths = [
                        ref_audio_path,  # 相对路径
                        os.path.join(os.path.dirname(__file__), "..", ref_audio_path),  # 从backend目录
                        os.path.join(os.path.dirname(__file__), ref_audio_path),  # 直接相对backend
                        f"../{ref_audio_path}",  # 上级目录
                    ]
                    
                    ref_audio_full_path = None
                    for path in possible_paths:
                        if os.path.exists(path):
                            ref_audio_full_path = path
                            break
                    
                    if ref_audio_full_path:
                        print(f"[音色合成] 使用预设音色: {reference_id}, 音频: {ref_audio_full_path}")
                        # 读取参考音频文件
                        with open(ref_audio_full_path, "rb") as f:
                            ref_audio_bytes = f.read()
                        # 转为 base64，使用 references 参数
                        import base64
                        audio_base64 = base64.b64encode(ref_audio_bytes).decode('utf-8')
                        
                        # 获取情感标签
                        # 注意：情感标签已经通过 final_text 传递，这里不需要重复
                        emotion_text = ""
                        
                        data = {
                            "text": final_text,
                            "temperature": 0.7,
                            "references": [
                                {
                                    "audio": audio_base64,
                                    "text": ""  # 参考音频的文本描述，不需要情感标签
                                }
                            ]
                        }
                        response = await client.post(
                            f"{AUTODL_BASE_URL}/v1/tts",
                            json=data,
                            timeout=60.0
                        )
                    else:
                        print(f"[音色合成] 未找到参考音频: {ref_audio_path}，尝试路径: {possible_paths}")
                        #  fallback 到纯文本
                        data = {"text": final_text, "temperature": 0.7}
                        response = await client.post(
                            f"{AUTODL_BASE_URL}/v1/tts",
                            json=data,
                            timeout=60.0
                        )
                else:
                    # 没有参考音频配置
                    data = {"text": final_text, "temperature": 0.7}
                    response = await client.post(
                        f"{AUTODL_BASE_URL}/v1/tts",
                        json=data,
                        timeout=60.0
                    )
            else:
                # 默认模式 - 不传参考音频
                data = {
                    "text": final_text,
                    "temperature": 0.7
                }
                
                response = await client.post(
                    f"{AUTODL_BASE_URL}/v1/tts",
                    json=data,
                    timeout=60.0
                )
            
            if response.status_code == 200:
                audio_data = response.content
                
                # 统一后处理：调整语速
                print(f"[FishSpeechService] 收到音频: {len(audio_data)} bytes")
                print(f"[FishSpeechService] params: {params}")
                
                if params:
                    speed = params.get("speed", 1.0)
                    print(f"[FishSpeechService] speed 值: {speed}, 类型: {type(speed)}")
                    
                    if speed != 1.0:
                        print(f"[FishSpeechService] 开始调整语速: {speed}x")
                        audio_data = AudioProcessor.adjust_speed(audio_data, speed)
                        print(f"[FishSpeechService] 语速调整完成")
                    else:
                        print(f"[FishSpeechService] speed=1.0, 跳过语速调整")
                else:
                    print(f"[FishSpeechService] params 为空，跳过语速调整")
                
                return audio_data
            
            # 详细错误信息
            error_detail = f"HTTP {response.status_code}: {response.text}"
            print(f"[TTS 错误] {error_detail}")
            print(f"[TTS 请求] 模式: {'克隆' if reference_audio else ('预设' if reference_id else '默认')}")
            raise Exception(f"合成失败: {error_detail}")
        finally:
            await client.aclose()


# ==================== 会话管理 ====================

class SynthesisSession:
    """合成会话"""
    
    def __init__(self):
        self.session_id = ""
        self.mode = "default"  # clone 或 default
        self.text = ""
        self.voice_id = "xiaoxiao"
        self.reference_audios: List[bytes] = []  # 支持多段音频
        self.analysis = {}
        self.current_params = {
            "speed": 1.0,
            "emotion_tag": ""
        }
        self.version = 0
        self.history = []


sessions: Dict[str, SynthesisSession] = {}


# ==================== API 路由 ====================

@app.get("/")
async def root():
    return {
        "message": "Voice Agent - Complete",
        "version": "5.0.0",
        "backend": "Fish Speech (统一后端)",
        "modes": ["clone", "default"],
        "features": ["情感合成", "多音频融合", "交互优化"]
    }


@app.get("/voices")
async def list_voices():
    """获取预设音色列表"""
    return {
        "voices": [
            {
                "id": k,
                "name": v["name"],
                "description": v["desc"],
                "default_params": v["default_params"],
                "preview_url": f"/voices/{k}/preview"
            }
            for k, v in DEFAULT_VOICES.items()
        ]
    }


@app.get("/voices/{voice_id}/preview")
async def get_voice_preview(voice_id: str):
    """获取预设音色的参考音频（用于试听）"""
    if voice_id not in DEFAULT_VOICES:
        return JSONResponse(status_code=404, content={"error": "音色不存在"})
    
    voice = DEFAULT_VOICES[voice_id]
    audio_path = voice.get("reference_audio")
    
    if not audio_path:
        return JSONResponse(status_code=404, content={"error": "该音色没有参考音频"})
    
    # 支持相对路径和绝对路径
    full_path = os.path.join(os.path.dirname(__file__), "..", audio_path)
    if not os.path.exists(full_path):
        return JSONResponse(status_code=404, content={"error": "音频文件不存在"})
    
    return FileResponse(full_path, media_type="audio/wav")


# ==================== 阶段1: 智能分析 ====================

@app.post("/synthesize/analyze")
async def analyze_text(
    mode: Literal["clone", "default"] = Form(...),
    text: str = Form(...),
    voice_id: Optional[str] = Form(None)
):
    """
    阶段1: 分析文本，推荐合成参数
    
    - 大模型分析文本场景、情感
    - 返回推荐的语速、音调、音量、情感标签
    """
    
    if not text:
        return JSONResponse(status_code=400, content={"error": "文本不能为空"})
    
    # 智能分析
    analysis = await LLMService.analyze_text(text)
    
    # 创建会话
    session_id = f"sess_{len(sessions)}_{os.urandom(4).hex()}"
    session = SynthesisSession()
    session.session_id = session_id
    session.mode = mode
    session.text = text
    session.voice_id = voice_id or "xiaoxiao"
    session.analysis = analysis
    
    # 提取情感标签（从 emotion 字段转换）
    emotion_value = analysis.get("emotion", "")
    # 如果 emotion 包含括号，提取标签名并转换为 <|emotion|> 格式
    emotion_map = {
        "(happy)": "<|happy|>",
        "(angry)": "<|angry|>",
        "(sad)": "<|sad|>",
        "(excited)": "<|excited|>",
        "(surprised)": "<|surprised|>",
        "(calm)": "<|calm|>"
    }
    emotion_tag = ""
    if emotion_value and "(" in emotion_value:
        # 可能是 "(happy) 开心" 或 "(happy)" 格式
        extracted = emotion_value.split(")")[0] + ")"
        emotion_tag = emotion_map.get(extracted, "")
    elif emotion_value and emotion_value.startswith("<"):
        # 已经是 <|emotion|> 格式
        emotion_tag = emotion_value
    
    session.current_params = {
        "speed": analysis.get("speed", 1.0),
        "pitch": analysis.get("pitch", 0),
        "volume": analysis.get("volume", 1.0),
        "emotion_tag": emotion_tag
    }
    
    sessions[session_id] = session
    
    return {
        "session_id": session_id,
        "phase": "analysis",
        "mode": mode,
        "text": text,
        "analysis": analysis,
        "suggested_params": session.current_params,
        "message": "分析完成，请确认参数或调整后合成"
    }


# ==================== 阶段2: 首次合成 ====================

@app.post("/synthesize")
async def synthesize(
    session_id: str = Form(...),
    speed: Optional[float] = Form(None),
    pitch: Optional[int] = Form(None),
    volume: Optional[float] = Form(None),
    emotion_tag: Optional[str] = Form(None),
    reference_audio: Optional[UploadFile] = File(None)
):
    """
    阶段2: 合成语音
    
    - 应用用户调整的参数
    - 支持上传参考音频（克隆模式）
    - 返回合成结果和优化建议
    """
    
    if session_id not in sessions:
        return JSONResponse(status_code=404, content={"error": "会话不存在"})
    
    session = sessions[session_id]
    
    # 应用用户调整
    if speed is not None:
        session.current_params["speed"] = speed
    if pitch is not None:
        session.current_params["pitch"] = pitch
    if volume is not None:
        session.current_params["volume"] = volume
    if emotion_tag is not None:
        session.current_params["emotion_tag"] = emotion_tag
    
    # 保存新上传的参考音频
    if reference_audio:
        audio_bytes = await reference_audio.read()
        session.reference_audios.append(audio_bytes)
    
    # 检查是否有参考音频
    if session.mode == "clone" and len(session.reference_audios) == 0:
        return JSONResponse(
            status_code=400,
            content={"error": "克隆模式需要上传参考音频", "code": "MISSING_AUDIO"}
        )
    
    try:
        # 执行合成
        if session.mode == "clone":
            # 克隆模式 - 使用用户上传的音频（取第一段或融合）
            ref_audio = session.reference_audios[0] if session.reference_audios else None
            audio_data = await FishSpeechService.synthesize(
                text=session.text,
                reference_audio=ref_audio,
                params=session.current_params
            )
        else:
            # 普通模式 - 使用预设音色
            audio_data = await FishSpeechService.synthesize(
                text=session.text,
                reference_id=session.voice_id,  # 传递音色ID
                params=session.current_params
            )
        
        # 保存音频到固定目录（语速调整已在 FishSpeechService 中完成）
        os.makedirs("outputs", exist_ok=True)
        audio_filename = f"outputs/{session_id}_{session.version}.wav"
        with open(audio_filename, "wb") as f:
            f.write(audio_data)
        
        session.version += 1
        
        # 构建提示
        tips = []
        if session.mode == "clone":
            tips.append(f"📎 当前使用 {len(session.reference_audios)} 段参考音频")
            if len(session.reference_audios) < 2:
                tips.append("💡 提示：上传更多音频可提升克隆相似度")
        
        return {
            "session_id": session_id,
            "phase": "synthesized",
            "version": session.version,
            "mode": session.mode,
            "audio_url": f"/audio/{os.path.basename(audio_filename)}",
            "params": session.current_params,
            "audio_count": len(session.reference_audios),
            "tips": tips,
            "message": f"第{session.version}版合成完成"
        }
    
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"[合成错误] {str(e)}")
        print(f"[错误详情] {error_trace}")
        return JSONResponse(status_code=500, content={"error": str(e), "detail": error_trace})


# ==================== 阶段3: 交互优化 ====================

@app.post("/synthesize/feedback/analyze")
async def feedback_analyze(
    session_id: str = Form(...),
    feedback: str = Form(...)
):
    """
    阶段3-1: 分析反馈，返回调整建议（不合成）
    
    用户确认后再调用 /synthesize/feedback/apply 执行合成
    """
    
    if session_id not in sessions:
        return JSONResponse(status_code=404, content={"error": "会话不存在"})
    
    session = sessions[session_id]
    
    # 理解反馈（大模型分析）
    result = await LLMService.understand_feedback(
        feedback,
        session.current_params,
        len(session.reference_audios)
    )
    
    # 计算调整后的参数（但不应用到 session）
    adjustments = result.get("adjustments", {})
    proposed_params = {**session.current_params}
    for key, value in adjustments.items():
        if value is not None:
            proposed_params[key] = value
    
    return {
        "session_id": session_id,
        "phase": "feedback_analyzed",
        "feedback": feedback,
        "analysis": result.get("analysis", ""),  # 大模型理解
        "adjustments": adjustments,  # 具体调整
        "current_params": session.current_params,  # 当前参数
        "proposed_params": proposed_params,  # 建议参数
        "tips": result.get("tips", []),
        "need_more_audio": result.get("need_more_audio", False),
        "message": "请确认参数调整"
    }


@app.post("/synthesize/feedback/apply")
async def feedback_apply(
    session_id: str = Form(...),
    apply_adjustments: bool = Form(True),
    params: Optional[str] = Form(None),  # JSON 字符串，包含调整后的参数
    additional_audio: Optional[UploadFile] = File(None)
):
    """
    阶段3-2: 应用反馈调整并合成
    
    用户确认后调用此接口执行实际合成
    """
    
    if session_id not in sessions:
        return JSONResponse(status_code=404, content={"error": "会话不存在"})
    
    session = sessions[session_id]
    
    # 保存额外上传的音频
    if additional_audio:
        audio_bytes = await additional_audio.read()
        session.reference_audios.append(audio_bytes)
    
    # 应用用户确认后的参数
    if apply_adjustments and params:
        try:
            import json
            new_params = json.loads(params)
            print(f"[feedback_apply] 应用调整后的参数: {new_params}")
            session.current_params.update(new_params)
        except Exception as e:
            print(f"[feedback_apply] 解析参数失败: {e}")
    
    try:
        # 执行合成 (feedback_apply)
        if session.mode == "clone":
            ref_audio = session.reference_audios[0] if session.reference_audios else None
            audio_data = await FishSpeechService.synthesize(
                text=session.text,
                reference_audio=ref_audio,
                params=session.current_params
            )
        else:
            # 普通模式 - 使用预设音色
            audio_data = await FishSpeechService.synthesize(
                text=session.text,
                reference_id=session.voice_id,  # 传递音色ID
                params=session.current_params
            )
        
        # 保存音频（语速调整已在 FishSpeechService 中完成）
        os.makedirs("outputs", exist_ok=True)
        session.version += 1
        audio_filename = f"outputs/{session_id}_{session.version}.wav"
        with open(audio_filename, "wb") as f:
            f.write(audio_data)
        
        # 获取最后一次反馈记录
        last_feedback = session.history[-1]["feedback"] if session.history else ""
        last_adjustments = session.history[-1]["adjustments"] if session.history else {}
        
        return {
            "session_id": session_id,
            "phase": "synthesized",
            "version": session.version,
            "mode": session.mode,
            "current_params": session.current_params,
            "audio_url": f"/audio/{os.path.basename(audio_filename)}",
            "audio_count": len(session.reference_audios),
            "message": f"第{session.version}版合成完成"
        }
    
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.post("/synthesize/feedback")
async def feedback(
    session_id: str = Form(...),
    feedback: str = Form(...),
    additional_audio: Optional[UploadFile] = File(None)
):
    """
    阶段3: 接收反馈、分析、调整参数、自动合成新语音（旧版，保留兼容）
    """
    
    if session_id not in sessions:
        return JSONResponse(status_code=404, content={"error": "会话不存在"})
    
    session = sessions[session_id]
    
    # 保存额外上传的音频
    if additional_audio:
        audio_bytes = await additional_audio.read()
        session.reference_audios.append(audio_bytes)
    
    # 理解反馈（大模型分析）
    result = await LLMService.understand_feedback(
        feedback,
        session.current_params,
        len(session.reference_audios)
    )
    
    # 应用调整
    adjustments = result.get("adjustments", {})
    for key, value in adjustments.items():
        if value is not None:
            session.current_params[key] = value
    
    # 记录历史
    session.history.append({
        "version": session.version,
        "feedback": feedback,
        "adjustments": adjustments,
        "analysis": result.get("analysis", ""),
        "function_calls": result.get("function_calls", [])
    })
    
    # 自动合成新语音
    try:
        # 执行合成
        if session.mode == "clone":
            ref_audio = session.reference_audios[0] if session.reference_audios else None
            audio_data = await FishSpeechService.synthesize(
                text=session.text,
                reference_audio=ref_audio,
                params=session.current_params
            )
        else:
            audio_data = await FishSpeechService.synthesize(
                text=session.text,
                params=session.current_params
            )
        
        # 保存音频（语速调整已在 FishSpeechService 中完成）
        os.makedirs("outputs", exist_ok=True)
        session.version += 1
        audio_filename = f"outputs/{session_id}_{session.version}.wav"
        with open(audio_filename, "wb") as f:
            f.write(audio_data)
        
        # 构建提示
        tips = result.get("tips", [])
        function_calls = result.get("function_calls", [])
        
        return {
            "session_id": session_id,
            "phase": "synthesized",
            "version": session.version,
            "mode": session.mode,
            "analysis": result.get("analysis", ""),  # 大模型分析过程
            "function_calls": function_calls,  # 调用的功能
            "adjustments": adjustments,  # 参数调整
            "current_params": session.current_params,
            "audio_url": f"/audio/{os.path.basename(audio_filename)}",
            "audio_count": len(session.reference_audios),
            "need_more_audio": result.get("need_more_audio", False),
            "tips": tips,
            "message": f"第{session.version}版合成完成（已根据反馈自动优化）"
        }
    
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


# ==================== 其他接口 ====================

@app.get("/session/{session_id}")
async def get_session(session_id: str):
    """获取会话状态"""
    if session_id not in sessions:
        return JSONResponse(status_code=404, content={"error": "会话不存在"})
    
    session = sessions[session_id]
    return {
        "session_id": session_id,
        "mode": session.mode,
        "text": session.text,
        "version": session.version,
        "audio_count": len(session.reference_audios),
        "current_params": session.current_params,
        "history": session.history
    }


@app.post("/session/{session_id}/add-audio")
async def add_audio(session_id: str, audio: UploadFile = File(...)):
    """添加更多参考音频"""
    if session_id not in sessions:
        return JSONResponse(status_code=404, content={"error": "会话不存在"})
    
    session = sessions[session_id]
    audio_bytes = await audio.read()
    session.reference_audios.append(audio_bytes)
    
    return {
        "success": True,
        "audio_count": len(session.reference_audios),
        "message": f"已添加第 {len(session.reference_audios)} 段音频"
    }


@app.get("/audio/{filename}")
async def get_audio(filename: str):
    """获取音频文件"""
    patterns = [
        f"/tmp/{filename}",
        f"/tmp/*{filename}*",
        f"outputs/{filename}",
        f"../assets/voices/{filename}",
        f"assets/voices/{filename}"
    ]
    
    for pattern in patterns:
        files = glob.glob(pattern)
        if files:
            return FileResponse(files[0], media_type="audio/wav")
    
    return JSONResponse(status_code=404, content={"error": "文件不存在"})


@app.get("/voices/{voice_id}/sample")
async def get_voice_sample(voice_id: str):
    """获取音色示例音频"""
    voices = load_voices()
    if voice_id not in voices:
        return JSONResponse(status_code=404, content={"error": "音色不存在"})
    
    voice = voices[voice_id]
    sample_audio = voice.get("sample_audio")
    
    if not sample_audio:
        return JSONResponse(status_code=404, content={"error": "该音色暂无示例音频"})
    
    patterns = [
        f"../assets/voices/{sample_audio}",
        f"assets/voices/{sample_audio}",
        f"{os.path.dirname(VOICE_CONFIG_PATH)}/{sample_audio}"
    ]
    
    for pattern in patterns:
        files = glob.glob(pattern)
        if files:
            return FileResponse(files[0], media_type="audio/wav")
    
    return JSONResponse(status_code=404, content={"error": "示例音频文件不存在"})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
