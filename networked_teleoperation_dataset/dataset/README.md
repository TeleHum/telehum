# Networked Teleoperation Dataset Sample

This directory is the run-level dataset sample included in this anonymized supplementary artifact. One run corresponds to one pseudonymized user under one application-side injected-delay condition.

```text
networked_teleoperation_dataset/dataset/
  subjective_ratings.csv
  delay0/
    user1/
      gnb_kpi.csv
      behavior_rosbag/
  delay300/
    user1/
      gnb_kpi.csv
      behavior_rosbag/
  delay600/
    user1/
      gnb_kpi.csv
      behavior_rosbag/
```

`subjective_ratings.csv` is a global run-level table. Each row corresponds to one user under one application-side injected-delay condition. The run-level linking keys are `user_id`, `delay_ms`, and `run_id`.

`run_id` is deterministically generated as `delay{delay_ms}_{user_id}`, for example `delay0_user1`, `delay300_user1`, and `delay600_user1`. It is derived from the condition directory and anonymous user identifier, does not encode personal identity, and is not an additional experimental variable.

Each run directory contains `gnb_kpi.csv` and a ROS 2 `behavior_rosbag/` directory with `metadata.yaml` and DB3 bag data. See the artifact-level `DATASET_DESCRIPTION.md` for field definitions and privacy notes.

The subjective-rating table contains these schema fields:

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
