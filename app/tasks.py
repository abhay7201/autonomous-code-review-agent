import json
import os
from celery import Celery
from typing import Optional
import requests
from openai import OpenAI
import redis

celery_app = Celery(
    "tasks",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/0",
)

# GitHub API Token (Optional)
GITHUB_API_URL = "https://api.github.com"

# Initialize Redis client
redis_client = redis.StrictRedis(host='localhost', port=6379, db=0)


@celery_app.task(bind=True)
def analyze_pr_task(self, repo_url: str, pr_number: int, github_token: Optional[str]):
    task_id = self.request.id
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
   # code_changes = [file['patch'] for file in pr_files]

    openai_client = OpenAI()
    # Step 3: Send code to OpenAI for analysis (simulate code review)

    analysis_results = {"files": [], "summary": {"total_files": 0, "total_issues": 0, "critical_issues": 0}}

    for file in pr_files:
        if "patch" in file:

            prompt = f"""
                Analyze the following code and identify:
                - Style issues
                - Bugs or errors
                - Performance improvements
                - Best practices

                Return the results as a JSON array of objects with:
                - type: issue type (e.g., 'style', 'bug', 'performance', 'best_practice')
                - line: line number
                - description: issue description
                - suggestion: improvement suggestion
                
                Note: 
                The response you provide will be parsed directly using json.loads() without any modification. Therefore, ensure the output consists solely of a valid JSON object or array, without any surrounding elements like comments, extra text, or special formatting. The goal is to have clean, parsable JSON that can be directly converted into a Python dictionary or list without any errors or additional processing.

                Code:
                {file["patch"]}
                """
            analysis = openai_client.chat.completions.create(
                model="gpt-4o",  
                messages = [
                {
                    "role": "user",
                    "content": prompt
                },
            ],
            )
            issues = analysis.choices[0].message.content
            issues=issues.strip().removeprefix("```json").removesuffix("```")
            print(issues)
            issues = json.loads(issues)


            analysis_results["files"].append({
                    "name": file["filename"],
                    "issues": issues
                })
            
            analysis_results["summary"]["total_files"] += 1
            analysis_results["summary"]["total_issues"] += len(issues)
            analysis_results["summary"]["critical_issues"] += sum(1 for issue in issues if issue.get("type") == "critical")

    redis_client.set(f"{task_id}_result", str({"task_id": task_id, "status": "completed", "results": analysis_results}))

    # Update the status in Redis
    redis_client.set(task_id, "Analysis completed.")
       