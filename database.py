# -*- coding: utf-8 -*-
"""
Created on Sun Apr 20 14:29:39 2025

@author: AshokKumarSathasivam
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import json
import os
import urllib.parse


ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
config_path = '/'.join([ROOT_DIR, 'config.json'])

# read json file
with open(config_path) as config_file:
    config = json.load(config_file)
    sql_config = config['localdatabase']


SQL_server = sql_config['server']
SQL_database = sql_config['database']
SQL_user = sql_config['user']
#SQL_password = sql_config['password']
SQL_password = urllib.parse.quote_plus(sql_config['password'])
SQL_port = sql_config.get('port', 3306)

DATABASE_URL = f"mysql+pymysql://{SQL_user}:{SQL_password}@{SQL_server}:{SQL_port}/{SQL_database}"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
