import uvicorn
from fastapi import FastAPI
from app.core.bootstrap import bootstrap
from app.core.settings import app_settings

app: FastAPI = bootstrap()

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=app_settings.endpoint_settings.HOST,
        port=app_settings.endpoint_settings.PORT,
        reload=app_settings.is_development,
    )
