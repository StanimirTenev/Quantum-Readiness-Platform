from fastapi import FastAPI

app = FastAPI(title="Policy Engine")

@app.get("/health")
def health():
    return {"status": "ok", "service": "policy-engine"}
