# Reasoning:
# - Design pattern: The example demonstrates the usage of the `Llm` class, which itself follows a layered architecture with dependency injection (LlmBaseProvider).
#   The `Llm` class uses composition by containing an `LlmConfig` and optionally a reasoner (`Llm` instance).
# - Optimization: The example showcases both synchronous and asynchronous calls (`complete` and `acomplete`), allowing for flexibility in usage.
#   The reasoning process is encapsulated within the `_reason` and `_areason` methods, making the main `complete` and `acomplete` methods cleaner.
# - Error Handling:  The `LlmConfig` class uses Pydantic's field validators to ensure data integrity (e.g., temperature range, supported reasoner providers and models).
#   The example itself doesn't implement specific error handling, relying on the underlying `Llm` and provider classes to handle potential exceptions (e.g., API errors).
# - Integration: The example integrates with the `LlmConfig` for configuration, and it uses the `Llm` class's methods to perform completions.
#   It demonstrates how to set up a reasoner, which is another `Llm` instance, to enhance the main LLM's responses. The example uses hardcoded API keys, which should be replaced with environment variables or a secure configuration mechanism in a production environment.

# Code starts here
from aicore.llm.llm import Llm
from aicore.llm.config import LlmConfig
from aicore.llm.templates import REASONING_STOP_TOKEN

import asyncio


async def main():
    # Configure the main LLM (using OpenAI as an example)
    main_config = LlmConfig(
        provider="openai",
        api_key="YOUR_OPENAI_API_KEY",  # Replace with your actual API key
        model="gpt-3.5-turbo",
        temperature=0.7,
        max_tokens=2000,
    )

    # Configure the reasoner LLM (using Mistral as an example)
    reasoner_config = LlmConfig(
        provider="mistral",
        api_key="YOUR_MISTRAL_API_KEY",  # Replace with your actual API key
        model="mistral-small",
        temperature=0.2,
        max_tokens=1000,
    )
    main_config.reasoner = reasoner_config

    # Create the Llm instance with the configuration
    llm = Llm.from_config(main_config)

    # Example prompt
    prompt = "Explain the theory of relativity in simple terms."

    # --- Synchronous call with reasoning ---
    print("--- Synchronous call with reasoning ---")
    response = llm.complete(prompt=prompt, stream=False)
    print(f"Final Response: {response}")
    print("\n")

    # --- Asynchronous call with reasoning ---
    print("--- Asynchronous call with reasoning ---")
    response = await llm.acomplete(prompt=prompt, stream=False)
    print(f"Final Response: {response}")
    print("\n")

    # --- Example without a reasoner ---
    print("--- Synchronous call without reasoning ---")
    llm_no_reasoner = Llm.from_config(config=main_config)
    llm_no_reasoner.reasoner = None  # Explicitly remove the reasoner
    response_no_reasoner = llm_no_reasoner.complete(prompt=prompt, stream=False)
    print(f"Response (no reasoner): {response_no_reasoner}")
    print("\n")

    # --- Asynchronous call without reasoning ---
    print("--- Asynchronous call without reasoning ---")
    response_no_reasoner = await llm_no_reasoner.acomplete(prompt=prompt, stream=False)
    print(f"Response (no reasoner): {response_no_reasoner}")
    print("\n")

    # --- Example with streaming and reasoning ---
    print("--- Synchronous call with reasoning and streaming ---")
    response_stream = llm.complete(prompt=prompt, stream=True)
    print(f"Final Response: {response_stream}")
    print("\n")

    # --- Example with streaming and without reasoning ---
    print("--- Synchronous call without reasoning and streaming ---")
    response_stream = llm_no_reasoner.complete(prompt=prompt, stream=True)
    print(f"Final Response: {response_stream}")
    print("\n")

    # --- Example with async streaming and reasoning ---
    print("--- Asynchronous call with reasoning and streaming ---")
    response_stream = await llm.acomplete(prompt=prompt, stream=True)
    print(f"Final Response: {response_stream}")
    print("\n")

    # --- Example with async streaming and without reasoning ---
    print("--- Asynchronous call without reasoning and streaming ---")
    response_stream = await llm_no_reasoner.acomplete(prompt=prompt, stream=True)
    print(f"Final Response: {response_stream}")
    print("\n")

if __name__ == "__main__":
    asyncio.run(main())