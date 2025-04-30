from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, LargeBinary, DateTime
from sqlalchemy.orm import relationship, sessionmaker, declarative_base
from datetime import datetime
from database import SessionLocal, Base, engine


# ------------------ MODELS ------------------

class PortalUser(Base):
    __tablename__ = "portal_user"
    portal_user_id = Column(Integer, primary_key=True, index=True)
    portal_user_name = Column(String(255), unique=True, nullable=False)
    password = Column(String(255), nullable=False)
    
class PanelMaster(Base):
    __tablename__ = "panel_master"
    panel_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    panel_name = Column(String)
    description = Column(String)
    file_meta = relationship("FileMeta", back_populates="panel")

class FileMeta(Base):
    __tablename__ = "file_meta"
    file_meta_id = Column(Integer, primary_key=True, index=True)
    panel_id = Column(Integer, ForeignKey("panel_master.panel_id"))
    file_name = Column(String)
    file_data = Column(LargeBinary)
    panel = relationship("PanelMaster", back_populates="file_meta")

class User(Base):
    __tablename__ = "users"
    user_id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    email_id = Column(String)
    phone_number = Column(String)

class UserAssignment(Base):
    __tablename__ = "user_assignment"
    user_assignment_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id"))
    panel_id = Column(Integer, ForeignKey("panel_master.panel_id"))
    secret_code = Column(String)
    qr_code = Column(LargeBinary)

class UserScanLog(Base):
    __tablename__ = "user_scan_log"
    log_id = Column(Integer, primary_key=True, index=True)
    user_assignment_id = Column(Integer, ForeignKey("user_assignment.user_assignment_id"))
    scan_datetime = Column(DateTime, default=datetime.utcnow)

Base.metadata.create_all(bind=engine)
