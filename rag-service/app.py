import os
from fastapi import FastAPI
from pydantic import BaseModel
from dotenv import load_dotenv
import psycopg2
from sentence_transformers import SentenceTransformer
import ollama

# โหลดตัวแปรสภาพแวดล้อมจากไฟล์ .env (เช่น DB_HOST, DB_NAME, OLLAMA_MODEL ฯลฯ)
# เพื่อไม่ hardcode config ในโค้ด
load_dotenv()

# สร้าง FastAPI application instance
app = FastAPI()

# ===== ENV =====
# ชื่อโมเดลที่ใช้กับ Ollama (LLM สำหรับ generate คำตอบ)
# ถ้าไม่ได้ตั้ง OLLAMA_MODEL ใน .env จะใช้ "llama3.1" เป็นค่า default
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1")

# ค่าการเชื่อมต่อ PostgreSQL
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME")  # ชื่อฐานข้อมูล (จำเป็น)
DB_USER = os.getenv("DB_USER")  # username (จำเป็น)
DB_PASS = os.getenv("DB_PASS")  # password (จำเป็น)

# ชื่อตารางที่เก็บคอร์ส (ทำให้ปรับเปลี่ยนตารางได้ผ่าน env)
# default คือ "course"
COURSE_TABLE = os.getenv("COURSE_TABLE", "course")  # table name in DB

# ===== MODELS =====
# โหลดโมเดล embedding จาก sentence-transformers
# BAAI/bge-m3 ให้ vector dimension = 1024 (สอดคล้องกับ vector(1024) ใน pgvector)
embedder = SentenceTransformer("BAAI/bge-m3")  # dim 1024

def get_conn():
    """
    สร้าง connection ไป PostgreSQL ด้วย psycopg2
    - เช็คก่อนว่ามี env จำเป็นครบไหม (DB_NAME, DB_USER, DB_PASS)
    - ถ้าไม่ครบจะ raise RuntimeError เพื่อหยุดให้รู้ว่าตั้งค่าไม่ถูก
    """
    if not all([DB_NAME, DB_USER, DB_PASS]):
        raise RuntimeError("DB env is not set. Please set DB_NAME, DB_USER, DB_PASS in rag-service/.env")

    # psycopg2.connect สร้างการเชื่อมต่อฐานข้อมูล
    return psycopg2.connect(
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASS,
        host=DB_HOST,
        port=DB_PORT,
    )

# ===== DTO =====
# DTO สำหรับยิงทดสอบ LLM (ollama) เฉย ๆ
class OllamaTestRequest(BaseModel):
    text: str

# DTO สำหรับ endpoint ที่ฝัง embedding ให้ “วิชาเดียว” (ระบุด้วย courseCode)
class EmbedOneCourseRequest(BaseModel):
    courseCode: str

# ===== HELPERS =====
def build_course_text(course_code, name_th, name_en, desc, category, credits):
    """
    รวมข้อมูลวิชาให้เป็นข้อความเดียว (text) เพื่อส่งเข้า embedder
    แนวคิด: embedding ควรถอดความหมายจากชื่อวิชา/คำอธิบาย/หมวด/หน่วยกิต/รหัสวิชา
    เพื่อให้ vector search หา “ความคล้าย” ได้ดีขึ้น
    """
    parts = []
    # ใส่เฉพาะ field ที่มีค่า (กัน None / empty)
    if name_th:
        parts.append(f"ชื่อวิชา: {name_th}")
    if name_en:
        parts.append(f"English name: {name_en}")
    if desc:
        parts.append(f"คำอธิบาย: {desc}")
    if category:
        parts.append(f"หมวด: {category}")
    # credits อาจเป็น 0 หรือ int ได้ จึงเช็ค is not None
    if credits is not None:
        parts.append(f"หน่วยกิต: {credits}")

    # ใส่รหัสวิชาท้ายสุดเสมอ (ช่วยให้ query ที่อ้างรหัสวิชาตรง ๆ ทำงานได้)
    parts.append(f"รหัสวิชา: {course_code}")

    # join เป็น multi-line text
    return "\n".join(parts)

# ===== ROUTES =====
@app.get("/health")
def health():
    """
    health check endpoint
    ใช้ตรวจว่า service ยังรันอยู่ + อ่าน env ได้
    แถมโชว์ config หลักบางส่วน (model/db/table) เพื่อ debug ง่าย
    """
    return {
        "status": "ok",
        "model": OLLAMA_MODEL,
        "dbHost": DB_HOST,
        "dbName": DB_NAME,
        "courseTable": COURSE_TABLE,
    }

