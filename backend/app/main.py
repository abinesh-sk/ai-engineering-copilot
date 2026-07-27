from fastapi import FastAPI
from app.core.database import check_connection
from app.trace.router import router as trace_router
from fastapi.middleware.cors import CORSMiddleware
app=FastAPI(title="AI Engineer Copilot")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://ai-engineering-copilot-nine.vercel.app"],  # loosened for now — tighten to your real Vercel URL once you have it
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(trace_router)
@app.get("/api/v1/dashboard")
def dashboard_stub():
    return {
        "total_traces": 0,
        "diagnosed_traces": 0,
        "message": "Dashboard data will populate as traces are processed."
    }
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