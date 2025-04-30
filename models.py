# -*- coding: utf-8 -*-
"""
Created on Sun Apr 20 14:29:58 2025

@author: AshokKumarSathasivam
"""

from sqlalchemy import Column, Integer, String, DateTime
from database import Base
from datetime import datetime



class FileMeta(Base):
    __tablename__ = 'filemeta'
    id = Column(Integer, primary_key=True, index=True)
    panel = Column(String(100))
    path = Column(String(255))
    filename = Column(String(255), unique=True, index=True)
    filetype = Column(String(100))
    created_by = Column(String(100))
    created_date = Column(DateTime, default=datetime.now())
    
class PanelMaster(Base):
    __tablename__ = 'panel_master'
    
    id = Column(Integer, primary_key=True)
    panel_name = Column(String(100), unique=True)
    description = Column(String(255))
    