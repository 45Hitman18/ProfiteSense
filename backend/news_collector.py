import json
from datetime import datetime
from database import get_connection, init_db, save_analysis
from nlp_engine import analyze_article, is_indian_market_article
from providers.news.aggregator import NewsAggregator

aggregator = NewsAggregator()

def sync_all_news() -> dict:
    """
    Ingests live news using the provider fallback chain:
    Provider A (Marketaux) -> Provider B (Alpha Vantage) -> Provider C (NewsAPI) -> Legitimate Financial RSS.
    Filters exclusively for Indian shares, Indian share market events, and macro factors affecting Indian markets.
    Analyzes with NLP and stores in SQLite database.
    """
    init_db()
    all_raw = aggregator.fetch_all(target_count=60)
    
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM articles")
    existing_ids = set(row[0] for row in cursor.fetchall())
    
    new_count = 0
    analyzed_count = 0
    
    for art in all_raw:
        if art["id"] in existing_ids:
            continue
            
        # Strictly ensure the news is relevant to Indian equities or market-affecting factors
        if not is_indian_market_article(art["title"], art.get("summary", ""), art.get("raw_content", "")):
            continue
            
        existing_ids.add(art["id"])
        
        cursor.execute("""
        INSERT INTO articles (id, title, summary, source, url, published_at, category, raw_content, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            art["id"], art["title"], art["summary"], art["source"],
            art["url"], art["published_at"], art["category"], art["raw_content"], art["created_at"]
        ))
        new_count += 1
        
        # Run NLP analysis and save full schema
        analysis = analyze_article(art["title"], art["summary"], art["raw_content"])
        save_analysis(art["id"], analysis, conn=conn)
        analyzed_count += 1
        
    conn.commit()
    conn.close()
    
    return {
        "status": "success",
        "new_articles_ingested": new_count,
        "articles_analyzed": analyzed_count,
        "active_providers": aggregator.get_active_providers(),
        "timestamp": datetime.now().isoformat()
    }

if __name__ == "__main__":
    print("Testing sync_all_news with fallback chain...")
    res = sync_all_news()
    print("Sync complete:", res)
