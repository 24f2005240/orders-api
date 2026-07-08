from fastapi import FastAPI, Header, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
import time
import uuid
import base64

app = FastAPI()

# Allow browser access (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

TOTAL_ORDERS = 55
RATE_LIMIT = 18
WINDOW = 10

# Stores
idempotency_store = {}
client_requests = []

# -----------------------------
# 1. Idempotent POST /orders
# -----------------------------
@app.post("/orders", status_code=201)
def create_order(idempotency_key: str = Header(..., alias="Idempotency-Key")):

    if idempotency_key in idempotency_store:
        return idempotency_store[idempotency_key]

    order = {
        "id": str(uuid.uuid4()),
        "status": "created"
    }

    idempotency_store[idempotency_key] = order
    return order


# -----------------------------
# 2. Cursor Pagination
# -----------------------------
@app.get("/orders")
def list_orders(limit: int = 10, cursor: str | None = None):

    start = 1

    if cursor:
        start = int(base64.b64decode(cursor).decode())

    end = min(start + limit - 1, TOTAL_ORDERS)

    items = []

    for i in range(start, end + 1):
        items.append({
            "id": i
        })

    next_cursor = None

    if end < TOTAL_ORDERS:
        next_cursor = base64.b64encode(
            str(end + 1).encode()
        ).decode()

    return {
        "items": items,
        "next_cursor": next_cursor
    }


# -----------------------------
# 3. Rate Limiting
# -----------------------------
@app.middleware("http")
async def rate_limit(request, call_next):

    client = request.headers.get("X-Client-Id", "anonymous")

    now = time.time()

    global client_requests

    client_requests[:] = [
        r for r in client_requests
        if now - r["time"] < WINDOW
    ]

    used = [
        r for r in client_requests
        if r["client"] == client
    ]

    if len(used) >= RATE_LIMIT:
        retry = WINDOW - int(now - used[0]["time"])
        response = Response(status_code=429)
        response.headers["Retry-After"] = str(max(1, retry))
        return response

    client_requests.append({
        "client": client,
        "time": now
    })

    return await call_next(request)