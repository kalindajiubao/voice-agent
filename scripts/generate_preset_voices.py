#!/usr/bin/env python3
"""
生成预设音色参考音频
使用 Edge-TTS 生成不同音色的样本
"""
import asyncio
import edge_tts
import os

# 音色配置 - 使用确认可用的音色
VOICES = {
    # 中文女声
    "zh_female_gentle": {
        "name": "温柔女声",
        "desc": "适合讲故事、客服场景",
        "voice": "zh-CN-XiaoxiaoNeural",
        "text": "你好，很高兴为你服务。今天天气不错，希望你有美好的一天。"
    },
    "zh_female_lively": {
        "name": "活泼女声", 
        "desc": "适合短视频、广告",
        "voice": "zh-CN-XiaoyiNeural",
        "text": "哇！这个真的太棒了！快来一起看看吧，绝对让你惊喜！"
    },
    
    # 中文男声
    "zh_male_calm": {
        "name": "沉稳男声",
        "desc": "适合商务、正式场合",
        "voice": "zh-CN-YunxiNeural",
        "text": "尊敬的各位来宾，欢迎大家参加今天的会议。接下来由我为大家介绍项目进展。"
    },
    "zh_male_young": {
        "name": "年轻男声",
        "desc": "适合游戏、动漫",
        "voice": "zh-CN-YunjianNeural",
        "text": "嘿，兄弟！这波操作太秀了吧！下次带我一起开黑啊！"
    },
    
    # 英文女声
    "en_female_warm": {
        "name": "Warm Female",
        "desc": "Friendly and approachable",
        "voice": "en-US-AriaNeural",
        "text": "Hello! Welcome to our service. I'm here to help you with anything you need."
    },
    "en_female_professional": {
        "name": "Professional Female",
        "desc": "Business and corporate",
        "voice": "en-US-JennyNeural",
        "text": "Good morning everyone. Let's begin with the quarterly financial report."
    },
    
    # 英文男声
    "en_male_friendly": {
        "name": "Friendly Male",
        "desc": "Casual and relaxed",
        "voice": "en-US-GuyNeural",
        "text": "Hey there! Thanks for checking out our app. Let me show you around."
    },
}

async def generate_voice(voice_id: str, config: dict, output_dir: str):
    """生成单个音色样本"""
    output_path = os.path.join(output_dir, f"{voice_id}.wav")
    
    try:
        communicate = edge_tts.Communicate(
            text=config["text"],
            voice=config["voice"],
            rate="+0%",
            volume="+0%"
        )
        
        await communicate.save(output_path)
        print(f"✅ 生成: {config['name']} -> {output_path}")
        return True
    except Exception as e:
        print(f"❌ 失败: {config['name']} - {e}")
        return False

async def main():
    """生成所有预设音色"""
    output_dir = "../assets/voices"
    os.makedirs(output_dir, exist_ok=True)
    
    print("🎙️ 开始生成预设音色参考音频...\n")
    
    success_count = 0
    for voice_id, config in VOICES.items():
        if await generate_voice(voice_id, config, output_dir):
            success_count += 1
        await asyncio.sleep(0.5)  # 避免请求过快
    
    print(f"\n✨ 完成！成功生成 {success_count}/{len(VOICES)} 个音色样本")
    print(f"📁 保存位置: {os.path.abspath(output_dir)}")
    
    # 生成配置文件
    config_path = os.path.join(output_dir, "voice_config.json")
    import json
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(VOICES, f, ensure_ascii=False, indent=2)
    print(f"📝 配置文件: {config_path}")

if __name__ == "__main__":
    asyncio.run(main())