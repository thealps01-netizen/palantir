# Changelog

Tüm önemli değişiklikler bu dosyada belgelenmiştir.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)
Versiyonlama: [Semantic Versioning](https://semver.org/spec/v2.0.0.html)

---

## [1.0.6] — 2026-03-30

### Eklendi
- Assets (overlay.png, settings.png) ve icon dosyaları repo'ya eklendi

### Düzeltildi
- Gizli pencereyi eski konumuna geri getirip kapanış animasyonu oynat

---

## [1.0.5] — 2026-03-30

### Düzeltildi
- Sağ tık quit animasyonu: pencereyi göster sonra animasyon oynat

---

## [1.0.4] — 2026-03-30

### Düzeltildi
- Sağ tık menüsünden çıkışta (minimize durumdan) kapanma animasyonu artık çalışıyor

---

## [1.0.3] — 2026-03-30

### Düzeltildi
- Quit: `closeEvent` + `_quitting` flag ile `QApplication.quit()` artık event loop'tan düzgün çıkıyor

---

## [1.0.2] — 2026-03-30

### Düzeltildi
- Dış uygulama close mesajları artık overlay'i gizlemiyor (`closeEvent` → `ignore`)
- Splash screen dolum yayı animasyonuna döndü

---

## [1.0.1] — 2026-03-30

### Değişti
- Splash screen: dolum yayı → kilit açılma animasyonu (kol sağa-yukarı sallanır, renk accent→yeşil)
- Overlay köşeleri: border-radius 18px (settings dialog ile tutarlı)

### Düzeltildi
- Sağ tık → Quit çalışmıyordu; `QTimer.singleShot` ile güvenilir kapanış sağlandı

---

## [1.0.0] — 2026-03-30

### Eklendi
- Gerçek zamanlı donanım izleme — FPS, GPU/CPU kullanım, sıcaklık, güç, clock, VRAM, RAM
- Her zaman üstte, çerçevesiz overlay (`WS_EX_NOACTIVATE` — oyunlardan focus çalmaz)
- **Açılış animasyonu** — overlay ilk açılışta yukarıdan kayarak + fade-in (500ms, OutCubic)
- **Kapanış animasyonu** — kapanırken aşağıya kayarak + fade-out (400ms, InCubic)
- **Splash screen** — uygulama başlarken ekran ortasında dönen dolum yayı animasyonu (~1.5s)
- **Slide in/out animasyonu** — system tray tıklamasıyla overlay'i göster/gizle (280ms)
- **Hover opacity** — overlay'in üzerine gelince şeffaflaşır, ayrılınca normale döner (350ms)
- Sürükle & bırak konumlandırma veya kilitleme
- System tray entegrasyonu ve bağlam menüsü
- Sensör başına özel renk seçimi
- Karanlık / Aydınlık tema + Windows High Contrast desteği
- MSI Afterburner shared memory (MAHM) üzerinden sensör okuma
- RAM kullanımı için Windows API entegrasyonu
- Otomatik güncelleme — GitHub Releases API üzerinden kontrol ve sessiz kurulum
- Windows başlangıcında çalışma (registry entegrasyonu)
- Dönen log dosyası (1 MB, 2 yedek) + detaylı crash raporları
- Atomic settings yazma — veri bütünlüğü için `.tmp` → rename
- İlk çalıştırma hoş geldiniz ekranı
- 14+ desteklenen sensör tipi

### Teknik
- PyQt6 tabanlı, tamamen Python
- Arka plan donanım polling'i için ayrı QThread (UI bloklamaz)
- PyInstaller + Inno Setup ile tek exe kurulum paketi
- PerMonitorV2 DPI awareness (Windows 11 çok monitör desteği)
- Windows App User Model ID (görev çubuğu gruplama + pin desteği)
- pytest tabanlı unit test altyapısı
