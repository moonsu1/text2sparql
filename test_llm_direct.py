"""
Direct LLM Test
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
import os

load_dotenv()

print("=" * 60)
print("ENV TEST")
print("=" * 60)
print(f"GEMINI_API_KEYS: {os.getenv('GEMINI_API_KEYS', 'NOT FOUND')[:50]}")
print(f"GEMINI_MODEL: {os.getenv('GEMINI_MODEL', 'NOT SET')}")
print()

from app.agents.llm_client import call_llm

print("=" * 60)
print("LLM CLIENT TEST")
print("=" * 60)
result = call_llm(
    system_prompt="You are a helpful assistant.",
    user_prompt="What is 2+2? Answer with just the number.",
    temperature=0.3,
    max_retries=2
)

print(f"\n결과: {result}")
print("=" * 60)
