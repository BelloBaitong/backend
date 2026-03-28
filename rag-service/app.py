import json
import os
from pydoc import text
import re # ใช้สำหรับอ่าน env variables
from fastapi import FastAPI ,HTTPException, Header   # สร้าง API server ด้วย FastAPI
from pydantic import BaseModel # สร้าง DTO (Data Transfer Object) สำหรับ request/response validation
from dotenv import load_dotenv # โหลดค่าจากไฟล์ .env เพื่อไม่ต้อง hardcode config ในโค้ด
import psycopg2 
from sentence_transformers import SentenceTransformer
import ollama  # สำหรับเรียก LLM ที่รันอยู่ใน Ollama (เช่น llama3.1)
from typing import Any, Literal

# โหลดตัวแปรสภาพแวดล้อมจากไฟล์ .env (เช่น DB_HOST, DB_NAME, OLLAMA_MODEL ฯลฯ)
load_dotenv()
app = FastAPI() # สร้าง FastAPI application instance ที่เราจะใช้ในการกำหนด routes ของ API server



# ===== ENV =====
# ชื่อโมเดลที่ใช้กับ Ollama (LLM สำหรับ generate คำตอบ)
# ถ้าไม่ได้ตั้ง OLLAMA_MODEL ใน .env จะใช้ "llama3.1" เป็นค่า default
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1")
OLLAMA_ANALYZE_MODEL = os.getenv("OLLAMA_ANALYZE_MODEL", OLLAMA_MODEL)
OLLAMA_EXPAND_MODEL = os.getenv("OLLAMA_EXPAND_MODEL", OLLAMA_MODEL)

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
def build_course_text(course_code, name_th, name_en, desc_th, desc_en, category, credits):
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
    if desc_th:
        parts.append(f"คำอธิบายภาษาไทย: {desc_th}")
    if desc_en:
        parts.append(f"English description: {desc_en}")
    if category:
        parts.append(f"หมวด: {category}") #append คือการเพิ่ม string เข้าไปใน list parts
    if credits is not None:
        parts.append(f"หน่วยกิต: {credits}") 
        parts.append(f"รหัสวิชา: {course_code}")

    return "\n".join(parts)  # รวมแต่ละส่วนเป็นข้อความเดียว โดยคั่นด้วย newline  newline ช่วยให้ embedding แยกแยะส่วนต่าง ๆ ได้ดีขึ้น) 

def build_course_text_test(name_th, name_en, desc_th_test, desc_en_test):
    """
    รวมข้อมูลวิชาให้เป็นข้อความเดียว (text) เพื่อส่งเข้า embedder
    แนวคิด: embedding ควรถอดความหมายจากชื่อวิชา/คำอธิบายเฉพาะที่เลือก 
    เพื่อให้ vector search หา "ความคล้าย" ได้ดีขึ้น
    """
    parts = []  # list เก็บแต่ละส่วนของข้อมูลวิชา
    # if เพื่อ ใส่เฉพาะฟิลด์ ที่มีค่า (กัน None / empty)
    if name_th:
        parts.append(f"ชื่อวิชา: {name_th}")
    if name_en:
        parts.append(f"English name: {name_en}")
    if desc_th_test:
        parts.append(f"คำอธิบายภาษาไทย: {desc_th_test}")
    if desc_en_test:
        parts.append(f"English description: {desc_en_test}")
  
    return "\n".join(parts)  # รวมแต่ละส่วนเป็นข้อความเดียว โดยคั่นด้วย newline

def build_profile_text(study_year, interests, career_goals):

    parts = []

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
        SELECT id, interests, "careerGoals"
        FROM {USER_PROFILE_TABLE}
        WHERE id = %s
    """, (req.userId,))

    row = cur.fetchone()

    if not row:
        cur.close()
        conn.close()
        return {"ok": False, "error": "profile not found"}

    user_id,  interests, career_goals = row

    text = build_profile_text( interests, career_goals)

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
    track: Literal["elective", "general"] = "elective"


@app.post("/courses/recommend")
def recommend_courses(req: RecommendRequest):
    result = recommend_courses_core(
        user_id=req.userId,
        query_text=None,
        limit=req.limit,
        mode="profile_only",
        session_context=None,
    )

    return {
        "ok": True,
        "userId": req.userId,
        "profileText": result["profileText"],
        "count": len(result["courses"]),
        "courses": result["courses"],
        "sessionContext": result["sessionContext"],
        "debug": result["debug"],
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
        SELECT "courseCode", "courseNameTh", "courseNameEn", "description", "descriptionEn", "category", "credits"
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
            course_code, name_th, name_en, desc_th, desc_en, category, credits = row

            print("row:", row)
            print("row type:", type(row))

            # 2) รวมข้อมูลวิชาให้เป็นข้อความเดียว
            text = build_course_text(course_code, name_th, name_en, desc_th, desc_en, category, credits)
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
        SELECT "courseCode", "courseNameTh", "courseNameEn", "description", "descriptionEn", "category", "credits"
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
                course_code, name_th, name_en, desc_th, desc_en, category, credits = row
                try:
                    # รวม text
                    text = build_course_text(course_code, name_th, name_en, desc_th, desc_en, category, credits)

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

@app.post("/courses/embed-missing-expand")
def embed_missing(req: EmbedMissingRequest):
    """
    ฝัง embedding ให้กับคอร์สที่ embedding ยังเป็น NULL (ทำทีละ limit)
    ใช้สำหรับ "เติมของค้าง" หรือ initial embedding ทั้งตารางแบบค่อย ๆ ทำ
    โดยใช้เฉพาะคอลัมน์ descriptionExpand สำหรับการฝัง embedding
    และข้ามหาก descriptionExpand เป็นค่าว่างหรือ NULL
    """

    # SELECT เฉพาะคอร์สที่ embedding IS NULL (ยังไม่เคยฝัง) และเลือกคอลัมน์ descriptionExpand
    sql_select = f"""
        SELECT "courseCode", "descriptionExpand"
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

    updated = 0
    failed = []

    with get_conn() as conn:
        with conn.cursor() as cur:
            # ดึงรายการที่ต้องทำ embedding
            cur.execute(sql_select, (req.limit,))
            rows = cur.fetchall()

            for row in rows:
                course_code, desc_expand = row  # ดึงข้อมูลจาก descriptionExpand
                try:
                    # ตรวจสอบว่า descriptionExpand เป็น NULL หรือค่าว่าง
                    if not desc_expand:  # ถ้าเป็น NULL หรือ empty string
                        continue  # ข้ามไปยังวิชาถัดไป

                    # ใช้ descriptionExpand ในการฝัง embedding
                    text = desc_expand

                    # ฝัง embedding
                    vec = embedder.encode(text).tolist()
                    vec_str = "[" + ", ".join(map(str, vec)) + "]"

                    # update embedding ในฐานข้อมูล
                    cur.execute(sql_update, (vec_str, course_code))  # ใช้ course_code ที่ดึงมา
                    updated += 1
                except Exception as e:
                    failed.append({"courseCode": course_code, "error": str(e)})

            # commit หลังจากทำครบทุกอย่าง
            conn.commit()

    return {"ok": True, "updated": updated, "failed": failed}

# DTO สำหรับ RAG endpoint request/response ต้องมี field อะไร ชนิดอะไร เวลาเรียก API ต้องส่งข้อมูลหน้าตายังไง
SYSTEM_CHAT_KEYWORDS = [
    "สวัสดี", "หวัดดี", "hello", "hi", "ขอบคุณ",
    "คุณคือใคร", "ทำอะไรได้บ้าง", "ช่วยอะไรได้บ้าง", "ใช้งานยังไง"
]

FOLLOW_UP_HINTS = [
    "แต่ละวิชา", "วิชาแรก", "วิชาที่สอง", "วิชาที่สาม", "ตัวแรก", "ตัวที่สอง",
    "ตัวที่สาม", "ตัวก่อน", "ตัวก่อนหน้า", "ตัวล่าสุด", "อันนี้", "ตัวนี้", "วิชานี้"
]

CAREER_RULES = [
    {
        "match": ["backend", "backend developer", "java backend", "java developer"],
        "include": ["java", "backend", "api", "database", "web", "software", "architecture", "enterprise", "server", "oop"],
        "exclude": ["android", "mobile", "predictive", "python", "machine learning", "data science"]
    },
    {
        "match": ["frontend", "frontend developer", "web developer", "ui", "ux"],
        "include": ["frontend", "web", "ui", "ux", "javascript", "html", "css", "design"],
        "exclude": ["database", "distributed", "machine learning"]
    },
    {
        "match": ["data science", "data scientist", "machine learning", "ai", "artificial intelligence", "analytics"],
        "include": ["data", "analytics", "machine learning", "ai", "python", "predictive"],
        "exclude": ["android", "mobile"]
    },
    {
        "match": ["mobile", "android", "ios", "mobile developer"],
        "include": ["mobile", "android", "ios", "app", "application"],
        "exclude": ["distributed", "data science"]
    },
]


class RagRequest(BaseModel):
    queryText: str
    topK: int = 5
    userId: int | None = None
    chatHistory: list[dict[str, Any]] | None = None
    sessionContext: dict[str, Any] | None = None
    track: Literal["elective", "general"] | None = None


def normalize_track(track: str | None) -> Literal["elective", "general"]:
    return "general" if track == "general" else "elective"


def resolve_selected_track(
    track: str | None,
    session_context: dict[str, Any] | None = None,
) -> Literal["elective", "general"]:
    saved_track = (session_context or {}).get("selectedTrack")
    return normalize_track(track or saved_track)


def resolve_category_filter(track: str | None) -> str:
    return "GENERAL" if normalize_track(track) == "general" else "ELECTIVE"

def normalize_text(text: str) -> str:
    text = (text or "").strip().lower()
    text = re.sub(r"\s+", " ", text)
    return text


