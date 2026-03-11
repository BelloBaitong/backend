import os
from pydoc import text # ใช้สำหรับอ่าน env variables
from fastapi import FastAPI ,HTTPException, Header   # สร้าง API server ด้วย FastAPI
from pydantic import BaseModel # สร้าง DTO (Data Transfer Object) สำหรับ request/response validation
from dotenv import load_dotenv # โหลดค่าจากไฟล์ .env เพื่อไม่ต้อง hardcode config ในโค้ด
import psycopg2 
from sentence_transformers import SentenceTransformer
import ollama  # สำหรับเรียก LLM ที่รันอยู่ใน Ollama (เช่น llama3.1)

# โหลดตัวแปรสภาพแวดล้อมจากไฟล์ .env (เช่น DB_HOST, DB_NAME, OLLAMA_MODEL ฯลฯ)
load_dotenv()
app = FastAPI() # สร้าง FastAPI application instance ที่เราจะใช้ในการกำหนด routes ของ API server



# ===== ENV =====
# ชื่อโมเดลที่ใช้กับ Ollama (LLM สำหรับ generate คำตอบ)
# ถ้าไม่ได้ตั้ง OLLAMA_MODEL ใน .env จะใช้ "llama3.1" เป็นค่า default
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1")

# ค่าการเชื่อมต่อ PostgreSQL
DB_HOST = os.getenv("DB_HOST", "localhost") # default เป็น localhost ถ้าไม่ตั้งใน env
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME")  # ชื่อฐานข้อมูล (จำเป็น)
DB_USER = os.getenv("DB_USER")  # username (จำเป็น)
DB_PASS = os.getenv("DB_PASS")  # password (จำเป็น)

# ชื่อตารางที่เก็บคอร์ส (ทำให้ปรับเปลี่ยนหรือเพิ่มข้อมูลตารางได้ผ่าน env)
# default คือ "course"
COURSE_TABLE = os.getenv("COURSE_TABLE", "course")  # table name in DB
USER_PROFILE_TABLE = os.getenv("USER_PROFILE_TABLE", "user_profile") # ชื่อตาราง user_profile ใน DB (สำหรับฝัง embedding โปรไฟล์ผู้ใช้)
REVIEW_TABLE = os.getenv("REVIEW_TABLE", "review")

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

# DTO สำหรับ endpoint ที่ฝัง embedding ให้ "วิชาเดียว" (ระบุด้วย courseCode)
class EmbedOneCourseRequest(BaseModel):
    courseCode: str

# ====เตรียมรายวิชาหลายฟิลด์ให้รวมเป็นข้อความเดียว เพื่อส่งเข้า embedding model====
def build_course_text(course_code, name_th, name_en, desc, category, credits):
    """
    รวมข้อมูลวิชาให้เป็นข้อความเดียว (text) เพื่อส่งเข้า embedder
    แนวคิด: embedding ควรถอดความหมายจากชื่อวิชา/คำอธิบาย/หมวด/หน่วยกิต/รหัสวิชา
    เพื่อให้ vector search หา "ความคล้าย" ได้ดีขึ้น
    """
    parts = [] # list เก็บแต่ละส่วนของข้อมูลวิชา
    # if เพื่อ ใส่เฉพาะฟิลด์ ที่มีค่า (กัน None / empty)
    if name_th:
        parts.append(f"ชื่อวิชา: {name_th}")
    if name_en:
        parts.append(f"English name: {name_en}")
    if desc:
        parts.append(f"คำอธิบาย: {desc}")
    if category:
        parts.append(f"หมวด: {category}") #append คือการเพิ่ม string เข้าไปใน list parts
    if credits is not None:
        parts.append(f"หน่วยกิต: {credits}") 
        parts.append(f"รหัสวิชา: {course_code}")

    return "\n".join(parts)  # รวมแต่ละส่วนเป็นข้อความเดียว โดยคั่นด้วย newline  newline ช่วยให้ embedding แยกแยะส่วนต่าง ๆ ได้ดีขึ้น) 

def build_profile_text(study_year, interests, career_goals):

    parts = []

    if study_year:
        parts.append(f"ชั้นปี: {study_year}")

    if interests:
        parts.append(f"ความสนใจ: {', '.join(interests or [])}")

    if career_goals:
        parts.append(f"เป้าหมายอาชีพ: {', '.join(career_goals or [])}")

    return "\n".join(parts)


class EmbedOneProfileRequest(BaseModel):
    userId: int


