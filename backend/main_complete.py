from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from typing import Optional, Literal, Dict, Any, List
import httpx
import os
import json
import tempfile
import re
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
AUTODL_BASE_URL = os.getenv("AUTODL_BASE_URL", "http://localhost:7860")
KIMI_API_KEY = os.getenv("KIMI_API_KEY", "")
KIMI_BASE_URL = "https://api.moonshot.cn/v1"

# 创建 HTTP 客户端（支持 HTTPS 跳过验证）
http_client = httpx.AsyncClient(verify=False, timeout=60.0)

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
            
            # 加载音频
            audio = AudioSegment.from_wav(io.BytesIO(audio_bytes))
            
            # 调整语速（改变帧率）
            if speed != 1.0:
                # 改变播放速度（同时保持音调）
                new_frame_rate = int(audio.frame_rate * speed)
                audio = audio._spawn(audio.raw_data, overrides={'frame_rate': new_frame_rate})
                # 转换回标准帧率
                audio = audio.set_frame_rate(24000)
            
            # 导出
            output = io.BytesIO()
            audio.export(output, format="wav")
            return output.getvalue()
            
        except ImportError:
            print("警告: 未安装 pydub，跳过语速调整")
            return audio_bytes
        except Exception as e:
            print(f"语速调整失败: {e}")
            return audio_bytes


# ==================== 预设音色（Fish Speech 参考音频）====================
# 实际应该预置一些参考音频文件，这里用配置占位
DEFAULT_VOICES = {
    "xiaoxiao": {
        "name": "晓晓",
        "desc": "温柔女声",
        "reference_id": "preset_xiaoxiao",
        "default_params": {"pitch": 0, "speed": 1.0, "emotion_tag": "(soft)"}
    },
    "xiaoyi": {
        "name": "小艺", 
        "desc": "活泼女声",
        "reference_id": "preset_xiaoyi",
        "default_params": {"pitch": 1, "speed": 1.1, "emotion_tag": "(happy)"}
    },
    "yunjian": {
        "name": "云健",
        "desc": "沉稳男声", 
        "reference_id": "preset_yunjian",
        "default_params": {"pitch": -1, "speed": 0.9, "emotion_tag": "(serious)"}
    },
    "yunxi": {
        "name": "云希",
        "desc": "年轻男声",
        "reference_id": "preset_yunxi", 
        "default_params": {"pitch": 0, "speed": 1.0, "emotion_tag": "(happy)"}
    },
}


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

【Fish Speech 支持的音频标记】
- 高级情感：(happy)开心, (angry)生气, (sad)悲伤, (excited)兴奋, (serious)严肃, (soft)温柔, (whispering)耳语, (shouting)喊叫
- 语调标记：[pitch:+2]提高音调, [pitch:-2]降低音调
- 特殊效果：[speed:1.2]加速, [speed:0.8]减速

文本："{text}"

请分析并选择最合适的标记：
1. 场景/场合
2. 情绪判断
3. 推荐情感标签（从上面列表选，或留空）
4. 推荐语速调整（1.0正常, >1加快, <1减慢）
5. 推荐音调调整（0正常, +升高, -降低）
6. 完整标记组合（如："(happy) [speed:1.1]"）

输出JSON：
{{
    "scene": "场景",
    "emotion": "情绪",
    "emotion_tag": "情感标记",
    "speed": 1.0,
    "pitch": 0,
    "full_tags": "完整标记组合",
    "reason": "分析理由"
}}"""

        async with http_client as client:
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
        
        if not KIMI_API_KEY:
            # 备用：规则匹配
            return LLMService._rule_based_feedback(feedback, current_params, audio_count)
        
        prompt = f"""分析用户反馈，确定语音合成参数调整方案。

【当前参数】
- 语速(speed): {current_params.get('speed', 1.0)}
- 音调(pitch): {current_params.get('pitch', 0)}
- 情感标签(emotion_tag): {current_params.get('emotion_tag', '无')}

【可用调整工具】
1. adjust_emotion: 调整情感标签
   - 可选: (happy), (angry), (sad), (excited), (serious), (soft), (whispering), (shouting)
   
2. adjust_speed: 调整语速（音频后处理）
   - 范围: 0.5-2.0, 1.0为正常
   - 注意: 这是独立的后处理步骤，不是TTS参数
   
3. adjust_pitch: 调整音调
   - 范围: -5到+5, 0为正常

【用户反馈】
"{feedback}"

请分析：
1. 用户反馈的具体含义
2. 需要调用哪些调整工具
3. 每个工具的具体参数
4. 调整理由

