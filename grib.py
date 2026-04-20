import pygrib
import numpy as np
import os
from scipy.interpolate import RegularGridInterpolator
from datetime import datetime, timedelta
import math
from collections import deque

def get_scampi_30_polars():
    """
    Definiuje i zwraca funkcję interpolującą dla krzywych polarnych jachtu Scampi 30.
    Używa RegularGridInterpolator do wyszukiwania 2D na podstawie TWA i TWS.
    """
    # Kąty (oś Y) i prędkości wiatru (oś X)
    twa_angles = [32, 36, 40, 45, 52, 60, 70, 80, 90, 100, 110, 120, 135, 150, 180]
    tws_speeds = [6, 8, 10, 12, 14, 16, 20]
    
    # Macierz prędkości jachtu (Vb) - rzędy to TWA, kolumny to TWS
    data = np.array([
        [2.8, 3.8, 4.6, 5.1, 5.3, 5.4, 5.4], # 32°
        [3.2, 4.3, 5.1, 5.5, 5.7, 5.8, 5.8], # 36°
        [3.6, 4.7, 5.4, 5.8, 6.0, 6.1, 6.2], # 40°
        [4.0, 5.1, 5.7, 6.1, 6.3, 6.4, 6.5], # 45°
        [4.4, 5.5, 6.0, 6.4, 6.6, 6.7, 6.9], # 52°
        [4.8, 5.8, 6.3, 6.6, 6.8, 7.0, 7.2], # 60°
        [5.1, 6.0, 6.5, 6.8, 7.1, 7.3, 7.5], # 70°
        [5.2, 6.1, 6.6, 7.0, 7.3, 7.5, 7.8], # 80°
        [5.3, 6.3, 6.8, 7.1, 7.4, 7.7, 8.1], # 90°
        [5.4, 6.4, 6.9, 7.3, 7.6, 7.9, 8.4], # 100°
        [5.3, 6.4, 7.0, 7.4, 7.8, 8.1, 8.6], # 110°
        [5.0, 6.2, 6.9, 7.3, 7.7, 8.1, 8.7], # 120°
        [4.3, 5.5, 6.4, 7.0, 7.4, 7.8, 8.5], # 135°
        [3.6, 4.7, 5.6, 6.4, 7.0, 7.4, 8.1], # 150°
        [3.1, 4.1, 5.0, 5.8, 6.4, 6.9, 7.6]  # 180°
    ])
    
    return RegularGridInterpolator((twa_angles, tws_speeds), data, bounds_error=False, fill_value=None)

def load_grib_to_memory(file_path):
    """
    Wczytuje cały plik GRIB do pamięci RAM, aby uniknąć powtarzalnych operacji I/O.
    """
    if not os.path.exists(file_path):
        return None
    
    weather_cache = {}
    all_dates = set()
    lats, lons = None, None
    
    try:
        grbs = pygrib.open(file_path)
        for msg in grbs:
            dt = msg.validDate
            all_dates.add(dt)
            param = msg.name
            
            if lats is None:
                lats, lons = msg.latlons()
                
            if dt not in weather_cache:
                weather_cache[dt] = {}
            
            weather_cache[dt][param] = msg.values
            
        grbs.close()
        return {
            'data': weather_cache,
            'dates': sorted(list(all_dates)),
            'lats': lats,
            'lons': lons
        }
    except Exception as e:
        print(f"Błąd podczas ładowania pliku GRIB do pamięci: {e}")
        return None

def get_weather_from_cache(cache, target_lat, target_lon, target_time):
    """
    Pobiera dane pogodowe z cache. Znajduje najbliższy krok czasowy i punkt siatki.
    """
    if not cache:
        return None

    all_dates = cache['dates']
    closest_date = min(all_dates, key=lambda d: abs(d - target_time))
    approximated = (target_time < all_dates[0]) or (target_time > all_dates[-1])
    
    lats, lons = cache['lats'], cache['lons']
    dist_sq = (lats - target_lat)**2 + (lons - target_lon)**2
    min_idx = np.unravel_index(np.argmin(dist_sq), dist_sq.shape)
    
    data_at_time = cache['data'][closest_date]
    
    u_val = data_at_time.get('10 metre U wind component')[min_idx]
    v_key = '10 metre v wind component' if '10 metre v wind component' in data_at_time else '10 metre V wind component'
    v_val = data_at_time.get(v_key)[min_idx]
    
    results = {
        'meta': {
            'actual_lat': lats[min_idx],
            'actual_lon': lons[min_idx],
            'time': closest_date,
            'approximated': approximated
        },
        'wind_u': u_val,
        'wind_v': v_val
    }
    return results

