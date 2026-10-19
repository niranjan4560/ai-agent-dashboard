# Creates any missing tables. Safe to re-run: existing tables and data are
# never dropped or altered. The app also runs this automatically on startup.
from database import engine, Base
from models import *

Base.metadata.create_all(bind=engine)

print("Database initialized!")
