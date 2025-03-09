
from aicore.const import DEFAULT_CONFIG_PATH, DEFAULT_OBSERVABILITY_DIR, DEFAULT_OBSERVABILITY_FILE, DEFAULT_DASHBOARD_PORT, DEFAULT_DASHBOARD_HOST
from aicore.embeddings import EmbeddingsConfig
from aicore.llm import LlmConfig
from pydantic import BaseModel, field_validator
from typing import Optional, Union, Dict, Any
from pathlib import Path
import yaml
import os

class ObservabilityConfig(BaseModel):
    """Configuration for the observability module."""
    enabled: bool = True
    storage_dir: Optional[str] = DEFAULT_OBSERVABILITY_DIR
    storage_file: Optional[str] = DEFAULT_OBSERVABILITY_FILE
    dashboard_enabled: bool = True
    dashboard_port: int = DEFAULT_DASHBOARD_PORT
    dashboard_host: str = DEFAULT_DASHBOARD_HOST
    
    @field_validator("dashboard_port")
    @classmethod
    def validate_port(cls, port: int) -> int:
        """Validate that the dashboard port is in a valid range."""
        if not (1024 <= port <= 65535):
            raise ValueError(f"Dashboard port must be between 1024 and 65535, got {port}")
        return port

class Config(BaseModel):
    embeddings: EmbeddingsConfig = None
    llm: LlmConfig = None
    observability: Optional[ObservabilityConfig] = ObservabilityConfig()
    
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
            config_path = os.getenv("CONFIG_PATH") or DEFAULT_CONFIG_PATH
        config_path = Path(config_path)

        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Configuration file not found: {config_path}. Please ensure the file exists and the path is correct.")
        
        with open(config_path, "r") as _file:
            yaml_config = yaml.safe_load(_file)

        # Set default observability settings if not provided
        if 'observability' not in yaml_config:
            yaml_config['observability'] = {}
            
        return cls(**yaml_config)