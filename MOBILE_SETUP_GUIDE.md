# NovaMind Mobile - Backend Bağlantı Kılavuzu

## ✅ Tamamlanan İşlemler

1. ✅ **Capacitor kurulumu** - Android platform eklendi
2. ✅ **Backend CORS güncellendi** - Mobil origin'ler eklendi
3. ✅ **Platform detection** - Otomatik IP tespit sistemi
4. ✅ **Environment configurations** - Farklı senaryolar için .env dosyaları

## 🎯 Ana Özellik: Otomatik Platform Algılama

Artık backend URL'si **otomatik** tespit ediliyor:
- **Web browser:** `localhost:8001`
- **Android emulator:** `10.0.2.2:8001`
- **Fiziksel cihaz:** `.env` dosyasındaki IP

📁 Dosya: `frontend/src/utils/platformHelper.js`

## 🚀 Kullanım

### 1️⃣ Backend'i Başlat

```bash
cd /c/Users/murat/Desktop/novamind\ mobil
./start_dev.sh
```

Backend şu adreste çalışacak: `http://localhost:8001`

### 2️⃣ Android Emulator'da Test

```bash
# Emulator için .env kullan
cd frontend
cp .env.android.emulator .env

# Build ve sync
npm run build
npx cap sync android

# Android Studio'da aç
npx cap open android
```

Android Studio'da **Run** butonuna bas. Emulator'da uygulama açılacak ve backend'e **10.0.2.2:8001** üzerinden bağlanacak.

### 3️⃣ Fiziksel Cihazda Test

```bash
# Fiziksel cihaz için .env kullan
cd frontend
cp .env.android.device .env

# Build ve sync
npm run build
npx cap sync android
```

**ÖNEMLİ:** 
- Bilgisayar ve telefon **aynı WiFi ağında** olmalı
- Windows Firewall port 8001'i **izin vermelisiniz**
- Şu anki IP: **10.5.28.235** (değişirse .env.android.device'i güncelleyin)

### 4️⃣ Web Browser'da Test

```bash
cd frontend
# Web için varsayılan .env zaten localhost kullanıyor
npm run dev
```

## 🔧 IP Adresi Değişirse

IP adresiniz değişirse (farklı WiFi ağı):

```bash
# 1. Yeni IP'yi bul
ipconfig  # Windows

# 2. .env.android.device dosyasını güncelle
# Örnek: VITE_API_URL=http://192.168.1.100:8001

# 3. Rebuild
npm run build
npx cap sync android
```

## 📱 Test Senaryoları

| Senaryo | .env Dosyası | Backend URL |
|---------|-------------|-------------|
| Web Browser | `.env` | `http://localhost:8001` |
| Android Emulator | `.env.android.emulator` | `http://10.0.2.2:8001` |
| Fiziksel Android | `.env.android.device` | `http://10.5.28.235:8001` |

## 🐛 Sorun Giderme

### "Cannot connect to backend" Hatası

**Emulator'da:**
1. Backend çalışıyor mu? (`http://localhost:8001` browser'da açılıyor mu?)
2. `.env` dosyası `10.0.2.2:8001` kullanıyor mu?
3. Build aldınız mı? (`npm run build && npx cap sync android`)

**Fiziksel cihazda:**
1. Cihaz ve bilgisayar aynı WiFi'de mi?
2. IP doğru mu? (`ipconfig` ile kontrol et)
3. Windows Firewall port 8001'i engelliyor mu?
   ```bash
   # Firewall kuralı ekle (Admin CMD)
   netsh advfirewall firewall add rule name="Novamind Backend" dir=in action=allow protocol=TCP localport=8001
   ```

### Logları Kontrol Et

Android Studio'da:
- **Logcat** -> Filtre: "API Client"
- Console'da şunu görmelisiniz: `[API Client] Using API URL: http://10.0.2.2:8001`

## 📝 Geliştirme Workflow'u

1. Frontend'de değişiklik yap
2. `npm run build`
3. `npx cap sync android`
4. Android Studio'da **Refresh** (veya yeniden **Run**)

## 🎉 Başarıyla Tamamlandı!

Backend-frontend bağlantısı artık hem web hem de Android'de çalışıyor!

**Sonraki adımlar:**
- [ ] Google OAuth mobil'de test et
- [ ] Gmail API entegrasyonu test et  
- [ ] Production APK build
- [ ] iOS platform ekle (opsiyonel)