def unique_keep_order(items: list[str]) -> list[str]:
    seen = set()
    output = []
    for item in items:
        if not item:
            continue
        key = item.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        output.append(item.strip())
    return output


def extract_course_code(text: str) -> str | None:
    match = re.search(r"\b\d{8}\b", text or "")
    return match.group(0) if match else None


def row_to_course_dict(row, distance: float | None = None):
    return {
        "courseCode": row[0],
        "courseNameTh": row[1],
        "courseNameEn": row[2],
        "description": row[3],
        "descriptionEn": row[4],
        "descriptionExpand": row[5],
        "category": row[6],
        "credits": row[7],
        "imageUrl": row[8],
        "distance": float(distance if distance is not None else 0.0),
    }


def build_courses_context(courses: list[dict]) -> str:
    return "\n\n".join([
        f"[{i+1}] {course['courseNameTh']} ({course['courseCode']})\n"
        f"EN: {course['courseNameEn']}\n"
        f"Desc: {course['description']}\n"
        f"Desc EN: {course['descriptionEn']}\n"
        f"Category: {course['category']} | Credits: {course['credits']}"
        for i, course in enumerate(courses)
    ])

def build_reviews_context(courses: list[dict], course_reviews: dict[str, str]) -> str:
    lines = []

    for i, course in enumerate(courses, start=1):
        review_text = course_reviews.get(course["courseCode"], "วิชานี้ยังไม่มีรีวิว")

        lines.append(
            f"[{i}] {course['courseNameTh']} ({course['courseCode']})\n"
            f"English name: {course['courseNameEn']}\n"
            f"Review summary: {review_text}"
        )

    return "\n\n".join(lines)


def get_user_profile(user_id: int | None):
    if not user_id:
        return None

    sql = f"""
        SELECT id, "userId", "studyYear", interests, "careerGoals", embedding
        FROM {USER_PROFILE_TABLE}
        WHERE "userId" = %s
        LIMIT 1
    """

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (user_id,))
            row = cur.fetchone()

    if not row:
        return None

    return {
        "profileId": row[0],
        "userId": row[1],
        "studyYear": row[2],
        "interests": row[3],
        "careerGoals": row[4],
        "embedding": row[5],
    }


def upsert_profile_embedding(profile_id: int, profile_text: str):
    if not profile_id or not profile_text.strip():
        return

    vec = embedder.encode(profile_text).tolist()
    vec_str = "[" + ", ".join(map(str, vec)) + "]"

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f'''
                UPDATE {USER_PROFILE_TABLE}
                SET embedding = %s::vector
                WHERE id = %s
                ''',
                (vec_str, profile_id),
            )
            conn.commit()

def get_courses_by_codes(
    course_codes: list[str],
    category_filter: str | None = None,
) -> list[dict]:
    cleaned_codes = [code for code in course_codes if code]
    if not cleaned_codes:
        return []

    where_clauses = ['"courseCode" = ANY(%s)']
    params: list[Any] = [cleaned_codes]

    if category_filter:
        where_clauses.append('"category" = %s')
        params.append(category_filter)

    sql = f"""
        SELECT
            "courseCode",
            "courseNameTh",
            "courseNameEn",
            "description",
            "descriptionEn",
            "descriptionExpand",
            "category",
            "credits",
            "imageUrl"
        FROM {COURSE_TABLE}
        WHERE {' AND '.join(where_clauses)}
    """

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, tuple(params))
            rows = cur.fetchall()

    course_map = {row[0]: row_to_course_dict(row) for row in rows}
    return [course_map[code] for code in cleaned_codes if code in course_map]


def get_rule_keywords_from_text(text: str) -> tuple[list[str], list[str]]:
    q = normalize_text(text)
    include_keywords: list[str] = []
    exclude_keywords: list[str] = []

    for rule in CAREER_RULES:
        if any(keyword in q for keyword in rule["match"]):
            include_keywords.extend(rule["include"])
            exclude_keywords.extend(rule["exclude"])

    return unique_keep_order(include_keywords), unique_keep_order(exclude_keywords)

