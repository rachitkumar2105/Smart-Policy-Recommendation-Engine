"""Load test for POST /api/v1/recommend.

Run against a live backend (with the policy catalog seeded):
    locust -f locustfile.py --headless -u 50 -r 5 --run-time 1m --host http://localhost:8000
"""

import random

from locust import HttpUser, between, task

OCCUPATIONS = ["DESK_JOB", "HAZARDOUS", "UNEMPLOYED"]


class SPREUser(HttpUser):
    wait_time = between(1, 3)

    @task(5)
    def get_recommendation(self):
        self.client.post(
            "/api/v1/recommend",
            json={
                "full_name": "Load Test User",
                "age": random.randint(18, 80),
                "monthly_income": random.randint(0, 150000),
                "occupation": random.choice(OCCUPATIONS),
                "is_smoker": random.choice([True, False]),
                "has_chronic_illness": random.choice([True, False]),
                "owns_vehicle": random.choice([True, False]),
                "vehicle_value": random.randint(0, 2000000),
                "owns_property": random.choice([True, False]),
                "property_value": random.randint(0, 10000000),
            },
        )

    @task(1)
    def list_policies(self):
        self.client.get("/api/v1/policies")

    @task(1)
    def health_check(self):
        self.client.get("/health")
