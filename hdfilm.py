import asyncio
import aiohttp
import re
import base64
import logging
import time
from urllib.parse import urljoin, quote
from bs4 import BeautifulSoup

# --- Temel Ayarlar ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

BASE_URL = "https://hdfilmsite.com/"
PROXY = "https://2.nejyoner19.workers.dev/?url="  # Proxy prefix
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Referer": BASE_URL
}
MAX_CONCURRENCY = 10  # Aynı anda çalışacak maksimum görev sayısı
MAX_PAGES = 100 # Taranacak maksimum sayfa sayısı

# --- Yardımcı Fonksiyonlar ---

def absolutize(url: str) -> str:
    """Göreceli URL'leri mutlak URL'lere dönüştürür."""
    if not url:
        return ""
    url = url.strip()
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("/"):
        return urljoin(BASE_URL, url)
    return url

def create_proxy_url(original_url: str) -> str:
    """URL'yi proxy üzerinden geçecek şekilde formatlar."""
    if not original_url:
        return ""
    # URL'yi güvenli bir şekilde encode et
    return PROXY + quote(original_url, safe=":/?&=%")

async def fetch_page(session: aiohttp.ClientSession, url: str) -> str | None:
    """Bir sayfanın içeriğini asenkron olarak çeker."""
    try:
        async with session.get(url, headers=HEADERS, timeout=30) as response:
            response.raise_for_status()
            return await response.text()
    except asyncio.TimeoutError:
        logger.error(f"Zaman aşımı hatası: {url}")
        return None
    except aiohttp.ClientError as e:
        logger.error(f"İstek hatası ({url}): {e}")
        return None

# --- Veri Çekme Fonksiyonları ---

def extract_poster_url(soup: BeautifulSoup) -> str:
    """Sayfa içerisinden poster URL'sini bulur."""
    # 1) <img itemprop="image">
    img = soup.find("img", attrs={"itemprop": "image"})
    if img:
        for attr in ("src", "data-src", "data-lazy-src"):
            if img.has_attr(attr) and img[attr]:
                return absolutize(img[attr])
    # 2) <meta property="og:image">
    meta = soup.find("meta", attrs={"property": "og:image"})
    if meta and meta.get("content"):
        return absolutize(meta["content"])
    return ""

async def get_movie_links_from_page(session: aiohttp.ClientSession, page_num: int) -> list[str]:
    """Belirli bir sayfadaki tüm film linklerini toplar."""
    list_url = f"{BASE_URL}/yeni-filmler/{page_num}" if page_num > 1 else BASE_URL
    logger.info(f"Sayfa {page_num} taranıyor: {list_url}")

    content = await fetch_page(session, list_url)
    if not content:
        logger.warning(f"Sayfa {page_num} içeriği alınamadı.")
        return []

    soup = BeautifulSoup(content, 'html.parser')
    lists_div = soup.find('div', class_='lists')
    if not lists_div:
        logger.warning(f"Sayfa {page_num} üzerinde 'lists' div'i bulunamadı.")
        return []

    movie_boxes = lists_div.find_all('div', class_='movie_box')
    links = []
    for movie_box in movie_boxes:
        image_link = movie_box.find('a', class_='image')
        if image_link and image_link.has_attr('href'):
            links.append(urljoin(BASE_URL, image_link['href']))

    logger.info(f"Sayfa {page_num} -> {len(links)} film linki bulundu.")
    return links

