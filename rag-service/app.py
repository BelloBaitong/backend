import os
from fastapi import FastAPI
from pydantic import BaseModel
from dotenv import load_dotenv
import psycopg2
from sentence_transformers import SentenceTransformer
import ollama

load_dotenv()

app = FastAPI()

# ===== ENV =====
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1")

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")

COURSE_TABLE = os.getenv("COURSE_TABLE", "course")  # table name in DB

# ===== MODELS =====
embedder = SentenceTransformer("BAAI/bge-m3")  # dim 1024

def get_conn():
    if not all([DB_NAME, DB_USER, DB_PASS]):
        raise RuntimeError("DB env is not set. Please set DB_NAME, DB_USER, DB_PASS in rag-service/.env")

    return psycopg2.connect(
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASS,
        host=DB_HOST,
        port=DB_PORT,
    )

# ===== DTO =====
class OllamaTestRequest(BaseModel):
    text: str

class EmbedOneCourseRequest(BaseModel):
    courseCode: str

# ===== HELPERS =====
def build_course_text(course_code, name_th, name_en, desc, category, credits):
    parts = []
    if name_th:
        parts.append(f"ชื่อวิชา: {name_th}")
    if name_en:
        parts.append(f"English name: {name_en}")
    if desc:
        parts.append(f"คำอธิบาย: {desc}")
    if category:
        parts.append(f"หมวด: {category}")
    if credits is not None:
        parts.append(f"หน่วยกิต: {credits}")
    parts.append(f"รหัสวิชา: {course_code}")
    return "\n".join(parts)

# ===== ROUTES =====
@app.get("/health")
def health():
    return {
        "status": "ok",
        "model": OLLAMA_MODEL,
        "dbHost": DB_HOST,
        "dbName": DB_NAME,
        "courseTable": COURSE_TABLE,
    }

@app.post("/ollama/test")
def ollama_test(req: OllamaTestRequest):
    resp = ollama.chat(
        model=OLLAMA_MODEL,
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": req.text},
        ],
    )
    return {"reply": resp["message"]["content"]}

@app.post("/courses/embed-one")
def embed_one_course(req: EmbedOneCourseRequest):
    # NOTE: your DB columns are camelCase -> MUST use double quotes in SQL
    sql_select = f"""
        SELECT "courseCode", "courseNameTh", "courseNameEn", "description", "category", "credits"
        FROM {COURSE_TABLE}
        WHERE "courseCode" = %s
        LIMIT 1;
    """

    sql_update = f"""
        UPDATE {COURSE_TABLE}
        SET embedding = %s::vector
        WHERE "courseCode" = %s;
    """

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql_select, (req.courseCode,))
            row = cur.fetchone()

            if not row:
                return {"ok": False, "message": "course not found", "courseCode": req.courseCode}

            course_code, name_th, name_en, desc, category, credits = row
            text = build_course_text(course_code, name_th, name_en, desc, category, credits)

            vec = embedder.encode(text).tolist()
            vec_str = "[" + ", ".join(map(str, vec)) + "]"

            cur.execute(sql_update, (vec_str, course_code))
            conn.commit()

    return {"ok": True, "courseCode": req.courseCode, "dim": len(vec)}


class EmbedMissingRequest(BaseModel):
    limit: int = 20  # ทำทีละ 20 ก่อน ปลอดภัย

@app.post("/courses/embed-missing")
def embed_missing(req: EmbedMissingRequest):
    sql_select = f"""
        SELECT "courseCode", "courseNameTh", "courseNameEn", "description", "category", "credits"
        FROM {COURSE_TABLE}
        WHERE "embedding" IS NULL
        ORDER BY "id" ASC
        LIMIT %s;
    """

    sql_update = f"""
        UPDATE {COURSE_TABLE}
        SET embedding = %s::vector
        WHERE "courseCode" = %s;
    """

    updated = 0
    failed = []

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql_select, (req.limit,))
            rows = cur.fetchall()

            for row in rows:
                course_code, name_th, name_en, desc, category, credits = row
                try:
                    text = build_course_text(course_code, name_th, name_en, desc, category, credits)
                    vec = embedder.encode(text).tolist()
                    vec_str = "[" + ", ".join(map(str, vec)) + "]"
                    cur.execute(sql_update, (vec_str, course_code))
                    updated += 1
                except Exception as e:
                    failed.append({"courseCode": course_code, "error": str(e)})

            conn.commit()

    return {"ok": True, "updated": updated, "failed": failed}

class RagRequest(BaseModel):
    queryText: str
    topK: int = 3

def query_courses_by_vector(qvec, k: int):
    qvec_str = "[" + ", ".join(map(str, qvec)) + "]"

    sql = f"""
        SELECT
            "courseCode",
            "courseNameTh",
            "courseNameEn",
            "description",
            "category",
            "credits",
            "imageUrl",
            embedding <-> %s::vector AS distance
        FROM {COURSE_TABLE}
        WHERE "embedding" IS NOT NULL
        ORDER BY distance ASC
        LIMIT %s;
    """

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (qvec_str, k))
            rows = cur.fetchall()

    sources = []
    for r in rows:
        sources.append({
            "courseCode": r[0],
            "courseNameTh": r[1],
            "courseNameEn": r[2],
            "description": r[3],
            "category": r[4],
            "credits": r[5],
            "imageUrl": r[6],
            "distance": float(r[7]),
        })
    return sources

@app.post("/rag/answer")
def rag_answer(req: RagRequest):
    qvec = embedder.encode(req.queryText).tolist()
    sources = query_courses_by_vector(qvec, req.topK)

    context = "\n\n".join([
        f"[{i+1}] {s['courseNameTh']} ({s['courseCode']})\n"
        f"EN: {s['courseNameEn']}\n"
        f"Desc: {s['description']}\n"
        f"Category: {s['category']} | Credits: {s['credits']}"
        for i, s in enumerate(sources)
    ])

    prompt = (
        "คุณคือผู้ช่วยแนะนำรายวิชาในมหาวิทยาลัย\n"
        "ให้ตอบโดยอิงจากข้อมูลวิชาใน CONTEXT\n\n"
        f"CONTEXT:\n{context}\n\n"
        f"QUESTION: {req.queryText}\n\n"
        "ขอผลลัพธ์เป็นภาษาไทย กระชับ และมี 2 ส่วน:\n"
        "1) answer: สรุปคำแนะนำ 3-6 บรรทัด\n"
        "2) recommendations: bullet list วิชาที่แนะนำพร้อมเหตุผลสั้นๆ\n"
    )

    resp = ollama.chat(
        model=OLLAMA_MODEL,
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt},
        ],
    )
    answer = resp["message"]["content"]

    return {"answer": answer, "sources": sources}
