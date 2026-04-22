import pygrib
import numpy as np
import os
from scipy.interpolate import RegularGridInterpolator
from datetime import datetime, timedelta
import math
from collections import deque
import json
import heapq

def get_scampi_30_polars():
    """
    Defines and returns an interpolation function for Scampi 30 polar curves.
    Uses RegularGridInterpolator for 2D lookups based on TWA and TWS.
    """
    # Angles (Y-axis) and wind speeds (X-axis)
    twa_angles = [32, 36, 40, 45, 52, 60, 70, 80, 90, 100, 110, 120, 135, 150, 180]
    tws_speeds = [6, 8, 10, 12, 14, 16, 20]
    
    # Yacht speed matrix (Vb) - rows are TWA, columns are TWS
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
    Loads the entire GRIB file into RAM to avoid repetitive I/O operations.
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
        print(f"Error while loading GRIB file: {e}")
        return None

def get_weather_from_cache(cache, target_lat, target_lon, target_time):
    """
    Retrieves weather data from cache for the nearest point and time.
    """
    if not cache: return None
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
    
    return {
        'meta': {
            'actual_lat': lats[min_idx], 
            'actual_lon': lons[min_idx], 
            'time': closest_date, 
            'approximated': approximated
        },
        'wind_u': u_val, 
        'wind_v': v_val
    }

def calculate_bearing(lat1, lon1, lat2, lon2):
    """Calculates the initial bearing between two points on a sphere."""
    d_lon = math.radians(lon2 - lon1)
    lat1_r = math.radians(lat1)
    lat2_r = math.radians(lat2)
    y = math.sin(d_lon) * math.cos(lat2_r)
    x = math.cos(lat1_r) * math.sin(lat2_r) - math.sin(lat1_r) * math.cos(lat2_r) * math.cos(d_lon)
    return (math.degrees(math.atan2(y, x)) + 360) % 360

def calculate_distance_nm(lat1, lon1, lat2, lon2):
    """Calculates distance in nautical miles (nm)."""
    avg_lat = math.radians((lat1 + lat2) / 2.0)
    d_lat = (lat2 - lat1) * 60.0
    d_lon = (lon2 - lon1) * 60.0 * math.cos(avg_lat)
    return math.sqrt(d_lat**2 + d_lon**2)

def identify_weather_danger_zones(cache, min_threshold, max_threshold=float('inf')):
    """Identifies true wind speed zones within the entire forecast window."""
    if not cache: return []
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
                first_time_grid[exceed_mask], first_speed_grid[exceed_mask] = dt, tws_grid[exceed_mask]
                found_mask |= exceed_mask
    indices = np.where(found_mask)
    return [{'lat': lats[r, c], 'lon': lons[r, c], 'speed': first_speed_grid[r, c], 'time': first_time_grid[r, c]} for r, c in zip(*indices)]

def identify_safe_sailing_areas(cache, max_wind_threshold=30.0):
    """Determines safe grid square centers (TWS consistently <= threshold)."""
    if not cache: return {}
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
    print(f"[SAFE AREA DIAG] Found {len(indices[0])} safe grid points (TWS <= {max_wind_threshold}kt).")
    return {(r, c): {'lat': lats[r, c], 'lon': lons[r, c], 'max_speed': max_observed_speed[r, c]} for r, c in zip(*indices)}

