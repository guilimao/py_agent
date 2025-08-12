# PyAgent

A command-line LLM agent example built with Python.

## Overview

PyAgent is a command-line LLM (Large Language Model) agent implemented in Python. This project demonstrates how to build an interactive agent capable of processing natural language commands and executing various tasks, with flexible support for specifying LLM models via command-line arguments.

## Features

- Interactive command-line interface
- Natural language processing capabilities
- Vision model support
- Extensible architecture for adding new features
- Flexible model specification: choose different LLM models via command-line arguments (supports multiple providers like Volcano Engine, DeepSeek, etc.)

## Installation

### Install via pip (Recommended)
```bash
pip install .
```

### Development Mode Installation
```bash
pip install -e .
```

## Usage

### Environment Setup
1. Install the project (as described above)

2. Configure API Keys:
   - Different models require corresponding provider API keys to be configured in environment variables (refer to the naming format in `config/provider_config.json`)

### Launch the Agent
```bash
pyagent [--model model_name]
```

Parameter Description:
- `--model` (optional): Specify the LLM model name to use
- Available models must match the provider-supported model list configured in `config/provider_config.json`
- You can add your desired model providers and model names by following the format in `config/provider_config.json`

Examples:
```bash
# Use default model (Volcano Engine doubao-1-5-thinking-pro-250415)
pyagent

# Specify Volcano Engine's deepseek-r1-250120 model
pyagent --model deepseek-r1-250120

# Specify DeepSeek's deepseek-chat model
pyagent --model deepseek-chat
```

## Roadmap

### Milestones

- [x] Multi-turn conversation support
- [x] Streaming capability
- [x] Tool calling support
- [x] Model specification via command line
- [x] Vision model support

### Tool Calling Features

- [x] File operations
  - [x] File reading
  - [x] Directory listing
  - [x] File creation/modification/deletion
  - [x] File path permission control
  - [x] Differential modification of large files
  - [ ] ... (more file operations)

## Acknowledgments

This project is inspired by Thorsten Ball's [How to Build an Agent](https://ampcode.com/how-to-build-an-agent), rewritten in Python.

Uses Stefano Baccianella's [Json Repair](https://github.com/mangiucugna/json_repair) project