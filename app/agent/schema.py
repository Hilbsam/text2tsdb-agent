# Diese Datei wurde mit der Dokumentation von https://docs.sqlalchemy.org/en/20/ erstellt.
from sqlalchemy import create_engine, MetaData, Table
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker
import os

engine = create_engine("postgresql://masterarbeit:masterarbeit@192.168.1.142:5433/oebb", connect_args={"application_name": "query_writer"})
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
Base   = declarative_base()
metadata = MetaData()

# Tabellen laden
arrivals = Table(
    'arrivals',
    metadata,
    schema='oebb',
    autoload_with=engine
)

departures = Table(
    'departures',
    metadata,
    schema='oebb',
    autoload_with=engine
)

station = Table(
    'station',
    metadata,
    schema='oebb',
    autoload_with=engine
)
trainnames = Table(
    'trainnames',
    metadata,
    schema='oebb',
    autoload_with=engine
)

holidays = Table(
    'holidays',
    metadata,
    schema='oebb',
    autoload_with=engine
)

# Session Local for dependency injection
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


