import datetime
import uuid
import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException
import httpx

from app.core.config import settings
from app.core.rate_limit import redis_client
from app.models.models import User, Organization, Membership, RoleEnum

ph = PasswordHasher()

def hash_password(password: str) -> str:
    return ph.hash(password)

def verify_password(password_hash: str, password: str) -> bool:
    try:
        ph.verify(password_hash, password)
        if ph.check_needs_rehash(password_hash):
            pass # Background rehash not implemented for simplicity
        return True
    except VerifyMismatchError:
        return False

def create_access_token(user_id: uuid.UUID) -> str:
    expire = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=15)
    payload = {
        "sub": str(user_id),
        "type": "access",
        "exp": expire,
        "iat": datetime.datetime.now(datetime.timezone.utc),
        "aud": "rankerpilot_api",
        "iss": "rankerpilot"
    }
    return jwt.encode(payload, settings.JWT_SECRET.get_secret_value(), algorithm="HS256")

async def create_refresh_token(user_id: uuid.UUID) -> dict:
    expire = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=30)
    token_id = str(uuid.uuid4())
    family_id = str(uuid.uuid4())
    
    payload = {
        "sub": str(user_id),
        "type": "refresh",
        "jti": token_id,
        "family": family_id,
        "exp": expire,
        "iat": datetime.datetime.now(datetime.timezone.utc),
        "aud": "rankerpilot_api",
        "iss": "rankerpilot"
    }
    token = jwt.encode(payload, settings.JWT_REFRESH_SECRET.get_secret_value(), algorithm="HS256")
    
    # Store in Redis: family_id maps to current valid token_id
    key = f"refresh_family:{family_id}"
    await redis_client.set(key, token_id, ex=30 * 24 * 3600)
    
    return {"token": token, "family": family_id, "jti": token_id}

async def rotate_refresh_token(token: str) -> dict:
    try:
        payload = jwt.decode(
            token,
            settings.JWT_REFRESH_SECRET.get_secret_value(),
            algorithms=["HS256"],
            audience="rankerpilot_api",
            issuer="rankerpilot"
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="TOKEN_EXPIRED")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
        
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid token type")
        
    family_id = payload.get("family")
    jti = payload.get("jti")
    user_id_str = payload.get("sub")
    
    key = f"refresh_family:{family_id}"
    current_valid_jti = await redis_client.get(key)
    
    if current_valid_jti is None:
        # Family revoked or expired
        raise HTTPException(status_code=401, detail="Refresh token family revoked or expired")
        
    if current_valid_jti != jti:
        # Reuse detected! Revoke family.
        await redis_client.delete(key)
        raise HTTPException(status_code=401, detail="Refresh token reuse detected. Family revoked. Please login again.")
        
    # Valid token. Rotate it.
    new_jti = str(uuid.uuid4())
    expire = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=30)
    
    new_payload = {
        "sub": user_id_str,
        "type": "refresh",
        "jti": new_jti,
        "family": family_id,
        "exp": expire,
        "iat": datetime.datetime.now(datetime.timezone.utc),
        "aud": "rankerpilot_api",
        "iss": "rankerpilot"
    }
    
    new_token = jwt.encode(new_payload, settings.JWT_REFRESH_SECRET.get_secret_value(), algorithm="HS256")
    
    # Update Redis
    await redis_client.set(key, new_jti, ex=30 * 24 * 3600)
    
    return {
        "access_token": create_access_token(uuid.UUID(user_id_str)),
        "refresh_token": new_token
    }

async def revoke_refresh_family(token: str):
    try:
        payload = jwt.decode(
            token,
            settings.JWT_REFRESH_SECRET.get_secret_value(),
            algorithms=["HS256"],
            audience="rankerpilot_api",
            issuer="rankerpilot"
        )
        family_id = payload.get("family")
        if family_id:
            await redis_client.delete(f"refresh_family:{family_id}")
    except Exception:
        pass # Ignore errors on logout

async def register_user(db: AsyncSession, email: str, password: str):
    # Check duplicate
    result = await db.execute(select(User).where(User.email == email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already registered")
        
    user_id = uuid.uuid4()
    org_id = uuid.uuid4()
    
    # Create user
    user = User(
        id=user_id,
        email=email,
        password_hash=hash_password(password)
    )
    db.add(user)
    
    # Create personal org
    org = Organization(
        id=org_id,
        name=f"Personal Org ({email})"
    )
    db.add(org)
    
    await db.flush()
    
    # Create membership
    membership = Membership(
        user_id=user_id,
        org_id=org_id,
        role=RoleEnum.owner
    )
    db.add(membership)
    
    await db.commit()
    
    access = create_access_token(user_id)
    refresh_data = await create_refresh_token(user_id)
    
    return {
        "access_token": access,
        "refresh_token": refresh_data["token"],
        "user_id": user_id
    }

async def login_user(db: AsyncSession, email: str, password: str):
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    
    if not user or not user.password_hash:
        raise HTTPException(status_code=401, detail="Invalid credentials")
        
    if not verify_password(user.password_hash, password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
        
    access = create_access_token(user.id)
    refresh_data = await create_refresh_token(user.id)
    
    return {
        "access_token": access,
        "refresh_token": refresh_data["token"]
    }

async def google_oauth_login(db: AsyncSession, code: str, code_verifier: str, redirect_uri: str):
    # 1. Exchange code for token
    async with httpx.AsyncClient() as client:
        resp = await client.post("https://oauth2.googleapis.com/token", data={
            "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
            "client_secret": settings.GOOGLE_OAUTH_CLIENT_SECRET.get_secret_value(),
            "code": code,
            "code_verifier": code_verifier,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code"
        })
        if resp.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to exchange code")
            
        token_data = resp.json()
        id_token_str = token_data.get("id_token")
        
        if not id_token_str:
            raise HTTPException(status_code=400, detail="No id_token in response")
            
        # 2. Decode id_token (skipping signature verification for speed since we just got it via TLS directly from Google)
        # In a real production scenario with arbitrary JWTs, verify it. Here we got it directly.
        decoded = jwt.decode(
            id_token_str, 
            options={"verify_signature": False},
            audience=settings.GOOGLE_OAUTH_CLIENT_ID,
            issuer=["https://accounts.google.com", "accounts.google.com"]
        )
        
        email = decoded.get("email")
        google_sub = decoded.get("sub")
        
        if not email or not google_sub:
            raise HTTPException(status_code=400, detail="Incomplete profile from Google")
            
        # 3. Find user
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        
        if user:
            if user.google_sub == google_sub:
                # Login
                pass
            elif not user.google_sub:
                # Password user exists. Linking requires verifying ownership first.
                raise HTTPException(status_code=409, detail="Requires password login to link account")
            else:
                # Another sub?
                raise HTTPException(status_code=409, detail="Email associated with different Google account")
        else:
            # Create user + org
            user_id = uuid.uuid4()
            org_id = uuid.uuid4()
            user = User(
                id=user_id,
                email=email,
                google_sub=google_sub
            )
            db.add(user)
            
            org = Organization(
                id=org_id,
                name=f"Personal Org ({email})"
            )
            db.add(org)
            
            await db.flush()
            
            membership = Membership(
                user_id=user_id,
                org_id=org_id,
                role=RoleEnum.owner
            )
            db.add(membership)
            await db.commit()
            
        access = create_access_token(user.id)
        refresh_data = await create_refresh_token(user.id)
        
        return {
            "access_token": access,
            "refresh_token": refresh_data["token"]
        }
