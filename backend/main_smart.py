from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from typing import Optional, Literal, Dict, Any
import httpx
import os
import json
import tempfile

app = FastAPI(title="Voice Agent - Smart Synthesis", version="4.0.0")

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

# 预设音色
DEFAULT_VOICES = {
    "xiaoxiao": {"name": "晓晓", "voice_id": "zh-CN-XiaoxiaoNeural", "desc": "温柔女声"},
    "xiaoyi": {"name": "小艺", "voice_id": "zh-CN-XiaoyiNeural", "desc": "活泼女声"},
    "yunjian": {"name": "云健", "voice_id": "zh-CN-YunjianNeural", "desc": "沉稳男声"},
    "yunxi": {"name": "云希", "voice_id": "zh-CN-YunxiNeural", "desc": "年轻男声"},
}


class LLMService:
    """大模型服务 - 智能分析"""
    
    @staticmethod
    async def analyze_text(text: str) -> Dict[str, Any]:
        """阶段1: 分析文本，确定合成参数"""
        
        if not KIMI_API_KEY:
            # 默认返回
            return {
                "scene": "通用对话",
                "emotion": "neutral",
                "emotion_tag": "",
                "pitch": 0,
                "speed": 1.0,
                "style": "自然",
                "reason": "未配置Kimi API，使用默认参数"
            }
        
        prompt = f"""分析以下文本，确定最佳语音合成参数：

文本："{text}"

请分析：
1. 场景/场合（如：客服、演讲、聊天、通知、道歉、喜庆、紧急等）
2. 情绪（如：开心、生气、悲伤、平静、兴奋、严肃等）
3. 语气风格（如：正式、随意、温柔、严肃、活泼、沉稳等）
4. 推荐语速（0.5-2.0，1.0为正常）
5. 推荐音调（-5到+5，0为正常，负值更低沉，正值更尖）
6. 推荐情感标签（可选：(happy), (angry), (sad), (excited), (serious), (soft)等）

输出JSON格式：
{{
    "scene": "场景",
    "emotion": "情绪",
    "style": "语气风格",
    "speed": 1.0,
    "pitch": 0,
    "emotion_tag": "情感标签或空字符串",
    "reason": "分析理由"
}}"""

        async with httpx.AsyncClient() as client:
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
                
                # 解析JSON
                try:
                    if "```json" in content:
                        content = content.split("```json")[1].split("```")[0]
                    elif "```" in content:
                        content = content.split("```")[1].split("```")[0]
                    return json.loads(content.strip())
                except:
                    return {
                        "scene": "通用",
                        "emotion": "neutral",
                        "emotion_tag": "",
                        "pitch": 0,
                        "speed": 1.0,
                        "style": "自然",
                        "reason": content
                    }
            else:
                raise Exception(f"Kimi API 失败: {response.text}")
    
    @staticmethod
    async def understand_feedback(feedback: str, current_params: Dict) -> Dict[str, Any]:
        """阶段2: 理解用户反馈，确定调整方案"""
        
        if not KIMI_API_KEY:
            # 简单规则匹配
            return LLMService._rule_based_feedback(feedback, current_params)
        
        prompt = f"""用户听完合成语音后提供了反馈，请分析需要调整哪些参数。

用户反馈："{feedback}"

当前参数：
- 语速(speed): {current_params.get('speed', 1.0)}
- 音调(pitch): {current_params.get('pitch', 0)}
- 情感标签(emotion_tag): {current_params.get('emotion_tag', '')}

可调参数：
- speed: 语速 (0.5-2.0)，值越大越快
- pitch: 音调 (-5到+5)，正值更尖，负值更低沉
- emotion_tag: 情感标签，可选：(happy), (angry), (sad), (excited), (serious), (soft), (shouting), (whispering)

输出JSON格式：
{{
    "adjustments": {{
        "speed": 1.0,
        "pitch": 0,
        "emotion_tag": ""
    }},
    "action": "调整描述",
    "reason": "调整理由"
}}"""

        async with httpx.AsyncClient() as client:
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
                    return LLMService._rule_based_feedback(feedback, current_params)
            else:
                return LLMService._rule_based_feedback(feedback, current_params)
    
    @staticmethod
    def _rule_based_feedback(feedback: str, current_params: Dict) -> Dict[str, Any]:
        """基于规则的反馈处理（备用）"""
        fb = feedback.lower()
        adjustments = {}
        
        # 语速
        if any(w in fb for w in ["快", "急", "赶", "加速"]):
            adjustments["speed"] = min(2.0, current_params.get("speed", 1.0) + 0.2)
        elif any(w in fb for w in ["慢", "缓", "拖", "减速"]):
            adjustments["speed"] = max(0.5, current_params.get("speed", 1.0) - 0.2)
        
        # 音调
        if any(w in fb for w in ["尖", "细", "高", "刺耳"]):
            adjustments["pitch"] = max(-5, current_params.get("pitch", 0) - 1)
        elif any(w in fb for w in ["粗", "厚", "低", "沉", "闷"]):
            adjustments["pitch"] = min(5, current_params.get("pitch", 0) + 1)
        
        # 年龄
        if any(w in fb for w in ["年轻", "嫩", "小孩"]):
            adjustments["emotion_tag"] = "(serious)"
        elif any(w in fb for w in ["老", "成熟", "沧桑"]):
            adjustments["emotion_tag"] = "(soft)"
        
        # 情感
        if any(w in fb for w in ["开心", "高兴", "活泼"]):
            adjustments["emotion_tag"] = "(happy)"
        elif any(w in fb for w in ["生气", "愤怒", "严肃"]):
            adjustments["emotion_tag"] = "(angry)"
        elif any(w in fb for w in ["温柔", "柔和"]):
            adjustments["emotion_tag"] = "(soft)"
        elif any(w in fb for w in ["悲伤", "难过"]):
            adjustments["emotion_tag"] = "(sad)"
        
        return {
            "adjustments": adjustments,
            "action": "基于规则的调整",
            "reason": f"识别到关键词: {fb}"
        }


