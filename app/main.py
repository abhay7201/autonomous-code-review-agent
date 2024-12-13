import os
import redis
import requests
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional
import openai
import uuid
from git import Repo
from threading import Thread
from openai import OpenAI



# FastAPI instance
app = FastAPI()

# Initialize Redis client
redis_client = redis.StrictRedis(host='localhost', port=6379, db=0)

# GitHub API Token (Optional)
GITHUB_API_URL = "https://api.github.com"

class AnalyzePRRequest(BaseModel):
    repo_url: str
    pr_number: int
    github_token: Optional[str] = None

# Background Task to process the PR
def analyze_pr_task(repo_url: str, pr_number: int, github_token: Optional[str], task_id: str):
    # Step 1: Fetch PR details using GitHub API
    headers = {"Authorization": f"token {github_token}"} if github_token else {}
    pr_url = f"{GITHUB_API_URL}/repos/{repo_url}/pulls/{pr_number}"
    response = requests.get(pr_url, headers=headers)

    if response.status_code != 200:
        redis_client.set(task_id, f"Failed to fetch PR data: {response.text}")
        return

    pr_data = response.json()

    # Step 2: Extract the changes (files changed, diff, etc.)
    pr_files_url = pr_data['url'] + '/files'
    pr_files_response = requests.get(pr_files_url, headers=headers)
    if pr_files_response.status_code != 200:
        redis_client.set(task_id, f"Failed to fetch PR files: {pr_files_response.text}")
        return

    pr_files = pr_files_response.json()
    code_changes = [file['patch'] for file in pr_files]

    openai_client = OpenAI()

    # Step 3: Send code to OpenAI for analysis (simulate code review)
    analysis_result = openai_client.chat.completions.create(
        model="gpt-4o",  # You can choose the appropriate model
        messages = [{ "role": "system", 
        "content": "You are an expert in coding. You will be provided with the code and your task will be to review the code and suggest improvements" },
        {
            "role": "user",
            "content": "Please review the following code and suggest improvements:\n" + "\n".join(code_changes),
        },
    ],
    )

    redis_client.set(f"{task_id}_result", analysis_result.choices[0].message.content)

    # Update the status in Redis
    redis_client.set(task_id, "Analysis completed.")
       

# Endpoint to trigger PR analysis
@app.post("/analyze-pr")
async def analyze_pr(request: AnalyzePRRequest, background_tasks: BackgroundTasks):
    task_id = str(uuid.uuid4())  # Unique task ID
    redis_client.set(task_id, "Analysis in progress...")

    # Run the PR analysis in the background
    background_tasks.add_task(analyze_pr_task, request.repo_url, request.pr_number, request.github_token, task_id)

    return {"task_id": task_id}

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
