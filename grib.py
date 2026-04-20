import pygrib
import numpy as np
import os
from scipy.interpolate import RegularGridInterpolator
from datetime import datetime, timedelta
import math

def get_scampi_30_polars():
    """
    Defines and returns an interpolating function for Scampi 30 polar curves.
    Uses RegularGridInterpolator for 2D lookups based on TWA and TWS.
    """
    # Angles (Y-axis) and Wind Speeds (X-axis)
    twa_angles = [32, 36, 40, 45, 52, 60, 70, 80, 90, 100, 110, 120, 135, 150, 180]
    tws_speeds = [6, 8, 10, 12, 14, 16, 20]
    
    # Boat speed matrix (Vb) - rows are TWA, columns are TWS
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
    
    # Initialize interpolator with linear extrapolation support
    return RegularGridInterpolator((twa_angles, tws_speeds), data, bounds_error=False, fill_value=None)

def load_grib_to_memory(file_path):
    """
    Loads the entire GRIB file into RAM to avoid repeated disk I/O.
    Returns a dictionary with data, coordinates grid, and available dates.
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
        print(f"Error loading GRIB to memory: {e}")
        return None

def get_weather_from_cache(cache, target_lat, target_lon, target_time):
    """
    Retrieves weather data from memory cache.
    Finds the nearest time step and spatial grid point.
    """
    if not cache:
        return None

    all_dates = cache['dates']
    # Find the nearest time step
    closest_date = min(all_dates, key=lambda d: abs(d - target_time))
    # Approximation: if the time is outside the GRIB file date range
    approximated = (target_time < all_dates[0]) or (target_time > all_dates[-1])
    
    lats, lons = cache['lats'], cache['lons']
    # Find the nearest grid point (Nearest Neighbor)
    dist_sq = (lats - target_lat)**2 + (lons - target_lon)**2
    min_idx = np.unravel_index(np.argmin(dist_sq), dist_sq.shape)
    
    data_at_time = cache['data'][closest_date]
    
    # Extract wind components (handles naming variations)
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
    """Calculates the initial bearing between two points on the sphere."""
    d_lon = math.radians(lon2 - lon1)
    lat1_r = math.radians(lat1)
    lat2_r = math.radians(lat2)
    y = math.sin(d_lon) * math.cos(lat2_r)
    x = math.cos(lat1_r) * math.sin(lat2_r) - math.sin(lat1_r) * math.cos(lat2_r) * math.cos(d_lon)
    return (math.degrees(math.atan2(y, x)) + 360) % 360

def simulate_vmg_route(weather_cache, time_step_min=30.0):
    """
    Simulates a route optimizing VMG towards a target (North boundary, E-W center).
    Uses RAM cache for high performance.
    """
    if not weather_cache: return []
    
    lats, lons = weather_cache['lats'], weather_cache['lons']
    min_lat, max_lat = lats.min(), lats.max()
    min_lon, max_lon = lons.min(), lons.max()
    
    target_lat = max_lat
    target_lon = (min_lon + max_lon) / 2.0
    curr_lat, curr_lon = (min_lat + max_lat) / 2, (min_lon + max_lon) / 2
    
    print(f"\n--- OPTIMIZED VMG SIMULATION ---")
    print(f"Target on GRIB boundary: {target_lat:.4f}, {target_lon:.4f}")
    
    polars = get_scampi_30_polars()
    current_time = datetime.now().replace(second=0, microsecond=0)
    route_points = []
    step_count, total_dist_nm = 0, 0.0

    print(f"{'Step':<4} | {'Sim_Time':<8} | {'Lat':<8} | {'Lon':<8} | {'TWS[kt]':<7} | {'Hdg[°]':<7} | {'BS[kt]':<6} | {'VMG[kt]':<7} | {'A':<2}")
    print("-" * 105)

    while curr_lat < target_lat:
        weather = get_weather_from_cache(weather_cache, curr_lat, curr_lon, current_time)
        if not weather: break
            
        u, v = weather['wind_u'], weather['wind_v']
        tws = np.sqrt(u**2 + v**2) * 1.94384
        twd = (math.degrees(math.atan2(-u, -v)) + 360) % 360
        bearing_to_target = calculate_bearing(curr_lat, curr_lon, target_lat, target_lon)
        
        best_vmg, best_heading, best_bs = -99.0, 0, 0
        # Scan possible headings co 2 degrees
        for h in range(0, 360, 2):
            twa = abs(((twd - h + 180) % 360) - 180)
            if twa < 32: continue # Dead zone
            b_speed = polars([twa, tws])[0]
            vmg = b_speed * math.cos(math.radians(h - bearing_to_target))
            if vmg > best_vmg:
                best_vmg, best_heading, best_bs = vmg, h, b_speed
        
        dist_nm = best_bs * (time_step_min / 60.0)
        total_dist_nm += dist_nm
        route_points.append({'lat': curr_lat, 'lon': curr_lon, 'time': current_time})
        
        approx_flag = "*" if weather['meta']['approximated'] else " "
        print(f"{step_count:<4} | {current_time.strftime('%H:%M:%S'):<8} | {curr_lat:<8.4f} | {curr_lon:<8.4f} | {tws:<7.2f} | {best_heading:<7.0f} | {best_bs:<6.2f} | {best_vmg:<7.2f} | {approx_flag:<2}")
        
        curr_lat += (dist_nm * math.cos(math.radians(best_heading))) / 60.0
        curr_lon += (dist_nm * math.sin(math.radians(best_heading))) / (60.0 * math.cos(math.radians(curr_lat)))
        current_time += timedelta(minutes=time_step_min)
        step_count += 1
        if step_count > 500 or not (min_lon <= curr_lon <= max_lon): break

    print("-" * 105)
    total_time_h = (step_count * time_step_min) / 60.0
    avg_speed = total_dist_nm / total_time_h if total_time_h > 0 else 0
    print(f"VMG Finished: Distance {total_dist_nm:.2f} nm, Average Speed {avg_speed:.2f} kt.")
    return route_points

def simulate_manual_route(weather_cache, target_heading=45, time_step_min=30.0, start_pos="center"):
    """
    Manual simulation (fixed heading) using RAM cache.
    """
    if not weather_cache: return []
    lats, lons = weather_cache['lats'], weather_cache['lons']
    min_lat, max_lat = lats.min(), lats.max()
    min_lon, max_lon = lons.min(), lons.max()

    if start_pos == "center":
        curr_lat, curr_lon = (min_lat + max_lat) / 2, (min_lon + max_lon) / 2
    else:
        curr_lat, curr_lon = min_lat, min_lon

    print(f"\n--- OPTIMIZED MANUAL SIMULATION (Heading: {target_heading}°) ---")
    polars = get_scampi_30_polars()
    current_time = datetime.now().replace(second=0, microsecond=0)
    route_points = []
    step_count, total_dist_nm = 0, 0.0

    print(f"{'Step':<4} | {'Sim_Time':<8} | {'Lat':<8} | {'Lon':<8} | {'TWS[kt]':<7} | {'H_act[°]':<8} | {'BS[kt]':<6} | {'A':<2} | {'Status'}")
    print("-" * 95)

    while min_lat <= curr_lat <= max_lat and min_lon <= curr_lon <= max_lon:
        weather = get_weather_from_cache(weather_cache, curr_lat, curr_lon, current_time)
        if not weather: break
            
        u, v = weather['wind_u'], weather['wind_v']
        tws = np.sqrt(u**2 + v**2) * 1.94384
        twd = (math.degrees(math.atan2(-u, -v)) + 360) % 360
        
        twa = abs(((twd - target_heading + 180) % 360) - 180)
        actual_heading, status = target_heading, "OK"
        
        if twa < 45: # Dead zone correction
            status = "CORRECTED"
            h1, h2 = (twd + 45) % 360, (twd - 45) % 360
            diff1 = abs(((h1 - target_heading + 180) % 360) - 180)
            diff2 = abs(((h2 - target_heading + 180) % 360) - 180)
            actual_heading = h1 if diff1 < diff2 else h2
            twa = 45.0

        boat_speed = polars([twa, tws])[0]
        dist_nm = boat_speed * (time_step_min / 60.0)
        total_dist_nm += dist_nm
        route_points.append({'lat': curr_lat, 'lon': curr_lon, 'time': current_time})
        
        approx_flag = "*" if weather['meta']['approximated'] else " "
        print(f"{step_count:<4} | {current_time.strftime('%H:%M:%S'):<8} | {curr_lat:<8.4f} | {curr_lon:<8.4f} | {tws:<7.2f} | {actual_heading:<8.0f} | {boat_speed:<6.2f} | {approx_flag:<2} | {status}")
        
        curr_lat += (dist_nm * math.cos(math.radians(actual_heading))) / 60.0
        curr_lon += (dist_nm * math.sin(math.radians(actual_heading))) / (60.0 * math.cos(math.radians(curr_lat)))
        current_time += timedelta(minutes=time_step_min)
        step_count += 1
        if step_count > 500: break

    print("-" * 95)
    total_time_h = (step_count * time_step_min) / 60.0
    avg_speed = total_dist_nm / total_time_h if total_time_h > 0 else 0
    print(f"Manual Finished: Distance {total_dist_nm:.2f} nm, Average Speed {avg_speed:.2f} kt.")
    return route_points

def analyze_grib_performance(file_path):
    """Scans GRIB file and displays comprehensive diagnostics."""
    print(f"--- COMPREHENSIVE GRIB DIAGNOSTICS ---")
    if not os.path.exists(file_path):
        print(f"ERROR: File '{file_path}' does not exist.")
        return
    try:
        grbs = pygrib.open(file_path)
        all_dates = sorted(list(set(grb.validDate for grb in grbs)))
        params = set(grb.name for grb in grbs)
        
        print(f"Location: {os.path.abspath(file_path)}")
        print(f"Time Range: {all_dates[0]} to {all_dates[-1]}")
        print(f"Parameters: {', '.join(params)}")
        
        grbs.seek(0)
        m = grbs.readline()
        lats, lons = m.latlons()
        print(f"Grid: Lat {lats.min():.2f}:{lats.max():.2f}, Lon {lons.min():.2f}:{lons.max():.2f}")
        print("-" * 50)
        grbs.close()
    except Exception as e:
        print(f"Diagnostics error: {e}")

def save_to_gpx(points, filename="route.gpx"):
    """Saves route points to a GPX file."""
    header = ['<?xml version="1.0" encoding="UTF-8"?>', '<gpx version="1.1" creator="ScampiRouter"><trk><trkseg>']
    footer = ['</trkseg></trk></gpx>']
    body = [f'<trkpt lat="{p["lat"]:.6f}" lon="{p["lon"]:.6f}"><time>{p["time"].strftime("%Y-%m-%dT%H:%M:%SZ")}</time></trkpt>' for p in points]
    with open(filename, 'w') as f: f.write('\n'.join(header + body + footer))
    print(f"GPX track saved: {filename}")

if __name__ == "__main__":
    file_name = "test.grb2"
    
    # 1. File Diagnostics
    analyze_grib_performance(file_name)
    
    # 2. Loading data to RAM
    print(f"Loading GRIB data into RAM...")
    weather_cache = load_grib_to_memory(file_name)
    
    if weather_cache:
        # 3. Select Simulation Mode
        
        # VMG Mode
        vmg_pts = simulate_vmg_route(weather_cache, time_step_min=1.0)
        if vmg_pts:
            save_to_gpx(vmg_pts, "scampi_vmg.gpx")
            
        # Manual Mode (optional)
        # manual_pts = simulate_manual_route(weather_cache, target_heading=45, time_step_min=30.0)
        # if manual_pts:
        #     save_to_gpx(manual_pts, "scampi_manual.gpx")
    else:
        print("Failed to load weather data.")