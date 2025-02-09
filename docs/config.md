# Configuration Management System Documentation

## Overview

The configuration management system is central to setting up and configuring the AI core functionalities. It provides a structured way to define and manage configurations for different components of the AI system, such as LLM (Large Language Models) and embeddings.

## Configuration Classes

### LLM Configuration (`LlmConfig`)

The `LlmConfig` class defines the configuration for Large Language Models. It includes fields for the provider, API key, model, base URL, temperature, max tokens, and an optional reasoner configuration.

```python
from typing import Literal, Optional, Union
from pydantic import BaseModel, field_validator

SUPPORTED_REASONER_PROVIDERS = ["gemini", "groq", "mistral", "nvidia", "openai", "openrouter"]
SUPPORTED_REASONER_MODELS = ["model1", "model2", "model3"]  # Example supported models

class LlmConfig(BaseModel):
    provider: Literal["gemini", "groq", "mistral", "nvidia", "openai", "openrouter"]
    api_key: str
    model: Optional[str] = None
    base_url: Optional[str] = None
    temperature: float = 0
    max_tokens: int = 12000
    reasoner: Union["LlmConfig", None] = None

    @field_validator("temperature")
    @classmethod
    def ensure_temperature_lower_than_unit(cls, temperature: float) -> float:
        assert 0 <= temperature <= 1, "temperature should be between 0 and 1"
        return temperature

    @field_validator("reasoner", mode="after")
    @classmethod
    def ensure_valid_reasoner(cls, reasoner: "LlmConfig") -> "LlmConfig":
        assert reasoner.provider in SUPPORTED_REASONER_PROVIDERS, f"{reasoner.provider} is not supported as a reasoner provider. Supported providers are {SUPPORTED_REASONER_PROVIDERS}"
        assert reasoner.model in SUPPORTED_REASONER_MODELS, f"{reasoner.model} is not supported as a reasoner model. Supported models are {SUPPORTED_REASONER_MODELS}"
        return reasoner
```

### Embeddings Configuration (`EmbeddingsConfig`)

The `EmbeddingsConfig` class defines the configuration for embeddings. It includes fields for the provider, API key, model, and base URL.

```python
class EmbeddingsConfig(BaseModel):
    provider: Literal["gemini", "groq", "mistral", "nvidia", "openai"]
    api_key: str
    model: Optional[str] = None
    base_url: Optional[str] = None
```

### Main Configuration (`Config`)

The `Config` class is the central configuration class that includes instances of `EmbeddingsConfig` and `LlmConfig`. It also provides a method to load the configuration from a YAML file.

```python
import os
from pathlib import Path
import yaml

DEFAULT_CONFIG_PATH = "path/to/default/config.yaml"

class Config(BaseModel):
    embeddings: EmbeddingsConfig = None
    llm: LlmConfig = None

    @classmethod
    def from_yaml(cls, config_path: Optional[Union[str, Path]] = None) -> "Config":
        if config_path is None:
            config_path = os.getenv("CONFIG_PATH") or DEFAULT_CONFIG_PATH
        config_path = Path(config_path)

        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Configuration file not found: {config_path}. Please ensure the file exists and the path is correct.")

        with open(config_path, "r") as _file:
            yaml_config = yaml.safe_load(_file)

        return cls(**yaml_config)
```

## Retry Logic for Rate-Limited Operations

The retry logic is handled by a custom decorator that retries API calls only on 429 rate-limit errors. This ensures that the system can handle API rate limits gracefully.

```python
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception
from functools import wraps

def retry_on_rate_limit(func):
    """Custom decorator for retrying API calls only on 429 rate-limit errors."""
    @retry(
        stop=stop_after_attempt(5),  # Retry up to 5 times
        wait=wait_exponential(multiplier=1, min=1, max=60),  # Exponential backoff
        retry=retry_if_exception(is_rate_limited),  # Retry only for 429 errors
        before_sleep=wait_for_retry  # Handle 429 Retry-After dynamically
    )
    @wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)
    return wrapper
```

## Integration Considerations

The configuration management system is designed to integrate seamlessly with other components of the AI system. The use of Pydantic's BaseModel ensures that the configuration data is validated and serialized efficiently. The retry logic for rate-limited operations ensures that the system can handle API rate limits gracefully.

## Error Handling

The system includes robust error handling for file not found scenarios and invalid configuration values. This ensures that users receive clear and actionable error messages.

```