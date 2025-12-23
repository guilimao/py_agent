PyAgent

一个使用 Python 构建的命令行 LLM 智能体示例。

## 概述

PyAgent 是一个用 Python 实现的命令行 LLM（大语言模型）智能体。本项目演示了如何构建一个能够处理自然语言命令并执行各种任务的交互式智能体，支持通过命令行参数灵活指定 LLM 模型。

## 功能特性

- 交互式命令行界面
- 自然语言处理能力
- 视觉模型支持
- 可扩展的架构，便于添加新功能
- 灵活的模型指定：通过命令行参数选择不同的 LLM 模型（支持火山引擎、DeepSeek 等多个提供商）

## 安装

### 通过 pip 安装（推荐）
```bash
pip install .
```

### 开发模式安装
```bash
pip install -e .
```

## 使用方法

### 环境配置
1. 安装项目（如上所述）

2. 配置 API 密钥：
   - 不同的模型需要将相应提供商的 API 密钥配置在环境变量中（参考 `config/provider_config.json` 中的命名格式）

### 启动智能体
```bash
pyagent [--model model_name]
```

参数说明：
- `--model`（可选）：指定要使用的 LLM 模型名称
- 可用模型必须与 `config/provider_config.json` 中配置的提供商支持的模型列表相匹配
- 您可以按照 `config/provider_config.json` 中的格式添加您想要的模型提供商和模型名称


## 路线图

### 里程碑

- [x] 多轮对话支持
- [x] 流式输出能力
- [x] 工具调用支持
- [x] 通过命令行指定模型
- [x] 视觉模型支持

### 工具调用功能

- [x] 文件操作
  - [x] 文件读取
  - [x] 目录列表
  - [x] 文件创建/修改/删除
  - [x] 文件路径权限控制
  - [x] 大文件的差异化修改
  - [ ] ...（更多文件操作）

## 致谢

本项目受到 Thorsten Ball 的 [如何构建智能体](https://ampcode.com/how-to-build-an-agent) 的启发，并使用 Python 重写。

使用了 Stefano Baccianella 的 [Json Repair](https://github.com/mangiucugna/json_repair) 项目。