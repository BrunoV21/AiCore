import os
from datetime import timedelta

# Authentication settings
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Rate limiting settings
RATE_LIMIT_PER_MINUTE = 20

# IP whitelist/blacklist
IP_WHITELIST = os.getenv("IP_WHITELIST", "").split(",")
IP_BLACKLIST = os.getenv("IP_BLACKLIST", "").split(",")

# LLM CONFIG PATH
CONFIG_PATH = os.getenv("CONFIG_PATH", "./config/config.yml")