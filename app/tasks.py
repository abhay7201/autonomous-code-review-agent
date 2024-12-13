from celery import Celery
from typing import Optional
import requests
import redis
from crewai.agent import Agent


celery_app = Celery(
    "tasks",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/0",
)

# GitHub API base URL
GITHUB_API_URL = "https://api.github.com"

# Initialize Redis client
redis_client = redis.StrictRedis(host="localhost", port=6379, db=0)

@celery_app.task(bind=True)
def analyze_pr_task(self, repo_url: str, pr_number: int, github_token: Optional[str]):
    task_id = self.request.id
    redis_client.set(task_id, "processing")

    try:
        # Step 1: Fetch PR details from GitHub API
        headers = {"Authorization": f"token {github_token}"} if github_token else {}
        pr_url = f"{GITHUB_API_URL}/repos/{repo_url}/pulls/{pr_number}"
        response = requests.get(pr_url, headers=headers)

        if response.status_code != 200:
            redis_client.set(task_id, f"failed: {response.text}")
            return

        pr_data = response.json()

        # Step 2: Fetch files in the pull request
        pr_files_url = pr_data["url"] + "/files"
        pr_files_response = requests.get(pr_files_url, headers=headers)
        if pr_files_response.status_code != 200:
            redis_client.set(task_id, f"failed: {pr_files_response.text}")
            return

        pr_files = pr_files_response.json()

        # Step 3: Analyze files using AI agent
        analysis_results = {"files": [], "summary": {"total_files": 0, "total_issues": 0, "critical_issues": 0}}

        for file in pr_files:
            if "patch" in file:
                # Analyze the file patch using the AI agent
                analysis = Agent.analyze_pull_request(file["patch"])
                if not analysis:
                    redis_client.set(task_id, f"failed: Could not analyze file {file['filename']}")
                    continue

                issues = []
                for issue in analysis.get("issues", []):
                    issues.append({
                        "type": issue.get("type"),  # Type of the issue: style, bug, etc.
                        "line": issue.get("line"),  # Line number where the issue occurred
                        "description": issue.get("description"),  # Issue description
                        "suggestion": issue.get("suggestion")  # Suggestion to fix the issue
                    })

                # Append analysis results for the current file
                analysis_results["files"].append({
                    "name": file["filename"],
                    "issues": issues
                })
                analysis_results["summary"]["total_files"] += 1
                analysis_results["summary"]["total_issues"] += len(analysis.get("issues", []))
                analysis_results["summary"]["critical_issues"] += sum(1 for issue in analysis.get("issues", []) if issue.get("type") == "critical")

        # Step 4: Store results in Redis
        result_object = {"task_id": task_id, "status": "completed", "results": analysis_results}
        redis_client.set(f"{task_id}_result", json.dumps(result_object))
        redis_client.set(task_id, "completed")
    
    except Exception as e:
        redis_client.set(task_id, f"failed: {str(e)}")
        raise
