# PyAgent

一个使用 Python 构建的命令行 LLM 代理示例。

## 概述

PyAgent 是一个基于 Python 实现的命令行 LLM（大型语言模型）代理。该项目展示了如何构建一个交互式代理，能够处理自然语言命令并执行各种任务，支持通过命令行参数灵活指定使用的LLM模型。

## 功能

- 交互式命令行界面
- 自然语言处理能力
- 支持视觉模型
- 可扩展架构，支持添加新功能
- 灵活的模型指定：通过命令行参数选择不同LLM模型（支持火山引擎、深度求索等多提供商）

## 使用方法

### 环境准备
1. 安装依赖库（首次运行前执行）：
```bash
pip install -r requirements.txt
```

2. 配置API Key：
   - 不同模型需要在环境变量中配置对应提供商的API Key（参照`config/provider_config.json`中的命名格式）

### 启动代理
```bash
python main.py [--model 模型名称]
```

参数说明：
- `--model`（可选）：指定使用的LLM模型名称
- 具体可用模型需与`config/provider_config.json`中配置的提供商支持模型列表匹配
- 你可以仿照`config/provider_config.json`中的格式，添加自己所需的模型提供商和模型名称

示例：
```bash
# 使用默认模型（火山引擎doubao-1-5-thinking-pro-250415）
python main.py

# 指定使用火山引擎的deepseek-r1-250120模型
python main.py --model deepseek-r1-250120

# 指定使用深度求索的deepseek-chat模型
python main.py --model deepseek-chat
```

## 路线图

### 里程碑

- [x] 实现多轮对话支持
- [x] 添加流式传输能力
- [x] 支持工具调用
- [x] 通过命令行指定模型
- [x] 支持视觉模型

### 工具调用功能

- [x] 文件操作
  - [x] 文件读取
  - [x] 目录列表
  - [x] 文件创建/修改/删除
  - [x] 文件路径权限控制
  - [x] 大文件的差分修改
  - [ ] ...（更多文件操作）

## 致谢

本项目灵感来源于 Thorsten Ball 的 [How to Build an Agent](https://ampcode.com/how-to-build-an-agent)，但使用 Python 重写。

使用了 Stefano Baccianella 的 [Json Repair](https://github.com/mangiucugna/json_repair) 项目

---

[English Version](README_EN.md)