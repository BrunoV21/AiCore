"""
credit: https://github.com/sst/opencode-anthropic-auth/tree/master

Anthropic OAuth Authentication Script

This script provides OAuth authentication functionality for Anthropic's API,
supporting both Claude Pro/Max access and API key creation.
"""

from urllib.parse import urlencode
from datetime import datetime
import requests
import secrets
import hashlib
import base64

from aicore.llm.providers.anthropic.consts import CC_CLIENT_ID

def generate_pkce():
    """
    Generate PKCE (Proof Key for Code Exchange) challenge and verifier.
    
    Returns:
        dict: Contains 'verifier' and 'challenge' for PKCE flow
    """
    # Generate a random verifier (43-128 characters)
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('utf-8').rstrip('=')
    
    # Create challenge from verifier using SHA256
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode('utf-8')).digest()
    ).decode('utf-8').rstrip('=')
    
    return {
        'verifier': verifier,
        'challenge': challenge
    }

def authorize(mode):
    """
    Generate OAuth authorization URL.
    
    Args:
        mode (str): Either "max" or "console" to determine the authorization endpoint
        
    Returns:
        dict: Contains 'url' and 'verifier' for the OAuth flow
    """
    pkce = generate_pkce()
    
    base_url = f"https://{'console.anthropic.com' if mode == 'console' else 'claude.ai'}/oauth/authorize"
    
    params = {
        'code': 'true',
        'client_id': CC_CLIENT_ID,
        'response_type': 'code',
        'redirect_uri': 'https://console.anthropic.com/oauth/code/callback',
        'scope': 'org:create_api_key user:profile user:inference',
        'code_challenge': pkce['challenge'],
        'code_challenge_method': 'S256',
        'state': pkce['verifier']
    }
    
    url = f"{base_url}?{urlencode(params)}"
    
    return {
        'url': url,
        'verifier': pkce['verifier']
    }


def exchange(code, verifier):
    """
    Exchange authorization code for access and refresh tokens.
    
    Args:
        code (str): Authorization code from OAuth callback
        verifier (str): PKCE verifier used in the authorization request
        
    Returns:
        dict: Contains token information or failure status
    """
    splits = code.split('#')
    
    payload = {
        'code': splits[0],
        'state': splits[1] if len(splits) > 1 else '',
        'grant_type': 'authorization_code',
        'client_id': CC_CLIENT_ID,
        'redirect_uri': 'https://console.anthropic.com/oauth/code/callback',
        'code_verifier': verifier
    }
    
    response = requests.post(
        'https://console.anthropic.com/v1/oauth/token',
        headers={'Content-Type': 'application/json'},
        json=payload
    )
    
    if not response.ok:
        return {'type': 'failed'}
    
    json_data = response.json()
    
    return {
        'type': 'success',
        'refresh': json_data['refresh_token'],
        'access': json_data['access_token'],
        'expires': datetime.now().timestamp() * 1000 + json_data['expires_in'] * 1000
    }


def authenticate_claude_max():
    """
    Authenticate with Claude Pro/Max using OAuth.
    
    Returns:
        dict: Authentication credentials
    """
    auth_data = authorize('max')
    print(f"Visit this URL to authorize:\n{auth_data['url']}\n")
    
    code = input("Paste the authorization code here: ")
    credentials = exchange(code, auth_data['verifier'])
    
    return credentials

def refresh_access_token(refresh_token):
    """
    Refresh an expired access token using a refresh token.
    
    Args:
        refresh_token (str): The refresh token
        
    Returns:
        dict: New access token and expiration time, or None if failed
    """
    payload = {
        'grant_type': 'refresh_token',
        'refresh_token': refresh_token,
        'client_id': CC_CLIENT_ID
    }
    
    response = requests.post(
        'https://console.anthropic.com/v1/oauth/token',
        headers={'Content-Type': 'application/json'},
        json=payload
    )
    
    if not response.ok:
        return None
    
    json_data = response.json()
    
    return {
        'access': json_data['access_token'],
        'refresh': json_data['refresh_token'],
        'expires': datetime.now().timestamp() * 1000 + json_data['expires_in'] * 1000
    }