def fallback_query_analysis(
    query_text: str,
    profile_text: str = "",
    session_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    q = normalize_text(query_text)
    session_context = session_context or {}

    # follow-up ชัด ๆ
    if "วิชาแรก" in q or "ตัวแรก" in q or "วิชาที่ 1" in q:
        return {
            "intent": "follow_up",
            "query_for_embedding": "",
            "include_keywords": [],
            "exclude_keywords": [],
            "mentioned_course_code": None,
            "mentioned_course_name": None,
            "follow_up_target": "first",
            "should_use_profile": False,
            "topic_shift": False,
        }

    if "วิชาที่สอง" in q or "ตัวที่สอง" in q or "วิชาที่ 2" in q:
        return {
            "intent": "follow_up",
            "query_for_embedding": "",
            "include_keywords": [],
            "exclude_keywords": [],
            "mentioned_course_code": None,
            "mentioned_course_name": None,
            "follow_up_target": "second",
            "should_use_profile": False,
            "topic_shift": False,
        }

    if "วิชาที่สาม" in q or "ตัวที่สาม" in q or "วิชาที่ 3" in q:
        return {
            "intent": "follow_up",
            "query_for_embedding": "",
            "include_keywords": [],
            "exclude_keywords": [],
            "mentioned_course_code": None,
            "mentioned_course_name": None,
            "follow_up_target": "third",
            "should_use_profile": False,
            "topic_shift": False,
        }

    if "แต่ละวิชา" in q or "ทุกวิชา" in q or "ทั้งหมดนี้" in q:
        return {
            "intent": "follow_up",
            "query_for_embedding": "",
            "include_keywords": [],
            "exclude_keywords": [],
            "mentioned_course_code": None,
            "mentioned_course_name": None,
            "follow_up_target": "all_previous",
            "should_use_profile": False,
            "topic_shift": False,
        }

    # คุยทั่วไป
    if q in {"สวัสดี", "หวัดดี", "hello", "hi", "ขอบคุณ", "thank you"}:
        return {
            "intent": "chat",
            "query_for_embedding": "",
            "include_keywords": [],
            "exclude_keywords": [],
            "mentioned_course_code": None,
            "mentioned_course_name": None,
            "follow_up_target": "none",
            "should_use_profile": False,
            "topic_shift": False,
        }

    # ขอแนะนำแบบกว้าง ๆ
    broad_recommend_patterns = [
        "แนะนำวิชาให้หน่อย",
        "แนะนำวิชา",
        "มีวิชาอะไรแนะนำบ้าง",
        "ควรเรียนวิชาอะไร",
    ]
    if any(p in q for p in broad_recommend_patterns):
        return {
            "intent": "recommend_courses",
            "query_for_embedding": "",
            "include_keywords": [],
            "exclude_keywords": [],
            "mentioned_course_code": None,
            "mentioned_course_name": None,
            "follow_up_target": "none",
            "should_use_profile": True,
            "topic_shift": False,
        }

    # ถ้ามีรหัสวิชา
    course_code = extract_course_code(query_text)
    if course_code:
        return {
            "intent": "course_detail",
            "query_for_embedding": query_text.strip(),
            "include_keywords": [],
            "exclude_keywords": [],
            "mentioned_course_code": course_code,
            "mentioned_course_name": None,
            "follow_up_target": "none",
            "should_use_profile": False,
            "topic_shift": False,
        }

    return {
        "intent": "recommend_courses",
        "query_for_embedding": query_text.strip(),
        "include_keywords": [],
        "exclude_keywords": [],
        "mentioned_course_code": None,
        "mentioned_course_name": None,
        "follow_up_target": "none",
        "should_use_profile": False,
        "topic_shift": False,
    }

def analyze_query_with_ollama(
    query_text: str,
    profile_text: str = "",
    session_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    session_context = session_context or {}

    # rule-based ก่อน ป้องกันเคสสำคัญพัง
    fallback_first = fallback_query_analysis(query_text, profile_text, session_context)

    q_norm = normalize_text(query_text)

    # ถ้าเป็น follow-up ชัด ๆ หรือ broad recommend ชัด ๆ ไม่ต้องเสี่ยงให้ LLM ตีผิด
    if fallback_first["intent"] == "follow_up":
        return fallback_first

    if fallback_first["intent"] == "recommend_courses" and fallback_first["query_for_embedding"] == "":
        return fallback_first

    # ใช้ profile เฉพาะกรณี profile_only ที่ตั้งใจวิเคราะห์จากโปรไฟล์จริง ๆ
    is_profile_only_analysis = query_text.strip() == "ช่วยวิเคราะห์โปรไฟล์นี้เพื่อแนะนำรายวิชาที่เหมาะสม"
    profile_excerpt = profile_text[:700] if (is_profile_only_analysis and profile_text) else ""
    session_summary = json.dumps(
        {
            "last_intent": session_context.get("last_intent"),
            "last_query": session_context.get("last_query"),
            "last_recommended_courses": session_context.get("last_recommended_courses"),
            "last_focus_course_code": session_context.get("last_focus_course_code"),
        },
        ensure_ascii=False,
    )[:1200]

    prompt = f"""
วิเคราะห์คำถามผู้ใช้เพื่อช่วยระบบค้นหารายวิชา

ห้ามอธิบาย ห้าม markdown
ตอบเป็น JSON เท่านั้น

คำถาม:
{query_text}

โปรไฟล์:
{profile_excerpt or "ไม่มี"}

context ก่อนหน้า:
{session_summary or "ไม่มี"}

schema:
{{
  "intent": "chat | recommend_courses | course_detail | follow_up",
  "query_for_embedding": "",
  "include_keywords": [],
  "exclude_keywords": [],
  "mentioned_course_code": null,
  "mentioned_course_name": null,
  "follow_up_target": "none | all_previous | first | second | third | last | current",
  "should_use_profile": true,
  "topic_shift": false
}}

กติกา:
- คุยทั่วไป -> chat
- ขอแนะนำวิชา -> recommend_courses
- ถามเจาะวิชาเดียว -> course_detail
- ถามต่อจากวิชาก่อนหน้า เช่น "วิชาแรก", "ตัวนี้", "แต่ละวิชา" -> follow_up
- ถ้าคำถามปัจจุบันชัดมาก ให้ should_use_profile = false
- ถ้าคำถามกว้าง เช่น "แนะนำวิชาให้หน่อย" ให้ should_use_profile = true
- query_for_embedding ต้องสั้นและคม ไม่ใช่ย่อหน้ายาว
- ถ้าเป็น broad recommend มาก ๆ ให้ query_for_embedding เป็นค่าว่างได้
- ถ้ามีการอ้างถึงวิชาจาก context ให้ follow_up_target ให้ถูกต้อง
- ถ้าผู้ใช้เริ่มเรื่องใหม่ชัดเจน ให้ topic_shift = true
""".strip()

    try:
        resp = ollama.chat(
            model=OLLAMA_ANALYZE_MODEL,
            messages=[
                {"role": "system", "content": "You are a strict JSON generator."},
                {"role": "user", "content": prompt},
            ],
        )

        print("==== OLLAMA RAW (ANALYZE) ====")
        print(resp)
        print("==== OLLAMA TEXT (ANALYZE) ====")
        print(resp["message"]["content"])


        raw = resp["message"]["content"].strip()
        match = re.search(r"\{.*\}", raw, re.S)
        parsed = json.loads(match.group(0) if match else raw)

        fallback = fallback_query_analysis(query_text, profile_text, session_context)

        result = {
            "intent": parsed.get("intent") or fallback["intent"],
            "query_for_embedding": (parsed.get("query_for_embedding") or fallback["query_for_embedding"]).strip(),
            "include_keywords": list(dict.fromkeys((parsed.get("include_keywords") or []) + fallback["include_keywords"])),
            "exclude_keywords": list(dict.fromkeys((parsed.get("exclude_keywords") or []) + fallback["exclude_keywords"])),
            "mentioned_course_code": parsed.get("mentioned_course_code") or fallback["mentioned_course_code"],
            "mentioned_course_name": parsed.get("mentioned_course_name") or fallback["mentioned_course_name"],
            "follow_up_target": parsed.get("follow_up_target") or fallback["follow_up_target"],
            "should_use_profile": bool(parsed.get("should_use_profile", fallback["should_use_profile"])),
            "topic_shift": bool(parsed.get("topic_shift", False)),
        }
        # ถ้ามี keyword/topic ชัดในคำถาม -> ห้ามใช้ profile
        has_clear_query = bool((result.get("query_for_embedding") or "").strip())
        has_keywords = bool(result.get("include_keywords"))

        if result["intent"] == "recommend_courses":
            result["should_use_profile"] = not (has_clear_query or has_keywords)

        # hard guard เพิ่ม
        if "วิชาแรก" in q_norm or "ตัวแรก" in q_norm:
            result["intent"] = "follow_up"
            result["follow_up_target"] = "first"
            result["should_use_profile"] = False
            result["query_for_embedding"] = ""

        if "แต่ละวิชา" in q_norm or "ทุกวิชา" in q_norm or "ทั้งหมดนี้" in q_norm:
            result["intent"] = "follow_up"
            result["follow_up_target"] = "all_previous"
            result["should_use_profile"] = False
            result["query_for_embedding"] = ""

        return result

    except Exception as e:
        print("analyze_query error:", e)
        return fallback_first

def expand_query_with_ollama(
    query_text: str,
    profile_text: str = "",
    analysis: dict[str, Any] | None = None,
) -> dict[str, Any]:
    analysis = analysis or {}

    prompt = f"""
คุณคือระบบช่วย "ขยายคำค้นสำหรับค้นหารายวิชา" ของนักศึกษา

งานของคุณไม่ใช่การตอบคำถามผู้ใช้โดยตรง
แต่คือการแปลงคำถามของผู้ใช้ให้เป็นคำค้นที่เหมาะกับการค้นหารายวิชาในฐานข้อมูลและ vector retrieval

จงแปลงคำถามของนักศึกษาที่ให้มา
ให้เป็นชุดคำสำคัญ (Keywords) ทางวิชาการทั้งภาษาไทยและอังกฤษ
ที่มักจะปรากฏในหลักสูตรคอมพิวเตอร์
เพื่อใช้ในการค้นหาข้อมูลวิชาที่เกี่ยวข้องที่สุด

ห้ามตอบเป็น prose
ห้ามอธิบายเหตุผล
ตอบเป็น JSON ตาม schema เท่านั้น

ข้อมูลนำเข้า
[คำถามผู้ใช้]
{query_text}

[โปรไฟล์ผู้ใช้]
{profile_text or "ไม่มี"}

[ผลวิเคราะห์เบื้องต้น]
{json.dumps(analysis, ensure_ascii=False)}

schema:
{{
  "expanded_query": "",
  "skill_keywords": [],
  "negative_keywords": []
}}

หลักการทำงาน:
1) เป้าหมายคือช่วย retrieval หา "รายวิชาที่เกี่ยวข้องจริง" ไม่ใช่สร้างประโยคสวย
2) ให้สกัด "แนวคิดวิชาการ / ทักษะ / สาขาย่อย / เทคโนโลยี / คำศัพท์มาตรฐาน" ที่เกี่ยวข้องโดยตรงกับคำถาม
3) ให้ prefer คำที่มีโอกาสพบในชื่อวิชา คำอธิบายรายวิชา หรือหัวข้อวิชาจริง
4) ถ้าคำถามเป็นนามธรรมหรือกว้าง ให้แปลงเป็นคำค้นเชิงวิชาการที่เฉพาะขึ้นได้
5) ถ้ามีคำศัพท์อังกฤษที่เป็นคำมาตรฐานของสาขา และช่วยให้ค้นได้แม่นขึ้น สามารถใส่ร่วมกับภาษาไทยได้
6) อย่าใช้คำกว้าง ฟุ้ง หรือภาษาพูด ถ้ายังไม่ช่วย retrieval มากพอ
7) อย่าใส่คำที่ไกลจากความหมายเดิม หรือเดาจากโปรไฟล์เกินจำเป็น
8) ถ้าคำถามเฉพาะอยู่แล้ว ให้รักษาแกนความหมายเดิมไว้ และเพิ่มเฉพาะคำที่ "อนุมานได้อย่างสมเหตุสมผล"
9) negative_keywords ใส่เฉพาะเมื่อผู้ใช้ "ไม่เอา" บางอย่างชัดเจน หรือมีสิ่งที่ควรตัดออกอย่างชัดเจนจากบริบท
10) ถ้าไม่มีคำขยายที่มั่นใจจริง ให้ตอบแบบ conservative ดีกว่าเดาคำเพิ่มมั่ว ๆ

กติกาการสร้างผลลัพธ์:
- expanded_query:
  - เป็นข้อความสั้น 1 บรรทัด
  - รวมแกนความหมายหลักของคำถาม + คำเชิงวิชาการที่เกี่ยวข้องโดยตรง
  - ไม่เขียนเป็นประโยคยาว
  - ไม่ใส่คำซ้ำ

- skill_keywords:
  - เป็น list ของคำสำคัญ 3-8 คำ
  - แต่ละคำควรเป็น keyword หรือ short phrase ที่ใช้ค้นวิชาได้จริง
  - prefer คำเชิงวิชาการหรือเทคนิค มากกว่าคำกว้างทั่วไป
  - ห้ามใส่คำที่แทบไม่ช่วยแยกวิชา

- negative_keywords:
  - ใส่เฉพาะคำที่ควรหลีกเลี่ยงจริง
  - ถ้าไม่มี ให้เป็น []

แนวทางตัดสินใจเชิงคุณภาพ:
- คำที่ดี = ช่วยแยกสาขา/หัวข้อได้ชัด และมีแนวโน้มอยู่ใน course title/description
- คำที่ไม่ดี = กว้างเกินไป, เป็นคำอธิบายลอย ๆ, หรือไม่ได้ช่วยให้ค้นแม่นขึ้น
- ให้เน้นความแม่นยำมากกว่าความครอบคลุม
- ถ้าไม่แน่ใจ ให้ใส่คำน้อยลง ไม่ต้องเดาเพิ่ม

ห้ามตอบเกิน schema
""".strip()

    try:
        resp = ollama.chat(
            model=OLLAMA_EXPAND_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You expand student queries for university course retrieval. "
                        "Return strict JSON only. "
                        "Convert informal student intent into canonical academic keywords in Thai and English when useful. "
                        "Prefer canonical academic concepts, subfields, technologies, and standard technical terms "
                        "Avoid vague paraphrases and avoid inventing unrelated terms."
                    )
                },
                {"role": "user", "content": prompt},
            ],
        )

        raw = resp["message"]["content"].strip()

        print("==== OLLAMA TEXT (EXPAND) ====")
        print(raw)

        match = re.search(r"\{.*\}", raw, re.S)
        parsed = json.loads(match.group(0) if match else raw)

        return {
            "expanded_query": (parsed.get("expanded_query") or "").strip(),
            "skill_keywords": list(dict.fromkeys(parsed.get("skill_keywords") or [])),
            "negative_keywords": list(dict.fromkeys(parsed.get("negative_keywords") or [])),
        }

    except Exception as e:
        print("expand_query_with_ollama error:", e)
        return {
            "expanded_query": "",
            "skill_keywords": [],
            "negative_keywords": [],
        }

