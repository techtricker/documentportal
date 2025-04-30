# -*- coding: utf-8 -*-
"""
Created on Sun Apr 20 14:29:39 2025

@author: AshokKumarSathasivam
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import json
import os


ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
config_path = '\\'.join([ROOT_DIR, 'config.json'])

# read json file
with open(config_path) as config_file:
    config = json.load(config_file)
    sql_config = config['database']


SQL_server = sql_config['server']
SQL_database = sql_config['database']
SQL_user = sql_config['user']
SQL_password = sql_config['password']


DATABASE_URL = f"mysql+pymysql://{SQL_user}:{SQL_password}@{SQL_server}:3306/{SQL_database}"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
