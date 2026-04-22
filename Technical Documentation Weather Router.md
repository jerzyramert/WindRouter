# **Technical Documentation: Scampi 30 GRIB Router & Performance Analyzer**

This document provides a comprehensive overview of the technical implementation, architectural logic, and functional specification of the yacht\_performance\_grib.py routing engine. It is intended for developers maintaining or extending the codebase.

## **1\. System Architecture**

The application follows a linear processing pipeline:

1. **Data Ingestion**: Loading GRIB2 meteorological data into a RAM-based cache.  
2. **Performance Modeling**: Initializing 2D interpolation for yacht-specific polar curves.  
3. **Spatial Analysis**: Identifying "safe zones" where True Wind Speed (TWS) remains below defined safety thresholds (30 kt).  
4. **Routing Engines**:  
   * **Dijkstra (Graph-based)**: Global optimization for the fastest route across a pre-calculated reachable graph.  
   * **VMG (Vector-based)**: Iterative greedy optimization aiming for the best velocity made good towards a specific target.  
5. **Audit & Export**: Generating detailed TXT logs and GPX tracks for external validation.

## **2\. Core Components & Logic**

### **2.1 Weather Data Handling**

* **True Wind Calculation**: The GRIB U and V components (10m above ground) are treated as **True Wind Speed (TWS)** and **True Wind Direction (TWD)** relative to the ground.  
* **Caching**: load\_grib\_to\_memory parses the file once and stores data in a nested dictionary weather\_cache\[date\]\[parameter\]. This significantly reduces I/O overhead during graph construction and simulation.

### **2.2 Yacht Performance (Polars)**

* **Interpolation**: The system uses scipy.interpolate.RegularGridInterpolator. It performs a linear 2D lookup: (TWA, TWS) \-\> Boat Speed.  
* **Dead Zone**: A hard constraint is applied: if the True Wind Angle (TWA) is less than **32°**, the Boat Speed (BS) is forced to 0 (or a high penalty cost in graphs).

### **2.3 Reachable Graph Logic (Dijkstra)**

The graph is built dynamically for each departure time using a Breadth-First Search (BFS) pattern:

* **Safe Points**: Only points where TWS never exceeds 30kt throughout the forecast are considered.  
* **Angle Filtering**: To ensure progress towards the target, a neighbor is only connected if the bearing to it is within **±80°** of the bearing to the final target.  
* **Cost Calculation**: Cost \= Distance / Boat Speed. The cost is measured in hours.

### **2.4 VMG Simulation Logic**

The VMG algorithm is an iterative solver:

1. **Heading Scan**: Every 2° (0-358), it calculates the potential Boat Speed.  
2. **VMG Calculation**: VMG \= BS \* cos(Heading \- BearingToTarget).  
3. **Boundary Protection**: Before committing to a heading, the algorithm predicts the next\_lat/lon. If the new position is outside the GRIB grid, the heading is discarded. This forces the yacht to tack/gybe inside the map.

## **3\. Function Reference**

### **Utility & Math**

* calculate\_bearing(lat1, lon1, lat2, lon2): Uses spherical trigonometry to find the initial bearing.  
* calculate\_distance\_nm(lat1, lon1, lat2, lon2): Uses a simplified Haversine/Spherical model for distance in nautical miles.

### **Data Processing**

* load\_grib\_to\_memory(file\_path): Entry point for data. Returns a cache object.  
* get\_weather\_from\_cache(cache, lat, lon, time): Finds the spatially and temporally nearest weather data point.  
* identify\_safe\_sailing\_areas(cache, max\_wind\_threshold): Filters the GRIB grid based on a TWS safety limit.

### **Routing & Algorithms**

* generate\_reachable\_graph(...): Constructs the adjacency map. Logs reasons for node rejection (Angle, Safety, Dead Zone) to graph\_log.txt.  
* find\_shortest\_path\_dijkstra(...): Implementation of the shortest path algorithm on the adjacency map.  
* simulate\_vmg\_route(...): Greedy simulator. Includes target-seeking logic and map boundary guards.

### **Logging & Output**

* save\_route\_detailed\_log(...): Produces a human-readable table (TXT) containing: Time, Position, TWS, TWD, Heading, TWA, and Boat Speed.  
* save\_to\_gpx(...): Standard GPX 1.1 track generation.

## **4\. Maintenance Notes for Developers**

### **Adjusting Safety Thresholds**

The safety limit is currently set to **30 knots**. To change this, modify the call to identify\_safe\_sailing\_areas in the \_\_main\_\_ block.

### **Changing the Target**

The target is calculated in the main block. Currently, it is the northern edge of the GRIB file at the longitudinal center. To change to a specific coordinate, update target\_lat and target\_lon.

### **Performance Optimization**

If the graph construction is slow:

1. Reduce the GRIB grid resolution (if possible).  
2. Tighten the angle\_diff constraint (e.g., from 80° back to 50°).  
3. The Dijkstra algorithm is currently calculated on a single-time weather snapshot (the departure time) to maintain graph stability. For time-dynamic routing (isochrones), a 3D graph (Lat, Lon, Time) would be required.

### **Future Extensibility**

* **Tidal Currents**: Adding a U\_current and V\_current parameter lookup would allow for Course Over Ground (COG) and Speed Over Ground (SOG) calculations.  
* **Fuel Consumption**: For motor-sailing scenarios, a fuel-per-hour coefficient could be added to the cost function.