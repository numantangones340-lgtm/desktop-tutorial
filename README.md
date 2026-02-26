# Guitar Amp Recorder (macOS / Windows)

Bu uygulama şunları yapar:
- 1. kanal: Hazır müzik (backing track)
- 2. kanal: Mikrofon kaydı
- Mikrofon kanalına amfi benzeri efektler (gain, boost, bass, treble, distortion)
- Mikrofon ve ses kartı cihaz ID seçimi (input/output, bos birakilabilir)
- Tek tık 5 sn cihaz/kayıt testi
- Sonucu otomatik MP3 olarak Masaüstüne çıkarır

## Kurulum (macOS önerilen)

1. Python 3.10+ kurulu olsun.
2. `ffmpeg` kurun:
   - macOS (Homebrew):
     ```bash
     brew install ffmpeg
     ```
3. Proje klasöründe sanal ortam kurup paketleri yükleyin:
   ```bash
   cd /Users/numantangones/Documents/GuitarAmpRecorder
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

## Çalıştırma

```bash
cd /Users/numantangones/Documents/GuitarAmpRecorder
source .venv/bin/activate
python app.py
```

## Kullanım

1. Mikrofon/Cikis Device ID kutularini bos birakabilirsiniz (varsayilan cihaz).
2. `Mikrofon/Ses Kartı Testi (5 sn)` butonuyla önce test yapın.
3. `Müzik Dosyası Seç` ile backing track seçin (`.wav/.aiff/.flac`).
4. Gain/Boost/Bass/Treble/Distortion ayarlarını yapın.
5. `Kaydı Başlat ve MP3 Çıkar` butonuna basın.
6. Kayıt bitince dosyalar Masaüstüne yazılır:
   - `dosyaadi.mp3` (mix)
   - `dosyaadi_vocal.wav` (işlenmiş vokal/gitar kanalınız)
   - `dosyaadi_device_test.wav` (test kaydı)

## Notlar

- Kayıt sırasında kulaklık kullanmanız geri besleme (feedback) riskini azaltır.
- `ffmpeg bulunamadı` hatası alırsanız `brew install ffmpeg` komutunu tekrar çalıştırın.
- Windows'ta da çalışır; `ffmpeg` ve Python kurulumu gerekir.