@app.post("/ollama/test")
def ollama_test(req: OllamaTestRequest):
    """
    ยิงไป Ollama เพื่อทดสอบว่า LLM ใช้งานได้จริง
    ไม่เกี่ยวกับ embedding/DB โดยตรง แค่ไว้ confirm ว่า Ollama chat ได้
    """
    resp = ollama.chat(
        model=OLLAMA_MODEL,
        messages=[
            # system prompt กำหนดบทบาท model แบบทั่วไป
            {"role": "system", "content": "You are a helpful assistant."},
            # user ส่งข้อความตามที่รับมาจาก req.text
            {"role": "user", "content": req.text},
        ],
    )
    # คืนข้อความคำตอบออกไป
    return {"reply": resp["message"]["content"]}

@app.post("/courses/embed-one")
def embed_one_course(req: EmbedOneCourseRequest):
    """
    ฝัง embedding ให้กับคอร์ส “1 วิชา” ตาม courseCode
    ขั้นตอน:
    1) SELECT ดึงข้อมูลวิชาจาก DB (courseCode, ชื่อ, คำอธิบาย ฯลฯ)
    2) build_course_text() รวมเป็นข้อความ
    3) embedder.encode() -> vector(1024)
    4) UPDATE ลงคอลัมน์ embedding ในตาราง
    """

    # NOTE: your DB columns are camelCase -> MUST use double quotes in SQL
    # ใน Postgres ถ้าชื่อ column มีตัวพิมพ์ใหญ่/เป็น camelCase จะต้องอ้างด้วย "double quotes"
    sql_select = f"""
        SELECT "courseCode", "courseNameTh", "courseNameEn", "description", "category", "credits"
        FROM {COURSE_TABLE}
        WHERE "courseCode" = %s
        LIMIT 1;
    """

    # UPDATE embedding ของคอร์สที่ระบุ
    # %s::vector คือ cast จาก string representation เป็นชนิด vector ของ pgvector
    sql_update = f"""
        UPDATE {COURSE_TABLE}
        SET embedding = %s::vector
        WHERE "courseCode" = %s;
    """

    # เปิด connection (context manager) เพื่อให้ปิดเองเมื่อจบ block
    with get_conn() as conn:
        # เปิด cursor เพื่อ execute SQL
        with conn.cursor() as cur:
            # 1) ดึงข้อมูลวิชา
            cur.execute(sql_select, (req.courseCode,))
            row = cur.fetchone() #

            # ถ้าไม่เจอวิชา -> คืน ok False
            if not row:
                return {"ok": False, "message": "course not found", "courseCode": req.courseCode}

            # แตก tuple เป็นตัวแปรที่อ่านง่าย
            course_code, name_th, name_en, desc, category, credits = row

            # 2) รวมข้อมูลวิชาให้เป็นข้อความเดียว
            text = build_course_text(course_code, name_th, name_en, desc, category, credits)

            # 3) ทำ embedding: ได้ list[float] ยาว 1024
            vec = embedder.encode(text).tolist()

            # แปลงเป็นรูปแบบ string ที่ pgvector รับได้ เช่น "[0.1, -0.2, ...]"
            vec_str = "[" + ", ".join(map(str, vec)) + "]"

            # 4) UPDATE ลง DB
            cur.execute(sql_update, (vec_str, course_code))

            # commit เพื่อบันทึกการเปลี่ยนแปลงจริง
            conn.commit()

    # คืนผลสำเร็จ + dim เพื่อเช็คว่าได้ 1024 จริง
    return {"ok": True, "courseCode": req.courseCode, "dim": len(vec)}


# DTO สำหรับฝัง embedding แบบ batch เฉพาะแถวที่ยังเป็น NULL
class EmbedMissingRequest(BaseModel):
    limit: int = 20  # ทำทีละ 20 ก่อน ปลอดภัย

@app.post("/courses/embed-missing")
def embed_missing(req: EmbedMissingRequest):
    """
    ฝัง embedding ให้กับคอร์สที่ embedding ยังเป็น NULL (ทำทีละ limit)
    ใช้สำหรับ “เติมของค้าง” หรือ initial embedding ทั้งตารางแบบค่อย ๆ ทำ
    """

    # SELECT เฉพาะคอร์สที่ embedding IS NULL (ยังไม่เคยฝัง)
    # ORDER BY id เพื่อให้รันซ้ำแล้ว predictable / ไล่ตามลำดับ
    sql_select = f"""
        SELECT "courseCode", "courseNameTh", "courseNameEn", "description", "category", "credits"
        FROM {COURSE_TABLE}
        WHERE "embedding" IS NULL
        ORDER BY "id" ASC
        LIMIT %s;
    """

    # UPDATE embedding ของแต่ละคอร์ส
    sql_update = f"""
        UPDATE {COURSE_TABLE}
        SET embedding = %s::vector
        WHERE "courseCode" = %s;
    """

    # ตัวนับว่าทำสำเร็จกี่รายการ
    updated = 0

    # เก็บรายการที่ทำไม่สำเร็จ พร้อม error (เพื่อ debug)
    failed = []

    with get_conn() as conn:
        with conn.cursor() as cur:
            # ดึงรายการที่ต้องทำ embedding
            cur.execute(sql_select, (req.limit,))
            rows = cur.fetchall()

            # วนทำทีละวิชา
            for row in rows:
                course_code, name_th, name_en, desc, category, credits = row
                try:
                    # รวม text
                    text = build_course_text(course_code, name_th, name_en, desc, category, credits)

                    # ฝัง embedding
                    vec = embedder.encode(text).tolist()
                    vec_str = "[" + ", ".join(map(str, vec)) + "]"

                    # update
                    cur.execute(sql_update, (vec_str, course_code))
                    updated += 1
                except Exception as e:
                    # ถ้าพังวิชาไหน ไม่ให้ทั้ง batch ล้ม: เก็บ error แล้วไปต่อ
                    failed.append({"courseCode": course_code, "error": str(e)})

            # commit ทีเดียวหลังทำครบ เพื่อประสิทธิภาพ + atomic ระดับหนึ่ง
            conn.commit()

    return {"ok": True, "updated": updated, "failed": failed}

