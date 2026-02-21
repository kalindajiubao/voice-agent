from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
import httpx
import os
import json
import tempfile
from typing import Optional
import asyncio

# Kimi API 配置
KIMI_API_KEY = os.getenv("KIMI_API_KEY", "")
KIMI_BASE_URL = "https://api.moonshot.cn/v1"

# AutoDL Fish Speech 配置
AUTODL_BASE_URL = os.getenv("AUTODL_BASE_URL", "http://localhost:7860")

app = FastAPI(title="Voice Agent API", version="1.0.0")

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class LLMService:
    """大模型服务 - 分析文本情感、理解用户需求"""
    
    @staticmethod
    async def analyze_emotion(text: str) -> dict:
        """分析文本情感，推荐最佳情感标签"""
        if not KIMI_API_KEY:
            # 默认返回中性
            return {
                "scene": "通用",
                "emotion": "neutral",
                "style": "自然",
                "suggested_tag": "",
                "reason": "未配置 Kimi API，使用默认"
            }
        
        prompt = f"""分析以下文本，判断最佳合成情感和语气：

文本："{text}"

请从以下维度分析：
1. 场景/场合：客服、演讲、聊天、通知、道歉、喜庆、紧急等
2. 情绪：开心、生气、悲伤、平静、兴奋、严肃等
3. 语气风格：正式、随意、温柔、严肃、活泼、沉稳等

可用的情感标签：
- (happy) 开心
- (angry) 生气
- (sad) 悲伤
- (excited) 兴奋
- (serious) 严肃
- (soft) 温柔
- (shouting) 大喊
- (whispering) 耳语

输出 JSON 格式：
{{
    "scene": "场景",
    "emotion": "情绪",
    "style": "语气风格",
    "suggested_tag": "推荐标签，如(happy)",
    "reason": "推荐理由"
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
                # 解析 JSON
                try:
                    # 提取 JSON 部分
                    if "```json" in content:
                        content = content.split("```json")[1].split("```")[0]
                    elif "```" in content:
                        content = content.split("```")[1].split("```")[0]
                    return json.loads(content.strip())
                except:
                    return {
                        "scene": "通用",
                        "emotion": "neutral",
                        "style": "自然",
                        "suggested_tag": "",
                        "reason": content
                    }
            else:
                raise HTTPException(status_code=500, detail="Kimi API 调用失败")
    
    @staticmethod
    async def modify_params(user_request: str, current_params: dict) -> dict:
        """理解用户修改需求，调整参数"""
        if not KIMI_API_KEY:
            return current_params
        
        prompt = f"""用户想要修改语音合成效果：

当前参数：{json.dumps(current_params, ensure_ascii=False)}
用户要求："{user_request}"

请分析用户需求，输出调整后的参数：
- speed: 语速 (0.5-2.0，1.0为正常)
- pitch: 音调 (-10到+10，0为正常)
- emotion_tag: 情感标签，如(angry), (happy), (soft)等

