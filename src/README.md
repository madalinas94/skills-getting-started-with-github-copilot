# CSV Sales Dashboard API

Upload any sales CSV — clean or messy — and get back a cleaned table,
aggregates, anomalies, and Romanian answers to questions about the data.
The model never computes a number: `data_pipeline.py` does the arithmetic,
`qa.py` only explains it.

## Getting Started

1. Install the dependencies:

   ```
   pip install -r ../requirements.txt
   ```

2. Run the application:

   ```
   python -m uvicorn app:app --reload
   ```

3. Open your browser and go to:
   - Dashboard: http://localhost:8000/
   - API docs: http://localhost:8000/docs

## API Endpoints

| Method | Endpoint            | Description                                                        |
| ------ | -------------------- | ------------------------------------------------------------------- |
| POST   | `/upload`            | Upload a CSV (multipart `file`); returns hash, cleaned columns, roles, cleaning report, aggregates, anomalies |
| GET    | `/data/{file_hash}`  | Full cleaned table + aggregates for a previously uploaded CSV        |
| POST   | `/ask`                | `{"hash": ..., "question": "..."}` → Romanian answer grounded in precomputed aggregates |

## Pipeline (`data_pipeline.py`)

1. **Parsing** — auto-detects the delimiter (`,`/`;`/tab/`|`) and skips any
   metadata lines before the real header row.
2. **Cleaning** — drops blank rows, parses Romanian-formatted numbers
   (`1.841,86` → `1841.86`), strips `TOTAL`/`SUBTOTAL` rows, removes exact
   duplicate rows, and unifies inconsistent casing (plus fuzzy name matching
   for client/vânzător-like columns).
3. **Column detection** — classifies each column as date/numeric/categorical
   by name, then by content.
4. **Aggregation** — sum/mean/min/max per numeric column, top-N breakdowns
   per categorical column (identifier-like columns are excluded).
5. **Anomaly detection** — IQR-based outlier flagging.

Sample dirty CSVs for manual testing live in `../sample_data/`.

## Tests

```
pytest
```
