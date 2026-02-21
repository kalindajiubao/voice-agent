#!/bin/bash
# 解决 git 克隆网络问题

cd /root/voice-service
rm -rf fish-speech

# 方法1: 使用 ghproxy 镜像
git clone --depth 1 https://ghproxy.com/https://github.com/fishaudio/fish-speech.git

# 方法2: 如果方法1失败，用 git 协议
# git clone --depth 1 git://github.com/fishaudio/fish-speech.git

# 方法3: 下载 zip
# wget https://ghproxy.com/https://github.com/fishaudio/fish-speech/archive/refs/tags/v1.5.0.zip
# unzip v1.5.0.zip
# mv fish-speech-1.5.0 fish-speech