@app.post("/profiles/embed-one")
def embed_one_profile(req: EmbedOneProfileRequest):

    conn = get_conn()
    cur = conn.cursor()

    cur.execute(f"""
        SELECT id, "studyYear", interests, "careerGoals"
        FROM {USER_PROFILE_TABLE}
        WHERE id = %s
    """, (req.userId,))

    row = cur.fetchone()

    if not row:
        cur.close()
        conn.close()
        return {"ok": False, "error": "profile not found"}

    user_id, study_year, interests, career_goals = row

    text = build_profile_text(study_year, interests, career_goals)

    vec = embedder.encode(text).tolist()

    cur.execute(f"""
        UPDATE {USER_PROFILE_TABLE}
        SET embedding = %s
        WHERE id = %s
    """, (vec, user_id))

    conn.commit()

    cur.close()
    conn.close()

    return {"ok": True, "userId": user_id, "dim": len(vec)}


class EmbedMissingProfilesRequest(BaseModel):
    limit: int = 200


@app.post("/profiles/embed-missing")
def embed_missing_profiles(req: EmbedMissingProfilesRequest):

    conn = get_conn()
    cur = conn.cursor()

    cur.execute(f"""
        SELECT id, "studyYear", interests, "careerGoals"
        FROM {USER_PROFILE_TABLE}
        WHERE embedding IS NULL
        LIMIT %s
    """, (req.limit,))

    rows = cur.fetchall()

    if not rows:
        cur.close()
        conn.close()
        return {"ok": True, "updated": 0}

    updated = 0

    for user_id, study_year, interests, career_goals in rows:

        text = build_profile_text(study_year, interests, career_goals)

        vec = embedder.encode(text).tolist()

        cur.execute(f"""
            UPDATE {USER_PROFILE_TABLE}
            SET embedding = %s
            WHERE id = %s
        """, (vec, user_id))

        updated += 1

    conn.commit()

    cur.close()
    conn.close()

    return {"ok": True, "updated": updated}

class RecommendRequest(BaseModel):
    userId: int
    limit: int = 10


@app.post("/courses/recommend")
def recommend_courses(req: RecommendRequest):
    """
    Hybrid recommendation:
    1) ใช้ user_profile.embedding เป็นหลัก
    2) ถ้า embedding ไม่มี -> สร้างจาก profile ล่าสุดแล้ว save
    3) เอา embedding นี้ไปค้น course.embedding
    """

    conn = get_conn()
    cur = conn.cursor()

    # 1) ดึง profile ของ user คนนี้
    cur.execute(f"""
        SELECT id, "studyYear", interests, "careerGoals", embedding
        FROM {USER_PROFILE_TABLE}
        WHERE "userId" = %s
        LIMIT 1
    """, (req.userId,))

    row = cur.fetchone()

    if not row:
        cur.close()
        conn.close()
        return {"ok": False, "error": "user profile not found"}

    profile_id, study_year, interests, career_goals, profile_embedding = row

    # 2) ถ้า embedding ไม่มี -> สร้างใหม่จาก profile ล่าสุด แล้ว save
    if profile_embedding is None:
        profile_text = build_profile_text(study_year, interests, career_goals)

        if not profile_text.strip():
            cur.close()
            conn.close()
            return {"ok": False, "error": "user profile is empty"}

        vec = embedder.encode(profile_text).tolist()
        vec_str = "[" + ", ".join(map(str, vec)) + "]"

        cur.execute(f"""
            UPDATE {USER_PROFILE_TABLE}
            SET embedding = %s::vector
            WHERE id = %s
        """, (vec_str, profile_id))

        conn.commit()
        profile_embedding = vec_str
    else:
        # ถ้ามี embedding อยู่แล้ว ใช้ได้เลย
        profile_text = build_profile_text(study_year, interests, career_goals)

    # 3) ค้นหา course ที่ใกล้ที่สุดจาก course.embedding
    cur.execute(f"""
        SELECT
            "courseCode",
            "courseNameTh",
            "courseNameEn",
            description,
            credits,
            category,
            "imageUrl",
            embedding <-> %s::vector AS distance
        FROM {COURSE_TABLE}
        WHERE embedding IS NOT NULL
        ORDER BY distance ASC
        LIMIT %s
    """, (profile_embedding, req.limit))

    rows = cur.fetchall()

    cur.close()
    conn.close()

    courses = []
    for courseCode, courseNameTh, courseNameEn, description, credits, category, imageUrl, distance in rows:
        courses.append({
            "courseCode": courseCode,
            "courseNameTh": courseNameTh,
            "courseNameEn": courseNameEn,
            "description": description,
            "credits": credits,
            "category": category,
            "imageUrl": imageUrl,
            "distance": float(distance),
        })

    return {
        "ok": True,
        "userId": req.userId,
        "profileText": profile_text,
        "count": len(courses),
        "courses": courses,
    }

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

