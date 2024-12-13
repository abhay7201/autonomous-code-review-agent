import redis
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
from tasks import analyze_pr_task

# FastAPI instance
app = FastAPI()

# Initialize Redis client
redis_client = redis.StrictRedis(host="localhost", port=6379, db=0)

class AnalyzePRRequest(BaseModel):
    repo_url: str
    pr_number: int
    github_token: Optional[str] = None

# POST /analyze-pr - Trigger PR Analysis
@app.post("/analyze-pr")
async def analyze_pr(request: AnalyzePRRequest):
    task = analyze_pr_task.delay(request.repo_url, request.pr_number, request.github_token)
    redis_client.set(task.id, "pending")
    return {"task_id": task.id}

# GET /status/<task_id> - Check Task Status
@app.get("/status/{task_id}")
async def get_task_status(task_id: str):
    status = redis_client.get(task_id)
    if status is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"task_id": task_id, "status": status.decode("utf-8")}

# GET /results/<task_id> - Fetch Results
@app.get("/results/{task_id}")
async def get_task_result(task_id: str):
    result = redis_client.get(f"{task_id}_result")
    if result is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"task_id": task_id, "result": result.decode("utf-8")}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
