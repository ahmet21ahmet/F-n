# Gerekli kütüphaneleri içe aktarıyoruz
import requests
from bs4 import BeautifulSoup
import re
import json
import time

# --- AYARLAR ---
# Ana sayfa URL'si
MAIN_PAGE_URL = "https://www.filmmodu.nl/"
# Linkleri oluşturmak için kullanılacak şablonlar
M3U8_TEMPLATE = "https://d1.rovideos.org/v/d/{imdb_id}/{lang}/1080.m3u8"
VTT_TEMPLATE = "https://www.filmmodu.nl/uploads/subs/{imdb_id}/tr.vtt"

def get_all_movie_pages(url):
    """
    Sitenin ana sayfasından veya arşiv sayfalarından tüm film linklerini toplar.
    Şimdilik sadece ana sayfayı analiz edecek şekilde basit tutulmuştur.
    Daha fazlası için sayfalama (pagination) mantığı eklenebilir.
    """
    print(f"Film linkleri şu adresten alınıyor: {url}")
    try:
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        movie_links = set() # Tekrarları önlemek için set kullanıyoruz
        # Film afişlerinin bulunduğu 'a' etiketlerini buluyoruz.
        # Sitenin yapısına göre bu seçici (selector) değişebilir.
        for a_tag in soup.select('div.poster a'):
            href = a_tag.get('href')
            if href and not href.startswith('#'):
                movie_links.add(href)
        
        print(f"{len(movie_links)} adet benzersiz film sayfası linki bulundu.")
        return list(movie_links)
    except requests.exceptions.RequestException as e:
        print(f"Hata: Ana sayfaya ulaşılamadı. {e}")
        return []

def extract_movie_details(movie_url):
    """
    Tek bir film sayfasını analiz ederek IMDb ID'sini ve başlığını bulur,
    ardından bu bilgilere dayanarak içerik linklerini oluşturur.
    """
    print(f"Analiz ediliyor: {movie_url}")
    try:
        response = requests.get(movie_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
        response.raise_for_status()
        
        # Sayfa içeriğinde IMDb ID'sini (tt ile başlayan) arıyoruz.
        # Genellikle script etiketleri içinde bulunur.
        imdb_id_match = re.search(r'"(tt\d+)"', response.text)
        
        if not imdb_id_match:
            print(f"  -> IMDb ID bulunamadı. Bu sayfa atlanıyor.")
            return None
            
        imdb_id = imdb_id_match.group(1)
        
        # Film başlığını almak için BeautifulSoup kullanıyoruz
        soup = BeautifulSoup(response.text, 'html.parser')
        title = soup.find('h1', class_='title').text.strip() if soup.find('h1', class_='title') else "Başlık Bulunamadı"
        
        # Bulunan IMDb ID'si ile linkleri şablona göre oluşturuyoruz
        movie_data = {
            "title": title,
            "imdb_id": imdb_id,
            "page_url": movie_url,
            "dubbed_m3u8": M3U8_TEMPLATE.format(imdb_id=imdb_id, lang="tr"),
            "subtitled_m3u8": M3U8_TEMPLATE.format(imdb_id=imdb_id, lang="en"),
            "subtitle_vtt": VTT_TEMPLATE.format(imdb_id=imdb_id)
        }
        
        print(f"  -> Bulundu: {title} ({imdb_id})")
        return movie_data
        
    except requests.exceptions.RequestException as e:
        print(f"  -> Hata: Film sayfasına ulaşılamadı. {e}")
        return None
    except Exception as e:
        print(f"  -> Beklenmedik bir hata oluştu: {e}")
        return None

if __name__ == "__main__":
    # 1. Adım: Sitedeki tüm film sayfalarının linklerini al
    movie_page_links = get_all_movie_pages(MAIN_PAGE_URL)
    
    all_movies_data = []
    
    # 2. Adım: Her bir film sayfasını tek tek analiz et
    if movie_page_links:
        for link in movie_page_links:
            details = extract_movie_details(link)
            if details:
                all_movies_data.append(details)
            # Sunucuyu yormamak için her istek arasında kısa bir bekleme ekliyoruz
            time.sleep(0.5) 
            
    # 3. Adım: Toplanan tüm verileri bir JSON dosyasına yaz
    if all_movies_data:
        output_filename = 'filmmodu_links.json'
        with open(output_filename, 'w', encoding='utf-8') as f:
            json.dump(all_movies_data, f, ensure_ascii=False, indent=4)
        print(f"\nİşlem tamamlandı! Toplam {len(all_movies_data)} filmin bilgisi '{output_filename}' dosyasına kaydedildi.")
    else:
        print("\nHiçbir film bilgisi çekilemedi.")