
# Reasoning Example

This example demonstrates how to use AiCore's reasoning augmentation feature, where a secondary LLM (reasoner) helps break down complex problems before the primary LLM generates a response.

## Prerequisites

1. Install AiCore:
```bash
pip install core-for-ai
```

2. Set up your API keys in a configuration file (e.g., `config.yml`):
```yaml
llm:
  provider: "openai"
  api_key: "your_openai_api_key"
  model: "gpt-4o"
  temperature: 0.7
  max_tokens: 1000
  reasoner:
    provider: "groq"
    api_key: "your_groq_api_key"
    model: "deepseek-r1-distill-llama-70b"
```

## Basic Usage

```python
from aicore.llm import Llm
from aicore.llm.config import LlmConfig

# Initialize with reasoner configuration
config = LlmConfig(
    provider="openai",
    api_key="your_openai_api_key",
    model="gpt-4o",
    reasoner=LlmConfig(
        provider="groq",
        api_key="your_groq_api_key",
        model="deepseek-r1-distill-llama-70b"
    )
)

llm = Llm(config=config)

# The main LLM will automatically use the reasoner for complex queries
response = llm.complete("Explain quantum computing to a 5-year-old")
print(response)
```

## How It Works

1. When you make a request, the system first sends the prompt to the reasoner LLM
2. The reasoner generates detailed reasoning steps wrapped in `<think>` tags
3. These steps are then included as context for the main LLM
4. The main LLM uses this reasoning to generate a more informed response

## Customizing Reasoning Behavior

You can customize the reasoning process:

```python
# Change the reasoning stop token
llm.reasoner.provider.use_as_reasoner(
    stop_thinking_token="[STOP_REASONING]"
)

# Access the raw reasoning steps
reasoning_response = llm.reasoner.provider.complete(
    "Break down this math problem: 2+2",
    stream=False
)
print(reasoning_response)
```

## Advanced Example: Problem Solving

```python
# Complex problem solving with reasoning
response = llm.complete(
    "Solve this calculus problem: Find the derivative of f(x) = 3x^2 + 2x - 5",
    system_prompt="You are a math tutor. Explain each step clearly."
)
print(response)
```

## Observing the Reasoning Process

You can observe the intermediate reasoning steps:

```python
# With streaming enabled (default)
response = llm.complete(
    "Explain how neural networks learn",
    stream=True
)

# The output will show:
# 1. The reasoner's thinking process (between <think> tags)
# 2. The main LLM's response
```

## Supported Reasoner Providers

Currently supported reasoner providers:
- Groq
- OpenRouter
- NVIDIA

Supported reasoner models:
- deepseek-r1-distill-llama-70b
- deepseek-ai/deepseek-r1
- deepseek/deepseek-r1:free

## Best Practices

1. Use faster models (like Groq) for the reasoner
2. Keep reasoner responses concise to save tokens
3. Monitor token usage with `llm.usage`
4. For complex problems, increase the main LLM's `max_tokens`
5. Consider adjusting temperatures:
   - Higher for reasoner (0.7-1.0) to encourage diverse thinking
   - Lower for main LLM (0.3-0.7) for more focused responses

## Troubleshooting

If you encounter issues:
1. Verify both main and reasoner API keys are valid
2. Check that the models are available in your region
3. Ensure you have sufficient credits/quotas
4. Monitor token usage to avoid rate limits