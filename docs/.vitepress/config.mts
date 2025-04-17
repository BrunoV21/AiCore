
import { defineConfig } from 'vitepress'
import { withMermaid } from "vitepress-plugin-mermaid";

export default withMermaid(
  defineConfig({
    title: 'AiCore Documentation',
    description: 'Documentation for AiCore - Python-based AI core system',
    themeConfig: {
      nav: [
        { text: 'Home', link: '/' },
        { text: 'Quickstart', link: '/quickstart/index.md' },
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
                { text: 'Installation', link: '/quickstart/installation' },
                { text: 'First Request', link: '/quickstart/first-request' }
              ]
            }
          ]
        },
        {
          text: 'Configuration',
          items: [
            { text: 'LLM Configuration', link: '/config/llmconfig' }
          ]
        },
        {
          text: 'LLM System',
          collapsed: false,
          items: [
            { text: 'Overview', link: '/llm/overview' },
            { text: 'Usage', link: '/llm/usage' },
            { text: 'Retry Mechanism', link: '/llm/retry' },
            { text: 'Base Provider', link: '/llm/base_provider' },
            { text: 'Models Metadata', link: '/llm/models_metadata' }
          ]
        },
        {
          text: 'Providers',
          collapsed: false,
          items: [
            { text: 'OpenAI', link: '/providers/openai' },
            { text: 'Anthropic', link: '/providers/anthropic' },
            { text: 'Mistral', link: '/providers/mistral' },
            { text: 'Groq', link: '/providers/groq' },
            { text: 'Gemini', link: '/providers/gemini' },
            { text: 'NVIDIA', link: '/providers/nvidia' },
            { text: 'Deepseek', link: '/providers/deepseek' },
            { text: 'Grok', link: '/providers/grok' },
            { text: 'OpenRouter', link: '/providers/openrouter' }
          ]
        },
        {
          text: 'Observability',
          collapsed: false,
          items: [
            { text: 'Overview', link: '/observability/overview' },
            { text: 'Collector', link: '/observability/collector' },
            { text: 'Dashboard', link: '/observability/dashboard' },
            { text: 'SQL Integration', link: '/observability/sql' },
            { text: 'Polars Integration', link: '/observability/polars' }
          ]
        },
        {
          text: 'Examples',
          link: '/examples/index.md'
        },
        {
          text: 'Showcase',
          items: [
            { text: 'Built with AiCore', link: '/built-with-aicore' }
          ]
        }
      ],

      socialLinks: [
        { icon: 'github', link: 'https://github.com/BrunoV21/AiCore' }
      ],

      footer: {
        message: 'Released under the MIT License.',
        copyright: 'Copyright © 2023-present AiCore Team'
      }
    },

    mermaid: {
      theme: "default", // "dark", "forest", etc.
    },

    mermaidPlugin: {
      class: "mermaid my-class"
    }
  })
)