def query_courses_by_vector(
    qvec,
    k: int,
    candidate_limit: int | None = None,
    category_filter: str | None = None,
):
    safe_limit = max(1, candidate_limit or k)
    qvec_str = "[" + ", ".join(map(str, qvec)) + "]"

    where_clauses = ['"embedding" IS NOT NULL']
    params: list[Any] = [qvec_str]

    if category_filter:
        where_clauses.append('"category" = %s')
        params.append(category_filter)

    sql = f"""
        SELECT
            "courseCode",
            "courseNameTh",
            "courseNameEn",
            "description",
            "descriptionEn",
            "descriptionExpand",
            "category",
            "credits",
            "imageUrl",
            embedding <-> %s::vector AS distance
        FROM {COURSE_TABLE}
        WHERE {' AND '.join(where_clauses)}
        ORDER BY distance ASC
        LIMIT %s;
    """

    params.append(safe_limit)

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, tuple(params))
            rows = cur.fetchall()

    return [row_to_course_dict(row[:9], distance=row[9]) for row in rows]

def fetch_reviews_for_courses(courses, limit_per_course: int = 5):
    course_codes = [course["courseCode"] for course in courses if course.get("courseCode")]
    if not course_codes:
        return {}

    sql = f"""
        WITH target_courses AS (
            SELECT id, "courseCode"
            FROM {COURSE_TABLE}
            WHERE "courseCode" = ANY(%s)
        ),
        ranked_reviews AS (
            SELECT
                tc."courseCode",
                r.rating,
                r.comment,
                r."createdAt",
                ROW_NUMBER() OVER (
                    PARTITION BY tc."courseCode"
                    ORDER BY r."createdAt" DESC
                ) AS rn
            FROM target_courses tc
            LEFT JOIN {REVIEW_TABLE} r
                ON r."courseId" = tc.id
        )
        SELECT "courseCode", rating, comment
        FROM ranked_reviews
        WHERE rn <= %s OR rn IS NULL
        ORDER BY "courseCode", rn
    """

    review_map = {code: [] for code in course_codes}

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (course_codes, limit_per_course))
            rows = cur.fetchall()

    for course_code, rating, comment in rows:
        line = None
        if comment and str(comment).strip():
            line = f"Rating: {rating}, Comment: {comment}" if rating is not None else f"Comment: {comment}"
        elif rating is not None:
            line = f"Rating: {rating}"

        if line:
            review_map[course_code].append(line)

    return {
        code: "\n".join(lines) if lines else "วิชานี้ยังไม่มีรีวิว"
        for code, lines in review_map.items()
    }


def find_exact_course_match(
    query_text: str,
    mentioned_course_code: str | None = None,
    mentioned_course_name: str | None = None,
    category_filter: str | None = None,
):
    q = normalize_text(query_text)
    course_code = mentioned_course_code or extract_course_code(query_text)

    with get_conn() as conn:
        with conn.cursor() as cur:
            if course_code:
                sql = f'''
                    SELECT
                        "courseCode",
                        "courseNameTh",
                        "courseNameEn",
                        "description",
                        "descriptionEn",
                        "descriptionExpand",
                        "category",
                        "credits",
                        "imageUrl"
                    FROM {COURSE_TABLE}
                    WHERE "courseCode" = %s
                '''
                params: list[Any] = [course_code]

                if category_filter:
                    sql += ' AND "category" = %s'
                    params.append(category_filter)

                sql += ' LIMIT 1'

                cur.execute(sql, tuple(params))
                row = cur.fetchone()
                if row:
                    return row_to_course_dict(row)

            course_name = normalize_text(mentioned_course_name or "")
            sql = f'''
                SELECT
                    "courseCode",
                    "courseNameTh",
                    "courseNameEn",
                    "description",
                    "descriptionEn",
                    "descriptionExpand",
                    "category",
                    "credits",
                    "imageUrl"
                FROM {COURSE_TABLE}
                WHERE (
                    LOWER(TRIM("courseNameTh")) = %s
                    OR LOWER(TRIM("courseNameEn")) = %s
                    OR LOWER(TRIM("courseCode")) = %s
                )
            '''
            params = [course_name or q, course_name or q, course_name or q]

            if category_filter:
                sql += ' AND "category" = %s'
                params.append(category_filter)

            sql += ' LIMIT 1'

            cur.execute(sql, tuple(params))
            row = cur.fetchone()

    return row_to_course_dict(row) if row else None

def find_course_by_name_in_query(
    query_text: str,
    category_filter: str | None = None,
):
    q = normalize_text(query_text)

    sql = f"""
        SELECT
            "courseCode",
            "courseNameTh",
            "courseNameEn",
            "description",
            "descriptionEn",
            "descriptionExpand",
            "category",
            "credits",
            "imageUrl"
        FROM {COURSE_TABLE}
        WHERE (
            POSITION(LOWER("courseNameTh") IN %s) > 0
            OR POSITION(LOWER("courseNameEn") IN %s) > 0
            OR POSITION(LOWER("courseCode") IN %s) > 0
        )
    """

    params: list[Any] = [q, q, q]

    if category_filter:
        sql += ' AND "category" = %s'
        params.append(category_filter)

    sql += """
        ORDER BY GREATEST(
            LENGTH(COALESCE("courseNameTh", '')),
            LENGTH(COALESCE("courseNameEn", ''))
        ) DESC
        LIMIT 1
    """

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, tuple(params))
            row = cur.fetchone()

    return row_to_course_dict(row) if row else None


def resolve_follow_up_courses(analysis: dict[str, Any], session_context: dict[str, Any] | None):
    if not session_context:
        return []

    items = session_context.get("last_recommended_courses") or []
    course_codes = []
    for item in items:
        code = item.get("courseCode") if isinstance(item, dict) else item
        if code:
            course_codes.append(code)

    if not course_codes:
        return []

    target = analysis.get("follow_up_target") or "none"
    if target == "all_previous":
        return course_codes
    if target == "first":
        return course_codes[:1]
    if target == "second":
        return course_codes[1:2]
    if target == "third":
        return course_codes[2:3]
    if target == "last":
        return course_codes[-1:]

    focus_code = session_context.get("last_focus_course_code")
    if target == "current" and focus_code:
        return [focus_code]

    if target == "current":
        return course_codes[:1]

    return []


def build_retrieval_signal(
    profile_text: str,
    analysis: dict[str, Any],
    mode: str,
    expansion: dict[str, Any] | None = None,
) -> dict[str, Any]:
    expansion = expansion or {}

    query_for_embedding = (analysis.get("query_for_embedding") or "").strip()
    should_use_profile = bool(analysis.get("should_use_profile", True))

    expanded_query = (expansion.get("expanded_query") or "").strip()
    expanded_keywords = list(dict.fromkeys(expansion.get("skill_keywords") or []))
    negative_keywords = list(dict.fromkeys(expansion.get("negative_keywords") or []))

    include_keywords = list(
        dict.fromkeys((analysis.get("include_keywords") or []) + expanded_keywords)
    )
    exclude_keywords = list(
        dict.fromkeys((analysis.get("exclude_keywords") or []) + negative_keywords)
    )

    if mode == "profile_only":
        parts = []

        if profile_text.strip():
            parts.append(profile_text.strip())

        if query_for_embedding:
            parts.append(query_for_embedding)

        if include_keywords:
            parts.append("คำสำคัญ: " + ", ".join(include_keywords))

        embedding_text = "\n".join([p for p in parts if p]).strip()

        return {
            "embedding_text": embedding_text or profile_text,
            "include_keywords": include_keywords,
            "exclude_keywords": exclude_keywords,
            "used_profile": True,
        }

    parts = []

    if query_for_embedding:
        parts.append(query_for_embedding)

    if expanded_query:
        parts.append(expanded_query)

    if include_keywords:
        parts.append("คำสำคัญ: " + ", ".join(include_keywords))

    if should_use_profile and profile_text.strip():
        parts.append("โปรไฟล์ที่เกี่ยวข้อง: " + profile_text.strip())

    embedding_text = "\n".join([p for p in parts if p]).strip()

    return {
        "embedding_text": embedding_text or expanded_query or query_for_embedding or profile_text,
        "include_keywords": include_keywords,
        "exclude_keywords": exclude_keywords,
        "used_profile": should_use_profile and bool(profile_text.strip()),
    }

def score_course_candidate(
    course: dict,
    query_text: str,
    include_keywords: list[str],
    exclude_keywords: list[str],
    exact_course_code: str | None = None,
    exact_course_name: str | None = None,
    preferred_codes: list[str] | None = None,
) -> float:
    title_th = normalize_text(str(course.get("courseNameTh", "") or ""))
    title_en = normalize_text(str(course.get("courseNameEn", "") or ""))
    code_text = normalize_text(str(course.get("courseCode", "") or ""))
    category_text = normalize_text(str(course.get("category", "") or ""))

    main_text = normalize_text(
        str(course.get("descriptionExpand", "") or "")
        or str(course.get("description", "") or "")
        or str(course.get("descriptionEn", "") or "")
    )

    score = 0.0

    # 1) include keywords
    for keyword in include_keywords:
        k = normalize_text(keyword)
        if not k:
            continue

        if k == code_text or k in title_th or k in title_en:
            score += 3.0
        elif k in main_text:
            score += 1.5

    # 2) exclude keywords
    for keyword in exclude_keywords:
        k = normalize_text(keyword)
        if not k:
            continue

        if k in title_th or k in title_en:
            score -= 3.0
        elif k in main_text:
            score -= 1.5

    # 3) token overlap จาก query จริง
    query_tokens = {
        token
        for token in re.split(r"[^\wก-๙]+", normalize_text(query_text))
        if len(token) >= 3
    }

    overlap_title = 0
    overlap_main = 0

    for token in query_tokens:
        if token == code_text or token in title_th or token in title_en:
            overlap_title += 1
        elif token in main_text:
            overlap_main += 1

    score += min(overlap_title, 4) * 1.2
    score += min(overlap_main, 6) * 0.4

    # 4) exact code
    if exact_course_code and course.get("courseCode") == exact_course_code:
        score += 20.0

    # 5) exact name
    exact_name = normalize_text(exact_course_name or "")
    if exact_name and (exact_name == title_th or exact_name == title_en):
        score += 12.0

    # 6) preferred codes
    if preferred_codes and course.get("courseCode") in preferred_codes:
        score += 15.0

    # 7) penalty วิชาทั่วไป
    if "general" in category_text or "ศึกษาทั่วไป" in category_text:
        score -= 0.5

    return score

