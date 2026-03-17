# PyAgent

A command-line LLM agent built with Python.

## Features

- Interactive command-line interface
- Natural language processing capabilities
- Vision model support
- Extensible architecture for easy addition of new features

## Installation

### Install via uv
```bash
uv sync
uv tool install -e .
```

## Usage

### Environment Configuration

1. Add the executable directory to environment variables

For Windows, create a new entry in PATH:
```path
%LOCALAPPDATA%\uv\tools\bin
```

For Linux, add the following command to the end of your shell configuration file (~/.bashrc or ~/.zshrc), then restart your terminal:
```bash
export PATH="$HOME/.local/bin:$PATH"
```

After that, you can launch it from any path using:

```bash
pyagent
```

2. Configure API Keys:
   - Different models require corresponding provider API keys to be configured in environment variables (refer to the naming format in `config/provider_config.json`)

```bash
export OPENROUTER_API_KEY="sk-......"
```

## Acknowledgments

This project is inspired by Thorsten Ball's [How to Build an Agent](https://ampcode.com/how-to-build-an-agent) and rewritten in Python.

Utilizes Stefano Baccianella's [Json Repair](https://github.com/mangiucugna/json_repair) project.
