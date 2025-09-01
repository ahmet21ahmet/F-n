import requests
from bs4 import BeautifulSoup
import re
import base64
import json
from urllib.parse import urljoin, quote

# SİTENİN ALAN ADI GÜNCELLENDİ
BASE_URL = "https://hdfilmce.com/"
PROXY = "https://2.nejyoner19.workers.dev/?url="  # Proxy prefix

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

m3u_content = ["#EXTM3U"]

def page_url(page: int) -> str:
    if page <= 1:
        return BASE_URL
    return urljoin(BASE_URL, f"yeni-filmler/{page}")

def fetch(url: str) -> BeautifulSoup | None:
    try:
        # Telif sayfasına yönlendirmeyi önlemek için allow_redirects=False eklenebilir
        # Ancak şimdilik varsayılan haliyle bırakıyoruz.
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        # Eğer sayfa telif sayfasına yönlendiriyorsa atla
        if 'telif.php' in resp.url:
            print(f"Telif sayfasına yönlendirildi, atlanıyor: {url}")
            return None
        return BeautifulSoup(resp.text, 'html.parser')
    except requests.exceptions.RequestException as e:
        print(f"İstek hatası ({url}): {e}")
        return None

def absolutize(url: str) -> str:
    if not url:
        return ""
    url = url.strip()
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("/"):
        return urljoin(BASE_URL, url)
    if url.startswith(("http://", "https://")):
        return url
    return urljoin(BASE_URL, url)

def extract_poster_url(soup: BeautifulSoup) -> str:
    img = soup.find("img", attrs={"itemprop": "image"})
    if img:
        for attr in ("src", "data-src", "data-lazy-src"):
            if img.has_attr(attr) and img[attr]:
                return absolutize(img[attr])
    meta = soup.find("meta", attrs={"property": "og:image"})
    if meta and meta.get("content"):
        return absolutize(meta["content"])
    return ""

total_added = 0

for page in range(1, 101):
    list_url = page_url(page)
    print(f"\n=== Sayfa {page}: {list_url} ===")

    soup = fetch(list_url)
    if not soup:
        continue

    lists_div = soup.find('div', class_='lists')
    if not lists_div:
        print("class='lists' bulunamadı, sayfa atlanıyor.")
        continue

    movie_boxes = lists_div.find_all('div', class_='movie_box')
    if not movie_boxes:
        print("Film kutusu bulunamadı.")
        continue

    for movie_box in movie_boxes:
        image_link = movie_box.find('a', class_='image')
        if not image_link or 'href' not in image_link.attrs:
            continue

        movie_url = urljoin(BASE_URL, image_link['href'])
        movie_soup = fetch(movie_url)
        if not movie_soup:
            continue

        title_tag = movie_soup.find('h1') or movie_soup.find('title')
        movie_title = title_tag.text.strip() if title_tag else movie_url.rstrip('/').split('/')[-1].replace('-', ' ').title()

        genre = "Bilinmiyor"
        genre_block = movie_soup.find('b', string="Film Türü")
        if genre_block:
            span_tag = genre_block.find_next('span')
            if span_tag and span_tag.find('a'):
                genre = span_tag.find('a').get_text(strip=True)

        poster_url = extract_poster_url(movie_soup)

        scripts = movie_soup.find_all('script')
        iframe_url = None
        for script in scripts:
            if script.string and "var ilkpartkod" in script.string:
                match = re.search(r"var\s+ilkpartkod\s*=\s*'([^']+)';", script.string)
                if match:
                    try:
                        decoded_string = base64.b64decode(match.group(1)).decode('utf-8', errors='ignore')
                        iframe_match = re.search(r'src="([^"]+)"', decoded_string)
                        if iframe_match:
                            iframe_url = iframe_match.group(1)
                    except Exception:
                        pass
                break

        if not iframe_url:
            continue

        iframe_soup = fetch(iframe_url)
        if not iframe_soup:
            continue

        video_id = None
        subtitle_url = ""
        
        iframe_scripts = iframe_soup.find_all('script')
        for script in iframe_scripts:
            if script.string:
                if "var id =" in script.string:
                    id_match = re.search(r"var\s+id\s*=\s*'([^']+)';", script.string)
                    if id_match:
                        video_id = id_match.group(1)
                
                if "jwSetup.tracks" in script.string:
                    tracks_match = re.search(r"jwSetup\.tracks\s*=\s*(\[.*?\]);", script.string, re.DOTALL)
                    if tracks_match:
                        try:
                            tracks_data_str = tracks_match.group(1)
                            tracks_list = json.loads(tracks_data_str)
                            
                            for track in tracks_list:
                                if (track.get('kind') == 'captions' and 
                                    'türkçe' in track.get('label', '').lower()):
                                    subtitle_url = track.get('file')
                                    print(f"✓ Altyazı bulundu.")
                                    break
                        except (json.JSONDecodeError, AttributeError):
                            pass
        
        if not video_id:
            continue

        real_url = f"https://vidmody.com/vs/{video_id}"
        new_url = PROXY + quote(real_url, safe=":/?&=%")

        extinf_line = f'#EXTINF:-1 tvg-id="{video_id}" tvg-name="{movie_title}"'
        
        if poster_url:
            extinf_line += f' tvg-logo="{poster_url}"'
        
        if subtitle_url:
            extinf_line += f' subtitle-url="{subtitle_url}"'

        extinf_line += f' group-title="{genre}",{movie_title}'

        m3u_content.append(extinf_line)
        m3u_content.append(new_url)

        print(f"✓ Eklendi: {movie_title}")
        total_added += 1

print(f"\nToplam eklenen film: {total_added}")

with open("movies.m3u", "w", encoding="utf-8") as f:
    f.write("\n".join(m3u_content))
print("\nM3U dosyası oluşturuldu: movies.m3u")