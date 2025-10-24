# --- BİRLEŞTİRİLMİŞ TÜM İTHALATLAR ---
import requests
import zstandard as zstd
import io
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import datetime
import asyncio
from playwright.async_api import async_playwright
import aiohttp
from zoneinfo import ZoneInfo
import platform
import sys
import re
import concurrent.futures

# ==============================================================================
# BÖLÜM 1: ISTPLAY SCRAPER (requests, zstd, threadpool)
# ==============================================================================

# --- 1.1. IstPlay: Hata toleranslı decompress fonksiyonu ---
def decompress_content_istplay(response):
    """Gelen yanıtı zstd formatında ise açar, değilse olduğu gibi döndürür."""
    try:
        if response.headers.get("content-encoding") == "zstd":
            dctx = zstd.ZstdDecompressor()
            with dctx.stream_reader(io.BytesIO(response.content)) as reader:
                return reader.read()
        else:
            return response.content
    except zstd.ZstdError:
        return response.content

# --- 1.2. IstPlay: m3u8 linkini alma fonksiyonu ---
def get_m3u8_istplay(stream_id, headers):
    """Verilen stream_id için m3u8 linkini çeker."""
    try:
        url = f"https://istplay.xyz/tv/?stream_id={stream_id}"
        response = requests.get(url, headers=headers, timeout=10)
        data = decompress_content_istplay(response)
        html_text = data.decode("utf-8", errors="replace")
        soup = BeautifulSoup(html_text, "html.parser")
        source = soup.find("source", {"type": "application/x-mpegURL"})
        if source and source.get("src"):
            return stream_id, source["src"]
    except Exception as e:
        print(f"⚠️ Hata (istplay stream_id={stream_id}): {e}")
    return stream_id, None

# --- 1.3. IstPlay: Spor isimleri ve logolar ---
SPORT_TRANSLATION_ISTPLAY = {
    "HORSE_RACING": {"name": "AT YARIŞI", "logo": "https://medya-cdn.tjk.org/haberftp/2022/ayyd12082022.jpg"},
    "FOOTBALL"    : {"name": "FUTBOL", "logo": "https://thepfsa.co.uk/wp-content/uploads/2022/06/Playing-Football.jpg"},
    "BASKETBALL"  : {"name": "BASKETBOL", "logo": "https://minio.yalispor.com.tr/sneakscloud/blog/basketbol-hakkinda-bilmen-gereken-kurallar_5e53ae3fdd3fc.jpg"},
    "TENNIS"      : {"name": "TENİS", "logo": "https://calista.com.tr/media/c2sl3pug/calista-resort-hotel-blog-tenis-banner.jpg"},
    "ICE_HOCKEY"  : {"name": "BUZ HOKEYİ", "logo": "https://istanbulbbsk.org/uploads/medias/public-4b3b1703-c744-4631-8c42-8bab9be542bc.jpg"},
    "TABLE_TENNIS": {"name": "MASA TENİSİ", "logo": "https://tossfed.gov.tr/storage/2022/03/1399486-masa-tenisinde-3-lig-2-nisan-da-baslayacak-60642719b43dd.jpg"},
    "VOLLEYBALL"  : {"name": "VOLEYBOL", "logo": "https://www.sidasturkiye.com/images/aktiviteler/alt-aktiviteler_voleybol4.jpg"},
    "BADMINTON"   : {"name": "BADMİNTON", "logo": "https://sporium.net/wp-content/uploads/2017/12/badminton-malatya-il-sampiyonasi-9178452_8314_o.jpg"},
    "CRICKET"     : {"name": "KRİKET", "logo": "https://storage.acerapps.io/app-1358/kriket-nedir-nasil-oynanir-kriket-kurallari-nelerdir-sporsepeti-sportsfly-spor-kutuphanesi.jpg"},
    "HANDBALL"    : {"name": "HENTBOL", "logo": "https://image.fanatik.com.tr/i/fanatik/75/0x410/6282949745d2a051587ed23b.jpg"},
    "BASEBALL"    : {"name": "BEYZBOL", "logo": "https://seyler.ekstat.com/img/max/800/d/dqOJz5N8jLORqVaA-636783298725804088.jpg"},
    "SNOOKER"     : {"name": "İNGİLTERE BİLARDOSU", "logo": "https://cdn.shopify.com/s/files/1/0644/5685/1685/files/pool-table-graphic-1.jpg"},
    "BILLIARDS"   : {"name": "BİLARDO", "logo": "https://www.bilardo.org.tr/image/be2a4809f1c796e4453b45ccf0d9740c.jpg"},
    "BICYCLE"     : {"name": "BİSİKLET YARIŞI", "logo": "https://www.gazetekadikoy.com.tr/Uploads/gazetekadikoy.com.tr/202204281854011-img.jpg"},
    "BOXING"      : {"name": "BOKS", "logo": "https://www.sportsmith.co/wp-content/uploads/2023/04/Thumbnail-scaled.jpg"},
}

