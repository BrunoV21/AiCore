
"""
Example script demonstrating how to launch and use the observability dashboard.

This example shows how to configure and start the observability dashboard,
demonstrating how to visualize LLM operation history and performance metrics.
"""

import os
import time
import asyncio
from aicore.config import Config
from aicore.llm import Llm
from aicore.observability import ObservabilityDashboard, OperationStorage

# Function to generate sample LLM requests for demonstration
async def generate_sample_data(llm: Llm, num_requests: int = 5):
    """Generate sample LLM requests to populate the dashboard."""
    print(f"Generating {num_requests} sample LLM requests...")
    
    prompts = [
        "What is machine learning?",
        "Explain the concept of a neural network in simple terms.",
        "How do large language models work?",
        "What are the ethical considerations in AI development?",
        "Compare supervised and unsupervised learning.",
        "What is transfer learning?",
        "Explain the concept of gradient descent.",
        "What is the difference between AI, ML, and deep learning?",
        "How does natural language processing work?",
        "What are embeddings in machine learning?"
    ]
    
    for i in range(min(num_requests, len(prompts))):
        print(f"Request {i+1}: {prompts[i]}")
        try:
            # Alternate between sync and async completions
            if i % 2 == 0:
                llm.complete(prompts[i], stream=False)
            else:
                await llm.acomplete(prompts[i], stream=False)
            # Add a small delay between requests
            await asyncio.sleep(1)
        except Exception as e:
            print(f"Error during request: {e}")

async def main():
    # Load configuration
    config_path = os.getenv("CONFIG_PATH", "./config/config_example_observability.yml")
    print(f"Loading configuration from: {config_path}")
    config = Config.from_yaml(config_path)
    
    # Initialize LLM with configuration
    llm = Llm.from_config(config.llm)
    
    # Generate sample data if storage is empty
    storage = OperationStorage()
    if storage.get_all_records().is_empty():
        await generate_sample_data(llm)
    
    dashboard = ObservabilityDashboard(from_local_records_only=True)
    print(dashboard.df)
    dashboard.run_server()

if __name__ == "__main__":
    asyncio.run(main())