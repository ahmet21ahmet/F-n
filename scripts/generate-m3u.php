<?php
// Config dosyasını oku
$config = json_decode(file_get_contents(__DIR__ . '/final-config.json'), true);

if (!$config) {
    die("Config yüklenemedi!\n");
}

$mainUrl = $config['mainUrl'];
$swKey = $config['swKey'];
$userAgent = $config['userAgent'];
$referer = $config['referer'];
$m3uUserAgent = 'googleusercontent';

echo "🎬 M3U Oluşturucu Başlıyor...\n";
echo "🔗 API: $mainUrl\n";

// Context ayarları
$context = stream_context_create([
    'http' => [
        'method' => 'GET',
        'header' => "User-Agent: $userAgent\r\nReferer: $referer\r\n",
        'timeout' => 25,
        'ignore_errors' => true
    ],
    'ssl' => [
        'verify_peer' => false,
        'verify_peer_name' => false
    ]
]);

$m3uContent = "#EXTM3U\n";

// 📺 CANLI YAYINLAR
echo "📺 Canlı yayınlar alınıyor...\n";
$totalChannels = 0;

for ($page = 0; $page < 10; $page++) {
    $apiUrl = "$mainUrl/api/channel/by/filtres/0/0/$page/$swKey";
    echo "Sayfa $page: $apiUrl\n";
    
    $response = @file_get_contents($apiUrl, false, $context);
    
    if ($response === FALSE) {
        echo "Sayfa $page: API erişilemedi, sonraki sayfaya geçiliyor\n";
        continue;
    }
    
    $data = json_decode($response, true);
    if ($data === null || !is_array($data) || count($data) === 0) {
        echo "Sayfa $page: Veri yok, canlı yayınlar tamamlandı\n";
        break;
    }
    
    $pageChannels = 0;
    foreach ($data as $content) {
        if (isset($content['sources']) && is_array($content['sources'])) {
            foreach ($content['sources'] as $source) {
                if (($source['type'] ?? '') === 'm3u8' && !empty($source['url'])) {
                    $pageChannels++;
                    $totalChannels++;
                    $title = $content['title'] ?? 'Başlıksız';
                    $image = $content['image'] ?? '';
                    $categories = isset($content['categories']) ? implode(", ", array_column($content['categories'], 'title')) : 'Genel';
                    
                    $m3uContent .= "#EXTINF:-1 tvg-id=\"{$content['id']}\" tvg-name=\"$title\" tvg-logo=\"$image\" group-title=\"$categories\", $title\n";
                    $m3uContent .= "#EXTVLCOPT:http-user-agent=$m3uUserAgent\n";
                    $m3uContent .= "#EXTVLCOPT:http-referrer=$referer\n";
                    $m3uContent .= "{$source['url']}\n";
                }
            }
        }
    }
    echo "Sayfa $page: $pageChannels kanal eklendi\n";
    
    // Son sayfada veri yoksa döngüyü kır
    if ($pageChannels === 0) {
        break;
    }
}
echo "✅ Canlı: $totalChannels kanal\n";

// 🎬 FİLMLER - TÜM KATEGORİLER ve TÜM SAYFALAR
echo "🎬 Filmler alınıyor (tüm kategoriler ve sayfalar)...\n";
$movieCategories = [
    "0" => "Son Filmler", "14" => "Aile", "1" => "Aksiyon", "13" => "Animasyon",
    "19" => "Belgesel", "4" => "Bilim Kurgu", "2" => "Dram", "10" => "Fantastik",
    "3" => "Komedi", "8" => "Korku", "17" => "Macera", "5" => "Romantik"
];

