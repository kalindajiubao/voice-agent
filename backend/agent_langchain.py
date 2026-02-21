from langchain.agents import Tool, AgentExecutor, create_openai_functions_agent
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.memory import ConversationBufferMemory
from typing import Dict, Any, Optional
import httpx
import os

# 配置
KIMI_API_KEY = os.getenv("KIMI_API_KEY", "")
AUTODL_BASE_URL = os.getenv("AUTODL_BASE_URL", "http://localhost:7860")

# 兼容 Kimi 的 OpenAI 配置
os.environ["OPENAI_API_KEY"] = KIMI_API_KEY
os.environ["OPENAI_API_BASE"] = "https://api.moonshot.cn/v1"


class TTSFunction:
    """TTS 工具基类"""
    
    async def synthesize(self, text: str, **kwargs) -> bytes:
        raise NotImplementedError


class EdgeTTSFunction(TTSFunction):
    """Edge TTS - 免费、快速"""
    
    name = "edge_tts"
    description = "使用 Edge TTS 合成语音，免费但音色有限，不支持情感控制"
    
    async def synthesize(self, text: str, voice: str = "zh-CN-XiaoxiaoNeural") -> bytes:
        import edge_tts
        import asyncio
        
        communicate = edge_tts.Communicate(text, voice)
        
        # 保存到临时文件
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
            tmp_path = tmp.name
        
        await communicate.save(tmp_path)
        
        with open(tmp_path, "rb") as f:
            return f.read()


class FishSpeechFunction(TTSFunction):
    """Fish Speech - 支持情感标签、音色克隆"""
    
    name = "fish_speech_tts"
    description = """使用 Fish Speech 合成语音，支持：
    - 情感标签：(happy), (angry), (sad), (excited), (serious), (soft), (shouting), (whispering)
    - 音色克隆：上传参考音频
    - 高质量中文合成
    """
    
    async def synthesize(
        self, 
        text: str, 
        reference_audio: Optional[bytes] = None,
        temperature: float = 0.7
    ) -> bytes:
        async with httpx.AsyncClient() as client:
            if reference_audio:
                files = {"reference_audio": ("audio.wav", reference_audio, "audio/wav")}
                data = {"text": text, "temperature": temperature}
                response = await client.post(
                    f"{AUTODL_BASE_URL}/tts", files=files, data=data, timeout=60.0
                )
            else:
                data = {"text": text, "temperature": temperature}
                response = await client.post(
                    f"{AUTODL_BASE_URL}/tts", json=data, timeout=60.0
                )
            
            if response.status_code == 200:
                return response.content
            raise Exception(f"Fish Speech 失败: {response.text}")


class VoiceCloneFunction:
    """音色克隆工具"""
    
    name = "clone_voice"
    description = "上传音频文件，克隆特定人的音色，后续可用该音色合成语音"
    
    async def clone(self, audio_file: bytes, voice_name: str) -> str:
        # 保存到向量库或文件系统
        # 返回 voice_id
        return f"voice_{voice_name}_{hash(audio_file) % 10000}"


class EmotionAnalysisFunction:
    """情感分析工具"""
    
    name = "analyze_emotion"
    description = """分析文本情感，推荐最佳情感标签和语气。
    返回：场景、情绪、风格、推荐标签"""
    
    async def analyze(self, text: str) -> Dict[str, Any]:
        # 这里实际由 LLM 直接处理，不需要单独调用
        return {
            "scene": "通用",
            "emotion": "neutral",
            "style": "自然",
            "suggested_tag": ""
        }


