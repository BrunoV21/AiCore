from aicore.config import Config
from aicore.llm import Llm
import os
import asyncio

if __name__ == "__main__":
    
    # os.environ["CONFIG_PATH"] = "./config/config_mcp_example.yml"
    config = Config.from_yaml()
    assert config.llm.mcp_config_path, "Provide a mcp_config_path to your mcp_config.json file to run thise example"
    print(config.model_dump_json(indent=4))
    llm = Llm.from_config(config.llm)

    async def run():
        response = await llm.acomplete(
            "Search for Elon Musk and tell me what do the news from today say about him",
            system_prompt="You are an helpfull assistant with tool calling capabilities. Make sure you use the tools at your disposal with relevant arguments passed! When makibng websearches always suggest three different queries to be obtian relevant information!",
            # stream=False,
            agent_id="mcp-agent", 
            action_id="tool-call"
        )
        print("\n\nFINAL RESPONSE")
        print(response)
       
    asyncio.run(run())