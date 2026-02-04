import os
import shutil
from typing import List
import uuid

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import get_current_user
from app.database import get_db
from app.models.user import User, UserRole
from app.models.classroom import Classroom, Material, generate_class_code
from app.schemas.classroom import (
    ClassroomCreate,
    ClassroomUpdate,
    ClassroomEnroll,
    ClassroomResponse,
    ClassroomDetailResponse,
    ClassroomListResponse,
    MaterialResponse,
    MaterialListResponse,
    TeacherInfo,
    StudentInfo,
)

router = APIRouter(prefix="/api/classrooms", tags=["Classrooms"])

# Create uploads directory
UPLOAD_DIR = "uploads/materials"
os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_EXTENSIONS = {'.pdf', '.txt', '.doc', '.docx', '.ppt', '.pptx', '.xls', '.xlsx'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


def get_teacher_user(current_user: User = Depends(get_current_user)) -> User:
    """Dependency to ensure the user is a teacher."""
    if current_user.role != UserRole.TEACHER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only teachers can perform this action"
        )
    return current_user


def get_student_user(current_user: User = Depends(get_current_user)) -> User:
    """Dependency to ensure the user is a student."""
    if current_user.role != UserRole.STUDENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only students can perform this action"
        )
    return current_user


def classroom_to_response(classroom: Classroom) -> ClassroomResponse:
    """Convert Classroom model to ClassroomResponse."""
    return ClassroomResponse(
        id=classroom.id,
        name=classroom.name,
        description=classroom.description,
        class_code=classroom.class_code,
        teacher_id=classroom.teacher_id,
        created_at=classroom.created_at,
        teacher=TeacherInfo(
            id=classroom.teacher.id,
            full_name=classroom.teacher.full_name,
            email=classroom.teacher.email
        ) if classroom.teacher else None,
        student_count=len(classroom.students)
    )


# ==================== Teacher Endpoints ====================

@router.post(
    "/create",
    response_model=ClassroomResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new classroom",
    description="Create a new classroom (Teacher only). A unique class code will be generated."
)
async def create_classroom(
    classroom_data: ClassroomCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_teacher_user)
) -> ClassroomResponse:
    """Create a new classroom with a unique class code."""
    
    # Generate unique class code
    class_code = generate_class_code()
    while db.query(Classroom).filter(Classroom.class_code == class_code).first():
        class_code = generate_class_code()
    
    new_classroom = Classroom(
        name=classroom_data.name,
        description=classroom_data.description,
        class_code=class_code,
        teacher_id=current_user.id
    )
    
    db.add(new_classroom)
    db.commit()
    db.refresh(new_classroom)
    
    return classroom_to_response(new_classroom)


@router.get(
    "/my-classes",
    response_model=ClassroomListResponse,
    summary="Get my classrooms",
    description="Get all classrooms for the current user (taught classes for teachers, enrolled classes for students)."
)
async def get_my_classrooms(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> ClassroomListResponse:
    """Get classrooms based on user role."""
    
    if current_user.role == UserRole.TEACHER:
        classrooms = db.query(Classroom).filter(
            Classroom.teacher_id == current_user.id
        ).order_by(Classroom.created_at.desc()).all()
    else:
        classrooms = current_user.enrolled_classes
    
    return ClassroomListResponse(
        classrooms=[classroom_to_response(c) for c in classrooms],
        total=len(classrooms)
    )


@router.get(
    "/{classroom_id}",
    response_model=ClassroomDetailResponse,
    summary="Get classroom details",
    description="Get detailed information about a classroom including students."
)
async def get_classroom(
    classroom_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> ClassroomDetailResponse:
    """Get classroom details."""
    
    classroom = db.query(Classroom).filter(Classroom.id == classroom_id).first()
    if not classroom:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Classroom not found"
        )
    
    # Check access: teacher of the class or enrolled student
    is_teacher = classroom.teacher_id == current_user.id
    is_enrolled = current_user in classroom.students
    
    if not is_teacher and not is_enrolled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this classroom"
        )
    
    return ClassroomDetailResponse(
        id=classroom.id,
        name=classroom.name,
        description=classroom.description,
        class_code=classroom.class_code,
        teacher_id=classroom.teacher_id,
        created_at=classroom.created_at,
        teacher=TeacherInfo(
            id=classroom.teacher.id,
            full_name=classroom.teacher.full_name,
            email=classroom.teacher.email
        ) if classroom.teacher else None,
        students=[
            StudentInfo(id=s.id, full_name=s.full_name, email=s.email)
            for s in classroom.students
        ],
        student_count=len(classroom.students)
    )


