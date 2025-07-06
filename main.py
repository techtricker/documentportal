from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, LargeBinary, DateTime, text
from sqlalchemy.orm import sessionmaker, relationship, declarative_base, Session
from datetime import datetime
from io import BytesIO
import uvicorn
from database import SessionLocal, Base, engine
from pydantic import BaseModel
from fastapi.security import OAuth2PasswordRequestForm
from models import PanelMaster, PortalUser, FileMeta, User, UserAssignment, UserScanLog
from auth import verify_token, verify_password, create_access_token, get_password_hash, get_assignment_id_from_token
from fastapi.middleware.cors import CORSMiddleware
from typing import List
import secrets
import string
import qrcode
import base64
import os
import hashlib

app = FastAPI()

# Add this CORS configuration
origins = [
    "http://localhost:3000",  # React app
    "http://document-portal-tt.s3-website.ap-south-1.amazonaws.com"
]

PANEL_BASE_DIR = "../panels"
WEBAPP_URL = "http://localhost:3000/#/"

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
    panel_name: str
    files: List[FileInfo]

# ------------------ SCHEMAS ------------------

class PanelAssignment(BaseModel):
    panel_id: int

class UserBase(BaseModel):
    name: str
    email_id: str
    phone_number: str

class UserCreate(UserBase):
    panels: List[PanelAssignment]

class UserUpdate(UserCreate):
    pass

class PanelCreate(BaseModel):
    panel_name: str
    description: str

class UserPanelList(BaseModel):
    panel_name: str

# class UserCreate(BaseModel):
#     name: str
#     email_id: str
#     phone_number: str
#     panels: List[UserPanelList]

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

class PanelUpdate(BaseModel):
    panel_name: str
    description: str

# class UserUpdate(BaseModel):
#     name: str
#     email_id: str
#     phone_number: str

class ScanLogRequest(BaseModel):
    user_assignment_id: int
    secret_code: str
    verification_status: str

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

# ------------------ Functions ------------------
def sync_panels_and_files(db: Session):
    # Step 1: Read current panel folders from disk
    actual_panels = {
        panel_name: os.path.join(PANEL_BASE_DIR, panel_name)
        for panel_name in os.listdir(PANEL_BASE_DIR)
        if os.path.isdir(os.path.join(PANEL_BASE_DIR, panel_name))
    }

    # Step 2: Fetch all existing panels from DB
    db_panels = db.query(PanelMaster).all()
    db_panel_map = {p.panel_name: p for p in db_panels}

    actual_panel_names = set(actual_panels.keys())
    db_panel_names = set(db_panel_map.keys())

    # Step 3: Mark deleted panels (present in DB but not on disk)
    panels_to_delete = db_panel_names - actual_panel_names
    for pname in panels_to_delete:
        db_panel_map[pname].is_deleted = True

    # Step 4: Add new panels and files
    for panel_name, panel_path in actual_panels.items():
        if panel_name not in db_panel_map:
            # New Panel
            new_panel = PanelMaster(panel_name=panel_name, description="", is_deleted=False)
            db.add(new_panel)
            db.commit()
            db.refresh(new_panel)
            db_panel_map[panel_name] = new_panel
        else:
            # Reactivate if it was previously marked deleted
            if db_panel_map[panel_name].is_deleted:
                db_panel_map[panel_name].is_deleted = False

        panel_id = db_panel_map[panel_name].panel_id

        # Fetch file records for this panel
        existing_files = db.query(FileMeta).filter(FileMeta.panel_id == panel_id).all()
        existing_file_names = {f.file_name: f for f in existing_files}

        # Files from disk
        actual_file_names = set()
        for fname in os.listdir(panel_path):
            file_path = os.path.join(panel_path, fname)
            if os.path.isfile(file_path):
                actual_file_names.add(fname)
                if fname not in existing_file_names:
                    # New file
                    new_file = FileMeta(panel_id=panel_id, file_name=fname, is_deleted=False)
                    db.add(new_file)
                else:
                    # Reactivate if deleted
                    file = existing_file_names[fname]
                    if file.is_deleted:
                        file.is_deleted = False

        # Mark missing files as deleted
        db_file_names = set(existing_file_names.keys())
        deleted_files = db_file_names - actual_file_names
        for missing_fname in deleted_files:
            existing_file_names[missing_fname].is_deleted = True

    db.commit()

