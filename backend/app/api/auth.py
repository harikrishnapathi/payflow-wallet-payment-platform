import uuid
from datetime import datetime,timedelta,timezone
from fastapi import APIRouter,Depends,HTTPException,status
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.dependencies import get_current_user
from app.core.config import settings
from app.core.security import create_access_token,create_refresh_token,decode_refresh_token,hash_password,verify_password
from app.core.token_utils import hash_token
from app.db.session import get_db
from app.models.refresh_token import RefreshToken
from app.models.user import User,UserRole
from app.schemas.auth import LoginRequest,MessageResponse,RefreshRequest,RegisterRequest,TokenResponse,UserResponse
from app.services.wallet_service import create_user_wallet
router=APIRouter(prefix='/auth',tags=['Authentication'])
@router.post('/register',response_model=UserResponse,status_code=201)
def register(request:RegisterRequest,db:Session=Depends(get_db)):
    if db.scalar(select(User).where(User.email==request.email.lower())): raise HTTPException(409,'Email address is already registered.')
    user=User(email=request.email.lower(),password_hash=hash_password(request.password),first_name=request.first_name.strip(),last_name=request.last_name.strip(),role=UserRole.USER)
    db.add(user); db.flush(); create_user_wallet(db,user); db.commit(); db.refresh(user); return user
@router.post('/login',response_model=TokenResponse)
def login(request:LoginRequest,db:Session=Depends(get_db)):
    user=db.scalar(select(User).where(User.email==request.email.lower()))
    if not user or not verify_password(request.password,user.password_hash): raise HTTPException(401,'Invalid email or password.',headers={'WWW-Authenticate':'Bearer'})
    if not user.is_active: raise HTTPException(403,'User account is inactive.')
    user.last_login_at=datetime.now(timezone.utc)
    access=create_access_token(subject=str(user.id),role=user.role.value); refresh=create_refresh_token(subject=str(user.id))
    db.add(RefreshToken(user_id=user.id,token_hash=hash_token(refresh),expires_at=datetime.now(timezone.utc)+timedelta(days=settings.refresh_token_expire_days))); db.commit()
    return TokenResponse(access_token=access,refresh_token=refresh,user=user)
@router.post('/refresh',response_model=TokenResponse)
def refresh(request:RefreshRequest,db:Session=Depends(get_db)):
    try: payload=decode_refresh_token(request.refresh_token)
    except JWTError: raise HTTPException(401,'Invalid or expired refresh token.')
    if payload.get('type')!='refresh' or not payload.get('sub'): raise HTTPException(401,'Invalid refresh token.')
    try: uid=uuid.UUID(payload['sub'])
    except ValueError: raise HTTPException(401,'Invalid refresh token.')
    stored=db.scalar(select(RefreshToken).where(RefreshToken.token_hash==hash_token(request.refresh_token)).with_for_update())
    if not stored or stored.revoked_at or stored.expires_at<=datetime.now(timezone.utc): raise HTTPException(401,'Refresh session is invalid or expired.')
    user=db.get(User,uid)
    if not user or not user.is_active: raise HTTPException(401,'User is inactive or does not exist.')
    stored.revoked_at=datetime.now(timezone.utc); access=create_access_token(subject=str(user.id),role=user.role.value); new_refresh=create_refresh_token(subject=str(user.id)); db.add(RefreshToken(user_id=user.id,token_hash=hash_token(new_refresh),expires_at=datetime.now(timezone.utc)+timedelta(days=settings.refresh_token_expire_days))); db.commit(); return TokenResponse(access_token=access,refresh_token=new_refresh,user=user)
@router.get('/me',response_model=UserResponse)
def me(current_user:User=Depends(get_current_user)): return current_user
@router.post('/logout',response_model=MessageResponse)
def logout(request:RefreshRequest,current_user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    token=db.scalar(select(RefreshToken).where(RefreshToken.user_id==current_user.id,RefreshToken.token_hash==hash_token(request.refresh_token)))
    if token: token.revoked_at=datetime.now(timezone.utc); db.commit()
    return MessageResponse(message='Logged out successfully.')
