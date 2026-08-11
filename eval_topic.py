import os
from dotenv import load_dotenv
from supabase import create_client
from gensim.corpora import Dictionary
from gensim.models.coherencemodel import CoherenceModel

def main():
    load_dotenv()
    supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

    news_res = supabase.table("news").select("title, clean_title").execute()
    docs_data = news_res.data if hasattr(news_res, 'data') else news_res
    docs = [item["clean_title"] if item.get("clean_title") else item["title"] for item in docs_data]

    tokenized_docs = [doc.lower().split() for doc in docs]
    dictionary = Dictionary(tokenized_docs)

    topics_res = supabase.table("topics").select("keywords").execute()
    data_topics = topics_res.data if hasattr(topics_res, 'data') else topics_res
    
    # Mengambil maksimal 5 kata kunci teratas per topik untuk evaluasi presisi
    topic_words = [item["keywords"].split(", ")[:5] for item in data_topics if isinstance(item, dict) and item.get("keywords")]

    if topic_words:
        print("Menghitung Coherence Score (C_v)... Mohon tunggu sebentar.")
        cm = CoherenceModel(
            topics=topic_words, 
            texts=tokenized_docs, 
            dictionary=dictionary, 
            coherence='c_v',
            processes=1
        )
        coherence_score = cm.get_coherence()
        
        print(f"📊 TOPIC COHERENCE SCORE (C_v): {coherence_score:.4f}")
        
        if coherence_score >= 0.5:
            print("✅ KESIMPULAN: Model BERTopic kamu SUDAH BAGUS dan konsisten!")
        else:
            print("⚠️ KESIMPULAN: Topik masih agak campur aduk, perlu penyesuaian stopwords.")

if __name__ == '__main__':
    main()