@router.put(
    "/{classroom_id}",
    response_model=ClassroomResponse,
    summary="Update classroom",
    description="Update classroom details (Teacher only)."
)
async def update_classroom(
    classroom_id: int,
    classroom_data: ClassroomUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_teacher_user)
) -> ClassroomResponse:
    """Update a classroom."""
    
    classroom = db.query(Classroom).filter(Classroom.id == classroom_id).first()
    if not classroom:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Classroom not found"
        )
    
    if classroom.teacher_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update your own classrooms"
        )
    
    if classroom_data.name is not None:
        classroom.name = classroom_data.name
    if classroom_data.description is not None:
        classroom.description = classroom_data.description
    
    db.commit()
    db.refresh(classroom)
    
    return classroom_to_response(classroom)


@router.delete(
    "/{classroom_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete classroom",
    description="Delete a classroom and all its materials (Teacher only)."
)
async def delete_classroom(
    classroom_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_teacher_user)
):
    """Delete a classroom."""
    
    classroom = db.query(Classroom).filter(Classroom.id == classroom_id).first()
    if not classroom:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Classroom not found"
        )
    
    if classroom.teacher_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete your own classrooms"
        )
    
    # Delete material files
    for material in classroom.materials:
        if os.path.exists(material.file_path):
            os.remove(material.file_path)
    
    db.delete(classroom)
    db.commit()


# ==================== Student Endpoints ====================

@router.post(
    "/enroll",
    response_model=ClassroomResponse,
    summary="Enroll in a classroom",
    description="Enroll in a classroom using the class code (Student only)."
)
async def enroll_in_classroom(
    enroll_data: ClassroomEnroll,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_student_user)
) -> ClassroomResponse:
    """Enroll in a classroom using class code."""
    
    classroom = db.query(Classroom).filter(
        Classroom.class_code == enroll_data.class_code.upper()
    ).first()
    
    if not classroom:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid class code. Classroom not found."
        )
    
    if current_user in classroom.students:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You are already enrolled in this classroom"
        )
    
    classroom.students.append(current_user)
    db.commit()
    db.refresh(classroom)
    
    return classroom_to_response(classroom)


@router.delete(
    "/{classroom_id}/unenroll",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Unenroll from a classroom",
    description="Unenroll from a classroom (Student only)."
)
async def unenroll_from_classroom(
    classroom_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_student_user)
):
    """Unenroll from a classroom."""
    
    classroom = db.query(Classroom).filter(Classroom.id == classroom_id).first()
    if not classroom:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Classroom not found"
        )
    
    if current_user not in classroom.students:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You are not enrolled in this classroom"
        )
    
    classroom.students.remove(current_user)
    db.commit()


# ==================== Material Endpoints ====================