def rerank_course_candidates(
    candidates: list[dict],
    query_text: str,
    analysis: dict[str, Any],
    signal: dict[str, Any],
    limit: int,
    preferred_codes: list[str] | None = None,
) -> list[dict]:
    include_keywords = signal.get("include_keywords", []) or []
    exclude_keywords = signal.get("exclude_keywords", []) or []

    exact_course_code = analysis.get("mentioned_course_code")
    exact_course_name = analysis.get("mentioned_course_name")

    if not candidates:
        return []

    distances = [float(c.get("distance", 999.0)) for c in candidates]
    min_d = min(distances)
    max_d = max(distances)

    reranked = []

    for course in candidates:
        base_distance = float(course.get("distance", 999.0))

        rule_score = score_course_candidate(
            course=course,
            query_text=query_text,
            include_keywords=include_keywords,
            exclude_keywords=exclude_keywords,
            exact_course_code=exact_course_code,
            exact_course_name=exact_course_name,
            preferred_codes=preferred_codes,
        )

        # normalize distance -> dense score 0..1
        if max_d > min_d:
            dense_score = 1.0 - ((base_distance - min_d) / (max_d - min_d))
        else:
            dense_score = 1.0

        # ให้ dense มีผล แต่ไม่กลบ rule ทั้งหมด
        semantic_bonus = dense_score * 2.0
        final_score = rule_score + semantic_bonus

        item = dict(course)
        item["ruleScore"] = rule_score
        item["denseScore"] = dense_score
        item["semanticBonus"] = semantic_bonus
        item["finalScore"] = final_score

        reranked.append(item)

    reranked.sort(
        key=lambda x: (
            -x["finalScore"],
            x.get("distance", 999.0),
            x.get("courseCode", ""),
        )
    )

    return reranked[: max(1, min(limit, 10))]

def print_ranked_courses(label: str, courses: list[dict]):
    """
    ใช้สำหรับ print ลำดับวิชาที่ระบบ "จัดอันดับเสร็จแล้ว"

    ข้อมูลที่ print ออกมาแต่ละช่องหมายถึง:
    - distance:
        ระยะห่างจาก vector search (embedding similarity)
        ยิ่งน้อย = ยิ่งใกล้กับ query/profie text ที่เอาไปค้น

    - ruleScore:
        คะแนนจากกฎฝั่ง backend ใน score_course_candidate()
        เช่น keyword match, token overlap, exact match,
        preferred course, penalty บางอย่าง ฯลฯ

    - semanticBonus:
        คะแนนเสริมจาก distance
        คำนวณจาก max(0.0, 3.0 - distance)
        ใช้เพื่อเอาความใกล้เชิง semantic มาช่วยเพิ่มคะแนน

    - finalScore:
        คะแนนสุดท้ายหลัง rerank
        = ruleScore + semanticBonus

    สรุป:
    log นี้คือ "ผลลำดับสุดท้ายที่ backend จัดเสร็จแล้ว"
    ก่อนจะไป fetch review / ส่งต่อให้ generate_course_answer()
    """
    print(f"\n==== RERANKED COURSES [{label}] ====")

    if not courses:
        print("(no courses)")
        return

    for i, c in enumerate(courses, start=1):
        print(
            f"{i}. "
            f"code={c.get('courseCode')} | "
            f"nameTh={c.get('courseNameTh')} | "
            f"distance={c.get('distance')} | "
            f"ruleScore={c.get('ruleScore')} | "
            f"semanticBonus={c.get('semanticBonus')} | "
            f"finalScore={c.get('finalScore')}"
        )


def recommend_courses_core(
    user_id: int | None,
    query_text: str | None,
    limit: int,
    mode: Literal["profile_only", "query_aware"],
    session_context: dict[str, Any] | None = None,
    category_filter: str | None = None,
) -> dict[str, Any]:
    session_context = session_context or {}
    safe_limit = max(1, min(limit, 10))

    profile = get_user_profile(user_id) if user_id else None

    profile_text = ""
    if profile:
        profile_text = build_profile_text(
            profile.get("studyYear"),
            profile.get("interests"),
            profile.get("careerGoals"),
        )

    # =========================
    # profile_only
    # =========================
    if mode == "profile_only":
        if not profile:
            raise HTTPException(status_code=404, detail="user profile not found")

        if not profile_text.strip():
            raise HTTPException(status_code=400, detail="user profile is empty")

        analysis = analyze_query_with_ollama(
            query_text="ช่วยวิเคราะห์โปรไฟล์นี้เพื่อแนะนำรายวิชาที่เหมาะสม",
            profile_text=profile_text,
            session_context=None,
        )

        analysis["intent"] = "recommend_courses"
        analysis["should_use_profile"] = True
        analysis["topic_shift"] = False

        signal = build_retrieval_signal(
            profile_text=profile_text,
            analysis=analysis,
            mode="profile_only",
            expansion=None,
        )

        print("\n==== BEFORE EMBEDDING [profile_only] ====")
        print("embedding_text:", signal["embedding_text"])
        print("include_keywords:", signal["include_keywords"])
        print("exclude_keywords:", signal["exclude_keywords"])
        print("used_profile:", signal["used_profile"])

        qvec = embedder.encode(signal["embedding_text"]).tolist()
        candidate_limit = max(safe_limit * 4, 20)

        candidates = query_courses_by_vector(
            qvec=qvec,
            k=safe_limit,
            candidate_limit=candidate_limit,
            category_filter=category_filter,
        )
        courses = rerank_course_candidates(
            candidates=candidates,
            query_text=signal["embedding_text"],
            analysis=analysis,
            signal=signal,
            limit=safe_limit,
            preferred_codes=None,
        )

        reviews = fetch_reviews_for_courses(courses) if courses else {}

        next_session_context = {
            "last_intent": "recommend_courses",
            "last_query": "",
            "last_recommended_courses": [
                {
                    "courseCode": c["courseCode"],
                    "courseNameTh": c["courseNameTh"],
                    "courseNameEn": c["courseNameEn"],
                }
                for c in courses
            ],
            "last_focus_course_code": courses[0]["courseCode"] if len(courses) == 1 else None,
            "last_query_analysis": analysis,
        }

        return {
            "profile": profile,
            "profileText": profile_text,
            "analysis": analysis,
            "expansion": None,
            "signal": signal,
            "courses": courses,
            "reviews": reviews,
            "sessionContext": next_session_context,
            "debug": {
                "mode": "profile_only",
                "intent": analysis.get("intent"),
                "queryForEmbedding": analysis.get("query_for_embedding"),
                "expandedQuery": "",
                "includeKeywords": signal.get("include_keywords", []),
                "excludeKeywords": signal.get("exclude_keywords", []),
                "expandedKeywords": [],
                "negativeKeywords": [],
                "embeddingText": signal.get("embedding_text", ""),
                "usedProfile": signal.get("used_profile", False),
                "candidateCount": len(candidates),
                "source": "profile_embedding",
            },
        }

    # =========================
    # query_aware
    # =========================
    effective_query = (query_text or "").strip()
    if not effective_query:
        raise HTTPException(status_code=400, detail="queryText is required")

    analysis = analyze_query_with_ollama(
        query_text=effective_query,
        profile_text=profile_text,
        session_context=session_context,
    )
    selected_track = normalize_track((session_context or {}).get("selectedTrack"))

# ถ้าเป็นวิชาศึกษาทั่วไป อย่าใช้โปรไฟล์สายคอมมาปน
    if selected_track == "general":
        analysis["should_use_profile"] = False

    # สำหรับ GENERAL ถ้ามี query จริง และไม่ใช่ greeting ชัด ๆ
