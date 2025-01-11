# AiCore Project

This project provides a framework for integrating various language models and embedding providers. It supports both synchronous and asynchronous operations for generating text completions and embeddings. The current implementation includes support for OpenAI, Mistral and Groq providers.

## Installation

To install the required dependencies, run:
```bash
pip install -r requirements.txt
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

### Embeddings

You can use the embeddings module to generate text embeddings. Below is an example of how to use the `OpenAiEmbeddings` provider:

```python
from aicore.embeddings.config import EmbeddingsConfig
from aicore.embeddings import Embeddings

config = EmbeddingsConfig(
    provider="openai",
    api_key="your_api_key",
    model="your_model_name"
)

embeddings = Embeddings.from_config(config)
vectors = embeddings.generate(["Hello, how are you?"])
print(vectors)
```

For asynchronous usage:

```python
import asyncio
from aicore.embeddings.config import EmbeddingsConfig
from aicore.embeddings import Embeddings

async def main():
    config = EmbeddingsConfig(
        provider="openai",
        api_key="your_api_key",
        model="your_model_name"
    )

    embeddings = Embeddings.from_config(config)
    vectors = await embeddings.agenerate(["Hello, how are you?"])
    print(vectors)

asyncio.run(main())
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

**Disclaimer**: the following diagrams and explanations were Ai Generated

## Class Diagram

The class diagram for this project will focus on the core components and their relationships, highlighting the configuration, embedding, and LLM modules. The key classes include `Config`, `EmbeddingsConfig`, `LlmConfig`, `Embeddings`, `Llm`, and various provider classes (`BaseProvider`, `GroqEmbeddings`, `MistralEmbeddings`, `OpenAiEmbeddings`, `GroqLlm`, `MistralLlm`, `OpenAiLlm`). These classes are interconnected through inheritance, composition, and dependencies, forming the backbone of the system's architecture.

1. **Configuration Classes**:
   - `Config`: Central configuration class that manages application settings, including embeddings and LLM configurations.
   - `EmbeddingsConfig`: Configures embedding providers with details like API key, model, and base URL.
   - `LlmConfig`: Configures LLM providers with details like API key, model, base URL, temperature, and max tokens.

2. **Embeddings Module**:
   - `Embeddings`: Manages embedding generation using configured providers.
   - `Providers` (Enum): Enumeration for instantiating embedding provider classes.
   - `BaseProvider`: Base class for embedding providers, defining common properties and methods.
   - `GroqEmbeddings`, `MistralEmbeddings`, `OpenAiEmbeddings`: Specific implementations of `BaseProvider` for different embedding providers.

3. **LLM Module**:
   - `Llm`: Manages configuration and interaction with various LLM providers.
   - `Providers` (Enum): Enumeration for instantiating LLM provider classes.
   - `BaseProvider`: Base class for LLM providers, defining common methods for configuration, completion, and normalization.
   - `GroqLlm`, `MistralLlm`, `OpenAiLlm`: Specific implementations of `BaseProvider` for different LLM providers.

