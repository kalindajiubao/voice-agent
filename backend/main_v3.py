from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from agent_v3 import VoiceAgent
import tempfile
import os

app = FastAPI(title="Voice Agent API v3", version="3.0.0")

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
    return {
        "message": "Voice Agent API v3",
        "version": "3.0.0",
        "features": ["多音频融合", "交互式优化", "参数调节"]
    }


@app.post("/upload")
async def upload_audio(
    audio: UploadFile = File(...),
    description: str = Form("")
):
    """上传参考音频"""
    audio_bytes = await audio.read()
    
    # 添加到优化器
    agent.clone_optimizer.add_reference_audio(audio_bytes, description)
    count = agent.clone_optimizer.get_audio_count()
    
    # 返回建议
    suggestions = agent.clone_optimizer.get_optimization_suggestions()
    
    return {
        "success": True,
        "audio_count": count,
        "message": f"已上传第 {count} 段音频",
        "suggestions": suggestions
    }


@app.post("/synthesize")
async def synthesize(
    text: str = Form(...),
    emotion_tag: str = Form(""),
    use_params: bool = Form(True)
):
    """合成语音"""
    if agent.clone_optimizer.get_audio_count() == 0:
        return JSONResponse(
            status_code=400,
            content={"error": "请先上传参考音频", "code": "NO_REFERENCE"}
        )
    
    # 获取融合音频
    from agent_v3 import FishSpeechFunction
    func = FishSpeechFunction()
    
    fused_audio = agent.clone_optimizer.get_fused_embedding()
    final_text = f"{emotion_tag} {text}" if emotion_tag else text
    
    # 合成
    import asyncio
    audio_data = await func.synthesize(
        text=final_text,
        reference_audio=fused_audio,
        params=agent.clone_optimizer.current_params if use_params else None
    )
    
    # 保存
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
        tmp.write(audio_data)
        tmp_path = tmp.name
    
    # 返回建议和参数
    suggestions = agent.clone_optimizer.get_optimization_suggestions()
    
    return {
        "audio_url": f"/audio/{os.path.basename(tmp_path)}",
        "current_params": agent.clone_optimizer.current_params,
        "suggestions": suggestions
    }


@app.post("/feedback")
async def feedback(user_feedback: str = Form(...)):
    """接收用户反馈并优化参数"""
    adjustments = agent.clone_optimizer.adjust_params(user_feedback)
    
    if not adjustments:
        return {
            "success": False,
            "message": "未能理解反馈，请尝试更具体的描述",
            "examples": ["太年轻了", "音调太尖", "语速太快", "没感情"]
        }
    
    return {
        "success": True,
        "adjustments": adjustments,
        "current_params": agent.clone_optimizer.current_params,
        "message": "参数已调整，请重新合成"
    }


@app.get("/status")
async def get_status():
    """获取当前状态"""
    return {
        "audio_count": agent.clone_optimizer.get_audio_count(),
        "feedback_count": len(agent.clone_optimizer.feedback_history),
        "current_params": agent.clone_optimizer.current_params,
        "suggestions": agent.clone_optimizer.get_optimization_suggestions()
    }


@app.post("/reset")
async def reset_params():
    """重置参数"""
    agent.clone_optimizer.reset_params()
    return {"success": True, "message": "参数已重置"}


@app.get("/audio/{filename}")
async def get_audio(filename: str):
    """获取音频文件"""
    # 简化处理，实际应该更安全的路径处理
    import glob
    files = glob.glob(f"/tmp/{filename}") + glob.glob(f"outputs/{filename}")
    if files:
        return FileResponse(files[0], media_type="audio/wav")
    return JSONResponse(status_code=404, content={"error": "文件不存在"})


@app.post("/chat")
async def chat(message: str = Form(...)):
    """对话式交互"""
    result = await agent.run(message)
    return {"response": result["output"]}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
