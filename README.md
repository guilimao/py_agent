# PyAgent

一个使用 Python 构建的命令行 LLM 代理示例。

## 概述

PyAgent 是一个基于 Python 实现的命令行 LLM（大型语言模型）代理。该项目展示了如何构建一个交互式代理，能够处理自然语言命令并执行各种任务，支持通过命令行参数灵活指定使用的LLM模型。

## 功能

- 交互式命令行界面
- 自然语言处理能力
- 支持视觉模型
- 可扩展架构，支持添加新工具
- 灵活的模型指定：在交互界面中选择不同LLM模型

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

### 环境准备
1. 安装项目（如上所述）

2. 配置API Key：
   - 不同模型需要在环境变量中配置对应提供商的API Key（参照`config/provider_config.json`中的命名格式）

### 启动代理
```bash
pyagent
```

参数说明：
- 输入编号以使用模型（初次使用时，需要跟随指引将API_KEY添加到环境变量）
- 你可以仿照`config/provider_config.json`中的格式，添加自己所需的模型提供商和模型名称

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