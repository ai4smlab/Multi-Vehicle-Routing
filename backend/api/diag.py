# api/diag.py
from fastapi import APIRouter, Request

router = APIRouter(prefix="/_diag", tags=["diag"])


@router.post("/echo")
async def echo(request: Request):
    j = await request.json()
    return {"status": "success", "data": j}
