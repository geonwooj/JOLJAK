import os
from openai import OpenAI

class LLMClient:
    def __init__(self, model="gpt-5.2", temperature=0.3):
        
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY 환경변수 설정 필요")

        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.temperature = temperature

    def call(self, system: str, user: str, response_format=None):
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user}
        ]

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=self.temperature,
            response_format=response_format
        )

        return response.choices[0].message.content