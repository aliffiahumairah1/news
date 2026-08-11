import os
import pandas as pd
from dotenv import load_dotenv
from supabase import create_client, Client
from bertopic import BERTopic
from sentence_transformers import SentenceTransformer
from sklearn.feature_extraction.text import CountVectorizer

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("SUPABASE_URL dan SUPABASE_KEY harus diisi di file .env")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Stopwords Jurnalistik Ketat
INDONESIAN_STOPWORDS = [
    "yang", "di", "dan", "dengan", "untuk", "dari", "ke", "dalam", "pada", "adalah",
    "sebagai", "akan", "ini", "itu", "juga", "atau", "oleh", "serta", "karena", "maka",
    "bisa", "ada", "tidak", "saat", "telah", "dapat", "lebih", "ia", "mereka", "kita",
    "jakarta", "dikutip", "ujar", "menteri", "kata", "terkait", "katanya", "ungkap",
    "senin", "selasa", "rabu", "kamis", "jumat", "sabtu", "minggu", "berita",
    "indonesia", "presiden", "pemerintah", "resmi", "baca", "foto", "video", "halaman",
    "kumparan", "antara", "liputan6", "detik", "kompas", "tempo", "viva"
]

def run_topic_modeling():
    print("MEMULAI PEMODELAN TOPIK")
    
    # Bersihkan topik lama
    try:
        supabase.table("news").update({"topic_id": None}).gt("id", -1).execute()
        supabase.table("recommendations").delete().gt("id", -1).execute()
        supabase.table("topics").delete().gt("id", -1).execute()
    except Exception as e:
        print(f"Catatan pembersihan: {e}")

    news_res = supabase.table("news").select("id, title, clean_title").execute()
    news_data = news_res.data if hasattr(news_res, 'data') else news_res
    
    docs = [item["clean_title"] if item.get("clean_title") else item["title"] for item in news_data]
    news_ids = [item["id"] for item in news_data]
    
    print(f"Memproses {len(docs)} artikel berita...")
    
    embedding_model = SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
    
    # Gunakan min_df=3 untuk membuang kata-kata langka yang menurunkan coherence
    vectorizer_model = CountVectorizer(stop_words=INDONESIAN_STOPWORDS, min_df=3)
    
    # BERTopic dengan pengelompokan rapat
    topic_model = BERTopic(
        embedding_model=embedding_model,
        vectorizer_model=vectorizer_model,
        min_topic_size=5, # Mengelompokkan berita ke kluster yang lebih padat
        calculate_probabilities=False,
        verbose=False
    )
    
    topics, _ = topic_model.fit_transform(docs)
    topic_info = topic_model.get_topic_info()
    
    print(f"BERTopic berhasil membentuk {len(topic_info) - 1} kluster topik padat.")
    
    topic_db_mapping = {}
    
    for idx, row in topic_info.iterrows():
        topic_num = row["Topic"]
        if topic_num == -1:
            continue
            
        # Ambil 5 kata kunci teratas yang paling dominan
        keywords_list = [word for word, _ in topic_model.get_topic(topic_num)[:5]]
        keywords_str = ", ".join(keywords_list)
        
        topic_name = f"Topik {topic_num + 1}: " + " & ".join(keywords_list[:3]).title()
        ai_summary = f"Kluster berita seputar isu {keywords_str}."
        
        topic_payload = {
            "name": topic_name,
            "keywords": keywords_str,
            "ai_summary": ai_summary,
            "trend_score": float(row["Count"]) * 1.5
        }
        
        inserted_topic = supabase.table("topics").insert(topic_payload).execute()
        topic_res_data = inserted_topic.data if hasattr(inserted_topic, 'data') else inserted_topic
        
        if topic_res_data:
            db_topic_id = topic_res_data[0]["id"]
            topic_db_mapping[topic_num] = db_topic_id

    print("Memperbarui referensi topik pada berita...")
    for news_id, assigned_topic in zip(news_ids, topics):
        if assigned_topic in topic_db_mapping:
            db_topic_id = topic_db_mapping[assigned_topic]
            supabase.table("news").update({"topic_id": db_topic_id}).eq("id", news_id).execute()

    print("PEMODELAN TOPIK SELESAI")

if __name__ == "__main__":
    run_topic_modeling()