def generate_reachable_graph(cache, safe_points_map, start_lat, start_lon, target_lat, target_lon, start_time, log_file="graph_log.txt"):
    """
    Builds a connection graph between safe grid points for a specific departure time.
    """
    if not safe_points_map:
        return set(), {}, None

    lats, lons = cache['lats'], cache['lons']
    polars = get_scampi_30_polars()
    
    dist_sq = (lats - start_lat)**2 + (lons - start_lon)**2
    min_d, start_node = float('inf'), None
    for (r, c) in safe_points_map.keys():
        d = dist_sq[r, c]
        if d < min_d: min_d, start_node = d, (r, c)

    if not start_node:
        print(f"[GRAPH DIAG] ERROR: No safe starting point found for time {start_time}.")
        return set(), {}, None

    reachable_nodes = {start_node}
    adjacency_map = {} 
    queue = deque([start_node])
    edges_count = 0
    
    with open(log_file, "a", encoding="utf-8") as log:
        log.write(f"\nGRAPH CONSTRUCTION LOG - START TIME: {start_time}\n")
        log.write(f"Start node: {start_node} ({safe_points_map[start_node]['lat']:.4f}N, {safe_points_map[start_node]['lon']:.4f}E)\n")
        log.write("-" * 80 + "\n")

        while queue:
            r, c = queue.popleft()
            curr_p = safe_points_map[(r, c)]
            bearing_to_target = calculate_bearing(curr_p['lat'], curr_p['lon'], target_lat, target_lon)
            
            # Fetch weather for the specific departure moment (start_time)
            weather = get_weather_from_cache(cache, curr_p['lat'], curr_p['lon'], start_time)
            u, v = weather['wind_u'], weather['wind_v']
            tws = np.sqrt(u**2 + v**2) * 1.94384
            twd = (math.degrees(math.atan2(-u, -v)) + 360) % 360
            
            adjacency_map[(r, c)] = []
            for dr in [-1, 0, 1]:
                for dc in [-1, 0, 1]:
                    if dr == 0 and dc == 0: continue
                    neighbor = (r + dr, c + dc)
                    
                    if neighbor not in safe_points_map:
                        continue
                    
                    n_p = safe_points_map[neighbor]
                    bearing_to_neighbor = calculate_bearing(curr_p['lat'], curr_p['lon'], n_p['lat'], n_p['lon'])
                    angle_diff = abs(((bearing_to_neighbor - bearing_to_target + 180) % 360) - 180)
                    
                    if angle_diff > 80.0:
                        continue
                    
                    dist = calculate_distance_nm(curr_p['lat'], curr_p['lon'], n_p['lat'], n_p['lon'])
                    twa = abs(((twd - bearing_to_neighbor + 180) % 360) - 180)
                    
                    if twa < 32:
                        continue
                    
                    bs = polars([twa, tws])[0]
                    cost = dist / bs if bs > 0 else 9999.0
                    adjacency_map[(r, c)].append({"target": neighbor, "cost": cost})
                    edges_count += 1
                    
                    if neighbor not in reachable_nodes:
                        reachable_nodes.add(neighbor)
                        queue.append(neighbor)

    print(f"[GRAPH DIAG] Construction complete (Start: {start_time}). Nodes: {len(reachable_nodes)}, Edges: {edges_count}")
    return reachable_nodes, adjacency_map, start_node

def find_shortest_path_dijkstra(start_node, adjacency_map, safe_points_map, target_lat, target_lon):
    """
    Searches for the fastest route in the generated graph to the node closest to the target coordinates.
    """
    if not start_node or not adjacency_map: return [], 0
    
    # 1. Calculate travel costs for all reachable nodes
    distances = {node: float('inf') for node in adjacency_map.keys()}
    distances[start_node] = 0
    predecessors = {node: None for node in adjacency_map.keys()}
    pq = [(0, start_node)]
    
    nodes_visited = 0
    while pq:
        curr_dist, curr_node = heapq.heappop(pq)
        nodes_visited += 1
        if curr_dist > distances[curr_node]: continue
        
        if curr_node in adjacency_map:
            for edge in adjacency_map[curr_node]:
                neighbor, weight = edge['target'], edge['cost']
                dist = curr_dist + weight
                if dist < distances[neighbor]:
                    distances[neighbor], predecessors[neighbor] = dist, curr_node
                    heapq.heappush(pq, (dist, neighbor))
                
    # 2. Select the target node (geographically closest to specified target)
    reachable_and_visited = [n for n in adjacency_map.keys() if distances[n] != float('inf')]
    if not reachable_and_visited: 
        print("[DIJKSTRA DIAG] ERROR: No reachable nodes found.")
        return [], 0
    
    # Search for the node in graph physically closest to target_lat, target_lon
    best_finish = min(reachable_and_visited, key=lambda n: calculate_distance_nm(
        safe_points_map[n]['lat'], safe_points_map[n]['lon'], target_lat, target_lon))
    
    total_cost = distances[best_finish]
    target_node_lat = safe_points_map[best_finish]['lat']
    target_node_lon = safe_points_map[best_finish]['lon']
    
    print(f"[DIJKSTRA DIAG] Route target: {target_node_lat:.4f}N, {target_node_lon:.4f}E | Cost: {total_cost:.2f} h")

    # 3. Path reconstruction
    path = []
    curr = best_finish
    while curr is not None:
        path.append(safe_points_map[curr]); curr = predecessors[curr]
    return path[::-1], total_cost