# --- 1.4. IstPlay: Ana Çalıştırıcı Fonksiyon ---
def fetch_istplay_streams():
    """IstPlay sitesinden verileri çeker ve M3U satır listesi döndürür."""
    print("📢 [IstPlay] Yayın listesi alınıyor...")
    url_list = "https://api.istplay.xyz/stream-list-v2/?tv=tv"
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Accept-Language": "tr-TR,tr;q=0.9,en-GB;q=0.8,en;q=0.7,en-US;q=0.6",
        "Origin": "https://istplay.xyz",
        "Referer": "https://istplay.xyz/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/141.0.0.0 Safari/537.36",
    }
    
    response = requests.get(url_list, headers=headers, timeout=15)
    data = decompress_content_istplay(response)
    parsed = json.loads(data)
    print("✅ [IstPlay] Yayın listesi başarıyla alındı.")

    all_events = []
    for sport_name, sport_category in parsed.get("sports", {}).items():
        if not isinstance(sport_category, dict):
            continue
        events = sport_category.get("events", {})
        iterable = events.items() if isinstance(events, dict) else [(str(i), e) for i, e in enumerate(events)]
        for event_id, event_data in iterable:
            stream_id = event_data.get("stream_id")
            if stream_id:
                all_events.append((sport_name, event_id, event_data))

    print(f"🔗 [IstPlay] {len(all_events)} adet yayın linki çekiliyor...")
    with ThreadPoolExecutor(max_workers=20) as executor:
        future_to_event = {executor.submit(get_m3u8_istplay, ev[2]['stream_id'], headers): ev for ev in all_events}
        for future in as_completed(future_to_event):
            sport_name, event_id, event_data = future_to_event[future]
            try:
                sid, m3u8_url = future.result()
                event_data["m3u8_url"] = m3u8_url
            except Exception as e:
                print(f"⚠️ [IstPlay] Future hatası: {e}")
    print("✅ [IstPlay] Tüm linkler çekildi.")

    print("📝 [IstPlay] M3U formatı oluşturuluyor...")
    output_lines = ['#EXTM3U', '']

    for sport_name, sport_category in parsed.get("sports", {}).items():
        if not isinstance(sport_category, dict):
            continue

        events = sport_category.get("events", {})
        iterable = events.items() if isinstance(events, dict) else [(str(i), e) for i, e in enumerate(events)]

        for event_id, event_data in iterable:
            league = event_data.get("league", "Bilinmiyor")
            competitors = event_data.get("competitiors", {}) # API'de yazım hatası var
            home = competitors.get("home", "").strip()
            away = competitors.get("away", "").strip()
            m3u8_url = event_data.get("m3u8_url")

            if not m3u8_url:
                continue

            start_timestamp = event_data.get("start_time")
            start_time_str = ""
            if start_timestamp:
                try:
                    dt_object = datetime.datetime.fromtimestamp(int(start_timestamp))
                    start_time_str = f"[{dt_object.strftime('%H:%M')}] "
                except (ValueError, TypeError):
                    start_time_str = "" 

            sport_info = SPORT_TRANSLATION_ISTPLAY.get(sport_name.upper(), {"name": sport_name.upper(), "logo": ""})
            display_sport = sport_info["name"]
            logo_url = sport_info.get("logo", "")
            group_title = f"IstPlay - {display_sport}" # Grup başlığına kaynak eklendi

            if sport_name.upper() == "HORSE_RACING":
                display_title = f"{start_time_str}{home.upper()} ({league.upper()}) (telegram @playtvmedya)"
            else:
                display_title = f"{start_time_str}{home.upper()} vs {away.upper()} ({league.upper()}) (telegram @playtvmedya)"

            line = f'#EXTINF:-1 tvg-name="{display_sport}" tvg-logo="{logo_url}" group-title="{group_title}",{display_title}\n{m3u8_url}'
            output_lines.append(line)
            
    return output_lines


