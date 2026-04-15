from sqlalchemy import Column, Integer, String, Boolean, DateTime
from datetime import datetime
from Backend.database import Base

class Project(Base):
    __tablename__ = "projects"

    # Define the columns for the 'projects' table
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    path = Column(String, unique=True, index=True)  # Where it lives on your hard drive
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class IDEPath(Base):
    __tablename__ = "ide_paths"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)  # e.g., "VS Code" or "PyCharm"
    path = Column(String)              # e.g., "C:/Program Files/.../Code.exe"