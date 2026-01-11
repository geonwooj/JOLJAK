from openai import OpenAI

class LLMClient:
    def __init__(self, model="gpt-4.1", temperature=0.3):
        self.client = OpenAI()
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