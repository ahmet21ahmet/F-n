<?php
// --- Yapılandırma ve Kurulum ---

// Hata raporlamayı etkinleştir (Geliştirme sırasında faydalıdır)
ini_set('display_errors', 1);
error_reporting(E_ALL);

// Config dosyasını oku
$configFile = __DIR__ . '/final-config.json';
if (!file_exists($configFile)) {
    die("HATA: Yapılandırma dosyası bulunamadı: $configFile\n");
}

$config = json_decode(file_get_contents($configFile), true);

if (!$config || empty($config['mainUrl']) || empty($config['swKey'])) {
    die("HATA: Yapılandırma dosyası geçersiz veya eksik.\n");
}

// Değişkenleri yapılandırmadan al
$mainUrl = $config['mainUrl'];
$swKey = $config['swKey'];
$userAgent = $config['userAgent'] ?? 'Dart/3.7 (dart:io)';
$referer = $config['referer'] ?? 'https://www.google.com/';
$m3uUserAgent = 'googleusercontent'; // M3U çalarlar için özel User-Agent

echo "🎬 Ayrı M3U Listeleri Oluşturucu Başlatılıyor...\n";
echo "🔗 Ana API Adresi: $mainUrl\n\n";

// HTTP istekleri için stream context oluştur
$context = stream_context_create([
    'http' => [
        'method' => 'GET',
        'header' => "User-Agent: $userAgent\r\nReferer: $referer\r\n",
        'timeout' => 30, // Zaman aşımı süresini artırdık
        'ignore_errors' => true // Hatalı yanıtlarda bile içeriği al
    ],
    'ssl' => [
        'verify_peer' => false,
        'verify_peer_name' => false
    ]
]);

// Çıktı klasörünü belirle
$outputDir = __DIR__ . '/../'; // Ana dizine kaydet

// --- İçerik Çekme ve Dosya Oluşturma Fonksiyonları ---

/**
 * Belirtilen API URL'sinden veri çeker ve JSON olarak çözer.
 * @param string $apiUrl
 * @param resource $context
 * @return array|null
 */
function fetchData($apiUrl, $context) {
    $response = @file_get_contents($apiUrl, false, $context);
    if ($response === FALSE) {
        echo "   -> Hata: API'ye erişilemedi: $apiUrl\n";
        return null;
    }
    $data = json_decode($response, true);
    if (json_last_error() !== JSON_ERROR_NONE) {
        echo "   -> Hata: Geçersiz JSON yanıtı alındı.\n";
        return null;
    }
    return $data;
}

/**
 * M3U içeriğini dosyaya yazar.
 * @param string $filePath
 * @param string $content
 * @param int $itemCount
 */
function writeM3UFile($filePath, $content, $itemCount) {
    file_put_contents($filePath, $content);
    $fileSize = round(filesize($filePath) / 1024, 2); // KB cinsinden
    echo "💾 Dosya oluşturuldu: $filePath ($itemCount içerik, {$fileSize} KB)\n\n";
}


// --- 1. CANLI TV LİSTESİ OLUŞTURMA ---

echo "📺 Canlı TV Yayınları Alınıyor...\n";
$liveTvContent = "#EXTM3U\n";
$totalChannels = 0;
$maxPages = 15; // Taranacak maksimum sayfa sayısı

for ($page = 0; $page < $maxPages; $page++) {
    $apiUrl = "$mainUrl/api/channel/by/filtres/0/0/$page/$swKey";
    echo " -> Sayfa $page taranıyor...\n";
    
    $data = fetchData($apiUrl, $context);
    if (empty($data)) {
        echo "   -> Veri bulunamadı. Canlı TV işlemi tamamlandı.\n";
        break;
    }
    
    $pageChannels = 0;
    foreach ($data as $item) {
        if (isset($item['sources']) && is_array($item['sources'])) {
            foreach ($item['sources'] as $source) {
                if (($source['type'] ?? '') === 'm3u8' && !empty($source['url'])) {
                    $pageChannels++;
                    $title = $item['title'] ?? 'İsimsiz Kanal';
                    $image = $item['image'] ?? '';
                    $categories = isset($item['categories']) ? implode(", ", array_column($item['categories'], 'title')) : 'Genel';
                    
                    $liveTvContent .= "#EXTINF:-1 tvg-id=\"{$item['id']}\" tvg-name=\"$title\" tvg-logo=\"$image\" group-title=\"$categories\",$title\n";
                    $liveTvContent .= "#EXTVLCOPT:http-user-agent=$m3uUserAgent\n";
                    $liveTvContent .= "#EXTVLCOPT:http-referrer=$referer\n";
                    $liveTvContent .= "{$source['url']}\n";
                }
            }
        }
    }
    echo "   -> Bu sayfadan $pageChannels kanal eklendi.\n";
    $totalChannels += $pageChannels;
}
echo "✅ Canlı TV: Toplam $totalChannels kanal listeye eklendi.\n";
writeM3UFile($outputDir . 'canli-tv.m3u', $liveTvContent, $totalChannels);


// --- 2. FİLMLER LİSTESİ OLUŞTURMA ---

