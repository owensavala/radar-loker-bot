import os
import time
import requests
from google import genai
from apify_client import ApifyClient
from dotenv import load_dotenv

# Muat variabel environment dari file .env lokal (jika ada)
load_dotenv()

# ==========================================
# 1. KREDENSIAL & KONFIGURASI SISTEM
# ==========================================
APIFY_TOKEN = os.environ.get("APIFY_TOKEN")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

# Validasi konfigurasi sebelum agen berjalan
missing_vars = []
if not APIFY_TOKEN:
    missing_vars.append("APIFY_TOKEN")
if not TELEGRAM_TOKEN:
    missing_vars.append("TELEGRAM_TOKEN")
if not CHAT_ID:
    missing_vars.append("CHAT_ID")
if not GEMINI_API_KEY:
    missing_vars.append("GEMINI_API_KEY")

if missing_vars:
    raise ValueError(f"🚨 Variabel environment belum dikonfigurasi: {', '.join(missing_vars)}")

# ==========================================
# 2. INISIALISASI KLIEN AI & HELPER
# ==========================================
client_ai = genai.Client(api_key=GEMINI_API_KEY)


def kirim_telegram(pesan: str) -> bool:
    """Mengirim pesan notifikasi ke chat / channel Telegram tujuan."""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": pesan,
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    }
    try:
        response = requests.post(url, data=payload, timeout=15)
        response.raise_for_status()
        return True
    except Exception as err:
        print(f"🚨 Gagal mengirim ke Telegram: {err}")
        return False


def saring_loker_dengan_ai(teks_loker: str) -> str:
    """Menganalisis dan menyaring teks loker menggunakan Google Gemini AI."""
    instruksi = f"""
    Kamu adalah asisten HRD profesional yang bertugas menganalisis dan merangkum lowongan pekerjaan.
    Baca teks pamflet/caption loker berikut secara teliti:
    \"\"\"{teks_loker}\"\"\"

    ATURAN FILTER:
    1. Periksa batas akhir (deadline) pendaftaran atau tahun penerbitan.
    2. Jika lowongan sudah lewat batas waktu (kedaluwarsa) atau merujuk ke tahun lama sebelum tahun berjalan, balas HANYA dengan 1 kata: KEDALUWARSA.
    3. Jika masih berlaku atau tidak menyebutkan batas waktu yang lewat, buatkan ringkasan padat dan informatif dengan format berikut:
    🏢 <b>Kategori:</b> [Industri/Bidang Usaha]
    💼 <b>Posisi:</b> [Nama Posisi / Pekerjaan]
    📝 <b>Kualifikasi:</b>
    • [Poin syarat utama 1]
    • [Poin syarat utama 2]
    • [Poin syarat utama 3]
    """
    try:
        respons = client_ai.models.generate_content(
            model=GEMINI_MODEL,
            contents=instruksi
        )
        return respons.text.strip()
    except Exception as e:
        print(f"🚨 Error saat memproses dengan Gemini AI: {e}")
        return "GAGAL_MERANGKUM"


def main():
    print("🚀 Radar Loker Bot: Memulai pemindaian sumber informasi...")
    client = ApifyClient(APIFY_TOKEN)

    input_pencarian = {
        "directUrls": [
            "https://www.instagram.com/tamangkerja/",
            "https://www.instagram.com/lokerkotaternateinfo/",
            "https://www.instagram.com/lokerternate.top/",
            "https://www.instagram.com/info_loker_area_ternate/",
            "https://www.instagram.com/lokerternate.update/",
            "https://www.instagram.com/info_loker_ternate/"
        ],
        "resultsLimit": 6,
    }

    try:
        run = client.actor("apify/instagram-scraper").call(run_input=input_pencarian)
        print("✅ Data feed berhasil didapatkan. Mulai proses kurasi konten via AI...")

        ada_hasil = False
        dataset = client.dataset(run["defaultDatasetId"])

        for item in dataset.iterate_items():
            if "url" in item and "caption" in item:
                teks_caption = item.get("caption", "").strip()
                link_ig = item.get("url", "")

                if not teks_caption:
                    continue

                print("⏳ Menjaga jeda rate-limit API (4 detik)...")
                time.sleep(4)

                print("🔄 AI sedang membaca dan menganalisis satu pamflet loker...")
                keputusan_ai = saring_loker_dengan_ai(teks_caption)

                if "KEDALUWARSA" not in keputusan_ai.upper() and "GAGAL_MERANGKUM" not in keputusan_ai.upper():
                    ada_hasil = True
                    laporan = (
                        f"🚨 <b>INFO LOWONGAN KERJA BARU!</b>\n\n"
                        f"{keputusan_ai}\n\n"
                        f"🔗 <b>Buka Postingan:</b> {link_ig}"
                    )
                    kirim_telegram(laporan)
                    print("📲 Notifikasi loker valid berhasil dikirim ke Telegram!")
                else:
                    print("🗑️ Postingan tidak valid / telah kedaluwarsa. Dilewati otomatis.")

        if not ada_hasil:
            pesan_laporan = "🤖 <b>Radar Loker:</b> Pemindaian selesai. Hari ini belum ditemukan postingan loker baru yang valid."
            kirim_telegram(pesan_laporan)
            print("ℹ️ Tidak ada lowongan baru yang memenuhi kriteria.")

    except Exception as err:
        print(f"❌ Terjadi kesalahan pada pipeline bot: {err}")


if __name__ == "__main__":
    main()
