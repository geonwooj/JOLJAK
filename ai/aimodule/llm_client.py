import os
from openai import OpenAI

class LLMClient:
    def __init__(self, model="gpt-5.2", temperature=0.1):

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY 환경변수 설정 필요")

        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.temperature = temperature

    def call(self, system: str, user: str, response_format=None,
             temperature: float = None):
        """
        temperature를 지정하지 않으면 생성자에 설정된 기본값(self.temperature)을
        쓴다. Phase별로 다른 temperature가 필요하면(예: Phase 2 앙상블 생성은
        의도적으로 다양한 초안이 나와야 클러스터링이 의미가 있음) 호출할 때
        temperature= 인자로 개별 오버라이드한다.
        """
        t = temperature if temperature is not None else self.temperature

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user}
        ]

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=t,
            response_format=response_format
        )

        return response.choices[0].message.content
