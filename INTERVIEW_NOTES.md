# Interview Notes

## One-sentence summary

The project loads the cell-count CSV into SQLite, calculates per-sample immune-cell frequencies, compares melanoma PBMC miraclib responders with non-responders, writes output files, and shows the results in a Streamlit dashboard.

## What the assignment asked for

The assignment asked for four pieces:

1. Create a SQLite schema and a root-level `load_data.py` script that loads `cell-count.csv` into a `.db` file.
2. Calculate each immune population's relative frequency within each sample.
3. Compare relative frequencies between melanoma PBMC miraclib responders and non-responders, visualize the comparison with boxplots, and report statistically significant populations.
4. Query the baseline melanoma PBMC miraclib subset and report project, response, sex, and B-cell summary counts.

It also asked for a dashboard, a README, generated input/output files, and a Makefile with `setup`, `pipeline`, and `dashboard` targets.

## Why SQLite

I used SQLite because the prompt asked for it. It also fits this project well: it creates one `.db` file, needs no database server, and works cleanly in Codespaces.

## Why the schema is normalized

The database has four tables:

- `projects`
- `subjects`
- `samples`
- `cell_counts`

This separates information by what it describes:

- project data belongs in `projects`
- subject metadata belongs in `subjects`
- sample metadata belongs in `samples`
- immune population counts belong in `cell_counts`

This avoids repeated metadata. In the CSV, each sample row repeats project and subject information. In the database, that information is stored once and linked by keys.

The other important decision is storing cell populations as rows in `cell_counts`, not as five hard-coded columns. That makes analytics easier because every population can be grouped, filtered, or compared using the same query pattern. If more immune populations were added later, the schema would not need to change.

## Why subject uniqueness is project-scoped

The schema uses `UNIQUE(project_id, subject_code)` for subjects. A subject code only needs to be unique inside a project.

That is safer than assuming subject codes are globally unique forever. In multi-project clinical data, two projects can easily reuse the same subject naming convention. Project-scoped uniqueness handles that case cleanly.

## Why response can be NULL

Some rows have blank response values, especially healthy/control rows where treatment response is not meaningful. The schema allows `response` to be `NULL` rather than inventing a fake value.

The responder analysis filters to `response IN ('yes', 'no')`, so only valid responder/non-responder samples are compared.

## Why relative frequency is calculated

Raw counts can be misleading when samples have different total cell counts. Relative frequency answers Bob's first question directly: what percentage of each sample is made up by each immune population?

The formula is:

```text
percentage = population_count / total_sample_count * 100
```

## Why Welch's t-test

The responder analysis compares two independent groups:

- responders
- non-responders

I used Welch's two-sample t-test because it compares group means without assuming both groups have equal variance. That is a reasonable default here because biological measurements often have different variability between groups.

The project marks results significant when:

```text
p_value < 0.05
```

The significant result in this dataset is:

```text
cd4_t_cell
p_value = 0.005013
mean_difference_pct = 0.635547
```

Responders had a higher average CD4 T-cell relative frequency than non-responders by about 0.64 percentage points.

## Why Streamlit

I used Streamlit because it gives us an interactive dashboard without much extra code. For this project, the dashboard just needs to show tables, filters, and the responder comparison plot.

The dashboard reads from the same SQLite database as the analysis pipeline.

## Why the Makefile uses a virtual environment

The Makefile creates a local `.venv` because modern Python installations often block global package installation. A project-local virtual environment also avoids changing the user's system Python.

The required commands are:

```bash
make setup
make pipeline
make dashboard
```

## How to explain the pipeline

The pipeline is:

```text
cell-count.csv
  -> load_data.py
  -> teiko.db
  -> analysis.py
  -> outputs/*.csv and outputs/response_boxplot.png
  -> dashboard.py
```

`load_data.py` handles the database. `analysis.py` handles the calculations. `dashboard.py` handles the interactive view.

## Final results to know

Database contents:

- 3 projects
- 3,500 subjects
- 10,500 samples
- 52,500 cell-count records

Responder comparison:

- `cd4_t_cell` is significant at the 0.05 level.
- `p_value = 0.005013`
- responders are higher by about `0.64` percentage points.

Baseline melanoma PBMC miraclib subset:

- `prj1 = 384` samples
- `prj3 = 272` samples
- `yes = 331` responder subjects
- `no = 325` non-responder subjects
- `M = 344` subjects
- `F = 312` subjects
- average B-cell count for melanoma male responders at time 0 is `10206.15`

## Likely interview questions

**Why not keep the CSV shape exactly as-is in the database?**

Keeping the CSV shape would work for this small file, but it would hard-code the five cell populations into the schema. The long `cell_counts` table makes it easier to add more populations and run the same analysis across every population.

**Why not use a more complex statistical model?**

The assignment asked for a direct comparison between responders and non-responders. Welch's t-test is easy to explain and works for an initial analysis. A larger production analysis might use regression models to control for time point, project, sex, age, and repeated samples per subject.

**What is one limitation of the analysis?**

Samples from the same subject may not be fully independent because subjects can have multiple time points. This follows the requested comparison, but a more advanced analysis could use subject-level aggregation or a mixed-effects model.

**Why include generated outputs in the repository?**

The assignment requested input and output files. Including outputs makes it easy for reviewers to inspect the results without rerunning the pipeline, while the Makefile still allows them to reproduce everything.
