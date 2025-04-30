# -*- coding: utf-8 -*-
"""
Created on Sun Apr 20 14:30:14 2025

@author: AshokKumarSathasivam
"""

from sqlalchemy.orm import Session
from models import FileMeta, PanelMaster

def get_file_by_name(db: Session, panel: str):
    return db.query(FileMeta).filter(FileMeta.panel == panel).first()

def get_panels(db: Session):
    return db.query(PanelMaster).all()