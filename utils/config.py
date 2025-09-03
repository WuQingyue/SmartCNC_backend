from pydantic_settings import BaseSettings
from typing import Optional
from dotenv import load_dotenv
import os
import secrets

load_dotenv()

class Settings(BaseSettings):
    # Google OAuth配置
    GOOGLE_CLIENT_ID: str
    GOOGLE_CLIENT_SECRET: str

    # 应用配置
    FRONTEND_URL: str
    BACKEND_URL: str
    
    # 数据库配置
    DATABASE_URL: str

    # Redis配置
    REDIS_HOST: str
    REDIS_PORT: int
    REDIS_DB: int
    REDIS_PASSWORD: Optional[str]
    
    # Session配置
    SESSION_SECRET_KEY: str
    SESSION_EXPIRE_SECONDS: int
    SESSION_COOKIE_DOMAIN: Optional[str]
    SESSION_COOKIE_SECURE: bool
    SESSION_COOKIE_SAMESITE: str

    # PayPal配置
    PAYPAL_MODE: str
    PAYPAL_CLIENT_ID: str
    PAYPAL_CLIENT_SECRET: str
    PAYPAL_API_BASE: str
    # JLC-CNC配置
    JLC_CNC_USERNAME: str
    JLC_CNC_PASSWORD: str
    
    # YT配置
    YT_USERNAME: str
    YT_PASSWORD: str

    # 运费配置
    JLC_FREIGHT_RATIO: float   # JLC运费比例，默认95%
    YT_FREIGHT_RATIO: float   # YT运费比例，默认90%


    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()