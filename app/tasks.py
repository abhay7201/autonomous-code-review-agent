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
       