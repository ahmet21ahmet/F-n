<?php
// Hata raporlamayı etkinleştir ve betik zaman aşımını kaldır
ini_set('display_errors', 1);
error_reporting(E_ALL);
set_time_limit(0);

// Config dosyasını kendi klasöründen oku (__DIR__)
$configFile = __DIR__ . '/final-config.json';
if (!file_exists($configFile)) {
    die("HATA: Yapılandırma dosyası bulunamadı: $configFile\n");
}
$config = json_decode(file_get_contents($configFile), true);

if (!$config || empty($config['mainUrl']) || empty($config['swKey'])) {
    die("HATA: Yapılandırma dosyası geçersiz veya eksik.\n");
}

$mainUrl = $config['mainUrl'];
$swKey = $config['swKey'];
$userAgent = $config['userAgent'] ?? 'Dart/3.7 (dart:io)';
$referer = $config['referer'] ?? 'https://www.google.com/';
$m3uUserAgent = 'googleusercontent';

echo "🎬 M3U Oluşturucu Başlatılıyor...\n";

// --- DEĞİŞİKLİK: Çıktı klasörü güncellendi ---
// __DIR__ betiğin kendi klasörünü (/scripts) verir.
// Dosyalar artık doğrudan 'scripts' klasörüne kaydedilecek.
$outputDir = __DIR__ . '/';
echo "ℹ️ M3U dosyaları şu konuma kaydedilecek: $outputDir\n\n";

// HTTP context
$context = stream_context_create([
    'http' => [ 'method' => 'GET', 'header' => "User-Agent: $userAgent\r\nReferer: $referer\r\n", 'timeout' => 45, 'ignore_errors' => true ],
    'ssl' => [ 'verify_peer' => false, 'verify_peer_name' => false ]
]);


function fetchData($apiUrl, $context) {
    echo "   -> İstek gönderiliyor: $apiUrl\n";
    $response = @file_get_contents($apiUrl, false, $context);
    if ($response === FALSE) { echo "   -> Hata: API'ye erişilemedi.\n"; return null; }
    $data = json_decode($response, true);
    if (json_last_error() !== JSON_ERROR_NONE) { echo "   -> Hata: Geçersiz JSON yanıtı.\n"; return null; }
    return $data;
}

function writeM3UFile($filePath, $content, $itemCount, $categoryName) {
    if ($itemCount > 0) {
        file_put_contents($filePath, $content);
        if (file_exists($filePath)) {
            $fileSize = round(filesize($filePath) / 1024, 2);
            echo "✅ $categoryName: Toplam $itemCount içerik eklendi.\n";
            echo "💾 Dosya oluşturuldu: $filePath ({$fileSize} KB)\n\n";
        } else {
            echo "❌ HATA: $categoryName dosyası oluşturulamadı!\n\n";
        }
    } else {
        echo "⚠️ $categoryName: İçerik bulunamadı, dosya oluşturulmadı.\n\n";
    }
}

// --- Canlı TV, Film ve Dizi çekme kodları ---

// CANLI TV
echo "--- BÖLÜM 1: CANLI TV YAYINLARI ---\n";
$liveTvContent = "#EXTM3U\n";
$totalChannels = 0;
for ($page = 0; $page < 15; $page++) {
    $apiUrl = "$mainUrl/api/channel/by/filtres/0/0/$page/$swKey";
    $data = fetchData($apiUrl, $context);
    if (empty($data)) { break; }
    foreach ($data as $item) {
        if (!empty($item['sources']) && is_array($item['sources'])) {
            foreach ($item['sources'] as $source) {
                if (($source['type'] ?? '') === 'm3u8' && !empty($source['url'])) {
                    $totalChannels++;
                    $title = $item['title'] ?? 'İsimsiz Kanal'; $image = $item['image'] ?? ''; $categories = isset($item['categories']) ? implode(", ", array_column($item['categories'], 'title')) : 'Genel';
                    $liveTvContent .= "#EXTINF:-1 tvg-id=\"{$item['id']}\" tvg-name=\"$title\" tvg-logo=\"$image\" group-title=\"$categories\",$title\n";
                    $liveTvContent .= "#EXTVLCOPT:http-user-agent=$m3uUserAgent\n#EXTVLCOPT:http-referrer=$referer\n{$source['url']}\n";
                }
            }
        }
    }
}
writeM3UFile($outputDir . 'canli-tv.m3u', $liveTvContent, $totalChannels, "Canlı TV");

