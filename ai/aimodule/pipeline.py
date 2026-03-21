# ai/pipeline.py
import json
from aimodule.llm_client import LLMClient
from aimodule.prompts import summarize, claim_parse, diff, claim_gen, consensus

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
    # 청구항 생성 + 합의 (연구 방법론 반영 수정)
    # ----------------------------
    def generate_claim(
        self,
        user_idea: str,          
        prior_arts: list = None, # [수정] 다수의 검색 결과(prior_arts)를 리스트로 받음
        elements: dict = None,   # [유지] 기존 단일 특허 호환성 유지
        diff_elements: dict = None,
        field: str = "fitness",
        n_shots: int = 3,
        temperature: float = 0.3
    ):
        """
        Retrieval-Guided Claim Drafting: 
        검색된 여러 선행 특허들을 종합 분석하여 차별화된 청구항 생성
        """
        # 1. 선행 기술 Context 통합 (방법론 6번 항목 반영)
        # 단일 특허(elements)만 들어온 경우 리스트로 변환하여 처리
        if prior_arts is None and elements is not None:
            prior_arts = [elements]
        
        if not prior_arts:
            raise ValueError("검색된 선행 특허(prior_arts)가 없습니다.")

        # 2. 가장 유사한 특허(첫 번째 특허)의 청구항 파싱 및 차이점 분석
        # 모든 선행 특허를 다 파싱하기보다, 가장 유사도가 높은 최상위 특허를 기준으로 기준점(Base) 설정
        top_prior_elements = self.parse_claim(prior_arts[0].get("claims", ""))

        if diff_elements is None:
            diff_result = self.diff_elements(user_idea, top_prior_elements.get("elements", []))
        else:
            diff_result = diff_elements

        # 3. 청구항 생성 (검색 결과 전체를 참고 자료로 전달)
        # claim_gen 프롬프트에서 여러 선행 문헌을 참고할 수 있도록 elements 대신 prior_arts 전달
        system, user = claim_gen.get_claim_gen_prompt(
            elements=prior_arts[0], # 기준 특허
            prior_arts=prior_arts,   # [추가] 전체 검색 결과 리스트
            diff_elements=diff_result,
            user_idea=user_idea,
            field=field,
            n_shots=n_shots,
            temperature=temperature
        )

        drafts = []
        # 연구 방법론의 신뢰성을 위해 5개의 초안을 생성한 뒤 합의(Consensus) 도출
        for _ in range(5):  
            raw = self.llm.call(system, user)
            drafts.append(raw)

        # 4. Consensus (최종 안 도출)
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
            # 오류 발생 시 디버깅을 위해 raw 텍스트 일부 출력
            raise ValueError(
                f"[{stage}] GPT 출력이 JSON 형식이 아님\n\n오류: {e}"
            )