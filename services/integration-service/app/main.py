from fastapi import FastAPI

app = FastAPI(title="Integration Service")

@app.get("/health")
def health():
    return {"status": "ok", "service": "integration-service"}
