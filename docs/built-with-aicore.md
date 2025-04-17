
# Projects Built with AiCore

Discover how developers are leveraging AiCore to build powerful AI applications. Below are featured projects that demonstrate the flexibility and capabilities of the AiCore system.

## Featured Projects

### Chainlit Chat Interface
- **Description**: Full-featured chat application with multiple LLM provider support
- **Key Features**:
  - Switch between different LLM providers on-the-fly
  - Built-in reasoning capabilities with configurable templates
  - Customizable UI with Chainlit components
  - Docker deployment ready
- **Repository**: [github.com/example/chainlit-aicore](https://github.com/example/chainlit-aicore)
- **Example Code**:
  ```python
  from aicore.llm import LLM
  from chainlit import user_session
  
  # Initialize AiCore LLM with Chainlit integration
  llm = LLM(config_path="config.yml")
  user_session.set("llm", llm)
  ```

### FastAPI Production API
- **Description**: Enterprise-ready API service with comprehensive AI capabilities
- **Key Features**:
  - JWT authentication
  - Advanced rate limiting
  - Real-time websocket support
  - Built-in observability dashboard
  - Example endpoints for common AI tasks
- **Repository**: [github.com/example/fastapi-aicore](https://github.com/example/fastapi-aicore)
- **Example Code**:
  ```python
  from fastapi import APIRouter
  from aicore.llm import LLM
  
  router = APIRouter()
  llm = LLM(config_path="config.yml")
  
  @router.post("/chat")
  async def chat_endpoint(prompt: str):
      return await llm.chat(prompt)
  ```

### Observability Dashboard
- **Description**: Real-time monitoring for AI workloads
- **Key Features**:
  - Visualize LLM usage metrics
  - Cost tracking per model/provider
  - Performance monitoring
  - SQL and Polars integration for analytics
- **Repository**: [github.com/example/aicore-dashboard](https://github.com/example/aicore-dashboard)

## Community Projects

| Project | Description | Tech Stack |
|---------|-------------|------------|
| [AI Content Generator](https://github.com/example/content-gen) | Automated content creation pipeline | AiCore + Celery |
| [Customer Support Bot](https://github.com/example/support-bot) | Intelligent customer support agent | AiCore + Django |
| [Research Assistant](https://github.com/example/research-ai) | Academic paper analysis tool | AiCore + Streamlit |

## Add Your Project

We welcome contributions to this showcase! To add your AiCore-based project:

1. Fork the repository
2. Add your project details to this file following the existing format
3. Submit a pull request

**Submission Guidelines**:
- Include a clear description and key features
- Provide a link to the repository
- Add example code snippets if applicable
- Keep entries concise and informative

Looking forward to seeing what you've built with AiCore!