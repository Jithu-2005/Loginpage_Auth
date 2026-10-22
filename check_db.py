from sqlalchemy import text
from app.database.session import engine

try:
    with engine.connect() as connection:
        result = connection.execute(text("SELECT 1"))
        print("Database connection successful:", result.scalar())
except Exception as error:
    print("Database connection failed.")
    print("Error:", error)
