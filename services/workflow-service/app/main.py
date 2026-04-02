from fastapi import FastAPI

app = FastAPI(title="Workflow Service")

@app.get("/health")
def health():
    return {"status": "ok", "service": "workflow-service"}
