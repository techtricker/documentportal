from sqlalchemy import Boolean, create_engine, Column, Integer, String, ForeignKey, LargeBinary, DateTime
from sqlalchemy.orm import relationship, sessionmaker, declarative_base
from datetime import datetime
from database import SessionLocal, Base, engine
import pytz

IST = pytz.timezone("Asia/Kolkata")

def get_ist_datetime():
    return datetime.now(IST)

# ------------------ MODELS ------------------

class PortalUser(Base):
    __tablename__ = "portal_user"
    portal_user_id = Column(Integer, primary_key=True, index=True)
    portal_user_name = Column(String(255), unique=True, nullable=False)
    password = Column(String(255), nullable=False)
    
class PanelMaster(Base):
    __tablename__ = "panel_master"
    panel_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    panel_name = Column(String(255))
    description = Column(String(1000))
    is_deleted = Column(Boolean, default=False)
    file_meta = relationship("FileMeta", back_populates="panel")

class FileMeta(Base):
    __tablename__ = "file_meta"
    file_meta_id = Column(Integer, primary_key=True, index=True)
    panel_id = Column(Integer, ForeignKey("panel_master.panel_id"))
    file_name = Column(String(255))
    is_deleted = Column(Boolean, default=False)
    panel = relationship("PanelMaster", back_populates="file_meta")

class User(Base):
    __tablename__ = "users"
    user_id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255))
    email_id = Column(String(255))
    phone_number = Column(String(20))

class UserAssignment(Base):
    __tablename__ = "user_assignment"
    user_assignment_id = Column(Integer, primary_key=True, index=True)
    secret_code = Column(String(255))
    qr_code = Column(LargeBinary)
    user_id = Column(Integer, nullable=True)
    panel_id = Column(Integer, ForeignKey("panel_master.panel_id"))
    # NEW (for panel-level access)
    visitor_name = Column(String(100), nullable=True)
    visitor_email = Column(String(150), nullable=True)
    visitor_phone = Column(String(20), nullable=True)
    is_temporary = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)



class UserScanLog(Base):
    __tablename__ = "user_scan_log"
    log_id = Column(Integer, primary_key=True, index=True)
    user_assignment_id = Column(Integer, ForeignKey("user_assignment.user_assignment_id"))
    scan_datetime = Column(DateTime)
    verification_status = Column(String(100))  # e.g., 'success', 'failed'
    created_at = Column(DateTime, default=datetime.utcnow)

class OtpChallenge(Base):
    __tablename__ = "otp_challenge"
    otp_id = Column(Integer, primary_key=True, index=True)
    user_assignment_id = Column(Integer, ForeignKey("user_assignment.user_assignment_id"), nullable=False, index=True)
    otp_hash = Column(String(255), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    attempts = Column(Integer, default=0, nullable=False)
    max_attempts = Column(Integer, default=5, nullable=False)
    consumed = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


Base.metadata.create_all(bind=engine)
