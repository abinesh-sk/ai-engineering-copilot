from fastapi import FastAPI
from app.core.database import check_connection
from app.trace.router import router as trace_router
app=FastAPI(title="AI Engineer Copilot")
app.include_router(trace_router)
@app.get("/")
def read_root():
    return {"status":"ok","service":"AI Engineer Copilot"}
@app.get("/health")
def health_check():
    return {"status": "healthy"}
@app.get("/db-check")
def db_check():
    version = check_connection()
    return {"postgres_version": version[0]}