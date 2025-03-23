# Welcome to Reasoner4All! 🚀🤖

Reasoner4All is a simple demo that allows you to supercharge your favorite LLMs by integrating advanced reasoning capabilities from the latest open-source thinking models. Whether you're working with OpenAI, Mistral, Groq, or Gemini, this framework seamlessly enhances their decision-making with an additional reasoning layer. Leverage models like DeepSeek R1 Distill LLaMA-70B to improve your AI's problem-solving skills and contextual understanding!

## Useful Links 🔗
A Hugging Face Space where you can chat with multiple reasoning augmented models.

[![Hugging Face Space](https://huggingface.co/datasets/huggingface/badges/raw/main/open-in-hf-spaces-xl.svg)](https://huggingface.co/spaces/McLoviniTtt/Reasoner4All)

## Features

**Supports Multiple LLM Providers**
- OpenAI
- Mistral
- Groq (including DeepSeek R1 Distill LLaMA-70B for reasoning)
- Gemini
- and more!

**Reasoner Integration** 
- Uses an additional (reasoning) LLM to enhance reasoning capabilities
- Support for Deepseek R1 Distill LLaMA-70B (Groq Hosted) and Deepseek R1 (Nvidia Hosted)

**Conversation History**
- For context reasons the converstation history up to latest 4096 tokens is preserved and passed to the llms as context

## User Interface
**Settings**
- Provider and Model selection
- Reasoner Option and Model selection
- Support for System Propmpt and Reasoner System prompt specification

**Profiles**
- Reasoner4All uses a series of pre-set API Keys for demo purposes
- OpenAi allows you to connect to your models with support for api key if required *don't worry I am not logging your keys anwyehre but you can check the src code of this space to be sure :)*

**Chat**
- Reasoning steps appear inside a step which can be expanded to visualize the process