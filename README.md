PyAgent

一个使用 Python 构建的命令行 LLM 智能体。

## 功能特性

- 交互式命令行界面
- 自然语言处理能力
- 视觉模型支持
- 可扩展的架构，便于添加新功能

## 安装

### 通过 uv 安装
```bash
uv sync
uv tool install -e .
```

## 使用方法

### 环境配置

1. 将可执行文件目录添加到环境变量

对于Windows系统，在path中新建一条：
```path
%LOCALAPPDATA%\uv\tools\bin
```

对于Linux系统，将以下命令添加到Shell配置文件末尾（~/.bashrc 或 ~/.zshrc），然后重启终端
```bash
export PATH="$HOME/.local/bin:$PATH"
```

随后可以在任意路径下使用该命令启动它：

```bash
pyagent
```

2. 配置 API 密钥：
   - 不同的模型需要将相应提供商的 API 密钥配置在环境变量中（参考 `config/provider_config.json` 中的命名格式）

```bash
export OPENROUTER_API_KEY="sk-......"
```

## 致谢

本项目受到 Thorsten Ball 的 [如何构建智能体](https://ampcode.com/how-to-build-an-agent) 的启发，并使用 Python 重写。

使用了 Stefano Baccianella 的 [Json Repair](https://github.com/mangiucugna/json_repair) 项目。