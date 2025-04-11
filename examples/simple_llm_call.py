from aicore.config import Config
from aicore.llm import Llm
import os

if __name__ == "__main__":
    os.environ["CONFIG_PATH"] = "./config/config.yml"
    config = Config.from_yaml()
    llm = Llm.from_config(config.llm)
    print(llm.config.max_tokens)
    llm.complete("Tell me the story of how OpenAi became ClosedAi")

    