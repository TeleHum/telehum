# Anonymization Report

Overall status: NEEDS FIX

The confirmed author-specific residues found in this pass were fixed. The remaining status is `NEEDS FIX` because the artifact still contains large third-party OAI example/configuration material that should be manually scoped for the final review archive, and because serialized ROS bag payloads may contain embedded message-level stamps that require domain-specific confirmation if the release policy demands complete timestamp removal.

## Check Scope

- Top-level review documents: `README.md`, `INSTALL.md`, `RUN_EXAMPLE.md`, `DATASET_DESCRIPTION.md`, `ETHICS_AND_PRIVACY.md`, `THIRD_PARTY_ATTRIBUTION.md`, `SUBMISSION_CHECKLIST.md`, and `LICENSE`.
- `code/teleoperation_ros2_pkg/`: README, scripts, ROS 2 package metadata, launch/config files, Python files, XML assets, and package manifests.
- `code/oai_gnb_kpi_recorder/`: component README, modified gNB source/configuration files, OAI docs/config examples, third-party notices, and best-effort media/PDF metadata scan.
- `code/ros2_kpi_toolkit/`: README, docs, package metadata, Python tools, setup files, tests, and config files.
- `networked_teleoperation_dataset/dataset/`: `subjective_ratings.csv`, all per-run `gnb_kpi.csv` files, all ROS bag `metadata.yaml` files, and all DB3 bag files.
- Exclusion/generation check: `.git/`, `build/`, `install/`, lowercase `log/`, `__pycache__/`, `.pytest_cache/`, `.vscode/`, and `.idea/`.

## Fixed Issues

- Replaced ROS 2 package maintainer metadata with `Anonymous Authors` and `anonymous@example.com` in teleoperation and KPI toolkit packages while preserving package names and imports.
- Removed live hostname capture from the KPI CSV exporter. New exports use `<host-name>` instead of reading the host machine name at runtime.
- Removed dashboard host-IP resolution from `code/ros2_kpi_toolkit/tools/kpi_dashboard.py`; it now prints the configured bind address.
- Replaced a project-specific gNB private IP address with `<gNB-host-ip>` in the local OAI/gNB configuration files that appeared to be project-specific.
- Replaced an author-machine OAI custom KPI output path with `/path/to/gnb_metrics.csv`.
- Cleaned `code/oai_gnb_kpi_recorder/README.md` deployment steps to use `/path/to/anonymized_artifact/...`, `<cn-host-ip>`, `<gnb-zenoh-ip>`, and the required local-configuration note: `Manual configuration required for the local OAI/gNB/SDR deployment.`
- Sanitized 72 ROS bag DB3 files by replacing embedded author-machine home paths with equal-length `/path/to/...` placeholders. SQLite `PRAGMA integrity_check` passed after replacement.
- Shifted 72 ROS bag DB3 storage timestamp columns to a synthetic time base while preserving within-run timing intervals.
- Updated 72 ROS bag `metadata.yaml` files to use matching synthetic `nanoseconds_since_epoch` values.
- Converted 72 `gnb_kpi.csv` files from raw wall-clock millisecond timestamps to per-run relative milliseconds from run start.

## Module Results

### teleoperation_ros2_pkg

Status: PASS with routine manual hardware confirmation.

- Package names and ROS imports were left unchanged.
- Maintainer metadata now uses anonymous placeholders.
- No old author GitHub URL, author email, local home path, or machine hostname was found in the non-OAI project scan.
- Serial device examples such as `/dev/ttyACM0` are generic hardware paths, not identity data; confirm local calibration files are not added later.

### oai_gnb_kpi_recorder

Status: NEEDS MANUAL CONFIRMATION.

- The component README was cleaned while preserving deployment instructions.
- Project-specific local gNB IP and KPI output path residues were replaced with placeholders.
- OAI third-party copyright, license, citations, and upstream links were preserved.
- OAI upstream/sample docs and configs still contain many example private IPs, hostnames, testbench names, device serial examples, and third-party email/citation data. These appear to be upstream/OAI material, so they were not over-anonymized. Manually confirm whether the final anonymous artifact should include all OAI docs/config examples or only the modified subset needed for review.
- The `NEU-INTEL Labs` reference in the component README remains as a possible third-party attribution and needs author confirmation.

### ros2_kpi_toolkit

Status: PASS.

- Package maintainer metadata uses anonymous placeholders.
- Runtime hostname capture was removed from the CSV exporter.
- Dashboard host-IP lookup was removed.
- Documentation uses placeholder artifact paths.

