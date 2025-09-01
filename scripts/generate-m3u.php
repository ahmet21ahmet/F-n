import json
import os
import requests

def create_fallback_config():
    """
    API'ye ulaşılamadığında kullanılacak yedek bir yapılandırma dosyası oluşturur.
    Bilgiler RecTV.kta dosyasından alınmıştır.
    """
    fallback_data = {
        "mainUrl": "https://m.prectv55.lol",
        "swKey": "4F5A9C3D9A86FA54EACEDDD635185/64f9535b-bd2e-4483-b234-89060b1e631c",
        "userAgent": "Dart/3.7 (dart:io)",
        "referer": "https://www.google.com/"
    }
    with open('api-config.json', 'w') as f:
        json.dump(fallback_data, f, indent=2)
    print("✓ Yedek 'api-config.json' dosyası oluşturuldu.")
    return fallback_data

def get_api_config():
    """API yapılandırmasını alır veya yedek oluşturur."""
    try:
        # --- DÜZELTME: API URL'si güncellendi ---
        api_url = "https://m.prectv55.lol/api/config"
        
        # Firebase token'ını oku (varsa)
        firebase_token = None
        if os.path.exists('firebase-token.txt'):
            with open('firebase-token.txt', 'r') as f:
                firebase_token = f.read().strip()
        
        headers = {
            'Authorization': f'Bearer {firebase_token}' if firebase_token else '',
            'User-Agent': 'RecTV-M3U-Generator/1.0',
            'Content-Type': 'application/json'
        }
        
        payload = {
            'deviceId': os.getenv('DEVICE_ID', 'github-action-device'),
            'token': firebase_token
        }
        
        print(f"-> API yapılandırması isteniyor: {api_url}")
        response = requests.post(api_url, json=payload, headers=headers, timeout=20)
        
        if response.status_code == 200:
            api_config = response.json()
            print("✓ API yapılandırması başarıyla alındı.")
            return api_config
        else:
            # Sunucudan hata dönerse, bunu bir istisna olarak yükselt
            raise Exception(f"API hatası: {response.status_code} - {response.text}")
            
    except Exception as e:
        print(f"✗ API yapılandırması alınamadı: {e}")
        # --- DÜZELTME: Yerel yedek dosyası oluştur ve kullan ---
        print("ℹ️ Yerel yedek yapılandırma kullanılacak.")
        return create_fallback_config()

if __name__ == "__main__":
    config = get_api_config()
    # 'final-config.json' dosyasına nihai yapılandırmayı yaz
    with open('final-config.json', 'w') as f:
        json.dump(config, f, indent=2)
    print("✓ 'final-config.json' dosyası başarıyla oluşturuldu/güncellendi.")