# Dataset Description

The dataset is organized at run level. One run corresponds to one pseudonymized participant under one application-side injected-delay condition.

The included review sample currently follows this structure:

```text
networked_teleoperation_dataset/dataset/
  README.md
  subjective_ratings.csv
  delay0/
    user1/
      gnb_kpi.csv
      behavior_rosbag/
        metadata.yaml
        behavior_rosbag_0.db3
  delay300/
    user1/
      gnb_kpi.csv
      behavior_rosbag/
        metadata.yaml
        behavior_rosbag_0.db3
  delay600/
    user1/
      gnb_kpi.csv
      behavior_rosbag/
        metadata.yaml
        behavior_rosbag_0.db3
```

The present sample contains 3 delay conditions and 24 pseudonymized user directories per condition.

## Identifiers

- `user_id`: Pseudonymized participant/run identifier such as `user1`. It must not encode names, student IDs, device IDs, contact information, or lab-specific scheduling information.
- `delay_ms`: Application-side injected delay condition in milliseconds. The sample uses `0`, `300`, and `600`.
- `run_id`: Deterministic linking key formed as `delay{delay_ms}_{user_id}`, for example `delay300_user1`.

## Per-Run Files

- `gnb_kpi.csv`: gNB-side KPI log exported from the OAI-side recorder. Representative fields include the `Timestamp` column, frame, slot, masked UE identifiers, throughput, BLER, MCS, RSRP/RSSI/SNR, buffer, and resource-block usage. In this review artifact, `Timestamp` is expressed as relative milliseconds from the start of each run, not as the original wall-clock collection time. IMSI values in the sample are masked; RNTI/UID-like radio fields remain technical run fields and should be manually confirmed before any public release.
- `behavior_rosbag/`: ROS 2 bag directory for behavior and KPI topics.
- `behavior_rosbag/metadata.yaml`: ROS 2 bag metadata, including storage format, duration, message counts, topics, synthetic start time, and relative DB3 file paths.
- `behavior_rosbag/behavior_rosbag_0.db3`: SQLite ROS 2 bag data for the run. The SQLite message timestamp column is shifted to a synthetic time base while preserving within-run timing intervals.
- `subjective_ratings.csv`: Top-level run-level questionnaire table. Each row links to a run through `user_id`, `delay_ms`, and `run_id`.

## Subjective Ratings

`subjective_ratings.csv` contains one row per run. The schema includes:

```text
user_id
delay_ms
run_id
perceived_delay
responsiveness
control_stability
trajectory_control
task_difficulty
task_confidence
success_expectation
compensatory_action
anticipatory_compensation
attention_load
adaptation
perceived_response_change
frustration
overall_experience
```

The ratings are intended for aggregate analysis. The artifact must not include raw names, emails, exact locations, device hostnames, Wi-Fi SSIDs, SIM subscriber identifiers, or unredacted participant notes.

## Anonymization Notes

The sample dataset uses pseudonymized `user_id` values, masked IMSI values, relative KPI timestamps, and synthetic ROS bag storage timestamps. Before a larger public release, decode or regenerate ROS bag message payloads if the release policy requires removing every embedded ROS header stamp, since those stamps may be stored inside serialized message data rather than in the visible bag metadata.
