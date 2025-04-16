
# AiCore Examples

This directory contains practical examples demonstrating how to use AiCore in different scenarios. Each example showcases specific features and integration patterns.

## Available Examples

### FastAPI Integration
- `fastapi/` - Complete FastAPI application demonstrating:
  - Authentication and authorization
  - Rate limiting middleware
  - Websocket support for streaming responses
  - Production-ready LLM service integration
  - Configuration management

### Chainlit Chat Interface
- `chainlit/` - Interactive chat application featuring:
  - Multiple LLM provider profiles
  - Advanced reasoning capabilities
  - Docker deployment setup
  - Customizable UI components

### Core Functionality
- `observability_dashboard.py` - Launch and interact with the observability dashboard
- `simple_llm_call.py` - Basic synchronous LLM call
- `simple_async_llm_call.py` - Basic asynchronous LLM call
- `reasoning_example.py` - Advanced reasoning capabilities demonstration

## Getting Started

### Prerequisites
1. Install AiCore:
```bash
pip install core-for-ai
```

2. Install example-specific dependencies:
```bash
pip install -r examples/<example_dir>/requirements.txt
```

### Configuration
1. Set up environment variables:
```bash
cp .env-example .env
# Edit .env with your API keys
```

2. Configure provider settings in `config/` directory as needed

### Running Examples
```bash
# For Python scripts
python examples/<script_name>.py

# For FastAPI
uvicorn examples.fastapi.main:app --reload

# For Chainlit
chainlit run examples/chainlit/app/app.py
```

## Example Structure
Each example directory contains:
- `README.md` - Specific instructions for that example
- `requirements.txt` - Python dependencies
- Source code demonstrating best practices

## Contributing
We welcome example contributions! Please:
1. Maintain consistent structure
2. Include proper documentation
3. Add requirements.txt if needed
4. Submit via pull request

For more complex integrations, see our [Built with AiCore](../built-with-aicore.md) showcase.