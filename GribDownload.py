import requests
from datetime import datetime, timedelta
import os

def download_gfs_48h():
    # 1. Ustawienia geograficzne (Twoje współrzędne)
    lon_min, lon_max = -3, 7
    lat_min, lat_max = 40, 60
    
    # 2. Dynamiczne ustalanie daty i najnowszego dostępnego runu (z zapasem 6h na przetworzenie)
    now = datetime.utcnow() - timedelta(hours=6)
    date_str = now.strftime("%Y%m%d")
    # Wybór najbliższego runu: 00, 06, 12, lub 18
    run_hour = (now.hour // 6) * 6
    run_str = f"{run_hour:02d}"

    print(f"Próba pobrania modelu GFS z dnia {date_str}, run: {run_str} UTC")

    base_url = "https://nomads.ncep.noaa.gov/cgi-bin/filter_gfs_0p25.pl"
    output_filename = "test.grb"
    
    # Usuwamy plik, jeśli istniał, aby zapisać nową paczkę
    if os.path.exists(output_filename):
        os.remove(output_filename)

    # 3. Pobieranie kroków co 3 godziny przez 48h (0, 3, 6... 48)
    for hour in range(0, 51, 3):
        forecast_hour = f"{hour:03d}"
        print(f"Pobieranie prognozy +{forecast_hour}h...", end="\r")
        
        params = {
            "file": f"gfs.t{run_str}z.pgrb2.0p25.f{forecast_hour}",
            "lev_10_m_above_ground": "on",
            "lev_surface": "on",
            "var_UGRD": "on",
            "var_VGRD": "on",
            "var_GUST": "on",
            "var_PRMSL": "on",
            "var_TMP": "on",
            "leftlon": lon_min,
            "rightlon": lon_max,
            "toplat": lat_max,
            "bottomlat": lat_min,
            "dir": f"/gfs.{date_str}/{run_str}/atmos"
        }

        try:
            response = requests.get(base_url, params=params, timeout=30)
            if response.status_code == 200:
                # Dopisujemy każdą "wiadomość" do jednego pliku (tryb "ab" - append binary)
                with open(output_filename, "ab") as f:
                    f.write(response.content)
            else:
                print(f"\nBłąd dla f{forecast_hour}: Kod {response.status_code} (Możliwe, że dane nie są jeszcze gotowe)")
        except Exception as e:
            print(f"\nBłąd połączenia: {e}")

    print(f"\nGotowe! Pełna prognoza zapisana w: {output_filename}")

if __name__ == "__main__":
    download_gfs_48h()