from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
import json
from typing import Optional

from services.llm_service import initialize_llm_session, simulate_llm_response, run_concurrent_tasks
from aicore.const import SPECIAL_TOKENS, STREAM_END_TOKEN
import ulid

router = APIRouter()

# WebSocket connection storage
active_connections = {}
active_histories = {}

@router.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id : Optional[str]=None):
    print("Here")
    await websocket.accept()

    if not session_id:
        session_id = ulid.ulid()
    
    # Store the connection
    active_connections[session_id] = websocket

    history  = []
    try:
        # Initialize LLM
        llm = await initialize_llm_session(session_id)
        if session_id not in active_histories:
            active_histories[session_id] = history
        else:
            history = active_histories[session_id]
        
        while True:
            data = await websocket.receive_text()
            message = data
            history.append(message)
            response = []
            async for chunk in run_concurrent_tasks(
                llm,
                message=history
            ):
                if chunk == STREAM_END_TOKEN:
                    break
                elif chunk in SPECIAL_TOKENS:
                    continue
                
                await websocket.send_text(json.dumps({"chunk": chunk}))
                response.append(chunk)
            
            history.append("".join(response))
    
    except WebSocketDisconnect:
        if session_id in active_connections:
            del active_connections[session_id]
    except Exception as e:
        if session_id in active_connections:
            await websocket.send_text(json.dumps({"error": str(e)}))
            del active_connections[session_id]