// FİLMLER
echo "--- BÖLÜM 2: FİLMLER ---\n";
$moviesContent = "#EXTM3U\n";
$totalMovies = 0;
$movieCategories = [ "0" => "Son Eklenenler", "1" => "Aksiyon", "17" => "Macera", "4" => "Bilim Kurgu", "8" => "Korku", "2" => "Dram" ];
foreach ($movieCategories as $catId => $catName) {
    for ($page = 0; $page < 50; $page++) {
        $apiUrl = "$mainUrl/api/movie/by/filtres/$catId/created/$page/$swKey";
        $data = fetchData($apiUrl, $context);
        if (empty($data)) { break; }
        $pageMovies = 0;
        foreach ($data as $item) {
            if (!empty($item['sources']) && is_array($item['sources'])) {
                foreach ($item['sources'] as $source) {
                    if (($source['type'] ?? '') === 'm3u8' && !empty($source['url'])) {
                        $totalMovies++; $pageMovies++; $title = $item['title'] ?? 'İsimsiz Film'; $image = $item['image'] ?? '';
                        $moviesContent .= "#EXTINF:-1 tvg-id=\"{$item['id']}\" tvg-name=\"$title\" tvg-logo=\"$image\" group-title=\"Film - $catName\",$title\n";
                        $moviesContent .= "#EXTVLCOPT:http-user-agent=$m3uUserAgent\n#EXTVLCOPT:http-referrer=$referer\n{$source['url']}\n";
                    }
                }
            }
        }
        if ($pageMovies === 0) { break; }
        sleep(1);
    }
}
writeM3UFile($outputDir . 'filmler.m3u', $moviesContent, $totalMovies, "Filmler");

// DİZİLER
echo "--- BÖLÜM 3: DİZİLER ---\n";
$seriesContent = "#EXTM3U\n";
$totalEpisodes = 0;
for ($page = 0; $page < 50; $page++) {
    $seriesListApiUrl = "$mainUrl/api/serie/by/filtres/0/created/$page/$swKey";
    $seriesList = fetchData($seriesListApiUrl, $context);
    if (empty($seriesList)) { break; }
    foreach ($seriesList as $series) {
        $seriesId = $series['id'] ?? null; if (!$seriesId) continue;
        $seriesTitle = $series['title'] ?? 'İsimsiz Dizi';
        $seasonsApiUrl = "$mainUrl/api/season/by/serie/$seriesId/$swKey";
        $seasonsData = fetchData($seasonsApiUrl, $context);
        if (empty($seasonsData)) { continue; }
        foreach ($seasonsData as $season) {
            if (empty($season['episodes']) || !is_array($season['episodes'])) continue;
            foreach ($season['episodes'] as $episode) {
                if (empty($episode['sources']) || !is_array($episode['sources'])) continue;
                foreach ($episode['sources'] as $source) {
                    if (($source['type'] ?? '') === 'm3u8' && !empty($source['url'])) {
                        $totalEpisodes++; $seasonTitle = $season['title'] ?? 'Sezon'; $episodeTitle = $episode['title'] ?? 'Bölüm';
                        $fullTitle = "$seriesTitle - $seasonTitle - $episodeTitle";
                        $seriesContent .= "#EXTINF:-1 tvg-id=\"{$episode['id']}\" tvg-name=\"$fullTitle\" tvg-logo=\"{$series['image']}\" group-title=\"$seriesTitle\",$fullTitle\n";
                        $seriesContent .= "#EXTVLCOPT:http-user-agent=$m3uUserAgent\n#EXTVLCOPT:http-referrer=$referer\n{$source['url']}\n";
                    }
                }
            }
        }
        sleep(1);
    }
}
writeM3UFile($outputDir . 'diziler.m3u', $seriesContent, $totalEpisodes, "Dizi Bölümleri");

echo "🎉 TÜM İŞLEMLER TAMAMLANDI!\n";
?>