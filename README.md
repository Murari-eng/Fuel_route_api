# Fuel Route API

A Django REST API that, given a start and end location within the USA, returns
the driving route along with the cost-optimal fuel stops, given a vehicle
with a 500-mile range and 10 MPG fuel economy.

## Overview

The API accepts a POST request with start and end coordinates. It:

1. Fetches the driving route from a routing provider (OSRM by default; one
   external API call per request).
2. Aligns the OPIS truckstop dataset against the route polyline to find all
   stations within a few miles of the route.
3. Runs a greedy algorithm to select fuel stops: at each step, choose the
   cheapest station reachable within the vehicle's remaining range.
4. Returns the route geometry, the chosen fuel stops, and the total fuel cost.

## Requirements

- Python 3.10+
- Django 5.x
- Django REST Framework
- pandas

Install dependencies:

```bash
pip install -r requirements.txt