### networked_teleoperation_dataset

Status: PASS with message-payload timestamp caveat.

- `user_id`, `delay_ms`, and `run_id` are pseudonymized run identifiers.
- No email, local path, private IP, or unmasked 15-digit IMSI was found in visible dataset CSV/YAML files after cleanup.
- `gnb_kpi.csv` IMSI values are masked as `0010100000107XX`.
- `gnb_kpi.csv` timestamps are now relative to run start.
- ROS bag metadata and DB3 storage timestamps are now synthetic.
- DB3-local author-machine paths were replaced with `/path/to/...` placeholders.
- Manual confirmation remains for embedded serialized ROS message payloads, because header stamps inside message data are not fully inspectable through text scans.

## Repository And Link Issues

- No `.git/` directory was present in the artifact tree.
- The current working directory is not a Git repository, so there is no included `.git/config`, origin remote, or commit-author metadata in the submitted tree.
- No old personal GitHub/user-name residue from the requested target patterns was found in the final targeted scan.
- Third-party upstream links in OAI and robot-model attribution were preserved. These include OAI GitLab links and external project links; they are not treated as author identity leaks.

## Dataset Privacy Issues

- Fixed: DB3 rosout/local-file path residue from author-machine home directories.
- Fixed: visible raw collection timestamps in `gnb_kpi.csv`.
- Fixed: visible ROS bag metadata/storage timestamps.
- Confirm manually: whether masked IMSI plus RNTI/UID-style radio identifiers are acceptable for the review archive and public release.
- Confirm manually: whether embedded ROS message header stamps need decoding/regeneration for the final public dataset release.
- Confirm manually: whether the sample-only release size and user count match the IRB/ethics and paper supplementary-material policy.

## Files Modified

- `ANONYMIZATION_REPORT.md`
- `DATASET_DESCRIPTION.md`
- `SUBMISSION_CHECKLIST.md`
- `code/oai_gnb_kpi_recorder/README.md`
- `code/oai_gnb_kpi_recorder/oai_custom/openair2/LAYER2/NR_MAC_gNB/main.c`
- `code/oai_gnb_kpi_recorder/oai_custom/targets/PROJECTS/GENERIC-NR-5GC/CONF/robort_arm_B210.conf`
- `code/oai_gnb_kpi_recorder/oai_custom/targets/PROJECTS/GENERIC-NR-5GC/CONF/gNB_SA_40_2x2.conf`
- `code/oai_gnb_kpi_recorder/oai_custom/targets/PROJECTS/GENERIC-LTE-EPC/CONF/testing_gnb_n310.conf`
- `code/oai_gnb_kpi_recorder/oai_custom/targets/PROJECTS/GENERIC-LTE-EPC/CONF/benetel-4g.conf`
- `code/ros2_kpi_toolkit/tools/kpi_dashboard.py`
- `code/ros2_kpi_toolkit/src/ros2_kpi_exporter/ros2_kpi_exporter/csv_exporter.py`
- `code/ros2_kpi_toolkit/src/ros2_kpi_exporter/test/test_csv_exporter.py`
- ROS 2 package metadata files under `code/teleoperation_ros2_pkg/src/*/package.xml`, `code/teleoperation_ros2_pkg/src/*/setup.py`, `code/ros2_kpi_toolkit/src/*/package.xml`, and `code/ros2_kpi_toolkit/src/*/setup.py`.
- 72 `networked_teleoperation_dataset/dataset/**/gnb_kpi.csv` files.
- 72 `networked_teleoperation_dataset/dataset/**/behavior_rosbag/metadata.yaml` files.
- 72 `networked_teleoperation_dataset/dataset/**/behavior_rosbag/behavior_rosbag_0.db3` files.

## Final Manual Confirmation Items

- Decide whether to trim third-party OAI docs/config examples that are not necessary for review, especially files with upstream testbench hostnames, private IP examples, and device serial examples.
- Confirm the `NEU-INTEL Labs` README reference is third-party attribution rather than an author identity clue.
- Confirm RNTI/UID-style radio fields and masked IMSI values are acceptable under the dataset privacy policy.
- Confirm whether serialized ROS message payloads need full decoding to remove embedded header stamps.
- Confirm final repository URL placeholder/current anonymous repository URL before submission.
- Clean paper PDF metadata and any archive-level metadata outside this repository before upload.
