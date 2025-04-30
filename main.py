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
from models import PanelMaster, PortalUser, FileMeta, User, UserAssignment, UserScanLog
from auth import verify_password, create_access_token, get_password_hash, get_assignment_id_from_token
from fastapi.middleware.cors import CORSMiddleware
from typing import List
import secrets
import string
import qrcode
import base64

app = FastAPI()

# Add this CORS configuration
origins = [
    "http://localhost:3000",  # React app
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,    # or ["*"] for all origins (use only for testing)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class LoginRequest(BaseModel):
    portal_user_name: str
    password: str

class GetFilesRequest(BaseModel):
    access_token: str
    
class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    
class FileInfo(BaseModel):
    file_meta_id: int
    file_name: str

class FilesDetail(BaseModel):
    user_assignment_id: int
    user_id: int
    files: List[FileInfo]

# ------------------ SCHEMAS ------------------

class PanelCreate(BaseModel):
    panel_name: str
    description: str

class UserCreate(BaseModel):
    name: str
    email_id: str
    phone_number: str

class FileMetaResponse(BaseModel):
    file_meta_id: int
    panel_id: int
    file_name: str

    class Config:
        orm_mode = True

class UserAssignmentCreate(BaseModel):
    user_id: int
    panel_id: int

    class Config:
        orm_mode = True

class UserAssignmentResponse(BaseModel):
    user_assignment_id: int
    user_id: int
    panel_id: int
    secret_code: str
    qr_code: bytes

    class Config:
        orm_mode = True

class UserDetails(BaseModel):
    user_id: int
    user_name: str
    email_id: str
    panel_id: int
    panel_name: str
    secret_code: str
    qr_code_base64: str  # base64 string for frontend

    class Config:
        orm_mode = True



# ------------------ Secret Code Generation ------------------
def generate_secret_code(length: int = 8) -> str:
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def generate_qr_code_bytes(url: str) -> bytes:
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    byte_stream = BytesIO()
    img.save(byte_stream, format='PNG')
    return byte_stream.getvalue()
    
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
    user = db.query(PortalUser).filter(PortalUser.portal_user_name == request.portal_user_name).first()
    if not user or not verify_password(request.password, user.password):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    access_token = create_access_token(data={"sub": user.portal_user_name})
    return {"access_token": access_token}


@app.post("/get-assigned-files", response_model=FilesDetail)
def login(request: GetFilesRequest, db: Session = Depends(get_db)):
    assignment_id = get_assignment_id_from_token(request.access_token)
    print(assignment_id)
    assignment = db.query(UserAssignment).filter(UserAssignment.user_assignment_id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=401, detail="Expired or Invalid access")

    # Get files by panel ID
    file_records = db.query(FileMeta).filter(FileMeta.panel_id == assignment.panel_id).all()

    files = [
        {"file_meta_id": f.file_meta_id, "file_name": f.file_name}
        for f in file_records
    ]

    return {
        "user_assignment_id": assignment.user_assignment_id,
        "user_id": assignment.user_id,
        "files": files,
    }

@app.get("/panel-files/{panel_id}", response_model=List[FileMetaResponse])
def get_files_by_panel(panel_id: int, db: Session = Depends(get_db)):
    files = db.query(FileMeta.file_meta_id, FileMeta.panel_id, FileMeta.file_name).filter(FileMeta.panel_id == panel_id).all()
    if not files:
        raise HTTPException(status_code=404, detail="No files found for this panel")
    return files

@app.get("/view-file/{file_meta_id}")
def view_file(file_meta_id: int, db: Session = Depends(get_db)):
    file = db.query(FileMeta).filter(FileMeta.file_meta_id == file_meta_id).first()
    if not file:
        raise HTTPException(status_code=404, detail="File not found")

    return StreamingResponse(BytesIO(file.file_data), media_type="application/pdf", headers={
        "Content-Disposition": f"inline; filename={file.file_name}"
    })
    
@app.post("/upload-file/")
def upload_file(panel_id: int = Form(...), file: UploadFile = File(...), db: Session = Depends(get_db)):
    contents = file.file.read()
    file_meta = FileMeta(panel_id=panel_id, file_name=file.filename, file_data=contents)
    db.add(file_meta)
    db.commit()
    return {"message": "File uploaded"}

@app.get("/view-file1/{assignment_id}")
def view_file(assignment_id: int, secret_code: str, db: Session = Depends(get_db)):
    assignment = db.query(UserAssignment).filter_by(user_assignment_id=assignment_id).first()
    if not assignment or assignment.secret_code != secret_code:
        raise HTTPException(status_code=403, detail="Invalid secret code")

    file_meta = db.query(FileMeta).filter_by(panel_id=assignment.panel_id).first()
    if not file_meta:
        raise HTTPException(status_code=404, detail="File not found")

    return StreamingResponse(BytesIO(file_meta.file_data), media_type="application/pdf", headers={"Content-Disposition": f"inline; filename={file_meta.file_name}"})

@app.post("/verify-secret/{secret_code}")
def verify_secret(secret_code: str, db: Session = Depends(get_db)):
    assignment = db.query(UserAssignment).filter_by(secret_code=secret_code).first()
    if assignment and assignment.secret_code == secret_code:
        user = db.query(User).filter_by(user_id=assignment.user_id).first()
        access_token = create_access_token(data={"name": user.name,"user_id":user.user_id,"assignment":assignment.user_assignment_id})
        return {"status": "verified","access_token":access_token}
    raise HTTPException(status_code=403, detail="Invalid secret code")

@app.post("/panels")
def create_panel(panel: PanelCreate, db: Session = Depends(get_db)):
    db_panel = PanelMaster(panel_name=panel.panel_name, description=panel.description)
    db.add(db_panel)
    db.commit()
    db.refresh(db_panel)
    return db_panel

@app.get("/panels")
def read_panels(db: Session = Depends(get_db)):
    return db.query(PanelMaster).all()

@app.post("/users")
def create_user(user: UserCreate, db: Session = Depends(get_db)):
    db_user = User(name=user.name,email_id=user.email_id,phone_number=user.phone_number)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

@app.post("/user-assignment")
def create_user_assignment(payload: UserAssignmentCreate, db: Session = Depends(get_db)):
    secret_code = generate_secret_code()
    file_url = f"http://localhost:8000/files/{payload.panel_id}?code={secret_code}"
    qr_code_bytes = generate_qr_code_bytes(file_url)

    assignment = UserAssignment(
        user_id=payload.user_id,
        panel_id=payload.panel_id,
        secret_code=secret_code,
        qr_code=qr_code_bytes,
    )

    db.add(assignment)
    db.commit()
    db.refresh(assignment)

    return {
        "user_assignment_id": assignment.user_assignment_id,
        "secret_code": assignment.secret_code
    }

@app.get("/users")
def read_users(db: Session = Depends(get_db)):
    return db.query(User).all()

@app.get("/user-details", response_model=List[UserDetails])
def get_user_assignments(db: Session = Depends(get_db)):
    assignments = (
        db.query(UserAssignment, User, PanelMaster)
        .join(User, User.user_id == UserAssignment.user_id)
        .join(PanelMaster, PanelMaster.panel_id == UserAssignment.panel_id)
        .all()
    )

    results = []
    for assignment, user, panel in assignments:
        qr_base64 = base64.b64encode(assignment.qr_code).decode('utf-8') if assignment.qr_code else ""
        results.append({
            "user_id": user.user_id,
            "user_name": user.name,
            "email_id": user.email_id,
            "panel_id": panel.panel_id,
            "panel_name": panel.panel_name,
            "secret_code": assignment.secret_code,
            "qr_code_base64": qr_base64,
        })

    return results

# ------------------ RUN ------------------
# Uncomment below to run directly
# if __name__ == "__main__":
#     uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
