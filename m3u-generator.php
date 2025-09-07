<?php
// Varsayılanlar (fallback - SADECE BAŞARISIZLIK DURUMUNDA)
$defaultMainUrl = 'https://m.prectv55.lol';
$defaultSwKey = '4F5A9C3D9A86FA54EACEDDD635185/c3c5bd17-e37b-4b94-a944-8a3688a30452/';
$defaultUserAgent = 'okhttp/4.12.0/';
$defaultReferer = 'https://twitter.com/';
$pageCount = 4;

// M3U çıktısı için sabit User-Agent
$m3uUserAgent = 'googleusercontent';

// YENİ Github kaynak dosyası
$sourceUrlRaw = 'https://raw.githubusercontent.com/nikyokki/nik-cloudstream/refs/heads/master/RecTV/src/main/kotlin/com/keyiflerolsun/RecTV.kt';
$proxyUrl = 'https://api.codetabs.com/v1/proxy/?quest=' . urlencode($sourceUrlRaw);

// 1. ADIM: Github'dan header bilgilerini çek
function fetchGithubContent($sourceUrlRaw, $proxyUrl) {
    $context = stream_context_create([
        'http' => [
            'method' => 'GET',
            'header' => "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36\r\n",
            'timeout' => 10
        ],
        'ssl' => [
            'verify_peer' => false,
            'verify_peer_name' => false
        ]
    ]);

    $githubContent = @file_get_contents($sourceUrlRaw, false, $context);
    if ($githubContent !== FALSE) return $githubContent;

    $githubContentProxy = @file_get_contents($proxyUrl, false, $context);
    if ($githubContentProxy !== FALSE) return $githubContentProxy;

    return FALSE;
}

function parseGithubHeaders($githubContent) {
    $headers = [
        'mainUrl' => null,
        'swKey' => null,
        'userAgent' => null,
        'referer' => null
    ];

    // mainUrl - Kotlin syntax'ına uygun regex
    if (preg_match('/override\s+var\s+mainUrl\s*=\s*"([^"]+)"/', $githubContent, $match)) {
        $headers['mainUrl'] = $match[1];
        echo "Github'dan mainUrl alındı: " . $headers['mainUrl'] . "\n";
    }

    // swKey - Kotlin syntax'ına uygun regex
    if (preg_match('/private\s+(val|var)\s+swKey\s*=\s*"([^"]+)"/', $githubContent, $match)) {
        $headers['swKey'] = $match[2];
        echo "Github'dan swKey alındı: " . $headers['swKey'] . "\n";
    }

    // user-agent - headers mapOf içinde
    if (preg_match('/headers\s*=\s*mapOf\([^)]*"user-agent"[^)]*to[^"]*"([^"]+)"/s', $githubContent, $match)) {
        $headers['userAgent'] = $match[1];
        echo "Github'dan userAgent alındı: " . $headers['userAgent'] . "\n";
    }

    // referer - iki farklı şekilde arıyoruz
    if (preg_match('/this\.referer\s*=\s*"([^"]+)"/', $githubContent, $match)) {
        $headers['referer'] = $match[1];
        echo "Github'dan referer alındı (this.referer): " . $headers['referer'] . "\n";
    } 
    else if (preg_match('/referer\s*=\s*"([^"]+)"/', $githubContent, $match)) {
        $headers['referer'] = $match[1];
        echo "Github'dan referer alındı (referer): " . $headers['referer'] . "\n";
    }
    // headers mapOf içinde referer
    else if (preg_match('/headers\s*=\s*mapOf\([^)]*"Referer"[^)]*to[^"]*"([^"]+)"/s', $githubContent, $match)) {
        $headers['referer'] = $match[1];
        echo "Github'dan referer alındı (headers): " . $headers['referer'] . "\n";
    }

    return $headers;
}

