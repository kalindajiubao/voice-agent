#!/usr/bin/env python3
"""
重新生成失败的音色样本
"""
import asyncio
import edge_tts
import os

# 需要重新生成的音色
VOICES_TO_REGEN = {
    "zh_female_mature": {
        "name": "成熟女声",
        "desc": "适合新闻播报、纪录片",
        "voice": "zh-CN-XiaoxiaoNeural",  # 使用xiaoxiao但调整语速
        "text": "各位观众晚上好，欢迎收看今天的新闻联播。",
        "rate": "-10%"  # 慢一点显得成熟
    },
    "zh_male_deep": {
        "name": "磁性男声",
        "desc": "适合有声书、深夜电台",
        "voice": "zh-CN-YunxiNeural",
        "text": "在这个宁静的夜晚，让我为你讲述一个关于远方的故事。",
        "rate": "-15%"
    },
    "en_male_authoritative": {
        "name": "Authoritative Male",
        "desc": "News and documentaries",
        "voice": "en-US-GuyNeural",
        "text": "In breaking news today, scientists have made a remarkable discovery.",
        "rate": "-10%"
    }
}

async def generate_voice(voice_id: str, config: dict, output_dir: str):
    """生成单个音色样本"""
    output_path = os.path.join(output_dir, f"{voice_id}.wav")
    
    try:
        communicate = edge_tts.Communicate(
            text=config["text"],
            voice=config["voice"],
            rate=config.get("rate", "+0%"),
            volume="+0%"
        )
        
        await communicate.save(output_path)
        size = os.path.getsize(output_path)
        if size > 0:
            print(f"✅ 生成: {config['name']} ({size} bytes)")
            return True
        else:
            print(f"❌ 失败: {config['name']} - 文件为空")
            return False
    except Exception as e:
        print(f"❌ 失败: {config['name']} - {e}")
        return False

async def main():
    output_dir = "../assets/voices"
    os.makedirs(output_dir, exist_ok=True)
    
    print("🎙️ 重新生成失败的音色样本...\n")
    
    success_count = 0
    for voice_id, config in VOICES_TO_REGEN.items():
        if await generate_voice(voice_id, config, output_dir):
            success_count += 1
        await asyncio.sleep(0.5)
    
    print(f"\n✨ 完成！成功生成 {success_count}/{len(VOICES_TO_REGEN)} 个音色")

if __name__ == "__main__":
    asyncio.run(main())