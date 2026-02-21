from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from agent_langchain import VoiceAgent, FishSpeechFunction, EdgeTTSFunction
import tempfile
import os

app = FastAPI(title="Voice Agent - LangChain", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 初始化 Agent
agent = VoiceAgent()


@app.get("/")
async def root():
    return {"message": "Voice Agent API (LangChain)", "version": "2.0.0"}


@app.post("/chat")
async def chat(message: str = Form(...)):
    """
    与 Agent 对话，自动选择工具执行
    
    示例：
    - "合成：你好"
    - "用开心的语气说：恭喜中奖"
    - "分析这段文字的情感：今天真倒霉"
    - "刚才的语音太温柔了，要生气点"
    """
    result = await agent.run(message)
    return {
        "response": result["output"],
        "chat_history": result.get("chat_history", [])
    }


@app.post("/tts/direct")
async def direct_tts(
    text: str = Form(...),
    provider: str = Form("fish"),  # fish 或 edge
    emotion_tag: str = Form(""),
    reference_audio: UploadFile = File(None)
):
    """直接调用 TTS，不走 Agent 决策"""
    
    if provider == "edge":
        func = EdgeTTSFunction()
        audio = await func.synthesize(text)
    else:
        func = FishSpeechFunction()
        if emotion_tag:
            text = f"{emotion_tag} {text}"
        
        audio_bytes = None
        if reference_audio:
            audio_bytes = await reference_audio.read()
        
        audio = await func.synthesize(text, reference_audio=audio_bytes)
    
    # 保存
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
        tmp.write(audio)
        return FileResponse(tmp.name, media_type="audio/wav")


@app.get("/tools")
async def list_tools():
    """列出所有可用工具"""
    return {
        "tools": [
            {
                "name": "edge_tts",
                "description": "免费快速合成",
                "params": ["text", "voice"]
            },
            {
                "name": "fish_speech_tts", 
                "description": "高质量，支持情感标签",
                "params": ["text", "emotion_tag", "use_clone"]
            },
            {
                "name": "analyze_emotion",
                "description": "分析文本情感",
                "params": ["text"]
            },
            {
                "name": "modify_voice",
                "description": "根据反馈修改语音",
                "params": ["original_text", "user_request"]
            }
        ]
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
