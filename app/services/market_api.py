import httpx
from bs4 import BeautifulSoup
import logging
import re

logger = logging.getLogger("uvicorn.error")

async def get_realtime_market_prices() -> dict:
    """
    Mengambil data real-time harga komoditi tingkat petani dari portal BAPPEBTI.
    Mereduksi data mentah berbasis struktur kartu (card layout) menjadi kamus (dict) 
    harga komoditas rata-rata yang bersih dan siap digunakan oleh engine AI.
    """
    url = "https://infoharga.bappebti.go.id/harga_komoditi_petani"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
    }
    
    # Dictionary sementara untuk menampung list harga guna menghitung rata-rata regional
    temp_prices = {}
    
    try:
        limits = httpx.Limits(max_keepalive_connections=5, max_connections=10)
        async with httpx.AsyncClient(timeout=12.0, limits=limits, follow_redirects=True) as client:
            response = await client.get(url, headers=headers)
            
            if response.status_code != 200:
                logger.warning(f"BAPPEBTI merespon dengan status code: {response.status_code}")
                return {}
                
            soup = BeautifulSoup(response.text, "html.parser")
            
            # 1. MENYIAR KARTU DATA (Berdasarkan Inspect Elemen panel-body)
            cards = soup.find_all("div", class_=re.compile(r"panel-body"))
            
            if not cards:
                logger.error("Gagal menemukan elemen struktur kartu (panel-body) di halaman BAPPEBTI.")
                return {}
                
            for card in cards:
                name_tag = card.find("h5")
                price_tag = card.find("h3", class_=re.compile(r"text-right"))
                
                if name_tag and price_tag:
                    # 2. EKSTRAKSI & PEMBERSIHAN NAMA KOMODITAS
                    # Mengubah menjadi lowercase dan menghapus spasi berlebih
                    komoditi_raw = name_tag.text.strip().lower()
                    komoditi_raw = re.sub(r"\s+", " ", komoditi_raw)
                    # Memisahkan nama wilayah (Contoh: "bawang merah - brebes" -> "bawang merah")
                    nama_komoditi = komoditi_raw.split("-")[0].strip()
                    
                    # 3. EKSTRAKSI & PEMBERSIHAN NOMINAL HARGA
                    harga_raw = price_tag.text.strip()
                    harga_digits = re.sub(r"[^\d]", "", harga_raw)  # Hanya ambil karakter angka
                    
                    if not harga_digits:
                        continue
                        
                    try:
                        harga_val = float(harga_digits)
                        
                        # Gabungkan harga ke dalam list untuk komoditas yang sama
                        if nama_komoditi in temp_prices:
                            temp_prices[nama_komoditi].append(harga_val)
                        else:
                            temp_prices[nama_komoditi] = [harga_val]
                    except ValueError:
                        continue
            
            # 4. REDUKSI DATA: Menghitung rata-rata nasional/regional dari komoditas yang sama
            realtime_prices = {}
            for komoditas, list_harga in temp_prices.items():
                rata_rata = sum(list_harga) / len(list_harga)
                realtime_prices[komoditas] = round(rata_rata, 2)
            
            if not realtime_prices:
                logger.error("Gagal mengekstrak data harga valid dari elemen kartu BAPPEBTI.")
                return {}
                
            logger.info(f"BAPPEBTI Data successfully retrieved & reduced via Card Engine: {realtime_prices}")
            return realtime_prices
                
    except httpx.TimeoutException:
        logger.error("Sinkronisasi gagal: Timeout saat menghubungi server BAPPEBTI.")
    except Exception as e:
        logger.error(f"Gagal melakukan sinkronisasi dengan BAPPEBTI: {str(e)}")
        
    return {}


async def get_realtime_fertilizer_prices() -> dict:
    """
    Mengambil HET (Harga Eceran Tertinggi) pupuk bersubsidi sesuai
    Permentan No. 47/SR.310/12/2017 Pasal 11.
    """
    baseline_het = {
        "urea":         1800.0,   # Permentan No. 47/2017
        "sp-36":        2000.0,   # Permentan No. 47/2017
        "za":           1400.0,   # Permentan No. 47/2017
        "npk phonska":  2300.0,   # Permentan No. 47/2017
        "organik":       500.0,   # Permentan No. 47/2017
        "kcl":          9500.0,   # Estimasi pasar non-subsidi
    }
    
    try:
        logger.info("Menggunakan HET pupuk bersubsidi sesuai Permentan No. 47/SR.310/12/2017 Pasal 11.")
        return baseline_het
    except Exception as e:
        logger.error(f"Fertilizer price sync failed: {str(e)}. Using baseline.")
        return baseline_het