# ให้ถือว่าเป็นการขอแนะนำวิชา ไม่ใช่ chat
    if (
        selected_track == "general"
        and analysis.get("intent") == "chat"
        and effective_query
        and normalize_text(effective_query) not in {"สวัสดี", "หวัดดี", "hello", "hi", "ขอบคุณ", "thank you"}
    ):
        analysis["intent"] = "recommend_courses"
        analysis["query_for_embedding"] = effective_query
        analysis["should_use_profile"] = False

    if analysis.get("topic_shift"):
        session_context = {}

    # broad recommend → ใช้ profile-first
    if (
        analysis.get("intent") == "recommend_courses"
        and not (analysis.get("query_for_embedding") or "").strip()
    ):
        profile_result = recommend_courses_core(
            user_id=user_id,
            query_text=None,
            limit=safe_limit,
            mode="profile_only",
            session_context=session_context,
            category_filter=category_filter,
        )

        profile_result["analysis"] = {
            **profile_result["analysis"],
            "intent": "recommend_courses",
            "follow_up_target": "none",
            "topic_shift": False,
        }

        profile_result["sessionContext"] = {
            **profile_result["sessionContext"],
            "last_intent": "recommend_courses",
            "last_query": effective_query,
            "last_query_analysis": analysis,
        }

        profile_result["debug"] = {
            **profile_result["debug"],
            "source": "profile_only_fallback_from_query",
        }

        return profile_result

    if analysis.get("intent") == "chat":
        return {
            "profile": profile,
            "profileText": profile_text,
            "analysis": analysis,
            "expansion": None,
            "signal": {
                "embedding_text": "",
                "include_keywords": [],
                "exclude_keywords": [],
                "used_profile": False,
            },
            "courses": [],
            "reviews": {},
            "sessionContext": {
                **session_context,
                "last_intent": "chat",
                "last_query": effective_query,
                "last_query_analysis": analysis,
            },
            "debug": {
                "mode": "query_aware",
                "intent": "chat",
                "candidateCount": 0,
                "source": "chat_only",
            },
        }

    preferred_codes = None
    follow_up_target = analysis.get("follow_up_target")

    if follow_up_target and follow_up_target != "none":
        previous = session_context.get("last_recommended_courses") or []
        previous_codes = [
            item["courseCode"] if isinstance(item, dict) else item
            for item in previous
            if item
        ]

        if previous_codes:
            if follow_up_target == "all_previous":
                preferred_codes = previous_codes[:safe_limit]
            elif follow_up_target == "first" and len(previous_codes) >= 1:
                preferred_codes = [previous_codes[0]]
            elif follow_up_target == "second" and len(previous_codes) >= 2:
                preferred_codes = [previous_codes[1]]
            elif follow_up_target == "third" and len(previous_codes) >= 3:
                preferred_codes = [previous_codes[2]]
            elif follow_up_target == "last" and len(previous_codes) >= 1:
                preferred_codes = [previous_codes[-1]]
            elif follow_up_target == "current":
                current_code = session_context.get("last_focus_course_code")
                if current_code:
                    preferred_codes = [current_code]

    if preferred_codes:
        courses = get_courses_by_codes(preferred_codes, category_filter=category_filter,)
        reviews = fetch_reviews_for_courses(courses) if courses else {}

        next_session_context = {
            **session_context,
            "last_intent": analysis.get("intent"),
            "last_query": effective_query,
            "last_recommended_courses": [
                {
                    "courseCode": c["courseCode"],
                    "courseNameTh": c["courseNameTh"],
                    "courseNameEn": c["courseNameEn"],
                }
                for c in courses
            ],
            "last_focus_course_code": courses[0]["courseCode"] if len(courses) == 1 else None,
            "last_query_analysis": analysis,
        }

        return {
            "profile": profile,
            "profileText": profile_text,
            "analysis": analysis,
            "expansion": None,
            "signal": {
                "embedding_text": "",
                "include_keywords": analysis.get("include_keywords", []),
                "exclude_keywords": analysis.get("exclude_keywords", []),
                "used_profile": False,
            },
            "courses": courses,
            "reviews": reviews,
            "sessionContext": next_session_context,
            "debug": {
                "mode": "query_aware",
                "intent": analysis.get("intent"),
                "candidateCount": len(courses),
                "source": "follow_up_context",
                "preferredCodes": preferred_codes,
            },
        }

    exact_course = find_exact_course_match(
    query_text=effective_query,
    mentioned_course_code=analysis.get("mentioned_course_code"),
    mentioned_course_name=analysis.get("mentioned_course_name"),
    category_filter=category_filter,
)

    if not exact_course:
        exact_course = find_course_by_name_in_query(
            effective_query,
            category_filter=category_filter,
        )

    if exact_course:
        courses = [exact_course]
        reviews = fetch_reviews_for_courses(courses)

        next_session_context = {
            **session_context,
            "last_intent": analysis.get("intent"),
            "last_query": effective_query,
            "last_recommended_courses": [
                {
                    "courseCode": exact_course["courseCode"],
                    "courseNameTh": exact_course["courseNameTh"],
                    "courseNameEn": exact_course["courseNameEn"],
                }
            ],
            "last_focus_course_code": exact_course["courseCode"],
            "last_query_analysis": analysis,
        }

        return {
            "profile": profile,
            "profileText": profile_text,
            "analysis": analysis,
            "expansion": None,
            "signal": {
                "embedding_text": "",
                "include_keywords": analysis.get("include_keywords", []),
                "exclude_keywords": analysis.get("exclude_keywords", []),
                "used_profile": False,
            },
            "courses": courses,
            "reviews": reviews,
            "sessionContext": next_session_context,
            "debug": {
                "mode": "query_aware",
                "intent": analysis.get("intent"),
                "candidateCount": 1,
                "source": "exact_match",
            },
        }

    expansion = expand_query_with_ollama(
        query_text=effective_query,
        profile_text=profile_text,
        analysis=analysis,
    )

    signal = build_retrieval_signal(
        profile_text=profile_text,
        analysis=analysis,
        mode="query_aware",
        expansion=expansion,
    )

    print("\n==== BEFORE EMBEDDING [query_aware] ====")
    print("embedding_text:", signal["embedding_text"])
    print("include_keywords:", signal["include_keywords"])
    print("exclude_keywords:", signal["exclude_keywords"])
    print("used_profile:", signal["used_profile"])

    qvec = embedder.encode(signal["embedding_text"]).tolist()
    candidate_limit = max(safe_limit * 4, 20)

    candidates = query_courses_by_vector(
        qvec=qvec,
        k=safe_limit,
        candidate_limit=candidate_limit,
        category_filter=category_filter,
    )
    print("==== RAW VECTOR CANDIDATES ====")
    for i, c in enumerate(candidates, 1):
        print(f"{i}. {c.get('courseCode')} | {c.get('courseNameTh')} | distance={c.get('distance')}")
            


    courses = rerank_course_candidates(
        candidates=candidates,
        query_text=effective_query,
        analysis=analysis,
        signal=signal,
        limit=safe_limit,
        preferred_codes=None,
    )

    reviews = fetch_reviews_for_courses(courses) if courses else {}

    next_session_context = {
        **session_context,
        "last_intent": analysis.get("intent"),
        "last_query": effective_query,
        "last_recommended_courses": [
            {
                "courseCode": c["courseCode"],
                "courseNameTh": c["courseNameTh"],
                "courseNameEn": c["courseNameEn"],
            }
            for c in courses
        ],
        "last_focus_course_code": courses[0]["courseCode"] if len(courses) == 1 else None,
        "last_query_analysis": analysis,
    }

    return {
        "profile": profile,
        "profileText": profile_text,
        "analysis": analysis,
        "expansion": expansion,
        "signal": signal,
        "courses": courses,
        "reviews": reviews,
        "sessionContext": next_session_context,
        "debug": {
            "mode": "query_aware",
            "intent": analysis.get("intent"),
            "queryForEmbedding": analysis.get("query_for_embedding"),
            "expandedQuery": expansion.get("expanded_query", ""),
            "includeKeywords": signal.get("include_keywords", []),
            "excludeKeywords": signal.get("exclude_keywords", []),
            "expandedKeywords": expansion.get("skill_keywords", []),
            "negativeKeywords": expansion.get("negative_keywords", []),
            "embeddingText": signal.get("embedding_text", ""),
            "usedProfile": signal.get("used_profile", False),
            "candidateCount": len(candidates),
            "source": "vector_plus_rerank",
        },
    }


def generate_chat_answer(query_text: str) -> str:
    prompt = f'''
คุณคือผู้ช่วยแนะนำรายวิชาในมหาวิทยาลัย
ผู้ใช้ส่งข้อความว่า: "{query_text}"

ตอบอย่างเป็นมิตร กระชับ และบอกว่า หากผู้ใช้ต้องการสามารถช่วยแนะนำรายวิชา อธิบายวิชา หรือสรุปรีวิวได้
'''.strip()

    resp = ollama.chat(
        model=OLLAMA_MODEL,
        messages=[
            {"role": "system", "content": "You are a friendly course advisor assistant."},
            {"role": "user", "content": prompt},
        ],
    )
    
    return resp["message"]["content"].strip()



