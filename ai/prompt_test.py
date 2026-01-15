
from ai.prompts.prompt import PromptBuilder

builder = PromptBuilder(field="fitness", n_shots=2, temperature=0.25)

system, user = builder.build(
    user_idea="스마트폰으로 실시간 운동 자세 교정해주는 AI 웨어러블 시스템",
    diff={"user_only": ["실시간 자세 피드백", "웨어러블 센서 연동"]},
    prior_claims="청구항 1. 스마트짐 내의 운동기구 각각과 통신하는 통신부; ..."
)

print("SYSTEM:\n", system)
print("\nUSER:\n", user)

from ai.pipeline import GPTPipeline
gpt = GPTPipeline()
response = gpt.llm.call(system, user)
print(response)