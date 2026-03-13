import sqlite3
import os
import json
from pathlib import Path

# 경로 설정
DATA_ROOT = "data"
REPROCESSED_DIR = os.path.join(DATA_ROOT, "reprocessed")
EMBED_DIR = os.path.join(DATA_ROOT, "embeddings_final_temp")
DB_PATH = os.path.join(DATA_ROOT, "patent_system.db")

def setup_auto_scan_db():
    if not os.path.exists(REPROCESSED_DIR):
        print(f"❌ 오류: {REPROCESSED_DIR} 경로가 존재하지 않습니다.")
        return

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("PRAGMA foreign_keys = ON;")

    print("[1/3] 테이블 초기화 중...")
    cur.execute("DROP TABLE IF EXISTS 원본특허DB")
    cur.execute("DROP TABLE IF EXISTS 특허원문저장소")
    cur.execute("DROP TABLE IF EXISTS 사용자입력DB")

    # 테이블 생성 (정규화 구조)
    cur.execute("CREATE TABLE 사용자입력DB (id INTEGER PRIMARY KEY AUTOINCREMENT, idea_text TEXT, status TEXT DEFAULT 'pending', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
    cur.execute("CREATE TABLE 특허원문저장소 (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, pdf_path TEXT NOT NULL, patent_type TEXT)")
    cur.execute("CREATE TABLE 원본특허DB (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, type TEXT, resultPath TEXT, patentRepo_id INTEGER, FOREIGN KEY (patentRepo_id) REFERENCES 특허원문저장소(id))")

    print("[2/3] 파일 시스템 스캔 및 데이터 주입 중...")
    
    # 분야 폴더 탐색 (data/reprocessed/*)
    field_folders = [d for d in Path(REPROCESSED_DIR).iterdir() if d.is_dir()]
    
    for field_path in field_folders:
        field_name = field_path.name  # 예: semiconductor, information
        # 해당 분야의 NPZ 파일 경로 확인
        npz_file = Path(EMBED_DIR) / f"{field_name}_combined_embeddings.npz"
        
        if not npz_file.exists():
            print(f"⚠️ 경고: {field_name} 분야의 NPZ 파일이 없어 건너뜁니다.")
            continue

        # 해당 분야 폴더 내의 모든 JSON 파일 스캔 (실제 특허 데이터)
        json_files = list(field_path.glob("*.json"))
        
        for json_path in json_files:
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    p_data = json.load(f)
                
                # 1. 특허원문저장소 채우기
                # JSON 내부에 'title'이 있으면 사용하고, 없으면 파일명을 이름으로 사용
                patent_title = p_data.get("title", json_path.stem)
                # 실제 PDF 경로는 data/pdf/분야/파일명.pdf 라고 가정하거나 가상 경로 지정
                pdf_link = os.path.join(DATA_ROOT, "pdf", field_name, json_path.stem + ".pdf")
                
                cur.execute('''
                    INSERT INTO 특허원문저장소 (name, pdf_path, patent_type) 
                    VALUES (?, ?, ?)
                ''', (patent_title, pdf_link, "국내특허"))
                
                repo_id = cur.lastrowid
                
                # 2. 원본특허DB 채우기
                # 여기서는 NPZ 파일 하나가 여러 특허를 포함하지만, 
                # 구조상 각 특허가 어떤 NPZ(분석결과)에 속해있는지 연결합니다.
                cur.execute('''
                    INSERT INTO 원본특허DB (name, type, resultPath, patentRepo_id) 
                    VALUES (?, ?, ?, ?)
                ''', (json_path.name, field_name, str(npz_file.absolute()), repo_id))
                
            except Exception as e:
                print(f"   > 파일 처리 오류 ({json_path.name}): {e}")

    # 3. 테스트 데이터 주입
    cur.execute("INSERT INTO 사용자입력DB (idea_text) VALUES ('본 발명은 인공지능 자동 절전시스템에 관한 것으로서, 보다 상세하게는, 매립형 콘센트 와 이동형 멀티 콘센트에 전류감지기술을 적용하여 대기전력차단 및 과부하 차단을 통해 절전이 가능하고, 인체감지센서를 이용 하여콘센트 전원을 차단하고, 차단되는 시간을 선택할 수 있음은 물론 센서 분리시 메인 콘센트의 전원을 항상 ON으로 유지하고, 유선 및 무선통신을 통해 인체감지센서의 인체감지 여부를 판단할 수 있으며, 적외선센서 구동방식기술을 프리모드와 코드모드 로 적용하여 소비자가 선택적으로 환경에 맞게 편리하게 변경하여 제어할 수있고, 터치 IC를 적용하여 대기전력과 소비전력을 판단한 후 자동으로 콘센트의 전원이 차단된 다음에 수동으로 전원을 인가할 수 있으며, 바닥 매립형 콘센트의 경우 사출물의 각도를 주어 사용자가 전자제품 코드 결합시 편리성을 제공할 수 있고, 바닥 매립형 콘센트와, 벽 매립형 콘센트에 적용할 수 있음은 물론 이동형 멀티콘센트에도 적용할 수 있으므로 그 사용 및 적용대상이 광범위한 효과가 있다.')")

    conn.commit()
    conn.close()
    print(f"\n✅ [성공] {REPROCESSED_DIR} 스캔 완료 및 DB 구축 성공!")

if __name__ == "__main__":
    setup_auto_scan_db()