from fastapi import APIRouter

router = APIRouter()


@router.get("/api/health")
def check_health():
    return {"ok": True}