@router.post(
    "/{classroom_id}/materials",
    response_model=MaterialResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload material",
    description="Upload a material file to a classroom (Teacher only)."
)
async def upload_material(
    classroom_id: int,
    title: str = Form(...),
    description: str = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_teacher_user)
) -> MaterialResponse:
    """Upload a material to a classroom."""
    
    classroom = db.query(Classroom).filter(Classroom.id == classroom_id).first()
    if not classroom:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Classroom not found"
        )
    
    if classroom.teacher_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only upload materials to your own classrooms"
        )
    
    # Validate file extension
    file_ext = os.path.splitext(file.filename or "")[1].lower()
    
    # If no extension in filename, try to infer from content type
    if not file_ext and file.content_type:
        content_type_to_ext = {
            "application/pdf": ".pdf",
            "text/plain": ".txt",
            "application/msword": ".doc",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
            "application/vnd.ms-excel": ".xls",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
            "application/vnd.ms-powerpoint": ".ppt",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation": ".pptx"
        }
        file_ext = content_type_to_ext.get(file.content_type, "")
    
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type not allowed. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}. Received: {file.filename or 'unknown'} (extension: {file_ext or 'none'})"
        )
    
    # Read file content to check size
    content = await file.read()
    file_size = len(content)
    
    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File too large. Maximum size is {MAX_FILE_SIZE // (1024*1024)} MB"
        )
    
    # Create classroom directory
    classroom_dir = os.path.join(UPLOAD_DIR, str(classroom_id))
    os.makedirs(classroom_dir, exist_ok=True)
    
    # Generate unique filename
    unique_filename = f"{uuid.uuid4().hex}_{file.filename}"
    file_path = os.path.join(classroom_dir, unique_filename)
    
    # Save file
    with open(file_path, "wb") as f:
        f.write(content)
    
    # Create material record
    material = Material(
        title=title,
        description=description,
        file_name=file.filename,
        file_path=file_path,
        file_type=file_ext.replace('.', ''),
        file_size=file_size,
        classroom_id=classroom_id,
        uploaded_by=current_user.id
    )
    
    db.add(material)
    db.commit()
    db.refresh(material)
    
    return MaterialResponse(
        id=material.id,
        title=material.title,
        description=material.description,
        file_name=material.file_name,
        file_type=material.file_type,
        file_size=material.file_size,
        classroom_id=material.classroom_id,
        uploaded_by=material.uploaded_by,
        uploaded_at=material.uploaded_at,
        uploader_name=current_user.full_name
    )


@router.get(
    "/{classroom_id}/materials",
    response_model=MaterialListResponse,
    summary="Get classroom materials",
    description="Get all materials for a classroom."
)
async def get_classroom_materials(
    classroom_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> MaterialListResponse:
    """Get all materials for a classroom."""
    
    classroom = db.query(Classroom).filter(Classroom.id == classroom_id).first()
    if not classroom:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Classroom not found"
        )
    
    # Check access
    is_teacher = classroom.teacher_id == current_user.id
    is_enrolled = current_user in classroom.students
    
    if not is_teacher and not is_enrolled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this classroom"
        )
    
    materials = db.query(Material).filter(
        Material.classroom_id == classroom_id
    ).order_by(Material.uploaded_at.desc()).all()
    
    return MaterialListResponse(
        materials=[
            MaterialResponse(
                id=m.id,
                title=m.title,
                description=m.description,
                file_name=m.file_name,
                file_type=m.file_type,
                file_size=m.file_size,
                classroom_id=m.classroom_id,
                uploaded_by=m.uploaded_by,
                uploaded_at=m.uploaded_at,
                uploader_name=m.uploader.full_name if m.uploader else None
            )
            for m in materials
        ],
        total=len(materials)
    )


@router.delete(
    "/{classroom_id}/materials/{material_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete material",
    description="Delete a material from a classroom (Teacher only)."
)
async def delete_material(
    classroom_id: int,
    material_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_teacher_user)
):
    """Delete a material."""
    
    material = db.query(Material).filter(
        Material.id == material_id,
        Material.classroom_id == classroom_id
    ).first()
    
    if not material:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Material not found"
        )
    
    if material.classroom.teacher_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete materials from your own classrooms"
        )
    
    # Delete file
    if os.path.exists(material.file_path):
        os.remove(material.file_path)
    
    db.delete(material)
    db.commit()


@router.get(
    "/{classroom_id}/materials/{material_id}/download",
    summary="Download material",
    description="Download a material file."
)
async def download_material(
    classroom_id: int,
    material_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Download a material file."""
    
    material = db.query(Material).filter(
        Material.id == material_id,
        Material.classroom_id == classroom_id
    ).first()
    
    if not material:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Material not found"
        )
    
    classroom = material.classroom
    
    # Check access
    is_teacher = classroom.teacher_id == current_user.id
    is_enrolled = current_user in classroom.students
    
    if not is_teacher and not is_enrolled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this material"
        )
    
    if not os.path.exists(material.file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found on server"
        )
    
    return FileResponse(
        path=material.file_path,
        filename=material.file_name,
        media_type="application/octet-stream"
    )