# ==============================================================================
# BÖLÜM 2: PPVLAND SCRAPER (asyncio, playwright, aiohttp)
# ==============================================================================

# --- 2.1. PPVLand: Sabitler ---
API_URL_PPV = "https://ppv.to/api/streams"

CUSTOM_HEADERS_PPV = [
    '#EXTVLCOPT:http-origin=https://ppvs.su',
    '#EXTVLCOPT:http-referrer=https://ppvs.su/',
    '#EXTVLCOPT:http-user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:140.0) Gecko/20100101 Firefox/140.0'
]

ALLOWED_CATEGORIES_PPV = {
    "24/7 Streams", "Wrestling", "Football", "Basketball", "Baseball",
    "Combat Sports", "Motorsports", "Miscellaneous", "Boxing", "Darts",
    "American Football"
}

CATEGORY_LOGOS_PPV = {
    "24/7 Streams": "https://github.com/BuddyChewChew/ppv/blob/main/assets/24-7.png?raw=true",
    "Wrestling": "https://github.com/BuddyChewChew/ppv/blob/main/assets/wwe.png?raw=true",
    "Football": "https://github.com/BuddyChewChew/ppv/blob/main/assets/football.png?raw=true",
    "Basketball": "https://github.com/BuddyChewChew/ppv/blob/main/assets/nba.png?raw=true",
    "Baseball": "https://github.com/BuddyChewChew/ppv/blob/main/assets/baseball.png?raw=true",
    "Combat Sports": "https://github.com/BuddyChewChew/ppv/blob/main/assets/mma.png?raw=true",
    "Motorsports": "https://github.com/BuddyChewChew/ppv/blob/main/assets/f1.png?raw=true",
    "Miscellaneous": "https://github.com/BuddyChewChew/ppv/blob/main/assets/24-7.png?raw=true",
    "Boxing": "https://github.com/BuddyChewChew/ppv/blob/main/assets/boxing.png?raw=true",
    "Darts": "https://github.com/BuddyChewChew/ppv/blob/main/assets/darts.png?raw=true",
    "American Football": "https://github.com/BuddyChewChew/ppv/blob/main/assets/nfl.png?raw=true"
}

CATEGORY_TVG_IDS_PPV = {
    "24/7 Streams": "24.7.Dummy.us",
    "Football": "Soccer.Dummy.us",
    "Wrestling": "PPV.EVENTS.Dummy.us",
    "Combat Sports": "PPV.EVENTS.Dummy.us",
    "Baseball": "MLB.Baseball.Dummy.us",
    "Basketball": "Basketball.Dummy.us",
    "Motorsports": "Racing.Dummy.us",
    "Miscellaneous": "PPV.EVENTS.Dummy.us",
    "Boxing": "PPV.EVENTS.Dummy.us",
    "Darts": "Darts.Dummy.us",
    "American Football": "NFL.Dummy.us"
}

GROUP_RENAME_MAP_PPV = {
    "24/7 Streams": "PPVLand - Live Channels 24/7",
    "Wrestling": "PPVLand - Wrestling Events",
    "Football": "PPVLand - Global Football Streams",
    "Basketball": "PPVLand - Basketball Hub",
    "Baseball": "PPVLand - Baseball Action HD",
    "Combat Sports": "PPVLand - MMA & Fight Nights",
    "Motorsports": "PPVLand - Motorsport Live",
    "Miscellaneous": "PPVLand - Random Events",
    "Boxing": "PPVLand - Boxing",
    "Darts": "PPVLand - Darts",
    "American Football": "PPVLand - NFL Action"
}

