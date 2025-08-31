import json
import os
import firebase_admin
from firebase_admin import credentials, auth

def authenticate_firebase():
    """Firebase authentication yap"""
    try:
        # Firebase configini oku
        try:
            with open('firebase-config.json', 'r') as f:
                firebase_config = json.load(f)
            print("✓ Firebase config dosyası okundu")
        except:
            print("ℹ Firebase config dosyası bulunamadı")
            return None
        
        # Service account (GitHub Secrets'tan)
        service_account = os.getenv('FIREBASE_SERVICE_ACCOUNT')
        
        if service_account:
            try:
                service_account_json = json.loads(service_account)
                cred = credentials.Certificate(service_account_json)
                firebase_admin.initialize_app(cred, firebase_config)
                
                # Custom token oluştur
                uid = os.getenv('FIREBASE_UID', 'default-user')
                custom_token = auth.create_custom_token(uid)
                
                print("✓ Firebase authentication başarılı")
                return custom_token.decode('utf-8')
                
            except Exception as e:
                print(f"✗ Firebase auth hatası: {e}")
                return None
        else:
            print("ℹ FIREBASE_SERVICE_ACCOUNT bulunamadı, devam ediliyor...")
            return None
            
    except Exception as e:
        print(f"✗ Firebase auth genel hatası: {e}")
        return None

if __name__ == "__main__":
    token = authenticate_firebase()
    if token:
        with open('firebase-token.txt', 'w') as f:
            f.write(token)
        print("✓ Firebase token kaydedildi")
    else:
        print("ℹ Firebase token alınamadı, API config doğrudan kullanılacak")
