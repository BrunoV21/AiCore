from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from datetime import timedelta

from models.schemas import Token, User, ChatRequest, LlmConfig
from auth.dependencies import get_current_active_user
from auth.utils import authenticate_user, create_access_token
from auth.dependencies import fake_users_db
from config import ACCESS_TOKEN_EXPIRE_MINUTES
from services.llm_service import initialize_llm_session, simulate_llm_response, set_llm

router = APIRouter()

@router.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = authenticate_user(fake_users_db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}


async def create_llm_session(
    request: LlmConfig
    # current_user: User = Depends(get_current_active_user)
):
    """
    Create a new LLM session with custom configuration
    
    Returns a session ID that can be used in subsequent chat requests
    """
    try:
        session_id = await set_llm(request)
        return {
            "session_id": session_id,
            "message": "LLM session created successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat")
async def chat(
    chat_request: ChatRequest
    # current_user: User = Depends(get_current_active_user)
):
    try:
        llm = await initialize_llm_session(chat_request.session_id)
        response = await llm.acomplete(chat_request.message)
        return {"response": response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))