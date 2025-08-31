import requests
import re
import json
import os

def download_rec_tv_kta():
    """Kendi reponuzdaki RecTV.kta dosyasını indir ve analiz et"""
    url = "https://raw.githubusercontent.com/koprulu555/rec3/main/scripts/RecTV.kta"
    
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        
        content = response.text
        print("✓ RecTV.kta başarıyla indirildi")
        
        # Firebase configini parse et
        firebase_config = {}
        
        patterns = {
            'apiKey': r'apiKey\s*=\s*"([^"]+)"',
            'authDomain': r'authDomain\s*=\s*"([^"]+)"',
            'projectId': r'projectId\s*=\s*"([^"]+)"',
            'storageBucket': r'storageBucket\s*=\s*"([^"]+)"',
            'messagingSenderId': r'messagingSenderId\s*=\s*"([^"]+)"',
            'appId': r'appId\s*=\s*"([^"]+)"'
        }
        
        for key, pattern in patterns.items():
            match = re.search(pattern, content)
            if match:
                firebase_config[key] = match.group(1)
                print(f"✓ {key}: {match.group(1)}")
            else:
                print(f"ℹ {key} bulunamadı")
        
        # API endpoint'lerini bul
        api_config = {}
        
        # mainUrl
        main_url_match = re.search(r'override\s+var\s+mainUrl\s*=\s*"([^"]+)"', content)
        if main_url_match:
            api_config['mainUrl'] = main_url_match.group(1)
            print(f"✓ mainUrl: {api_config['mainUrl']}")
        else:
            # Fallback mainUrl
            api_config['mainUrl'] = 'https://m.prectv55.lol'
            print("ℹ mainUrl bulunamadı, fallback kullanılıyor")
        
        # swKey
        sw_key_match = re.search(r'private\s+(val|var)\s+swKey\s*=\s*"([^"]+)"', content)
        if sw_key_match:
            api_config['swKey'] = sw_key_match.group(2)
            print(f"✓ swKey: {api_config['swKey']}")
        else:
            # Fallback swKey
            api_config['swKey'] = '4F5A9C3D9A86FA54EACEDDD635185/64f9535b-bd2e-4483-b234-89060b1e631c'
            print("ℹ swKey bulunamadı, fallback kullanılıyor")
        
        # userAgent
        ua_match = re.search(r'"user-agent"\s*to\s*"([^"]+)"', content)
        if ua_match:
            api_config['userAgent'] = ua_match.group(1)
            print(f"✓ userAgent: {api_config['userAgent']}")
        else:
            # Fallback userAgent
            api_config['userAgent'] = 'Dart/3.7 (dart:io)'
            print("ℹ userAgent bulunamadı, fallback kullanılıyor")
        
        # referer
        referer_match = re.search(r'"Referer"\s*to\s*"([^"]+)"', content)
        if referer_match:
            api_config['referer'] = referer_match.group(1)
            print(f"✓ referer: {api_config['referer']}")
        else:
            # Fallback referer
            api_config['referer'] = 'https://twitter.com/'
            print("ℹ referer bulunamadı, fallback kullanılıyor")
        
        # Configleri kaydet
        with open('firebase-config.json', 'w') as f:
            json.dump(firebase_config, f, indent=2)
        
        with open('api-config.json', 'w') as f:
            json.dump(api_config, f, indent=2)
            
        print("✓ Config dosyaları oluşturuldu")
        return True
        
    except Exception as e:
        print(f"✗ Hata: {e}")
        return False

def create_fallback_config():
    """Fallback config oluştur"""
    fallback_config = {
        'mainUrl': 'https://m.prectv55.lol',
        'swKey': '4F5A9C3D9A86FA54EACEDDD635185/64f9535b-bd2e-4483-b234-89060b1e631c',
        'userAgent': 'Dart/3.7 (dart:io)',
        'referer': 'https://twitter.com/'
    }
    
    with open('api-config.json', 'w') as f:
        json.dump(fallback_config, f, indent=2)
    print("✓ Fallback config oluşturuldu")

if __name__ == "__main__":
    success = download_rec_tv_kta()
    if not success:
        create_fallback_config()
