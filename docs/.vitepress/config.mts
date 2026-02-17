
import { defineConfig } from 'vitepress'
import { withMermaid } from "vitepress-plugin-mermaid";

export default withMermaid(
  defineConfig({
    title: 'AiCore Documentation',
    base: '/AiCore/',
    description: 'Documentation for AiCore - Python-based AI core system',
    head: [['link', { rel: 'icon', href: '/AiCore/favicon.ico' }]],
    themeConfig: {
      nav: [
        { text: 'Home', link: '/' },
        { text: 'Quickstart', link: '/quickstart/index.md' },
        { text: 'News', link: '/news/claude-code-provider.md' },
        { text: 'Configuration', link: '/config/index.md' },
        { text: 'LLM System', link: '/llm/index.md' },
        { text: 'Providers', link: '/providers/index.md' },
        { text: 'Observability', link: '/observability/index.md' },
        { text: 'Examples', link: '/examples/index.md' }
      ],

      sidebar: [
        {
          text: 'Getting Started',
          items: [
            { text: 'Introduction', link: '/' },
            { 
              text: 'Quickstart', 
              items: [
                { text: 'Installation', link: '/quickstart/installation.md' },
                { text: 'First Request', link: '/quickstart/first-request.md' },
                { text: 'Claude Code Quickstart', link: '/quickstart/claude-code.md' }
              ]
            }
          ]
        },
        {
          text: 'News',
          items: [
            { text: 'Claude Code Provider', link: '/news/claude-code-provider.md' },
            { text: 'MCP Integration', link: '/news/mcp-integration.md' }
          ]
        },
        {
          text: 'Configuration',
          items: [
            { text: 'LLM Configuration', link: '/config/llmconfig.md' }
          ]
        },
        {
          text: 'LLM System',
          collapsed: false,
          items: [
            { text: 'Overview', link: '/llm/overview.md' },
            { text: 'Usage', link: '/llm/usage.md' },
            { text: 'Retry Mechanism', link: '/llm/retry.md' },
            { text: 'Base Provider', link: '/llm/base_provider.md' },
            { text: 'Models Metadata', link: '/llm/models_metadata.md' },
            { text: 'MCP Integration', link: '/llm/mcp.md' },
            { text: 'Claude Code Providers', link: '/llm/claude-code.md' }
          ]
        },
        {
          text: 'Providers',
          collapsed: false,
          items: [
            { text: 'OpenAI', link: '/providers/openai.md' },
            { text: 'Anthropic', link: '/providers/anthropic.md' },
            { text: 'Mistral', link: '/providers/mistral.md' },
            { text: 'Groq', link: '/providers/groq.md' },
            { text: 'Gemini', link: '/providers/gemini.md' },
            { text: 'NVIDIA', link: '/providers/nvidia.md' },
            { text: 'Deepseek', link: '/providers/deepseek.md' },
            { text: 'Grok', link: '/providers/grok.md' },
            { text: 'OpenRouter', link: '/providers/openrouter.md' },
            { text: 'Claude Code (Local)', link: '/providers/claude-code.md' },
            { text: 'Claude Code (Remote)', link: '/providers/claude-code.md#remote-provider-remote-claude-code' }
          ]
        },
        {
          text: 'Observability',
          collapsed: false,
          items: [
            { text: 'Overview', link: '/observability/overview.md' },
            { text: 'Connection Strings', link: '/observability/env-example.md' },
            { text: 'Collector', link: '/observability/collector.md' },
            { text: 'Dashboard', link: '/observability/dashboard.md' },
            { text: 'SQL Integration', link: '/observability/sql.md' },
            { text: 'Polars Integration', link: '/observability/polars.md' },
          ]
        },
        {
          text: 'Examples',
          collapsed: false,
          items: [
            { text: 'Overview', link: '/examples/index.md' },
            { text: 'FastAPI', link: '/examples/fastapi.md' },
            { text: 'Chainlit', link: '/examples/chainlit.md' },
            { text: 'Observability Dashboard', link: '/examples/observability_dashboard.md' },
            { text: 'Reasoning Example', link: '/examples/reasoning_example.md' },
            { text: 'Simple Async LLM Call', link: '/examples/simple_async_llm_call.md' },
            { text: 'Simple LLM Call', link: '/examples/simple_llm_call.md' },
            { text: 'Async LLM Call with MCP', link: '/examples/async_llm_call_with_mcp.md' }
          ]
        },
        {
          text: 'Showcase',
          items: [
            { text: 'Built with AiCore', link: '/built-with-aicore.md' }
          ]
        }
      ],

      socialLinks: [
        { icon: 'github', link: 'https://github.com/BrunoV21/AiCore' }
      ],

      footer: {
        message: 'Released under the MIT License.',
        copyright: 'Copyright © 2024-present AiCore Team'
      }
    },

    mermaid: {
      theme: "default",
    },

    mermaidPlugin: {
      class: "mermaid my-class"
    }
  })
)