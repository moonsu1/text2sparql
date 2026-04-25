"""
간단한 웹 UI 테스트 페이지
"""

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

html_content = """
<!DOCTYPE html>
<html>
<head>
    <title>RDF KG Chat</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 800px;
            margin: 50px auto;
            padding: 20px;
            background: #f5f5f5;
        }
        .chat-container {
            background: white;
            border-radius: 10px;
            padding: 20px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        h1 {
            color: #333;
            text-align: center;
        }
        .input-group {
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
        }
        input[type="text"] {
            flex: 1;
            padding: 12px;
            border: 1px solid #ddd;
            border-radius: 5px;
            font-size: 14px;
        }
        button {
            padding: 12px 24px;
            background: #007bff;
            color: white;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            font-size: 14px;
        }
        button:hover {
            background: #0056b3;
        }
        .checkbox-group {
            margin-bottom: 15px;
        }
        .checkbox-group label {
            display: flex;
            align-items: center;
            gap: 8px;
            cursor: pointer;
        }
        .messages {
            max-height: 400px;
            overflow-y: auto;
            margin-top: 20px;
        }
        .message {
            margin-bottom: 15px;
            padding: 12px;
            border-radius: 8px;
        }
        .user-message {
            background: #e3f2fd;
            margin-left: 20%;
        }
        .assistant-message {
            background: #f5f5f5;
            margin-right: 20%;
        }
        .message-label {
            font-weight: bold;
            margin-bottom: 5px;
            color: #666;
            font-size: 12px;
        }
        .message-content {
            color: #333;
            line-height: 1.5;
        }
        .metadata {
            margin-top: 8px;
            padding-top: 8px;
            border-top: 1px solid #ddd;
            font-size: 12px;
            color: #666;
        }
        .loading {
            text-align: center;
            color: #666;
            padding: 20px;
        }
        .error {
            background: #ffebee;
            color: #c62828;
            padding: 12px;
            border-radius: 5px;
            margin-top: 10px;
        }
    </style>
</head>
<body>
    <div class="chat-container">
        <h1>🔍 RDF Knowledge Graph Chat</h1>
        
        <div class="checkbox-group">
            <label>
                <input type="checkbox" id="linkPrediction" />
                <span>Link Prediction 사용 (Sparse Data 처리)</span>
            </label>
        </div>
        
        <div class="input-group">
            <input type="text" id="queryInput" placeholder="질문을 입력하세요... (예: 최근 통화한 사람은 누구야?)" />
            <button onclick="sendQuery()">전송</button>
        </div>
        
        <div class="messages" id="messages"></div>
    </div>

    <script>
        const messagesDiv = document.getElementById('messages');
        const queryInput = document.getElementById('queryInput');
        const linkPrediction = document.getElementById('linkPrediction');

        queryInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') sendQuery();
        });

        async function sendQuery() {
            const query = queryInput.value.trim();
            if (!query) return;

            // Add user message
            addMessage('user', query);
            queryInput.value = '';

            // Show loading
            const loadingId = addLoading();

            try {
                const response = await fetch('/api/v1/chat', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        query: query,
                        use_link_prediction: linkPrediction.checked
                    })
                });

                removeLoading(loadingId);

                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}`);
                }

                const data = await response.json();
                
                // Add assistant message with metadata
                addMessage('assistant', data.answer, {
                    workflow: data.workflow_path.join(' → '),
                    sources: data.sources.join(', ') || 'None',
                    sparse: data.is_sparse ? 'Yes' : 'No',
                    predicted: data.predicted_triples.length,
                    time: `${data.execution_time_ms.toFixed(2)}ms`
                });

            } catch (error) {
                removeLoading(loadingId);
                addError(`Error: ${error.message}`);
            }
        }

        function addMessage(role, content, metadata = null) {
            const div = document.createElement('div');
            div.className = `message ${role}-message`;
            
            const label = document.createElement('div');
            label.className = 'message-label';
            label.textContent = role === 'user' ? 'You' : 'Assistant';
            
            const contentDiv = document.createElement('div');
            contentDiv.className = 'message-content';
            contentDiv.textContent = content;
            
            div.appendChild(label);
            div.appendChild(contentDiv);
            
            if (metadata) {
                const metaDiv = document.createElement('div');
                metaDiv.className = 'metadata';
                metaDiv.innerHTML = `
                    <div><strong>Workflow:</strong> ${metadata.workflow}</div>
                    <div><strong>Sources:</strong> ${metadata.sources}</div>
                    <div><strong>Sparse:</strong> ${metadata.sparse} | <strong>Predicted:</strong> ${metadata.predicted} | <strong>Time:</strong> ${metadata.time}</div>
                `;
                div.appendChild(metaDiv);
            }
            
            messagesDiv.appendChild(div);
            messagesDiv.scrollTop = messagesDiv.scrollHeight;
        }

        function addLoading() {
            const div = document.createElement('div');
            div.className = 'loading';
            div.id = 'loading';
            div.textContent = '답변 생성 중...';
            messagesDiv.appendChild(div);
            messagesDiv.scrollTop = messagesDiv.scrollHeight;
            return 'loading';
        }

        function removeLoading(id) {
            const elem = document.getElementById(id);
            if (elem) elem.remove();
        }

        function addError(message) {
            const div = document.createElement('div');
            div.className = 'error';
            div.textContent = message;
            messagesDiv.appendChild(div);
            messagesDiv.scrollTop = messagesDiv.scrollHeight;
        }

        // Welcome message
        addMessage('assistant', '안녕하세요! RDF Knowledge Graph 기반 질의응답 시스템입니다. 스마트폰 로그에 대해 물어보세요.', {
            workflow: 'system',
            sources: 'N/A',
            sparse: 'N/A',
            predicted: 0,
            time: '0ms'
        });
    </script>
</body>
</html>
"""

def add_test_ui_route(app: FastAPI):
    """Add simple test UI route"""
    
    @app.get("/test", response_class=HTMLResponse)
    async def test_ui():
        return html_content