// 2. ADIM: API test fonksiyonu
function testApiWithHeaders($mainUrl, $swKey, $userAgent, $referer) {
    $testUrl = $mainUrl . '/api/channel/by/filtres/0/0/0/' . $swKey;
    echo "API test URL: $testUrl\n";
    echo "Test Header - User-Agent: $userAgent\n";
    echo "Test Header - Referer: $referer\n";

    $opts = [
        'http' => [
            'method' => 'GET',
            'header' => "User-Agent: $userAgent\r\nReferer: $referer\r\n",
            'timeout' => 15,
            'ignore_errors' => true
        ],
        'ssl' => [
            'verify_peer' => false,
            'verify_peer_name' => false
        ]
    ];

    $ctx = stream_context_create($opts);
    $response = @file_get_contents($testUrl, false, $ctx);

    if ($response === FALSE) {
        echo "✗ API testi BAŞARISIZ - Cevap alınamadı\n";
        return false;
    }

    $data = json_decode($response, true);
    $success = $data !== null && is_array($data);

    if ($success) {
        echo "✓ API testi BAŞARILI - " . count($data) . " kanal bulundu\n";
    } else {
        echo "✗ API testi BAŞARISIZ - Geçersiz JSON\n";
    }

    return $success;
}

// 3. ADIM: İLK ÖNCE GITHUB'DAN DEĞERLERİ AL VE TEST ET
echo "=== GITHUB HEADER TESTİ ===\n";
$githubContent = fetchGithubContent($sourceUrlRaw, $proxyUrl);

if ($githubContent !== FALSE) {
    echo "✓ Github içeriği başarıyla alındı\n";

    $githubHeaders = parseGithubHeaders($githubContent);

    // Github'dan gelen değerlerin hepsi var mı kontrol et
    if ($githubHeaders['mainUrl'] && $githubHeaders['swKey'] && 
        $githubHeaders['userAgent'] && $githubHeaders['referer']) {

        echo "\n=== API TESTİ (GITHUB HEADER'LARI İLE) ===\n";

        // İLK ETAP: SADECE Github header'ları ile API testi yap
        $apiTestResult = testApiWithHeaders(
            $githubHeaders['mainUrl'], 
            $githubHeaders['swKey'], 
            $githubHeaders['userAgent'], 
            $githubHeaders['referer']
        );

        if ($apiTestResult) {
            echo "\n✓ İLK ETAP BAŞARILI - Github header'ları kullanılacak\n";
            $mainUrl = $githubHeaders['mainUrl'];
            $swKey = $githubHeaders['swKey'];
            $userAgent = $githubHeaders['userAgent'];
            $referer = $githubHeaders['referer'];
            $source = "GITHUB";
        } else {
            echo "\n✗ İLK ETAP BAŞARISIZ - Varsayılan değerlerle test yapılıyor...\n";

            // İkinci etap: Varsayılan değerlerle test
            $defaultTestResult = testApiWithHeaders(
                $defaultMainUrl,
                $defaultSwKey,
                $defaultUserAgent,
                $defaultReferer
            );

            if ($defaultTestResult) {
                echo "\n✓ İKİNCİ ETAP BAŞARILI - Varsayılan değerler kullanılacak\n";
                $mainUrl = $defaultMainUrl;
                $swKey = $defaultSwKey;
                $userAgent = $defaultUserAgent;
                $referer = $defaultReferer;
                $source = "VARSayILAN";
            } else {
                echo "\n✗ TÜM TESTLER BAŞARISIZ - Son çare varsayılan değerler kullanılacak\n";
                $mainUrl = $defaultMainUrl;
                $swKey = $defaultSwKey;
                $userAgent = $defaultUserAgent;
                $referer = $defaultReferer;
                $source = "VARSayILAN (ZORUNLU)";
            }
        }
    } else {
        echo "✗ Github'dan eksik header bilgileri! Varsayılan değerler kullanılıyor.\n";
        $mainUrl = $defaultMainUrl;
        $swKey = $defaultSwKey;
        $userAgent = $defaultUserAgent;
        $referer = $defaultReferer;
        $source = "VARSayILAN";
    }
} else {
    echo "✗ Github içeriği alınamadı! Varsayılan değerler kullanılıyor.\n";
    $mainUrl = $defaultMainUrl;
    $swKey = $defaultSwKey;
    $userAgent = $defaultUserAgent;
    $referer = $defaultReferer;
    $source = "VARSayILAN";
}

