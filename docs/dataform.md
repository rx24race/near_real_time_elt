# Dataform Setup

Story 6 initializes the Dataform project used for BigQuery transformations.

Dataform is external to Docker in this project. The local repository stores the project source, while execution happens through Dataform/BigQuery.

## Project Layout

```text
dataform/
  workflow_settings.yaml
  includes/
    datasets.js
  definitions/
    bronze/
      cdc_events.sqlx
    silver/
    gold/
    assertions/
      bronze_cdc_events_required_fields.sqlx
```

## Dataset Configuration

Datasets are configured in `dataform/workflow_settings.yaml`:

```yaml
vars:
  bronzeDataset: bronze
  silverDataset: silver
  goldDataset: gold
```

The Bronze table is declared in Dataform as an external input:

```text
bronze.cdc_events
```

Stories 7 through 9 will add the actual Silver and Gold transformations.

## Local Compile

From the repository root:

```bash
npm run dataform:compile
```

The root `package.json` uses `npx` to run the Dataform CLI against the `dataform/` folder. This keeps `dataform/` as pure Dataform source, which avoids local `node_modules` files being interpreted as project files.

Compilation validates the Dataform project structure and SQLX syntax. It does not run transformations in BigQuery.

## Cloud Dataform Setup

1. Create a Dataform repository in the same GCP project used by BigQuery.
2. Connect the repository to this Git project.
3. Set the repository root or workspace path to:

   ```text
   dataform
   ```

4. Confirm `workflow_settings.yaml` uses the correct project and location:

   ```yaml
   defaultProject: near-real-time-elt
   defaultLocation: US
   ```

5. Grant Dataform's service account permissions to read Bronze and create Silver/Gold objects.

Recommended roles for this demo project:

- `BigQuery Data Editor`
- `BigQuery Job User`

## Current Actions

Story 6 includes:

- A declaration for `bronze.cdc_events`
- An assertion that checks required Bronze fields are not null
- Empty folders for Silver and Gold models
- Shared dataset constants in `includes/datasets.js`

The assertion is intentionally small. It gives the project a compile-friendly quality check without implementing the Story 7 Silver models early.
