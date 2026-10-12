
import math
from decimal import Decimal

import requests

from fuel_route_optimizer.models import FuelStation


OSRM_URL = "https://router.project-osrm.org"
EARTH_RADIUS_MILES = 3958.8
METERS_PER_MILE = 1609.344
ROUTE_CORRIDOR_MILES = 15
SAFETY_MARGIN_MILES = 20


def haversine_miles(lat1, lon1, lat2, lon2):
    """Calculate straight-line distance between two coordinates."""

    lat1, lon1, lat2, lon2 = map(
        math.radians,
        [lat1, lon1, lat2, lon2],
    )

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1)
        * math.cos(lat2)
        * math.sin(dlon / 2) ** 2
    )

    return 2 * EARTH_RADIUS_MILES * math.asin(
        math.sqrt(min(1, a))
    )


def get_road_route(start_lon, start_lat, end_lon, end_lat):
    """Get a road route from OSRM without an API key."""

    url = (
        f"{OSRM_URL}/route/v1/driving/"
        f"{start_lon},{start_lat};{end_lon},{end_lat}"
    )

    response = requests.get(
        url,
        params={
            "overview": "full",
            "geometries": "geojson",
            "steps": "false",
        },
        timeout=20,
    )
    response.raise_for_status()

    data = response.json()

    if data.get("code") != "Ok" or not data.get("routes"):
        raise ValueError("OSRM could not find a driving route.")

    route = data["routes"][0]

    return {
        "distance_miles": route["distance"] / METERS_PER_MILE,
        "duration_minutes": route["duration"] / 60,
        "coordinates": route["geometry"]["coordinates"],
    }


def project_station_onto_route(station, coordinates):
    """
    Estimate a station's distance along the route and its
    distance from the nearest route segment.

    Route coordinates use [longitude, latitude].
    """

    cumulative_miles = 0
    best_distance = float("inf")
    best_route_position = None

    for index in range(len(coordinates) - 1):
        lon1, lat1 = coordinates[index]
        lon2, lat2 = coordinates[index + 1]

        segment_length = haversine_miles(
            lat1, lon1, lat2, lon2
        )

        if segment_length == 0:
            continue

        mean_lat = math.radians(
            (lat1 + lat2 + station.latitude) / 3
        )

        scale_x = 69.172 * math.cos(mean_lat)
        scale_y = 69.0

        ax = (lon1 - station.longitude) * scale_x
        ay = (lat1 - station.latitude) * scale_y
        bx = (lon2 - station.longitude) * scale_x
        by = (lat2 - station.latitude) * scale_y

        dx = bx - ax
        dy = by - ay
        denominator = dx * dx + dy * dy

        if denominator == 0:
            fraction = 0
        else:
            fraction = max(
                0,
                min(1, -(ax * dx + ay * dy) / denominator),
            )

        nearest_x = ax + fraction * dx
        nearest_y = ay + fraction * dy

        distance_from_route = math.hypot(
            nearest_x, nearest_y
        )

        if distance_from_route < best_distance:
            best_distance = distance_from_route
            best_route_position = (
                cumulative_miles + fraction * segment_length
            )

        cumulative_miles += segment_length

    return best_route_position, best_distance


def find_stations_near_route(coordinates, route_distance_miles):
    """Find stations in a corridor around the route."""

    stations = FuelStation.objects.all()
    candidates = []

    for station in stations.iterator():
        route_position, distance_from_route = (
            project_station_onto_route(station, coordinates)
        )

        if route_position is None:
            continue

        if (
            distance_from_route <= ROUTE_CORRIDOR_MILES
            and 0 < route_position < route_distance_miles
        ):
            candidates.append({
                "station": station,
                "route_position_miles": route_position,
                "distance_from_route_miles": distance_from_route,
            })

    return sorted(
        candidates,
        key=lambda item: item["route_position_miles"],
    )


