# PyAgent

A command line LLM agent example built using Python.

## Overview

PyAgent is a Python implementation of a command-line LLM (Large Language Model) agent. This project demonstrates how to build an interactive agent that can process natural language commands and perform various tasks.

## Features

- Interactive command-line interface
- Natural language processing capabilities
- Extensible architecture for adding new functionalities

## Usage

### Environment Setup
1. Install dependencies (execute before first run):
```bash
pip install openai
```

2. Configure Volcengine API Key:
   - **Windows**: Run in command prompt (temporary effect):
     ```bash
     set ARK_API_KEY=your_volcengine_api_key
     ```
     Or set via system environment variables (permanent effect): Control Panel -> System and Security -> System -> Advanced System Settings -> Environment Variables -> Add `ARK_API_KEY` key-value pair under User Variables.
   - **macOS/Linux**: Run in terminal (temporary effect):
     ```bash
     export ARK_API_KEY=your_volcengine_api_key
     ```
     Or add to `~/.bashrc` or `~/.zshrc` file (permanent effect).

### Start the Agent
```bash
python main.py
```

## Roadmap

### Starting Goals

- [x] Implement multi-turn conversation support
- [x] Add streaming transmission capability

### Tool Calling Features

- [x] File operations
  - [x] File reading
  - [x] Directory listing
  - [x] File creation/modification/deletion
  - [x] File path permission control
  - [ ] Differential modification of large files
  - [ ] ... (additional file operations)

- [x] Command-line execution

## Credits

This project was inspired by [How to Build an Agent](https://ampcode.com/how-to-build-an-agent) by Thorsten Ball, but rewritten in Python.

---

[Chinese Version](README.md)