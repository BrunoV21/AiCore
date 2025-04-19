# Llm Config .env file

You can create a Config object directly from a .env file:

```bash
WORKSPACE="your-workspace
LLM_PROVIDER="mistral"
MAX_TOKENS="2048"
LLM_MODEL="mistral-small-latest"
LLM_API_KEY="..."
```

Which can the be used to initialize a Llm class:
```python
    from aicore.config import Config
    from aicore.llm import Llm
    
    config = Config.from_environment()
    llm = Llm.from_config(config.llm)
```