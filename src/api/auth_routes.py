"""Authentication routes for AutoGen Financial Analysis System"""

from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import JSONResponse
from typing import Dict, Any, Optional
import logging
from datetime import datetime, timedelta
import secrets

from .models import ErrorResponse
from ..security.security_manager import get_security_manager

# Get security manager instance
security_manager = get_security_manager()

# Create router
auth_routes = APIRouter(prefix="/auth")

@auth_routes.post("/login")
async def login(request: Request, credentials: Dict[str, str]):
    """User login endpoint"""
    try:
        username = credentials.get("username")
        password = credentials.get("password")
        
        if not username or not password:
            raise HTTPException(status_code=400, detail="Username and password are required")
        
        # Get client IP and user agent
        client_ip = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent", "unknown")
        
        # Authenticate user
        session_token = security_manager.authenticate_user(username, password, client_ip, user_agent)
        
        if not session_token:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        return {
            "status": "success",
            "data": {
                "access_token": session_token,
                "token_type": "bearer",
                "expires_in": 3600
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Login error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@auth_routes.post("/refresh")
async def refresh_token(request: Request):
    """Refresh JWT token"""
    try:
        # Get authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Missing or invalid authorization header")
        
        token = auth_header.split(" ")[1]
        
        # Verify current token
        payload = security_manager.verify_session_token(token)
        if not payload:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
        
        # Get user info
        user_id = payload.get("user_id")
        username = payload.get("username")
        roles = payload.get("roles", [])
        permissions = payload.get("permissions", [])
        
        # Generate new token
        new_payload = {
            'user_id': user_id,
            'username': username,
            'roles': roles,
            'permissions': permissions,
            'created_at': datetime.now().isoformat(),
            'expires_at': (datetime.now() + timedelta(hours=1)).isoformat()
        }
        
        new_token = security_manager._generate_session_token_from_payload(new_payload)
        
        return {
            "status": "success",
            "data": {
                "access_token": new_token,
                "token_type": "bearer",
                "expires_in": 3600
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Token refresh error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@auth_routes.get("/verify")
async def verify_token(request: Request):
    """Verify JWT token"""
    try:
        # Get authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Missing or invalid authorization header")
        
        token = auth_header.split(" ")[1]
        
        # Verify token
        payload = security_manager.verify_session_token(token)
        if not payload:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
        
        return {
            "status": "success",
            "data": {
                "valid": True,
                "username": payload.get("username"),
                "expires_at": payload.get("expires_at")
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Token verification error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

# Add helper method to security manager for generating token from payload
def _generate_session_token_from_payload(self, payload: Dict[str, Any]) -> str:
    """Generate JWT session token from payload"""
    import jwt
    token = jwt.encode(payload, self.jwt_secret, algorithm='HS256')
    return token

# Monkey patch the method
import types
security_manager._generate_session_token_from_payload = types.MethodType(_generate_session_token_from_payload, security_manager)