from fastapi import FastAPI

app = FastAPI(title="Crypto Fingerprint Service")

@app.get("/health")
def health():
    return {"status": "ok", "service": "crypto-fingerprint-service"}