@app.post("/courses/embed-one") # endpoint สำหรับฝัง embedding ให้กับคอร์สเดียว (ระบุด้วย courseCode)
def embed_one_course(req: EmbedOneCourseRequest): # รับ request ที่มี courseCode เพื่อระบุว่าคอร์สไหนที่เราจะฝัง embedding
    """
    ฝัง embedding ให้กับคอร์ส "1 วิชา" ตาม courseCode
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
    # รับค่า vector เป็น string แล้วแปลงเป็น vector ใน SQL
    # %s::vector คือ cast จาก string representation เป็นชนิด vector ของ pgvector
    sql_update = f"""
        UPDATE {COURSE_TABLE}
        SET embedding = %s::vector 
        WHERE "courseCode" = %s;
    """

    
    with get_conn() as conn: #เปิด connection ไปยัง PostgreSQL database โดยใช้ฟังก์ชัน get_conn() ที่เราเขียนไว้ข้างต้น ซึ่งจะอ่านค่าการเชื่อมต่อจาก env variables และสร้าง connection object ให้เราใช้งานได้
        # เปิด cursor เพื่อ execute SQL exceute() ใช้สำหรับรันคำสั่ง SQL ต่าง ๆ กับฐานข้อมูล
        with conn.cursor() as cur: 
            # 1) ดึงข้อมูลวิชา
            cur.execute(sql_select, (req.courseCode,))
            row = cur.fetchone() # fetchone() ดึงผลลัพธ์ของ SQL query ซึ่งจะเป็น tuple ที่มีค่าตามคอลัมน์ที่เราเลือกใน sql_select (courseCode, courseNameTh, courseNameEn, description, category, credits) หรือ None ถ้าไม่เจอวิชาที่ระบุด้วย courseCode

            # ถ้าไม่เจอวิชา -> คืน ok False
            if not row:
                return {"ok": False, "message": "course not found", "courseCode": req.courseCode}

            # แตก tuple เป็นตัวแปรที่อ่านง่าย
            course_code, name_th, name_en, desc, category, credits = row

            print("row:", row)
            print("row type:", type(row))

            # 2) รวมข้อมูลวิชาให้เป็นข้อความเดียว
            text = build_course_text(course_code, name_th, name_en, desc, category, credits)
            print("TEXT:\n", text)
            print("TEXT_LEN:", len(text))
            print("Text type:", type(text))

            # 3) ทำ embedding: ได้ list[float] ยาว 1024
            vec = embedder.encode(text).tolist()
            print("VEC_DIM:", len(vec))
            print("VEC_HEAD:", vec[:5])
            print("VEC_TAIL:", vec[-5:])
            print("vec type:", type(vec), flush=True)
            print("vec element type:", type(vec[0]), flush=True)

            # แปลงเป็นรูปแบบ string ที่ pgvector รับได้ เช่น "[0.1, -0.2, ...]"
            vec_str = "[" + ", ".join(map(str, vec)) + "]"
            print("VEC_STR_PREVIEW:", vec_str[:120], "...")
            print("vec_str type:", type(vec_str), flush=True)

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
    ใช้สำหรับ "เติมของค้าง" หรือ initial embedding ทั้งตารางแบบค่อย ๆ ทำ
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


# DTO สำหรับ RAG endpoint request/response ต้องมี field อะไร ชนิดอะไร เวลาเรียก API ต้องส่งข้อมูลหน้าตายังไง
class RagRequest(BaseModel):
    queryText: str # คำถามจากผู้ใช้ (เช่น "แนะนำวิชาที่เกี่ยวกับ AI หน่อย")
    topK: int = 3 # จำนวนวิชาที่อยากได้จาก retrieval (default 3)

def query_courses_by_vector(qvec, k: int): # ฟังก์ชันสำหรับค้นหาวิชาที่ใกล้เคียงกับ query vector (qvec) ที่เราฝังไว้ใน DB
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
    print("rows:", rows)
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
        print("sources:", sources)
    return sources
    

def check_if_course_related_query(query_text: str) -> bool:
    """
    ตรวจสอบว่าคำถามเกี่ยวข้องกับการถามเรื่องรายวิชาหรือไม่
    ใช้ LLM ช่วยตัดสินใจว่าควรค้นหาวิชาหรือแค่ทักทายธรรมดา
    คืนค่า True ถ้าถามเกี่ยวกับวิชา, False ถ้าเป็นแค่ทักทายหรือไม่เกี่ยวกับวิชา
    """
    classification_prompt = f"""วิเคราะห์คำถามต่อไปนี้ว่าเป็นการถามเกี่ยวกับ "รายวิชา" หรือไม่:

คำถาม: "{query_text}"

ตอบเพียง "YES" ถ้าคำถามต้องการข้อมูลเกี่ยวกับรายวิชา/คอร์สเรียน/หลักสูตร
ตอบเพียง "NO" ถ้าเป็นเพียงการทักทาย/สนทนาทั่วไป/ไม่เกี่ยวกับรายวิชา

ตัวอย่าง:
- "สวัสดีค่ะ" -> NO
- "ขอบคุณค่ะ" -> NO  
- "วิชาอะไรดี" -> YES
- "แนะนำวิชาเกี่ยวกับ AI" -> YES
- "รหัสวิชา 05506216 คืออะไร" -> YES
- "มีวิชาเกี่ยวกับการเขียนโปรแกรมไหม" -> YES

ตอบ:"""

    resp = ollama.chat(
        model=OLLAMA_MODEL,
        messages=[
            {"role": "system", "content": "You are a query classifier. Answer only YES or NO."},
            {"role": "user", "content": classification_prompt},
        ],
    )
    
    answer = resp["message"]["content"].strip().upper()
    return "YES" in answer

@app.post("/rag/answer")
def rag_answer(req: RagRequest):
    """
    RAG หลัก:
    0) ตรวจสอบก่อนว่าคำถามเกี่ยวกับรายวิชาหรือไม่
    1) เอา queryText -> ทำ embedding (qvec)
    2) เอา qvec ไปค้นหา courses ที่ใกล้ที่สุด (sources)
    3) สร้าง CONTEXT จาก sources
    4) ส่ง prompt + context เข้า Ollama ให้ช่วย "เขียนคำตอบ"
    5) คืน {answer, sources} กลับไปให้ Nest/Frontend
    """

    # 0) ตรวจสอบว่าคำถามเกี่ยวกับวิชาหรือไม่
    is_course_query = check_if_course_related_query(req.queryText)
    
    # ถ้าไม่เกี่ยวกับวิชา (เช่น แค่ทักทาย) ให้ตอบกลับแบบสนทนาธรรมดาโดยไม่ค้นหาวิชา
    if not is_course_query:
        simple_prompt = f"""คุณคือผู้ช่วยแนะนำรายวิชาในมหาวิทยาลัย
ผู้ใช้ได้ส่งข้อความมาว่า: "{req.queryText}"

