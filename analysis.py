import sqlite3
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from scipy import stats


ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "teiko.db"
OUTPUT_DIR = ROOT / "outputs"


FREQUENCY_QUERY = """
WITH totals AS (
    SELECT sample_id, SUM(count) AS total_count
    FROM cell_counts
    GROUP BY sample_id
)
SELECT
    s.sample_code AS sample,
    totals.total_count AS total_count,
    cc.population AS population,
    cc.count AS count,
    100.0 * cc.count / totals.total_count AS percentage,
    p.project_name AS project,
    subj.subject_code AS subject,
    subj.condition,
    subj.sex,
    subj.treatment,
    subj.response,
    s.sample_type,
    s.time_from_treatment_start
FROM cell_counts cc
JOIN totals ON totals.sample_id = cc.sample_id
JOIN samples s ON s.sample_id = cc.sample_id
JOIN subjects subj ON subj.subject_id = s.subject_id
JOIN projects p ON p.project_id = subj.project_id
ORDER BY s.sample_code, cc.population;
"""


def ensure_database() -> None:
    if not DB_PATH.exists():
        raise FileNotFoundError("Run `python load_data.py` before analysis.")


def load_frequency_table(conn: sqlite3.Connection) -> pd.DataFrame:
    df = pd.read_sql_query(FREQUENCY_QUERY, conn)
    public_cols = ["sample", "total_count", "population", "count", "percentage"]
    df[public_cols].to_csv(OUTPUT_DIR / "cell_frequency_summary.csv", index=False)
    return df


def responder_statistics(frequencies: pd.DataFrame) -> pd.DataFrame:
    subset = frequencies[
        (frequencies["condition"].str.lower() == "melanoma")
        & (frequencies["treatment"].str.lower() == "miraclib")
        & (frequencies["sample_type"].str.upper() == "PBMC")
        & (frequencies["response"].isin(["yes", "no"]))
    ].copy()

    rows = []
    for population, group in subset.groupby("population"):
        responders = group.loc[group["response"] == "yes", "percentage"]
        non_responders = group.loc[group["response"] == "no", "percentage"]
        statistic, p_value = stats.ttest_ind(
            responders, non_responders, equal_var=False, nan_policy="omit"
        )
        rows.append(
            {
                "population": population,
                "responder_mean_pct": responders.mean(),
                "non_responder_mean_pct": non_responders.mean(),
                "mean_difference_pct": responders.mean() - non_responders.mean(),
                "p_value": p_value,
                "significant_at_0.05": bool(p_value < 0.05),
                "n_responder_samples": int(responders.shape[0]),
                "n_non_responder_samples": int(non_responders.shape[0]),
            }
        )

    results = pd.DataFrame(rows).sort_values("p_value")
    results.to_csv(OUTPUT_DIR / "responder_statistics.csv", index=False)

    plt.figure(figsize=(10, 6))
    sns.boxplot(data=subset, x="population", y="percentage", hue="response")
    plt.title("Melanoma PBMC miraclib relative frequencies by response")
    plt.xlabel("Cell population")
    plt.ylabel("Relative frequency (%)")
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "response_boxplot.png", dpi=160)
    plt.close()

    return results


def subset_analysis(conn: sqlite3.Connection) -> pd.DataFrame:
    baseline_query = """
    SELECT
        p.project_name AS project,
        subj.subject_code AS subject,
        subj.response,
        subj.sex,
        s.sample_code AS sample,
        s.sample_type,
        s.time_from_treatment_start
    FROM samples s
    JOIN subjects subj ON subj.subject_id = s.subject_id
    JOIN projects p ON p.project_id = subj.project_id
    WHERE lower(subj.condition) = 'melanoma'
      AND lower(subj.treatment) = 'miraclib'
      AND upper(s.sample_type) = 'PBMC'
      AND s.time_from_treatment_start = 0
    ORDER BY p.project_name, subj.subject_code, s.sample_code;
    """
    baseline = pd.read_sql_query(baseline_query, conn)
    baseline.to_csv(OUTPUT_DIR / "baseline_melanoma_miraclib_pbmc_samples.csv", index=False)

    summary_rows = []
    for label, counts in {
        "samples_by_project": baseline["project"].value_counts().sort_index(),
        "subjects_by_response": baseline.drop_duplicates("subject")["response"]
        .value_counts()
        .sort_index(),
        "subjects_by_sex": baseline.drop_duplicates("subject")["sex"].value_counts().sort_index(),
    }.items():
        for category, count in counts.items():
            summary_rows.append({"metric": label, "category": category, "count": int(count)})

    average_query = """
    SELECT AVG(cc.count) AS average_b_cells
    FROM cell_counts cc
    JOIN samples s ON s.sample_id = cc.sample_id
    JOIN subjects subj ON subj.subject_id = s.subject_id
    WHERE cc.population = 'b_cell'
      AND lower(subj.condition) = 'melanoma'
      AND subj.sex = 'M'
      AND subj.response = 'yes'
      AND s.time_from_treatment_start = 0;
    """
    avg_b_cells = pd.read_sql_query(average_query, conn).loc[0, "average_b_cells"]
    summary_rows.append(
        {
            "metric": "avg_b_cells_melanoma_male_responders_time_0",
            "category": "all_sample_and_treatment_types",
            "count": f"{avg_b_cells:.2f}",
        }
    )

    summary = pd.DataFrame(summary_rows)
    summary.to_csv(OUTPUT_DIR / "subset_summary.csv", index=False)
    return summary


def main() -> None:
    ensure_database()
    OUTPUT_DIR.mkdir(exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        frequencies = load_frequency_table(conn)
        stats_table = responder_statistics(frequencies)
        subset = subset_analysis(conn)

    print("Wrote outputs:")
    for output in sorted(OUTPUT_DIR.iterdir()):
        print(f"- {output.relative_to(ROOT)}")
    print("\nSignificant responder differences:")
    significant = stats_table[stats_table["significant_at_0.05"]]
    print(significant[["population", "mean_difference_pct", "p_value"]].to_string(index=False))
    print("\nSubset summary:")
    print(subset.to_string(index=False))


if __name__ == "__main__":
    main()