# --- 2.2. PPVLand: Yardımcı Fonksiyonlar ---
async def check_m3u8_url_ppv(url):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://ppvs.su",
            "Origin": "https://ppvs.su"
        }
        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, headers=headers) as resp:
                return resp.status == 200
    except Exception as e:
        print(f"❌ [PPVLand] Error checking {url}: {e}")
        return False

async def get_streams_ppv():
    try:
        timeout = aiohttp.ClientTimeout(total=30)
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
            print(f"🌐 [PPVLand] Fetching streams from {API_URL_PPV}")
            async with session.get(API_URL_PPV) as resp:
                print(f"🔍 [PPVLand] Response status: {resp.status}")
                if resp.status != 200:
                    error_text = await resp.text()
                    print(f"❌ [PPVLand] Error response: {error_text[:500]}")
                    return None
                return await resp.json()
    except Exception as e:
        print(f"❌ [PPVLand] Error in get_streams_ppv: {str(e)}")
        return None

async def grab_m3u8_from_iframe_ppv(page, iframe_url):
    found_streams = set()

    def handle_response(response):
        if ".m3u8" in response.url:
            found_streams.add(response.url)

    page.on("response", handle_response)
    print(f"🌐 [PPVLand] Navigating to iframe: {iframe_url}")

    try:
        await page.goto(iframe_url, timeout=15000)
    except Exception as e:
        print(f"❌ [PPVLand] Failed to load iframe: {e}")
        page.remove_listener("response", handle_response)
        return set()

    await asyncio.sleep(2)

    try:
        box = page.viewport_size or {"width": 1280, "height": 720}
        cx, cy = box["width"] / 2, box["height"] / 2
        for i in range(4):
            if found_streams:
                break
            print(f"🖱️ [PPVLand] Click #{i + 1}")
            try:
                await page.mouse.click(cx, cy)
            except Exception:
                pass
            await asyncio.sleep(0.3)
    except Exception as e:
        print(f"❌ [PPVLand] Mouse click error: {e}")

    print("⏳ [PPVLand] Waiting 5s for final stream load...")
    await asyncio.sleep(5)
    page.remove_listener("response", handle_response)

    valid_urls = set()
    for url in found_streams:
        if await check_m3u8_url_ppv(url):
            valid_urls.add(url)
        else:
            print(f"❌ [PPVLand] Invalid or unreachable URL: {url}")
    return valid_urls

def build_m3u_ppv(streams, url_map):
    lines = ['#EXTM3U url-tvg="https://epgshare01.online/epgshare01/epg_ripper_DUMMY_CHANNELS.xml.gz"']
    seen_names = set()

    for s in streams:
        name_lower = s["name"].strip().lower()
        if name_lower in seen_names:
            continue
        seen_names.add(name_lower)

        unique_key = f"{s['name']}::{s['category']}::{s['iframe']}"
        urls = url_map.get(unique_key, [])

        if not urls:
            print(f"⚠️ [PPVLand] No working URLs for {s['name']}")
            continue

        orig_category = s["category"].strip()
        final_group = GROUP_RENAME_MAP_PPV.get(orig_category, orig_category)
        logo = CATEGORY_LOGOS_PPV.get(orig_category, "")
        tvg_id = CATEGORY_TVG_IDS_PPV.get(orig_category, "Sports.Dummy.us")
        url = next(iter(urls))

        # --- İSTENEN DEĞİŞİKLİK BURADA ---
        title = f"{s['name']} (telegram @playtvmedya)"
        lines.append(f'#EXTINF:-1 tvg-id="{tvg_id}" tvg-logo="{logo}" group-title="{final_group}",{title}')
        lines.extend(CUSTOM_HEADERS_PPV)
        lines.append(url)

    return lines