echo "🎬 Filmler Alınıyor...\n";
$moviesContent = "#EXTM3U\n";
$totalMovies = 0;
$movieCategories = [
    "0" => "Tüm Filmler", "14" => "Aile", "1" => "Aksiyon", "13" => "Animasyon",
    "19" => "Belgesel", "4" => "Bilim Kurgu", "2" => "Dram", "10" => "Fantastik",
    "3" => "Komedi", "8" => "Korku", "17" => "Macera", "5" => "Romantik"
];
$maxPagesPerCategory = 50; // Her kategori için maksimum sayfa

foreach ($movieCategories as $catId => $catName) {
    echo " -> Kategori: '$catName' taranıyor...\n";
    for ($page = 0; $page < $maxPagesPerCategory; $page++) {
        $apiUrl = "$mainUrl/api/movie/by/filtres/$catId/created/$page/$swKey";
        
        $data = fetchData($apiUrl, $context);
        if (empty($data)) {
            // Veri yoksa sonraki kategoriye geç
            break;
        }
        
        $pageMovies = 0;
        foreach ($data as $item) {
            if (isset($item['sources']) && is_array($item['sources'])) {
                foreach ($item['sources'] as $source) {
                    if (($source['type'] ?? '') === 'm3u8' && !empty($source['url'])) {
                        $pageMovies++;
                        $title = $item['title'] ?? 'İsimsiz Film';
                        $image = $item['image'] ?? '';
                        
                        $moviesContent .= "#EXTINF:-1 tvg-id=\"{$item['id']}\" tvg-name=\"$title\" tvg-logo=\"$image\" group-title=\"Film - $catName\",$title\n";
                        $moviesContent .= "#EXTVLCOPT:http-user-agent=$m3uUserAgent\n";
                        $moviesContent .= "#EXTVLCOPT:http-referrer=$referer\n";
                        $moviesContent .= "{$source['url']}\n";
                    }
                }
            }
        }
        $totalMovies += $pageMovies;
        
        if ($pageMovies === 0) {
            // Bu sayfada film yoksa döngüyü kırıp diğer kategoriye geç
            break; 
        }
        sleep(1); // API'yi yormamak için kısa bir bekleme
    }
}
echo "✅ Filmler: Toplam $totalMovies film listeye eklendi.\n";
writeM3UFile($outputDir . 'filmler.m3u', $moviesContent, $totalMovies);


// --- 3. DİZİLER LİSTESİ OLUŞTURMA ---

echo "📺 Diziler Alınıyor...\n";
$seriesContent = "#EXTM3U\n";
$totalSeries = 0;
$maxPages = 50; // Taranacak maksimum sayfa sayısı

for ($page = 0; $page < $maxPages; $page++) {
    $apiUrl = "$mainUrl/api/serie/by/filtres/0/created/$page/$swKey";
    echo " -> Sayfa $page taranıyor...\n";

    $data = fetchData($apiUrl, $context);
    if (empty($data)) {
        echo "   -> Veri bulunamadı. Dizi işlemi tamamlandı.\n";
        break;
    }
    
    $pageSeries = 0;
    foreach ($data as $item) {
        // Genellikle dizilerde bölümler ayrı bir API çağrısı ile gelir.
        // Bu betik, ana dizi linkini ekler.
        // Eğer `sources` anahtarı doğrudan dizi listesinde m3u8 içeriyorsa ekleyecektir.
        if (isset($item['sources']) && is_array($item['sources'])) {
            foreach ($item['sources'] as $source) {
                if (($source['type'] ?? '') === 'm3u8' && !empty($source['url'])) {
                     $pageSeries++;
                    $title = $item['title'] ?? 'İsimsiz Dizi';
                    $image = $item['image'] ?? '';
                    
                    $seriesContent .= "#EXTINF:-1 tvg-id=\"{$item['id']}\" tvg-name=\"$title\" tvg-logo=\"$image\" group-title=\"Diziler\",$title\n";
                    $seriesContent .= "#EXTVLCOPT:http-user-agent=$m3uUserAgent\n";
                    $seriesContent .= "#EXTVLCOPT:http-referrer=$referer\n";
                    $seriesContent .= "{$source['url']}\n";
                }
            }
        }
    }
    echo "   -> Bu sayfadan $pageSeries dizi eklendi.\n";
    $totalSeries += $pageSeries;
    
    if ($pageSeries === 0 && !empty($data)) {
        // Veri geldi ama kaynak (source) bulunamadı.
        // Bu normal bir durum olabilir, dizi bölümleri farklı bir mantıkla çalışıyorsa.
    }

    sleep(1); // API'yi yormamak için kısa bir bekleme
}
echo "✅ Diziler: Toplam $totalSeries dizi listeye eklendi.\n";
writeM3UFile($outputDir . 'diziler.m3u', $seriesContent, $totalSeries);


// --- BİTİŞ ---
$totalItems = $totalChannels + $totalMovies + $totalSeries;
echo "🎉 TÜM İŞLEMLER TAMAMLANDI!\n";
echo "========================================\n";
echo "📊 GENEL İSTATİSTİKLER:\n";
echo "----------------------------------------\n";
echo "📺 Canlı TV Kanalları: $totalChannels\n";
echo "🎬 Filmler: $totalMovies\n";
echo "📺 Diziler: $totalSeries\n";
echo "🏆 Toplam İçerik Sayısı: $totalItems\n";
echo "========================================\n";

?>