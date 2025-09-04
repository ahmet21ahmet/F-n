import json
import os

# Girdi ve çıktı dosya adları
INPUT_JSON_FILE = 'filmmodu_links.json'
OUTPUT_DUBBED_M3U = 'turkce_dublaj.m3u'
OUTPUT_SUBTITLED_M3U = 'turkce_altyazi.m3u'

def create_m3u_playlists():
    """
    JSON dosyasını okur ve Türkçe Dublaj / Türkçe Altyazı için
    ayrı ayrı .m3u formatında playlistler oluşturur.
    """
    # Girdi JSON dosyasının var olup olmadığını kontrol et
    if not os.path.exists(INPUT_JSON_FILE):
        print(f"Hata: '{INPUT_JSON_FILE}' dosyası bulunamadı. Lütfen önce film_scraper.py betiğini çalıştırın.")
        return

    # JSON dosyasını oku
    with open(INPUT_JSON_FILE, 'r', encoding='utf-8') as f:
        movies_data = json.load(f)

    print(f"Toplam {len(movies_data)} film verisi okundu. M3U dosyaları oluşturuluyor...")

    # Playlist içeriklerini tutacak listeler
    dubbed_playlist = ['#EXTM3U']
    subtitled_playlist = ['#EXTM3U']

    # Her film için M3U girdilerini oluştur
    for movie in movies_data:
        title = movie.get('title', 'Bilinmeyen Film')
        imdb_id = movie.get('imdb_id', '')
        
        # IPTV oynatıcıları için standart formatta EXTINF bilgisi
        extinf_line = f'#EXTINF:-1 tvg-id="{imdb_id}" tvg-name="{title}",{title}'

        # Türkçe Dublaj linki varsa playliste ekle
        dubbed_url = movie.get('dubbed_m3u8')
        if dubbed_url:
            dubbed_playlist.append(extinf_line)
            dubbed_playlist.append(dubbed_url)

        # Türkçe Altyazı linki varsa playliste ekle
        subtitled_url = movie.get('subtitled_m3u8')
        if subtitled_url:
            subtitled_playlist.append(extinf_line)
            subtitled_playlist.append(subtitled_url)
    
    # Türkçe Dublaj M3U dosyasını yaz
    with open(OUTPUT_DUBBED_M3U, 'w', encoding='utf-8') as f:
        f.write('\n'.join(dubbed_playlist))
    print(f"-> '{OUTPUT_DUBBED_M3U}' dosyası {len(dubbed_playlist) // 2} içerik ile oluşturuldu.")

    # Türkçe Altyazı M3U dosyasını yaz
    with open(OUTPUT_SUBTITLED_M3U, 'w', encoding='utf-8') as f:
        f.write('\n'.join(subtitled_playlist))
    print(f"-> '{OUTPUT_SUBTITLED_M3U}' dosyası {len(subtitled_playlist) // 2} içerik ile oluşturuldu.")


if __name__ == "__main__":
    create_m3u_playlists()