#------------------- APIs -------------------------

#### Panel APIs

@app.get("/sync-panels-manually")
def manual_sync(db: Session = Depends(get_db)):
    sync_panels_and_files(db)
    return {"message": "Panels and files synced successfully"}

# @app.get("/panels")
# def get_panels_from_folders(str = Depends(verify_token)):
#     panels = []
#     for folder_name in os.listdir(PANEL_BASE_DIR):
#         full_path = os.path.join(PANEL_BASE_DIR, folder_name)
#         if os.path.isdir(full_path):
#             # Create deterministic short hash as panel_id
#             hash_bytes = hashlib.sha256(folder_name.encode()).digest()
#             short_id = base64.urlsafe_b64encode(hash_bytes[:6]).decode('utf-8').rstrip('=')

#             # Count files in the folder
#             file_names = [
#                 f for f in os.listdir(full_path)
#                 if os.path.isfile(os.path.join(full_path, f))
#             ]

#             panels.append({
#                 "panel_id": short_id,
#                 "panel_name": folder_name,
#                 "panel_path": os.path.abspath(full_path),
#                 "file_count": len(file_names),
#                 "files": file_names
#             })

#     return panels

## str = Depends(verify_token)

@app.get("/panels")
def get_panels(db: Session = Depends(get_db), str = Depends(verify_token)):
    panels = []

    # Fetch all active (non-deleted) panels
    db_panels = db.query(PanelMaster).filter(PanelMaster.is_deleted == False).all()

    for panel in db_panels:
        # Fetch non-deleted files for this panel
        file_records = db.query(FileMeta).filter(
            FileMeta.panel_id == panel.panel_id,
            FileMeta.is_deleted == False
        ).all()

        # Build file list with id and name
        file_list = [
            {
                "file_meta_id": f.file_meta_id,
                "file_name": f.file_name
            }
            for f in file_records
        ]

        panels.append({
            "panel_id": panel.panel_id,
            "panel_name": panel.panel_name,
            "file_count": len(file_records),
            "files": file_list
        })

    return panels




#### Authentication APIs

