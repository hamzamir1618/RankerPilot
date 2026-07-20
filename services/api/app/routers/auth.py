from fastapi import APIRouter, Depends, HTTPException, Response, Cookie
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from pydantic import BaseModel, EmailStr, Field
from app.core.config import settings
from app.services import auth_service
from app.core.deps import get_db
from app.core.rate_limit import limit_login, limit_register

class RegisterRequest(BaseModel):
    email: EmailStr = Field(description="The user's email address.")
    password: str = Field(description="The user's chosen password, minimum 8 characters.")

class LoginRequest(BaseModel):
    email: EmailStr = Field(description="The user's registered email address.")
    password: str = Field(description="The user's password.")

class GoogleLoginRequest(BaseModel):
    code: str = Field(description="The authorization code returned by Google.")
    code_verifier: str = Field(description="The PKCE code verifier used during the initial authorization request.")
    redirect_uri: str = Field(description="The redirect URI used during the initial authorization request.")

def get_cookie_settings():
    return {
        "httponly": True,
        "secure": True, # Always True since production requires HTTPS and localhost allows Secure=True
        "samesite": "lax" if settings.is_dev else "none",
        "max_age": 30 * 24 * 3600
    }

router = APIRouter(prefix="/v1/auth", tags=["Auth"])

@router.post(
    "/register", 
    dependencies=[Depends(limit_register)],
    summary="Register a new user",
    description="Creates a new user account and returns an access token along with setting an HTTP-only refresh token cookie.",
    responses={
        200: {"description": "Successfully registered."},
        400: {"description": "Email already registered."},
        429: {"description": "Too many registration attempts."}
    }
)
async def register(
    data: RegisterRequest, 
    response: Response,
    db: AsyncSession = Depends(get_db)
):
    res = await auth_service.register_user(db, data.email, data.password)
    response.set_cookie(key="refresh_token", value=res["refresh_token"], **get_cookie_settings())
    return {"access_token": res["access_token"], "user_id": res["user_id"]}

@router.post(
    "/login", 
    dependencies=[Depends(limit_login)],
    summary="Login user",
    description="Authenticates a user via email and password, returning an access token and setting a refresh token cookie.",
    responses={
        200: {"description": "Successfully logged in."},
        400: {"description": "Invalid credentials."},
        429: {"description": "Too many login attempts."}
    }
)
async def login(
    data: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db)
):
    res = await auth_service.login_user(db, data.email, data.password)
    response.set_cookie(key="refresh_token", value=res["refresh_token"], **get_cookie_settings())
    return {"access_token": res["access_token"]}

@router.post(
    "/refresh",
    summary="Refresh access token",
    description="Rotates the refresh token securely and issues a new access token. Requires the `refresh_token` HTTP-only cookie to be present.",
    responses={
        200: {"description": "Successfully refreshed tokens."},
        401: {"description": "No refresh token provided or token invalid/expired."},
        403: {"description": "Refresh token family revoked due to reuse detection."}
    }
)
async def refresh(
    response: Response,
    refresh_token: Optional[str] = Cookie(None)
):
    if not refresh_token:
        raise HTTPException(status_code=401, detail="No refresh token provided")
        
    res = await auth_service.rotate_refresh_token(refresh_token)
    response.set_cookie(key="refresh_token", value=res["refresh_token"], **get_cookie_settings())
    return {"access_token": res["access_token"]}

@router.post(
    "/google",
    summary="Google OAuth login",
    description="Exchanges a Google OAuth authorization code for an access token and sets a refresh token cookie.",
    responses={
        200: {"description": "Successfully logged in via Google."},
        400: {"description": "Google authentication failed or returned no email."}
    }
)
async def google_login(
    data: GoogleLoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db)
):
    res = await auth_service.google_oauth_login(
        db, 
        code=data.code, 
        code_verifier=data.code_verifier, 
        redirect_uri=data.redirect_uri
    )
    response.set_cookie(key="refresh_token", value=res["refresh_token"], **get_cookie_settings())
    return {"access_token": res["access_token"]}

@router.post(
    "/logout",
    summary="Logout user",
    description="Revokes the refresh token family and deletes the refresh token cookie.",
    responses={
        200: {"description": "Successfully logged out."}
    }
)
async def logout(
    response: Response,
    refresh_token: Optional[str] = Cookie(None)
):
    if refresh_token:
        await auth_service.revoke_refresh_family(refresh_token)
    response.delete_cookie("refresh_token")
    return {"status": "logged_out"}