def choose_fuel_stops(
    candidates,
    route_distance_miles,
    max_range_miles,
):
    """
    Select affordable reachable stations along the route.

    Assumes the vehicle starts with a full tank. A 20-mile
    safety margin is used when choosing intermediate stops.
    """

    stops = []
    current_position = 0.0
    max_stops = math.ceil(
        route_distance_miles / max_range_miles
    ) + 2

    for _ in range(max_stops):
        remaining = route_distance_miles - current_position

        if remaining <= max_range_miles:
            return stops

        safe_reach = current_position + max(
            0, max_range_miles - SAFETY_MARGIN_MILES
        )

        reachable = [
            item
            for item in candidates
            if (
                current_position + 1
                < item["route_position_miles"]
                <= safe_reach
            )
        ]

        if not reachable:
            raise ValueError(
                "No fuel station found within the vehicle's "
                "safe driving range. Try a larger route corridor "
                "or add more fuel station data."
            )
        selected = min(
            reachable,
            key=lambda item: (
                Decimal(str(item["station"].price_per_gallon)),
                -item["route_position_miles"],
            ),
        )

        stops.append(selected)
        current_position = selected["route_position_miles"]

        candidates = [
            item for item in candidates
            if item["route_position_miles"] > current_position
        ]

    if route_distance_miles - current_position > max_range_miles:
        raise ValueError("Could not find a feasible fuel-stop plan.")

    return stops


def optimize_fuel_route(
    start_latitude,
    start_longitude,
    end_latitude,
    end_longitude,
    mpg=10,
    max_range_miles=500,
):
    """Calculate the route and suggest economical fuel stops."""

    route = get_road_route(
        start_longitude,
        start_latitude,
        end_longitude,
        end_latitude,
    )

    route_distance = route["distance_miles"]

    candidates = find_stations_near_route(
        route["coordinates"],
        route_distance,
    )

    stops = choose_fuel_stops(
        candidates,
        route_distance,
        max_range_miles,
    )
    current_position = 0.0
    total_fuel_cost = 0.0
    stop_results = []

    for item in stops:
        position = item["route_position_miles"]
        leg_distance = position - current_position
        station = item["station"]

        gallons = leg_distance / mpg
        leg_cost = gallons * float(station.price_per_gallon)
        total_fuel_cost += leg_cost

        stop_results.append({
            "station_id": station.station_id,
            "name": station.name,
            "address": station.address,
            "latitude": station.latitude,
            "longitude": station.longitude,
            "price_per_gallon": float(station.price_per_gallon),
            "route_position_miles": round(position, 2),
            "distance_from_route_miles": round(
                item["distance_from_route_miles"], 2
            ),
            "estimated_leg_gallons": round(gallons, 2),
            "estimated_leg_fuel_cost": round(leg_cost, 2),
        })

        current_position = position

    final_leg_distance = route_distance - current_position
    if stops:
        final_price = float(
            stops[-1]["station"].price_per_gallon
        )
    elif candidates:
        final_price = min(
            float(item["station"].price_per_gallon)
            for item in candidates
        )
    else:
        final_price = 0.0

    final_leg_gallons = final_leg_distance / mpg
    final_leg_cost = final_leg_gallons * final_price
    total_fuel_cost += final_leg_cost

    return {
        "route_distance_miles": round(route_distance, 2),
        "estimated_duration_minutes": round(
            route["duration_minutes"], 2
        ),
        "mpg": mpg,
        "max_range_miles": max_range_miles,
        "estimated_total_gallons": round(
            route_distance / mpg, 2
        ),
        "estimated_fuel_cost": round(total_fuel_cost,2),
        "fuel_stops": stop_results,
        "stations_considered": len(candidates),
        "routing_provider": "OSRM",
        "api_key_required": False,
        "cost_estimate_note": (
            "Approximate fuel cost. Station detours and exact "
            "refueling quantities are not routed individually."
        ),
    }