from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "ClassroomPortal API"
    DEBUG: bool = True
    
    # Database
    DATABASE_URL: str = "postgresql://user:priyanshu@localhost:5432/classroom_portal"
    
    # JWT
    SECRET_KEY: str = "635c283e5f6d2920cf864fe77fca83c446fa243a96b51057a65b3ea94fcc1f602e6cb86db9b94b36af99ac5add1e0be0d54ce899f94ec26d7aff084c2a10c005"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:8080",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8080",
        "http://10.0.2.2:8000",  # Android emulator
    ]
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