# --- 2.3. PPVLand: Ana Çalıştırıcı Fonksiyon ---
async def fetch_ppvland_streams():
    """PPVLand sitesinden verileri çeker ve M3U satır listesi döndürür."""
    print("🚀 [PPVLand] Stream Fetcher Başlatılıyor")
    data = await get_streams_ppv()

    if not data or 'streams' not in data:
        print("❌ [PPVLand] API'den geçerli veri alınamadı")
        if data:
            print(f"API Yanıtı: {data}")
        return ["#EXTM3U"]

    print(f"✅ [PPVLand] {len(data['streams'])} kategori bulundu")
    streams = []

    for category in data.get("streams", []):
        cat = category.get("category", "").strip()
        if cat not in ALLOWED_CATEGORIES_PPV:
            continue
        for stream in category.get("streams", []):
            iframe = stream.get("iframe")
            name = stream.get("name", "Unnamed Event")
            if iframe:
                streams.append({"name": name, "iframe": iframe, "category": cat})

    seen_names = set()
    deduped_streams = []
    for s in streams:
        name_key = s["name"].strip().lower()
        if name_key not in seen_names:
            seen_names.add(name_key)
            deduped_streams.append(s)
    streams = deduped_streams

    if not streams:
        print("🚫 [PPVLand] API yanıtında geçerli yayın bulunamadı.")
        return ["#EXTM3U"]

    print(f"🔍 [PPVLand] İşlenecek {len(streams)} benzersiz yayın bulundu.")

    async with async_playwright() as p:
        browser = await p.firefox.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        url_map = {}
        for s in streams:
            key = f"{s['name']}::{s['category']}::{s['iframe']}"
            print(f"\n🔍 [PPVLand] Scraping: {s['name']} ({s['category']})")
            urls = await grab_m3u8_from_iframe_ppv(page, s["iframe"])
            if urls:
                print(f"✅ [PPVLand] {s['name']} için {len(urls)} yayın bulundu")
            url_map[key] = urls

        await browser.close()

    print("\n📝 [PPVLand] M3U formatı oluşturuluyor...")
    playlist_lines = build_m3u_ppv(streams, url_map)
    return playlist_lines


# ==============================================================================
# BÖLÜM 3: STREAMEDSU SCRAPER (requests, concurrent.futures)
# ==============================================================================

# --- 3.1. StreamedSU: Sabitler ---
FALLBACK_LOGOS_SU = {
    "american-football": "http://drewlive24.duckdns.org:9000/Logos/Am-Football2.png",
    "football":          "https://i.imgur.com/RvN0XSF.png",
    "fight":             "http://drewlive24.duckdns.org:9000/Logos/Combat-Sports.png",
    "basketball":        "http://drewlive24.duckdns.org:9000/Logos/Basketball5.png"
}

CUSTOM_HEADERS_SU = {
    "Origin": "https://embedsports.top",
    "Referer": "https://embedsports.top/",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:143.0) Gecko/20100101 Firefox/143.0"
}

TV_IDS_SU = {
    "Baseball": "MLB.Baseball.Dummy.us",
    "Fight": "PPV.EVENTS.Dummy.us",
    "American Football": "NFL.Dummy.us",
    "Afl": "AUS.Rules.Football.Dummy.us",
    "Football": "Soccer.Dummy.us",
    "Basketball": "Basketball.Dummy.us",
    "Hockey": "NHL.Hockey.Dummy.us",
    "Tennis": "Tennis.Dummy.us",
    "Darts": "Darts.Dummy.us"
}

# --- 3.2. StreamedSU: Yardımcı Fonksiyonlar ---
def get_matches_su(endpoint="all"):
    url = f"https://streamed.pk/api/matches/{endpoint}"
    try:
        print(f"📡 [StreamedSU] {endpoint} maçları API'den alınıyor...")
        response = requests.get(url, timeout=20)
        response.raise_for_status()
        print(f"✅ [StreamedSU] {endpoint} maçları başarıyla alındı.")
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"❌ [StreamedSU] {endpoint} maçları alınırken hata: {e}", file=sys.stderr)
        return []

