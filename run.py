"""Start the API:  python run.py   (Swagger UI: http://localhost:3000/docs)"""
import uvicorn

from app import config

if __name__ == "__main__":
    print(f"🚀 Server running at {config.BASE_URL}")
    print(f"📘 Swagger UI:      {config.BASE_URL}/docs")
    uvicorn.run("app.main:app", host="127.0.0.1", port=config.PORT, reload=True)
