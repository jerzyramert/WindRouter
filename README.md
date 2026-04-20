# **Scampi 30 GRIB Router & Performance Analyzer**

A Python-based development tool for analyzing GRIB meteorological data and simulating the performance of a **Scampi 30** class yacht (designed by Peter Norlin). The program allows for determining optimal sailing routes using the vessel's actual polar curves.

## **🚀 Main Features**

* **GRIB Diagnostics**: Full insight into .grb and .grb2 file metadata (time ranges, WMO parameters, geographic grids).  
* **Scampi 30 Polar Curves**: Implemented yacht performance model using modern RegularGridInterpolator interpolation.  
* **VMG (Velocity Made Good) Optimization**: An intelligent navigation mode that selects the best tack to reach the upwind destination as quickly as possible.  
* **Manual Simulation**: Ability to test a fixed course with automatic dead zone correction (bearing away from the wind).  
* **GPX Export**: Generation of GPS tracks compatible with external applications (e.g., Windy, OpenCPN, Garmin).  
* **Approximation Handling**: Intelligent detection of missing data in the GRIB file and marking time steps that require extrapolation.

## **🛠 Technical Requirements**

The project requires the following libraries to be installed:

* pygrib – support for WMO binary formats.  
* numpy – matrix calculations.  
* scipy – advanced 2D interpolation.

### **System Library Installation (Linux/macOS)**

The pygrib library requires the ecCodes (ECMWF) engine to be installed.

**macOS (Homebrew):**

brew install eccodes  
pip install pygrib numpy scipy

**Ubuntu/Debian:**

sudo apt-get install libeccodes-dev  
pip install pygrib numpy scipy

## **📋 Usage Instructions**

1. Place the forecast file in the root directory (by default, the program looks for aaa.grb2).  
2. Run the main script:  
   python yacht\_performance\_grib.py

3. The program will perform diagnostics and then conduct the route simulation.  
4. Upon completion, a scampi\_vmg.gpx file will appear in the folder, which you can import into your favorite map application.

## **⛵ Nautical Model Details**

* **Dead Zone**: A safe angle of ![][image1] relative to the true wind has been assumed.  
* **Time Step**: By default, the simulation takes place in 10-minute intervals.  
* **VMG Principle**: The algorithm scans headings every ![][image2] to find the maximum projection of boat speed onto the direction of the target.

## **📁 Results Table Structure**

| **Column** | **Description** |

| **Czas\_SIM** | Current simulation time (voyage clock). |

| **Czas\_GRB** | Time of origin for the wind data from the GRIB file. |

| **TWS / TWD** | True Wind Speed

![][image3]and True Wind Direction

![][image4]relative to the ground. |

| **H\_act** | Actual yacht heading after accounting for VMG or corrections. |

| **BS** | Boat Speed – yacht speed through the water. |

| **VMG** | Velocity Made Good – velocity component towards the target. |

| **A** | Approximation flag (\* indicates missing time data in GRIB). |

## **⚖️ License**

Project created for educational and hobby purposes. The authors do not take responsibility for navigational decisions made based on simulation results.

*Project developed as part of experiments with weather routing for classic IOR yachts.*

[image1]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABsAAAAXCAYAAAD6FjQuAAABX0lEQVR4Xu2STytEURjGbyiKkjTNYrjuvwVfg40PYCXsbHwHtr6BKF9B2FAWNv40peykZDakLBSbaSwUv3M7J6+3c28zdnSfenrP+7x/nnNnThBU+BeI43gKfGod7S0Mw2U4liTJKHEB7VX2oG2jNWEHzsiaF8aowCzXJRuNxoSrY7RUr9eHRb7hzl5EUXTCknaRGQs2iVvEOU+9qTX2TWsth7klSw4Yeiky05oEs6uEAZfTvybKP+GW/dbMgC85pG8ftuCsruegsJem6aQ9F5qx7I54Ay/hRyC+pCvw840zeOryMrMsywZFfuTrK4UeKDLTMH++6YPruuYFAzv6xZSY9au8z5rdKt0PGo/hmaJZYGjOu7bv3mhcbMjN1mq1Edt3/r2xRzgzqfGsH9DaUsN43vYuSr0n+MzMS0VrSY38HXak1jUYvIbP8NHSnK9cna9bsRd5svFCzleo8HfwBaihfOpX5NZiAAAAAElFTkSuQmCC>

[image2]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABEAAAAYCAYAAAAcYhYyAAAA50lEQVR4XmNgGAUEgYqKiii6GAxISUmJKCgopIuKivKgy4E0ssvLy/8DKtgFpJ8B8X8gvoysBihXoaioqA9iA+WcgDgYWR4k+B+N7wg16BpMTE5ObgeamhvIfLAhQPwTixjccKBLNiLLA/mXkPkwDT+wiCEb0gkKExAb6ColoFwKQjUOgG4IVEwTaFiHkpKSHLI4ViAPCTiQIYvQ5YgGUANuoosTDYDONQcZgi+94AXAABOEGsCOLkcsYMISkIuR+QQBUMM/LGJ/0cVwAqDiX9DAxMDoarECGRkZaXSNSPg7uvpRMNQAAK8ySTUuS3D1AAAAAElFTkSuQmCC>

[image3]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAmwAAAA/CAYAAABdEJRVAAABuUlEQVR4Xu3dsUrDUBQGYDvrGuuUpLSbg4+g4OSqLj6Ck4tvIoiru4P4Jk4iOIqLLj6A6DmQQAxCcEir8H0Qzr3n3O4/SdusrQEAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAMB/UVXVeVwfcX32ZwAA/BGLxaIYCmwxPxw6AwDASCKIXQ6FsZi/Dp0BAGAkGcSGwljOy7K87fcBAFiCDGN1XZ/kOupd7B+i7raz/vX90wAAjCqDWhvCor5EmWSN/nV7JvY3ghoAwIpEEHvMMBYBba/Tuy+KYqOzzztrb+0eAIAlasLYU9ayLK/685Sz2Wy20+8DADCyuq63MozN5/PN3Deh7bh/zuNQAIAViSB20Q1jzaPR01x3glt+p6175r1dAwAwsqr3hoPmDtt2/pFu25tOp+vRf851zM7aX5MCALAEEcQOfugdRZl0e/nINMLafrcHAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAwG98AY3gS4uzdk7HAAAAAElFTkSuQmCC>

[image4]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAmwAAAA+CAYAAACWTEfwAAAA3klEQVR4Xu3WwQmAMAwF0K4hBtqL4H5O4DoO40zmIpSePFZ4D8IPyQK/FAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAPirWuv97q21q/8BADCBLGlnlrYlc888xj8AABOIiDVnG+8AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAPDNA4/bBc1Es/Z7AAAAAElFTkSuQmCC>