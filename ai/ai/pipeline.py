import json
from .llm_client import LLMClient
from .prompts import summarize, claim_parse, diff, claim_gen, consensus

class GPTPipeline:
    def __init__(self):
        self.llm = LLMClient()

    # ----------------------------
    # 요약
    # ----------------------------
    def summarize_patent(self, text):
        raw = self.llm.call(
            summarize.SYSTEM,
            summarize.build_prompt(text)
        )
        return self._load_json(raw, "summarize")

    # ----------------------------
    # 청구항 파싱
    # ----------------------------
    def parse_claim(self, claim_text):
        raw = self.llm.call(
            claim_parse.SYSTEM,
            claim_parse.build_prompt(claim_text)
        )
        return self._load_json(raw, "claim_parse")

    # ----------------------------
    # 차이 분석 (diff)
    # ----------------------------
    def diff_elements(self, idea, prior):
        raw = self.llm.call(
            diff.SYSTEM,
            diff.build_prompt(idea, prior)
        )
        return self._load_json(raw, "diff")

    # ----------------------------
    # 청구항 생성 + 합의
    # ----------------------------
    def generate_claim(self, elements: dict, diff_elements: dict, examples):
        drafts = [
            self.llm.call(
                claim_gen.SYSTEM,
                claim_gen.build_prompt(elements, diff_elements, examples)
            )
            for _ in range(5)
        ]

        final = self.llm.call(
            consensus.SYSTEM,
            consensus.build_prompt(drafts)
        )
        return final

    # ----------------------------
    # 공통 JSON 파서
    # ----------------------------
    def _load_json(self, raw: str, stage: str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            raise ValueError(
                f"[{stage}] GPT 출력이 JSON 형식이 아님\n\n{raw}"
            )