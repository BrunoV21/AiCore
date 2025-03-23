from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import asyncio
import json
import jwt
import os
import time
from aicore.config import Config
from aicore.llm import Llm

# Initialize FastAPI app
app = FastAPI(title="LLM Service API")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Authentication settings
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Rate limiting settings
RATE_LIMIT_PER_MINUTE = 20
rate_limit_storage: Dict[str, List[float]] = {}

# IP whitelist/blacklist
IP_WHITELIST = os.getenv("IP_WHITELIST", "").split(",")
IP_BLACKLIST = os.getenv("IP_BLACKLIST", "").split(",")

# LLM session storage
llm_sessions: Dict[str, Llm] = {}
active_connections: Dict[str, WebSocket] = {}

# Models
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

class User(BaseModel):
    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    disabled: Optional[bool] = None

class UserInDB(User):
    hashed_password: str

class ChatRequest(BaseModel):
    session_id: str
    message: str
    model_params: Optional[Dict[str, Any]] = None

# Mock user database - in production, use a real database
fake_users_db = {
    "testuser": {
        "username": "testuser",
        "full_name": "Test User",
        "email": "test@example.com",
        "hashed_password": "fakehashedsecret",
        "disabled": False,
    }
}

# Authentication functions
def verify_password(plain_password, hashed_password):
    # In production, use proper password hashing
    return plain_password == "password" and hashed_password == "fakehashedsecret"

def get_user(db, username: str):
    if username in db:
        user_dict = db[username]
        return UserInDB(**user_dict)
    return None

def authenticate_user(fake_db, username: str, password: str):
    user = get_user(fake_db, username)
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except jwt.PyJWTError:
        raise credentials_exception
    user = get_user(fake_users_db, username=token_data.username)
    if user is None:
        raise credentials_exception
    return user

async def get_current_active_user(current_user: User = Depends(get_current_user)):
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

# Rate limiting middleware
@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    # Get client IP or use token if authenticated
    client_ip = request.client.host
    now = time.time()
    
    # Check blacklist and whitelist
    if IP_BLACKLIST and client_ip in IP_BLACKLIST:
        raise HTTPException(status_code=403, detail="IP address is blacklisted")
    
    # if IP_WHITELIST and client_ip not in IP_WHITELIST:
    #     raise HTTPException(status_code=403, detail="IP address is not whitelisted")
    
    # Apply rate limiting
    if client_ip not in rate_limit_storage:
        rate_limit_storage[client_ip] = []
    
    # Remove timestamps older than 1 minute
    rate_limit_storage[client_ip] = [t for t in rate_limit_storage[client_ip] if now - t < 60]
    
    # Check if rate limit is exceeded
    if len(rate_limit_storage[client_ip]) >= RATE_LIMIT_PER_MINUTE:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    
    # Add current timestamp
    rate_limit_storage[client_ip].append(now)
    
    # Continue with request
    response = await call_next(request)
    return response

# Token endpoint for authentication
@app.post("/token", response_model=Token)
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

# Initialize LLM for a session
async def initialize_llm_session(session_id: str) -> Llm:
    if session_id in llm_sessions:
        return llm_sessions[session_id]
    
    try:
        # Initialize LLM
        os.environ["CONFIG_PATH"] = "./config/config.yml"
        config = Config.from_yaml()
        llm = Llm.from_config(config.llm)
        llm_sessions[session_id] = llm
        return llm
    except Exception as e:
        print(f"Error initializing LLM for session {session_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to initialize LLM: {str(e)}")


def simulate_llm_response(message: str) -> List[str]:
    """Simulate LLM response by breaking a dummy response into chunks."""
    response = f"This is a simulated response to: '{message}'. In a real implementation, this would be the actual output from your LLM model. The response would be generated in chunks and streamed back to the client as they become available."
    
    # Break into chunks of approximately 10 characters
    chunks = []
    for i in range(0, len(response), 10):
        chunks.append(response[i:i+10])
    
    return chunks

# Cleanup function for LLM sessions
@app.on_event("shutdown")
async def shutdown_event():
    # Clean up any resources when the application shuts down
    for session_id, connection in active_connections.items():
        try:
            await connection.close()
        except:
            pass
    
    # Clear session storage
    llm_sessions.clear()
    active_connections.clear()

# Health check endpoint
@app.get("/health")
async def health_check():#current_user: User = Depends(get_current_active_user)):
    return {"status": "healthy"}#, "user": current_user.username}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)