@app.post("/login", response_model=TokenResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(PortalUser).filter(PortalUser.portal_user_name == request.portal_user_name).first()
    if not user or not verify_password(request.password, user.password):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    access_token = create_access_token(data={"sub": user.portal_user_name})
    return {"access_token": access_token}


#### Application APIs

@app.get("/admin-dashboard")
def get_dashboard_summary(db: Session = Depends(get_db)):
    result = db.execute(text("SELECT metrics_json FROM dashboard_summary_view")).fetchone()
    return {"dashboard": result[0]}


#### User APIs


@app.get("/users")
def read_users(db: Session = Depends(get_db)):
    return db.query(User).all()

@app.get("/user-details")
def get_user_assignments(db: Session = Depends(get_db)):
    assignments = (
        db.query(UserAssignment, User, PanelMaster)
        .join(User, User.user_id == UserAssignment.user_id)
        .join(PanelMaster, PanelMaster.panel_id == UserAssignment.panel_id)
        .all()
    )

    user_map = {}

    for assignment, user, panel in assignments:
        qr_base64 = base64.b64encode(assignment.qr_code).decode('utf-8') if assignment.qr_code else ""

        if user.user_id not in user_map:
            user_map[user.user_id] = {
                "user_id": user.user_id,
                "user_name": user.name,
                "email_id": user.email_id,
                "phone_number": user.phone_number,
                "assignments": []
            }

        user_map[user.user_id]["assignments"].append({
            "panel_id": panel.panel_id,
            "panel_name": panel.panel_name,
            "secret_code": assignment.secret_code,
            "qr_code_base64": qr_base64,
        })

    return list(user_map.values())

# @app.get("/user-details", response_model=List[UserDetails])
# def get_user_assignments(db: Session = Depends(get_db)):
#     assignments = (
#         db.query(UserAssignment, User, PanelMaster)
#         .join(User, User.user_id == UserAssignment.user_id)
#         .join(PanelMaster, PanelMaster.panel_id == UserAssignment.panel_id)
#         .all()
#     )

#     results = []
#     for assignment, user, panel in assignments:
#         qr_base64 = base64.b64encode(assignment.qr_code).decode('utf-8') if assignment.qr_code else ""
#         results.append({
#             "user_id": user.user_id,
#             "user_name": user.name,
#             "email_id": user.email_id,
#             "panel_id": panel.panel_id,
#             "panel_name": panel.panel_name,
#             "secret_code": assignment.secret_code,
#             "qr_code_base64": qr_base64,
#         })

#     return results

@app.delete("/users/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Optional: delete related assignments
    db.query(UserAssignment).filter(UserAssignment.user_id == user_id).delete()
    
    db.delete(user)
    db.commit()
    return {"message": f"User {user_id} deleted successfully"}

@app.post("/users")
def create_user(user: UserCreate, db: Session = Depends(get_db)):
    db_user = User(name=user.name,email_id=user.email_id,phone_number=user.phone_number)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    # Loop through assignments and create them
    for panel in user.panels:
        secret_code = generate_secret_code()
        # Proper base64 encoding of the secret code
        encoded_bytes = base64.b64encode(secret_code.encode('utf-8'))
        encoded_str = encoded_bytes.decode('utf-8')
        file_url = f"{WEBAPP_URL}verify-secret-code/{encoded_str}"
        qr_code_bytes = generate_qr_code_bytes(file_url)
        db_assignment = UserAssignment(
            user_id=db_user.user_id,
            panel_id=panel.panel_id,
            secret_code=secret_code,
            qr_code=qr_code_bytes
        )
        db.add(db_assignment)

    db.commit()
    return db_user



@app.put("/users/{user_id}")
def update_user(user_id: int, user_update: UserUpdate, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.name = user_update.name
    user.email_id = user_update.email_id
    user.phone_number = user_update.phone_number

    db.commit()
    db.refresh(user)

    # Get current & incoming panel names
    existing_assignments = db.query(UserAssignment).filter(UserAssignment.user_id == user.user_id).all()
    existing_panel_names = {a.panel_id for a in existing_assignments}
    new_panel_names = {p.panel_id for p in user_update.panels}

    # Delete removed panels
    panels_to_delete = existing_panel_names - new_panel_names
    if panels_to_delete:
        db.query(UserAssignment).filter(
            UserAssignment.user_id == user_id,
            UserAssignment.panel_id.in_(panels_to_delete)
        ).delete(synchronize_session=False)

    # Add new panels
    panels_to_add = new_panel_names - existing_panel_names
    for panel in user_update.panels:
        if panel.panel_id in panels_to_add:
            secret_code = generate_secret_code()
            encoded_str = base64.b64encode(secret_code.encode('utf-8')).decode('utf-8')
            file_url = f"{WEBAPP_URL}verify-secret-code/{encoded_str}"
            qr_code_bytes = generate_qr_code_bytes(file_url)

            db_assignment = UserAssignment(
                user_id=user_id,
                panel_id=panel.panel_id,
                secret_code=secret_code,
                qr_code=qr_code_bytes
            )
            db.add(db_assignment)

    db.commit()
    return {"message": f"User {user_id} updated successfully", "user": user}



# @app.post("/get-assigned-files", response_model=FilesDetail)
# def login(request: GetFilesRequest, db: Session = Depends(get_db)):
#     assignment_id = get_assignment_id_from_token(request.access_token)
#     print(assignment_id)
#     assignment = db.query(UserAssignment).filter(UserAssignment.user_assignment_id == assignment_id).first()
#     if not assignment:
#         raise HTTPException(status_code=401, detail="Expired or Invalid access")

#     # Get files by panel ID
#     file_records = db.query(FileMeta).filter(FileMeta.panel_id == assignment.panel_id).all()

#     files = [
#         {"file_meta_id": f.file_meta_id, "file_name": f.file_name}
#         for f in file_records
#     ]

#     return {
#         "user_assignment_id": assignment.user_assignment_id,
#         "user_id": assignment.user_id,
#         "files": files,
#     }

#### Verify Secret & View Files

@app.post("/user-scan-log")
def log_scan(request: ScanLogRequest, db: Session = Depends(get_db)):
    assignment = db.query(UserAssignment).filter_by(secret_code=request.secret_code).first()
    scan_log = UserScanLog(
        user_assignment_id=assignment.user_assignment_id,
        scan_datetime=datetime.utcnow,
        verification_status=request.verification_status
    )
    db.add(scan_log)
    db.commit()
    return {"message": "Scan log saved"}
    # userAssignId = request.user_assignment_id
    # if assignment:
    #     userAssignId = assignment.user_assignment_id
    
    # if userAssignId != 0:
    #     scan_log = UserScanLog(
    #         user_assignment_id=request.user_assignment_id,
    #         verification_status=request.verification_status
    #     )
    #     db.add(scan_log)
    #     db.commit()
    #     return {"message": "Scan log saved"}
    # raise HTTPException(status_code=500, detail="Internal Server Error")

@app.post("/verify-secret/{secret_code}")
def verify_secret(secret_code: str, db: Session = Depends(get_db)):
    assignment = db.query(UserAssignment).filter_by(secret_code=secret_code).first()
    if assignment and assignment.secret_code == secret_code:
        user = db.query(User).filter_by(user_id=assignment.user_id).first()
        access_token = create_access_token(data={"sub": user.name,"user_id":user.user_id,"assignment":assignment.user_assignment_id})
        scan_log = UserScanLog(
            user_assignment_id=assignment.user_assignment_id,
            verification_status="1"
        )
        db.add(scan_log)
        db.commit()
        return {"status": "verified","access_token":access_token}
    else:
        scan_log = UserScanLog(
            user_assignment_id=assignment.user_assignment_id,
            verification_status="2"
        )
        db.add(scan_log)
        db.commit()
    raise HTTPException(status_code=403, detail="Invalid secret code")

@app.post("/get-assigned-files", response_model=FilesDetail)
def get_assigned_files(request: GetFilesRequest, db: Session = Depends(get_db)):
    assignment_data = (
        db.query(UserAssignment, PanelMaster)
        .join(PanelMaster, PanelMaster.panel_id == UserAssignment.panel_id)
        .filter(UserAssignment.user_assignment_id == get_assignment_id_from_token(request.access_token))
        .first()
    )

    if not assignment_data:
        raise HTTPException(status_code=401, detail="Expired or Invalid access")

    assignment, panel = assignment_data  # Unpack tuple properly

    panel_folder = os.path.join(PANEL_BASE_DIR, panel.panel_name)

    if not os.path.exists(panel_folder) or not os.path.isdir(panel_folder):
        raise HTTPException(status_code=404, detail="Panel folder not found")

    file_names = os.listdir(panel_folder)

    files = [
        {"file_meta_id": idx + 1, "file_name": f}
        for idx, f in enumerate(file_names)
        if os.path.isfile(os.path.join(panel_folder, f))
    ]

    return {
        "user_assignment_id": assignment.user_assignment_id,
        "user_id": assignment.user_id,
        "files": files,
        "panel_name": panel.panel_name  # Use panel name from PanelMaster
    }


# @app.post("/get-assigned-files", response_model=FilesDetail)
# def get_assigned_files(request: GetFilesRequest, db: Session = Depends(get_db)):
#     assignment_id = get_assignment_id_from_token(request.access_token)
#     assignment = db.query(UserAssignment, PanelMaster).join(PanelMaster, PanelMaster.panel_id == UserAssignment.panel_id).filter(UserAssignment.user_assignment_id == assignment_id).first()
    
#     if not assignment:
#         raise HTTPException(status_code=401, detail="Expired or Invalid access")

#     panel_folder = os.path.join(PANEL_BASE_DIR, assignment.panel_name)

#     if not os.path.exists(panel_folder) or not os.path.isdir(panel_folder):
#         raise HTTPException(status_code=404, detail="Panel folder not found")

#     file_names = os.listdir(panel_folder)

#     files = [
#         {"file_meta_id": idx + 1, "file_name": f}
#         for idx, f in enumerate(file_names)
#         if os.path.isfile(os.path.join(panel_folder, f))
#     ]

#     return {
#         "user_assignment_id": assignment.user_assignment_id,
#         "user_id": assignment.user_id,
#         "files": files,
#         "panel_name": assignment.panel_id
#     }

@app.get("/panel-files/{panel_id}", response_model=List[FileMetaResponse])
def get_files_by_panel(panel_id: int, db: Session = Depends(get_db)):
    files = db.query(FileMeta.file_meta_id, FileMeta.panel_id, FileMeta.file_name).filter(FileMeta.panel_id == panel_id).all()
    if not files:
        raise HTTPException(status_code=404, detail="No files found for this panel")
    return files

# @app.get("/view-file/{file_meta_id}")
# def view_file(file_meta_id: int, db: Session = Depends(get_db)):
#     file = db.query(FileMeta).filter(FileMeta.file_meta_id == file_meta_id).first()
#     if not file:
#         raise HTTPException(status_code=404, detail="File not found")

#     return StreamingResponse(BytesIO(file.file_data), media_type="application/pdf", headers={
#         "Content-Disposition": f"inline; filename={file.file_name}"
#     })

# @app.get("/view-file/{panel_name}/{file_name}")
# def view_file(panel_name: str, file_name: str):
#     file_path = os.path.join(PANEL_BASE_DIR, panel_name, file_name)

#     if not os.path.exists(file_path) or not os.path.isfile(file_path):
#         raise HTTPException(status_code=404, detail="File not found")

#     file_stream = open(file_path, "rb")
#     return StreamingResponse(file_stream, media_type="application/pdf", headers={
#         "Content-Disposition": f"inline; filename={file_name}"
#     })

@app.get("/view-file/{panel_name}/{file_name}")
def view_file(panel_name: str, file_name: str):
    file_path = os.path.join(PANEL_BASE_DIR, panel_name, file_name)

    if not os.path.exists(file_path) or not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail="File not found")

    file_size = os.path.getsize(file_path)  # Get the file size in bytes
    file_stream = open(file_path, "rb")

    return StreamingResponse(
        file_stream,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"inline; filename={file_name}",
            "Content-Length": str(file_size),  # Add this line
            "Access-Control-Expose-Headers": "Content-Length"  # Optional but important for frontend JS to read it
        }
    )
    
@app.get("/view-file1/{assignment_id}")
def view_file(assignment_id: int, secret_code: str, db: Session = Depends(get_db)):
    assignment = db.query(UserAssignment).filter_by(user_assignment_id=assignment_id).first()
    if not assignment or assignment.secret_code != secret_code:
        raise HTTPException(status_code=403, detail="Invalid secret code")

    file_meta = db.query(FileMeta).filter_by(panel_id=assignment.panel_id).first()
    if not file_meta:
        raise HTTPException(status_code=404, detail="File not found")

    return StreamingResponse(BytesIO(file_meta.file_data), media_type="application/pdf", headers={"Content-Disposition": f"inline; filename={file_meta.file_name}"})






@app.post("/user-assignment")
def create_user_assignment(payload: UserAssignmentCreate, db: Session = Depends(get_db)):
    secret_code = generate_secret_code()
    # Proper base64 encoding of the secret code
    encoded_bytes = base64.b64encode(secret_code.encode('utf-8'))
    encoded_str = encoded_bytes.decode('utf-8')
    file_url = f"{WEBAPP_URL}verify-secret-code/{encoded_str}"
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

    
# ------------------ RUN ------------------
# Uncomment below to run directly
# if __name__ == "__main__":
#     uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
