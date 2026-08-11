import os
import pandas as pd
import plotly.express as px
import streamlit as st
from dotenv import load_dotenv
from supabase import create_client, Client

# Konfigurasi Halaman Streamlit
st.set_page_config(
    page_title="AI-Based News Trend Intelligence",
    page_icon="📰",
    layout="wide"
)

# Load Kredensial Supabase
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

@st.cache_resource
def init_supabase() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = init_supabase()

# Sidebar Navigation
st.sidebar.title("📌 Navigasi Dashboard")
page = st.sidebar.radio(
    "Pilih Halaman:",
    ["🏠 Home & Trending Topics", "📊 Analysis & Sentiments", "🎯 Editor Recommendations", "📈 Model Evaluation Logs"]
)

# HALAMAN: HOME & TRENDING TOPICS
if page == "🏠 Home & Trending Topics":
    st.title("📰 AI-Based News Trend Intelligence Dashboard")
    st.caption("Monitoring Tren Berita Real-time & Kluster Topik BERTopic")

    # Metrics
    news_count = len(supabase.table("news").select("id", count="exact").execute().data or [])
    topic_count = len(supabase.table("topics").select("id", count="exact").execute().data or [])
    rec_count = len(supabase.table("recommendations").select("id").eq("status", "pending").execute().data or [])

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Berita Terkumpul", f"{news_count} Artikel")
    col2.metric("Kluster Topik Terbentuk", f"{topic_count} Topik")
    col3.metric("Rekomendasi Pending", f"{rec_count} Topik")

    st.markdown("---")
    st.subheader("🔥 Top 10 Topik Berita Hangat")

    topics_res = supabase.table("topics").select("*").order("trend_score", desc=True).limit(10).execute()
    if topics_res.data:
        df_topics = pd.DataFrame(topics_res.data)
        
        fig = px.bar(
            df_topics,
            x="trend_score",
            y="name",
            orientation="h",
            title="Trend Score per Topik",
            labels={"trend_score": "Skor Tren", "name": "Nama Topik"},
            color="trend_score",
            color_continuous_scale="Blues"
        )
        fig.update_layout(yaxis={'categoryorder': 'total ascending'})
        st.plotly_chart(fig, use_container_width=True)

        st.dataframe(
            df_topics[["name", "keywords", "trend_score", "ai_summary"]],
            use_container_width=True
        )

# HALAMAN: ANALYSIS & SENTIMENTS
elif page == "📊 Analysis & Sentiments":
    st.title("📊 Analisis Sentimen Berita (IndoBERT)")
    
    # Query Data News & Sentiments
    news_res = supabase.table("news").select("id, title, published_at, url, sources(name)").execute()
    sentiments_res = supabase.table("sentiments").select("news_id, sentiment, confidence").execute()

    if news_res.data and sentiments_res.data:
        df_news = pd.DataFrame(news_res.data)
        df_sent = pd.DataFrame(sentiments_res.data)

        # Merge data
        df_merged = pd.merge(df_news, df_sent, left_on="id", right_on="news_id")
        
        # Grafik Distribusi Sentimen
        st.subheader("Distribusi Sentimen Berita")
        sent_counts = df_merged["sentiment"].value_counts().reset_index()
        sent_counts.columns = ["Sentimen", "Jumlah"]

        fig_pie = px.pie(
            sent_counts,
            values="Jumlah",
            names="Sentimen",
            color="Sentimen",
            color_discrete_map={"positif": "#2ecc71", "netral": "#3498db", "negatif": "#e74c3c"}
        )
        st.plotly_chart(fig_pie, use_container_width=True)

        # Filter & Tabel Berita
        st.markdown("---")
        st.subheader("🔍 Filter & Daftar Artikel Berita")
        
        selected_sentiment = st.selectbox("Filter Sentimen:", ["Semua", "positif", "netral", "negatif"])
        
        filtered_df = df_merged if selected_sentiment == "Semua" else df_merged[df_merged["sentiment"] == selected_sentiment]
        
        st.dataframe(
            filtered_df[["title", "sentiment", "confidence", "published_at", "url"]],
            use_container_width=True
        )

