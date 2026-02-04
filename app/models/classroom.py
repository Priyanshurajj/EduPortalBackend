from datetime import datetime, timezone
import secrets
import string

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Table
from sqlalchemy.orm import relationship
from app.database.connection import Base


def generate_class_code(length: int = 6) -> str:
    """Generate a unique class code."""
    characters = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(characters) for _ in range(length))


# Association table for many-to-many relationship between students and classrooms
student_classroom = Table(
    'student_classroom',
    Base.metadata,
    Column('student_id', Integer, ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
    Column('classroom_id', Integer, ForeignKey('classrooms.id', ondelete='CASCADE'), primary_key=True),
    Column('enrolled_at', DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
)


class Classroom(Base):
    """Classroom model for class management."""
    
    __tablename__ = "classrooms"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    class_code = Column(String(10), unique=True, index=True, nullable=False, default=generate_class_code)
    teacher_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    created_at = Column(
        DateTime(timezone=True), 
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    
    # Relationships
    teacher = relationship("User", backref="taught_classes", foreign_keys=[teacher_id])
    students = relationship(
        "User",
        secondary=student_classroom,
        backref="enrolled_classes"
    )
    materials = relationship("Material", back_populates="classroom", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Classroom(id={self.id}, name='{self.name}', code='{self.class_code}')>"


class Material(Base):
    """Material model for class resources/files."""
    
    __tablename__ = "materials"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    file_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_type = Column(String(50), nullable=False)  # pdf, txt, etc.
    file_size = Column(Integer, nullable=False)  # in bytes
    classroom_id = Column(Integer, ForeignKey('classrooms.id', ondelete='CASCADE'), nullable=False)
    uploaded_by = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    uploaded_at = Column(
        DateTime(timezone=True), 
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    
    # Relationships
    classroom = relationship("Classroom", back_populates="materials")
    uploader = relationship("User", backref="uploaded_materials")
    
    def __repr__(self):
        return f"<Material(id={self.id}, title='{self.title}', classroom_id={self.classroom_id})>"
