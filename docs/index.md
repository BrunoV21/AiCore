---
# https://vitepress.dev/reference/default-theme-home-page
layout: home

hero:
  name: "AiCore Docs"
  text: "Official Documentation for the AiCore project"
  tagline: Unify your LLM stack. Track everything. Stay in control.
  actions:
    - theme: brand
      text: Quickstart
      link: /quickstart/index
    - theme: alt
      text: Built with AiCore
      link: /built-with-aicore
    - theme: alt
      text: llms.txt
      link: https://github.com/BrunoV21/AiCore/blob/main/llms.txt

features:
  - title: 🔌 Unified Multi-LLM Interface
    details: Seamlessly connect to multiple LLM providers via a single interface. llms.txt included so that your agents can build with AiCore.
  - title: 📊 Token, Cost & Usage Tracking
    details: Automatically track tokens, latency, and cost per call, storing everything in your SQL database of choice.
  - title: 📈 Observability Dashboard
    details: Visualize model performance, cost trends, full prompt details and usage patterns with a built-in dashboard powered by SQL or local data.

---