class SynthesisSession:
    """合成会话 - 保存状态"""
    
    def __init__(self):
        self.text = ""
        self.mode = "default"  # clone 或 default
        self.voice_id = "xiaoxiao"
        self.reference_audio = None
        self.analysis = {}  # 阶段1分析结果
        self.current_params = {
            "speed": 1.0,
            "pitch": 0,
            "emotion_tag": ""
        }
        self.history = []  # 优化历史
        self.version = 0


# 存储会话（简化版，生产环境用Redis）
sessions = {}


@app.post("/synthesize/start")
async def start_synthesis(
    mode: Literal["clone", "default"] = Form(...),
    text: str = Form(...),
    voice_id: Optional[str] = Form("xiaoxiao"),
    reference_audio: Optional[UploadFile] = File(None)
):
    """
    阶段1: 开始合成 - 智能分析文本
    
    1. 接收用户输入
    2. 大模型分析文本场景、情感
    3. 返回推荐的合成参数
    4. 用户确认后开始合成
    """
    
    if not text:
        return JSONResponse(status_code=400, content={"error": "文本不能为空"})
    
    # 创建会话
    session_id = f"sess_{len(sessions)}"
    session = SynthesisSession()
    session.text = text
    session.mode = mode
    session.voice_id = voice_id
    
    if reference_audio:
        session.reference_audio = await reference_audio.read()
    
    # 智能分析
    analysis = await LLMService.analyze_text(text)
    session.analysis = analysis
    
    # 应用分析结果到参数
    session.current_params["speed"] = analysis.get("speed", 1.0)
    session.current_params["pitch"] = analysis.get("pitch", 0)
    session.current_params["emotion_tag"] = analysis.get("emotion_tag", "")
    
    sessions[session_id] = session
    
    return {
        "session_id": session_id,
        "phase": "analysis",
        "text": text,
        "analysis": analysis,
        "suggested_params": session.current_params,
        "message": "分析完成，请确认参数或调整"
    }


