import os

import httpx
import pandas as pd
import streamlit as st

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

st.set_page_config(page_title="Smart Policy Recommendation Engine", page_icon="🛡️", layout="centered")

st.title("🛡️ Smart Policy Recommendation Engine")
st.caption(
    "Simulates an insurance underwriting workflow: submit a risk profile and get "
    "ranked, explainable policy recommendations with a risk-adjusted premium."
)

with st.form("risk_profile_form"):
    st.subheader("Your Risk Profile")

    col1, col2 = st.columns(2)
    with col1:
        full_name = st.text_input("Full name", value="Jane Doe")
        age = st.number_input("Age", min_value=18, max_value=100, value=30)
        monthly_income = st.number_input("Monthly income", min_value=0.0, value=50000.0, step=1000.0)
        occupation = st.selectbox("Occupation", ["DESK_JOB", "HAZARDOUS", "UNEMPLOYED"])

    with col2:
        is_smoker = st.checkbox("Smoker")
        has_chronic_illness = st.checkbox("Has a chronic illness")
        owns_vehicle = st.checkbox("Owns a vehicle")
        vehicle_value = st.number_input(
            "Vehicle value", min_value=0.0, value=0.0, step=10000.0, disabled=not owns_vehicle
        )
        owns_property = st.checkbox("Owns property")
        property_value = st.number_input(
            "Property value", min_value=0.0, value=0.0, step=50000.0, disabled=not owns_property
        )

    submitted = st.form_submit_button("Get Recommendations", type="primary")

if submitted:
    payload = {
        "full_name": full_name,
        "age": int(age),
        "monthly_income": monthly_income,
        "occupation": occupation,
        "is_smoker": is_smoker,
        "has_chronic_illness": has_chronic_illness,
        "owns_vehicle": owns_vehicle,
        "vehicle_value": vehicle_value if owns_vehicle else 0,
        "owns_property": owns_property,
        "property_value": property_value if owns_property else 0,
    }

    try:
        with st.spinner("Scoring policies against your risk profile..."):
            resp = httpx.post(f"{BACKEND_URL}/api/v1/recommend", json=payload, timeout=10.0)
    except httpx.RequestError as exc:
        st.error(f"Could not reach the backend at {BACKEND_URL}: {exc}")
        st.stop()

    if resp.status_code == 422:
        st.error("Please check your inputs — the backend rejected the request as invalid.")
        st.json(resp.json())
        st.stop()
    elif resp.status_code == 429:
        st.warning("Rate limit exceeded. Please wait a moment and try again.")
        st.stop()
    elif resp.status_code != 200:
        st.error(f"Backend returned an unexpected error ({resp.status_code}).")
        st.stop()

    data = resp.json()
    recommendations = data["recommendations"]

    st.success(f"Generated {len(recommendations)} recommendation(s) for customer #{data['customer_id']}.")

    if not recommendations:
        st.info("No policies matched your risk profile's eligibility criteria (age / income).")
    else:
        for rec in recommendations:
            with st.container(border=True):
                st.markdown(f"**#{rec['rank']} — {rec['policy_name']}** ({rec['policy_type']})")
                col_a, col_b = st.columns(2)
                col_a.metric("Suitability score", f"{rec['suitability_score']:.1f} / 100")
                col_b.metric("Final premium", f"₹{rec['final_premium']:.2f}")
                st.caption(rec["reasoning"])

        chart_df = pd.DataFrame(
            {
                "Policy": [f"#{r['rank']} {r['policy_name']}" for r in recommendations],
                "Suitability Score": [r["suitability_score"] for r in recommendations],
            }
        ).set_index("Policy")
        st.subheader("Suitability Comparison")
        st.bar_chart(chart_df)

st.divider()
with st.expander("View active policy catalog"):
    try:
        policies_resp = httpx.get(f"{BACKEND_URL}/api/v1/policies", timeout=10.0)
        if policies_resp.status_code == 200:
            st.dataframe(pd.DataFrame(policies_resp.json()), use_container_width=True)
        else:
            st.warning("Could not load the policy catalog.")
    except httpx.RequestError as exc:
        st.warning(f"Could not reach the backend at {BACKEND_URL}: {exc}")