ตอบกลับอย่างเป็นมิตรและสุภาพ พร้อมบอกว่าคุณพร้อมช่วยแนะนำรายวิชาถ้าต้องการ
ตอบเป็นภาษาไทย กระชับ ไม่ต้องยาว"""

        resp = ollama.chat(
            model=OLLAMA_MODEL,
            messages=[
                {"role": "system", "content": "You are a friendly course advisor assistant."},
                {"role": "user", "content": simple_prompt},
            ],
        )
        
        answer = resp["message"]["content"]
        # คืนคำตอบโดยไม่มี sources (เพราะไม่ได้ค้นหาวิชา)
        return {"answer": answer, "sources": []}

    # ถ้าเกี่ยวกับวิชา ให้ทำ RAG ตามปกติ
    # 1) ฝัง embedding ของคำถามผู้ใช้
    qvec = embedder.encode(req.queryText).tolist()

    # 2) retrieval: หา topK วิชาที่ใกล้ที่สุดตาม vector distance
    sources = query_courses_by_vector(qvec, req.topK)

    # 3) สร้าง context string ให้ LLM อ่านข้อมูลวิชาที่ดึงมา
    # ทำรูปแบบเป็น [1], [2], ... เพื่ออ้างอิงได้
    context = "\n\n".join([
        f"[{i+1}] {s['courseNameTh']} ({s['courseCode']})\n"
        f"EN: {s['courseNameEn']}\n"
        f"Desc: {s['description']}\n"
        f"Category: {s['category']} | Credits: {s['credits']}"
        for i, s in enumerate(sources)
    ])
    print("CONTEXT:\n", context) #ได้เป็นวิชาที่ใกล้เคียงกับคำถามผู้ใช้ พร้อมรายละเอียดที่ LLM จะใช้ในการเขียนคำตอบ

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
        "2) recommendations: bullet list วิชาที่แนะนำพร้อมเหตุผล\n"
    )

    # 5) เรียก Ollama chat เพื่อให้ LLM สรุป + เขียนคำตอบตาม context
    resp = ollama.chat(
        model=OLLAMA_MODEL,
        messages=[
            {"role": "system", "content": "You are a friendly course advisor assistant."},
            {"role": "user", "content": prompt},
        ],
    )

    # ดึงข้อความคำตอบจริง ๆ
    answer = resp["message"]["content"]

    # คืนทั้ง answer และ sources (เพื่อให้ frontend แสดงรายการอ้างอิงได้)
    return {"answer": answer, "sources": sources}


class CourseSummaryRequest(BaseModel):
    courseId: int
    maxReviews: int = 20

def fetch_course_and_reviews_by_code(course_code: str, max_reviews: int):
    with get_conn() as conn:
        with conn.cursor() as cur:
            # 1) ดึงรายละเอียดวิชา
            cur.execute(f"""
                SELECT
                  c.id,
                  c."courseCode",
                  c."courseNameTh",
                  c."courseNameEn",
                  c.description,
                  c.category,
                  c.credits
                FROM {COURSE_TABLE} c
                WHERE c."courseCode" = %s
                LIMIT 1
            """, (course_code,))
            course = cur.fetchone()

            if not course:
                return None, []

            course_id = course[0]

            # 2) ดึงรีวิว โดยอิง FK "courseId" (ตาม TypeORM)
            cur.execute(f"""
                SELECT
                  r.rating,
                  r.comment,
                  r."isAnonymous",
                  r."createdAt"
                FROM {REVIEW_TABLE} r
                WHERE r."courseId" = %s
                ORDER BY r."createdAt" DESC
                LIMIT %s
            """, (course_id, max_reviews))

            reviews = cur.fetchall()

    return course, reviews


@app.post("/courses/summary")
def summarize_course(req: CourseSummaryRequest):
    course, reviews = fetch_course_and_reviews_by_code(req.courseCode, req.maxReviews)

    if not course:
        raise HTTPException(status_code=404, detail="course not found")

    # ถ้าไม่มีรีวิว -> ส่งสถานะข้อมูลไม่พอ (ให้กล่องขึ้นข้อความตาม requirement)
    if not reviews or len(reviews) == 0:
        return {
            "ok": True,
            "courseCode": req.courseCode,
            "status": "INSUFFICIENT_DATA",
            "summary": None,
        }

    _, course_code, name_th, name_en, desc, category, credits = course

    review_text_lines = []
    for rating, comment, is_anon, created_at in reviews:
        if not comment:
            continue
        review_text_lines.append(f"- rating: {rating} | comment: {comment}")

    # ถ้าทุกอัน comment ว่างหมด ก็ถือว่าข้อมูลไม่พอ
    if len(review_text_lines) == 0:
        return {
            "ok": True,
            "courseCode": req.courseCode,
            "status": "INSUFFICIENT_DATA",
            "summary": None,
        }

    review_text = "\n".join(review_text_lines)

    prompt = f"""
คุณคือผู้ช่วยสรุปรายวิชาสำหรับนักศึกษา (ภาษาไทย)
สรุปโดยอิงจาก "รายละเอียดรายวิชา" และ "รีวิว" เท่านั้น ห้ามเดาเกินข้อมูล

รายละเอียดรายวิชา:
- รหัส: {course_code}
- ชื่อไทย: {name_th}
- ชื่ออังกฤษ: {name_en}
- หมวด: {category}
- หน่วยกิต: {credits}
- คำอธิบาย: {desc}

รีวิวจากผู้เรียน:
{review_text}

ให้สรุปเป็นข้อความสั้น 4-7 บรรทัด ครอบคลุม:
1) ภาพรวมวิชาเรียนอะไร
2) จุดเด่น/ข้อควรระวัง (ตามรีวิว)
3) เหมาะกับใคร
4) ความยาก/งานหนัก (ถ้ามีข้อมูล)

ตอบเป็นภาษาไทยเท่านั้น ไม่ต้องใส่หัวข้อ
""".strip()

    resp = ollama.chat(
        model=OLLAMA_MODEL,
        messages=[
            {"role": "system", "content": "Summarize strictly from provided data. No hallucinations."},
            {"role": "user", "content": prompt},
        ],
    )

    summary = resp["message"]["content"].strip()

    return {
        "ok": True,
        "courseCode": req.courseCode,
        "status": "OK",
        "summary": summary,
    }