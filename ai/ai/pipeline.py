# ai/pipeline.py

import json
from ai.llm_client import LLMClient
from ai.prompts import summarize, claim_parse, diff, claim_gen, consensus

class GPTPipeline:
    def __init__(self):
        self.llm = LLMClient()

    # ----------------------------
    # 요약
    # ----------------------------
    def summarize_patent(self, text):
        system = summarize.SYSTEM
        user = summarize.get_summarize_prompt(text)
        raw = self.llm.call(system, user)
        return self._load_json(raw, "summarize")

    # ----------------------------
    # 청구항 파싱
    # ----------------------------
    def parse_claim(self, claim_text):
        system = claim_parse.SYSTEM
        user = claim_parse.get_claim_parse_prompt(claim_text)
        raw = self.llm.call(system, user)
        return self._load_json(raw, "claim_parse")

    # ----------------------------
    # 차이 분석 (diff)
    # ----------------------------
    def diff_elements(self, idea, prior):
        system = diff.SYSTEM
        user = diff.get_diff_prompt(idea, prior)
        raw = self.llm.call(system, user)
        return self._load_json(raw, "diff")

    # ----------------------------
    # 청구항 생성 + 합의 (핵심 수정)
    # ----------------------------
    def generate_claim(
        self,
        elements: dict,
        diff_elements: dict,
        field: str = "fitness",
        n_shots: int = 3,
        temperature: float = 0.3
    ):
        system, user = claim_gen.get_claim_gen_prompt(
            elements=elements,
            diff_elements=diff_elements,
            field=field,
            n_shots=n_shots,
            temperature=temperature
        )

        drafts = []
        for _ in range(5):
            raw = self.llm.call(system, user)
            drafts.append(raw)

        consensus_system = consensus.SYSTEM
        consensus_user = consensus.get_consensus_prompt(drafts)
        final_raw = self.llm.call(consensus_system, consensus_user)

        return self._load_json(final_raw, "consensus")

    # ----------------------------
    # 공통 JSON 파서
    # ----------------------------
    def _load_json(self, raw: str, stage: str):
        try:
            start = raw.find('{')
            end = raw.rfind('}') + 1
            cleaned = raw[start:end]
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            raise ValueError(
                f"[{stage}] GPT 출력이 JSON 형식이 아님\n\n원본:\n{raw}\n\n오류: {e}"
            )