class VoiceAgent:
    """语音 Agent - 基于 LangChain"""
    
    def __init__(self):
        self.llm = ChatOpenAI(
            model="moonshot-v1-8k",
            temperature=0.3
        )
        
        # 初始化工具
        self.tools = self._create_tools()
        
        # 创建 Agent
        self.agent = create_openai_functions_agent(
            llm=self.llm,
            tools=self.tools,
            prompt=self._create_prompt()
        )
        
        # Agent Executor
        self.executor = AgentExecutor(
            agent=self.agent,
            tools=self.tools,
            memory=ConversationBufferMemory(
                memory_key="chat_history",
                return_messages=True
            ),
            verbose=True
        )
    
    def _create_tools(self) -> list:
        """创建工具列表"""
        
        async def edge_tts_tool(text: str, voice: str = "zh-CN-XiaoxiaoNeural") -> str:
            """使用 Edge TTS 快速合成语音"""
            func = EdgeTTSFunction()
            audio = await func.synthesize(text, voice)
            # 保存并返回路径
            return self._save_audio(audio, "edge")
        
        async def fish_tts_tool(
            text: str, 
            emotion_tag: str = "",
            use_clone: bool = False
        ) -> str:
            """使用 Fish Speech 合成高质量语音，支持情感标签"""
            func = FishSpeechFunction()
            if emotion_tag:
                text = f"{emotion_tag} {text}"
            audio = await func.synthesize(text)
            return self._save_audio(audio, "fish")
        
        async def analyze_emotion_tool(text: str) -> str:
            """分析文本情感，推荐最佳情感标签"""
            # LLM 直接处理
            return "建议使用 (happy) 标签，文本表达喜悦情绪"
        
        async def modify_voice_tool(
            original_text: str,
            user_request: str
        ) -> str:
            """根据用户反馈修改语音参数"""
            # 解析用户意图
            if "生气" in user_request:
                return f"(angry) {original_text}"
            elif "温柔" in user_request or "软" in user_request:
                return f"(soft) {original_text}"
            elif "快" in user_request:
                return f"[speed:1.5] {original_text}"
            else:
                return original_text
        
        return [
            Tool(
                name="edge_tts",
                func=lambda x: edge_tts_tool(**eval(x)),
                description="Edge TTS：免费快速合成，适合简单场景。参数：{\"text\": \"你好\", \"voice\": \"zh-CN-XiaoxiaoNeural\"}"
            ),
            Tool(
                name="fish_speech_tts",
                func=lambda x: fish_tts_tool(**eval(x)),
                description="Fish Speech：高质量合成，支持情感标签。参数：{\"text\": \"你好\", \"emotion_tag\": \"(happy)\", \"use_clone\": false}"
            ),
            Tool(
                name="analyze_emotion",
                func=lambda x: analyze_emotion_tool(x),
                description="分析文本情感，推荐情感标签。参数：文本内容"
            ),
            Tool(
                name="modify_voice",
                func=lambda x: modify_voice_tool(**eval(x)),
                description="根据用户反馈修改语音。参数：{\"original_text\": \"你好\", \"user_request\": \"要生气点\"}"
            ),
        ]
    
    def _create_prompt(self):
        """创建 Agent Prompt"""
        return ChatPromptTemplate.from_messages([
            ("system", """你是一个智能语音合成助手，帮助用户合成高质量的语音。

你可以使用的工具：
1. edge_tts - 免费快速合成，适合简单场景
2. fish_speech_tts - 高质量合成，支持情感标签如 (happy), (angry), (sad) 等
3. analyze_emotion - 分析文本推荐最佳情感
4. modify_voice - 根据用户反馈调整语音

工作流程：
1. 如果用户只说文字，先 analyze_emotion 分析，再用 fish_speech_tts 合成
2. 如果用户指定了情感，直接用 fish_speech_tts 合成
3. 如果用户要求修改，用 modify_voice 调整后再合成

情感标签说明：
- (happy) 开心
- (angry) 生气  
- (sad) 悲伤
- (excited) 兴奋
- (serious) 严肃
- (soft) 温柔
- (shouting) 大喊
- (whispering) 耳语
"""),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])
    
    def _save_audio(self, audio: bytes, prefix: str) -> str:
        """保存音频并返回路径"""
        import tempfile
        import os
        
        os.makedirs("outputs", exist_ok=True)
        with tempfile.NamedTemporaryFile(
            delete=False, 
            suffix=".wav",
            dir="outputs",
            prefix=f"{prefix}_"
        ) as f:
            f.write(audio)
            return f.name
    
    async def run(self, user_input: str) -> Dict[str, Any]:
        """运行 Agent"""
        result = await self.executor.ainvoke({"input": user_input})
        return result


# 使用示例
if __name__ == "__main__":
    import asyncio
    
    async def main():
        agent = VoiceAgent()
        
        # 示例 1：简单合成
        result = await agent.run("合成：你好，很高兴见到你")
        print(f"输出：{result['output']}")
        
        # 示例 2：指定情感
        result = await agent.run("用生气的语气说：你怎么迟到了")
        print(f"输出：{result['output']}")
        
        # 示例 3：修改语音
        result = await agent.run("刚才的语音太温柔了，要生气一点")
        print(f"输出：{result['output']}")
    
    asyncio.run(main())