def calculate_bearing(lat1, lon1, lat2, lon2):
    """Oblicza początkowy namiar między dwoma punktami na sferze."""
    d_lon = math.radians(lon2 - lon1)
    lat1_r = math.radians(lat1)
    lat2_r = math.radians(lat2)
    y = math.sin(d_lon) * math.cos(lat2_r)
    x = math.cos(lat1_r) * math.sin(lat2_r) - math.sin(lat1_r) * math.cos(lat2_r) * math.cos(d_lon)
    return (math.degrees(math.atan2(y, x)) + 360) % 360

def identify_weather_danger_zones(cache, min_threshold, max_threshold=float('inf')):
    """
    Identyfikuje punkty siatki w danym zakresie prędkości wiatru.
    Zwraca informację o pierwszym wystąpieniu niebezpieczeństwa.
    """
    if not cache:
        return []

    lats, lons, dates = cache['lats'], cache['lons'], cache['dates']
    found_mask = np.zeros(lats.shape, dtype=bool)
    first_time_grid = np.empty(lats.shape, dtype=object)
    first_speed_grid = np.zeros(lats.shape)
    
    for dt in dates:
        data_at_time = cache['data'][dt]
        u = data_at_time.get('10 metre U wind component')
        v_key = '10 metre v wind component' if '10 metre v wind component' in data_at_time else '10 metre V wind component'
        v = data_at_time.get(v_key)
        
        if u is not None and v is not None:
            tws_grid = np.sqrt(u**2 + v**2) * 1.94384
            in_range = (tws_grid > min_threshold) & (tws_grid <= max_threshold)
            exceed_mask = in_range & (~found_mask)
            
            if np.any(exceed_mask):
                first_time_grid[exceed_mask] = dt
                first_speed_grid[exceed_mask] = tws_grid[exceed_mask]
                found_mask |= exceed_mask
    
    indices = np.where(found_mask)
    return [{'lat': lats[r, c], 'lon': lons[r, c], 'speed': first_speed_grid[r, c], 'time': first_time_grid[r, c]} for r, c in zip(*indices)]

def identify_safe_sailing_areas(cache, max_wind_threshold=20.0):
    """
    Wyznacza środki kwadratów bezpiecznych (wiatr cały czas <= threshold).
    """
    if not cache:
        return {}

    lats, lons, dates = cache['lats'], cache['lons'], cache['dates']
    safe_mask = np.ones(lats.shape, dtype=bool)
    max_observed_speed = np.zeros(lats.shape)

    for dt in dates:
        data_at_time = cache['data'][dt]
        u = data_at_time.get('10 metre U wind component')
        v_key = '10 metre v wind component' if '10 metre v wind component' in data_at_time else '10 metre V wind component'
        v = data_at_time.get(v_key)
        
        if u is not None and v is not None:
            tws_grid = np.sqrt(u**2 + v**2) * 1.94384
            safe_mask &= (tws_grid <= max_wind_threshold)
            max_observed_speed = np.maximum(max_observed_speed, tws_grid)

    indices = np.where(safe_mask)
    return {(r, c): {'lat': lats[r, c], 'lon': lons[r, c], 'max_speed': max_observed_speed[r, c]} for r, c in zip(*indices)}

