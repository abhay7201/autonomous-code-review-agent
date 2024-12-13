import os
import redis
import requests
from fastapi import FastAPI, HTTPException, BackgroundTasks
import openai
from pydantic import BaseModel
import uuid
from git import Repo
from threading import Thread
from openai import OpenAI
from tasks import analyze_pr_task
from typing import Optional

# FastAPI instance
app = FastAPI()

class AnalyzePRRequest(BaseModel):
    repo_url: str
    pr_number: int
    github_token: Optional[str] = None


redis_client = redis.StrictRedis(host='localhost', port=6379, db=0)


# Endpoint to trigger PR analysis
@app.post("/analyze-pr")
async def analyze_pr(request: AnalyzePRRequest):
    #task_id = str(uuid.uuid4())  # Unique task ID
    task = analyze_pr_task.delay(request.repo_url, request.pr_number, request.github_token)
    redis_client.set(task.id, "Analysis in progress...")
    return {"task_id": task.id}

# Endpoint to get the status of the task
@app.get("/status/{task_id}")
async def get_task_status(task_id: str):
    status = redis_client.get(task_id)
    if status is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"task_id": task_id, "status": status.decode("utf-8")}

# Endpoint to get the result of the analysis
@app.get("/results/{task_id}")
async def get_task_result(task_id: str):
    result = redis_client.get(f"{task_id}_result")
    if result is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"task_id": task_id, "result": result.decode("utf-8")}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)