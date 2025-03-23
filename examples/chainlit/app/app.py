import chainlit as cl

from aicore.logger import _logger
from aicore.config import LlmConfig
from aicore.const import STREAM_END_TOKEN, STREAM_START_TOKEN, REASONING_START_TOKEN, REASONING_STOP_TOKEN

from aicore.llm import Llm

from ulid import ulid
import asyncio
import time

from utils import MODELS_PROVIDERS_MAP, PROVIDERS_API_KEYS, REASONER_PROVIDERS_MAP, check_openai_api_key, trim_messages
from settings import PROFILES_SETTINGS

DEFAULT_REASONER_CONFIG = LlmConfig(
    provider="groq",
    api_key=PROVIDERS_API_KEYS.get("groq"),
    model="deepseek-r1-distill-llama-70b",
    temperature=0.5,
    max_tokens=1024
)

DEFAULT_LLM_CONFIG = {
    "Reasoner4All": LlmConfig(
        provider="mistral",
        api_key=PROVIDERS_API_KEYS.get("mistral"),
        model="mistral-small-latest",
        temperature=0,
        max_tokens=1024,
        reasoner=DEFAULT_REASONER_CONFIG
    ),
    "OpenAi": LlmConfig(
        provider="openai",
        api_key=PROVIDERS_API_KEYS.get("openai", ""),
        model="gpt-4o-mini",
        temperature=0,
        max_tokens=1024,
        reasoner=DEFAULT_REASONER_CONFIG
    )
}

@cl.set_chat_profiles
async def chat_profile():
    return [
        cl.ChatProfile(
            name="Reasoner4All",
            markdown_description="A deepseek-r1-distill-llama-70b powered Reasoner for your favourite open-source LLMs",
            icon="https://picsum.photos/200",
        ),
        cl.ChatProfile(
            name="OpenAi",
            markdown_description="A deepseek-r1-distill-llama-70b powered Reasoner for closed source LLMs",
            icon="https://picsum.photos/200",
        )
    ]
    
@cl.on_settings_update
async def setup_agent(settings):
    provider = MODELS_PROVIDERS_MAP.get(settings.get("Model"), "openai")
    llm_config = LlmConfig(
        provider=provider,
        api_key=PROVIDERS_API_KEYS.get(provider) or settings.get("Api Key"),
        model=settings.get("Model"),
        temperature=settings.get("Temperature"),
        max_tokens=settings.get("Max Tokens")
    )
    if settings.get("Use Reasoner"):
        reasoner_provder = REASONER_PROVIDERS_MAP.get(settings.get("Reasoner Model"), "openai")
        reasoner_config = LlmConfig(
            provider=reasoner_provder,
            api_key=PROVIDERS_API_KEYS.get(reasoner_provder) or settings.get("Reasoner Api Key"),
            model=settings.get("Reasoner Model"),
            temperature=settings.get("Reasoner Temperature"),
            max_tokens=settings.get("Reasoner Max Tokens")
        )
        llm_config.reasoner = reasoner_config
    
    llm = Llm.from_config(llm_config)
    llm.session_id = ulid()
    llm.system_prompt = settings.get("System Prompt")
    if llm.reasoner:
        llm.reasoner.system_prompt = settings.get("Reasoner System Prompt")

    cl.user_session.set(
        "llm", llm
    )

@cl.on_chat_start
async def start_chat():
    user_profile = cl.user_session.get("chat_profile")
    cl.user_session.set("history", [])
    llm_config = DEFAULT_LLM_CONFIG.get(user_profile)
    llm = Llm.from_config(llm_config)
    llm.session_id = ulid()
    cl.user_session.set(
        "llm", llm
    )
    
    settings = await cl.ChatSettings(
        PROFILES_SETTINGS.get(user_profile)
    ).send()
    

async def run_concurrent_tasks(llm, message):
    asyncio.create_task(llm.acomplete(message))
    asyncio.create_task(_logger.distribute())
    # Stream logger output while LLM is running
    while True:        
        async for chunk in _logger.get_session_logs(llm.session_id):
            yield chunk  # Yield each chunk directly

@cl.on_message
async def main(message: cl.Message):
    llm = cl.user_session.get("llm")
    if not llm.config.api_key:
        while True:
            api_key_msg = await cl.AskUserMessage(content="Please provide a valid api_key", timeout=10).send()
            if api_key_msg:
                api_key = api_key_msg.get("output")
                valid = check_openai_api_key(api_key)
                if valid:
                    await cl.Message(
                        content=f"Config updated with key.",
                    ).send()
                    llm.config.api_key = api_key
                    cl.user_session.set("llm", llm)
                    break
    
    start = time.time()
    thinking=False
    
    history = cl.user_session.get("history")
    history.append(message.content)
    history = trim_messages(history, llm.tokenizer)
    model_id = None
    try:
        if llm.reasoner is not None or llm.config.model in REASONER_PROVIDERS_MAP:
            # Streaming the thinking
            async with cl.Step(name=f"{llm.reasoner.config.provider} - {llm.reasoner.config.model} to think", type="llm") as thinking_step:
                msg = cl.Message(content="")
                async for chunk in run_concurrent_tasks(
                        llm,
                        message=history
                    ):
                    if chunk == STREAM_START_TOKEN:
                        continue
                    if chunk == REASONING_START_TOKEN:
                        thinking = True
                        continue
                        # chunk = " - *reasoning*\n```html\n"
                    if chunk == REASONING_STOP_TOKEN:
                        thinking = False
                        thought_for = round(time.time() - start)
                        thinking_step.name = f"{llm.reasoner.config.model} to think for {thought_for}s"
                        await thinking_step.update()
                        chunk = f"```{llm.config.model}```\n"
                        model_id = f"```{llm.config.model}```\n"

                    if chunk == STREAM_END_TOKEN:
                        break
                    
                    if thinking:
                        await thinking_step.stream_token(chunk)
                    else:
                        await msg.stream_token(chunk)
        else:
            msg = cl.Message(content="")
            async for chunk in run_concurrent_tasks(
                    llm,
                    message=history
                ):
                if chunk == STREAM_START_TOKEN:
                    continue

                if chunk == STREAM_END_TOKEN:
                        break
                
                await msg.stream_token(chunk)
            
        hst_msg = msg.content.replace(model_id, "") if model_id else msg.content
        history.append(hst_msg)
        await msg.send()
    
    except Exception as e:
        await cl.ErrorMessage("Internal Server Error").send()