from pdf_processor.pipeline import process_pdf
from ai.pipeline import GPTPipeline

def run(pdf_path: str):
    patent_json = process_pdf(pdf_path)

    gpt = GPTPipeline()

    summary = gpt.summarize_patent(
        patent_json["description"]
    )

    claim_analysis = gpt.parse_claim(
        patent_json["claims"]
    )

    user_idea = "본 발명은 테스트용 AI 시스템에 관한 것이다."
    diff = gpt.diff_elements(
        idea=user_idea,
        prior=claim_analysis
    )

    final_claim = gpt.generate_claim(
        elements=claim_analysis,
        diff_elements=diff,
        examples=[]
    )

    return {
        "summary": summary,
        "claim_analysis": claim_analysis,
        "diff": diff,
        "final_claim": final_claim
    }


if __name__ == "__main__":
    result = run("data/raw_pdf/sample.pdf")
    print(result["final_claim"])