def get_stream_embed_url_su(source):
    try:
        src_name = source.get('source')
        src_id = source.get('id')
        if not src_name or not src_id:
            return None
        api_url = f"https://streamed.pk/api/stream/{src_name}/{src_id}"
        response = requests.get(api_url, timeout=10)
        response.raise_for_status()
        streams = response.json()
        if streams and streams[0].get('embedUrl'):
            return streams[0]['embedUrl']
    except:
        pass
    return None

def find_m3u8_in_content_su(page_content):
    patterns = [
        r'source:\s*["\'](https?://[^\'"]+\.m3u8?[^\'"]*)["\']',
        r'file:\s*["\'](https?://[^\'"]+\.m3u8?[^\'"]*)["\']',
        r'hlsSource\s*=\s*["\'](https?://[^\'"]+\.m3u8?[^\'"]*)["\']',
        r'src\s*:\s*["\'](https?://[^\'"]+\.m3u8?[^\'"]*)["\']',
        r'["\'](https?://[^\'"]+\.m3u8?[^\'"]*)["\']'
    ]
    for pattern in patterns:
        match = re.search(pattern, page_content)
        if match:
            return match.group(1)
    return None

def extract_m3u8_from_embed_su(embed_url):
    if not embed_url:
        return None
    try:
        response = requests.get(embed_url, headers=CUSTOM_HEADERS_SU, timeout=15)
        response.raise_for_status()
        return find_m3u8_in_content_su(response.text)
    except:
        return None

def validate_logo_su(url, fallback):
    if not url:
        return fallback
    try:
        resp = requests.head(url, timeout=5)
        if resp.status_code == 200:
            return url
    except:
        pass
    return fallback

def build_logo_url_su(match):
    api_category = match.get('category') or ''
    logo_url = None

    teams = match.get('teams') or {}
    for team_key in ['away','home']:
        team = teams.get(team_key, {})
        badge = team.get('badge') or team.get('id')
        if badge:
            logo_url = f"https://streamed.pk/api/images/badge/{badge}.webp"
            break

    if not logo_url and match.get('poster'):
        poster = match['poster']
        logo_url = f"https://streamed.pk/api/images/proxy/{poster}.webp"

    for key in FALLBACK_LOGOS_SU:
        if key.lower() in api_category.lower():
            logo_url = validate_logo_su(logo_url, FALLBACK_LOGOS_SU[key])
            break

    return logo_url, api_category

def process_match_su(match):
    title = match.get('title','Untitled Match')
    sources = match.get('sources', [])
    for source in sources:
        embed_url = get_stream_embed_url_su(source)
        if embed_url:
            print(f"  🔎 [StreamedSU] Kontrol ediliyor '{title}': {embed_url}")
            m3u8 = extract_m3u8_from_embed_su(embed_url)
            if m3u8:
                return match, m3u8
    return match, None

# --- 3.3. StreamedSU: Ana Çalıştırıcı Fonksiyon ---
def fetch_streamedsu_streams():
    """StreamedSU sitesinden verileri çeker ve M3U satır listesi döndürür."""
    all_matches = get_matches_su("all")
    live_matches = get_matches_su("live")
    matches = all_matches + live_matches 

    if not matches:
        return ["#EXTM3U", "#EXTINF:-1,No Matches Found\n"]

    content = ["#EXTM3U"]
    success = 0

    vlc_header_lines = [
        f'#EXTVLCOPT:http-origin={CUSTOM_HEADERS_SU["Origin"]}',
        f'#EXTVLCOPT:http-referrer={CUSTOM_HEADERS_SU["Referer"]}',
        f'#EXTVLCOPT:user-agent={CUSTOM_HEADERS_SU["User-Agent"]}'
    ]

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(process_match_su, m): m for m in matches}
        for future in concurrent.futures.as_completed(futures):
            match, url = future.result()
            title = match.get('title','Untitled Match')
            if url:
                logo, cat = build_logo_url_su(match)
                display_cat = cat.replace('-', ' ').title() if cat else "General"
                tv_id = TV_IDS_SU.get(display_cat, "General.Dummy.us")

                # --- İSTENEN DEĞİŞİKLİK BURADA ---
                display_title = f"{title} (telegram @playtvmedya)"
                content.append(f'#EXTINF:-1 tvg-id="{tv_id}" tvg-name="{title}" tvg-logo="{logo}" group-title="StreamedSU - {display_cat}",{display_title}')
                content.extend(vlc_header_lines)
                content.append(url)
                success += 1
                print(f"  ✅ [StreamedSU] {title} eklendi.")

    print(f"🎉 [StreamedSU] {success} yayın bulundu.")
    return content

