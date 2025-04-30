from fastapi import FastAPI, Depends, Query, UploadFile, File, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.responses import StreamingResponse
from fastapi import Form

from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from database import SessionLocal, engine
from models import Base, FileMeta, PanelMaster
from crud import get_file_by_name
from pathlib import Path
import qrcode
from io import BytesIO
import shutil

app = FastAPI()

# Create DB tables
Base.metadata.create_all(bind=engine)

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Files directory
FILES_DIR = Path("static")
FILES_DIR.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=FILES_DIR), name="static")


@app.post("/upload/")
async def upload_file(file: UploadFile = File(...), created_by: str = Form(...),
    panel: str = Form(...),
    db: Session = Depends(get_db)):
    file_path = FILES_DIR / file.filename
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    filemeta = FileMeta(
        filename=file.filename,
        path=str(file_path),
        filetype=file.content_type,
        created_by=created_by,
        panel=panel
    )
    db.add(filemeta)
    db.commit()
    db.refresh(filemeta)

    return {"filename": file.filename}


@app.get("/panels/")
def get_panels(db: Session = Depends(get_db)):
    return db.query(PanelMaster).all()

@app.get("/generate-qr")
def generate_qr(panel: str = Query(..., description="Panel name to generate QR for"), db: Session = Depends(get_db)):
    file = get_file_by_name(db, panel)
    # device_type = get_file_by_name(db, filename)
    if not file:
        raise HTTPException(status_code=404, detail="File not found")

    file_url = f"http://localhost:8000/files/{file.filename}"
    qr = qrcode.make(file_url)
    buf = BytesIO()
    qr.save(buf, format="PNG")
    buf.seek(0)

    return StreamingResponse(buf, media_type="image/png")
