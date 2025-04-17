import { defineConfig } from 'vitepress'

export default defineConfig({
  title: 'AiCore Documentation',
  description: 'Documentation for AiCore - Python-based AI core system',
  themeConfig: {
    nav: [
      { text: 'Home', link: '/' },
      { text: 'Quickstart', link: '/quickstart/' },
      { text: 'Configuration', link: '/config/' },
      { text: 'LLM System', link: '/llm/' },
      { text: 'Providers', link: '/providers/' },
      { text: 'Observability', link: '/observability/' },
      { text: 'Examples', link: '/examples/' }
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
        link: '/examples/'
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
  }
})