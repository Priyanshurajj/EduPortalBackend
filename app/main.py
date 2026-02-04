from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
import socketio

from app.core.config import settings
from app.core.socketio_manager import sio
# from app.core.socketio_manager import socket_app
from app.database import Base, engine
from app.routers import auth, classroom, chat

# Create database tables
Base.metadata.create_all(bind=engine)

# Create uploads directory
os.makedirs("uploads/materials", exist_ok=True)

# Create FastAPI application
fastapi_app = FastAPI(
    title=settings.APP_NAME,
    description="A classroom portal API for teachers and students",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Configure CORS
fastapi_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for Socket.IO compatibility
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files for uploads
fastapi_app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# Mount Socket.IO app
# app.mount("/ws", socket_app)

# Include routers
fastapi_app.include_router(auth.router)
fastapi_app.include_router(classroom.router)
fastapi_app.include_router(chat.router)


@fastapi_app.get("/", tags=["Health"])
async def root():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "message": "Welcome to ClassroomPortal API",
        "docs": "/docs",
        "socket_io": "/ws/socket.io"
    }


@fastapi_app.get("/health", tags=["Health"])
async def health_check():
    """Detailed health check endpoint."""
    return {
        "status": "healthy",
        "app_name": settings.APP_NAME,
        "debug": settings.DEBUG,
    }

# Wrap FastAPI app with Socket.IO
app = socketio.ASGIApp(sio, other_asgi_app=fastapi_app)