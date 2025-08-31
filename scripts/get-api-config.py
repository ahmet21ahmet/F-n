import json
import os
import requests

def get_api_config():
    """API configlerini al"""
    try:
        # Firebase token'ı oku
        try:
            with open('firebase-token.txt', 'r') as f:
                firebase_token = f.read().strip()
        except:
            firebase_token = None
        
        # API config endpoint (RecTV uygulamasının kullandığı endpoint)
        api_url = "https://yourapi-domain.com/api/config"
        
        headers = {
            'Authorization': f'Bearer {firebase_token}' if firebase_token else '',
            'User-Agent': 'RecTV-M3U-Generator/1.0',
            'Content-Type': 'application/json'
        }
        
        payload = {
            'deviceId': os.getenv('DEVICE_ID', 'github-action-device'),
            'token': firebase_token
        }
        
        response = requests.post(api_url, json=payload, headers=headers, timeout=15)
        
        if response.status_code == 200:
            api_config = response.json()
            print("✓ API config başarıyla alındı")
            return api_config
        else:
            raise Exception(f"API error: {response.status_code}")
            
    except Exception as e:
        print(f"✗ API config alınamadı: {e}")
        # Local configi kullan
        with open('api-config.json', 'r') as f:
            local_config = json.load(f)
        print("✓ Local config kullanılıyor")
        return local_config

if __name__ == "__main__":
    config = get_api_config()
    with open('final-config.json', 'w') as f:
        json.dump(config, f, indent=2)
