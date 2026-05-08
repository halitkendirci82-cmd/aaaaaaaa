import sqlite3
import httpx
from bs4 import BeautifulSoup
import asyncio

DB_FILE = "quotes.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # 매 실행 시 기존 테이블을 삭제하고 새로 생성하여 최신 상태 유지
    cursor.execute('DROP TABLE IF EXISTS quotes')
    
    # UNIQUE 제약 조건을 제거하여 교차 태그 간의 중복 수집 허용
    cursor.execute('''
        CREATE TABLE quotes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT,
            author TEXT,
            tags TEXT
        )
    ''')
    conn.commit()
    conn.close()

async def fetch_top_ten_tags():
    """메인 페이지에서 실시간으로 Top 10 태그를 크롤링하여 반환합니다."""
    async with httpx.AsyncClient() as client:
        response = await client.get("http://quotes.toscrape.com/")
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            tag_elements = soup.select(".tags-box .tag-item a.tag")
            top_tags = [tag.get_text(strip=True) for tag in tag_elements][:10]
            return top_tags
    return []

async def fetch_quotes_by_tag(tag: str, limit: int = 20):
    quotes_data = []
    page = 1
    
    async with httpx.AsyncClient() as client:
        while len(quotes_data) < limit:
            url = f"http://quotes.toscrape.com/tag/{tag}/page/{page}/"
            response = await client.get(url)
            
            if response.status_code != 200:
                break
                
            soup = BeautifulSoup(response.text, "html.parser")
            quotes = soup.find_all("div", class_="quote")
            
            if not quotes:
                break
                
            for quote in quotes:
                if len(quotes_data) >= limit:
                    break
                text = quote.find("span", class_="text").get_text(strip=True)
                author = quote.find("small", class_="author").get_text(strip=True)
                tags = [t.get_text(strip=True) for t in quote.find_all("a", class_="tag")]
                
                quotes_data.append((text, author, ",".join(tags)))
            page += 1
            
    return quotes_data

async def run_scraper():
    print("실시간 Top 10 태그 정보를 가져오는 중...")
    top_tags = await fetch_top_ten_tags()
    
    if not top_tags:
        print("태그를 가져오지 못했습니다. 사이트 상태를 확인하세요.")
        return

    print(f"수집 대상 태그: {', '.join(top_tags)}\n")
    
    init_db()
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    total_added = 0
    for tag in top_tags:
        data = await fetch_quotes_by_tag(tag, limit=20)
        found_count = len(data)
        
        added_for_tag = 0
        duplicate_in_tag = 0
        
        # 단일 태그 내에서의 중복 검사를 위한 임시 셋(Set)
        seen_in_this_tag = set()
        
        for text, author, tags in data:
            # 단일 태그 안에서 이미 수집된 격언이라면 건너뜀
            if text in seen_in_this_tag:
                duplicate_in_tag += 1
                continue
                
            seen_in_this_tag.add(text)
            
            # DB 삽입 (교차 태그 간 중복은 허용되므로 UNIQUE 에러 발생 안 함)
            cursor.execute(
                "INSERT INTO quotes (text, author, tags) VALUES (?, ?, ?)",
                (text, author, tags)
            )
            added_for_tag += 1
            total_added += 1
                
        print(f"[{tag}] 발견: {found_count}개 -> DB 저장: {added_for_tag}개 (단일 태그 내 중복 제외: {duplicate_in_tag}개)")
                
    conn.commit()
    conn.close()
    print(f"\nDB 갱신 완료. 총 {total_added}개의 격언이 저장되었습니다.")

if __name__ == "__main__":
    asyncio.run(run_scraper())
