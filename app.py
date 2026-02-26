import shutil
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from tkinter import Tk, Label, Button, Scale, HORIZONTAL, filedialog, StringVar, Entry
from typing import Optional, Tuple

import numpy as np
import sounddevice as sd
import soundfile as sf


def db_to_linear(db: float) -> float:
    return 10 ** (db / 20.0)


def one_pole_lowpass(signal: np.ndarray, sample_rate: int, cutoff_hz: float) -> np.ndarray:
    if cutoff_hz <= 0:
        return np.zeros_like(signal)
    alpha = np.exp(-2.0 * np.pi * cutoff_hz / sample_rate)
    out = np.zeros_like(signal)
    out[0] = (1.0 - alpha) * signal[0]
    for i in range(1, len(signal)):
        out[i] = (1.0 - alpha) * signal[i] + alpha * out[i - 1]
    return out


def apply_amp_chain(
    voice: np.ndarray,
    sample_rate: int,
    gain_db: float,
    boost_db: float,
    bass_db: float,
    treble_db: float,
    distortion: float,
) -> np.ndarray:
    x = voice.astype(np.float32)

    x = x * db_to_linear(gain_db + boost_db)

    low = one_pole_lowpass(x, sample_rate, 220.0)
    high_base = one_pole_lowpass(x, sample_rate, 2800.0)
    high = x - high_base

    bass_mix = (db_to_linear(bass_db) - 1.0)
    treble_mix = (db_to_linear(treble_db) - 1.0)
    x = x + low * bass_mix + high * treble_mix

    drive = 1.0 + (distortion / 100.0) * 24.0
    x = np.tanh(x * drive) / np.tanh(drive)

    return np.clip(x, -1.0, 1.0)


def ensure_stereo(audio: np.ndarray) -> np.ndarray:
    if audio.ndim == 1:
        return np.stack([audio, audio], axis=1)
    if audio.shape[1] == 1:
        return np.repeat(audio, 2, axis=1)
    return audio[:, :2]


def resample_linear(audio: np.ndarray, src_sr: int, dst_sr: int) -> np.ndarray:
    if src_sr == dst_sr:
        return audio
    ratio = dst_sr / src_sr
    src_len = len(audio)
    dst_len = max(1, int(src_len * ratio))
    src_x = np.linspace(0.0, 1.0, src_len)
    dst_x = np.linspace(0.0, 1.0, dst_len)

    if audio.ndim == 1:
        return np.interp(dst_x, src_x, audio).astype(np.float32)

    channels = []
    for ch in range(audio.shape[1]):
        channels.append(np.interp(dst_x, src_x, audio[:, ch]))
    return np.stack(channels, axis=1).astype(np.float32)


