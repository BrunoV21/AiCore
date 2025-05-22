
# AiCore Project
[![GitHub Stars](https://img.shields.io/github/stars/BrunoV21/AiCore?style=social)](https://github.com/BrunoV21/AiCore/stargazers)
[![Docs](https://img.shields.io/badge/docs-AiCore.github.io-red)](https://brunov21.github.io/AiCore/)
[![PyPI Downloads](https://static.pepy.tech/badge/core-for-ai)](https://pepy.tech/projects/core-for-ai)
![PyPI - Python Version](https://img.shields.io/pypi/pyversions/core-for-ai?style=flat)
![PyPI - Version](https://img.shields.io/pypi/v/core-for-ai?style=flat)
[![Pydantic v2](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/pydantic/pydantic/main/docs/badge/v2.json)](https://pydantic.dev)

✨ **AiCore** is a comprehensive framework for integrating various language models and embedding providers with a unified interface. It supports both synchronous and asynchronous operations for generating text completions and embeddings, featuring:  

🔌 **Multi-provider support**: OpenAI, Mistral, Groq, Gemini, NVIDIA, and more  
🤖 **Reasoning augmentation**: Enhance traditional LLMs with reasoning capabilities  
📊 **Observability**: Built-in monitoring and analytics  
💰 **Token tracking**: Detailed usage metrics and cost tracking  
⚡ **Flexible deployment**: Chainlit, FastAPI, and standalone script support  
🛠️ **MCP Integration**: Connect to Model Control Protocol servers via tool calling

## Quickstart
```bash
pip install git+https://github.com/BrunoV21/AiCore
```

or

```bash
pip install git+https://github.com/BrunoV21/AiCore.git#egg=core-for-ai[all]
```

or

```bash
pip install core-for-ai[all]
```

### Make your First Request

#### Sync
```python
from aicore.llm import Llm
from aicore.llm.config import LlmConfig
import os

llm_config = LlmConfig(
  provider="openai",
  model="gpt-4o",
  api_key="super_secret_openai_key"
)

llm = Llm.from_config(llm_config)

# Generate completion
response = llm.complete("Hello, how are you?")
print(response)
```

#### Async
```python
from aicore.llm import Llm
from aicore.llm.config import LlmConfig
import os

async def main():
  llm_config = LlmConfig(
    provider="openai",
    model="gpt-4o",
    api_key="super_secret_openai_key"
  )

  llm = Llm.from_config(llm_config)

  # Generate completion
  response = await llm.acomplete("Hello, how are you?")
  print(response)

if __name__ == "__main__":
  asyncio.run(main())
```

more examples available at [examples/](https://github.com/BrunoV21/AiCore/tree/main/examples) and [docs/exampes/](https://brunov21.github.io/AiCore/examples/)

## Key Features

### Multi-provider Support
**LLM Providers:**
- Anthropic
- OpenAI
- Mistral
- Groq
- Gemini
- NVIDIA
- OpenRouter
- DeepSeek

**Embedding Providers:**
- OpenAI
- Mistral
- Groq
- Gemini
- NVIDIA

**Observability Tools:**
- Operation tracking and metrics collection
- Interactive dashboard for visualization
- Token usage and latency monitoring
- Cost tracking

**MCP Integration:**
- Connect to multiple MCP servers simultaneously
- Automatic tool discovery and calling
- Support for WebSocket, SSE, and stdio transports

To configure the application for testing, you need to set up a `config.yml` file with the necessary API keys and model names for each provider you intend to use. The `CONFIG_PATH` environment variable should point to the location of this file. Here's an example of how to set up the `config.yml` file:

```yaml
# config.yml
embeddings:
  provider: "openai" # or "mistral", "groq", "gemini", "nvidia"
  api_key: "your_openai_api_key"
  model: "text-embedding-3-small" # Optional

llm:
  provider: "openai" # or "mistral", "groq", "gemini", "nvidia"
  api_key: "your_openai_api_key"
  model: "gpt-o4" # Optional
  temperature: 0.1
  max_tokens: 1028
  reasonning_effort: "high"
  mcp_config_path: "./mcp_config.json" # Path to MCP configuration
  max_tool_calls_per_response: 3 # Optional limit on tool calls
```
config examples for the multiple providers are included in the [config dir](https://github.com/BrunoV21/AiCore/tree/main/config)

## MCP Integration Example

```python
from aicore.llm import Llm
from aicore.config import Config
import asyncio

async def main():
    # Load configuration with MCP settings
    config = Config.from_yaml("./config/config_example_mcp.yml")
    
    # Initialize LLM with MCP capabilities
    llm = Llm.from_config(config.llm)
    
    # Make async request that can use MCP-connected tools
    response = await llm.acomplete(
        "Search for latest news about AI advancements",
        system_prompt="Use available tools to gather information"
    )
    print(response)

asyncio.run(main())
```

Example MCP configuration (`mcp_config.json`):
```json
{
  "mcpServers": {
    "search-server": {
      "transport_type": "ws",
      "url": "ws://localhost:8080",
      "description": "WebSocket server for search functionality"
    },
    "data-server": {
      "transport_type": "stdio",
      "command": "python",
      "args": ["data_server.py"],
      "description": "Local data processing server"
    },
    "brave-search": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-brave-search"
      ],
      "env": {
        "BRAVE_API_KEY": "SUPER-SECRET-BRAVE-SEARCH-API-KEY"
      }
    }
  }
}
```

## Usage

### Language Models

You can use the language models to generate text completions. Below is an example of how to use the `MistralLlm` provider:

```python
from aicore.llm.config import LlmConfig
from aicore.llm.providers import MistralLlm

config = LlmConfig(
    api_key="your_api_key",
    model="your_model_name",
    temperature=0.7,
    max_tokens=100
)

mistral_llm = MistralLlm.from_config(config)
response = mistral_llm.complete(prompt="Hello, how are you?")
print(response)
```

### Loading from a Config File

To load configurations from a YAML file, set the `CONFIG_PATH` environment variable and use the `Config` class to load the configurations. Here is an example:

```python
from aicore.config import Config
from aicore.llm import Llm
import os

if __name__ == "__main__":
    os.environ["CONFIG_PATH"] = "./config/config.yml"
    config = Config.from_yaml()
    llm = Llm.from_config(config.llm)
    llm.complete("Once upon a time, there was a")
```

Make sure your `config.yml` file is properly set up with the necessary configurations.

## Observability

AiCore includes a comprehensive observability module that tracks:

- **Request/response metadata**
- **Token usage** (prompt, completion, total)
- **Latency metrics** (response time, time-to-first-token)
- **Cost estimates** (based on provider pricing)
- **Tool call statistics** (for MCP integrations)

### Dashboard Features
![Observability Dashboard](https://brunov21.github.io/AiCore/assets/dashboard-overview.Ch5Sfrrh.png)

Key metrics tracked:
- Requests per minute
- Average response time
- Token usage trends
- Error rates
- Cost projections

```python
from aicore.observability import ObservabilityDashboard

dashboard = ObservabilityDashboard(storage="observability_data.json")
dashboard.run_server(port=8050)
```

## Advanced Usage

**Reasoner Augmented Config**

AiCore also contains native support to augment *traditional* Llms with *reasoning* capabilities by providing them with the thinking steps generated by an open-source reasoning capable model, allowing it to generate its answers in a Reasoning Augmented way. 

This can be usefull in multiple scenarios, such as:
- ensure your agentic systems still work with the propmts you have crafted for your favourite llms while augmenting them with reasoning steps
- direct control for how long you want your reasoner to reason (via max_tokens param) and how creative it can be (reasoning temperature decoupled from generation temperature) without compromising generation settings

To leverage the reasoning augmentation just introduce one of the supported llm configs into the reasoner field and AiCore handles the rest

```yaml
# config.yml
embeddings:
  provider: "openai" # or "mistral", "groq", "gemini", "nvidia"
  api_key: "your_openai_api_key"
  model: "your_openai_embedding_model" # Optional

llm:
  provider: "mistral" # or "openai", "groq", "gemini", "nvidia"
  api_key: "your_mistral_api_key"
  model: "mistral-small-latest" # Optional
  temperature: 0.6
  max_tokens: 2048
  reasoner:
    provider: "groq" # or openrouter or nvidia
    api_key: "your_groq_api_key"
    model: "deepseek-r1-distill-llama-70b" # or "deepseek/deepseek-r1:free" or "deepseek/deepseek-r1"
    temperature: 0.5
    max_tokens: 1024
```

## [Built with AiCore](https://brunov21.github.io/AiCore/built-with-aicore.html)
### Reasoner4All
A Hugging Face Space showcasing reasoning-augmented models  
[![Hugging Face Space](https://huggingface.co/datasets/huggingface/badges/raw/main/open-in-hf-spaces-xl.svg)](https://huggingface.co/spaces/McLoviniTtt/Reasoner4All)

### GitRecap
Instant summaries of Git activity  
🌐 [Live App](https://brunov21.github.io/GitRecap/)  
📦 [GitHub Repository](https://github.com/BrunoV21/GitRecap)

### CodeGraph (Coming Soon)
Graph representation of codebases for enhanced retrieval


## Future Plans
- **Extended Provider Support**: Additional LLM and embedding providers
- **Add support for Speech**: Integrate text2speech and speech to text objects with usage and observability4
  
## Documentation

For complete documentation, including API references, advanced usage examples, and configuration guides, visit:

📖 [Official Documentation Site](https://brunov21.github.io/AiCore/)

## License

This project is licensed under the Apache 2.0 License.