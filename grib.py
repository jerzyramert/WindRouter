import pygrib
import numpy as np
import os
from scipy.interpolate import RegularGridInterpolator
from datetime import datetime, timedelta
import math

def get_scampi_30_polars():
    """
    Defines and returns an interpolating function for Scampi 30 polar curves.
    Uses RegularGridInterpolator for 2D lookups.
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

def save_to_gpx(points, filename="route.gpx"):
    """
    Saves a list of coordinates to a GPX format file.
    """
    gpx_header = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<gpx version="1.1" creator="Scampi30Router" xmlns="http://www.topografix.com/GPX/1/1">',
        '  <trk>',
        '    <name>Scampi 30 Route</name>',
        '    <trkseg>'
    ]
    
    gpx_footer = [
        '    </trkseg>',
        '  </trk>',
        '</gpx>'
    ]
    
    body = []
    for p in points:
        time_str = p['time'].strftime('%Y-%m-%dT%H:%M:%SZ')
        body.append(f'      <trkpt lat="{p["lat"]:.6f}" lon="{p["lon"]:.6f}"><time>{time_str}</time></trkpt>')
    
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            f.write('\n'.join(gpx_header + body + gpx_footer))
        print(f"\n[SUCCESS] GPX track saved to: {filename}")
    except Exception as e:
        print(f"Error saving GPX file: {e}")

def get_weather_at_point(file_path, target_lat, target_lon, target_time=None):
    """
    Extracts weather data for a specific coordinate and time.
    Searches for the nearest time step in the GRIB file.
    Approximation flag is set only if target_time is outside the file range.
    """
    if not os.path.exists(file_path):
        return None

    results = {}
    try:
        grbs = pygrib.open(file_path)
        all_dates = sorted(list(set(grb.validDate for grb in grbs)))
        
        if not all_dates:
            grbs.close()
            return None

        # Approximation occurs when the target time is outside the GRIB file range
        min_date = all_dates[0]
        max_date = all_dates[-1]
        approximated = (target_time < min_date) or (target_time > max_date)
        
        # Find the closest available time step
        closest_date = min(all_dates, key=lambda d: abs(d - target_time))
        selected_grbs = grbs.select(validDate=closest_date)

        first_msg = selected_grbs[0]
        lats, lons = first_msg.latlons()
        
        # Find nearest spatial grid point
        dist_sq = (lats - target_lat)**2 + (lons - target_lon)**2
        min_idx = np.unravel_index(np.argmin(dist_sq), dist_sq.shape)
        
        results['meta'] = {
            'actual_lat': lats[min_idx],
            'actual_lon': lons[min_idx],
            'time': closest_date,
            'approximated': approximated
        }
        results['data'] = {}

        for msg in selected_grbs:
            val = msg.values[min_idx]
            results['data'][msg.name] = {'value': val, 'units': msg.units}

        grbs.close()
        return results
    except Exception as e:
        print(f"Error extracting weather data: {e}")
        return None

def calculate_bearing(lat1, lon1, lat2, lon2):
    """Calculates the bearing from point 1 to point 2."""
    d_lon = math.radians(lon2 - lon1)
    lat1_r = math.radians(lat1)
    lat2_r = math.radians(lat2)
    y = math.sin(d_lon) * math.cos(lat2_r)
    x = math.cos(lat1_r) * math.sin(lat2_r) - math.sin(lat1_r) * math.cos(lat2_r) * math.cos(d_lon)
    bearing = math.degrees(math.atan2(y, x))
    return (bearing + 360) % 360

def simulate_vmg_route(file_path, time_step_min=10.0):
    """
    Mode 1: VMG optimization simulation towards a target (North border, E-W center).
    The yacht automatically selects the most favorable tack.
    """
    try:
        grbs = pygrib.open(file_path)
        msg = grbs.readline()
        lats, lons = msg.latlons()
        min_lat, max_lat = lats.min(), lats.max()
        min_lon, max_lon = lons.min(), lons.max()
        grbs.close()
    except Exception as e:
        print(f"Error initializing VMG simulation: {e}")
        return []

    target_lat = max_lat
    target_lon = (min_lon + max_lon) / 2.0
    curr_lat, curr_lon = (min_lat + max_lat) / 2, (min_lon + max_lon) / 2
    
    print(f"\n--- VMG OPTIMIZATION SIMULATION ---")
    print(f"Target on GRIB boundary: {target_lat:.4f}, {target_lon:.4f}")
    
    polars = get_scampi_30_polars()
    current_time = datetime.now().replace(second=0, microsecond=0)
    route_points = []
    step_count = 0
    total_dist_nm = 0.0

    print(f"{'Step':<4} | {'Sim_Time':<8} | {'Grib_Time':<8} | {'Lat':<8} | {'Lon':<8} | {'TWS[kt]':<7} | {'Hdg_act[°]':<10} | {'TWA[°]':<6} | {'BS[kt]':<6} | {'VMG[kt]':<7} | {'A':<2}")
    print("-" * 145)

    while curr_lat < target_lat and min_lon <= curr_lon <= max_lon:
        weather = get_weather_at_point(file_path, curr_lat, curr_lon, target_time=current_time)
        if not weather or '10 metre U wind component' not in weather['data']: break
            
        u = weather['data']['10 metre U wind component']['value']
        # Handle potential case variations in GRIB parameter names
        v_key = '10 metre v wind component' if '10 metre v wind component' in weather['data'] else '10 metre V wind component'
        v = weather['data'][v_key]['value']
        
        tws = np.sqrt(u**2 + v**2) * 1.94384
        twd = (math.degrees(math.atan2(-u, -v)) + 360) % 360
        bearing_to_target = calculate_bearing(curr_lat, curr_lon, target_lat, target_lon)
        
        best_vmg, best_heading, best_bs = -99.0, 0, 0
        for h in range(0, 360, 2):
            twa = abs(((twd - h + 180) % 360) - 180)
            if twa < 32: continue # Dead zone check
            b_speed = polars([twa, tws])[0]
            vmg = b_speed * math.cos(math.radians(h - bearing_to_target))
            if vmg > best_vmg:
                best_vmg, best_heading, best_bs = vmg, h, b_speed
        
        dist_nm = best_bs * (time_step_min / 60.0)
        total_dist_nm += dist_nm
        route_points.append({'lat': curr_lat, 'lon': curr_lon, 'time': current_time})
        
        approx = "*" if weather['meta']['approximated'] else " "
        print(f"{step_count:<4} | {current_time.strftime('%H:%M:%S'):<8} | {weather['meta']['time'].strftime('%H:%M:%S'):<8} | {curr_lat:<8.4f} | {curr_lon:<8.4f} | {tws:<7.2f} | {best_heading:<10.0f} | {abs(((twd - best_heading + 180) % 360) - 180):<6.1f} | {best_bs:<6.2f} | {best_vmg:<7.2f} | {approx:<2}")
        
        curr_lat += (dist_nm * math.cos(math.radians(best_heading))) / 60.0
        curr_lon += (dist_nm * math.sin(math.radians(best_heading))) / (60.0 * math.cos(math.radians(curr_lat)))
        current_time += timedelta(minutes=time_step_min)
        step_count += 1
        if step_count > 500: break

    print("-" * 145)
    total_time_h = (step_count * time_step_min) / 60.0
    avg_speed = total_dist_nm / total_time_h if total_time_h > 0 else 0
    print(f"VMG Summary: Total Distance {total_dist_nm:.2f} nm, Average Speed {avg_speed:.2f} kt.")
    return route_points

def simulate_manual_route(file_path, target_heading=45, time_step_min=10.0, start_pos="center"):
    """
    Mode 2: Manual simulation (fixed heading).
    Bears away from the wind if the heading leads into the dead zone.
    """
    print(f"\n--- MANUAL SIMULATION (TARGET HEADING: {target_heading}°) ---")
    try:
        grbs = pygrib.open(file_path)
        msg = grbs.readline()
        lats, lons = msg.latlons()
        min_lat, max_lat = lats.min(), lats.max()
        min_lon, max_lon = lons.min(), lons.max()
        grbs.close()
    except Exception as e:
        print(f"Error initializing manual simulation: {e}")
        return []

    if start_pos == "center": curr_lat, curr_lon = (min_lat + max_lat) / 2, (min_lon + max_lon) / 2
    elif start_pos == "top_right": curr_lat, curr_lon = max_lat, max_lon
    else: curr_lat, curr_lon = min_lat, min_lon

    polars = get_scampi_30_polars()
    current_time = datetime.now().replace(second=0, microsecond=0)
    route_points = []
    step_count = 0
    total_dist_nm = 0.0

    print(f"{'Step':<4} | {'Sim_Time':<8} | {'Grib_Time':<8} | {'Lat':<8} | {'Lon':<8} | {'TWS[kt]':<7} | {'Hdg_act[°]':<10} | {'TWA[°]':<6} | {'BS[kt]':<6} | {'A':<2} | {'Status'}")
    print("-" * 145)

    while min_lat <= curr_lat <= max_lat and min_lon <= curr_lon <= max_lon:
        weather = get_weather_at_point(file_path, curr_lat, curr_lon, target_time=current_time)
        if not weather or '10 metre U wind component' not in weather['data']: break
            
        u = weather['data']['10 metre U wind component']['value']
        v_key = '10 metre v wind component' if '10 metre v wind component' in weather['data'] else '10 metre V wind component'
        v = weather['data'][v_key]['value']
        
        tws = np.sqrt(u**2 + v**2) * 1.94384
        twd = (math.degrees(math.atan2(-u, -v)) + 360) % 360
        
        twa = abs(((twd - target_heading + 180) % 360) - 180)
        actual_heading, status = target_heading, "OK"
        
        if twa < 45:
            status = "CORRECTED"
            h1, h2 = (twd + 45) % 360, (twd - 45) % 360
            # Choose heading closest to the original target
            diff1 = abs(((h1 - target_heading + 180) % 360) - 180)
            diff2 = abs(((h2 - target_heading + 180) % 360) - 180)
            actual_heading = h1 if diff1 < diff2 else h2
            twa = 45.0

        boat_speed = polars([twa, tws])[0]
        dist_nm = boat_speed * (time_step_min / 60.0)
        total_dist_nm += dist_nm
        route_points.append({'lat': curr_lat, 'lon': curr_lon, 'time': current_time})
        
        approx = "*" if weather['meta']['approximated'] else " "
        print(f"{step_count:<4} | {current_time.strftime('%H:%M:%S'):<8} | {weather['meta']['time'].strftime('%H:%M:%S'):<8} | {curr_lat:<8.4f} | {curr_lon:<8.4f} | {tws:<7.2f} | {actual_heading:<10.0f} | {twa:<6.1f} | {boat_speed:<6.2f} | {approx:<2} | {status}")
        
        curr_lat += (dist_nm * math.cos(math.radians(actual_heading))) / 60.0
        curr_lon += (dist_nm * math.sin(math.radians(actual_heading))) / (60.0 * math.cos(math.radians(curr_lat)))
        current_time += timedelta(minutes=time_step_min)
        step_count += 1
        if step_count > 500: break

    print("-" * 145)
    total_time_h = (step_count * time_step_min) / 60.0
    avg_speed = total_dist_nm / total_time_h if total_time_h > 0 else 0
    print(f"Manual Summary: Total Distance {total_dist_nm:.2f} nm, Average Speed {avg_speed:.2f} kt.")
    return route_points

def analyze_grib_performance(file_path):
    """Scans the GRIB file and displays date ranges, parameters, and grid limits."""
    print(f"--- COMPREHENSIVE GRIB DIAGNOSTICS ---")
    if not os.path.exists(file_path):
        print(f"ERROR: File '{file_path}' does not exist.")
        return
    try:
        grbs = pygrib.open(file_path)
        all_dates = sorted(list(set(grb.validDate for grb in grbs)))
        params = set(grb.name for grb in grbs)
        
        print(f"Location: {os.path.abspath(file_path)}")
        print(f"Date range: {all_dates[0]} to {all_dates[-1]}")
        print(f"Number of time steps: {len(all_dates)}")
        print(f"Available parameters: {', '.join(params)}")
        
        grbs.seek(0)
        m = grbs.readline()
        lats, lons = m.latlons()
        print(f"Grid (Lat): {lats.min():.2f} : {lats.max():.2f}")
        print(f"Grid (Lon): {lons.min():.2f} : {lons.max():.2f}")
        print("-" * 50)
        grbs.close()
    except Exception as e:
        print(f"Diagnostic error: {e}")

if __name__ == "__main__":
    file_name = "test.grb2"
    analyze_grib_performance(file_name)
    
    # Example call for VMG Optimization simulation
    vmg_pts = simulate_vmg_route(file_name, time_step_min=10.0)
    if vmg_pts:
        save_to_gpx(vmg_pts, "scampi_vmg.gpx")
        
    # Example call for Manual simulation
    # manual_pts = simulate_manual_route(file_name, target_heading=45, start_pos="center")
    # if manual_pts:
    #     save_to_gpx(manual_pts, "scampi_manual.gpx")