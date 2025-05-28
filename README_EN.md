PyAgent

A command-line LLM agent example built with Python.

## Overview

PyAgent is a Python-based command-line LLM (Large Language Model) agent. This project demonstrates how to build an interactive agent capable of processing natural language commands and executing various tasks, with flexible LLM model specification through command-line arguments.

## Features

- Interactive command-line interface
- Natural language processing capabilities
- Scalable architecture for adding new features
- Flexible model specification: Select different LLM models via command-line arguments (supports multiple providers such as Volcano Engine and DeepSeek)

## Usage

### Environment Preparation
1. Install dependencies (execute before first run):
```bash
pip install openai
```

2. Configure API Key:
   - Different models require configuring the corresponding provider's API Key in environment variables (e.g., configure `ARK_API_KEY` for Volcano Engine models, `DEEPSEEK_API_KEY` for DeepSeek models)
   - **Windows**: Execute in command line (temporary effect)
     ```bash
     set CORRESPONDING_API_KEY_ENV_VAR_NAME=your_api_key
     ```
     Or set via system environment variables (permanent effect): Control Panel -> System and Security -> System -> Advanced System Settings -> Environment Variables -> Add the corresponding key-value pair in user variables.
   - **macOS/Linux**: Execute in terminal (temporary effect)
     ```bash
     export CORRESPONDING_API_KEY_ENV_VAR_NAME=your_api_key
     ```
     Or add to `~/.bashrc` or `~/.zshrc` file (permanent effect).

### Start the Agent
```bash
python main.py [--model MODEL_NAME]
```

Parameter Description:
- `--model` (optional): Specify the LLM model name to use, default is `doubao-1-5-thinking-pro-250415` (Volcano Engine model)
- Example supported models:
  - Volcano Engine: `doubao-1-5-thinking-pro-250415`, `deepseek-r1-250120`, `deepseek-v3-250324`
  - DeepSeek: `deepseek-chat`, `deepseek-reasoner`
- Specific available models must match the provider-supported model list configured in `config/provider_config.json`

Example:
```bash
# Use default model (Volcano Engine doubao-1-5-thinking-pro-250415)
python main.py

# Specify Volcano Engine's deepseek-r1-250120 model
python main.py --model deepseek-r1-250120

# Specify DeepSeek's deepseek-chat model
python main.py --model deepseek-chat
```

## Roadmap

### Milestones

- [x] Implement multi-turn conversation support
- [x] Add streaming capability
- [x] Support tool invocation
- [x] Model specification via command line

### Tool Invocation Features

- [x] File operations
  - [x] File reading
  - [x] Directory listing
  - [x] File creation/modification/deletion
  - [x] File path permission control
  - [ ] Differential modification of large files
  - [ ] ... (more file operations)

- [x] Command line execution

## Acknowledgments

This project is inspired by Thorsten Ball's [How to Build an Agent](https://ampcode.com/how-to-build-an-agent), but rewritten in Python.

---

[English Version](README_EN.md)