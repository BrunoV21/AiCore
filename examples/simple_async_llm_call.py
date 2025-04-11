from aicore.config import Config
from aicore.llm import Llm
import os
import asyncio

if __name__ == "__main__":

    # asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    # os.environ["CONFIG_PATH"] = "./config/config.yml"
    config = Config.from_yaml()
    llm = Llm.from_config(config.llm)
    print(llm.usage.pricing)
    async def run():
        reposne = await asyncio.create_task(llm.acomplete("how much us 8 + 9 - 15", agent_id="o3-mano", action_id="complex_ask"))

        print(f"{reposne=}")
        # await asyncio.create_task(llm.acomplete("how much us 8 + 9 - 15", agent_id="o3-mate"))
    asyncio.run(run())