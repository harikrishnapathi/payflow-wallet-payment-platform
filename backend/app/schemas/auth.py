import uuid
from datetime import datetime
from pydantic import BaseModel,ConfigDict,EmailStr,Field
class RegisterRequest(BaseModel): email:EmailStr; password:str=Field(min_length=8,max_length=128); first_name:str=Field(min_length=1,max_length=100); last_name:str=Field(min_length=1,max_length=100)
class LoginRequest(BaseModel): email:EmailStr; password:str=Field(min_length=1,max_length=128)
class UserResponse(BaseModel): model_config=ConfigDict(from_attributes=True); id:uuid.UUID; email:EmailStr; first_name:str; last_name:str; role:str; is_active:bool; is_verified:bool; created_at:datetime
class TokenResponse(BaseModel): access_token:str; refresh_token:str; token_type:str='bearer'; user:UserResponse
class RefreshRequest(BaseModel): refresh_token:str
class MessageResponse(BaseModel): message:str