async def process_movie(session: aiohttp.ClientSession, movie_url: str) -> dict | None:
    """Tek bir film sayfasını işler ve m3u bilgilerini çıkarır."""
    logger.info(f"Film işleniyor: {movie_url}")
    movie_content = await fetch_page(session, movie_url)
    if not movie_content:
        return None

    soup = BeautifulSoup(movie_content, 'html.parser')

    # 1. Başlık, Tür ve Poster bilgilerini al
    title_tag = soup.find('h1') or soup.find('title')
    movie_title = title_tag.text.strip() if title_tag else "Bilinmeyen Film"

    genre = "Bilinmiyor"
    genre_block = soup.find('b', string="Film Türü")
    if genre_block and (span_tag := genre_block.find_next('span')) and (a_tag := span_tag.find('a')):
        genre = a_tag.get_text(strip=True)

    poster_url = extract_poster_url(soup)

    # 2. 'ilkpartkod' değişkeninden iframe URL'sini çıkar
    iframe_url = None
    for script in soup.find_all('script'):
        if script.string and "var ilkpartkod" in script.string:
            match = re.search(r"var\s+ilkpartkod\s*=\s*'([^']+)';", script.string)
            if match:
                try:
                    decoded_string = base64.b64decode(match.group(1)).decode('utf-8', errors='ignore')
                    iframe_match = re.search(r'src="([^"]+)"', decoded_string)
                    if iframe_match:
                        iframe_url = iframe_match.group(1)
                        logger.info(f"-> Iframe URL'si bulundu: {iframe_url}")
                except Exception as e:
                    logger.warning(f"Base64 çözme hatası: {e}")
                break
    
    if not iframe_url:
        logger.warning(f"Iframe URL'si bulunamadı: {movie_title}")
        return None

    # 3. Iframe sayfasından video ID'sini al
    iframe_content = await fetch_page(session, iframe_url)
    if not iframe_content:
        logger.warning(f"Iframe içeriği alınamadı: {iframe_url}")
        return None

    video_id = None
    iframe_soup = BeautifulSoup(iframe_content, 'html.parser')
    for script in iframe_soup.find_all('script'):
        if script.string and "var id =" in script.string:
            id_match = re.search(r"var\s+id\s*=\s*'([^']+)';", script.string)
            if id_match:
                video_id = id_match.group(1)
                logger.info(f"-> Video ID bulundu: {video_id}")
                break

    if not video_id:
        logger.warning(f"Video ID bulunamadı: {movie_title}")
        return None

    # 4. Son M3U8 URL'sini oluştur
    real_url = f"https://vidmody.com/vs/{video_id}"
    proxied_url = create_proxy_url(real_url)

    return {
        "title": movie_title,
        "genre": genre,
        "poster_url": poster_url,
        "video_id": video_id,
        "final_url": proxied_url
    }

# --- Ana İşlem Akışı ---

async def main():
    """Ana fonksiyon, tüm süreci yönetir."""
    start_time = time.time()
    all_movie_links = []
    
    async with aiohttp.ClientSession() as session:
        # Tüm sayfalardaki film linklerini topla
        for i in range(1, MAX_PAGES + 1):
            links = await get_movie_links_from_page(session, i)
            if not links:
                logger.info(f"Sayfa {i}'de link bulunamadı, tarama durduruluyor.")
                break
            all_movie_links.extend(links)
        
        # Tekrarlanan linkleri kaldır
        unique_links = sorted(list(set(all_movie_links)))
        logger.info(f"\nToplam {len(unique_links)} benzersiz film linki bulundu.\n")

        # Filmleri işle ve M3U dosyasına yaz
        m3u_content = ["#EXTM3U"]
        successful_count = 0
        
        # Görevleri oluştur
        semaphore = asyncio.Semaphore(MAX_CONCURRENCY)
        tasks = []

        async def worker(link):
            async with semaphore:
                return await process_movie(session, link)

        for link in unique_links:
            tasks.append(worker(link))
            
        # Görevleri çalıştır ve sonuçları topla
        results = await asyncio.gather(*tasks)

        for result in results:
            if result:
                # M3U formatına uygun satırları oluştur
                extinf = f'#EXTINF:-1 tvg-id="{result["video_id"]}" tvg-name="{result["title"]}"'
                if result["poster_url"]:
                    extinf += f' tvg-logo="{result["poster_url"]}"'
                extinf += f' group-title="{result["genre"]}",{result["title"]}'
                
                m3u_content.append(extinf)
                m3u_content.append(result["final_url"])
                logger.info(f"✓ Eklendi: {result['title']}")
                successful_count += 1

    # M3U dosyasını kaydet
    with open("movies.m3u", "w", encoding="utf-8") as f:
        f.write("\n".join(m3u_content))

    end_time = time.time()
    logger.info("\n" + "="*30)
    logger.info(f"İşlem Tamamlandı!")
    logger.info(f"Toplam eklenen film: {successful_count}")
    logger.info(f"M3U dosyası oluşturuldu: movies.m3u")
    logger.info(f"Geçen süre: {end_time - start_time:.2f} saniye")
    logger.info("="*30)


if __name__ == "__main__":
    asyncio.run(main())