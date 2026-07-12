import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Configurable vía DATABASE_URL para que la suite de pruebas pueda apuntar a
# una base de datos aislada sin tocar la de desarrollo (ver backend/tests/).
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./sri_notas.db")

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()
