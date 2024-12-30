import os

DEFAULT_CONFIG_PATH = "./config/config.yml"

COMMERCIAL_ADS_DATASET_PATH = "./microsoft-commercial-ads-dataset"
COMMERCIAL_ADS_DATA_JSON_PATH = os.environ.get("COMMERCIAL_ADS_DATA_JSON_PATH") or f"{COMMERCIAL_ADS_DATASET_PATH}/commercial_ads_dataset.json"
PROCESSED_COMMERCIAL_ADS_DATA_JSON_PATH = os.environ.get("PROCESSED_COMMERCIAL_ADS_DATA_JSON_PATH") or f"{COMMERCIAL_ADS_DATASET_PATH}/processed_commercial_ads_dataset.json"


DEFAULT_ENCODING = "utf8"