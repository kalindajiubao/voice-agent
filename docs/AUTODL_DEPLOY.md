# AutoDL 部署指南

## 快速开始

### 1. 创建 AutoDL 实例

1. 登录 [AutoDL](https://www.autodl.com)
2. 选择地区（推荐北京/上海）
3. 选择 GPU：**RTX 3090** 或 **RTX 4090**（24GB显存）
4. 镜像选择：**PyTorch 2.x + CUDA 12.x**
5. 点击「立即创建」

### 2. 上传部署脚本

```bash
# 在本地终端，将脚本上传到 AutoDL
scp deploy_autodl.sh root@你的autodl-ip:/root/
```

或者直接在 JupyterLab 中新建文件，复制脚本内容。

### 3. 运行部署脚本

```bash
# SSH 进入实例
ssh root@你的autodl-ip

# 运行部署脚本
cd /root
bash deploy_autodl.sh
```

部署过程约 5-10 分钟，会自动：
- ✅ 安装系统依赖
- ✅ 下载 Fish Speech
- ✅ 安装 Python 包
- ✅ 下载模型文件
- ✅ 创建启动脚本

### 4. 启动服务

```bash
cd /root/voice-service/fish-speech
bash start_service.sh
```

看到以下输出表示成功：
```
启动 Fish Speech 服务...
服务地址: http://0.0.0.0:7860
```

### 5. 开放端口

1. 返回 AutoDL 控制台
2. 点击「更多」→「端口开放」
3. 添加端口：`7860`
4. 复制对外地址：`http://xxx.autodl.top:xxxxx`

### 6. 测试服务

```bash
# 在实例中测试
python test_api.py
```

### 7. 配置后端

在你的后端代码中设置环境变量：

```bash
export AUTODL_BASE_URL="http://xxx.autodl.top:xxxxx"  # 你的对外地址
export KIMI_API_KEY="your-moonshot-api-key"
```

## 常见问题

### Q: 模型下载失败
```bash
# 手动下载模型
cd /root/voice-service/fish-speech
source venv/bin/activate

pip install huggingface_hub
python -c "
from huggingface_hub import snapshot_download
snapshot_download('fishaudio/fish-speech-1.5', local_dir='checkpoints/fish-speech-1.5')
"
```

### Q: 显存不足
- 确保使用 24GB 显存的实例（3090/4090）
- 或修改启动参数降低 batch size

### Q: 服务启动慢
- 首次启动需要加载模型，正常
- 后续启动会快很多

### Q: 端口无法访问
- 检查 AutoDL 控制台是否开放了端口
- 检查防火墙设置

## 文件说明

```
/root/voice-service/fish-speech/
├── venv/                   # Python 虚拟环境
├── checkpoints/            # 模型文件
│   └── fish-speech-1.5/
├── start_service.sh        # 启动脚本
├── test_api.py            # 测试脚本
└── voice-tts.service      # systemd 服务文件
```

## 常用命令

```bash
# 启动服务
bash start_service.sh

# 测试服务
python test_api.py

# 查看日志
tail -f /root/voice-service/fish-speech/webui.log

# 重启服务
pkill -f fish_speech
bash start_service.sh
```

## 联系支持

遇到问题？检查：
1. GPU 是否正常：`nvidia-smi`
2. 服务是否运行：`curl http://localhost:7860`
3. 端口是否开放：AutoDL 控制台
