from langchain.agents import Tool, AgentExecutor, create_openai_functions_agent
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.memory import ConversationBufferMemory
from typing import Dict, Any, Optional, List
import httpx
import os
import numpy as np

# 配置
KIMI_API_KEY = os.getenv("KIMI_API_KEY", "")
AUTODL_BASE_URL = os.getenv("AUTODL_BASE_URL", "http://localhost:7860")

os.environ["OPENAI_API_KEY"] = KIMI_API_KEY
os.environ["OPENAI_API_BASE"] = "https://api.moonshot.cn/v1"


class VoiceCloneOptimizer:
    """音色克隆优化器 - 支持多音频融合和参数调节"""
    
    def __init__(self):
        self.reference_audios = []  # 存储多段参考音频
        self.current_params = {
            "pitch": 0,           # 音调: -10 ~ +10
            "speed": 1.0,         # 语速: 0.5 ~ 2.0
            "timbre_depth": 0,    # 音色厚度: -5 ~ +5
            "age_shift": 0,       # 年龄感: -5(更老) ~ +5(更年轻)
            "emotion_strength": 1.0  # 情感强度: 0.5 ~ 2.0
        }
        self.feedback_history = []
    
    def add_reference_audio(self, audio_bytes: bytes, description: str = ""):
        """添加参考音频"""
        self.reference_audios.append({
            "audio": audio_bytes,
            "description": description
        })
    
    def get_audio_count(self) -> int:
        """获取已上传音频数量"""
        return len(self.reference_audios)
    
    def get_fused_embedding(self):
        """融合多段音频的特征"""
        if len(self.reference_audios) == 0:
            return None
        if len(self.reference_audios) == 1:
            return self.reference_audios[0]["audio"]
        
        # TODO: 实现真正的特征融合
        # 目前简单返回第一个，实际应该调用模型的融合API
        return self.reference_audios[0]["audio"]
    
    def adjust_params(self, feedback: str) -> Dict[str, Any]:
        """根据用户反馈调整参数"""
        feedback_lower = feedback.lower()
        adjustments = {}
        
        # 年龄相关
        if any(word in feedback_lower for word in ["年轻", "嫩", "小孩", "太幼"]):
            self.current_params["age_shift"] -= 2
            adjustments["age_shift"] = self.current_params["age_shift"]
        elif any(word in feedback_lower for word in ["老", "成熟", "沧桑", "太老"]):
            self.current_params["age_shift"] += 2
            adjustments["age_shift"] = self.current_params["age_shift"]
        
        # 音调相关
        if any(word in feedback_lower for word in ["尖", "细", "高", "刺耳"]):
            self.current_params["pitch"] -= 2
            self.current_params["timbre_depth"] += 1
            adjustments["pitch"] = self.current_params["pitch"]
            adjustments["timbre_depth"] = self.current_params["timbre_depth"]
        elif any(word in feedback_lower for word in ["粗", "厚", "低", "沉", "闷"]):
            self.current_params["pitch"] += 2
            self.current_params["timbre_depth"] -= 1
            adjustments["pitch"] = self.current_params["pitch"]
            adjustments["timbre_depth"] = self.current_params["timbre_depth"]
        
        # 语速相关
        if any(word in feedback_lower for word in ["快", "急", "赶"]):
            self.current_params["speed"] -= 0.2
            adjustments["speed"] = self.current_params["speed"]
        elif any(word in feedback_lower for word in ["慢", "缓", "拖"]):
            self.current_params["speed"] += 0.2
            adjustments["speed"] = self.current_params["speed"]
        
        # 情感强度
        if any(word in feedback_lower for word in ["平淡", "没感情", "机械"]):
            self.current_params["emotion_strength"] += 0.3
            adjustments["emotion_strength"] = self.current_params["emotion_strength"]
        elif any(word in feedback_lower for word in ["太夸张", "过火", "做作"]):
            self.current_params["emotion_strength"] -= 0.3
            adjustments["emotion_strength"] = self.current_params["emotion_strength"]
        
        self.feedback_history.append({
            "feedback": feedback,
            "adjustments": adjustments
        })
        
        return adjustments
    
    def get_optimization_suggestions(self) -> List[str]:
        """根据当前状态给出优化建议"""
        suggestions = []
        
        if len(self.reference_audios) == 0:
            suggestions.append("📤 请先上传一段参考音频（建议 10-30 秒）")
        elif len(self.reference_audios) == 1:
            suggestions.append("💡 提示：上传 2-3 段不同语调/情感的音频，融合后效果更稳定")
        elif len(self.reference_audios) >= 3:
            suggestions.append(f"✅ 已上传 {len(self.reference_audios)} 段音频，融合效果较好")
        
        if len(self.feedback_history) > 0:
            suggestions.append(f"📝 已根据 {len(self.feedback_history)} 次反馈优化参数")
        
        return suggestions
    
    def reset_params(self):
        """重置参数"""
        self.current_params = {
            "pitch": 0,
            "speed": 1.0,
            "timbre_depth": 0,
            "age_shift": 0,
            "emotion_strength": 1.0
        }


