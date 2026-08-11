import hashlib
import re
import os
from datetime import datetime
import feedparser
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from supabase import create_client, Client

# Load variabel dari file .env
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("SUPABASE_URL dan SUPABASE_KEY harus diisi di file .env")

# Inisialisasi client Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def clean_html(text: str) -> str:
    """Menghapus tag HTML dari teks ringkasan/konten berita."""
    if not text:
        return ""
    soup = BeautifulSoup(text, "html.parser")
    return soup.get_text(separator=" ", strip=True)

def generate_title_hash(title: str) -> str:
    """Membuat hash SHA256 dari judul yang sudah dibersihkan untuk deduplikasi exact-match."""
    cleaned = re.sub(r'[^\w\s]', '', title.lower()).strip()
    return hashlib.sha256(cleaned.encode('utf-8')).hexdigest()

def preprocess_text(text: str) -> str:
    """Preprocessing dasar: lowercasing, hapus tanda baca & karakter khusus."""
    if not text:
        return ""
    text = text.lower()
    text = re.sub(r'https?://\S+|www\.\S+', '', text)  # Hapus URL
    text = re.sub(r'[^\w\s]', '', text)               # Hapus tanda baca
    text = re.sub(r'\s+', ' ', text).strip()          # Hapus spasi berlebih
    return text

def run_crawler():
    print("MEMULAI PROSES CRAWLING BERITA")
    
    # Ambil sumber berita yang aktif dari Supabase
    response = supabase.table("sources").select("*").eq("is_active", True).execute()
    sources = response.data
    
    print(f"Berhasil mengambil {len(sources)} sumber berita aktif.\n")
    
    total_inserted = 0
    total_skipped = 0
    
    for source in sources:
        source_id = source["id"]
        source_name = source["name"]
        rss_url = source["rss_url"]
        
        print(f"Fetching RSS: {source_name} ({rss_url})...")
        try:
            feed = feedparser.parse(rss_url)
            print(f"-> Ditemukan {len(feed.entries)} artikel.")
            
            for entry in feed.entries:
                title = entry.get("title", "").strip()
                link = entry.get("link", "").strip()
                
                if not title or not link:
                    continue
                
                # Ambil ringkasan/konten
                raw_content = entry.get("summary", entry.get("description", ""))
                clean_content = clean_html(raw_content)
                
                # Ambil tanggal terbit
                published_parsed = entry.get("published_parsed", entry.get("updated_parsed"))
                if published_parsed:
                    published_at = datetime(*published_parsed[:6]).isoformat()
                else:
                    published_at = datetime.utcnow().isoformat()
                
                # Generate hash untuk deduplikasi
                title_hash = generate_title_hash(title)
                clean_title_text = preprocess_text(title)
                
                # Cek apakah berita sudah ada di database (Cek URL & Title Hash)
                check_existing = supabase.table("news").select("id").or_(f"url.eq.{link},title_hash.eq.{title_hash}").execute()
                
                if check_existing.data:
                    total_skipped += 1
                    continue
                
                # Simpan berita baru ke Supabase
                news_payload = {
                    "source_id": source_id,
                    "title": title,
                    "clean_title": clean_title_text,
                    "content": clean_content,
                    "url": link,
                    "title_hash": title_hash,
                    "published_at": published_at
                }
                
                supabase.table("news").insert(news_payload).execute()
                total_inserted += 1
                
        except Exception as e:
            print(f" Error saat crawling {source_name}: {e}")
            continue

    print("\nRINGKASAN CRAWLING")
    print(f" Berita Baru Disimpan: {total_inserted}")
    print(f" Berita Duplikat Dilewati: {total_skipped}")

if __name__ == "__main__":
    run_crawler()