def generate_reachable_graph(cache, safe_points_map, start_lat, start_lon, target_lat, target_lon):
    """
    Buduje graf osiągalnych bezpiecznych punktów siatki (+- 50 stopni).
    """
    if not safe_points_map:
        return []

    lats, lons = cache['lats'], cache['lons']
    dist_sq = (lats - start_lat)**2 + (lons - start_lon)**2
    
    min_d = float('inf')
    start_node = None
    for (r, c) in safe_points_map.keys():
        d = dist_sq[r, c]
        if d < min_d:
            min_d, start_node = d, (r, c)

    if not start_node:
        return []

    reachable_nodes = {start_node}
    queue = deque([start_node])
    
    while queue:
        r, c = queue.popleft()
        curr_p = safe_points_map[(r, c)]
        bearing_to_target = calculate_bearing(curr_p['lat'], curr_p['lon'], target_lat, target_lon)
        
        for dr in [-1, 0, 1]:
            for dc in [-1, 0, 1]:
                if dr == 0 and dc == 0: continue
                neighbor = (r + dr, c + dc)
                
                if neighbor in safe_points_map and neighbor not in reachable_nodes:
                    n_p = safe_points_map[neighbor]
                    bearing_to_neighbor = calculate_bearing(curr_p['lat'], curr_p['lon'], n_p['lat'], n_p['lon'])
                    angle_diff = abs(((bearing_to_neighbor - bearing_to_target + 180) % 360) - 180)
                    
                    if angle_diff <= 50.0:
                        reachable_nodes.add(neighbor)
                        queue.append(neighbor)
    
    return [safe_points_map[node] for node in reachable_nodes]

def simulate_vmg_route(weather_cache, start_lat=53.25, start_lon=2.6, time_step_min=30.0):
    """
    Symuluje trasę optymalizując VMG.
    """
    if not weather_cache: return []
    lats, lons = weather_cache['lats'], weather_cache['lons']
    target_lat, target_lon = lats.max(), (lons.min() + lons.max()) / 2.0
    curr_lat, curr_lon = start_lat, start_lon
    
    print(f"\n--- SYMULACJA VMG ---")
    print(f"Start: {curr_lat}, {curr_lon} | Cel: {target_lat:.4f}, {target_lon:.4f}")
    
    polars = get_scampi_30_polars()
    current_time = datetime.now().replace(second=0, microsecond=0)
    route_points = []
    step_count, total_dist_nm = 0, 0.0

    print(f"{'Krok':<4} | {'Czas_SIM':<8} | {'Lat':<8} | {'Lon':<8} | {'TWS[kt]':<7} | {'Hdg[°]':<7} | {'BS[kt]':<6} | {'VMG[kt]':<7} | {'A':<2}")
    print("-" * 110)

    while curr_lat < target_lat:
        weather = get_weather_from_cache(weather_cache, curr_lat, curr_lon, current_time)
        if not weather: break
            
        u, v = weather['wind_u'], weather['wind_v']
        tws = np.sqrt(u**2 + v**2) * 1.94384
        twd = (math.degrees(math.atan2(-u, -v)) + 360) % 360
        bearing_to_target = calculate_bearing(curr_lat, curr_lon, target_lat, target_lon)
        
        best_vmg, best_hdg, best_bs = -99.0, 0, 0
        for h in range(0, 360, 2):
            twa = abs(((twd - h + 180) % 360) - 180)
            if twa < 32: continue
            b_speed = polars([twa, tws])[0]
            vmg = b_speed * math.cos(math.radians(h - bearing_to_target))
            if vmg > best_vmg:
                best_vmg, best_hdg, best_bs = vmg, h, b_speed
        
        dist_nm = best_bs * (time_step_min / 60.0)
        total_dist_nm += dist_nm
        route_points.append({'lat': curr_lat, 'lon': curr_lon, 'time': current_time})
        
        approx = "*" if weather['meta']['approximated'] else " "
        print(f"{step_count:<4} | {current_time.strftime('%H:%M:%S'):<8} | {curr_lat:<8.4f} | {curr_lon:<8.4f} | {tws:<7.2f} | {best_hdg:<7.0f} | {best_bs:<6.2f} | {best_vmg:<7.2f} | {approx:<2}")
        
        curr_lat += (dist_nm * math.cos(math.radians(best_hdg))) / 60.0
        curr_lon += (dist_nm * math.sin(math.radians(best_hdg))) / (60.0 * math.cos(math.radians(curr_lat)))
        current_time += timedelta(minutes=time_step_min)
        step_count += 1
        if step_count > 500 or not (lons.min() <= curr_lon <= lons.max()): break

    print("-" * 110)
    print(f"Koniec VMG: Dystans {total_dist_nm:.2f} nm.")
    return route_points

