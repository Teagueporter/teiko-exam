from pathlib import Path
import sqlite3

import pandas as pd
import plotly.express as px
import streamlit as st
from scipy import stats


ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "teiko.db"


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


def checkbox_filter(label: str, options: list[str]) -> list[str]:
    st.caption(label)
    cols = st.columns(len(options))
    selected = []
    for col, option in zip(cols, options):
        if col.checkbox(option, value=True, key=f"{label}-{option}"):
            selected.append(option)
    return selected


def responder_statistics(comparison: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for population, group in comparison.groupby("population"):
        responders = group.loc[group["response"] == "yes", "percentage"]
        non_responders = group.loc[group["response"] == "no", "percentage"]
        _, p_value = stats.ttest_ind(responders, non_responders, equal_var=False)
        rows.append(
            {
                "population": population,
                "responder_mean_pct": responders.mean(),
                "non_responder_mean_pct": non_responders.mean(),
                "mean_difference_pct": responders.mean() - non_responders.mean(),
                "p_value": p_value,
                "significant_at_0.05": p_value < 0.05,
            }
        )
    return pd.DataFrame(rows).sort_values("p_value")


st.set_page_config(page_title="Teiko Cell Analysis", layout="wide")
st.title("Teiko Cell Analysis")

if not DB_PATH.exists():
    st.error("Database not found. Run `make pipeline` first.")
    st.stop()

df = load_data()

st.subheader("Relative Frequency Summary")
condition_options = sorted(df["condition"].unique())
treatment_options = sorted(df["treatment"].unique())
sample_type_options = sorted(df["sample_type"].unique())

filter_cols = st.columns(3)
with filter_cols[0]:
    condition = checkbox_filter("Condition", condition_options)
with filter_cols[1]:
    treatment = checkbox_filter("Treatment", treatment_options)
with filter_cols[2]:
    sample_type = checkbox_filter("Sample type", sample_type_options)

filtered = df[
    df["condition"].isin(condition)
    & df["treatment"].isin(treatment)
    & df["sample_type"].isin(sample_type)
]

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
    & (df["response"].isin(["yes", "no"]))
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

st.dataframe(responder_statistics(comparison), use_container_width=True, hide_index=True)

st.subheader("Baseline Melanoma PBMC Miraclib Samples")
baseline = df[
    (df["condition"].str.lower() == "melanoma")
    & (df["treatment"].str.lower() == "miraclib")
    & (df["sample_type"].str.upper() == "PBMC")
    & (df["time_from_treatment_start"] == 0)
].drop_duplicates("sample")
baseline_subjects = baseline.drop_duplicates(["project", "subject"])

left, middle, right = st.columns(3)
left.metric("Baseline samples", len(baseline))
middle.metric("Projects", baseline["project"].nunique())
right.metric("Subjects", len(baseline_subjects))

project_counts = (
    baseline["project"]
    .value_counts()
    .sort_index()
    .rename_axis("project")
    .reset_index(name="samples")
)
response_counts = (
    baseline_subjects["response"]
    .value_counts()
    .sort_index()
    .rename_axis("response")
    .reset_index(name="subjects")
)
sex_counts = (
    baseline_subjects["sex"]
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
    baseline[
        [
            "project",
            "subject",
            "response",
            "sex",
            "sample",
            "sample_type",
            "time_from_treatment_start",
        ]
    ],
    use_container_width=True,
)
