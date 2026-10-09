from fastapi import FastAPI, APIRouter

app = FastAPI(title="StudyForge API")

api_router = APIRouter()

@app.get("/health")
def health_check():
    return {"status": "ok"}

app.include_router(api_router, prefix="/api/v1")