# ==============================================================================
# BÖLÜM 4: ANA ÇALIŞTIRICI VE BİRLEŞTİRİCİ
# ==============================================================================

async def main():
    print("--- KOMBİNE M3U OLUŞTURUCU BAŞLADI ---")
    
    # PPVLand'den gelen EPG başlığını ana başlık olarak kullanalım
    final_playlist_lines = ['#EXTM3U url-tvg="https://epgshare01.online/epgshare01/epg_ripper_DUMMY_CHANNELS.xml.gz"']

    # --- Tarayıcı 1: IstPlay (Senkron) ---
    print("\n[1/3] 🚀 IstPlay scraper çalıştırılıyor (Senkron)...")
    try:
        # Senkron fonksiyonu ayrı bir thread'de çalıştır
        istplay_lines = await asyncio.to_thread(fetch_istplay_streams)
        if istplay_lines and len(istplay_lines) > 1:
            # İlk satır ('#EXTM3U') hariç diğerlerini ekle
            final_playlist_lines.extend(istplay_lines[1:])
            print(f"✅ [IstPlay] {len(istplay_lines) - 1} satır eklendi.")
        else:
            print("⚠️ [IstPlay] Hiç yayın bulunamadı.")
    except Exception as e:
        print(f"❌ HATA (IstPlay): {e}")

    # --- Tarayıcı 2: StreamedSU (Senkron) ---
    print("\n[2/3] 🚀 StreamedSU scraper çalıştırılıyor (Senkron)...")
    try:
        # Senkron fonksiyonu ayrı bir thread'de çalıştır
        streamedsu_lines = await asyncio.to_thread(fetch_streamedsu_streams)
        if streamedsu_lines and len(streamedsu_lines) > 1:
            # İlk satır ('#EXTM3U') hariç diğerlerini ekle
            final_playlist_lines.extend(streamedsu_lines[1:])
            print(f"✅ [StreamedSU] {len(streamedsu_lines) - 1} satır eklendi.")
        else:
            print("⚠️ [StreamedSU] Hiç yayın bulunamadı.")
    except Exception as e:
        print(f"❌ HATA (StreamedSU): {e}")

    # --- Tarayıcı 3: PPVLand (Asenkron/Playwright) ---
    print("\n[3/3] 🚀 PPVLand scraper çalıştırılıyor (Asenkron/Playwright)...")
    try:
        ppvland_lines = await fetch_ppvland_streams()
        if ppvland_lines and len(ppvland_lines) > 1:
            # İlk satır (başlık) hariç diğerlerini ekle
            final_playlist_lines.extend(ppvland_lines[1:])
            print(f"✅ [PPVLand] {len(ppvland_lines) - 1} satır eklendi.")
        else:
            print("⚠️ [PPVLand] Hiç yayın bulunamadı.")
    except Exception as e:
        print(f"❌ HATA (PPVLand): {e}")

    # --- Final Yazma İşlemi ---
    output_filename = "PlayTV_Medya_Combined.m3u"
    print(f"\n💾 Tüm yayınlar '{output_filename}' dosyasına yazılıyor...")
    try:
        with open(output_filename, "w", encoding="utf-8") as f:
            f.write("\n".join(final_playlist_lines))
        print(f"🎉 Başarılı! Toplam {len(final_playlist_lines)} satır '{output_filename}' dosyasına yazıldı.")
    except IOError as e:
        print(f"❌ Dosyaya yazma hatası: {e}")

if __name__ == "__main__":
    # Windows'ta Playwright ve asyncio uyumluluğu için
    if platform.system() == 'Windows':
         asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
