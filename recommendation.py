import os
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("SUPABASE_URL dan SUPABASE_KEY harus diisi di file .env")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def generate_recommendations():
    print("MEMULAI GENERASI REKOMENDASI REDAKSI")
    
    # Bersihkan rekomendasi lama agar data selalu fresh & tidak konflik ID
    try:
        supabase.table("recommendations").delete().gt("id", 0).execute()
    except Exception as e:
        print(f"Catatan pembersihan rekomendasi: {e}")

    # Ambil daftar topik
    topics_res = supabase.table("topics").select("*").execute()
    topics = topics_res.data
    
    if not topics:
        print("Tidak ada data topik ditemukan. Jalankan topic.py terlebih dahulu.")
        return

    print(f"Mengevaluasi {len(topics)} topik untuk membuat rekomendasi redaksi...")
    
    recommendations_payload = []
    
    for topic in topics:
        topic_id = topic["id"]
        topic_name = topic["name"]
        keywords = topic.get("keywords", "")
        trend_score = topic.get("trend_score", 0.0)
        
        # Hitung jumlah berita per topik
        news_in_topic = supabase.table("news").select("id").eq("topic_id", topic_id).execute().data
        news_count = len(news_in_topic) if news_in_topic else 0
        
        if news_count == 0:
            continue
            
        # Kalkulasi Recommendation Score sederhana (skala 0 - 100)
        rec_score = min(round((trend_score * 1.8) + (news_count * 2.5), 1), 98.5)
        
        # Buat narasi alasan rekomendasi
        reason = (
            f"Topik '{topic_name}' sedang hangat dibahas dengan total {news_count} artikel berita terkait. "
            f"Kata kunci utama meliputi: {keywords}."
        )
        
        recommendations_payload.append({
            "topic_id": topic_id,
            "recommendation_score": rec_score,
            "reason": reason,
            "status": "pending"
        })

    # Simpan rekomendasi baru ke Supabase
    if recommendations_payload:
        supabase.table("recommendations").insert(recommendations_payload).execute()
        print(f"Berhasil menyimpan {len(recommendations_payload)} rekomendasi topik baru ke Supabase.")
    else:
        print("Tidak ada rekomendasi baru yang dihasilkan.")

    print("GENERASI REKOMENDASI SELESAI")

if __name__ == "__main__":
    generate_recommendations()