from fastapi import FastAPI

app = FastAPI(title="API Gateway")

@app.get("/health")
def health():
    return {"status": "ok", "service": "api-gateway"}