```mermaid
classDiagram
    %% Configuration Classes
    config.Config "1" --> "1" embeddings.config.EmbeddingsConfig : embeddings
    config.Config "1" --> "1" llm.config.LlmConfig : llm

    class config.Config {
        +EmbeddingsConfig embeddings
        +LlmConfig llm
        +from_yaml(config_path: Optional[Union[str, Path]]) : Config
    }

    class embeddings.config.EmbeddingsConfig {
        +Literal["groq", "mistral", "openai"] provider
        +str api_key
        +Optional[str] model
        +Optional[str] base_url
    }

    class llm.config.LlmConfig {
        +Literal["groq", "mistral", "openai"] provider
        +str api_key
        +Optional[str] model
        +Optional[str] base_url
        +float temperature
        +int max_tokens
        +field_validator(temperature: float) : float
    }

    %% Embeddings Module
    embeddings.embeddings.Embeddings "1" --> "1" embeddings.config.EmbeddingsConfig : config
    embeddings.embeddings.Embeddings "1" --> "1" embeddings.providers.base_provider.BaseProvider : _provider
    embeddings.embeddings.Providers ..|> embeddings.providers.base_provider.BaseProvider : get_instance

    class embeddings.embeddings.Embeddings {
        +EmbeddingsConfig config
        +BaseProvider _provider
        +provider() : BaseProvider
        +provider(provider: BaseProvider) : void
        +vector_dimensions() : int
        +start_provider() : Self
        +from_config(config: EmbeddingsConfig) : Embeddings
        +generate(text_batches: List[str]) : void
        +agenerate(text_batches: List[str]) : void
    }

    class embeddings.embeddings.Providers {
        <<enumeration>>
        OPENAI
        MISTRAL
        GROQ
        +get_instance(config: EmbeddingsConfig) : BaseProvider
    }

    embeddings.providers.base_provider.BaseProvider <|-- embeddings.providers.groq.GroqEmbeddings
    embeddings.providers.base_provider.BaseProvider <|-- embeddings.providers.mistral.MistralEmbeddings
    embeddings.providers.base_provider.BaseProvider <|-- embeddings.providers.openai.OpenAiEmbeddings

    class embeddings.providers.base_provider.BaseProvider {
        +EmbeddingsConfig config
        +int vector_dimensions
        +Any _client
        +Any _aclient
        +from_config(config: EmbeddingsConfig) : BaseProvider
        +client() : Any
        +client(client: Any) : void
        +aclient() : Any
        +aclient(aclient: Any) : void
        +generate() : void
        +agenerate() : void
    }

    class embeddings.providers.groq.GroqEmbeddings {
        +int vector_dimensions = 1024
        +set_groq() : Self
        +generate(text_batches: List[str]) : CreateEmbeddingResponse
        +agenerate(text_batches: List[str]) : CreateEmbeddingResponse
    }

    class embeddings.providers.mistral.MistralEmbeddings {
        +int vector_dimensions = 1024
        +set_mistral() : Self
        +generate(text_batches: List[str]) : EmbeddingResponse
        +agenerate(text_batches: List[str]) : EmbeddingResponse
    }

    class embeddings.providers.openai.OpenAiEmbeddings {
        +int vector_dimensions = 1536
        +set_openai() : Self
        +generate(text_batches: List[str]) : CreateEmbeddingResponse
        +agenerate(text_batches: List[str]) : CreateEmbeddingResponse
    }

    %% LLM Module
    llm.llm.Llm "1" --> "1" llm.config.LlmConfig : config
    llm.llm.Llm "1" --> "1" llm.providers.base_provider.BaseProvider : _provider
    llm.llm.Providers ..|> llm.providers.base_provider.BaseProvider : get_instance

    class llm.llm.Llm {
        +LlmConfig config
        +BaseProvider _provider
        +provider() : BaseProvider
        +provider(provider: BaseProvider) : void
        +start_provider() : Self
        +from_config(config: LlmConfig) : Llm
        +tokenizer() : Any
        +complete(prompt: Union[str, BaseModel, RootModel], system_prompt: Optional[str], prefix_prompt: Optional[str], img_path: Optional[Union[Union[str, Path], List[Union[str, Path]]]], json_output: bool, stream: bool) : Union[str, Dict]
        +acomplete(prompt: Union[str, BaseModel, RootModel], system_prompt: Optional[str], prefix_prompt: Optional[str], img_path: Optional[Union[Union[str, Path], List[Union[str, Path]]]], json_output: bool, stream: bool) : Union[str, Dict]
    }

    class llm.llm.Providers {
        <<enumeration>>
        OPENAI
        MISTRAL
        GROQ
        +get_instance(config: LlmConfig) : BaseProvider
    }

    llm.providers.base_provider.BaseProvider <|-- llm.providers.groq.GroqLlm
    llm.providers.base_provider.BaseProvider <|-- llm.providers.mistral.MistralLlm
    llm.providers.base_provider.BaseProvider <|-- llm.providers.openai.OpenAiLlm

    class llm.providers.base_provider.BaseProvider {
        +LlmConfig config
        +Any _client
        +Any _aclient
        +Dict _completion_args
        +Any _completion_fn
        +Any _acompletion_fn
        +Any _normalize_fn
        +Any _tokenizer_fn
        +from_config(config: LlmConfig) : BaseProvider
        +client() : Any
        +client(client: Any) : void
        +aclient() : Any
        +aclient(aclient: Any) : void
        +completion_args() : Dict
        +completion_args(args: Dict) : void
        +completion_fn() : Any
        +completion_fn(completion_fn: Any) : void
        +acompletion_fn() : Any
        +acompletion_fn(acompletion_fn: Any) : void
        +normalize_fn() : Any
        +normalize_fn(normalize_fn: Any) : void
        +tokenizer_fn() : Any
        +tokenizer_fn(tokenizer_fn: Any) : void
        +get_default_tokenizer(model_name: str) : str
        +_message_content(prompt: str, img_b64_str: Optional[List[str]]) : List[Dict]
        +_message_body(prompt: str, role: Literal["user", "system", "assistant"], img_b64_str: Optional[List[str]]) : Dict
        +completion_args_template(prompt: str, system_prompt: Optional[str], prefix_prompt: Optional[str], img_b64_str: Optional[Union[str, List[str]]], stream: bool) : Dict
        +_prepare_completion_args(prompt: str, system_prompt: Optional[str], prefix_prompt: Optional[str], img_path: Optional[Union[Union[str, Path], List[Union[str, Path]]]], stream: bool) : Dict
        +_stream(stream) : str
        +_astream(stream) : str
        +model_to_str(model: Union[BaseModel, RootModel]) : str
        +extract_json(output: str) : Dict
        +complete(prompt: Union[str, BaseModel, RootModel], system_prompt: Optional[str], prefix_prompt: Optional[str], img_path: Optional[Union[Union[str, Path], List[Union[str, Path]]]], json_output: bool, stream: bool) : Union[str, Dict]
        +acomplete(prompt: Union[str, BaseModel, RootModel], system_prompt: Optional[str], prefix_prompt: Optional[str], img_path: Optional[Union[Union[str, Path], List[Union[str, Path]]]], json_output: bool, stream: bool) : Union[str, Dict]
    }

    class llm.providers.groq.GroqLlm {
        +set_groq() : Self
    }

    class llm.providers.mistral.MistralLlm {
        +set_mistral() : Self
    }

    class llm.providers.openai.OpenAiLlm {
        +set_openai() : Self
    }
```

