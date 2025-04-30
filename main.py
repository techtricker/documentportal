from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, LargeBinary, DateTime
from sqlalchemy.orm import sessionmaker, relationship, declarative_base, Session
from datetime import datetime
from io import BytesIO
import uvicorn
from database import SessionLocal, Base, engine
from pydantic import BaseModel
from fastapi.security import OAuth2PasswordRequestForm

app = FastAPI()

class LoginRequest(BaseModel):
    portal_user_name: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

# ------------------ MODELS ------------------

class PortalUser(Base):
    __tablename__ = "portal_user"
    portal_user_id = Column(Integer, primary_key=True, index=True)
    portal_user_name = Column(String(255), unique=True, nullable=False)
    password = Column(String(255), nullable=False)
    
class PanelMaster(Base):
    __tablename__ = "panel_master"
    panel_id = Column(Integer, primary_key=True, index=True)
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

# ------------------ SCHEMAS ------------------

class PanelCreate(BaseModel):
    panel_id: int

class UserCreate(BaseModel):
    user_id: int

# ------------------ DEPENDENCY ------------------

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ------------------ ENDPOINTS ------------------

@app.post("/login", response_model=TokenResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(models.PortalUser).filter(models.PortalUser.portal_user_name == request.portal_user_name).first()
    if not user or not verify_password(request.password, user.password):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    access_token = create_access_token(data={"sub": user.portal_user_name})
    return {"access_token": access_token}

@app.post("/upload-file/")
def upload_file(panel_id: int = Form(...), file: UploadFile = File(...), db: Session = Depends(get_db)):
    contents = file.file.read()
    file_meta = FileMeta(panel_id=panel_id, file_name=file.filename, file_data=contents)
    db.add(file_meta)
    db.commit()
    return {"message": "File uploaded"}

@app.get("/view-file/{assignment_id}")
def view_file(assignment_id: int, secret_code: str, db: Session = Depends(get_db)):
    assignment = db.query(UserAssignment).filter_by(user_assignment_id=assignment_id).first()
    if not assignment or assignment.secret_code != secret_code:
        raise HTTPException(status_code=403, detail="Invalid secret code")

    file_meta = db.query(FileMeta).filter_by(panel_id=assignment.panel_id).first()
    if not file_meta:
        raise HTTPException(status_code=404, detail="File not found")

    return StreamingResponse(BytesIO(file_meta.file_data), media_type="application/pdf", headers={"Content-Disposition": f"inline; filename={file_meta.file_name}"})

@app.post("/verify-secret/{assignment_id}")
def verify_secret(assignment_id: int, secret_code: str = Form(...), db: Session = Depends(get_db)):
    assignment = db.query(UserAssignment).filter_by(user_assignment_id=assignment_id).first()
    if assignment and assignment.secret_code == secret_code:
        return {"status": "verified"}
    raise HTTPException(status_code=403, detail="Invalid secret code")

@app.post("/panels")
def create_panel(panel: PanelCreate, db: Session = Depends(get_db)):
    db_panel = PanelMaster(panel_id=panel.panel_id)
    db.add(db_panel)
    db.commit()
    db.refresh(db_panel)
    return db_panel

@app.get("/panels")
def read_panels(db: Session = Depends(get_db)):
    return db.query(PanelMaster).all()

@app.post("/users")
def create_user(user: UserCreate, db: Session = Depends(get_db)):
    db_user = User(user_id=user.user_id)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

@app.get("/users")
def read_users(db: Session = Depends(get_db)):
    return db.query(User).all()

# ------------------ RUN ------------------
# Uncomment below to run directly
# if __name__ == "__main__":
#     uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
