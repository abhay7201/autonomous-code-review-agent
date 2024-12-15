import openai
from langchain.tools import Tool
from typing import Dict, Any
import logging

class AIFileAnalysisTool(Tool):
    def __init__(self, api_key: str):
        self.api_key = api_key
        openai.api_key = api_key

        # Pass the analysis function as `func`
        super().__init__(
            name="ai_file_analysis_tool",
            description="Uses AI to analyze files for style, bugs, and performance improvements.",
            func=self.analyze_pull_request  # Specify the function that will handle the logic
        )

    def analyze_pull_request(self, file_name: str, file_content: str) -> Dict[str, Any]:
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

        Code:
        {file_content}
        """
        try:
            response = openai.ChatCompletion.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}]
            )
            logging.info(f"OpenAI Response: {response}")
            issues = eval(response["choices"][0]["message"]["content"])  # Convert response to JSON
            return {"file_name": file_name, "issues": issues}
        except Exception as e:
            logging.error(f"Error during file analysis: {str(e)}")
            return {"file_name": file_name, "issues": [], "error": str(e)}

    def _arun(self, *args, **kwargs) -> Any:
        raise NotImplementedError("Async mode not implemented yet")