// 4. ADIM: SONUÇLARI GÖSTER
echo "\n=== SON KULLANILAN DEĞERLER ===\n";
echo "Kaynak: $source\n";
echo "Main URL: $mainUrl\n";
echo "SwKey: $swKey\n";
echo "User-Agent: $userAgent\n";
echo "Referer: $referer\n";
echo "M3U User-Agent: $m3uUserAgent\n";

// 5. ADIM: API İSTEKLERİNİ SEÇİLEN HEADER'LAR İLE YAP
echo "\n=== M3U OLUŞTURULUYOR ===\n";
$m3uContent = "#EXTM3U\n";

$options = [
    'http' => [
        'method' => 'GET',
        'header' => "User-Agent: $userAgent\r\nReferer: $referer\r\n",
        'timeout' => 30,
        'ignore_errors' => true
    ],
    'ssl' => [
        'verify_peer' => false,
        'verify_peer_name' => false
    ]
];
$context = stream_context_create($options);

// CANLI YAYINLAR
echo "Canlı yayınlar alınıyor...\n";
for ($page = 0; $page < $pageCount; $page++) {
    $apiUrl = $mainUrl . "/api/channel/by/filtres/0/0/$page/" . $swKey;
    $response = @file_get_contents($apiUrl, false, $context);

    if ($response === FALSE) {
        echo "API hatası: $apiUrl\n";
        continue;
    }

    $data = json_decode($response, true);
    if ($data === null || !is_array($data)) {
        echo "JSON decode hatası: $apiUrl\n";
        continue;
    }

    $channelCount = 0;
    foreach ($data as $content) {
        if (isset($content['sources']) && is_array($content['sources'])) {
            foreach ($content['sources'] as $source) {
                if (($source['type'] ?? '') === 'm3u8' && isset($source['url'])) {
                    $channelCount++;
                    $title = $content['title'] ?? '';
                    $image = isset($content['image']) ? (
                        (strpos($content['image'], 'http') === 0) ? $content['image'] : $mainUrl . '/' . ltrim($content['image'], '/')
                    ) : '';
                    $categories = isset($content['categories']) && is_array($content['categories'])
                        ? implode(", ", array_column($content['categories'], 'title'))
                        : '';

                    $m3uContent .= "#EXTINF:-1 tvg-id=\"{$content['id']}\" tvg-name=\"$title\" tvg-logo=\"$image\" group-title=\"$categories\", $title\n";
                    $m3uContent .= "#EXTVLCOPT:http-user-agent=$m3uUserAgent\n";
                    $m3uContent .= "#EXTVLCOPT:http-referrer=$referer\n";
                    $m3uContent .= "{$source['url']}\n";
                }
            }
        }
    }
    echo "Sayfa $page: $channelCount kanal eklendi\n";
}

// FİLMLER
echo "Filmler alınıyor...\n";
$movieApis = [
    "api/movie/by/filtres/0/created/SAYFA/$swKey"   => "Son Filmler",
    "api/movie/by/filtres/14/created/SAYFA/$swKey"  => "Aile",
    "api/movie/by/filtres/1/created/SAYFA/$swKey"   => "Aksiyon",
    "api/movie/by/filtres/13/created/SAYFA/$swKey"  => "Animasyon",
    "api/movie/by/filtres/19/created/SAYFA/$swKey"  => "Belgesel Filmleri",
    "api/movie/by/filtres/4/created/SAYFA/$swKey"   => "Bilim Kurgu",
    "api/movie/by/filtres/2/created/SAYFA/$swKey"   => "Dram",
    "api/movie/by/filtres/10/created/SAYFA/$swKey"  => "Fantastik",
    "api/movie/by/filtres/3/created/SAYFA/$swKey"   => "Komedi",
    "api/movie/by/filtres/8/created/SAYFA/$swKey"   => "Korku",
    "api/movie/by/filtres/17/created/SAYFA/$swKey"  => "Macera",
    "api/movie/by/filtres/5/created/SAYFA/$swKey"   => "Romantik",
];