# DTO สำหรับ RAG endpoint
class RagRequest(BaseModel):
    queryText: str
    topK: int = 3

def query_courses_by_vector(qvec, k: int):
    """
    รับ query vector (qvec) แล้วไปค้นหาในตารางด้วย vector similarity
    หลักการ:
    - ใช้ operator <-> ของ pgvector (distance)
    - ORDER BY distance ASC (ยิ่งน้อย ยิ่งใกล้/คล้าย)
    - LIMIT k รายการ
    """

    # qvec เป็น list[float] -> แปลงเป็น string vector literal
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

    # query DB เพื่อดึง top-k ที่ใกล้ที่สุด
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (qvec_str, k))
            rows = cur.fetchall()

    # แปลงผลลัพธ์เป็น list[dict] ส่งออกเป็น sources
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
            "distance": float(r[7]),  # cast เป็น float เพื่อ JSON serialize ง่าย
        })
    return sources

@app.post("/rag/answer")
def rag_answer(req: RagRequest):
    """
    RAG หลัก:
    1) เอา queryText -> ทำ embedding (qvec)
    2) เอา qvec ไปค้นหา courses ที่ใกล้ที่สุด (sources)
    3) สร้าง CONTEXT จาก sources
    4) ส่ง prompt + context เข้า Ollama ให้ช่วย “เขียนคำตอบ”
    5) คืน {answer, sources} กลับไปให้ Nest/Frontend
    """

    # 1) ฝัง embedding ของคำถามผู้ใช้
    qvec = embedder.encode(req.queryText).tolist()

    # 2) retrieval: หา topK วิชาที่ใกล้ที่สุดตาม vector distance
    sources = query_courses_by_vector(qvec, req.topK)

    # 3) สร้าง context string ให้ LLM เห็นข้อมูลวิชาที่ดึงมา
    # ทำรูปแบบเป็น [1], [2], ... เพื่ออ้างอิงได้
    context = "\n\n".join([
        f"[{i+1}] {s['courseNameTh']} ({s['courseCode']})\n"
        f"EN: {s['courseNameEn']}\n"
        f"Desc: {s['description']}\n"
        f"Category: {s['category']} | Credits: {s['credits']}"
        for i, s in enumerate(sources)
    ])

    # 4) prompt สำหรับ LLM:
    # - กำหนดบทบาท: ผู้ช่วยแนะนำรายวิชา
    # - บังคับให้ตอบโดยอิงจาก CONTEXT
    # - บอก format ที่อยากได้ (ภาษาไทย, กระชับ, 2 ส่วน)
    prompt = (
        "คุณคือผู้ช่วยแนะนำรายวิชาในมหาวิทยาลัย\n"
        "ให้ตอบโดยอิงจากข้อมูลวิชาใน CONTEXT\n\n"
        f"CONTEXT:\n{context}\n\n"
        f"QUESTION: {req.queryText}\n\n"
        "ขอผลลัพธ์เป็นภาษาไทย กระชับ และมี 2 ส่วน:\n"
        "1) answer: สรุปคำแนะนำ 3-6 บรรทัด\n"
        "2) recommendations: bullet list วิชาที่แนะนำพร้อมเหตุผลสั้นๆ\n"
    )

    # 5) เรียก Ollama chat เพื่อให้ LLM สรุป + เขียนคำตอบตาม context
    resp = ollama.chat(
        model=OLLAMA_MODEL,
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt},
        ],
    )

    # ดึงข้อความคำตอบจริง ๆ
    answer = resp["message"]["content"]

    # คืนทั้ง answer และ sources (เพื่อให้ frontend แสดงรายการอ้างอิงได้)
    return {"answer": answer, "sources": sources}
