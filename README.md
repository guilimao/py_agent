# PyAgent

一个使用 Python 构建的命令行 LLM 代理示例。

## 概述

PyAgent 是一个基于 Python 实现的命令行 LLM（大型语言模型）代理。该项目展示了如何构建一个交互式代理，能够处理自然语言命令并执行各种任务。

## 功能

- 交互式命令行界面
- 自然语言处理能力
- 可扩展架构，支持添加新功能

## 使用方法

### 环境准备
1. 安装依赖库（首次运行前执行）：
```bash
pip install openai
```

2. 配置火山引擎 API Key：
   - **Windows**：在命令行执行（临时生效）
     ```bash
     set ARK_API_KEY=your_volcengine_api_key
     ```
     或通过系统环境变量设置（永久生效）：控制面板 -> 系统和安全 -> 系统 -> 高级系统设置 -> 环境变量 -> 用户变量中添加 `ARK_API_KEY` 键值对。
   - **macOS/Linux**：在终端执行（临时生效）
     ```bash
     export ARK_API_KEY=your_volcengine_api_key
     ```
     或添加到 `~/.bashrc` 或 `~/.zshrc` 文件中（永久生效）。

### 启动代理
```bash
python main.py
```

## 路线图

### 初始目标

- [x] 实现多轮对话支持
- [x] 添加流式传输能力

### 工具调用功能

- [x] 文件操作
  - [x] 文件读取
  - [x] 目录列表
  - [x] 文件创建/修改/删除
  - [x] 文件路径权限控制
  - [ ] 大文件的差分修改
  - [ ] ...（更多文件操作）

- [x] 命令行执行

## 致谢

本项目灵感来源于 Thorsten Ball 的 [How to Build an Agent](https://ampcode.com/how-to-build-an-agent)，但使用 Python 重写。

---

[English Version](README_EN.md)