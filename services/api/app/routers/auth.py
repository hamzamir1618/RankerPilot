from fastapi import APIRouter, Depends, HTTPException, Response, Cookie
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from pydantic import BaseModel, EmailStr

from app.core.deps import get_db
from app.core.rate_limit import limit_login, limit_register
from app.services import auth_service

router = APIRouter(prefix="/v1/auth", tags=["Auth"])

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class GoogleLoginRequest(BaseModel):
    code: str
    code_verifier: str
    redirect_uri: str

@router.post("/register", dependencies=[Depends(limit_register)])
async def register(
    data: RegisterRequest, 
    response: Response,
    db: AsyncSession = Depends(get_db)
):
    res = await auth_service.register_user(db, data.email, data.password)
    response.set_cookie(
        key="refresh_token",
        value=res["refresh_token"],
        httponly=True,
        secure=True, # Should be true in production, assuming TLS
        samesite="lax",
        max_age=30 * 24 * 3600
    )
    return {"access_token": res["access_token"], "user_id": res["user_id"]}

@router.post("/login", dependencies=[Depends(limit_login)])
async def login(
    data: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db)
):
    res = await auth_service.login_user(db, data.email, data.password)
    response.set_cookie(
        key="refresh_token",
        value=res["refresh_token"],
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=30 * 24 * 3600
    )
    return {"access_token": res["access_token"]}

@router.post("/refresh")
async def refresh(
    response: Response,
    refresh_token: Optional[str] = Cookie(None)
):
    if not refresh_token:
        raise HTTPException(status_code=401, detail="No refresh token provided")
        
    res = await auth_service.rotate_refresh_token(refresh_token)
    response.set_cookie(
        key="refresh_token",
        value=res["refresh_token"],
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=30 * 24 * 3600
    )
    return {"access_token": res["access_token"]}

@router.post("/google")
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
    response.set_cookie(
        key="refresh_token",
        value=res["refresh_token"],
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=30 * 24 * 3600
    )
    return {"access_token": res["access_token"]}

@router.post("/logout")
async def logout(
    response: Response,
    refresh_token: Optional[str] = Cookie(None)
):
    if refresh_token:
        await auth_service.revoke_refresh_family(refresh_token)
    response.delete_cookie("refresh_token")
    return {"status": "logged_out"}