foreach ($movieApis as $movieApi => $categoryName) {
    $totalMovies = 0;
    for ($page = 0; $page <= 25; $page++) {
        $apiUrl = $mainUrl . '/' . str_replace('SAYFA', $page, $movieApi);
        $response = @file_get_contents($apiUrl, false, $context);

        if ($response === FALSE) {
            break;
        }

        $data = json_decode($response, true);
        if ($data === null) {
            break;
        }

        $movieCount = 0;
        foreach ($data as $content) {
            if (isset($content['sources']) && is_array($content['sources'])) {
                foreach ($content['sources'] as $source) {
                    if (($source['type'] ?? '') === 'm3u8' && isset($source['url'])) {
                        $movieCount++;
                        $totalMovies++;
                        $title = $content['title'] ?? '';
                        $image = isset($content['image']) ? (
                            (strpos($content['image'], 'http') === 0) ? $content['image'] : $mainUrl . '/' . ltrim($content['image'], '/')
                        ) : '';
                        $m3uContent .= "#EXTINF:-1 tvg-id=\"{$content['id']}\" tvg-name=\"$title\" tvg-logo=\"$image\" group-title=\"$categoryName\", $title\n";
                        $m3uContent .= "#EXTVLCOPT:http-user-agent=$m3uUserAgent\n";
                        $m3uContent .= "#EXTVLCOPT:http-referrer=$referer\n";
                        $m3uContent .= "{$source['url']}\n";
                    }
                }
            }
        }
        if ($movieCount == 0) break;
    }
    echo "$categoryName: $totalMovies film eklendi\n";
}

// DİZİLER
echo "Diziler alınıyor...\n";
$seriesApis = [
    "api/serie/by/filtres/0/created/SAYFA/$swKey" => "Son Diziler"
];

foreach ($seriesApis as $seriesApi => $categoryName) {
    $totalSeries = 0;
    for ($page = 0; $page <= 25; $page++) {
        $apiUrl = $mainUrl . '/' . str_replace('SAYFA', $page, $seriesApi);
        $response = @file_get_contents($apiUrl, false, $context);

        if ($response === FALSE) {
            break;
        }

        $data = json_decode($response, true);
        if ($data === null) {
            break;
        }

        $seriesCount = 0;
        foreach ($data as $content) {
            if (isset($content['sources']) && is_array($content['sources'])) {
                foreach ($content['sources'] as $source) {
                    if (($source['type'] ?? '') === 'm3u8' && isset($source['url'])) {
                        $seriesCount++;
                        $totalSeries++;
                        $title = $content['title'] ?? '';
                        $image = isset($content['image']) ? (
                            (strpos($content['image'], 'http') === 0) ? $content['image'] : $mainUrl . '/' . ltrim($content['image'], '/')
                        ) : '';
                        $m3uContent .= "#EXTINF:-1 tvg-id=\"{$content['id']}\" tvg-name=\"$title\" tvg-logo=\"$image\" group-title=\"$categoryName\", $title\n";
                        $m3uContent .= "#EXTVLCOPT:http-user-agent=$m3uUserAgent\n";
                        $m3uContent .= "#EXTVLCOPT:http-referrer=$referer\n";
                        $m3uContent .= "{$source['url']}\n";
                    }
                }
            }
        }
        if ($seriesCount == 0) break;
    }
    echo "$categoryName: $totalSeries dizi eklendi\n";
}

// Dosyaya kaydet
file_put_contents('output.m3u', $m3uContent);

echo "\nOluşturulan M3U dosyası: output.m3u\n";
echo "İşlem tamamlandı!\n";
?>