def generate_course_answer(query_text: str, engine_result: dict[str, Any]) -> str:
    courses = engine_result.get("courses", []) or []
    reviews = engine_result.get("reviews", {}) or {}
    analysis = engine_result.get("analysis", {}) or {}

    intent = analysis.get("intent", "recommend_courses")
    # 🔥 กันกรณีมีวิชาเดียว แต่มีหลาย review
    unique_course_codes = {c["courseCode"] for c in courses}

    if len(unique_course_codes) == 1:
        # มีวิชาเดียว → อย่าให้ LLM ไป generate แบบ list 3 อัน
        intent = "course_detail"

    if not courses:
        if intent == "chat":
            prompt = f"""
You are a university course recommendation assistant.

User message: "{query_text}"

Reply in Thai in a friendly and concise way.
Explain that you can help with:
- recommending courses based on interests
- explaining course content
- summarizing student reviews
- comparing courses
""".strip()

            resp = ollama.chat(
                model=OLLAMA_MODEL,
                messages=[
                    {"role": "system", "content": "You are a friendly university course assistant."},
                    {"role": "user", "content": prompt},
                ],
            )
            return resp["message"]["content"].strip()

        return "ยังไม่พบรายวิชาที่ตรงกับคำถามนี้ในฐานข้อมูล"

    if intent == "recommend_courses" and len(courses) >= 5:
        courses = courses[: max(5, min(len(courses), 10))]

    print("==== COURSES PASSED TO OLLAMA ====")
    for i, c in enumerate(courses, 1):
        print(
            f"{i}. {c.get('courseCode')} | "
            f"{c.get('courseNameTh')} | "
            f"finalScore={c.get('finalScore')}"
        )

    context = build_courses_context(courses)
    print("==== GENERATED CONTEXT ====")
    print(context)
    reviews_context = build_reviews_context(courses, reviews)

    if intent == "follow_up":
        answer_style = """
This is a follow-up question.
Answer using only the courses in CONTEXT.

Rules:
- If the user asks what each course is about, explain each course one by one.
- If the user refers to "the first course" or "this one", answer only the relevant course.
- If reviews are mentioned, include course code, Thai course name, and English course name.
- If there is no review, write exactly: "(วิชานี้ยังไม่มีรีวิว)"
- Do not mention any course outside CONTEXT.
"""
    elif intent == "course_detail":
        answer_style = """
The user is asking about a specific course.
Answer only using the relevant course in CONTEXT.

Required format:
- Thai course name (course code) / English course name
- Explain what the course is about
- Explain what skills the student will gain
- Mention whether reviews exist

Rules:
- If there is no review, write exactly: "(วิชานี้ยังไม่มีรีวิว)"
- If CONTEXT contains only one course, do not recommend any additional courses.
- Do not use any information outside CONTEXT and REVIEWS.
"""
    else:
        answer_style = """
The user is asking for course recommendations.

You must follow this format exactly.

**คำแนะนำภาพรวม**
Write one short overview paragraph.

**วิชาที่แนะนำ**
Always recommend at least 5 courses if CONTEXT contains 5 or more courses.
- If CONTEXT has fewer than 5 courses, recommend all available courses.
- Do not answer with fewer than 5 courses if CONTEXT contains 5 or more courses.

For each course, use exactly this format:
• **[ลำดับ] ชื่อวิชาภาษาไทย (รหัสวิชา) / ชื่อวิชาภาษาอังกฤษ**: 1-2 sentences explaining why this course is recommended

**สรุปรีวิวจากนักศึกษา**
For each course, use exactly this format:
• **[ลำดับ] ชื่อวิชาภาษาไทย (รหัสวิชา) / ชื่อวิชาภาษาอังกฤษ**: [review summary]

If there is no review, use exactly this format:
• **[ลำดับ] ชื่อวิชาภาษาไทย (รหัสวิชา) / ชื่อวิชาภาษาอังกฤษ**: (วิชานี้ยังไม่มีรีวิว)

Strict requirements:
- Always include course code + Thai name + English name in both the recommendation section and the review section
- Do not add a final note such as "หมายเหตุ: ..."
- If a course has no review, append "(วิชานี้ยังไม่มีรีวิว)" directly to that course
- Do not answer with fewer than 5 courses if CONTEXT contains 5 or more courses
- Do not use any information outside CONTEXT and REVIEWS
- Do not invent reviews
"""
    prompt = f"""
You are a university course recommendation assistant.
Answer using CONTEXT and REVIEWS only.

Important rules:
- Do not recommend any course outside CONTEXT
- Do not guess or add technologies/tools that are not explicitly in the course data
- If no review exists, do not invent one
- If no review exists, use exactly: "(วิชานี้ยังไม่มีรีวิว)"
- For course recommendations, strictly follow the required headings and bullet format
- In the "สรุปรีวิวจากนักศึกษา" section, keep the same course order as in the "วิชาที่แนะนำ" section

Response instructions:
{answer_style}


Question analysis:
{json.dumps(analysis, ensure_ascii=False, indent=2)}

CONTEXT:
{context}

REVIEWS:
{reviews_context}

User question:
{query_text}

Final answer requirements:
- Write the final answer in Thai
- Keep it concise, clear, and easy to read
- Preserve the exact Thai section headings shown above
""".strip()

    try:
        resp = ollama.chat(
            model=OLLAMA_MODEL,
            messages=[
                {"role": "system", "content": "You are a precise university course advisor. Follow instructions exactly and answer in Thai when requested."},
                {"role": "user", "content": prompt},
            ],
        )
        answer = resp["message"]["content"].strip()
    except Exception:
        if intent == "recommend_courses":
            lines = []
            lines.append("**คำแนะนำภาพรวม**")
            lines.append("จากข้อมูลรายวิชาที่พบ ระบบได้คัดเลือกวิชาที่มีความเกี่ยวข้องกับคำถามของคุณและน่าจะช่วยต่อยอดความรู้หรือทักษะที่ต้องการได้")
            lines.append("")
            lines.append("**วิชาที่แนะนำ**")

            for i, c in enumerate(courses[: max(5, min(len(courses), 6))], start=1):
                lines.append(
                    f"• **[{i}] {c.get('courseNameTh', '-')} ({c.get('courseCode', '-')}) / {c.get('courseNameEn', '-')}**: "
                    f"วิชานี้มีเนื้อหาที่สอดคล้องกับคำถามและสามารถช่วยต่อยอดความรู้ในด้านที่คุณสนใจได้"
                )

            lines.append("")
            lines.append("**สรุปรีวิวจากนักศึกษา**")

            for i, c in enumerate(courses[: max(5, min(len(courses), 6))], start=1):
                review_text = reviews.get(c.get("courseCode", ""), "")
                if not review_text or "ยังไม่มีรีวิว" in review_text:
                    lines.append(
                        f"• **[{i}] {c.get('courseNameTh', '-')} ({c.get('courseCode', '-')}) / {c.get('courseNameEn', '-')}**: "
                        f"(วิชานี้ยังไม่มีรีวิว)"
                    )
                else:
                    lines.append(
                        f"• **[{i}] {c.get('courseNameTh', '-')} ({c.get('courseCode', '-')}) / {c.get('courseNameEn', '-')}**: "
                        f"{review_text}"
                    )

            return "\n".join(lines)

        return "ขออภัย ระบบยังไม่สามารถสรุปคำตอบได้ในขณะนี้"

    return answer


def get_user_career_goals(user_id: int):
    profile = get_user_profile(user_id)
    return profile.get("careerGoals") if profile else None




@app.post("/rag/answer")
def rag_answer(req: RagRequest):
    selected_track = resolve_selected_track(req.track, req.sessionContext)
    category_filter = resolve_category_filter(selected_track)

    merged_session_context = {
        **(req.sessionContext or {}),
        "selectedTrack": selected_track,
    }

    result = recommend_courses_core(
        user_id=req.userId,
        query_text=req.queryText,
        limit=req.topK,
        mode="query_aware",
        session_context=merged_session_context,
        category_filter=category_filter,
    )

    result["sessionContext"] = {
        **(result.get("sessionContext") or {}),
        "selectedTrack": selected_track,
    }

    answer = generate_course_answer(req.queryText, result)

    return {
        "answer": answer,
        "sources": result["courses"],
        "sessionContext": result["sessionContext"],
        "debug": {
            **result["debug"],
            "selectedTrack": selected_track,
            "categoryFilter": category_filter,
        },
    }

@app.post("/rag/answer-career")
def rag_answer_career(req: RagRequest):
    selected_track = resolve_selected_track(req.track, req.sessionContext)
    category_filter = resolve_category_filter(selected_track)

    merged_session_context = {
        **(req.sessionContext or {}),
        "selectedTrack": selected_track,
    }

    result = recommend_courses_core(
        user_id=req.userId,
        query_text=req.queryText,
        limit=req.topK,
        mode="query_aware",
        session_context=merged_session_context,
        category_filter=category_filter,
    )

    result["sessionContext"] = {
        **(result.get("sessionContext") or {}),
        "selectedTrack": selected_track,
    }

    answer = generate_course_answer(req.queryText, result)

    return {
        "answer": answer,
        "sources": result["courses"],
        "sessionContext": result["sessionContext"],
        "debug": {
            **result["debug"],
            "selectedTrack": selected_track,
            "categoryFilter": category_filter,
        },
    }

class RecommendCoursesRequest(BaseModel):
    userId: int
    limit: int = 10
    track: Literal["elective", "general"] = "elective"


@app.post("/recommendations/courses")
def recommend_courses_legacy(req: RecommendCoursesRequest):
    selected_track = normalize_track(req.track)
    category_filter = resolve_category_filter(selected_track)

    result = recommend_courses_core(
        user_id=req.userId,
        query_text=None,
        limit=req.limit,
        mode="profile_only",
        session_context=None,
        category_filter=category_filter,
    )

    result["sessionContext"] = {
        **(result.get("sessionContext") or {}),
        "selectedTrack": selected_track,
    }

    return {
        "ok": True,
        "userId": req.userId,
        "profileText": result["profileText"],
        "count": len(result["courses"]),
        "courses": result["courses"],
        "sessionContext": result["sessionContext"],
        "debug": {
            **result["debug"],
            "selectedTrack": selected_track,
            "categoryFilter": category_filter,
        },
    }