class FishSpeechFunction:
    """Fish Speech - 支持参数调节的 TTS"""
    
    name = "fish_speech_tts"
    description = """使用 Fish Speech 合成语音，支持情感标签和参数调节"""
    
    async def synthesize(
        self, 
        text: str, 
        reference_audio: Optional[bytes] = None,
        params: Optional[Dict] = None,
        temperature: float = 0.7
    ) -> bytes:
        """合成语音，支持参数调节"""
        
        # 应用参数调节（通过文本标签模拟）
        if params:
            # 音调调节
            pitch = params.get("pitch", 0)
            if pitch < -2:
                text = f"[pitch:low] {text}"
            elif pitch > 2:
                text = f"[pitch:high] {text}"
            
            # 语速调节
            speed = params.get("speed", 1.0)
            if speed < 0.9:
                text = f"[speed:slow] {text}"
            elif speed > 1.1:
                text = f"[speed:fast] {text}"
            
            # 年龄感（通过情感标签模拟）
            age_shift = params.get("age_shift", 0)
            if age_shift < -2:
                text = f"(soft) {text}"  # 年轻感
            elif age_shift > 2:
                text = f"(serious) {text}"  # 成熟感
        
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


class VoiceAgent:
    """语音 Agent - 支持交互式优化"""
    
    def __init__(self):
        self.llm = ChatOpenAI(model="moonshot-v1-8k", temperature=0.3)
        self.clone_optimizer = VoiceCloneOptimizer()
        self.tools = self._create_tools()
        
        self.agent = create_openai_functions_agent(
            llm=self.llm,
            tools=self.tools,
            prompt=self._create_prompt()
        )
        
        self.executor = AgentExecutor(
            agent=self.agent,
            tools=self.tools,
            memory=ConversationBufferMemory(memory_key="chat_history", return_messages=True),
            verbose=True
        )
    
    def _create_tools(self) -> list:
        """创建工具列表"""
        
        async def upload_reference_audio(audio_bytes: str, description: str = "") -> str:
            """上传参考音频用于音色克隆。支持多次上传，多段音频会融合使用。"""
            # 注意：实际应该接收 bytes，这里简化处理
            self.clone_optimizer.add_reference_audio(audio_bytes.encode(), description)
            count = self.clone_optimizer.get_audio_count()
            
            if count == 1:
                return f"✅ 已上传第 1 段音频。💡 建议再上传 1-2 段不同语调的音频，融合后效果更稳定。"
            elif count == 2:
                return f"✅ 已上传第 2 段音频。💡 可以再上传 1 段，或开始合成。"
            else:
                return f"✅ 已上传第 {count} 段音频，融合效果较好，可以开始合成。"
        
        async def synthesize_with_clone(text: str, emotion_tag: str = "") -> str:
            """使用克隆的音色合成语音。如果已上传多段音频，会自动融合。"""
            if self.clone_optimizer.get_audio_count() == 0:
                return "❌ 请先上传参考音频"
            
            # 获取融合后的音频
            fused_audio = self.clone_optimizer.get_fused_embedding()
            
            # 应用当前参数
            func = FishSpeechFunction()
            final_text = f"{emotion_tag} {text}" if emotion_tag else text
            
            audio = await func.synthesize(
                text=final_text,
                reference_audio=fused_audio,
                params=self.clone_optimizer.current_params
            )
            
            # 保存并返回路径
            path = self._save_audio(audio, "cloned")
            suggestions = self.clone_optimizer.get_optimization_suggestions()
            
            return f"✅ 合成完成：{path}\n\n" + "\n".join(suggestions)
        
        async def optimize_voice(feedback: str) -> str:
            """根据反馈优化音色。可以描述问题如：'太年轻了'、'音调太尖'、'语速太快'等。"""
            adjustments = self.clone_optimizer.adjust_params(feedback)
            
            if not adjustments:
                return f"🤔 未能理解反馈：'{feedback}'。请尝试描述具体一些，如：\n- '太年轻了'\n- '音调太尖'\n- '语速太快'\n- '情感太平淡'"
            
            adjustment_desc = []
            for param, value in adjustments.items():
                if param == "pitch":
                    adjustment_desc.append(f"音调 {'降低' if value < 0 else '提高'} 到 {value}")
                elif param == "speed":
                    adjustment_desc.append(f"语速 {'减慢' if value < 1.0 else '加快'} 到 {value:.1f}")
                elif param == "age_shift":
                    adjustment_desc.append(f"年龄感 {'增加' if value > 0 else '减少'} 到 {value}")
                elif param == "timbre_depth":
                    adjustment_desc.append(f"音色厚度 {'增加' if value > 0 else '减少'} 到 {value}")
                elif param == "emotion_strength":
                    adjustment_desc.append(f"情感强度调整到 {value:.1f}")
            
            return f"✅ 已根据反馈调整：\n" + "\n".join(f"  - {desc}" for desc in adjustment_desc) + "\n\n请重新合成语音查看效果。"
        
        async def get_optimization_tips() -> str:
            """获取优化建议"""
            suggestions = self.clone_optimizer.get_optimization_suggestions()
            current_params = self.clone_optimizer.current_params
            
            result = "📊 当前状态：\n"
            result += f"  - 参考音频：{self.clone_optimizer.get_audio_count()} 段\n"
            result += f"  - 优化次数：{len(self.clone_optimizer.feedback_history)} 次\n\n"
            result += "🔧 当前参数：\n"
            for param, value in current_params.items():
                result += f"  - {param}: {value}\n"
            result += "\n💡 建议：\n"
            result += "\n".join(f"  - {s}" for s in suggestions)
            
            return result
        
        async def reset_voice_params() -> str:
            """重置所有参数到默认值"""
            self.clone_optimizer.reset_params()
            return "✅ 参数已重置为默认值"
        
        return [
            Tool(
                name="upload_reference_audio",
                func=lambda x: upload_reference_audio(**eval(x)),
                description="上传参考音频用于音色克隆。参数：{\"audio_bytes\": \"...\", \"description\": \"描述\"}"
            ),
            Tool(
                name="synthesize_with_clone",
                func=lambda x: synthesize_with_clone(**eval(x)),
                description="使用克隆音色合成语音。参数：{\"text\": \"你好\", \"emotion_tag\": \"(happy)\"}"
            ),
            Tool(
                name="optimize_voice",
                func=lambda x: optimize_voice(x),
                description="根据反馈优化音色。参数：反馈描述如'太年轻了'、'音调太尖'"
            ),
            Tool(
                name="get_optimization_tips",
                func=lambda x: get_optimization_tips(),
                description="获取当前优化建议和参数状态"
            ),
            Tool(
                name="reset_voice_params",
                func=lambda x: reset_voice_params(),
                description="重置所有参数到默认值"
            ),
        ]
    
    def _create_prompt(self):
        return ChatPromptTemplate.from_messages([
            ("system", """你是智能语音合成助手，帮助用户克隆和优化音色。

工作流程：
1. 引导用户上传参考音频（建议 10-30 秒，清晰无噪音）
2. 提醒用户可以上传多段音频融合，效果更好
3. 合成后询问用户反馈
4. 根据反馈使用 optimize_voice 调整参数
5. 重新合成，直到用户满意

可调参数：
- pitch: 音调高低（-10 ~ +10）
- speed: 语速快慢（0.5 ~ 2.0）
- timbre_depth: 音色厚度（-5 ~ +5）
- age_shift: 年龄感（-5 更年轻 ~ +5 更成熟）
- emotion_strength: 情感强度（0.5 ~ 2.0）

常见反馈及处理：
- "太年轻了" → age_shift 增加
- "太老了" → age_shift 减少
- "音调太尖" → pitch 降低，timbre_depth 增加
- "声音太粗" → pitch 提高，timbre_depth 减少
- "语速太快" → speed 降低
- "语速太慢" → speed 提高
- "没感情" → emotion_strength 增加
"""),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])
    
    def _save_audio(self, audio: bytes, prefix: str) -> str:
        import tempfile
        import os
        os.makedirs("outputs", exist_ok=True)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav", dir="outputs", prefix=f"{prefix}_") as f:
            f.write(audio)
            return f.name
    
    async def run(self, user_input: str) -> Dict[str, Any]:
        result = await self.executor.ainvoke({"input": user_input})
        return result
