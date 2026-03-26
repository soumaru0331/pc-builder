# reload trigger
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pathlib import Path

from database import init_db
from routers import parts, builds, compatibility, prices, suggest, export, sync

app = FastAPI(title="PC Builder", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(parts.router,         prefix="/api/parts",         tags=["parts"])
app.include_router(builds.router,        prefix="/api/builds",        tags=["builds"])
app.include_router(compatibility.router, prefix="/api/compatibility",  tags=["compatibility"])
app.include_router(prices.router,        prefix="/api/prices",         tags=["prices"])
app.include_router(suggest.router,       prefix="/api/suggest",        tags=["suggest"])
app.include_router(export.router,        prefix="/api/export",         tags=["export"])
app.include_router(sync.router,          prefix="/api/sync",            tags=["sync"])

FRONTEND = Path(__file__).parent.parent / "frontend"


@app.get("/")
async def root():
    return FileResponse(str(FRONTEND / "index.html"))


app.mount("/static", StaticFiles(directory=str(FRONTEND)), name="static")


@app.on_event("startup")
async def startup():
    init_db()
    print("PC Builder 起動完了 http://127.0.0.1:8000")
