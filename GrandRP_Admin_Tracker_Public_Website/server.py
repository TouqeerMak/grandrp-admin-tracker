"""Run with: uvicorn server:app --host 127.0.0.1 --port 8000"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from scanner import scan, period_bounds, ScanError

ROOT = Path(__file__).resolve().parent
app = FastAPI(title='Grand RP Admin Forum Tracker', docs_url=None, redoc_url=None)
scan_lock = asyncio.Lock()

class ScanRequest(BaseModel):
    preset: str = 'week'
    start: str = Field(default='', max_length=10)
    end: str = Field(default='', max_length=10)

@app.get('/api/health')
async def health():
    return {'ok': True, 'forum':'Grand RP forum 36', 'timezone':'Europe/London'}

@app.post('/api/scan')
async def run_scan(body: ScanRequest, request: Request):
    try:
        period_bounds(body.preset, body.start, body.end)
    except ScanError as exc:
        raise HTTPException(status_code=400,detail=str(exc)) from exc
    if scan_lock.locked():
        raise HTTPException(status_code=429,detail='Another scan is running on this server. Try again after it completes.')

    async def events():
        async with scan_lock:
            try:
                async for event in scan(body.preset,body.start,body.end):
                    if await request.is_disconnected():
                        break
                    yield json.dumps(event,ensure_ascii=False,separators=(',',':'))+'\n'
            except asyncio.CancelledError:
                raise
            except Exception:
                # Unexpected failures do not expose server internals.
                yield json.dumps({'type':'done','status':'partial','message':'The scanner stopped unexpectedly. Results are incomplete.',
                                  'complete':False,'results':[]})+'\n'

    return StreamingResponse(events(),media_type='application/x-ndjson',headers={
        'Cache-Control':'no-store, no-transform', 'X-Accel-Buffering':'no', 'X-Content-Type-Options':'nosniff'
    })

@app.get('/')
async def index():
    return FileResponse(ROOT/'public'/'index.html',media_type='text/html')

app.mount('/',StaticFiles(directory=ROOT/'public'),name='static')
