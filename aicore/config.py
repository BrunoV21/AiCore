
from aicore.const import DEFAULT_CONFIG_PATH
from aicore.embeddings import EmbeddingsConfig
from aicore.llm import LlmConfig
from pydantic import BaseModel
from typing import Optional, Union
from pathlib import Path
import yaml
import os

class Config(BaseModel):
    embeddings: EmbeddingsConfig = None
    llm: LlmConfig = None
    
    @classmethod
    def from_yaml(cls, config_path: Optional[Union[str, Path]] = None) -> "Config":
        """
        Load configuration from a YAML file.
        
        Args:
            config_path: Path to the YAML configuration file. If None, it will try to use
                        the CONFIG_PATH environment variable or the default path.
                        
        Returns:
            Config: Configuration object with settings from the YAML file.
            
        Raises:
            FileNotFoundError: If the configuration file doesn't exist.
        """
        if config_path is None:
            config_path = DEFAULT_CONFIG_PATH
        config_path = Path(config_path)

        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Configuration file not found: {config_path}. Please ensure the file exists and the path is correct.")
        
        with open(config_path, "r") as _file:
            yaml_config = yaml.safe_load(_file)

        # Set default observability settings if not provided
        if 'observability' not in yaml_config:
            yaml_config['observability'] = {}
            
        return cls(**yaml_config)
    
    @staticmethod
    def get_env_var(key: str, required: bool = True) -> Optional[str]:
        value = os.getenv(key)
        if required and not value:
            raise ValueError(f"Environment variable {key} is required but not set or empty.")
        return value
    
    @classmethod
    def from_environment(cls) -> "Config":
        """
        Load configuration from environment variables.
        
        This method initializes a Config object using environment variables.
        It ensures all required fields are present and raises an error if any mandatory field is missing.
        Optional fields are included if set in the environment.
        
        If all required fields for a specific config (embeddings or llm) are missing, that config is set to None.
        
        Returns:
            Config: An instance of the Config class with values from environment variables.
        
        Raises:
            ValueError: If any required environment variable is missing or empty.
        """
        obj = cls()

        embeddings_required_keys = ["EMBEDDINGS_PROVIDER", "EMBEDDINGS_API_KEY", "EMBEDDINGS_MODEL"]
        embeddings_values = {key: cls.get_env_var(key, required=False) for key in embeddings_required_keys}
        
        if all(not value for value in embeddings_values.values()):
            embeddings_config = None
        else:
            embeddings_config = EmbeddingsConfig(
                provider=embeddings_values["EMBEDDINGS_PROVIDER"],
                api_key=embeddings_values["EMBEDDINGS_API_KEY"],
                model=embeddings_values["EMBEDDINGS_MODEL"],
                base_url=cls.get_env_var("EMBEDDINGS_BASE_URL", required=False),
            )
            obj.embeddings = embeddings_config

        llm_required_keys = ["LLM_PROVIDER", "LLM_API_KEY", "LLM_MODEL"]
        llm_values = {key: cls.get_env_var(key, required=False) for key in llm_required_keys}
        
        if all(not value for value in llm_values.values()):
            llm_config = None
        else:
            llm_config = LlmConfig(
                provider=llm_values["LLM_PROVIDER"],
                api_key=llm_values["LLM_API_KEY"],
                model=llm_values["LLM_MODEL"],
                base_url=cls.get_env_var("LLM_BASE_URL", required=False),
                temperature=float(cls.get_env_var("LLM_TEMPERATURE", required=False) or 0),
                max_tokens=int(cls.get_env_var("LLM_MAX_TOKENS", required=False) or 12000),
            )
            obj.llm = llm_config

        if not (embeddings_config or llm_config):
            raise ValueError("One of embeddings or llm configs must be passed")

        return obj