from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, Field


# ==================== Classroom Schemas ====================

class ClassroomCreate(BaseModel):
    """Schema for creating a new classroom."""
    name: str = Field(..., min_length=2, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)


class ClassroomUpdate(BaseModel):
    """Schema for updating a classroom."""
    name: Optional[str] = Field(None, min_length=2, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)


class ClassroomEnroll(BaseModel):
    """Schema for enrolling in a classroom."""
    class_code: str = Field(..., min_length=6, max_length=10)


class TeacherInfo(BaseModel):
    """Schema for teacher information in classroom response."""
    id: int
    full_name: str
    email: str
    
    class Config:
        from_attributes = True


class StudentInfo(BaseModel):
    """Schema for student information in classroom response."""
    id: int
    full_name: str
    email: str
    
    class Config:
        from_attributes = True


class ClassroomResponse(BaseModel):
    """Schema for classroom response."""
    id: int
    name: str
    description: Optional[str]
    class_code: str
    teacher_id: int
    created_at: datetime
    teacher: Optional[TeacherInfo] = None
    student_count: int = 0
    
    class Config:
        from_attributes = True


class ClassroomDetailResponse(BaseModel):
    """Schema for detailed classroom response with students."""
    id: int
    name: str
    description: Optional[str]
    class_code: str
    teacher_id: int
    created_at: datetime
    teacher: Optional[TeacherInfo] = None
    students: List[StudentInfo] = []
    student_count: int = 0
    
    class Config:
        from_attributes = True


class ClassroomListResponse(BaseModel):
    """Schema for list of classrooms."""
    classrooms: List[ClassroomResponse]
    total: int


# ==================== Material Schemas ====================

class MaterialCreate(BaseModel):
    """Schema for creating material metadata."""
    title: str = Field(..., min_length=2, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)


class MaterialResponse(BaseModel):
    """Schema for material response."""
    id: int
    title: str
    description: Optional[str]
    file_name: str
    file_type: str
    file_size: int
    classroom_id: int
    uploaded_by: int
    uploaded_at: datetime
    uploader_name: Optional[str] = None
    
    class Config:
        from_attributes = True


class MaterialListResponse(BaseModel):
    """Schema for list of materials."""
    materials: List[MaterialResponse]
    total: int
