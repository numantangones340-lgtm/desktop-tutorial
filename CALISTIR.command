#!/bin/bash
set -e

cd /Users/numantangones/Documents/GuitarAmpRecorder

echo "Guitar Amp Recorder baslatiliyor..."

auto_python="python3"
if ! command -v "$auto_python" >/dev/null 2>&1; then
  echo "HATA: python3 bulunamadi. Lutfen Python 3 kurun."
  echo "https://www.python.org/downloads/"
  read -n 1 -s -r -p "Cikmak icin bir tusa basin..."
  echo
  exit 1
fi

if [ ! -d ".venv" ]; then
  echo "Sanal ortam olusturuluyor..."
  "$auto_python" -m venv .venv
fi

source .venv/bin/activate

echo "Gerekli kutuphaneler yukleniyor..."
pip install -r requirements.txt

if command -v brew >/dev/null 2>&1; then
  if ! command -v ffmpeg >/dev/null 2>&1; then
    echo "ffmpeg kuruluyor (Homebrew)..."
    brew install ffmpeg
  fi
else
  if ! command -v ffmpeg >/dev/null 2>&1; then
    echo "UYARI: Homebrew yok ve ffmpeg bulunamadi."
    echo "MP3 cevirme icin ffmpeg gerekir."
    echo "Homebrew kurulumu:"
    echo '/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'
    echo
  fi
fi

echo "Terminal surumu aciliyor..."
python cli_app.py

