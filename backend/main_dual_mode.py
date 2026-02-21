from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from typing import Optional, Literal
import tempfile
import os
import httpx

app = FastAPI(title="Voice Agent API - Dual Mode", version="3.1.0")

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

# 预设音色列表
DEFAULT_VOICES = {
    "xiaoxiao": {"name": "晓晓", "voice_id": "zh-CN-XiaoxiaoNeural", "desc": "温柔女声"},
    "xiaoyi": {"name": "小艺", "voice_id": "zh-CN-XiaoyiNeural", "desc": "活泼女声"},
    "yunjian": {"name": "云健", "voice_id": "zh-CN-YunjianNeural", "desc": "沉稳男声"},
    "yunxi": {"name": "云希", "voice_id": "zh-CN-YunxiNeural", "desc": "年轻男声"},
    "xiaochen": {"name": "晓辰", "voice_id": "zh-CN-XiaochenNeural", "desc": "成熟女声"},
}


class VoiceSynthesizer:
    """语音合成器 - 支持克隆模式和默认模式"""
    
    async def synthesize_clone(
        self,
        text: str,
        reference_audio: bytes,
        emotion_tag: str = "",
        params: Optional[dict] = None
    ) -> bytes:
        """克隆模式：用上传的音频音色合成"""
        
        async with httpx.AsyncClient() as client:
            files = {"reference_audio": ("audio.wav", reference_audio, "audio/wav")}
            
            # 构建带情感标签的文本
            final_text = f"{emotion_tag} {text}" if emotion_tag else text
            
            data = {
                "text": final_text,
                "temperature": 0.7
            }
            
            response = await client.post(
                f"{AUTODL_BASE_URL}/tts",
                files=files,
                data=data,
                timeout=60.0
            )
            
            if response.status_code == 200:
                return response.content
            raise Exception(f"克隆合成失败: {response.text}")
    
    async def synthesize_default(
        self,
        text: str,
        voice_id: str,
        emotion_tag: str = ""
    ) -> bytes:
        """默认模式：用预设音色合成（Edge-TTS）"""
        
        import edge_tts
        import asyncio
        
        # 构建带情感标签的文本
        final_text = f"{emotion_tag} {text}" if emotion_tag else text
        
        communicate = edge_tts.Communicate(final_text, voice_id)
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
            tmp_path = tmp.name
        
        await communicate.save(tmp_path)
        
        with open(tmp_path, "rb") as f:
            return f.read()


# 初始化
synthesizer = VoiceSynthesizer()


# ========== API 路由 ==========

@app.get("/")
async def root():
    return {
        "message": "Voice Agent API - Dual Mode",
        "version": "3.1.0",
        "modes": ["clone", "default"]
    }


@app.get("/voices")
async def list_voices():
    """获取预设音色列表"""
    return {
        "voices": [
            {"id": k, "name": v["name"], "description": v["desc"]}
            for k, v in DEFAULT_VOICES.items()
        ]
    }


@app.post("/synthesize")
async def synthesize(
    mode: Literal["clone", "default"] = Form(...),
    text: str = Form(...),
    # 克隆模式参数
    reference_audio: Optional[UploadFile] = File(None),
    # 默认模式参数
    voice_id: Optional[str] = Form(None),
    # 通用参数
    emotion_tag: str = Form("")
):
    """
    合成语音 - 支持两种模式
    
    **克隆模式 (mode=clone):**
    - 必须上传 reference_audio
    - 使用上传音频的音色
    
    **默认模式 (mode=default):**
    - 必须提供 voice_id
    - 使用预设音色
    """
    
    if not text:
        return JSONResponse(status_code=400, content={"error": "文本不能为空"})
    
    try:
        if mode == "clone":
            # 克隆模式
            if not reference_audio:
                return JSONResponse(
                    status_code=400,
                    content={"error": "克隆模式需要上传参考音频", "code": "MISSING_AUDIO"}
                )
            
            audio_bytes = await reference_audio.read()
            result = await synthesizer.synthesize_clone(
                text=text,
                reference_audio=audio_bytes,
                emotion_tag=emotion_tag
            )
            
            # 保存
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
                tmp.write(result)
                tmp_path = tmp.name
            
            return {
                "mode": "clone",
                "audio_url": f"/audio/{os.path.basename(tmp_path)}",
                "message": "使用克隆音色合成成功"
            }
        
        elif mode == "default":
            # 默认模式
            if not voice_id:
                return JSONResponse(
                    status_code=400,
                    content={"error": "默认模式需要选择音色", "code": "MISSING_VOICE_ID"}
                )
            
            if voice_id not in DEFAULT_VOICES:
                return JSONResponse(
                    status_code=400,
                    content={"error": f"未知音色: {voice_id}", "code": "INVALID_VOICE"}
                )
            
            voice = DEFAULT_VOICES[voice_id]
            result = await synthesizer.synthesize_default(
                text=text,
                voice_id=voice["voice_id"],
                emotion_tag=emotion_tag
            )
            
            # 保存
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
                tmp.write(result)
                tmp_path = tmp.name
            
            return {
                "mode": "default",
                "voice_name": voice["name"],
                "audio_url": f"/audio/{os.path.basename(tmp_path)}",
                "message": f"使用预设音色 '{voice['name']}' 合成成功"
            }
        
        else:
            return JSONResponse(status_code=400, content={"error": "无效模式"})
    
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.post("/synthesize/advanced")
async def synthesize_advanced(
    mode: Literal["clone", "default"] = Form(...),
    text: str = Form(...),
    reference_audio: Optional[UploadFile] = File(None),
    voice_id: Optional[str] = Form(None),
    emotion_tag: str = Form(""),
    # 高级参数
    pitch: Optional[int] = Form(0),        # -10 ~ +10
    speed: Optional[float] = Form(1.0),    # 0.5 ~ 2.0
    volume: Optional[float] = Form(1.0)    # 0.5 ~ 2.0
):
    """
    高级合成 - 支持参数调节
    
    参数:
    - pitch: 音调 (-10 更低 ~ +10 更高)
    - speed: 语速 (0.5 更慢 ~ 2.0 更快)
    - volume: 音量 (0.5 更轻 ~ 2.0 更响)
    """
    
    # 构建带参数的文本标签
    final_text = text
    if pitch != 0:
        final_text = f"[pitch:{pitch}] {final_text}"
    if speed != 1.0:
        final_text = f"[speed:{speed}] {final_text}"
    if emotion_tag:
        final_text = f"{emotion_tag} {final_text}"
    
    # 调用基础合成
    return await synthesize(
        mode=mode,
        text=final_text,
        reference_audio=reference_audio,
        voice_id=voice_id,
        emotion_tag=""
    )


@app.get("/audio/{filename}")
async def get_audio(filename: str):
    """获取音频文件"""
    import glob
    
    # 搜索临时文件
    patterns = [
        f"/tmp/{filename}",
        f"/tmp/clone_{filename}",
        f"/tmp/default_{filename}",
        f"outputs/{filename}"
    ]
    
    for pattern in patterns:
        files = glob.glob(pattern)
        if files:
            # 根据扩展名判断类型
            if files[0].endswith('.mp3'):
                return FileResponse(files[0], media_type="audio/mpeg")
            return FileResponse(files[0], media_type="audio/wav")
    
    return JSONResponse(status_code=404, content={"error": "文件不存在"})


@app.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "ok",
        "autodl_url": AUTODL_BASE_URL,
        "modes": ["clone", "default"],
        "default_voices": len(DEFAULT_VOICES)
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