class CourseSummaryRequest(BaseModel):
    courseCode: str
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
                  c."descriptionEn",
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

    _, course_code, name_th, name_en, desc_th, desc_en, category, credits = course

    review_text_lines = []
    ratings = []

    if reviews:
        for rating, comment, is_anon, created_at in reviews:
            if rating is not None:
                ratings.append(rating)

            if comment and str(comment).strip():
                review_text_lines.append(f"- rating: {rating} | comment: {comment}")

    has_reviews = len(review_text_lines) > 0
    review_count = len(review_text_lines)
    avg_rating = round(sum(ratings) / len(ratings), 2) if len(ratings) > 0 else None
    rating_text = f"{avg_rating}/5" if avg_rating is not None else "ไม่มีข้อมูล"

    if has_reviews:
        review_text = "\n".join(review_text_lines)

        prompt = f"""
คุณคือผู้ช่วยสรุปรายวิชาสำหรับนักศึกษา (ภาษาไทย)
แนวทางการสรุป:
- ให้ใช้ข้อมูลรายวิชาและรีวิวเป็นฐานหลัก
- สามารถใช้ความรู้ทั่วไปของศาสตร์หรือสายวิชานั้นเพื่อช่วยอธิบายว่าเนื้อหาเหล่านี้มักเกี่ยวข้องกับอะไร และนักศึกษามักจะได้ทักษะแบบไหน
- ถ้าเป็นการอธิบายจากความรู้ทั่วไป ไม่ใช่ข้อมูลตรงจากรายวิชา ให้ใช้คำว่า "โดยทั่วไป", "มัก", "อาจ", "มีแนวโน้ม"
- อย่าคัดลอกคำอธิบายรายวิชามาเรียงใหม่เฉย ๆ แต่ให้ตีความและอธิบายให้นักศึกษาเข้าใจง่ายขึ้น
- ให้เน้นว่าวิชานี้น่าจะ useful อย่างไรกับการเรียนต่อหรือการทำงาน

ข้อสำคัญ:
- ห้ามคัดลอกหรือเรียบเรียงคำอธิบายรายวิชาแบบตรงตัวทั้งย่อหน้า
- ย่อหน้าแรกต้องเป็นการสรุปใหม่ด้วยภาษาที่เข้าใจง่าย เหมือนอธิบายให้นักศึกษาฟัง
- ถ้าจะอนุมานจากคำอธิบายวิชา ให้ใช้คำว่า "อาจ", "มีแนวโน้ม", "จากลักษณะของวิชา"
- ให้แยกให้ชัดว่าอะไรดูมาจากรีวิว และอะไรเป็นการตีความจากคำอธิบายรายวิชา
- ถ้าไม่มีข้อมูลชัดเจนในบางเรื่อง ให้บอกตรง ๆ ว่า "ยังไม่พบข้อมูลชัดเจน"

รายละเอียดรายวิชา:
- รหัส: {course_code}
- ชื่อไทย: {name_th}
- ชื่ออังกฤษ: {name_en}
- หมวด: {category}
- หน่วยกิต: {credits}
- คำอธิบาย: {desc_th}
- คำอธิบายอังกฤษ: {desc_en}

สถิติรีวิว:
- จำนวนรีวิวที่ใช้สรุป: {review_count}
- คะแนนเฉลี่ย: {rating_text}

รีวิวจากผู้เรียน:
{review_text}

ให้สรุปเป็นภาษาไทยแบบอ่านง่าย ครอบคลุมประเด็นต่อไปนี้:
1) วิชานี้เรียนเกี่ยวกับอะไร ลักษณะของวิชา เช่น เน้นทฤษฎี ปฏิบัติ การวิเคราะห์ หรือการเขียนโปรแกรมในภาพรวม 3-5 บรรทัด 
2) พื้นฐานที่ควรมีก่อนเรียน ถ้ามีแนวโน้มจากคำอธิบายหรือรีวิว
3) นักศึกษาน่าจะได้ทักษะหรือความรู้ด้านใดจากวิชานี้
4) จุดเด่นและข้อควรระวังที่เห็นจากรีวิว
5) เหมาะกับใคร
6) ปิดท้ายด้วยความเห็นสรุปสั้น ๆ ว่าถ้าสนใจสายนี้ วิชานี้น่าจะตอบโจทย์หรือไม่

รูปแบบการตอบ:
- ใช้ภาษาธรรมชาติ
- อ่านง่าย
- ยาวรวมประมาณ 6-8 บรรทัด ไม่ต้องยาวเกินไป
- ไม่ต้องใส่หัวข้อย่อยแบบตัวเลข
- ไม่ต้องใช้ markdown
- ไม่ต้องขึ้นต้นว่า "สรุป:"
""".strip()

        status = "OK"
        note = None

    else:
        prompt = f"""
คุณคือผู้ช่วยสรุปรายวิชาสำหรับนักศึกษา (ภาษาไทย)
แนวทางการสรุป:
- ให้ใช้ข้อมูลรายวิชาและรีวิวเป็นฐานหลัก
- สามารถใช้ความรู้ทั่วไปของศาสตร์หรือสายวิชานั้นเพื่อช่วยอธิบายว่าเนื้อหาเหล่านี้มักเกี่ยวข้องกับอะไร และนักศึกษามักจะได้ทักษะแบบไหน
- ถ้าเป็นการอธิบายจากความรู้ทั่วไป ไม่ใช่ข้อมูลตรงจากรายวิชา ให้ใช้คำว่า "โดยทั่วไป", "มัก", "อาจ", "มีแนวโน้ม"
- อย่าคัดลอกคำอธิบายรายวิชามาเรียงใหม่เฉย ๆ แต่ให้ตีความและอธิบายให้นักศึกษาเข้าใจง่ายขึ้น
- ให้เน้นว่าวิชานี้น่าจะ useful อย่างไรกับการเรียนต่อหรือการทำงาน

ข้อสำคัญ:
- ห้ามคัดลอกหรือเรียบเรียงคำอธิบายรายวิชาแบบตรงตัวทั้งย่อหน้า
- ย่อหน้าแรกต้องเป็นการสรุปใหม่ด้วยภาษาที่เข้าใจง่าย
- ถ้าจะอนุมานจากคำอธิบายวิชา ให้ใช้คำว่า "อาจ", "มีแนวโน้ม", "จากลักษณะของวิชา"
- ห้ามอ้างว่ามีรีวิว
- ถ้าไม่มีข้อมูลชัดเจนในบางเรื่อง ให้บอกตรง ๆ ว่า "ยังไม่พบข้อมูลชัดเจน"
- ห้ามเขียนยาวหรือเขียนซ้ำ

รายละเอียดรายวิชา:
- รหัส: {course_code}
- ชื่อไทย: {name_th}
- ชื่ออังกฤษ: {name_en}
- หมวด: {category}
- หน่วยกิต: {credits}
- คำอธิบาย: {desc_th}
- คำอธิบายอังกฤษ: {desc_en}

ให้สรุปแบบสั้น กระชับ และเหมาะสำหรับแสดงบนหน้าเว็บ โดยใช้รูปแบบนี้:
- บรรทัดแรก: บอกสั้น ๆ ว่าวิชานี้ยังไม่มีรีวิวจากนักศึกษา และข้อมูลต่อไปนี้สรุปจากคำอธิบายรายวิชาเป็นหลัก
- จากนั้นสรุป สั้น ๆ 5-6 บรรทัด ครอบคลุม:
  1) วิชาเรียนเกี่ยวกับอะไร
  2) พื้นฐานที่อาจควรมีก่อนเรียน
  3) ทักษะหรือความรู้ที่น่าจะได้จากวิชา
- ความยาวรวมไม่เกิน 5-6 บรรทัด
- ไม่ต้องใช้ markdown
- ไม่ต้องใช้ตัวหนา
- ไม่ต้องปิดท้ายซ้ำอีกว่ามาจากคำอธิบายรายวิชา
""".strip()

        status = "NO_REVIEWS"
        note = "วิชานี้ยังไม่มีรีวิวจากนักศึกษา สรุปนี้อ้างอิงจากคำอธิบายรายวิชาเป็นหลัก"

    resp = ollama.chat(
        model=OLLAMA_MODEL,
        messages=[
            {
                "role": "system",
                "content": "You summarize university courses for students in Thai. Use the provided course description and reviews as the main evidence. Write naturally and concisely for a web UI. Do not copy the description verbatim, do not start like a formal report, and do not invent unsupported specific facts."            },
            {"role": "user", "content": prompt},
        ],
    )

    summary = resp["message"]["content"].strip()

    return {
        "ok": True,
        "courseCode": req.courseCode,
        "status": status,
        "summary": summary,
        "note": note,
        "meta": {
            "reviewCount": review_count,
            "averageRating": avg_rating,
        },
    }


def search_courses_by_keyword(query_text: str, limit: int = 5) -> list[dict[str, Any]]:
    query_text = (query_text or "").strip()

    if not query_text:
        return []

    expanded = expand_query_with_ollama(
        query_text=query_text,
        analysis=None,
    )

    expanded_query = (expanded.get("expanded_query") or "").strip()
    skill_keywords = expanded.get("skill_keywords") or []
    negative_keywords = expanded.get("negative_keywords") or []

    # ใช้เฉพาะ query เดิม + expanded + skill สำหรับทำ embedding
    embedding_parts = [query_text]

    if expanded_query and expanded_query != query_text:
        embedding_parts.append(expanded_query)

    if skill_keywords:
        embedding_parts.append(" ".join(str(k).strip() for k in skill_keywords if str(k).strip()))

    embedding_text = " ".join(part.strip() for part in embedding_parts if part and part.strip())

    print("==== SEARCH QUERY ORIGINAL ====")
    print(query_text)
    print("==== SEARCH QUERY EXPANDED ====")
    print(expanded)
    print("==== SEARCH EMBEDDING TEXT ====")
    print(embedding_text)
    print("==== SEARCH NEGATIVE KEYWORDS ====")
    print(negative_keywords)

    conn = get_conn()
    cur = conn.cursor()

    try:
        qvec = embedder.encode(embedding_text).tolist()
        qvec_str = "[" + ", ".join(map(str, qvec)) + "]"

        # ดึงมาเผื่อกรองออกทีหลัง
        fetch_limit = 5
        cur.execute("""
            SELECT
                "courseCode",
                "courseNameTh",
                "courseNameEn",
                description,
                "descriptionEn",
                credits,
                category,
                "imageUrl",
                embedding <-> %s::vector AS distance
            FROM course
            WHERE embedding IS NOT NULL
            ORDER BY distance ASC
            LIMIT %s
        """, (qvec_str,fetch_limit))

        rows = cur.fetchall()

        results = []
        for r in rows:
            course = {
                "courseCode": r[0],
                "courseNameTh": r[1],
                "courseNameEn": r[2],
                "description": r[3],
                "descriptionEn": r[4],
                "credits": r[5],
                "category": r[6],
                "imageUrl": r[7],
                "distance": float(r[8]),
            }

            # รวมข้อความไว้เช็ก negative
            haystack = " ".join([
                str(course.get("courseCode") or ""),
                str(course.get("courseNameTh") or ""),
                str(course.get("courseNameEn") or ""),
                str(course.get("description") or ""),
                str(course.get("descriptionEn") or ""),
                str(course.get("category") or ""),
            ]).lower()

            blocked = False
            for keyword in negative_keywords:
                keyword_text = str(keyword).strip().lower()
                if keyword_text and keyword_text in haystack:
                    blocked = True
                    break

            if blocked:
                continue

            results.append(course)

            if len(results) >= limit:
                break

        return results

    finally:
        cur.close()
        conn.close()


@app.post("/test/search")
def test_search(req: dict):
    query = req.get("query", "")

    results = search_courses_by_keyword(query, limit=5)

    return {
        "query": query,
        "results": results
    }