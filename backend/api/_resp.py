# api/_resp.py
from fastapi import HTTPException


def ok(data: dict | list | str | int | float | None = None, **extras):
    payload = {"status": "success"}
    if data is not None:
        payload["data"] = data
    if extras:
        payload.update(extras)
    return payload


def fail(status: int, message: str):
    raise HTTPException(status, message)
