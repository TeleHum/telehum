# Anonymous Supplementary Artifact

This repository is a supplementary artifact prepared for double-blind review for an UbiComp/IMWUT submission. Author names, affiliations, original repository remotes, Git history, local machine paths, and direct participant identifiers are intentionally excluded.

The artifact is organized as a single review package:

```text
ANONYMIZED_ARTIFACT/
  README.md
  INSTALL.md
  RUN_EXAMPLE.md
  DATASET_DESCRIPTION.md
  ETHICS_AND_PRIVACY.md
  THIRD_PARTY_ATTRIBUTION.md
  ANONYMIZATION_REPORT.md
  SUBMISSION_CHECKLIST.md
  LICENSE
  code/
    teleoperation_ros2_pkg/
    oai_gnb_kpi_recorder/
    ros2_kpi_toolkit/
  networked_teleoperation_dataset/
    dataset/
```

## Modules

- `code/teleoperation_ros2_pkg/`: ROS 2 teleoperation and simulation interface.
- `code/oai_gnb_kpi_recorder/`: gNB-side KPI recording utilities.
- `code/ros2_kpi_toolkit/`: parsing, analysis, and utility scripts.
- `networked_teleoperation_dataset/dataset/`: run-level dataset structure and sample data.

## Reviewer Entry Points

- Start with `INSTALL.md` for software and hardware dependencies.
- Use `RUN_EXAMPLE.md` for a software-only review path and a full-system run path.
- Use `DATASET_DESCRIPTION.md` for dataset layout, identifiers, and per-run files.
- Use `ANONYMIZATION_REPORT.md` and `SUBMISSION_CHECKLIST.md` before packaging or mirroring the artifact.

The complete hardware reproduction path requires ROS 2 Humble, SO101-compatible hardware, 5G UE/gNB equipment, OpenAirInterface, and local radio/network configuration. The software-only path is intended to let reviewers inspect the code, build ROS 2 workspaces, and examine the dataset structure without access to the physical system.
