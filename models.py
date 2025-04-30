from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, LargeBinary, DateTime
from sqlalchemy.orm import relationship, sessionmaker, declarative_base
from datetime import datetime

DATABASE_URL = "mysql+pymysql://username:password@localhost/documentportal"  # Change this to your MySQL credentials

# Create SQLAlchemy engine and session
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()

# PanelMaster Model
class PanelMaster(Base):
    __tablename__ = "panel_master"
    panel_id = Column(Integer, primary_key=True, index=True)
    file_meta = relationship("FileMeta", back_populates="panel")

# FileMeta Model
class FileMeta(Base):
    __tablename__ = "file_meta"
    file_meta_id = Column(Integer, primary_key=True, index=True)
    panel_id = Column(Integer, ForeignKey("panel_master.panel_id"))
    file_name = Column(String)
    file_data = Column(LargeBinary)

    # Relationship to PanelMaster
    panel = relationship("PanelMaster", back_populates="file_meta")

# User Model
class User(Base):
    __tablename__ = "users"
    user_id = Column(Integer, primary_key=True, index=True)

# UserAssignment Model
class UserAssignment(Base):
    __tablename__ = "user_assignment"
    user_assignment_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id"))
    panel_id = Column(Integer, ForeignKey("panel_master.panel_id"))
    secret_code = Column(String)
    qr_code = Column(LargeBinary)

# UserScanLog Model
class UserScanLog(Base):
    __tablename__ = "user_scan_log"
    log_id = Column(Integer, primary_key=True, index=True)
    user_assignment_id = Column(Integer, ForeignKey("user_assignment.user_assignment_id"))
    scan_datetime = Column(DateTime, default=datetime.utcnow)

# Create tables in the database
Base.metadata.create_all(bind=engine)
