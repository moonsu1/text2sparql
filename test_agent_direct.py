"""
Direct Agent Test
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

print("=" * 60)
print("AGENT INITIALIZATION")
print("=" * 60)
from app.agents.kg_agent import KGAgent

agent = KGAgent()
print("Agent initialized successfully!")
print()

print("=" * 60)
print("AGENT QUERY TEST")
print("=" * 60)
result = agent.query(
    query="오늘 전화 통화 기록 보여줘",
    use_link_prediction=False
)

print(f"\n답변: {result.get('answer', '')[:500]}")
print(f"\nSPARQL: {result.get('sparql_query', '')[:300]}")
print(f"\nWorkflow: {' -> '.join(result.get('workflow_path', []))}")
print("=" * 60)
