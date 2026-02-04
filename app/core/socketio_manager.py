import socketio
from datetime import datetime, timezone
from jose import JWTError, jwt

from app.core.config import settings
from app.database.connection import SessionLocal
from app.models.user import User
from app.models.classroom import Classroom, student_classroom
from app.models.chat import ChatMessage

# Create Socket.IO async server
sio = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins='*',
    logger=True,
    engineio_logger=True,
    ping_timeout=60,
    ping_interval=25
)

# Create ASGI app for Socket.IO
# When mounted at /ws, the full path will be /ws/socket.io
socket_app = socketio.ASGIApp(
    sio, 
    socketio_path='socket.io'  # Relative path without leading slash
)


def get_user_from_token(token: str):
    """Validate JWT token and return user."""
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        email: str = payload.get("sub")
        if email is None:
            return None
        
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.email == email).first()
            return user
        finally:
            db.close()
    except JWTError:
        return None


def is_user_in_classroom(user_id: int, classroom_id: int) -> bool:
    """Check if user is teacher or enrolled student in the classroom."""
    db = SessionLocal()
    try:
        classroom = db.query(Classroom).filter(Classroom.id == classroom_id).first()
        if not classroom:
            return False
        
        # Check if user is the teacher
        if classroom.teacher_id == user_id:
            return True
        
        # Check if user is an enrolled student
        enrollment = db.execute(
            student_classroom.select().where(
                (student_classroom.c.student_id == user_id) &
                (student_classroom.c.classroom_id == classroom_id)
            )
        ).first()
        
        return enrollment is not None
    finally:
        db.close()


def save_message(classroom_id: int, sender_id: int, content: str) -> dict:
    """Save message to database and return message data."""
    db = SessionLocal()
    try:
        message = ChatMessage(
            classroom_id=classroom_id,
            sender_id=sender_id,
            content=content
        )
        db.add(message)
        db.commit()
        db.refresh(message)
        
        # Get sender info
        sender = db.query(User).filter(User.id == sender_id).first()
        
        return {
            'id': message.id,
            'classroom_id': message.classroom_id,
            'sender_id': message.sender_id,
            'sender_name': sender.full_name if sender else 'Unknown',
            'sender_role': sender.role.value if sender else 'unknown',
            'content': message.content,
            'sent_at': message.sent_at.isoformat()
        }
    finally:
        db.close()


# Store connected users: {sid: {'user_id': int, 'user_name': str, 'rooms': set()}}
connected_users = {}


@sio.event
async def connect(sid, environ, auth):
    """Handle client connection with JWT authentication."""
    print(f"Client attempting to connect: {sid}")
    print(f"Auth data received: {auth}")
    print(f"Environ keys: {list(environ.keys())}")
    
    # Get token from auth data
    token = None
    if auth and isinstance(auth, dict) and 'token' in auth:
        token = auth['token']
    
    # Also try to get from query string if not in auth
    if not token:
        query_string = environ.get('QUERY_STRING', '')
        print(f"Query string: {query_string}")
        # Parse token from query string if present
        for param in query_string.split('&'):
            if param.startswith('token='):
                token = param.split('=', 1)[1]
                break
    
    if not token:
        print(f"No token provided for {sid}")
        # Don't reject - allow connection but mark as unauthenticated
        # This allows the client to authenticate later
        connected_users[sid] = {
            'user_id': None,
            'user_name': 'Anonymous',
            'user_role': 'guest',
            'rooms': set(),
            'authenticated': False
        }
        print(f"Anonymous connection allowed for {sid}")
        return True
    
    # Validate token and get user
    user = get_user_from_token(token)
    if not user:
        print(f"Invalid token for {sid}")
        connected_users[sid] = {
            'user_id': None,
            'user_name': 'Anonymous',
            'user_role': 'guest',
            'rooms': set(),
            'authenticated': False
        }
        return True
    
    # Store user info
    connected_users[sid] = {
        'user_id': user.id,
        'user_name': user.full_name,
        'user_role': user.role.value,
        'rooms': set(),
        'authenticated': True
    }
    
    print(f"User {user.full_name} (ID: {user.id}) connected with sid: {sid}")
    await sio.emit('connected', {'message': 'Connected successfully', 'user_id': user.id}, to=sid)
    return True


@sio.event
async def disconnect(sid):
    """Handle client disconnection."""
    if sid in connected_users:
        user_info = connected_users[sid]
        print(f"User {user_info['user_name']} disconnected")
        
        # Leave all rooms
        for room in user_info['rooms']:
            await sio.leave_room(sid, f"classroom_{room}")
        
        del connected_users[sid]
    else:
        print(f"Unknown client disconnected: {sid}")