def save_danger_zones_to_gpx(points, filename, layer_name, symbol="Danger Area"):
    """Zapisuje punkty niebezpieczne do GPX."""
    header = ['<?xml version="1.0" encoding="UTF-8"?>', f'<gpx version="1.1"><metadata><name>{layer_name}</name></metadata>']
    body = []
    for p in points:
        time_iso = p['time'].strftime('%Y-%m-%dT%H:%M:%SZ')
        body.append(f'  <wpt lat="{p["lat"]:.6f}" lon="{p["lon"]:.6f}"><time>{time_iso}</time><name>{p["speed"]:.1f}kt</name><sym>{symbol}</sym></wpt>')
    footer = ['</gpx>']
    with open(filename, 'w', encoding='utf-8') as f: f.write('\n'.join(header + body + footer))
    print(f"[SUKCES] Zapisano {len(points)} punktów do {filename}")

def save_to_gpx(points, filename="route.gpx"):
    """Zapisuje ślad trasy do GPX."""
    header = ['<?xml version="1.0" encoding="UTF-8"?>', '<gpx version="1.1"><trk><trkseg>']
    body = [f'  <trkpt lat="{p["lat"]:.6f}" lon="{p["lon"]:.6f}"><time>{p["time"].strftime("%Y-%m-%dT%H:%M:%SZ")}</time></trkpt>' for p in points]
    footer = ['</trkseg></trk></gpx>']
    with open(filename, 'w', encoding='utf-8') as f: f.write('\n'.join(header + body + footer))
    print(f"[SUKCES] Zapisano ślad do {filename}")

def analyze_grib_performance(file_path):
    """Diagnostyka pliku GRIB."""
    if not os.path.exists(file_path): return
    grbs = pygrib.open(file_path)
    msg = grbs.readline(); lats, lons = msg.latlons()
    min_lat, max_lat, min_lon, max_lon = lats.min(), lats.max(), lons.min(), lons.max()
    avg_lat = (min_lat + max_lat) / 2.0
    sn_nm, ew_nm = (max_lat - min_lat) * 60.0, (max_lon - min_lon) * 60.0 * math.cos(math.radians(avg_lat))
    print(f"--- DIAGNOSTYKA GRIB ---\nZakres: Lat {min_lat:.2f}:{max_lat:.2f}, Lon {min_lon:.2f}:{max_lon:.2f}")
    print(f"Wymiary: S-N: {sn_nm:.2f} nm, E-W: {ew_nm:.2f} nm\n" + "-"*50)
    grbs.close()

if __name__ == "__main__":
    file_name = "test.grb2"
    analyze_grib_performance(file_name)
    weather_cache = load_grib_to_memory(file_name)
    
    if weather_cache:
        lats, lons = weather_cache['lats'], weather_cache['lons']
        target_lat, target_lon = lats.max(), (lons.min() + lons.max()) / 2.0
        start_lat, start_lon = 53.25, 2.6

        # 1. Obszary zagrożenia
        print("Identyfikacja stref wiatrowych...")
        forbidden = identify_weather_danger_zones(weather_cache, 30.0)
        save_danger_zones_to_gpx(forbidden, "forbidden_areas.gpx", "Forbidden (>30kt)")
        
        not_recommended = identify_weather_danger_zones(weather_cache, 20.0, 30.0)
        save_danger_zones_to_gpx(not_recommended, "not_recommended.gpx", "Caution (20-30kt)", symbol="Waypoint")

        # 2. Bezpieczna siatka i graf
        print("Analiza bezpiecznej siatki...")
        safe_map = identify_safe_sailing_areas(weather_cache, 20.0)
        reachable = generate_reachable_graph(weather_cache, safe_map, start_lat, start_lon, target_lat, target_lon)
        
        header_safe = ['<?xml version="1.0" encoding="UTF-8"?>', '<gpx version="1.1"><metadata><name>Reachable Grid</name></metadata>']
        body_safe = [f'  <wpt lat="{p["lat"]:.6f}" lon="{p["lon"]:.6f}"><name>GRID</name><sym>Circle</sym></wpt>' for p in reachable]
        with open("reachable_safe_points.gpx", "w") as f: f.write('\n'.join(header_safe + body_safe + ['</gpx>']))
        print(f"[SUKCES] Zapisano {len(reachable)} punktów osiągalnych.")

        # 3. Symulacja trasy
        vmg_pts = simulate_vmg_route(weather_cache, start_lat, start_lon, time_step_min=0.0)
        if vmg_pts:
            save_to_gpx(vmg_pts, "scampi_vmg.gpx")
    else:
        print("Błąd wczytywania pliku.")