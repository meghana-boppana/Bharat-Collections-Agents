
import os
import json
import csv
import io
import re
import sqlite3
import base64
import requests
import webbrowser
import threading
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_from_directory
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024

GNANI_API_KEY = os.getenv("GNANI_API_KEY", "").strip()
GNANI_STT_URL = "https://api.vachana.ai/stt/v3"
GNANI_TTS_URL = "https://api.vachana.ai/api/v1/tts/sse"
GNANI_CHAT_URL = "https://api.gnani.ai/chat"
gnani_connected = bool(GNANI_API_KEY)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
AUDIO_DIR = os.path.join(BASE_DIR, "static", "audio")
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(AUDIO_DIR, exist_ok=True)
DB_PATH = os.path.join(BASE_DIR, "customers.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute("""CREATE TABLE IF NOT EXISTS customers (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, phone TEXT, due TEXT, file_name TEXT, call_status TEXT DEFAULT 'Not Called', customer_reply TEXT DEFAULT '', last_reply TEXT DEFAULT '', last_reply_english TEXT DEFAULT '', created_at TEXT)""")
    conn.commit()
    conn.close()

init_db()

LANG_MAP = {"Telugu": "te", "Hindi": "hi", "English": "en", "Tamil": "ta", "Kannada": "kn", "Malayalam": "ml", "Marathi": "mr", "Bengali": "bn", "Gujarati": "gu", "Punjabi": "pa", "Odia": "or", "Assamese": "as", "Urdu": "ur"}

def detect_language(text):
    if not text:
        return "Telugu"
    t = text.lower()
    for ch in text:
        o = ord(ch)
        if 0x0C00 <= o <= 0x0C7F:
            return "Telugu"
        if 0x0900 <= o <= 0x097F:
            return "Hindi"
        if 0x0B80 <= o <= 0x0BFF:
            return "Tamil"
        if 0x0C80 <= o <= 0x0CFF:
            return "Kannada"
        if 0x0D00 <= o <= 0x0D7F:
            return "Malayalam"
        if 0x0A00 <= o <= 0x0A7F:
            return "Punjabi"
        if 0x0980 <= o <= 0x09FF:
            return "Bengali"
        if 0x0A80 <= o <= 0x0AFF:
            return "Gujarati"
        if 0x0B00 <= o <= 0x0B7F:
            return "Odia"
    if any(w in t for w in ["nanu", "nenu", "kadhathanu", "kathanu", "kattestha", "kattanu", "rapu", "repu", "aagu", "kavali", "ledhu", "enti", "asalu", "cheyyanu", "ivvanu"]):
        return "Telugu"
    if any(w in t for w in ["main", "kal", "karunga", "karenge", "ruko", "chahiye", "nahi", "karo", "dunga", "dena"]):
        return "Hindi"
    if any(w in t for w in ["naan", "naalaiku", "katturen", "konjam", "poru", "venum", "illa", "kattamaaten"]):
        return "Tamil"
    if any(w in t for w in ["naanu", "naale", "kattuttene", "swalpa", "beku", "illa"]):
        return "Kannada"
    if any(w in t for w in ["njan", "naale", "kattum", "koncham", "venam"]):
        return "Malayalam"
    if any(w in t for w in ["mi", "udya", "bharnar", "thamba", "pahije"]):
        return "Marathi"
    if any(w in t for w in ["ami", "kalke", "dibo", "ektu", "darao"]):
        return "Bengali"
    if any(w in t for w in ["i will", "i am", "will pay", "tomorrow", "tommarow", "please", "human", "wait", "will not"]):
        if re.search(r"\b(i will|i am|will pay|tomorrow|please|will not)\b", t):
            return "English"
    return "Telugu"

REPLIES = {
    "PAYMENT_PROMISE": {"Telugu": "Thank you, repu payment kosam wait chestham.", "Hindi": "Dhanyavaad, kal payment ke liye wait karenge. Confirm karne ke liye shukriya.", "English": "Thank you, we will wait for your payment tomorrow. Thanks for confirming.", "Tamil": "Nandri, naalaiku payment kaaga wait pannuvom. Confirm pannadhukku nandri.", "Kannada": "Dhanyavadagalu, naale payment koskara wait madthivi. Confirm madidhakke dhanyavadagalu.", "Malayalam": "Nanni, naale payment nu vendi wait cheyyum. Confirm cheythathinu nanni.", "Marathi": "Dhanyavad, udya payment sathi wait karu. Confirm kelyabaddal dhanyavad.", "Bengali": "Dhonnobad, kalke payment er jonno wait korbo. Confirm korar jonno dhonnobad.", "Gujarati": "Aabhar, kale payment mate wait karishu. Confirm karva badal aabhar.", "Punjabi": "Dhannvad, kal payment layi wait karange. Confirm karan layi dhannvad.", "Odia": "Dhanyabad, kali payment pain wait karibu. Confirm karibaru dhanyabad.", "Assamese": "Dhonnobad, kali payment or babe wait korim. Confirm kora babe dhonnobad.", "Urdu": "Shukriya, kal payment ke liye wait karenge. Confirm karne ke liye shukriya."},
    "HUMAN_REQUEST": {"Telugu": "Sure, human agent ni connect chestham. Konchem wait cheyyandi.", "Hindi": "Zaroor, human agent se connect karte hain. Thoda wait kijiye.", "English": "Sure, connecting you to a human agent. Please wait.", "Tamil": "Kandippa, human agent kitta connect pannurom. Konjam wait pannunga.", "Kannada": "Khanditha, human agent ge connect madthivi. Swalpa wait madi.", "Malayalam": "Urappu, human agent ne connect cheyyum. Koncham wait cheyyu.", "Marathi": "Nakki, human agent la connect karto. Thoda wait kara.", "Bengali": "Nishchoi, human agent er sathe connect korchi. Ektu wait korun.", "Gujarati": "Chokkas, human agent ne connect karu chhu. Thodu wait karo.", "Punjabi": "Pakka, human agent nal connect karde haan. Thoda wait karo.", "Odia": "Nischaya, human agent nku connect karibu. Tikie wait karantu.", "Assamese": "Nishchoy, human agent or logot connect korim. Olop wait korok.", "Urdu": "Zaroor, human agent se connect karte hain. Thoda wait kijiye."},
    "WAIT": {"Telugu": "Okay, konchem wait chestham. Meeku time istham.", "Hindi": "Okay, thoda wait karenge. Aapko time denge.", "English": "Okay, we will wait. Take your time.", "Tamil": "Okay, konjam wait pannuvom. Ungalukku time tharuvom.", "Kannada": "Okay, swalpa wait madthivi. Nimge time kodthivi.", "Malayalam": "Okay, koncham wait cheyyum. Ningalkku time tharum.", "Marathi": "Okay, thoda wait karu. Tumhala time deto.", "Bengali": "Okay, ektu wait korbo. Apnake time dibo.", "Gujarati": "Okay, thodu wait karishu. Tamne time aapishu.", "Punjabi": "Okay, thoda wait karange. Tuhnu time devange.", "Odia": "Okay, tikie wait karibu. Apananku samaya debu.", "Assamese": "Okay, olop wait korim. Apunak xomoy dim.", "Urdu": "Okay, thoda wait karenge. Aapko time denge."},
    "REFUSAL": {"Telugu": "Okay, ardham ayindhi. Mee situation ardham ayindhi. Kopam vadhu, human agent tho matladisthara? Mee problem vinataniki ready ga unnam.", "Hindi": "Okay, samajh gaya. Aapki situation samajh gaya. Gussa mat kijiye, human agent se baat karvau? Aapki problem sunne ke liye ready hain.", "English": "Okay, understood. I understand your situation. No pressure, shall I connect you to a human agent? We are ready to listen to your problem.", "Tamil": "Okay, purinjidhu. Unga situation purinjidhu. Kovam vendaam, human agent kitta pesalama?", "Kannada": "Okay, arthayithu. Nimma situation arthayithu. Koppa beda, human agent jothe mathadana?", "Malayalam": "Okay, manassilayi. Ningalude situation manassilayi. Deshyam venda, human agent ne connect cheyyatte?", "Marathi": "Okay, samajla. Tumchi situation samajli. Ragavu naka, human agent shi bolu ka?", "Bengali": "Okay, bujhlam. Apnar situation bujhlam. Rag korben na, human agent er sathe kotha bolben?", "Gujarati": "Okay, samjai gayu. Tamari situation samjai gai. Gusso na karo, human agent sathe vaat karavu?", "Punjabi": "Okay, samajh gaya. Tuhadi situation samajh gayi. Gussa na karo, human agent nal gal karvavan?", "Odia": "Okay, bujhi gali. Apanankara situation bujhi gali. Raga karantu nahin, human agent nka sahita katha hebe ki?", "Assamese": "Okay, buji paisu. Apunar situation buji paisu. Khong nohoribo, human agent or logot kotha patim ne?", "Urdu": "Okay, samajh gaya. Aapki situation samajh gaya. Gussa mat kijiye, human agent se baat karvau?"},
    "GENERAL": {"Telugu": "Thank you, mee reply note chesukunnam.", "Hindi": "Dhanyavaad, aapka reply note kar liya. Payment me help karenge.", "English": "Thank you, we noted your reply. We will help with payment.", "Tamil": "Nandri, unga reply note pannittom. Payment ku help pannuvom.", "Kannada": "Dhanyavadagalu, nimma reply note madidivi. Payment ge help madthivi.", "Malayalam": "Nanni, ningalude reply note cheythu. Payment nu help cheyyum.", "Marathi": "Dhanyavad, tumcha reply note kela. Payment la help karu.", "Bengali": "Dhonnobad, apnar reply note korlam. Payment e help korbo.", "Gujarati": "Aabhar, tamaro reply note karyo. Payment ma help karishu.", "Punjabi": "Dhannvad, tuhada reply note kar laya. Payment ch help karange.", "Odia": "Dhanyabad, apanankara reply note kali. Payment re help karibu.", "Assamese": "Dhonnobad, apunar reply note korilu. Payment ot help korim.", "Urdu": "Shukriya, aapka reply note kar liya. Payment me help karenge."},
}

def gnani_headers():
    return {"X-API-Key-ID": GNANI_API_KEY, "Content-Type": "application/json"}

def gnani_stt(audio_bytes, filename="voice.m4a"):
    try:
        if filename.endswith(".webm"):
            filename = "voice.m4a"
        files = {"audio_file": (filename, audio_bytes)}
        data = {"language_code": "te-IN", "preferred_language": "te-IN", "format": "transcribe"}
        headers = {"X-API-Key-ID": GNANI_API_KEY}
        r = requests.post(GNANI_STT_URL, headers=headers, files=files, data=data, timeout=60)
        if r.status_code == 504:
            return None, "Gnani Server Busy (504) - 20 Sec Aagi Malli Voice Try Cheyyi"
        if r.status_code == 429:
            return None, "Gnani Limit Ayipoyindhi (429) - 1 Min Aagi Malli Try Cheyyi"
        if r.status_code != 200:
            return None, f"Gnani STT Error: {r.status_code} - {r.text[:300]}"
        data_json = r.json()
        text = data_json.get("transcript") or data_json.get("transcription") or data_json.get("text") or data_json.get("result") or ""
        if not text and isinstance(data_json.get("data"), dict):
            d = data_json["data"]
            text = d.get("transcript") or d.get("transcription") or d.get("text") or ""
            if not text and isinstance(d.get("transcripts"), list) and d["transcripts"]:
                first = d["transcripts"][0]
                text = first.get("transcript", "") if isinstance(first, dict) else str(first)
            if not text and isinstance(d.get("segments"), list) and d["segments"]:
                text = " ".join([s.get("text", "") if isinstance(s, dict) else str(s) for s in d["segments"]])
        if not text and isinstance(data_json.get("segments"), list) and data_json["segments"]:
            text = " ".join([s.get("text", "") if isinstance(s, dict) else str(s) for s in data_json["segments"]])
        if not text:
            return None, "Gnani STT - Text Raledhu - Konchem Peddaga, 2-3 Sec Matladu"
        return text, None
    except Exception as e:
        return None, str(e)

def simple_reply(text):
    t = text.lower().strip()
    lang = detect_language(text)
    is_refusal = any(w in t for w in ["asalu", "kathanu", "kattanu", "cheyyanu", "ivvanu", "ivvalenu", "kudharadhu", "kudaradhu", "ledhu", "never", "won't", "will not", "cannot", "can't", "nahi", "no pay", "not pay", "asalu kattanu", "asalu kathanu", "pay cheyyanu", "dena nahi", "kattamaaten", "dunga nahi"])
    if is_refusal:
        intent = "REFUSAL"
        reply = REPLIES["REFUSAL"].get(lang, REPLIES["REFUSAL"]["Telugu"])
        return {"reply": reply, "lang": lang, "english": text, "intent": intent}, None
    has_pay = any(w in t for w in ["pay", "kattestha", "kadhathanu", "katturen", "kattuttene", "kattum", "bharnar", "dibo", "pay kar", "chestha"])
    has_tomorrow = any(w in t for w in ["tomorrow", "tommarow", "tomorow", "tomarrow", "tommorrow", "tommorow", "rep", "rapu", "repu", "kal", "tom", "naalaiku", "naale", "udya", "kalke", "kale"])
    if has_pay or has_tomorrow or "will pay" in t:
        intent = "PAYMENT_PROMISE"
    elif any(w in t for w in ["human", "manishi", "agent", "kavali", "chahiye", "venum", "beku", "pahije"]):
        intent = "HUMAN_REQUEST"
    elif any(w in t for w in ["wait", "aagu", "aagandi", "time", "ruko", "poru", "swalpa", "thamba", "darao"]):
        intent = "WAIT"
    else:
        intent = "GENERAL"
    reply = REPLIES[intent].get(lang, REPLIES[intent]["Telugu"])
    return {"reply": reply, "lang": lang, "english": text, "intent": intent}, None

def gnani_chat(text, customer="Test User"):
    detected_lang = detect_language(text)
    try:
        payload = {"model": "evon-30b", "customer": customer, "text": text, "language": detected_lang, "lang": detected_lang, "messages": [{"role": "user", "content": f"Reply in {detected_lang} language only. User said: {text}"}]}
        r = requests.post(GNANI_CHAT_URL, headers=gnani_headers(), json=payload, timeout=60)
        if r.status_code != 200:
            return simple_reply(text)
        data = r.json()
        reply = data.get("reply") or data.get("response") or data.get("text") or ""
        if not reply:
            return simple_reply(text)
        intent_raw = (data.get("intent") or "").upper()
        if intent_raw in REPLIES:
            gnani_lang = data.get("lang") or data.get("language") or ""
            if gnani_lang and gnani_lang.lower() != detected_lang.lower() and gnani_lang.lower() not in detected_lang.lower():
                reply = REPLIES[intent_raw].get(detected_lang, reply)
            return {"reply": reply, "lang": detected_lang, "english": text, "intent": intent_raw}, None
        return {"reply": reply, "lang": detected_lang, "english": text, "intent": "GENERAL"}, None
    except Exception:
        return simple_reply(text)

def gnani_tts(text, lang="Telugu"):
    try:
        lang_map_tts = {"Telugu": "te-IN", "Hindi": "hi-IN", "English": "en-IN", "Tamil": "ta-IN", "Kannada": "kn-IN", "Malayalam": "ml-IN", "Marathi": "mr-IN", "Bengali": "bn-IN", "Gujarati": "gu-IN", "Punjabi": "pa-IN", "Odia": "or-IN", "Assamese": "as-IN", "Urdu": "ur-IN"}
        lang_code = lang_map_tts.get(lang, "te-IN")
        payload = {"text": text, "language_code": lang_code, "voice": "vachana-voice-v3", "model": "timbre-v2.5"}
        headers = {"X-API-Key-ID": GNANI_API_KEY, "Content-Type": "application/json"}
        r = requests.post(GNANI_TTS_URL, headers=headers, json=payload, timeout=60, stream=True)
        if r.status_code != 200:
            return None
        ctype = r.headers.get("Content-Type", "")
        if "audio" in ctype:
            fname = f"reply_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp3"
            path = os.path.join(AUDIO_DIR, fname)
            with open(path, "wb") as f:
                f.write(r.content)
            return f"/static/audio/{fname}"
        raw = r.text if hasattr(r, "text") else ""
        audio_bytes = b""
        for line in raw.splitlines():
            line = line.strip()
            if line.startswith("data:"):
                payload_str = line[5:].strip()
                if payload_str in ("[DONE]", ""):
                    continue
                try:
                    j = json.loads(payload_str)
                    b64 = j.get("audio") or j.get("audio_base64") or j.get("data") or j.get("chunk") or ""
                    if b64 and isinstance(b64, str):
                        try:
                            audio_bytes += base64.b64decode(b64)
                        except Exception:
                            pass
                    url = j.get("audio_url") or j.get("url")
                    if url:
                        return url
                except Exception:
                    continue
        if audio_bytes:
            fname = f"reply_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp3"
            path = os.path.join(AUDIO_DIR, fname)
            with open(path, "wb") as f:
                f.write(audio_bytes)
            return f"/static/audio/{fname}"
        try:
            data = json.loads(raw) if raw else {}
            audio_url = data.get("audio_url") or data.get("url") or data.get("audioUrl")
            if audio_url:
                return audio_url
        except Exception:
            pass
        return None
    except Exception:
        return None

def clean_phone(raw):
    if not raw:
        return ""
    digits = re.sub(r"[^0-9]", "", str(raw))
    if len(digits) > 10 and digits.startswith("91"):
        digits = digits[-10:]
    return digits

def clean_name(raw):
    if not raw:
        return "Unknown"
    name = str(raw).strip()
    name = re.sub(r"[^A-Za-z ]", "", name).strip()
    if not name or name.lower() in ("phone number", "phone", "name", "due", "amount", "unknown"):
        return "Unknown"
    return name

def clean_due(raw):
    if raw is None:
        return ""
    return re.sub(r"[^0-9.]", "", str(raw))

def parse_single_line(line):
    line = line.strip()
    if not line:
        return None
    low = line.lower()
    if "phone number" in low and "due" not in low and "name" not in low:
        return None
    if low in ("name", "phone", "due", "phone number", "name,phone,due"):
        return None
    if low.startswith("name") or low.startswith("phone") or low.startswith("due"):
        return None
    m = re.search(r"(\+?91[\s\-]?)?([6-9]\d{4}[\s\-]?\d{5})", line)
    if not m:
        return None
    phone = clean_phone(m.group(0))
    before = line[:m.start()].strip(" ,|:-")
    after = line[m.end():].strip(" ,|:-Rs.₹")
    after = clean_due(after)
    name = clean_name(before.split(",")[0] if before else "Unknown")
    return (name, phone, after)

def parse_text_blocks(full_text):
    customers = []
    cur_name = ""
    cur_phone = ""
    cur_due = ""

    def save_block():
        nonlocal cur_name, cur_phone, cur_due
        if cur_phone:
            customers.append((clean_name(cur_name), clean_phone(cur_phone), clean_due(cur_due)))
        cur_name = ""
        cur_phone = ""
        cur_due = ""

    for raw in full_text.splitlines():
        line = raw.strip()
        if not line:
            continue
        low = line.lower()
        if low in ("name", "phone", "phone number", "due", "amount", "name,phone,due", "name phone due"):
            continue
        if low.startswith("name") and ":" in line:
            if cur_phone:
                save_block()
            cur_name = line.split(":", 1)[-1].strip()
            continue
        if low.startswith("name") and " " in line and len(line) > 5 and not re.search(r"\d", line):
            if cur_phone:
                save_block()
            cur_name = line.replace("Name", "").replace("name", "").strip(" :")
            continue
        if "phone" in low:
            m = re.search(r"([6-9]\d{9})", line.replace(" ", "").replace("-", ""))
            if m:
                cur_phone = m.group(1)
            continue
        if low.startswith("due") or low.startswith("amount") or low.startswith("balance") or low.startswith("pending"):
            m = re.search(r"([0-9,]+)", line)
            if m:
                cur_due = m.group(1).replace(",", "")
            if cur_phone:
                save_block()
            continue
        r = parse_single_line(line)
        if r:
            if cur_phone:
                save_block()
            customers.append(r)
            continue
        if re.fullmatch(r"[\+0-9\s\-]+", line) and len(re.sub(r"[^0-9]", "", line)) == 10:
            if cur_phone:
                save_block()
            cur_phone = re.sub(r"[^0-9]", "", line)
            continue
        if cur_phone and re.fullmatch(r"[₹Rs.\s]*[0-9,]+", line):
            cur_due = clean_due(line)
            save_block()
            continue
    save_block()
    return customers

def parse_file_content(filename, content_bytes):
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    customers = []
    try:
        if ext == "csv":
            text = content_bytes.decode("utf-8-sig", errors="ignore").strip()
            lines = [l for l in text.splitlines() if l.strip()]
            if not lines:
                return customers
            try:
                if "name" in lines[0].lower() or "phone" in lines[0].lower():
                    reader = csv.DictReader(io.StringIO("\n".join(lines)))
                    for row in reader:
                        if not row:
                            continue
                        row2 = {str(k).strip().lower(): v for k, v in row.items() if k}
                        name = row2.get("name") or row2.get("customer") or ""
                        phone = row2.get("phone") or row2.get("mobile") or row2.get("phone number") or ""
                        due = row2.get("due") or row2.get("amount") or row2.get("balance") or ""
                        if clean_phone(phone):
                            customers.append((clean_name(name), clean_phone(phone), clean_due(due)))
                    if customers:
                        return customers
            except Exception:
                pass
            return parse_text_blocks(text)
        elif ext == "json":
            data = json.loads(content_bytes.decode("utf-8", errors="ignore"))
            items = data if isinstance(data, list) else data.get("customers", [])
            for row in items:
                if isinstance(row, dict):
                    name = row.get("name") or row.get("customer") or ""
                    phone = row.get("phone") or row.get("mobile") or row.get("phone_number") or ""
                    due = row.get("due") or row.get("amount") or ""
                    if clean_phone(phone):
                        customers.append((clean_name(name), clean_phone(phone), clean_due(due)))
            return customers
        elif ext == "txt":
            return parse_text_blocks(content_bytes.decode("utf-8", errors="ignore"))
        elif ext == "pdf":
            try:
                import fitz
                doc = fitz.open(stream=content_bytes, filetype="pdf")
                full = ""
                for page in doc:
                    full += page.get_text() + "\n"
                return parse_text_blocks(full)
            except Exception as e:
                print("PDF Parse Error:", e)
        elif ext in ("docx", "doc"):
            try:
                import docx
                d = docx.Document(io.BytesIO(content_bytes))
                full_lines = []
                for para in d.paragraphs:
                    full_lines.append(para.text)
                for table in d.tables:
                    for row in table.rows:
                        cells = [c.text.strip() for c in row.cells]
                        full_lines.append(" ".join(cells))
                return parse_text_blocks("\n".join(full_lines))
            except Exception as e:
                print("DOCX Parse Error:", e)
        elif ext in ("xls", "xlsx"):
            try:
                import openpyxl
                wb = openpyxl.load_workbook(io.BytesIO(content_bytes), data_only=True)
                all_lines = []
                for ws in wb.worksheets:
                    for row in ws.iter_rows(values_only=True):
                        if not row or all(v is None for v in row):
                            continue
                        vals = [str(v).strip() for v in row if v is not None]
                        joined = " ".join(vals)
                        if "name" in joined.lower() and "phone" in joined.lower():
                            continue
                        all_lines.append(joined)
                return parse_text_blocks("\n".join(all_lines))
            except Exception as e:
                print("Excel Parse Error:", e)
        else:
            try:
                return parse_text_blocks(content_bytes.decode("utf-8", errors="ignore"))
            except Exception:
                pass
    except Exception as e:
        print("Parse Error:", e)
    return customers

@app.route("/")
def index():
    if not gnani_connected:
        return render_template("index.html", gnani_connected=False, files=[], customers=[])
    conn = get_db()
    customers = conn.execute("SELECT * FROM customers ORDER BY id DESC").fetchall()
    conn.close()
    seen = {}
    for c in customers:
        fn = c["file_name"] or "Unknown"
        seen[fn] = seen.get(fn, 0) + 1
    files = [{"file_name": fn, "cnt": cnt} for fn, cnt in seen.items()]
    cust_list = []
    for c in customers:
        cust_list.append({"id": c["id"], "name": c["name"], "phone": c["phone"], "due": c["due"], "call_status": c["call_status"], "customer_reply": c["customer_reply"], "last_reply": c["last_reply"], "last_reply_english": c["last_reply_english"], "file_name": c["file_name"]})
    return render_template("index.html", gnani_connected=True, files=files, customers=cust_list)

@app.route("/upload", methods=["POST"])
def upload():
    if not gnani_connected:
        return jsonify({"error": "Gnani API Key Required - .env Lo GNANI_API_KEY Petti Restart Cheyyi"}), 401
    if "files" not in request.files:
        return jsonify({"error": "Files levu"}), 400
    files = request.files.getlist("files")
    total = 0
    per_file = []
    conn = get_db()
    for f in files:
        if not f.filename:
            continue
        content = f.read()
        parsed = parse_file_content(f.filename, content)
        for name, phone, due in parsed:
            conn.execute("INSERT INTO customers (name, phone, due, file_name, call_status, created_at) VALUES (?, ?, ?, ?, ?, ?)", (name, phone, due, f.filename, "Not Called", datetime.now().strftime("%Y-%m-%d %H:%M")))
            total += 1
        per_file.append(f"{f.filename} - {len(parsed)}")
    conn.commit()
    conn.close()
    return jsonify({"message": f"{total} Customers Upload Ayayi - Gnani Ready! | " + " | ".join(per_file)})

@app.route("/call_file", methods=["POST"])
def call_file():
    if not gnani_connected:
        return jsonify({"error": "Gnani API Key Required"}), 401
    data = request.get_json() or {}
    fname = data.get("file_name")
    if not fname:
        return jsonify({"error": "File name ledhu"}), 400
    hour = datetime.now().hour
    if hour >= 21 or hour < 8:
        return jsonify({"error": "Night Block - Calling 8 AM - 9 PM Matrame - TRAI Rule"}), 403
    conn = get_db()
    conn.execute("UPDATE customers SET call_status='Called' WHERE file_name=?", (fname,))
    conn.commit()
    cnt = conn.execute("SELECT COUNT(*) FROM customers WHERE file_name=?", (fname,)).fetchone()[0]
    conn.close()
    return jsonify({"message": f"{fname} - {cnt} Calls Gnani Ki Pampincham!"})

@app.route("/chat", methods=["POST"])
def chat():
    if not gnani_connected:
        return jsonify({"error": "Gnani API Key Required"}), 401
    data = request.get_json() or {}
    text = data.get("text", "").strip()
    customer = data.get("customer", "Test User")
    if not text:
        return jsonify({"error": "Text ledhu"}), 400
    result, err = gnani_chat(text, customer)
    if err:
        return jsonify({"error": err}), 500
    audio_url = gnani_tts(result["reply"], result["lang"])
    return jsonify({"lang": result["lang"], "english": result["english"], "intent": result["intent"], "reply": result["reply"], "audio_url": audio_url})

@app.route("/gnani_voice", methods=["POST"])
def gnani_voice():
    if not gnani_connected:
        return jsonify({"error": "Gnani API Key Required"}), 401
    if "audio" not in request.files:
        return jsonify({"error": "Audio ledhu"}), 400
    audio_file = request.files["audio"]
    audio_bytes = audio_file.read()
    customer = request.form.get("customer", "Test User")
    fname = audio_file.filename or "voice.m4a"
    if fname.endswith(".webm"):
        fname = "voice.m4a"
    text, err = gnani_stt(audio_bytes, fname)
    if err or not text:
        return jsonify({"error": err or 'Text raaledhu'}), 500
    result, err2 = gnani_chat(text, customer)
    if err2:
        return jsonify({"error": err2}), 500
    audio_url = gnani_tts(result["reply"], result["lang"])
    return jsonify({"text": text, "english": result["english"], "lang": result["lang"], "intent": result["intent"], "reply": result["reply"], "audio_url": audio_url})

@app.route("/delete_file", methods=["POST"])
def delete_file():
    data = request.get_json() or {}
    fname = data.get("file_name")
    conn = get_db()
    conn.execute("DELETE FROM customers WHERE file_name=?", (fname,))
    conn.commit()
    conn.close()
    return jsonify({"message": "File Delete Ayindhi"})

@app.route("/delete_customer", methods=["POST"])
def delete_customer():
    data = request.get_json() or {}
    conn = get_db()
    conn.execute("DELETE FROM customers WHERE id=?", (data.get("id"),))
    conn.commit()
    conn.close()
    return jsonify({"message": "Deleted"})

@app.route("/delete_customers", methods=["POST"])
def delete_customers():
    data = request.get_json() or {}
    ids = data.get("ids", [])
    conn = get_db()
    for i in ids:
        conn.execute("DELETE FROM customers WHERE id=?", (i,))
    conn.commit()
    conn.close()
    return jsonify({"message": "Deleted"})

@app.route("/static/audio/<path:filename>")
def serve_audio(filename):
    return send_from_directory(AUDIO_DIR, filename)

if __name__ == "__main__":
    if not gnani_connected:
        print("WARNING: GNANI_API_KEY Lekhu - .env Lo Key Petti Restart Cheyyi")
    else:
        print("Gnani API Connected - Server Running")
    port = int(os.environ.get("PORT", 5000))
    if os.environ.get("RENDER") != "true":
        threading.Timer(1.0, lambda: webbrowser.open("http://127.0.0.1:5000")).start()
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)