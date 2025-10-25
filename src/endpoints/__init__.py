from fastapi import APIRouter

from .picker import picker_router

all_routers = [
    picker_router,
]
