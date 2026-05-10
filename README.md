# Spotter Fuel Route Optimizer

A production-style backend API that computes the **cheapest possible refueling plan** between any two U.S. locations using real truck-stop fuel price data.

Built with **Django 5**, **Django REST Framework**, **PostgreSQL/PostGIS**, and powered by free public routing/geocoding services — no API keys required.

---

## Features

- Cheapest fuel-stop optimization algorithm
- Real truck-stop fuel price integration
- Route generation using OSRM
- Geocoding using Nominatim
- PostgreSQL + PostGIS spatial queries
- GeoJSON export for instant visualization
- Dockerized setup
- Robust handling for routing edge cases
- U.S.-only validation support

---

## Tech Stack

- Python 3.11
- Django 5
- Django REST Framework
- PostgreSQL 15
- PostGIS
- Docker & Docker Compose
- OSRM (Routing)
- Nominatim (Geocoding)

---

## Project Structure

```text
spotter-backend/
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── .env
├── fuel-prices-for-be-assessment.csv
└── app/
    ├── manage.py
    ├── spotter/
    │   ├── __init__.py
    │   ├── settings.py
    │   ├── urls.py
    │   ├── asgi.py
    │   └── wsgi.py
    └── api/
        ├── models.py
        ├── views.py
        ├── urls.py
        ├── services.py
        └── management/
            └── commands/
                └── load_fuel_data.py
```

---

## Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/sayan049/spotter-optimized-fuel-route.git
cd spotter-optimized-fuel-route
```

---

### 2. Create Environment Variables

(Optional — defaults work locally)

```bash
cp .env.example .env
```

Edit the `.env` file if needed.

---

### 3. Start Docker Containers

```bash
docker-compose up -d
```

---

### 4. Run Database Migrations

```bash
docker-compose exec web python manage.py migrate
```

---

### 5. Load Fuel Price Dataset

This step imports and geocodes the truck-stop fuel data.

```bash
docker-compose exec web python manage.py load_fuel_data fuel-prices-for-be-assessment.csv
```

> **Note:**  
> Initial data loading may take several hours because the project uses the free public Nominatim geocoding service with strict rate limits.

---

# API Usage

## Endpoint

```http
GET /api/route/
```

---

## Query Parameters

| Parameter | Required | Description |
|---|---|---|
| `start` | Yes | Start location (Example: `Chicago,IL`) |
| `finish` | Yes | Destination location (Example: `Houston,TX`) |
| `export_geojson` | No | Set to `true` to download a GeoJSON visualization |

---

## Example Request

```bash
curl "http://localhost:8000/api/route/?start=Chicago,IL&finish=Houston,TX"
```

---

## Example JSON Response

```json
{
  "route_map": {
    "type": "LineString",
    "coordinates": [
      [-87.6298, 41.8781]
    ]
  },
  "total_distance_miles": 1082.19,
  "optimal_stops": [
    {
      "station_name": "QUIKTRIP #7191",
      "city": "Effingham",
      "state": "IL",
      "coordinates": [39.1369746, -88.5607241],
      "gallons_purchased": 20.9,
      "price_per_gallon": 2.999,
      "cost_at_stop": 62.67
    }
  ],
  "total_fuel_cost": 170.72
}
```

---

# GeoJSON Visualization

You can instantly visualize the optimized route using GeoJSON.

Add:

```text
&export_geojson=true
```

to any route request.

---

## Example

```bash
curl "http://localhost:8000/api/route/?start=Chicago,IL&finish=Houston,TX&export_geojson=true" -o chicago_houston.geojson
```

Then:

1. Open [geojson.io](https://geojson.io/)
2. Drag and drop the `.geojson` file

The generated visualization includes:

- Blue route line
- Green start marker
- Black destination marker
- Red fuel-stop markers

---

# Optimization Algorithm

The system implements a **provably optimal greedy fuel-planning algorithm** for continuous refueling with full future fuel-price knowledge.

## Strategy

At every fuel station:

### Case 1 — Cheaper Fuel Exists Ahead

If a cheaper station exists within the vehicle range:

- Purchase only enough fuel to reach the nearest cheaper station

### Case 2 — No Cheaper Fuel Ahead

If no cheaper station exists within range:

- Fill the tank to maximum capacity
- Drive to:
  - the farthest reachable station with the minimum price
  - or directly to the destination if possible

---

## Vehicle Constraints

| Property | Value |
|---|---|
| Vehicle Range | 500 miles |
| Fuel Efficiency | 10 MPG |
| Tank Capacity | 50 gallons |

---

## Why This Is Optimal

The algorithm minimizes total fuel cost by:

- Avoiding expensive fuel whenever cheaper fuel is reachable
- Maximizing purchases only when future fuel prices are worse
- Leveraging complete route fuel-price visibility

This guarantees the minimum achievable fuel cost under the given constraints.

---

# Input Validation & Edge Cases

## Supported Validations

### U.S.-Only Locations

Both start and destination must be located in the United States.

Non-U.S. addresses return:

```json
HTTP 400 Bad Request
```

---

### Invalid Addresses

Ungеocodable addresses immediately return validation errors.

---

### Trips Under 500 Miles

Short trips may require:

- No fuel stops
- Or only minimal top-offs

---

### Corridor Expansion

To avoid false routing gaps caused by imperfect geocoding:

- Initial search corridor: 10 miles
- Automatic retries up to: 50 miles

This ensures robust station discovery.

---

# Running Without Docker

## Install Dependencies

```bash
pip install -r requirements.txt
```

---

## Configure PostgreSQL + PostGIS

Create a PostgreSQL database with PostGIS enabled.

---

## Run Migrations

```bash
python manage.py migrate
```

---

## Start Development Server

```bash
python manage.py runserver
```

---

# Example Workflow

```bash
# Start containers
docker-compose up -d

# Run migrations
docker-compose exec web python manage.py migrate

# Import fuel data
docker-compose exec web python manage.py load_fuel_data fuel-prices-for-be-assessment.csv

# Test API
curl "http://localhost:8000/api/route/?start=Chicago,IL&finish=Houston,TX"
```

---

# Future Improvements

- Redis caching for routing/geocoding
- Async fuel data loading
- Multi-vehicle support
- Fuel consumption based on elevation/traffic
- Frontend visualization dashboard
- Route alternatives comparison
- Authentication & rate limiting
- Production-grade deployment support

---

# License

This project was built as part of a technical assessment and is not intended for production deployment without additional security, scalability, and infrastructure review.