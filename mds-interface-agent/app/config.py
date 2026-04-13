"""Application configuration — loads from .env file."""

import os
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# Auto-detect which LLM provider to use
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "").lower()  # "openai" or "anthropic"
if not LLM_PROVIDER:
    if OPENAI_API_KEY:
        LLM_PROVIDER = "openai"
    elif ANTHROPIC_API_KEY:
        LLM_PROVIDER = "anthropic"

MODEL_NAME = os.getenv("MODEL_NAME", "")
if not MODEL_NAME:
    MODEL_NAME = "gpt-4.1" if LLM_PROVIDER == "openai" else "claude-sonnet-4-5-20250929"

MAX_ITERATIONS = int(os.getenv("MAX_ITERATIONS", "25"))
DEMO_MODE = not ANTHROPIC_API_KEY and not OPENAI_API_KEY

# InfluxDB — set these to enable time-series queries
INFLUXDB_VERSION = os.getenv("INFLUXDB_VERSION", "1")  # "1" or "2"
INFLUXDB_URL = os.getenv("INFLUXDB_URL", "")  # e.g. http://localhost:8086
INFLUXDB_TOKEN = os.getenv("INFLUXDB_TOKEN", "")  # v2 only
INFLUXDB_ORG = os.getenv("INFLUXDB_ORG", "")  # v2 only
INFLUXDB_BUCKET = os.getenv("INFLUXDB_BUCKET", "mds_san")  # v2 bucket or v1 database
INFLUXDB_USERNAME = os.getenv("INFLUXDB_USERNAME", "")  # v1 only
INFLUXDB_PASSWORD = os.getenv("INFLUXDB_PASSWORD", "")  # v1 only
