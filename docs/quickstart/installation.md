
# Installation Guide

## Prerequisites

- Python 3.11 or later
- pip package manager
- Valid API key(s) for your chosen LLM provider(s)

## Installation Options

### Recommended: Install from PyPI

```bash
pip install core-for-ai
```

### Install from Source (Development Version)

```bash
pip install git+https://github.com/BrunoV21/AiCore@main
```

## Optional Features

AiCore supports additional functionality through optional dependencies:

```bash
# Observability dashboard (requires Node.js for frontend)
pip install "core-for-ai[dashboard]"

# SQL database integration
pip install "core-for-ai[sql]"

# All optional features
pip install "core-for-ai[all]"
```

## Configuration Setup

1. **Environment Variables**:
   - Copy `.env-example` to `.env` in your project root
   - Fill in your API keys for the providers you plan to use

2. **LLM Configuration**:
   - Copy example config files from `config/` directory
   - Set `CONFIG_PATH` environment variable to point to your config file
   - Or use environment variables prefixed with `LLM_` (e.g., `LLM_PROVIDER`, `LLM_API_KEY`)

## Verification

After installation, verify the package is working:

```python
import aicore
print(aicore.__version__)
```

## Troubleshooting

- **Permission Errors**: Use `pip install --user` or a virtual environment
- **Missing Dependencies**: Run `pip install -r requirements.txt` from the source directory
- **API Connection Issues**: Verify your API keys and network connectivity

## Next Steps

- [Make your first request](first-request.md)
- [Configure your LLM provider](../config/llmconfig.md)
- [Explore available providers](../providers/)