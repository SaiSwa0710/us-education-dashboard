import os
import pandas as pd
import streamlit as st
import plotly.express as px
from pyathena import connect

st.set_page_config(page_title="US Education Dashboard", layout="wide")
st.title("US Education Dashboard")

REGION = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
DB = "us_education_curated"
RESULTS_S3 = "s3://us-education-pipeline-2025/athena-results/"

# Prefer the view you created earlier. If you didn't create it, we'll fallback.
PREFERRED_SOURCE = "v_state_year_metrics"
FALLBACK_SOURCE = "states_all"

STATE_TO_CODE = {
    "Alabama":"AL","Alaska":"AK","Arizona":"AZ","Arkansas":"AR","California":"CA",
    "Colorado":"CO","Connecticut":"CT","Delaware":"DE","District of Columbia":"DC",
    "Florida":"FL","Georgia":"GA","Hawaii":"HI","Idaho":"ID","Illinois":"IL",
    "Indiana":"IN","Iowa":"IA","Kansas":"KS","Kentucky":"KY","Louisiana":"LA",
    "Maine":"ME","Maryland":"MD","Massachusetts":"MA","Michigan":"MI","Minnesota":"MN",
    "Mississippi":"MS","Missouri":"MO","Montana":"MT","Nebraska":"NE","Nevada":"NV",
    "New Hampshire":"NH","New Jersey":"NJ","New Mexico":"NM","New York":"NY",
    "North Carolina":"NC","North Dakota":"ND","Ohio":"OH","Oklahoma":"OK","Oregon":"OR",
    "Pennsylvania":"PA","Rhode Island":"RI","South Carolina":"SC","South Dakota":"SD",
    "Tennessee":"TN","Texas":"TX","Utah":"UT","Vermont":"VT","Virginia":"VA",
    "Washington":"WA","West Virginia":"WV","Wisconsin":"WI","Wyoming":"WY"
}

def get_conn():
    return connect(
        s3_staging_dir=RESULTS_S3,
        region_name=REGION,
        schema_name=DB
    )

@st.cache_data(ttl=900)
def athena_df(sql: str) -> pd.DataFrame:
    return pd.read_sql(sql, get_conn())

@st.cache_data(ttl=3600)
def pick_source() -> str:
    q = f"""
    SELECT table_name
    FROM information_schema.tables
    WHERE table_schema = '{DB}'
    """
    tables = set(athena_df(q)["table_name"].str.lower())
    return PREFERRED_SOURCE if PREFERRED_SOURCE.lower() in tables else FALLBACK_SOURCE

SOURCE = pick_source()

@st.cache_data(ttl=3600)
def get_states():
    q_states = f"SELECT DISTINCT state FROM {SOURCE} ORDER BY state"
    return athena_df(q_states)["state"].dropna().tolist()


# metric mapping depends on whether we have the view
if SOURCE == PREFERRED_SOURCE:
    metric_options = {
        "Expenditure per student": "expenditure_per_student",
        "Revenue per student": "revenue_per_student",
        "Surplus / Deficit": "surplus_deficit",
        "Total Expenditure": "total_expenditure",
        "Total Revenue": "total_revenue",
    }
    years_sql = f"SELECT DISTINCT year FROM {SOURCE} ORDER BY year"
else:
    # fallback: compute metrics on the fly (works, but slower / less “clean”)
    metric_options = {
        "Expenditure per student": "total_expenditure / NULLIF(enroll, 0)",
        "Revenue per student": "total_revenue / NULLIF(enroll, 0)",
        "Surplus / Deficit": "total_revenue - total_expenditure",
        "Total Expenditure": "total_expenditure",
        "Total Revenue": "total_revenue",
    }
    years_sql = f"SELECT DISTINCT CAST(year AS integer) AS year FROM {SOURCE} ORDER BY year"

years = athena_df(years_sql)["year"].astype(int).tolist()
min_year, max_year = min(years), max(years)

c1, c2, c3 = st.columns([2, 3, 2])
with c1:
    metric_label = st.selectbox("Metric", list(metric_options.keys()), index=0)
with c2:
    year = st.slider("Year", min_year, max_year, max_year)
with c3:
    st.caption(f"Source: {SOURCE}")

metric_expr = metric_options[metric_label]

# Pull data for selected year
if SOURCE == PREFERRED_SOURCE:
    q = f"""
    SELECT state, year, {metric_expr} AS metric, enroll, total_revenue, total_expenditure
    FROM {SOURCE}
    WHERE year = {year}
    """
else:
    q = f"""
    SELECT state,
           CAST(year AS integer) AS year,
           {metric_expr} AS metric,
           enroll, total_revenue, total_expenditure
    FROM {SOURCE}
    WHERE CAST(year AS integer) = {year}
    """

df = athena_df(q)
def to_state_code(s: str):
    if s is None:
        return None

    s = str(s).strip()

    # If already a 2-letter code, keep it
    if len(s) == 2 and s.isalpha():
        return s.upper()

    # Normalize: underscores -> spaces, collapse whitespace, and standardize case
    s_norm = s.replace("_", " ").strip()
    s_norm = " ".join(s_norm.split())  # collapse multiple spaces

    # Try title-case match: "new mexico" -> "New Mexico"
    s_title = s_norm.title()
    if s_title in STATE_TO_CODE:
        return STATE_TO_CODE[s_title]

    # Try uppercase match
    upper_map = {k.upper(): v for k, v in STATE_TO_CODE.items()}
    s_upper = s_norm.upper()
    return upper_map.get(s_upper)


