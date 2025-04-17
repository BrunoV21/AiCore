
# Configuration Guide

Welcome to the AiCore Configuration documentation! This section covers all aspects of configuring the AiCore system.

## Configuration Options

1. [LLM Configuration](./llmconfig.md) - Configure LLM providers and models
2. [Environment Variables](../.env-example) - Reference for environment-based configuration
3. [YAML Configuration](../config/) - Example configuration files

## Key Concepts

- YAML and environment variable support
- Pydantic validation for all configurations
- Provider-specific configuration options
- Hierarchical configuration (global → provider → model)
- Environment variable overrides

## Configuration Sources

AiCore supports multiple configuration sources with the following precedence:
1. Environment variables (highest priority)
2. YAML configuration files
3. Default values (lowest priority)

## Getting Started

1. Copy the example configuration from `config/config_example_*.yml`
2. Modify the settings for your provider
3. Set any sensitive values via environment variables
4. Initialize your components using the configuration

For detailed provider-specific configuration, see the [Providers section](../providers/).