@app.post("/synthesize/confirm")
async def confirm_synthesis(
    session_id: str = Form(...),
    speed: Optional[float] = Form(None),
    pitch: Optional[int] = Form(None),
    emotion_tag: Optional[str] = Form(None)
):
    """
    确认参数并合成第一版
    """
    if session_id not in sessions:
        return JSONResponse(status_code=404, content={"error": "会话不存在"})
    
    session = sessions[session_id]
    
    # 应用用户调整
    if speed is not None:
        session.current_params["speed"] = speed
    if pitch is not None:
        session.current_params["pitch"] = pitch
    if emotion_tag is not None:
        session.current_params["emotion_tag"] = emotion_tag
    
    # 合成语音
    try:
        audio_data = await do_synthesis(session)
        
        # 保存
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
            tmp.write(audio_data)
            audio_path = tmp.name
        
        session.version += 1
        
        return {
            "session_id": session_id,
            "phase": "synthesized",
            "version": session.version,
            "audio_url": f"/audio/{os.path.basename(audio_path)}",
            "params": session.current_params,
            "message": "第1版合成完成，请试听并提供反馈"
        }
    
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.post("/synthesize/feedback")
async def feedback_and_optimize(
    session_id: str = Form(...),
    feedback: str = Form(...)
):
    """
    阶段2: 接收反馈并优化
    
    1. 接收用户反馈
    2. 大模型理解需求
    3. 调整参数
    4. 重新合成
    """
    if session_id not in sessions:
        return JSONResponse(status_code=404, content={"error": "会话不存在"})
    
    session = sessions[session_id]
    
    # 记录反馈
    session.history.append({
        "version": session.version,
        "feedback": feedback,
        "params_before": session.current_params.copy()
    })
    
    # 大模型理解反馈
    result = await LLMService.understand_feedback(feedback, session.current_params)
    adjustments = result.get("adjustments", {})
    
    # 应用调整
    for key, value in adjustments.items():
        if value:  # 不为空
            session.current_params[key] = value
    
    # 记录调整后
    session.history[-1]["params_after"] = session.current_params.copy()
    session.history[-1]["adjustment_reason"] = result.get("reason", "")
    
    # 重新合成
    try:
        audio_data = await do_synthesis(session)
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
            tmp.write(audio_data)
            audio_path = tmp.name
        
        session.version += 1
        
        return {
            "session_id": session_id,
            "phase": "optimized",
            "version": session.version,
            "audio_url": f"/audio/{os.path.basename(audio_path)}",
            "adjustments": adjustments,
            "current_params": session.current_params,
            "action": result.get("action", "参数调整"),
            "reason": result.get("reason", ""),
            "message": f"第{session.version}版合成完成"
        }
    
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


async def do_synthesis(session: SynthesisSession) -> bytes:
    """执行合成"""
    
    # 构建带参数的文本
    text = session.text
    params = session.current_params
    
    if params.get("emotion_tag"):
        text = f"{params['emotion_tag']} {text}"
    
    # 克隆模式
    if session.mode == "clone":
        if not session.reference_audio:
            raise Exception("克隆模式需要参考音频")
        
        async with httpx.AsyncClient() as client:
            files = {"reference_audio": ("audio.wav", session.reference_audio, "audio/wav")}
            data = {"text": text, "temperature": 0.7}
            
            response = await client.post(
                f"{AUTODL_BASE_URL}/tts",
                files=files,
                data=data,
                timeout=60.0
            )
            
            if response.status_code == 200:
                return response.content
            raise Exception(f"合成失败: {response.text}")
    
    # 默认模式
    else:
        import edge_tts
        
        voice = DEFAULT_VOICES.get(session.voice_id, DEFAULT_VOICES["xiaoxiao"])
        communicate = edge_tts.Communicate(text, voice["voice_id"])
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
            tmp_path = tmp.name
        
        await communicate.save(tmp_path)
        
        with open(tmp_path, "rb") as f:
            return f.read()


@app.get("/session/{session_id}")
async def get_session(session_id: str):
    """获取会话状态"""
    if session_id not in sessions:
        return JSONResponse(status_code=404, content={"error": "会话不存在"})
    
    session = sessions[session_id]
    return {
        "session_id": session_id,
        "text": session.text,
        "mode": session.mode,
        "current_params": session.current_params,
        "version": session.version,
        "history": session.history
    }


@app.get("/voices")
async def list_voices():
    """获取预设音色"""
    return {"voices": [{"id": k, **v} for k, v in DEFAULT_VOICES.items()]}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
