import time
from typing import Dict, List
from fastapi import Request, HTTPException
from fastapi import FastAPI

# Rate limit storage
rate_limit_storage: Dict[str, List[float]] = {}

def add_rate_limiting_middleware(app: FastAPI):
    """Add rate limiting middleware to FastAPI app"""
    
    @app.middleware("http")
    async def rate_limit_middleware(request: Request, call_next):
        from config import RATE_LIMIT_PER_MINUTE, IP_BLACKLIST, IP_WHITELIST
        
        # Get client IP
        client_ip = request.client.host
        now = time.time()
        
        # Check blacklist and whitelist
        if IP_BLACKLIST and client_ip in IP_BLACKLIST:
            raise HTTPException(status_code=403, detail="IP address is blacklisted")
        
        # Uncomment if you want to enforce whitelist
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
    
    return app