class GuitarAmpRecorderApp:
    def __init__(self, root: Tk) -> None:
        self.root = root
        self.root.title("Guitar Amp Recorder")
        self.root.geometry("560x660")

        self.backing_file: Optional[Path] = None

        self.status_text = StringVar(value="Hazır")
        self.output_name = StringVar(value=f"guitar_mix_{time.strftime('%Y%m%d_%H%M%S')}")
        self.input_device_id = StringVar(value="")
        self.output_device_id = StringVar(value="")

        Label(root, text="Mikrofon Device ID (bos = varsayilan):").pack(anchor="w", padx=12, pady=(12, 2))
        Entry(root, textvariable=self.input_device_id, width=20).pack(anchor="w", padx=12)

        Label(root, text="Cikis Device ID (bos = varsayilan):").pack(anchor="w", padx=12, pady=(8, 2))
        Entry(root, textvariable=self.output_device_id, width=20).pack(anchor="w", padx=12)

        Label(
            root,
            text="Not: Cihaz ID bilmiyorsaniz iki alanı da bos birakin (en guvenli yol).",
            fg="#2c3e50",
        ).pack(anchor="w", padx=12, pady=(4, 8))

        Label(root, text="Backing Track:").pack(anchor="w", padx=12, pady=(10, 2))
        self.backing_label = Label(root, text="Dosya seçilmedi", fg="gray")
        self.backing_label.pack(anchor="w", padx=12)

        Button(root, text="Müzik Dosyası Seç", command=self.select_backing).pack(anchor="w", padx=12, pady=8)

        Label(root, text="Çıkış Dosya Adı (MP3):").pack(anchor="w", padx=12, pady=(8, 2))
        Entry(root, textvariable=self.output_name, width=48).pack(anchor="w", padx=12)

        self.gain = self.make_slider("Gain (dB)", -12, 24, 6)
        self.boost = self.make_slider("Boost (dB)", 0, 18, 6)
        self.bass = self.make_slider("Bass (dB)", -12, 12, 3)
        self.treble = self.make_slider("Treble (dB)", -12, 12, 2)
        self.distortion = self.make_slider("Distortion (%)", 0, 100, 25)

        Button(root, text="Mikrofon/Ses Kartı Testi (5 sn)", command=self.start_test_thread, bg="#1f6feb", fg="white").pack(
            fill="x", padx=12, pady=(10, 6)
        )
        Button(root, text="Kaydı Başlat ve MP3 Çıkar", command=self.start_recording_thread, bg="#27ae60", fg="white").pack(
            fill="x", padx=12, pady=12
        )

        Label(root, textvariable=self.status_text, fg="#2c3e50", wraplength=490, justify="left").pack(anchor="w", padx=12, pady=(0, 10))

    def make_slider(self, label: str, min_v: int, max_v: int, default: int) -> Scale:
        Label(self.root, text=label).pack(anchor="w", padx=12)
        slider = Scale(self.root, from_=min_v, to=max_v, orient=HORIZONTAL, length=490, resolution=1)
        slider.set(default)
        slider.pack(anchor="w", padx=12)
        return slider

    def set_status(self, text: str) -> None:
        self.status_text.set(text)
        self.root.update_idletasks()

    def select_backing(self) -> None:
        file_path = filedialog.askopenfilename(
            title="Backing track seç",
            filetypes=[
                ("Audio Files", "*.wav *.aiff *.aif *.flac"),
                ("WAV", "*.wav"),
                ("AIFF", "*.aiff *.aif"),
                ("FLAC", "*.flac"),
            ],
        )
        if not file_path:
            return
        self.backing_file = Path(file_path)
        self.backing_label.config(text=self.backing_file.name, fg="#2c3e50")

    def selected_device_pair(self) -> Tuple[Optional[int], Optional[int]]:
        input_text = self.input_device_id.get().strip()
        output_text = self.output_device_id.get().strip()
        input_idx = int(input_text) if input_text else None
        output_idx = int(output_text) if output_text else None
        return input_idx, output_idx

    def start_test_thread(self) -> None:
        worker = threading.Thread(target=self.run_device_test, daemon=True)
        worker.start()

    def run_device_test(self) -> None:
        try:
            sr = 44100
            seconds = 5
            frames = sr * seconds
            input_idx, output_idx = self.selected_device_pair()

            self.set_status("Test kaydı başlıyor (5 sn). Mikrofona konuşun/çalın...")
            recorded = sd.rec(
                frames=frames,
                samplerate=sr,
                channels=1,
                dtype="float32",
                device=input_idx,
            )
            sd.wait()
            voice = recorded[:, 0]

            processed = apply_amp_chain(
                voice=voice,
                sample_rate=sr,
                gain_db=float(self.gain.get()),
                boost_db=float(self.boost.get()),
                bass_db=float(self.bass.get()),
                treble_db=float(self.treble.get()),
                distortion=float(self.distortion.get()),
            )

            preview = np.stack([processed, processed], axis=1)
            self.set_status("Test çalınıyor...")
            sd.play(preview, samplerate=sr, device=output_idx)
            sd.wait()

            desktop = Path.home() / "Desktop"
            test_path = desktop / f"{self.output_name.get().strip() or 'guitar_mix'}_device_test.wav"
            sf.write(test_path, processed, sr)

            peak = float(np.max(np.abs(voice))) if len(voice) else 0.0
            self.set_status(f"Test tamam. Peak={peak:.3f} | Dosya: {test_path}")
        except Exception as exc:
            self.set_status(f"Test hatası: {exc}")

    def start_recording_thread(self) -> None:
        if self.backing_file is None:
            self.set_status("Önce bir backing track seçin.")
            return
        worker = threading.Thread(target=self.record_and_export, daemon=True)
        worker.start()

    def record_and_export(self) -> None:
        try:
            self.set_status("Backing yükleniyor...")
            backing, sr = sf.read(self.backing_file, dtype="float32")
            backing = ensure_stereo(backing)

            target_sr = 44100
            if sr != target_sr:
                self.set_status(f"Sample rate {sr} -> {target_sr} dönüştürülüyor...")
                backing = resample_linear(backing, sr, target_sr)
                sr = target_sr

            duration_sec = len(backing) / sr
            input_idx, output_idx = self.selected_device_pair()
            self.set_status(
                f"Kayıt başlıyor ({duration_sec:.1f} sn). Kulaklık önerilir. Backing çalarken mikrofona söyleyin/çalın..."
            )

            recorded = sd.playrec(backing, samplerate=sr, channels=1, dtype="float32", device=(input_idx, output_idx))
            sd.wait()

            voice = recorded[:, 0]
            self.set_status("Amfi efektleri uygulanıyor...")
            processed_voice = apply_amp_chain(
                voice=voice,
                sample_rate=sr,
                gain_db=float(self.gain.get()),
                boost_db=float(self.boost.get()),
                bass_db=float(self.bass.get()),
                treble_db=float(self.treble.get()),
                distortion=float(self.distortion.get()),
            )

            mix = backing.copy()
            mix[:, 0] += processed_voice * 0.85
            mix[:, 1] += processed_voice * 0.85

            peak = np.max(np.abs(mix))
            if peak > 0.98:
                mix = mix / peak * 0.98
            mix = np.clip(mix, -1.0, 1.0)

            desktop = Path.home() / "Desktop"
            base_name = self.output_name.get().strip() or f"guitar_mix_{time.strftime('%Y%m%d_%H%M%S')}"
            mp3_path = desktop / f"{base_name}.mp3"
            mix_wav_path = desktop / f"{base_name}_mix.wav"
            vocal_wav_path = desktop / f"{base_name}_vocal.wav"

            self.set_status("Dosyalar hazırlanıyor...")
            ffmpeg_bin = shutil.which("ffmpeg")

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_wav:
                tmp_wav_path = Path(tmp_wav.name)

            try:
                sf.write(tmp_wav_path, mix, sr)
                sf.write(vocal_wav_path, processed_voice, sr)

                if ffmpeg_bin:
                    cmd = [
                        ffmpeg_bin,
                        "-y",
                        "-i",
                        str(tmp_wav_path),
                        "-codec:a",
                        "libmp3lame",
                        "-qscale:a",
                        "2",
                        str(mp3_path),
                    ]
                    subprocess.run(cmd, check=True, capture_output=True)
                    final_note = f"MP3: {mp3_path}"
                else:
                    sf.write(mix_wav_path, mix, sr)
                    final_note = f"ffmpeg yok, WAV mix kaydedildi: {mix_wav_path}"
            finally:
                if tmp_wav_path.exists():
                    tmp_wav_path.unlink()

            self.set_status(
                f"Tamamlandı. {final_note} | Vocal WAV: {vocal_wav_path}"
            )
        except Exception as exc:
            self.set_status(f"Hata: {exc}")


def main() -> None:
    root = Tk()
    GuitarAmpRecorderApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