def save_route_detailed_log(points, cache, filename, label):
    """
    Generates a detailed text log for the route, containing position, time, and weather conditions.
    """
    if not points: return
    
    polars = get_scampi_30_polars()
    
    with open(filename, "w", encoding="utf-8") as f:
        f.write(f"DETAILED ROUTE LOG: {label}\n")
        f.write(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("-" * 110 + "\n")
        header = f"{'Time':<20} | {'Latitude':<10} | {'Longitude':<10} | {'TWS [kt]':<8} | {'TWD [°]':<8} | {'Heading [°]':<11} | {'TWA [°]':<8} | {'BS [kt]':<8}\n"
        f.write(header)
        f.write("-" * 110 + "\n")
        
        for i in range(len(points)):
            p = points[i]
            lat, lon = p['lat'], p['lon']
            time = p.get('time', datetime.now())
            
            # Fetch weather
            w = get_weather_from_cache(cache, lat, lon, time)
            u, v = w['wind_u'], w['wind_v']
            tws = np.sqrt(u**2 + v**2) * 1.94384
            twd = (math.degrees(math.atan2(-u, -v)) + 360) % 360
            
            # Heading - bearing to the next point
            if i < len(points) - 1:
                hdg = calculate_bearing(lat, lon, points[i+1]['lat'], points[i+1]['lon'])
            else:
                # Last point - keep heading from the previous step
                hdg = calculate_bearing(points[i-1]['lat'], points[i-1]['lon'], lat, lon) if i > 0 else 0
            
            # TWA (True Wind Angle)
            twa = abs(((twd - hdg + 180) % 360) - 180)
            
            # Boat Speed (BS) from polars
            bs = polars([max(32, twa), tws])[0] if twa >= 32 else 0
            
            row = f"{time.strftime('%Y-%m-%d %H:%M'):<20} | {lat:<10.6f} | {lon:<10.6f} | {tws:<8.2f} | {twd:<8.1f} | {hdg:<11.1f} | {twa:<8.1f} | {bs:<8.2f}\n"
            f.write(row)
            
    print(f"[LOG] Detailed log saved: {filename}")

def print_route_summary(points, label, time_hours=None):
    """Prints route statistic summary."""
    if not points or len(points) < 2:
        print(f"\n--- {label} --- No data available."); return
    dist = sum(calculate_distance_nm(points[i]['lat'], points[i]['lon'], points[i+1]['lat'], points[i+1]['lon']) for i in range(len(points)-1))
    if time_hours is None and 'time' in points[0] and 'time' in points[-1]:
        time_hours = (points[-1]['time'] - points[0]['time']).total_seconds() / 3600.0
    avg_speed = dist / time_hours if time_hours and time_hours > 0 else 0
    print(f"--- SUMMARY: {label} ---")
    print(f"Points: {len(points)} | Distance: {dist:.2f} nm | Time: {time_hours:.2f} h | Avg Speed: {avg_speed:.2f} kt\n")

def save_graph_to_json(reachable_nodes, adjacency_map, safe_points_map, filename="sailing_graph.json"):
    """Saves the graph structure to a JSON file."""
    data = {
        "metadata": {"nodes": len(reachable_nodes), "unit": "hours", "timestamp": datetime.now().isoformat()},
        "nodes": {f"{r},{c}": {"lat": safe_points_map[(r, c)]["lat"], "lon": safe_points_map[(r, c)]["lon"]} for r, c in reachable_nodes},
        "edges": {f"{r},{c}": [{"target": f"{e['target'][0]},{e['target'][1]}", "cost": round(e['cost'], 4)} for e in edges] for (r, c), edges in adjacency_map.items()}
    }
    with open(filename, 'w', encoding='utf-8') as f: json.dump(data, f, indent=4)

def simulate_vmg_route(cache, start_lat, start_lon, target_lat, target_lon, start_time, time_step_min=10.0):
    """
    VMG routing based on True Wind Speed (TWS) with dynamic start time.
    """
    if not cache: return []
    lats, lons = cache['lats'], cache['lons']
    lat_min, lat_max = lats.min(), lats.max()
    lon_min, lon_max = lons.min(), lons.max()
    
    curr_lat, curr_lon = start_lat, start_lon
    polars = get_scampi_30_polars()
    
    # Initialize simulation time from the given start_time
    curr_time = start_time
    route_points = []
    step = 0
    
    print(f"[VMG DIAG] Start simulation: {curr_time.strftime('%Y-%m-%d %H:%M')}")
    
    while curr_lat < target_lat:
        weather = get_weather_from_cache(cache, curr_lat, curr_lon, curr_time)
        if not weather: break
        
        u, v = weather['wind_u'], weather['wind_v']
        tws = np.sqrt(u**2 + v**2) * 1.94384
        twd = (math.degrees(math.atan2(-u, -v)) + 360) % 360
        
        bearing_to_target = calculate_bearing(curr_lat, curr_lon, target_lat, target_lon)
        
        best_vmg = -99.0
        best_hdg = None
        best_bs = 0
        
        # Scan headings every 2 degrees
        for h in range(0, 360, 2):
            twa = abs(((twd - h + 180) % 360) - 180)
            if twa < 32: continue # Dead zone
            
            v_boat = polars([twa, tws])[0]
            dist_step = v_boat * (time_step_min / 60.0)
            
            next_lat = curr_lat + (dist_step * math.cos(math.radians(h))) / 60.0
            next_lon = curr_lon + (dist_step * math.sin(math.radians(h))) / (60.0 * math.cos(math.radians(curr_lat)))
            
            if not (lat_min <= next_lat <= lat_max and lon_min <= next_lon <= lon_max):
                continue 
                
            vmg = v_boat * math.cos(math.radians(h - bearing_to_target))
            if vmg > best_vmg:
                best_vmg = vmg
                best_hdg = h
                best_bs = v_boat
        
        if best_hdg is None:
            break
            
        dist = best_bs * (time_step_min / 60.0)
        route_points.append({'lat': curr_lat, 'lon': curr_lon, 'time': curr_time})
        
        curr_lat += (dist * math.cos(math.radians(best_hdg))) / 60.0
        curr_lon += (dist * math.sin(math.radians(best_hdg))) / (60.0 * math.cos(math.radians(curr_lat)))
        curr_time += timedelta(minutes=time_step_min)
        step += 1
        
        if calculate_distance_nm(curr_lat, curr_lon, target_lat, target_lon) < 1.0:
            break
            
        if step >= 10000: break
        
    return route_points

def save_to_gpx(points, filename, label="Route"):
    """Saves the route track to a GPX file."""
    header = ['<?xml version="1.0" encoding="UTF-8"?>', f'<gpx version="1.1" creator="ScampiRouter" xmlns="http://www.topografix.com/GPX/1/1"><trk><name>{label}</name><trkseg>']
    body = [f'  <trkpt lat="{p["lat"]:.6f}" lon="{p["lon"]:.6f}">' + (f"<time>{p['time'].strftime('%Y-%m-%dT%H:%M:%SZ')}</time>" if 'time' in p else "") + '</trkpt>' for p in points]
    with open(filename, 'w', encoding='utf-8') as f: f.write('\n'.join(header + body + ['</trkseg></trk></gpx>']))

def analyze_grib_performance(file_path):
    """GRIB file diagnostics."""
    if not os.path.exists(file_path): return
    grbs = pygrib.open(file_path); msg = grbs.readline(); lats, lons = msg.latlons()
    min_lat, max_lat, min_lon, max_lon = lats.min(), lats.max(), lons.min(), lons.max()
    sn_nm = (max_lat - min_lat) * 60.0
    ew_nm = (max_lon - min_lon) * 60.0 * math.cos(math.radians((min_lat + max_lat) / 2.0))
    print(f"--- GRIB DIAGNOSTICS ---\nGrid: Lat {min_lat:.2f}:{max_lat:.2f}, Lon {min_lon:.2f}:{max_lon:.2f}")
    print(f"Dimensions: S-N: {sn_nm:.2f} nm, E-W: {ew_nm:.2f} nm\n" + "-"*50); grbs.close()

if __name__ == "__main__":
    file_name = "test.grb2"
    analyze_grib_performance(file_name)
    weather_cache = load_grib_to_memory(file_name)
    
    if weather_cache:
        lats, lons = weather_cache['lats'], weather_cache['lons']
        start_lat, start_lon = 53.25, 2.6
        
        # DEFINITION OF SHARED TARGET FOR BOTH ALGORITHMS
        target_lat = lats.max()
        target_lon = (lons.min() + lons.max()) / 2.0
        
        # Initialize first departure time from GRIB file
        base_start_time = weather_cache['dates'][0]
        
        # Clear log before starting
        if os.path.exists("graph_log.txt"): os.remove("graph_log.txt")

        # 1. Identify danger zones and safe areas
        save_to_gpx(identify_weather_danger_zones(weather_cache, 40.0), "forbidden_areas.gpx", "Wind >40kt")
        save_to_gpx(identify_weather_danger_zones(weather_cache, 30.0, 40.0), "caution_areas.gpx", "Wind 30-40kt")
        safe_map = identify_safe_sailing_areas(weather_cache, 30.0)
        
        print("\n--- STARTING SIMULATION OF 4 ROUTES EVERY 5 HOURS ---")

        for i in range(1, 5):
            current_departure_time = base_start_time + timedelta(hours=(i-1)*5)
            print(f"\n>>> SIMULATION NO {i} (Departure: {current_departure_time.strftime('%Y-%m-%d %H:%M')}) <<<")
            
            # --- DIJKSTRA ALGORITHM ---
            nodes, adj, start_idx = generate_reachable_graph(weather_cache, safe_map, start_lat, start_lon, target_lat, target_lon, current_departure_time)
            
            if nodes:
                fastest_path, d_cost = find_shortest_path_dijkstra(start_idx, adj, safe_map, target_lat, target_lon)
                if fastest_path:
                    # Add time to Dijkstra points
                    for idx, p in enumerate(fastest_path):
                        p['time'] = current_departure_time + timedelta(hours=(idx * d_cost / len(fastest_path)))
                    
                    filename_d_gpx = f"fastest_path_start_{i}.gpx"
                    filename_d_log = f"log_dijkstra_start_{i}.txt"
                    
                    save_to_gpx(fastest_path, filename_d_gpx, f"Dijkstra Route {i}")
                    save_route_detailed_log(fastest_path, weather_cache, filename_d_log, f"Dijkstra Route {i}")
                    print_route_summary(fastest_path, f"DIJKSTRA (START {i})", d_cost)
            
            # --- VMG ALGORITHM ---
            vmg_pts = simulate_vmg_route(weather_cache, start_lat, start_lon, target_lat, target_lon, current_departure_time, 10.0)
            if vmg_pts:
                filename_v_gpx = f"scampi_vmg_start_{i}.gpx"
                filename_v_log = f"log_vmg_start_{i}.txt"
                
                save_to_gpx(vmg_pts, filename_v_gpx, f"VMG Route {i}")
                save_route_detailed_log(vmg_pts, weather_cache, filename_v_log, f"VMG Route {i}")
                print_route_summary(vmg_pts, f"VMG (START {i})")

        print("\nSimulations complete. Generated GPX files and detailed TXT logs.")
    else:
        print("GRIB file not loaded.")