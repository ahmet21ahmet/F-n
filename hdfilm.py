import requests
from bs4 import BeautifulSoup
import re
import base64
from urllib.parse import urljoin, quote
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# --- Ayarlar ---
BASE_URL = "https://hdfilmsite.com/"
PROXY = "https://2.nejyoner19.workers.dev/?url="  # Video URL'leri için proxy
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"

# --- Selenium Tarayıcı Kurulumu ---
def setup_driver():
    """
    GitHub Actions ve lokal ortamlar için uyumlu, headless Selenium WebDriver'ı kurar.
    """
    print("Selenium WebDriver hazırlanıyor...")
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Arka planda çalıştırır
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument(f"user-agent={USER_AGENT}")
    
    # webdriver-manager ile sürücüyü otomatik olarak indir ve kur
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    print("WebDriver hazır.")
    return driver

# --- Yardımcı Fonksiyonlar ---
def page_url(page: int) -> str:
    """Belirtilen sayfa numarası için URL oluşturur."""
    if page <= 1:
        return BASE_URL
    return urljoin(BASE_URL, f"yeni-filmler/{page}")

def get_page_source_with_selenium(driver, url: str) -> str | None:
    """Selenium kullanarak bir sayfanın JavaScript'i işlenmiş HTML kaynağını alır."""
    try:
        driver.get(url)
        # Sayfanın yüklenmesi için kısa bir bekleme süresi ekleyebiliriz.
        # Daha gelişmiş yöntemler WebDriverWait kullanmaktır.
        time.sleep(3) # JavaScript'in yüklenmesi için 3 saniye bekle
        return driver.page_source
    except Exception as e:
        print(f"Selenium ile sayfa yüklenemedi ({url}): {e}")
        return None

def fetch_requests(url: str) -> BeautifulSoup | None:
    """Basit iframe gibi sayfalar için requests kütüphanesini kullanır."""
    try:
        headers = {"User-Agent": USER_AGENT}
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, 'html.parser')
    except requests.exceptions.RequestException as e:
        print(f"Requests ile istek hatası ({url}): {e}")
        return None

def absolutize(url: str) -> str:
    """Göreceli URL'leri mutlak URL'lere dönüştürür."""
    if not url: return ""
    url = url.strip()
    if url.startswith("//"): return "https:" + url
    if url.startswith("/"): return urljoin(BASE_URL, url)
    return url

def extract_poster_url(soup: BeautifulSoup) -> str:
    """Sayfa içerisinden poster URL'sini bulmaya çalışır."""
    img = soup.find("img", attrs={"itemprop": "image"})
    if img:
        for attr in ("src", "data-src", "data-lazy-src"):
            if img.has_attr(attr) and img[attr]:
                return absolutize(img[attr])
    meta = soup.find("meta", attrs={"property": "og:image"})
    if meta and meta.get("content"):
        return absolutize(meta["content"])
    return ""

# --- Ana İşlem ---
def main():
    driver = setup_driver()
    m3u_content = ["#EXTM3U"]
    total_added = 0
    page = 1

    while True:
        list_url = page_url(page)
        print(f"\n{'='*10} Sayfa {page}: {list_url} {'='*10}")

        html_source = get_page_source_with_selenium(driver, list_url)
        if not html_source:
            print(f"Sayfa {page} kaynağı alınamadı. İşlem sonlandırılıyor.")
            break

        soup = BeautifulSoup(html_source, 'html.parser')
        
        movie_boxes = soup.select('div.lists div.movie_box')
        if not movie_boxes:
            print("Bu sayfada film bulunamadı. Muhtemelen son sayfaya ulaşıldı.")
            break

        for movie_box in movie_boxes:
            image_link = movie_box.find('a', class_='image')
            if not (image_link and image_link.get('href')):
                continue

            movie_url = urljoin(BASE_URL, image_link['href'])
            print(f"-> Film işleniyor: {movie_url}")
            
            movie_html = get_page_source_with_selenium(driver, movie_url)
            if not movie_html:
                continue
            
            movie_soup = BeautifulSoup(movie_html, 'html.parser')
            
            title_tag = movie_soup.find('h1') or movie_soup.find('title')
            movie_title = title_tag.text.strip() if title_tag else "Başlık Bulunamadı"

            genre_block = movie_soup.find('b', string="Film Türü")
            genre = genre_block.find_next('span').find('a').get_text(strip=True) if genre_block else "Bilinmiyor"
            
            poster_url = extract_poster_url(movie_soup)

            iframe_url = None
            scripts = movie_soup.find_all('script', string=re.compile(r"var\s+ilkpartkod"))
            for script in scripts:
                match = re.search(r"var\s+ilkpartkod\s*=\s*'([^']+)';", script.string)
                if match:
                    try:
                        decoded_string = base64.b64decode(match.group(1)).decode('utf-8', errors='ignore')
                        iframe_match = re.search(r'src="([^"]+)"', decoded_string)
                        if iframe_match:
                            iframe_url = iframe_match.group(1)
                            break
                    except Exception as e:
                        print(f"Base64 çözme hatası: {e}")
            
            if not iframe_url:
                print(f"  - Uyarı: iframe URL ('ilkpartkod') bulunamadı: {movie_title}")
                continue

            iframe_soup = fetch_requests(iframe_url)
            if not iframe_soup:
                continue

            video_id = None
            id_script = iframe_soup.find('script', string=re.compile(r"var\s+id\s*="))
            if id_script:
                id_match = re.search(r"var\s+id\s*=\s*'([^']+)';", id_script.string)
                if id_match:
                    video_id = id_match.group(1)
            
            if not video_id:
                print(f"  - Uyarı: Video ID ('var id') bulunamadı: {movie_title}")
                continue

            real_url = f"https://vidmody.com/vs/{video_id}"
            proxied_url = PROXY + quote(real_url, safe=":/?&=%")
            
            info_line = f'#EXTINF:-1 tvg-id="{video_id}" tvg-name="{movie_title}" tvg-logo="{poster_url}" group-title="{genre}",{movie_title}'
            m3u_content.append(info_line)
            m3u_content.append(proxied_url)

            print(f"  ✓ Eklendi: {movie_title}")
            total_added += 1

        page += 1 # Sonraki sayfaya geç
        time.sleep(2) # Siteye çok yüklenmemek için sayfalar arası bekle

    driver.quit()
    print(f"\nTarama tamamlandı. Toplam eklenen film: {total_added}")

    with open("movies.m3u", "w", encoding="utf-8") as f:
        f.write("\n".join(m3u_content))
    print("\nM3U dosyası oluşturuldu: movies.m3u")


if __name__ == "__main__":
    main()