# US Education Analytics Pipeline

End-to-end **AWS-native analytics pipeline** that ingests public US education data, performs **Spark-based ETL using AWS Glue**, models analytics with **Athena views**, and serves an **interactive Streamlit dashboard**.

> ⚠️ Deployment note: The Streamlit dashboard is deployed on **Streamlit Community Cloud** (free tier). AWS App Runner was evaluated but not used due to being a paid service.

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Architecture Diagram](#architecture-diagram)
3. [Data Flow](#data-flow)
4. [AWS Setup](#aws-setup)

   * S3 Data Lake
   * Glue Catalog & Crawlers
   * Glue Spark ETL Job
5. [Analytics Layer (Athena)](#analytics-layer-athena)
6. [IAM & Security](#iam--security)
7. [Dashboard Development](#dashboard-development)
8. [Local Development & Testing](#local-development--testing)
9. [Docker & CI/CD (Planned)](#docker--cicd-planned)
10. [Deployment on Streamlit Community Cloud](#deployment-on-streamlit-community-cloud)
11. [Cost Awareness](#cost-awareness)
12. [Key Learnings](#key-learnings)

---

## Project Overview

This project demonstrates a **production-style analytics pipeline** using AWS managed services and best practices:

* Immutable raw data storage
* Distributed Spark ETL
* Columnar Parquet storage with partitioning
* SQL-based semantic modeling
* Stateless dashboard consuming Athena
* Strong IAM separation and cost control

The dataset used is the **US Education Dataset (Kaggle)** containing state-level education metrics over time.

### 🔗 Live Dashboard

The deployed Streamlit dashboard is publicly accessible here:

👉 **[https://us-education-dashboard-t9qcrknkq2e9w7wat6erbz.streamlit.app/](https://us-education-dashboard-t9qcrknkq2e9w7wat6erbz.streamlit.app/)**

This dashboard is hosted on **Streamlit Community Cloud** and queries Amazon Athena directly using secure IAM credentials stored as application secrets.

---

## Architecture Diagram

```text
                    +-------------------+
                    |   Kaggle Dataset  |
                    +---------+---------+
                              |
                              v
+-------------------+   +--------------+   +----------------------+
|      Raw Zone     |   | Glue Crawler |   | Glue Data Catalog    |
|   S3 (CSV)        +-->|  (Raw)       +-->|  raw table           |
+-------------------+   +--------------+   +----------+-----------+
                                                             |
                                                             v
                                                +----------------------+
                                                | Glue Spark ETL Job   |
                                                | (CSV -> Parquet)     |
                                                +----------+-----------+
                                                             |
                                                             v
+-------------------+   +--------------+   +----------------------+
|   Curated Zone    |   | Glue Crawler |   | Glue Data Catalog    |
| S3 (Parquet/year=)|<--+  (Curated)  +-->| curated table        |
+-------------------+   +--------------+   +----------+-----------+
                                                             |
                                                             v
                                                    +----------------+
                                                    | Amazon Athena  |
                                                    | SQL Views      |
                                                    +-------+--------+
                                                            |
                                                            v
                                                +------------------------+
                                                | Streamlit Dashboard    |
                                                | (Community Cloud)      |
                                                +------------------------+
```

---

## Data Flow

1. Raw CSV uploaded to **S3 raw zone**
2. Glue Crawler infers schema
3. Glue Spark job cleans & transforms data
4. Data written as **Parquet**, partitioned by `year`
5. Curated crawler registers Parquet table
6. Athena views create analytics-ready schema
7. Streamlit dashboard queries Athena directly

---

## AWS Setup

### S3 Data Lake Structure

```text
s3://us-education-pipeline-2025/
├── raw/
│   └── us_education/states_all.csv
├── curated/
│   └── us_education/states_all/year=YYYY/
└── athena-results/
```

* **Raw zone** is immutable
* **Curated zone** stores optimized Parquet
* Athena results stored separately

---

### Glue Catalog & Crawlers

* Raw crawler registers CSV table
* Curated crawler registers Parquet partitions
* All schemas stored centrally in Glue Data Catalog

---

### Glue Spark ETL Job

Key transformations:

* Schema enforcement
* Null filtering
* Negative value handling
* Partitioning by `year`

**Output format:** Parquet (Snappy)

---

## Analytics Layer (Athena)

Athena is used as the **semantic layer**.

### Core Views

* `v_states_all`
* `v_state_year_metrics`
* `v_national_summary`

Benefits:

* No business logic in the dashboard
* Consistent metric definitions
* Easy extensibility

---

## IAM & Security

### IAM User for Local Development

Permissions:

* Athena query execution
* Glue catalog read
* S3 read on curated data
* S3 write on Athena results

Used with AWS CLI for local testing.

---

### IAM User for Streamlit Cloud

A **separate IAM user** was created specifically for deployment.

Permissions:

* `athena:StartQueryExecution`
* Glue catalog read-only
* S3 read curated data
* S3 write Athena results

Access via **Access Key + Secret** stored securely in Streamlit Cloud secrets.

---

## Dashboard Development

* Built using **Streamlit + Plotly**
* Choropleth map (state-level)
* Year slider & metric selector
* State vs national trend comparison

Dashboard is **stateless** and SQL-driven.

---

## Local Development & Testing

### Environment Setup

```bash
aws configure
pip install -r requirements.txt
streamlit run dashboard.py
```

### Environment Variable Handling

```python
REGION = st.secrets.get(
    "AWS_DEFAULT_REGION",
    os.getenv("AWS_DEFAULT_REGION", "us-east-1")
)

DB = st.secrets.get(
    "ATHENA_DB",
    os.getenv("ATHENA_DB", "us_education_curated")
)

RESULTS_S3 = st.secrets.get(
    "ATHENA_OUTPUT",
    os.getenv("ATHENA_OUTPUT", "s3://us-education-pipeline-2025/athena-results/")
)
```

Works seamlessly locally and in the cloud.

---

## Docker & CI/CD (Planned)

### Dockerfile

* Streamlit app containerized
* Local Docker testing completed

### GitHub Actions

* Workflow created for Docker build & ECR push
* Blocked initially due to GitHub billing
* CI design retained for future extension

### AWS App Runner (Evaluated)

* App Runner requires paid tier
* Intentionally **not used** to avoid costs

---

## Deployment on Streamlit Community Cloud

Final deployment uses **Streamlit Community Cloud**:

Steps:

1. Connect GitHub repository
2. Set `dashboard.py` as entry point
3. Configure secrets:

```toml
AWS_DEFAULT_REGION = "us-east-1"
AWS_ACCESS_KEY_ID = "<hidden>"
AWS_SECRET_ACCESS_KEY = "<hidden>"
ATHENA_DB = "us_education_curated"
ATHENA_OUTPUT = "s3://us-education-pipeline-2025/athena-results/"
```

4. App auto-deploys on every push

---

## Cost Awareness

* No long-running AWS compute
* S3 usage under free tier
* Athena pay-per-query only
* Glue jobs run once
* No App Runner / EC2 / Fargate

Project designed to be **cost-safe**.

---

## Key Learnings

* Designing scalable data lakes
* Spark ETL with AWS Glue
* IAM debugging & least-privilege access
* SQL-based analytics modeling
* Production dashboard patterns
* Cloud cost control

---

## Final Note

This project intentionally mirrors **real-world data engineering workflows**, emphasizing reliability, security, and cost efficiency.