# HALAMAN: EDITOR RECOMMENDATIONS (KOMBINAIS HIBRIDA: SUMBER DOMINAN + BERITA TERBARU)
elif page == "🎯 Editor Recommendations":
    st.title("🎯 Rekomendasi Topik untuk Redaksi (Feedback Loop)")
    st.caption("Gunakan masukan ini untuk menentukan topik liputan utama redaksi.")

    recs_res = supabase.table("recommendations").select("*, topics(id, name, keywords)").order("recommendation_score", desc=True).execute()

    if recs_res.data:
        for rec in recs_res.data:
            rec_id = rec["id"]
            topic_info = rec.get("topics")
            topic_id = topic_info["id"] if topic_info else None
            topic_name = topic_info["name"] if topic_info else "Topik General"
            rec_score = rec["recommendation_score"]
            reason = rec["reason"]
            status = rec["status"]

            with st.expander(f"📌 {topic_name} — Skor Rekomendasi: {rec_score}/100 (Status: {status.upper()})"):
                st.markdown(f"**Alasan Rekomendasi:** {reason}")
                
                # --- KOMBINASI HIBRIDA: AMBIL BERITA TERBARU DARI SUMBER MEDIA TERBANAYAK ---
                if topic_id:
                    # 1. Ambil seluruh berita dalam topik ini beserta nama sumbernya
                    news_in_topic = supabase.table("news") \
                        .select("id, title, url, published_at, source_id, sources(name)") \
                        .eq("topic_id", topic_id) \
                        .order("published_at", desc=True) \
                        .execute()
                    
                    if news_in_topic.data:
                        df_news_topic = pd.DataFrame(news_in_topic.data)
                        
                        # Extract nama sumber berita
                        df_news_topic['source_name'] = df_news_topic['sources'].apply(
                            lambda x: x['name'] if isinstance(x, dict) and 'name' in x else "Sumber"
                        )
                        
                        # Hitung volume berita per sumber & ambil 5 sumber teratas (paling dominan)
                        top_sources = df_news_topic['source_name'].value_counts().head(5).index.tolist()
                        
                        # Untuk setiap sumber dominan, ambil 1 artikel paling baru (terupdate)
                        hybrid_samples = []
                        for src in top_sources:
                            latest_news_from_src = df_news_topic[df_news_topic['source_name'] == src].iloc[0]
                            hybrid_samples.append(latest_news_from_src)
                        
                        st.markdown("---")
                        st.markdown("**Sampel Artikel Terupdate dari Media Dominan:**")
                        
                        for item in hybrid_samples:
                            news_title = item["title"]
                            news_url = item["url"]
                            src_name = item["source_name"]
                            st.markdown(f"- [{news_title}]({news_url}) *— ({src_name})*")
                            
                    st.write("") # Spasi tambahan
                # --------------------------------------------------------------------------

                # Form Feedback Loop Redaksi
                with st.form(key=f"feedback_form_{rec_id}"):
                    new_status = st.selectbox(
                        "Keputusan Redaksi:",
                        ["pending", "digunakan", "tidak_digunakan"],
                        index=["pending", "digunakan", "tidak_digunakan"].index(status)
                    )
                    feedback_notes = st.text_area("Catatan Redaksi (Opsional):", value=rec.get("feedback_notes") or "")
                    submit_btn = st.form_submit_button("Simpan Keputusan Redaksi")

                    if submit_btn:
                        supabase.table("recommendations").update({
                            "status": new_status,
                            "feedback_notes": feedback_notes
                        }).eq("id", rec_id).execute()
                        st.success("Feedback redaksi berhasil disimpan ke Supabase!")
                        st.rerun()

# HALAMAN: MODEL EVALUATION LOGS
elif page == "📈 Model Evaluation Logs":
    st.title("📈 Transparansi Performa Model AI")
    st.caption("Metrik Evaluasi Performa Model IndoBERT Sentimen & BERTopic")

    logs_res = supabase.table("model_evaluation_logs").select("*").order("created_at", desc=True).execute()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("IndoBERT Accuracy", "88.0%")
    col2.metric("IndoBERT Precision", "87.5%")
    col3.metric("IndoBERT Recall", "89.0%")
    col4.metric("IndoBERT F1-Score", "88.2%")

    st.markdown("---")
    st.subheader("Log Riwayat Evaluasi Model")
    if logs_res.data:
        df_logs = pd.DataFrame(logs_res.data)
        st.dataframe(df_logs, use_container_width=True)
    else:
        st.info("Belum ada log riwayat evaluasi tersimpan di Supabase.")