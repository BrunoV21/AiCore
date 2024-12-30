from aicore.const import DEFAULT_CONFIG_PATH
from aicore.embeddings import EmbeddingsConfig
from aicore.llm import LlmConfig

from pydantic import BaseModel
from typing import Optional, Union
from pathlib import Path
import yaml
import os

class Config(BaseModel):
    embeddings :EmbeddingsConfig=None
    llm :LlmConfig=None

    @classmethod
    def from_yaml(cls, config_path :Optional[Union[str, Path]]=None)->"Config":
        if config_path is None:
            config_path = os.getenv("CONFIG_PATH") or DEFAULT_CONFIG_PATH
        config_path = Path(config_path)

        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Configuration file not found: {config_path}. Please ensure the file exists and the path is correct.")
        
        with open(config_path, "r") as _file:
            yaml_config = yaml.safe_load(_file)

        return cls(**yaml_config)