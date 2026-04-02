from fastapi import FastAPI

app = FastAPI(title="Evidence Normalizer")

@app.get("/health")
def health():
    return {"status": "ok", "service": "evidence-normalizer"}
