from pathlib import Path
import sqlite3

import pandas as pd
import plotly.express as px
import streamlit as st


ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "teiko.db"
OUTPUT_DIR = ROOT / "outputs"


@st.cache_data
def load_data() -> pd.DataFrame:
    query = """
    WITH totals AS (
        SELECT sample_id, SUM(count) AS total_count
        FROM cell_counts
        GROUP BY sample_id
    )
    SELECT
        p.project_name AS project,
        subj.subject_code AS subject,
        subj.condition,
        subj.sex,
        subj.treatment,
        subj.response,
        s.sample_code AS sample,
        s.sample_type,
        s.time_from_treatment_start,
        cc.population,
        cc.count,
        totals.total_count,
        100.0 * cc.count / totals.total_count AS percentage
    FROM cell_counts cc
    JOIN totals ON totals.sample_id = cc.sample_id
    JOIN samples s ON s.sample_id = cc.sample_id
    JOIN subjects subj ON subj.subject_id = s.subject_id
    JOIN projects p ON p.project_id = subj.project_id;
    """
    with sqlite3.connect(DB_PATH) as conn:
        return pd.read_sql_query(query, conn)


@st.cache_data
def load_responder_statistics() -> pd.DataFrame:
    stats_path = OUTPUT_DIR / "responder_statistics.csv"
    if not stats_path.exists():
        return pd.DataFrame()
    return pd.read_csv(stats_path)


st.set_page_config(page_title="Teiko Cell Analysis", layout="wide")
st.title("Teiko Cell Analysis")

if not DB_PATH.exists():
    st.error("Database not found. Run `make pipeline` first.")
    st.stop()

df = load_data()

with st.sidebar:
    condition = st.multiselect("Condition", sorted(df["condition"].unique()), default=sorted(df["condition"].unique()))
    treatment = st.multiselect("Treatment", sorted(df["treatment"].unique()), default=sorted(df["treatment"].unique()))
    sample_type = st.multiselect("Sample type", sorted(df["sample_type"].unique()), default=sorted(df["sample_type"].unique()))

filtered = df[
    df["condition"].isin(condition)
    & df["treatment"].isin(treatment)
    & df["sample_type"].isin(sample_type)
]

st.subheader("Relative Frequency Summary")
st.dataframe(
    filtered[["sample", "total_count", "population", "count", "percentage"]]
    .sort_values(["sample", "population"]),
    use_container_width=True,
)

st.subheader("Responder Comparison")
comparison = df[
    (df["condition"].str.lower() == "melanoma")
    & (df["treatment"].str.lower() == "miraclib")
    & (df["sample_type"].str.upper() == "PBMC")
]
fig = px.box(
    comparison,
    x="population",
    y="percentage",
    color="response",
    points="all",
    labels={"percentage": "Relative frequency (%)", "population": "Cell population"},
)
st.plotly_chart(fig, use_container_width=True)

stats_table = load_responder_statistics()
if not stats_table.empty:
    st.dataframe(
        stats_table.sort_values("p_value"),
        use_container_width=True,
        hide_index=True,
    )

st.subheader("Baseline Melanoma PBMC Miraclib Samples")
baseline = df[
    (df["condition"].str.lower() == "melanoma")
    & (df["treatment"].str.lower() == "miraclib")
    & (df["sample_type"].str.upper() == "PBMC")
    & (df["time_from_treatment_start"] == 0)
].drop_duplicates("sample")

left, middle, right = st.columns(3)
left.metric("Baseline samples", len(baseline))
middle.metric("Projects", baseline["project"].nunique())
right.metric("Subjects", baseline["subject"].nunique())

project_counts = baseline["project"].value_counts().sort_index().rename_axis("project").reset_index(name="samples")
response_counts = (
    baseline.drop_duplicates("subject")["response"]
    .value_counts()
    .sort_index()
    .rename_axis("response")
    .reset_index(name="subjects")
)
sex_counts = (
    baseline.drop_duplicates("subject")["sex"]
    .value_counts()
    .sort_index()
    .rename_axis("sex")
    .reset_index(name="subjects")
)

avg_b_cells = df[
    (df["population"] == "b_cell")
    & (df["condition"].str.lower() == "melanoma")
    & (df["sex"] == "M")
    & (df["response"] == "yes")
    & (df["time_from_treatment_start"] == 0)
]["count"].mean()

left, middle, right = st.columns(3)
with left:
    st.caption("Samples by project")
    st.dataframe(project_counts, use_container_width=True, hide_index=True)
with middle:
    st.caption("Subjects by response")
    st.dataframe(response_counts, use_container_width=True, hide_index=True)
with right:
    st.caption("Subjects by sex")
    st.dataframe(sex_counts, use_container_width=True, hide_index=True)

st.metric(
    "Average B cells for melanoma male responders at time 0",
    f"{avg_b_cells:.2f}",
)

st.dataframe(
    baseline[["project", "subject", "response", "sex", "sample", "sample_type", "time_from_treatment_start"]],
    use_container_width=True,
)
