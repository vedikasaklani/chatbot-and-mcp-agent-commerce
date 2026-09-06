"""Database configuration file"""
import os

from dotenv import load_dotenv
from fastapi import Depends
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import database.database_models as database_models

load_dotenv()

# we keep autocommit and autoflush off: to maintain unit of work (db is not updated per operation)
#: to maintain atomicity (if subsequent transactions are failing, the prior ones should not execute.
# so we cannot execute the transactions one by one simply)
db_url=os.environ["DATABASE_URL"]
engine=create_engine(db_url)
session = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = session()
    try:
        yield db
    finally:
        db.close()
