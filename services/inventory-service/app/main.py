from fastapi import FastAPI

app = FastAPI(title="Inventory Service")

@app.get("/health")
def health():
    return {"status": "ok", "service": "inventory-service"}