$totalMovies = 0;
foreach ($movieCategories as $categoryId => $categoryName) {
    echo "🎥 Kategori: $categoryName\n";
    $categoryMovies = 0;
    
    for ($page = 0; $page < 100; $page++) { // Yüksek limit, veri gelmeyince kırılacak
        $apiUrl = "$mainUrl/api/movie/by/filtres/$categoryId/created/$page/$swKey";
        
        $response = @file_get_contents($apiUrl, false, $context);
        
        if ($response === FALSE) {
            echo "  Sayfa $page: API erişilemedi, sonraki sayfaya geçiliyor\n";
            continue;
        }
        
        $data = json_decode($response, true);
        if ($data === null || !is_array($data) || count($data) === 0) {
            echo "  Sayfa $page: Veri yok, kategori tamamlandı\n";
            break;
        }
        
        $pageMovies = 0;
        foreach ($data as $content) {
            if (isset($content['sources']) && is_array($content['sources'])) {
                foreach ($content['sources'] as $source) {
                    if (($source['type'] ?? '') === 'm3u8' && !empty($source['url'])) {
                        $pageMovies++;
                        $categoryMovies++;
                        $totalMovies++;
                        $title = $content['title'] ?? 'Başlıksız Film';
                        $image = $content['image'] ?? '';
                        
                        $m3uContent .= "#EXTINF:-1 tvg-id=\"{$content['id']}\" tvg-name=\"$title\" tvg-logo=\"$image\" group-title=\"Film-$categoryName\", $title\n";
                        $m3uContent .= "#EXTVLCOPT:http-user-agent=$m3uUserAgent\n";
                        $m3uContent .= "#EXTVLCOPT:http-referrer=$referer\n";
                        $m3uContent .= "{$source['url']}\n";
                    }
                }
            }
        }
        echo "  Sayfa $page: $pageMovies film eklendi\n";
        
        // Sayfada film yoksa bir sonraki kategoriye geç
        if ($pageMovies === 0) {
            break;
        }
        
        // Her sayfa arasında küçük bekleme
        sleep(1);
    }
    echo "  ✅ $categoryName: $categoryMovies film\n";
}
echo "✅ Toplam Filmler: $totalMovies film\n";

// 📺 DİZİLER - TÜM SAYFALAR
echo "📺 Diziler alınıyor (tüm sayfalar)...\n";
$totalSeries = 0;

for ($page = 0; $page < 100; $page++) { // Yüksek limit, veri gelmeyince kırılacak
    $apiUrl = "$mainUrl/api/serie/by/filtres/0/created/$page/$swKey";
    echo "Dizi Sayfa $page\n";
    
    $response = @file_get_contents($apiUrl, false, $context);
    
    if ($response === FALSE) {
        echo "  Sayfa $page: API erişilemedi, sonraki sayfaya geçiliyor\n";
        continue;
    }
    
    $data = json_decode($response, true);
    if ($data === null || !is_array($data) || count($data) === 0) {
        echo "  Sayfa $page: Veri yok, diziler tamamlandı\n";
        break;
    }
    
    $pageSeries = 0;
    foreach ($data as $content) {
        if (isset($content['sources']) && is_array($content['sources'])) {
            foreach ($content['sources'] as $source) {
                if (($source['type'] ?? '') === 'm3u8' && !empty($source['url'])) {
                    $pageSeries++;
                    $totalSeries++;
                    $title = $content['title'] ?? 'Başlıksız Dizi';
                    $image = $content['image'] ?? '';
                    
                    $m3uContent .= "#EXTINF:-1 tvg-id=\"{$content['id']}\" tvg-name=\"$title\" tvg-logo=\"$image\" group-title=\"Diziler\", $title\n";
                    $m3uContent .= "#EXTVLCOPT:http-user-agent=$m3uUserAgent\n";
                    $m3uContent .= "#EXTVLCOPT:http-referrer=$referer\n";
                    $m3uContent .= "{$source['url']}\n";
                }
            }
        }
    }
    echo "  Sayfa $page: $pageSeries dizi eklendi\n";
    
    // Sayfada dizi yoksa döngüyü kır
    if ($pageSeries === 0) {
        break;
    }
    
    // Her sayfa arasında küçük bekleme
    sleep(1);
}
echo "✅ Diziler: $totalSeries dizi\n";

// 💾 Dosyaya yaz (KÖK DİZİNE)
$outputFile = __DIR__ . '/../rectv-playlist.m3u';
file_put_contents($outputFile, $m3uContent);

$totalItems = $totalChannels + $totalMovies + $totalSeries;
echo "🎉 İŞLEM TAMAMLANDI!\n";
echo "📊 Toplam: $totalItems içerik\n";
echo "💾 Dosya: $outputFile\n";
echo "📏 Boyut: " . round(filesize($outputFile) / 1024 / 1024, 2) . " MB\n";

// İstatistikleri göster
echo "\n📈 İSTATİSTİKLER:\n";
echo "📺 Canlı Yayınlar: $totalChannels\n";
echo "🎬 Filmler: $totalMovies\n";
echo "📺 Diziler: $totalSeries\n";
echo "🏆 Toplam: $totalItems\n";
?>