df["state_code"] = df["state"].apply(to_state_code)

# DEBUG: show mapping success rate
# st.caption(f"Rows from Athena: {len(df)} | Mapped state codes: {df['state_code'].notna().sum()}")

# Only drop after we’ve shown debug info
df = df.dropna(subset=["state_code"])


# KPI cards
k1, k2, k3, k4 = st.columns(4)
k1.metric("States in view", f"{df['state'].nunique()}")
k2.metric("Avg metric", f"{df['metric'].mean():,.2f}" if df["metric"].notna().any() else "—")
k3.metric("Max metric", f"{df['metric'].max():,.2f}" if df["metric"].notna().any() else "—")
k4.metric("Min metric", f"{df['metric'].min():,.2f}" if df["metric"].notna().any() else "—")

left, right = st.columns([2.2, 1])

with left:
    fig = px.choropleth(
        df,
        locations="state_code",
        locationmode="USA-states",
        color="metric",
        scope="usa",
        hover_name="state",
        hover_data={"state_code": False, "metric": True, "enroll": True, "total_revenue": True, "total_expenditure": True},
        labels={"metric": metric_label},
    )
    fig.update_layout(margin=dict(l=0, r=0, t=0, b=0))
    st.plotly_chart(fig, use_container_width=True)

with right:
    st.subheader(f"{metric_label} — {year}")
    top = df.sort_values("metric", ascending=False).head(10)[["state", "metric"]]
    bottom = df.sort_values("metric", ascending=True).head(10)[["state", "metric"]]
    st.write("Top 10")
    st.dataframe(top, use_container_width=True, height=240)
    st.write("Bottom 10")
    st.dataframe(bottom, use_container_width=True, height=240)

states_list = get_states()
selected_state = st.selectbox("Drill into a state", states_list, index=states_list.index("NEW_YORK") if "NEW_YORK" in states_list else 0)

st.divider()
st.subheader(f"Trend: {selected_state.replace('_',' ').title()} vs National")

# Use view columns if available
if SOURCE == PREFERRED_SOURCE:
    state_trend_q = f"""
    SELECT year, {metric_expr} AS metric
    FROM {SOURCE}
    WHERE state = '{selected_state}'
    ORDER BY year
    """
else:
    state_trend_q = f"""
    SELECT CAST(year AS integer) AS year, {metric_expr} AS metric
    FROM {SOURCE}
    WHERE state = '{selected_state}'
    ORDER BY CAST(year AS integer)
    """

# National line (always use v_national_summary if it exists)
# We'll detect it and fallback if needed.
@st.cache_data(ttl=3600)
def has_table_or_view(name: str) -> bool:
    q = f"""
    SELECT table_name
    FROM information_schema.tables
    WHERE table_schema = '{DB}'
      AND lower(table_name) = lower('{name}')
    """
    return len(athena_df(q)) > 0

use_national = has_table_or_view("v_national_summary")

if use_national:
    # national spend per student exists in the view, but for other metrics we approximate:
    # - revenue per student: national_revenue/national_enrollment
    # - surplus_deficit: national_revenue - national_expenditure (total, not per student)
    # We'll compute a "national metric" that matches the selected metric label as best as possible.
    if metric_label == "Expenditure per student":
        nat_expr = "national_spend_per_student"
    elif metric_label == "Revenue per student":
        nat_expr = "national_revenue / NULLIF(national_enrollment, 0)"
    elif metric_label == "Surplus / Deficit":
        nat_expr = "national_revenue - national_expenditure"
    elif metric_label == "Total Expenditure":
        nat_expr = "national_expenditure"
    elif metric_label == "Total Revenue":
        nat_expr = "national_revenue"
    else:
        nat_expr = "national_spend_per_student"

    national_q = f"""
    SELECT year, {nat_expr} AS metric
    FROM v_national_summary
    ORDER BY year
    """
else:
    # fallback: compute national aggregate from SOURCE directly
    if SOURCE == PREFERRED_SOURCE:
        national_q = f"""
        SELECT
          year,
          AVG({metric_expr}) AS metric
        FROM {SOURCE}
        GROUP BY year
        ORDER BY year
        """
    else:
        national_q = f"""
        SELECT
          CAST(year AS integer) AS year,
          AVG({metric_expr}) AS metric
        FROM {SOURCE}
        GROUP BY CAST(year AS integer)
        ORDER BY CAST(year AS integer)
        """

state_trend = athena_df(state_trend_q)
national_trend = athena_df(national_q)

state_trend["series"] = selected_state.replace("_"," ").title()
national_trend["series"] = "National"

trend = pd.concat([state_trend, national_trend], ignore_index=True)
trend = trend.dropna(subset=["year", "metric"])
trend["year"] = trend["year"].astype(int)

fig2 = px.line(
    trend,
    x="year",
    y="metric",
    color="series",
    markers=True,
    labels={"metric": metric_label, "year": "Year", "series": ""},
)

fig2.update_layout(margin=dict(l=0, r=0, t=10, b=0))
st.plotly_chart(fig2, use_container_width=True)

# KPI delta for selected year
try:
    st_year_val = float(state_trend[state_trend["year"].astype(int) == year]["metric"].iloc[0])
    nat_year_val = float(national_trend[national_trend["year"].astype(int) == year]["metric"].iloc[0])
    delta = st_year_val - nat_year_val
    st.caption(f"{selected_state.replace('_',' ').title()} vs National in {year}: {delta:,.2f} ({metric_label})")
except Exception:
    pass