## Sequence Diagram

The sequence diagram will illustrate the interactions between the core components of the system, focusing on the configuration and usage of embeddings and LLM providers. The diagram will highlight the following key interactions:

1. **Configuration Loading**: The `Config` class loads the configuration from a YAML file, which includes settings for both embeddings and LLM providers.
2. **Embeddings Configuration**: The `EmbeddingsConfig` class specifies the provider details for embedding providers.
3. **LLM Configuration**: The `LlmConfig` class specifies the provider details for LLM providers.
4. **Provider Instantiation**: The `Providers` enum in both the embeddings and LLM modules instantiates the appropriate provider classes based on the configuration.
5. **Embeddings Generation**: The `Embeddings` class manages embedding generation using the configured provider.
6. **LLM Completion**: The `Llm` class manages interactions with LLM providers for synchronous and asynchronous completions.

The diagram will use full module paths to ensure clarity and avoid ambiguity, highlighting the key messages and events critical to the system�s main functionalities.

```mermaid
sequenceDiagram
    autonumber

    participant Config as config.Config
    participant EmbeddingsConfig as embeddings.config.EmbeddingsConfig
    participant LlmConfig as llm.config.LlmConfig
    participant EmbeddingsProviders as embeddings.embeddings.Providers
    participant LlmProviders as llm.llm.Providers
    participant Embeddings as embeddings.embeddings.Embeddings
    participant Llm as llm.llm.Llm
    participant BaseProvider as embeddings.providers.base_provider.BaseProvider
    participant MistralLlm as llm.providers.mistral.MistralLlm
    participant OpenAiLlm as llm.providers.openai.OpenAiLlm

    Config->>Config: from_yaml(config_path)
    Config->>EmbeddingsConfig: Initialize with embeddings config
    Config->>LlmConfig: Initialize with LLM config

    EmbeddingsConfig->>EmbeddingsProviders: Get provider instance
    EmbeddingsProviders->>BaseProvider: Instantiate provider
    BaseProvider-->>EmbeddingsProviders: Provider instance
    EmbeddingsProviders-->>EmbeddingsConfig: Provider instance

    LlmConfig->>LlmProviders: Get provider instance
    LlmProviders->>BaseProvider: Instantiate provider
    BaseProvider-->>LlmProviders: Provider instance
    LlmProviders-->>LlmConfig: Provider instance

    EmbeddingsConfig->>Embeddings: from_config(config)
    Embeddings->>EmbeddingsProviders: Get provider instance
    EmbeddingsProviders->>BaseProvider: Instantiate provider
    BaseProvider-->>EmbeddingsProviders: Provider instance
    EmbeddingsProviders-->>Embeddings: Provider instance

    LlmConfig->>Llm: from_config(config)
    Llm->>LlmProviders: Get provider instance
    LlmProviders->>BaseProvider: Instantiate provider
    BaseProvider-->>LlmProviders: Provider instance
    LlmProviders-->>Llm: Provider instance

    Embeddings->>Embeddings: generate(text_batches)
    Embeddings->>BaseProvider: generate(text_batches)
    BaseProvider-->>Embeddings: Embeddings generated

    Llm->>Llm: complete(prompt)
    Llm->>BaseProvider: complete(prompt)
    BaseProvider-->>Llm: Completion result

    Llm->>Llm: acomplete(prompt)
    Llm->>BaseProvider: acomplete(prompt)
    BaseProvider-->>Llm: Asynchronous completion result

    note over Embeddings,Llm: Synchronous and Asynchronous operations
```
## License

This project is licensed under the Apache 2.0 License.