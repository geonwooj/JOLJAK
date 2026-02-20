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
        elements: dict,          # sections (title, abstract, claims 등)
        user_idea: str,          # ← 추가
        diff_elements: dict = None,
        field: str = "fitness",
        n_shots: int = 3,
        temperature: float = 0.3
    ):
        # 1. 선행 청구항 파싱
        prior_elements = self.parse_claim(elements.get("claims", ""))

        # 2. 차별점 분석 (user_idea 명시 전달)
        if diff_elements is None:
            diff_result = self.diff_elements(user_idea, prior_elements.get("elements", []))
        else:
            diff_result = diff_elements

        # 3. 청구항 생성 (few-shot 포함)
        system, user = claim_gen.get_claim_gen_prompt(
            elements=elements,
            diff_elements=diff_result,
            field=field,
            n_shots=n_shots,
            temperature=temperature
        )

        drafts = []
        for _ in range(5):  # 5개 초안 생성
            raw = self.llm.call(system, user)
            drafts.append(raw)

        # 4. consensus
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