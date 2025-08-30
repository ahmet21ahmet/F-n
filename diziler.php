<?php
// Bu betik, birden çok yedek API URL'sini test ederek çalışacak şekilde tasarlanmıştır.

// --- BAŞLANGIÇ: Ortak Ayarlar ---
// YENİ: Yedek URL listesi. En yeni veya en olası olanı en başa yazmak iyi bir pratiktir.
$fallbackBaseUrls = [
    'https://m.prectv52.lol',
    'https://m.prectv52.sbs',
    'https://m.prectv51.sbs',
    'https://m.prectv50.sbs',
    'https://m.prectv49.sbs' 
];
$defaultSuffix = '4F5A9C3D9A86FA54EACEDDD635185/c3c5bd17-e37b-4b94-a944-8a3688a30452/';
$defaultUserAgent = 'Dart/3.7 (dart:io)';
$defaultReferer = 'https://twitter.com/';

// Github kaynak dosyası (en güncel veriler için ilk tercih)
$sourceUrlRaw = 'https://raw.githubusercontent.com/kerimmkirac/cs-kerim2/main/RecTV/src/main/kotlin/com/kerimmkirac/RecTV.kt';
$proxyUrl = 'https://api.codetabs.com/v1/proxy/?quest=' . urlencode($sourceUrlRaw);

// Değişkenler
$suffix = $defaultSuffix;
$userAgent = $defaultUserAgent;
$referer = $defaultReferer;
$activeBaseUrl = ''; // YENİ: Çalışan URL bu değişkende saklanacak.

function fetchGithubContent($sourceUrlRaw, $proxyUrl) {
    $contextOptions = ['http' => ['timeout' => 7]];
    $context = stream_context_create($contextOptions);
    $githubContent = @file_get_contents($sourceUrlRaw, false, $context);
    if ($githubContent !== FALSE) return $githubContent;
    return @file_get_contents($proxyUrl, false, $context);
}

function isApiWorking($baseUrl, $suffix, $userAgent) {
    $testUrl = $baseUrl . '/api/channel/by/filtres/0/0/0/' . $suffix;
    $opts = ['http' => ['header' => "User-Agent: $userAgent\r\n", 'timeout' => 5]];
    $ctx = stream_context_create($opts);
    $response = @file_get_contents($testUrl, false, $ctx);
    return $response !== FALSE && !empty($response);
}

// YENİ: Çalışan ilk URL'yi bulma mantığı
echo "Çalışan bir API URL'si aranıyor...\n";
$githubContent = fetchGithubContent($sourceUrlRaw, $proxyUrl);

$githubBaseUrl = '';
if ($githubContent !== FALSE) {
    if (preg_match('/override\s+var\s+mainUrl\s*=\s*"([^"]+)"/', $githubContent, $m)) $githubBaseUrl = $m[1];
    if (preg_match('/private\s+val\s+swKey\s*=\s*"([^"]+)"/', $githubContent, $m)) $suffix = $m[1];
    if (preg_match('/user-agent"\s*to\s*"([^"]+)"/', $githubContent, $m)) $userAgent = $m[1];
    if (preg_match('/Referer"\s*to\s*"([^"]+)"/', $githubContent, $m)) $referer = $m[1];
}

// 1. Önce Github'dan geleni dene
if (!empty($githubBaseUrl) && isApiWorking($githubBaseUrl, $suffix, $userAgent)) {
    $activeBaseUrl = $githubBaseUrl;
    echo "Başarılı: Github'dan alınan güncel API URL'si çalışıyor: $activeBaseUrl\n";
} else {
    echo "Bilgi: Github'dan alınan URL çalışmıyor veya alınamadı. Yedekler deneniyor...\n";
    // 2. Yedek listesini dene
    foreach ($fallbackBaseUrls as $fallbackUrl) {
        echo "  -> Deneniyor: $fallbackUrl\n";
        if (isApiWorking($fallbackUrl, $suffix, $userAgent)) {
            $activeBaseUrl = $fallbackUrl;
            echo "Başarılı: Çalışan yedek API URL'si bulundu: $activeBaseUrl\n";
            break; // Çalışan ilk URL'yi bulduk, döngüden çık.
        }
    }
}

// Hiçbir URL çalışmazsa betiği durdur.
if (empty($activeBaseUrl)) {
    echo "HATA: Çalışan hiçbir API URL'si bulunamadı. Betik durduruluyor.\n";
    exit(1); // Hata koduyla çık
}

$options = ['http' => ['header' => "User-Agent: $userAgent\r\nReferer: $referer\r\n", 'timeout' => 10]];
$context = stream_context_create($options);
// --- BİTİŞ: Ortak Ayarlar ---

$m3uContent = "#EXTM3U\n";
$foundSeriesCount = 0;

echo "Diziler çekiliyor...\n";
$seriesApi = "api/serie/by/filtres/0/created/SAYFA/$suffix";
$categoryName = "Diziler";

for ($page = 0; $page <= 50; $page++) {
    $apiUrl = $activeBaseUrl . '/' . str_replace('SAYFA', $page, $seriesApi);
    $response = @file_get_contents($apiUrl, false, $context);
    
    if ($response === FALSE || empty(json_decode($response, true))) {
        echo "Bilgi: Sayfa $page için veri alınamadı veya boş. İşlem sonlandırılıyor.\n";
        break;
    }
    
    $data = json_decode($response, true);
    echo "Sayfa $page bulundu, " . count($data) . " içerik işleniyor...\n";

    foreach ($data as $content) {
        if (isset($content['sources']) && is_array($content['sources'])) {
            foreach ($content['sources'] as $source) {
                if (($source['type'] ?? '') === 'm3u8' && isset($source['url'])) {
                    $title = $content['title'] ?? 'Baslik Yok';
                    $image = isset($content['image']) ? ((strpos($content['image'], 'http') === 0) ? $content['image'] : $activeBaseUrl . '/' . ltrim($content['image'], '/')) : '';
                    $m3uContent .= "#EXTINF:-1 tvg-id=\"{$content['id']}\" tvg-name=\"$title\" tvg-logo=\"$image\" group-title=\"$categoryName\", $title\n";
                    $m3uContent .= "#EXTVLCOPT:http-user-agent=googleusercontent\n";
                    $m3uContent .= "#EXTVLCOPT:http-referrer=https://twitter.com/\n";
                    $m3uContent .= "{$source['url']}\n";
                    $foundSeriesCount++;
                }
            }
        }
    }
}

if ($foundSeriesCount > 0) {
    file_put_contents('diziler.m3u', $m3uContent);
    echo "İşlem tamamlandı. Toplam $foundSeriesCount adet dizi bulundu ve 'diziler.m3u' dosyası oluşturuldu.\n";
} else {
    echo "Uyarı: API'den hiç dizi verisi alınamadı. 'diziler.m3u' dosyası oluşturulmadı.\n";
}
?>