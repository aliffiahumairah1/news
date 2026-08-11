import os
import torch
from dotenv import load_dotenv
from supabase import create_client, Client
from transformers import AutoTokenizer, AutoModelForSequenceClassification

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("SUPABASE_URL dan SUPABASE_KEY harus diisi di file .env")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Menggunakan model Hugging Face milik Aliffia
MODEL_NAME = "aliffiaaliffia/indobert_sentiment_news"

print(f"Memuat Model IndoBERT buatan Aliffia: ({MODEL_NAME})...")
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
model = AutoModelForSequenceClassification.from_pretrained(MODEL_NAME)
model.eval()

# Cek pemetaan label langsung dari config model Hugging Face kamu
id2label = model.config.id2label

def get_clean_label(pred_id: int) -> str:
    raw_label = str(id2label.get(pred_id, "netral")).lower().strip()
    
    # Normalisasi nama label
    if "pos" in raw_label or "1" in raw_label:
        return "positif"
    elif "neg" in raw_label or "0" in raw_label:
        return "negatif"
    else:
        return "netral"

def analyze_sentiment(text: str):
    if not text:
        return "netral", 0.5
    
    inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=128, padding=True)
    with torch.no_grad():
        outputs = model(**inputs)
        probs = torch.nn.functional.softmax(outputs.logits, dim=-1)
        confidence, predicted_class = torch.max(probs, dim=-1)
        
    pred_id = predicted_class.item()
    label = get_clean_label(pred_id)
    return label, float(confidence.item())

def run_sentiment_pipeline():
    print("MEMULAI ANALISIS SENTIMEN (INDOBERT CUSTOM)")
    
    # 1. Ambil ID berita yang sudah memiliki sentimen agar tidak dianalisis ulang
    existing_sentiments = supabase.table("sentiments").select("news_id").execute()
    processed_news_ids = {item["news_id"] for item in existing_sentiments.data}
    
    # 2. Ambil berita dari tabel news
    all_news = supabase.table("news").select("id, title, content").execute().data
    
    unprocessed_news = [n for n in all_news if n["id"] not in processed_news_ids]
    print(f"Ditemukan {len(unprocessed_news)} berita baru untuk dianalisis sentimennya.")
    
    if not unprocessed_news:
        print("Semua berita sudah memiliki data sentimen.")
        return

    sentiments_payload = []
    
    for idx, item in enumerate(unprocessed_news, start=1):
        news_id = item["id"]
        text_to_analyze = item["title"]
        if item.get("content"):
            text_to_analyze += " " + item["content"][:200]
            
        sentiment, confidence = analyze_sentiment(text_to_analyze)
        
        sentiments_payload.append({
            "news_id": news_id,
            "sentiment": sentiment,
            "confidence": round(confidence, 4)
        })
        
        # Simpan batch per 50 item ke Supabase
        if len(sentiments_payload) >= 50 or idx == len(unprocessed_news):
            supabase.table("sentiments").insert(sentiments_payload).execute()
            print(f"-> Berhasil menyimpan batch {len(sentiments_payload)} data sentimen.")
            sentiments_payload = []

    print("ANALISIS SENTIMEN SELESAI")

if __name__ == "__main__":
    run_sentiment_pipeline()