输出 JSON：
{{
    "speed": 1.0,
    "pitch": 0,
    "emotion_tag": "(happy)",
    "reason": "调整原因"
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
                    modifications = json.loads(content.strip())
                    current_params.update(modifications)
                    return current_params
                except:
                    return current_params
            else:
                return current_params


class TTSService:
    """TTS 服务 - 调用 AutoDL Fish Speech"""
    
    @staticmethod
    async def synthesize(
        text: str,
        reference_audio: Optional[bytes] = None,
        reference_id: Optional[str] = None,
        temperature: float = 0.7,
        top_p: float = 0.7,
        speed: float = 1.0
    ) -> bytes:
        """合成语音"""
        
        async with httpx.AsyncClient() as client:
            if reference_audio:
                # 使用参考音频即时克隆
                files = {"reference_audio": ("audio.wav", reference_audio, "audio/wav")}
                data = {
                    "text": text,
                    "temperature": temperature,
                    "top_p": top_p
                }
                response = await client.post(
                    f"{AUTODL_BASE_URL}/tts",
                    files=files,
                    data=data,
                    timeout=60.0
                )
            elif reference_id:
                # 使用已保存的音色ID
                data = {
                    "text": text,
                    "reference_id": reference_id,
                    "temperature": temperature,
                    "top_p": top_p
                }
                response = await client.post(
                    f"{AUTODL_BASE_URL}/tts",
                    json=data,
                    timeout=60.0
                )
            else:
                # 使用默认音色
                data = {
                    "text": text,
                    "temperature": temperature,
                    "top_p": top_p
                }
                response = await client.post(
                    f"{AUTODL_BASE_URL}/tts",
                    json=data,
                    timeout=60.0
                )
            
            if response.status_code == 200:
                return response.content
            else:
                raise HTTPException(
                    status_code=500,
                    detail=f"TTS 合成失败: {response.text}"
                )


# ========== API 路由 ==========

@app.get("/")
async def root():
    return {"message": "Voice Agent API", "version": "1.0.0"}


@app.post("/analyze")
async def analyze_text(text: str = Form(...)):
    """分析文本情感，推荐最佳情感标签"""
    result = await LLMService.analyze_emotion(text)
    return result


@app.post("/tts")
async def text_to_speech(
    text: str = Form(...),
    reference_audio: Optional[UploadFile] = File(None),
    reference_id: Optional[str] = Form(None),
    temperature: float = Form(0.7),
    top_p: float = Form(0.7),
    speed: float = Form(1.0),
    auto_emotion: bool = Form(False)
):
    """文字转语音
    
    Args:
        text: 要合成的文字（可带情感标签如 (angry) 你好）
        reference_audio: 参考音频文件（用于音色克隆）
        reference_id: 已保存的音色ID
        temperature: 采样温度
        top_p: nucleus sampling
        speed: 语速
        auto_emotion: 是否自动分析情感
    """
    
    # 自动分析情感
    if auto_emotion and "(" not in text:
        emotion_result = await LLMService.analyze_emotion(text)
        tag = emotion_result.get("suggested_tag", "")
        if tag:
            text = f"{tag} {text}"
    
    # 读取参考音频
    audio_bytes = None
    if reference_audio:
        audio_bytes = await reference_audio.read()
    
    # 合成语音
    audio_data = await TTSService.synthesize(
        text=text,
        reference_audio=audio_bytes,
        reference_id=reference_id,
        temperature=temperature,
        top_p=top_p,
        speed=speed
    )
    
    # 保存临时文件
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
        tmp.write(audio_data)
        tmp_path = tmp.name
    
    return FileResponse(tmp_path, media_type="audio/wav", filename="synthesis.wav")


@app.post("/modify")
async def modify_voice(
    text: str = Form(...),
    user_request: str = Form(...),
    reference_audio: Optional[UploadFile] = File(None),
    reference_id: Optional[str] = Form(None)
):
    """根据用户反馈修改语音
    
    Args:
        text: 原始文字
        user_request: 用户修改需求（如"要生气点""粗一点"）
        reference_audio: 参考音频
        reference_id: 音色ID
    """
    
    # 解析用户修改需求
    current_params = {
        "text": text,
        "speed": 1.0,
        "pitch": 0,
        "emotion_tag": ""
    }
    
    modified_params = await LLMService.modify_params(user_request, current_params)
    
    # 构建新文本（加情感标签）
    new_text = modified_params.get("emotion_tag", "") + " " + text
    new_text = new_text.strip()
    
    # 重新合成
    audio_bytes = None
    if reference_audio:
        audio_bytes = await reference_audio.read()
    
    audio_data = await TTSService.synthesize(
        text=new_text,
        reference_audio=audio_bytes,
        reference_id=reference_id,
        speed=modified_params.get("speed", 1.0)
    )
    
    # 保存临时文件
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
        tmp.write(audio_data)
        tmp_path = tmp.name
    
    return {
        "modified_params": modified_params,
        "audio": FileResponse(tmp_path, media_type="audio/wav", filename="modified.wav")
    }


@app.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "ok",
        "autodl_connected": True,  # TODO: 实际检查
        "kimi_configured": bool(KIMI_API_KEY)
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
