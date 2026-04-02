from fastapi import FastAPI

app = FastAPI(title="Planner Service")

@app.get("/health")
def health():
    return {"status": "ok", "service": "planner-service"}
