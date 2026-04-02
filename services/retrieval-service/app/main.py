from fastapi import FastAPI

app = FastAPI(title="Retrieval Service")

@app.get("/health")
def health():
    return {"status": "ok", "service": "retrieval-service"}