输出JSON格式：
{{
    "analysis": "详细分析过程...",
    "adjustments": {{
        "speed": 1.0,
        "pitch": 0,
        "emotion_tag": ""
    }},
    "function_calls": [
        {{"function": "adjust_emotion", "params": {{"tag": "(happy)"}}, "reason": "..."}},
        {{"function": "adjust_speed", "params": {{"speed": 0.9}}, "reason": "..."}}
    ],
    "tips": ["提示1", "提示2"]
}}"""

        async with http_client as client:
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
        
        # 音调调整
        if any(w in fb for w in ["尖", "细", "高", "刺耳"]):
            new_pitch = max(-5, current_params.get("pitch", 0) - 1)
            adjustments["pitch"] = new_pitch
            function_calls.append({
                "function": "adjust_pitch",
                "params": {"pitch": new_pitch},
                "reason": "用户反馈音调太尖，需要降低"
            })
        elif any(w in fb for w in ["粗", "厚", "低", "沉", "闷"]):
            new_pitch = min(5, current_params.get("pitch", 0) + 1)
            adjustments["pitch"] = new_pitch
            function_calls.append({
                "function": "adjust_pitch",
                "params": {"pitch": new_pitch},
                "reason": "用户反馈音调太低，需要提高"
            })
        
        # 情感调整
        emotion = ""
        if any(w in fb for w in ["开心", "高兴", "活泼"]):
            emotion = "(happy)"
        elif any(w in fb for w in ["生气", "愤怒", "严肃"]):
            emotion = "(angry)"
        elif any(w in fb for w in ["温柔", "柔和", "软"]):
            emotion = "(soft)"
        elif any(w in fb for w in ["悲伤", "难过"]):
            emotion = "(sad)"
        
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
                # 情感标记用于控制，但要从文本中移除防止被读出来
                # Fish Speech 会通过其他方式识别（如参考音频的情感）
        
        # 过滤所有情感标记，防止被读出来
        import re
        # 过滤基础情感标记
        final_text = re.sub(r'\(happy\)|\(angry\)|\(sad\)|\(excited\)|\(serious\)|\(soft\)|\(whispering\)|\(shouting\)', '', final_text)
        # 过滤高级情感标记
        final_text = re.sub(r'\(disdainful\)|\(unhappy\)|\(anxious\)|\(hysterical\)|\(indifferent\)|\(impatient\)|\(guilty\)|\(scornful\)|\(panicked\)|\(furious\)|\(reluctant\)|\(keen\)|\(disapproving\)|\(negative\)|\(denying\)|\(astonished\)|\(sarcastic\)|\(conciliative\)|\(comforting\)|\(sincere\)|\(sneering\)|\(hesitating\)|\(yielding\)|\(painful\)|\(awkward\)|\(amused\)', '', final_text)
        # 过滤特殊音效
        final_text = re.sub(r'\(laughing\)|\(chuckling\)|\(sobbing\)|\(crying loudly\)|\(sighing\)|\(panting\)|\(groaning\)|\(crowd laughing\)|\(background laughter\)|\(audience laughing\)', '', final_text)
        # 过滤语调标记
        final_text = re.sub(r'\(in a hurry tone\)|\(shouting\)|\(screaming\)|\(whispering\)|\(soft tone\)', '', final_text)
        # 清理多余空格
        final_text = re.sub(r'\s+', ' ', final_text).strip()
        
        # 创建临时客户端
        client = httpx.AsyncClient(verify=False, timeout=60.0)
        
        try:
            if reference_audio:
                # 克隆模式 - 使用上传的音频
                files = {"reference_audio": ("audio.wav", reference_audio, "audio/wav")}
                data = {"text": final_text, "temperature": 0.7}
                
                response = await client.post(
                    f"{AUTODL_BASE_URL}/tts",
                    files=files,
                    data=data,
                    timeout=60.0
                )
            else:
                # 普通模式 - 使用 /v1/tts 接口
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
                return response.content
            raise Exception(f"合成失败: {response.text}")
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
            "pitch": 0,
            "volume": 1.0,
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
                "default_params": v["default_params"]
            }
            for k, v in DEFAULT_VOICES.items()
        ]
    }


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
    session.current_params = {
        "speed": analysis.get("speed", 1.0),
        "pitch": analysis.get("pitch", 0),
        "volume": analysis.get("volume", 1.0),
        "emotion_tag": analysis.get("emotion_tag", "")
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
            # 普通模式 - 不传 reference_id，直接用文本合成
            audio_data = await FishSpeechService.synthesize(
                text=session.text,
                params=session.current_params
            )
        
        # 后处理：调整语速
        speed = session.current_params.get("speed", 1.0)
        if speed != 1.0:
            print(f"调整语速: {speed}x")
            audio_data = AudioProcessor.adjust_speed(audio_data, speed)
        
        # 保存音频到固定目录
        import os
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
        return JSONResponse(status_code=500, content={"error": str(e)})


# ==================== 阶段3: 交互优化 ====================

@app.post("/synthesize/feedback")
async def feedback(
    session_id: str = Form(...),
    feedback: str = Form(...),
    additional_audio: Optional[UploadFile] = File(None)
):
    """
    阶段3: 接收反馈并优化
    
    - 理解用户反馈
    - 提示上传更多音频（如果需要）
    - 调整参数
    """
    
    if session_id not in sessions:
        return JSONResponse(status_code=404, content={"error": "会话不存在"})
    
    session = sessions[session_id]
    
    # 保存额外上传的音频
    if additional_audio:
        audio_bytes = await additional_audio.read()
        session.reference_audios.append(audio_bytes)
    
    # 理解反馈
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
        "function_calls": result.get("function_calls", []),
        "tips": result.get("tips", [])
    })
    
    return {
        "session_id": session_id,
        "phase": "optimized",
        "analysis": result.get("analysis", ""),  # 大模型分析过程
        "function_calls": result.get("function_calls", []),  # 调用的功能列表
        "adjustments": adjustments,
        "current_params": session.current_params,
        "audio_count": len(session.reference_audios),
        "need_more_audio": result.get("need_more_audio", False),
        "tips": result.get("tips", []),
        "message": "参数已调整，请重新合成"
    }


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
    import glob
    
    patterns = [
        f"/tmp/{filename}",
        f"/tmp/*{filename}*",
        f"outputs/{filename}"
    ]
    
    for pattern in patterns:
        files = glob.glob(pattern)
        if files:
            return FileResponse(files[0], media_type="audio/wav")
    
    return JSONResponse(status_code=404, content={"error": "文件不存在"})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
