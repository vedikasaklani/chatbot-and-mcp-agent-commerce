from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
import database.database_models as database_models
from fastapi import Depends
# we keep autocommit and autoflush off: to maintain unit of work (db is not updated per operation)
#: to maintain atomicity (if subsequent transactions are failing, the prior ones should not execute.
# so we cannot execute the transactions one by one simply)
db_url="postgresql://postgres:vedika123@127.0.0.1:5433/my-fast-api-db"
engine=create_engine(db_url)
session = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = session()
    try:
        yield db
    finally:
        db.close()
