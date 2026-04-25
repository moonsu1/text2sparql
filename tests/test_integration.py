"""
End-to-End Integration Test
"""

import sys
from pathlib import Path
import requests
import time

sys.path.append(str(Path(__file__).parent))

def test_health():
    """Test health endpoint"""
    print("\n[TEST] Health Check")
    response = requests.get("http://localhost:8000/health")
    print(f"  Status: {response.status_code}")
    print(f"  Response: {response.json()}")
    assert response.status_code == 200
    

def test_chat_dense():
    """Test chat with dense data (no link prediction)"""
    print("\n[TEST] Chat - Dense Data")
    
    payload = {
        "query": "최근 통화한 사람은 누구야?",
        "use_link_prediction": False
    }
    
    start_time = time.time()
    response = requests.post("http://localhost:8000/api/v1/chat", json=payload)
    elapsed = (time.time() - start_time) * 1000
    
    print(f"  Status: {response.status_code}")
    print(f"  Response time: {elapsed:.2f}ms")
    
    if response.status_code == 200:
        result = response.json()
        print(f"  Answer: {result['answer'][:100]}...")
        print(f"  Workflow: {' -> '.join(result['workflow_path'])}")
        print(f"  Sources: {result['sources']}")
    else:
        print(f"  Error: {response.text}")


def test_chat_sparse():
    """Test chat with sparse data (with link prediction)"""
    print("\n[TEST] Chat - Sparse Data (Link Prediction)")
    
    payload = {
        "query": "김철수랑 통화하고 나서 들른 카페 어디였지?",
        "use_link_prediction": True
    }
    
    start_time = time.time()
    response = requests.post("http://localhost:8000/api/v1/chat", json=payload)
    elapsed = (time.time() - start_time) * 1000
    
    print(f"  Status: {response.status_code}")
    print(f"  Response time: {elapsed:.2f}ms")
    
    if response.status_code == 200:
        result = response.json()
        print(f"  Answer: {result['answer'][:200]}...")
        print(f"  Is sparse: {result['is_sparse']}")
        print(f"  Predicted triples: {len(result['predicted_triples'])}")
        print(f"  Workflow: {' -> '.join(result['workflow_path'])}")
    else:
        print(f"  Error: {response.text}")


def test_openai_compat():
    """Test OpenAI-compatible endpoint"""
    print("\n[TEST] OpenAI-Compatible API")
    
    payload = {
        "model": "rdf-kg-agent",
        "messages": [
            {"role": "user", "content": "가장 자주 쓴 앱 뭐야?"}
        ]
    }
    
    start_time = time.time()
    response = requests.post("http://localhost:8000/v1/chat/completions", json=payload)
    elapsed = (time.time() - start_time) * 1000
    
    print(f"  Status: {response.status_code}")
    print(f"  Response time: {elapsed:.2f}ms")
    
    if response.status_code == 200:
        result = response.json()
        print(f"  Model: {result['model']}")
        print(f"  Answer: {result['choices'][0]['message']['content'][:100]}...")
    else:
        print(f"  Error: {response.text}")


def main():
    """Run all tests"""
    print("=" * 70)
    print("End-to-End Integration Test")
    print("=" * 70)
    print("\nNOTE: Make sure FastAPI server is running on http://localhost:8000")
    print("Run: python backend/main.py")
    print()
    
    try:
        test_health()
        test_chat_dense()
        test_chat_sparse()
        test_openai_compat()
        
        print("\n" + "=" * 70)
        print("All tests completed!")
        print("=" * 70)
    
    except requests.exceptions.ConnectionError:
        print("\n[ERROR] Cannot connect to server. Is it running?")
        print("Start server with: python backend/main.py")
    
    except Exception as e:
        print(f"\n[ERROR] Test failed: {e}")


if __name__ == "__main__":
    main()
