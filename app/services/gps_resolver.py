import httpx
import logging

logger = logging.getLogger("uvicorn.error")

async def get_elevation_from_gps(lat: float, lon: float) -> int:
    """
    Mengambil data ketinggian (mdpl) berdasarkan koordinat menggunakan Open-Meteo Elevation API.
    """
    url = f"https://api.open-meteo.com/v1/elevation?latitude={lat}&longitude={lon}"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                data = resp.json()
                elevation_list = data.get("elevation", [])
                if elevation_list:
                    elev = int(elevation_list[0])
                    logger.info(f"Open-Meteo GPS Elevation: {elev} mdpl")
                    return elev
    except Exception as e:
        logger.error(f"Error fetching elevation from GPS: {str(e)}")
    return 150  # Fallback standard lowland elevation

async def get_location_name_from_gps(lat: float, lon: float) -> str:
    """
    Melakukan reverse geocoding berdasarkan koordinat menggunakan OpenStreetMap Nominatim API.
    """
    url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lon}&zoom=10"
    headers = {"User-Agent": "AgroAI-App/1.0 (agroai@example.com)"}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                address = data.get("address", {})
                state = address.get("state") or address.get("region")
                city = address.get("city") or address.get("county") or address.get("municipality") or address.get("suburb")
                
                parts = []
                if city:
                    parts.append(city)
                if state:
                    parts.append(state)
                
                if parts:
                    loc_name = ", ".join(parts)
                    logger.info(f"OSM Nominatim GPS Location: {loc_name}")
                    return loc_name
    except Exception as e:
        logger.error(f"Error reverse geocoding GPS coordinate: {str(e)}")
    return "Indonesia (GPS)"

def get_soil_type_from_gps(lat: float, lon: float, elevation: int) -> str:
    """
    Mengklasifikasikan jenis tanah secara otomatis berdasarkan koordinat dan ketinggian (Indonesia context).
    """
    # 1. Ketinggian tinggi (dataran tinggi pegunungan vulkanik) -> Andosol
    if elevation >= 800:
        return "Andosol"
    
    # 2. Daerah rawa gambut di dataran rendah Sumatra, Kalimantan, Papua
    # Sumatra peatland box: lat [-6.0, 6.0], lon [95.0, 106.0]
    # Kalimantan peatland box: lat [-4.5, 4.5], lon [108.0, 119.0]
    # Papua peatland box: lat [-9.0, 0.0], lon [130.0, 141.0]
    if elevation < 80:
        in_sumatra = -6.0 <= lat <= 6.0 and 95.0 <= lon <= 106.0
        in_kalimantan = -4.5 <= lat <= 4.5 and 108.0 <= lon <= 119.0
        in_papua = -9.0 <= lat <= 0.0 and 130.0 <= lon <= 141.0
        if in_sumatra or in_kalimantan or in_papua:
            return "Gambut"
            
    # 3. Kawasan pantai berpasir (elevasi sangat rendah di dekat garis pantai)
    if elevation < 15:
        return "Pasir"
        
    # 4. Daerah perbukitan kering kapur/karst (misal: bagian selatan Jawa) -> Laterit
    if -9.0 <= lat <= -7.0 and 110.0 <= lon <= 115.0 and 200 <= elevation < 800:
        return "Laterit"
        
    # 5. Lembah sungai atau sawah irigasi dataran rendah -> Aluvial
    if elevation < 200:
        return "Aluvial"
        
    # 6. Default tanah liat/lempung (Liat) untuk dataran sedang
    return "Liat"