@sio.event
async def join_room(sid, data):
    """Handle joining a classroom chat room."""
    if sid not in connected_users:
        await sio.emit('error', {'message': 'Not connected'}, to=sid)
        return
    
    user_info = connected_users[sid]
    
    # Check if authenticated
    if not user_info.get('authenticated', False) or user_info.get('user_id') is None:
        await sio.emit('error', {'message': 'Not authenticated'}, to=sid)
        return
    
    classroom_id = data.get('classroom_id')
    if not classroom_id:
        await sio.emit('error', {'message': 'classroom_id is required'}, to=sid)
        return
    
    user_id = user_info['user_id']
    
    # Check if user is authorized to join this classroom
    if not is_user_in_classroom(user_id, classroom_id):
        await sio.emit('error', {'message': 'Not authorized to join this classroom'}, to=sid)
        return
    
    room_name = f"classroom_{classroom_id}"
    await sio.enter_room(sid, room_name)
    user_info['rooms'].add(classroom_id)
    
    print(f"User {user_info['user_name']} joined room {room_name}")
    await sio.emit('room_joined', {
        'classroom_id': classroom_id,
        'message': f"Joined classroom {classroom_id}"
    }, to=sid)


@sio.event
async def leave_room(sid, data):
    """Handle leaving a classroom chat room."""
    if sid not in connected_users:
        return
    
    classroom_id = data.get('classroom_id')
    if not classroom_id:
        return
    
    user_info = connected_users[sid]
    room_name = f"classroom_{classroom_id}"
    
    await sio.leave_room(sid, room_name)
    user_info['rooms'].discard(classroom_id)
    
    print(f"User {user_info['user_name']} left room {room_name}")
    await sio.emit('room_left', {'classroom_id': classroom_id}, to=sid)


@sio.event
async def send_message(sid, data):
    """Handle sending a chat message."""
    if sid not in connected_users:
        await sio.emit('error', {'message': 'Not connected'}, to=sid)
        return
    
    user_info = connected_users[sid]
    
    # Check if authenticated
    if not user_info.get('authenticated', False) or user_info.get('user_id') is None:
        await sio.emit('error', {'message': 'Not authenticated'}, to=sid)
        return
    
    classroom_id = data.get('classroom_id')
    content = data.get('content', '').strip()
    
    if not classroom_id:
        await sio.emit('error', {'message': 'classroom_id is required'}, to=sid)
        return
    
    if not content:
        await sio.emit('error', {'message': 'Message content is required'}, to=sid)
        return
    
    if len(content) > 2000:
        await sio.emit('error', {'message': 'Message too long (max 2000 characters)'}, to=sid)
        return
    
    user_id = user_info['user_id']
    
    # Verify user is in this classroom
    if classroom_id not in user_info['rooms']:
        # Try to verify authorization
        if not is_user_in_classroom(user_id, classroom_id):
            await sio.emit('error', {'message': 'Not authorized to send messages in this classroom'}, to=sid)
            return
    
    # Save message to database
    message_data = save_message(classroom_id, user_id, content)
    
    # Broadcast message to all users in the room
    room_name = f"classroom_{classroom_id}"
    await sio.emit('message_received', message_data, room=room_name)
    
    print(f"Message sent by {user_info['user_name']} in classroom {classroom_id}: {content[:50]}...")


@sio.event
async def typing(sid, data):
    """Handle typing indicator."""
    if sid not in connected_users:
        return
    
    classroom_id = data.get('classroom_id')
    if not classroom_id:
        return
    
    user_info = connected_users[sid]
    room_name = f"classroom_{classroom_id}"
    
    # Broadcast typing indicator to others in the room
    await sio.emit('user_typing', {
        'user_id': user_info['user_id'],
        'user_name': user_info['user_name'],
        'classroom_id': classroom_id
    }, room=room_name, skip_sid=sid)


@sio.event
async def stop_typing(sid, data):
    """Handle stop typing indicator."""
    if sid not in connected_users:
        return
    
    classroom_id = data.get('classroom_id')
    if not classroom_id:
        return
    
    user_info = connected_users[sid]
    room_name = f"classroom_{classroom_id}"
    
    await sio.emit('user_stop_typing', {
        'user_id': user_info['user_id'],
        'classroom_id': classroom_id
    }, room=room_name, skip_sid=sid)
