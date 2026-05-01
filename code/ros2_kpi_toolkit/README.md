# ROS 2 通信质量 KPI 工具链 MVP

这是一个面向 ROS 2 Humble 的第一版 KPI 工具链，用于测量“UE 端 publisher -> 基站端 subscriber”这一跳的 ROS 2 层通信质量。

现在它同时支持两种接入方式：

- `probe` 模式：继续使用工具链自带的 `KpiProbe` 探测流量
- `generic_topic` 模式：直接订阅任意业务 topic，并尽量从业务消息里自动提取时间戳、序号和字节数

当前版本只覆盖 ROS 2 层统计，不采集 5G 无线链路 KPI，不依赖 Grafana / Prometheus / GUI，也不引入 Zenoh 或 DDS 对比逻辑。

## 快速使用模板

如果你只是想“先跑起来再说”，最推荐直接套下面这个模板。通常你只需要改 4 个值：

- `TOPIC_NAME`
- `TOPIC_TYPE`
- `TIMESTAMP_FIELD`
- `SEQUENCE_FIELD`

### 模板 1：任意业务 Topic 通用模板

适合大多数现有业务 topic。

```bash
source /opt/ros/humble/setup.bash
cd /path/to/anonymized_artifact/code/ros2_kpi_toolkit
source install/setup.bash

TOPIC_NAME=/your_topic
TOPIC_TYPE=your_pkg/msg/YourMsg
TIMESTAMP_FIELD=header.stamp
SEQUENCE_FIELD=
SAMPLE_TOPIC=${TOPIC_NAME}_kpi_samples

ros2 launch ros2_kpi_bringup kpi_pipeline.launch.py \
  measurement_mode:=generic_topic \
  enable_publisher:=false \
  enable_subscriber:=true \
  enable_collector:=true \
  enable_exporter:=true \
  topic_name:=${TOPIC_NAME} \
  topic_type:=${TOPIC_TYPE} \
  timestamp_field:=${TIMESTAMP_FIELD} \
  sequence_field:=${SEQUENCE_FIELD} \
  qos_profile_mode:=match_publisher \
  sample_topic_name:=${SAMPLE_TOPIC} \
  metrics_topic_name:=/kpi_window_stats \
  dashboard_metrics_topic_name:=/kpi_metrics \
  window_size_sec:=5.0 \
  csv_output_path:=./output/kpi_metrics.csv
```

怎么填：

- 如果消息里有发送时间戳，通常填 `TIMESTAMP_FIELD=header.stamp`
- 如果消息里没有时间戳，就把它留空：`TIMESTAMP_FIELD=`
- 如果消息里有递增序号，例如 `seq` 或 `meta.sequence_id`，就填进去
- 如果消息里没有递增序号，就把它留空：`SEQUENCE_FIELD=`

### 模板 2：完整 KPI 推荐模板

如果你希望尽量拿到完整 KPI，推荐被测消息至少具备下面两个观测字段：

```text
std_msgs/Header header
uint64 seq
<YourBusinessMsg> data
```

也可以不包 `data`，只要你的业务消息本身已经包含这些字段即可。这个模板的好处是：

- `header.stamp` 用来计算单向时延及其窗口统计
- `seq` 用来计算丢包、丢包率和乱序
- 整条消息的序列化大小天然可以用来估算吞吐

对应推荐启动模板：

```bash
source /opt/ros/humble/setup.bash
cd /path/to/anonymized_artifact/code/ros2_kpi_toolkit
source install/setup.bash

TOPIC_NAME=/your_full_kpi_topic
TOPIC_TYPE=your_pkg/msg/YourWrappedMsg
SAMPLE_TOPIC=${TOPIC_NAME}_kpi_samples

ros2 launch ros2_kpi_bringup kpi_pipeline.launch.py \
  measurement_mode:=generic_topic \
  enable_publisher:=false \
  enable_subscriber:=true \
  enable_collector:=true \
  enable_exporter:=true \
  topic_name:=${TOPIC_NAME} \
  topic_type:=${TOPIC_TYPE} \
  timestamp_field:=header.stamp \
  sequence_field:=seq \
  qos_profile_mode:=match_publisher \
  sample_topic_name:=${SAMPLE_TOPIC} \
  metrics_topic_name:=/kpi_window_stats \
  dashboard_metrics_topic_name:=/kpi_metrics \
  window_size_sec:=5.0 \
  csv_output_path:=./output/kpi_metrics.csv
```

### 模板 3：`/joint_states` 直接套用

如果你现在就是要测 `/joint_states`，那几乎不用想，直接用这组值：

```bash
TOPIC_NAME=/joint_states
TOPIC_TYPE=sensor_msgs/msg/JointState
TIMESTAMP_FIELD=header.stamp
SEQUENCE_FIELD=
```

这意味着：

- 能拿到 `latency + jitter + rate + throughput`
- 默认拿不到 `loss / out_of_order`

## 项目简介

本工程提供一个最小可运行 MVP：

- `ros2_kpi_interfaces`：定义探测消息、单条样本消息、窗口统计消息
- `ros2_kpi_probe`：提供探测流量 publisher / subscriber，以及任意 topic 监测节点
- `ros2_kpi_collector`：在滑动窗口内聚合 KPI
- `ros2_kpi_exporter`：将窗口统计导出到 CSV
- `ros2_kpi_bringup`：统一 launch 入口，支持实验参数和 QoS 切换

工作空间根目录就是一个标准 colcon workspace，源代码位于 `src/`。

## Python 环境与 `pyproject.toml`

仓库根目录现在提供了一个轻量的 `pyproject.toml`，用于管理开发环境中的 Python 工具依赖，例如 `pytest`。

需要说明的是：

- `pyproject.toml` 只用于管理开发和测试工具，不替代 ROS 2 的 `colcon`、`ament_python`、`ament_cmake`
- `rclpy`、ROS 2 message 生成链、`launch_ros` 等运行时能力仍然来自 ROS 2 Humble 环境
- 推荐做法是使用虚拟环境管理 Python 工具，再叠加 `/opt/ros/humble/setup.bash`

最小使用方式：

```bash
cd /path/to/anonymized_artifact/code/ros2_kpi_toolkit
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
source /opt/ros/humble/setup.bash
```

如果只是构建和运行 ROS 2 节点，没有强制要求必须用 `pip` 安装整个 workspace；但对于统一管理测试工具、隔离本机 Python 环境来说，这样会更整洁。

## 架构说明

数据流如下：

1. `probe` 模式下，UE 侧 `probe_publisher` 周期性发布 `KpiProbe`
2. `probe` 模式下，基站侧 `probe_subscriber` 订阅 `KpiProbe`，记录接收时刻并计算单条样本
3. `generic_topic` 模式下，`topic_monitor` 直接订阅任意业务 topic，并尝试从业务消息中提取发送时间戳、序号和序列化字节数
4. `probe_subscriber` 或 `topic_monitor` 都会把单条观测统一发布到内部 topic `KpiSample`
5. `metrics_node` 在滑动窗口内聚合统计，同时发布 legacy `KpiWindowStats` 和实时 `KpiWindowMetrics`
6. `csv_exporter` 订阅 legacy 窗口统计并写入可滚动 CSV

逻辑分层如下：

- 探测流量生成：`ros2_kpi_probe/probe_publisher.py`
- 单样本观测：`ros2_kpi_probe/probe_subscriber.py`
- 任意 topic 观测：`ros2_kpi_probe/topic_monitor.py`
- 窗口聚合：`ros2_kpi_collector/metrics_node.py`
- 结果导出：`ros2_kpi_exporter/csv_exporter.py`

## Clock synchronization and timing assumptions

当前工具测量的是 ROS 2 层的单向时延，也就是 UE 端发送时间戳到基站端接收时间戳之间的差值。

时间假设如下：

- 所有节点默认 `use_sim_time=false`
- 发送端和接收端都必须使用系统时间
- 如果两台机器时钟未同步，单向 `latency_ms` 会混入 clock offset
- 第一版推荐使用 `chrony` 做系统时间同步
- 在运行 demo 前，建议先自行检查 `chrony` 状态
- 如果无法保证时钟同步，建议把结果标注为“近似单向时延”

### Minimal chrony checklist

建议至少检查以下项目，不展开运维细节：

- 两台机器都确认 `chrony` 处于运行状态
- 运行 `chronyc tracking`，确认本机有有效同步状态
- 运行 `chronyc sources -v`，确认存在可用时间源且状态正常
- 运行 `date -Ins` 或等效命令，确认两台机器当前时间不存在明显漂移
- 若实验对毫秒级甚至更细粒度单向时延敏感，先确认你的同步精度满足实验要求

## KPI 定义

当前版本实现以下 KPI：

- `latency_ms = recv_time - msg.header.stamp`
- `jitter_ms = latency_ms` 在滑动窗口内的标准差
- `recv_rate_hz = 窗口内接收消息数 / window_size_sec`
- `throughput_Bps = 窗口内接收字节数 / window_size_sec`
- `sequence loss` 通过 `seq` 跳号统计
- `out_of_order` 当 `current_seq <= last_seq` 时记一次

同时输出：

- `avg_latency_ms`
- `p95_latency_ms`
- `p99_latency_ms`
- `std_latency_ms`
- `jitter_ms`
- `recv_rate_hz`
- `throughput_Bps`
- `lost_count`
- `loss_rate`
- `out_of_order_count`

实现细节说明：

- `p95 / p99` 采用 nearest-rank 百分位实现
- `loss_rate = lost_count / (received_count + lost_count)`
- `jitter_ms` 第一版直接定义为 `latency_ms` 的标准差
- `payload_size` 参与吞吐统计，单位为字节

`generic_topic` 模式下还需要注意：

- `throughput_Bps` 使用消息序列化后的字节数估算，而不是业务侧自定义 payload 字段
- 如果业务消息能提供发送时间戳，例如 `header.stamp`，则可以计算单向 `latency_ms`
- 如果业务消息还能提供单调递增的序号字段，例如 `seq` / `sequence_id`，则可以计算 `loss` 和 `out_of_order`
- 如果没有可用时间戳，窗口中的 latency 相关字段会输出 `NaN`
- 如果没有可用序号字段，`lost_count` 和 `out_of_order_count` 会保持为 `0`

## 实时 KPI Topic

collector 现在会同时发布两个窗口统计 topic：

- legacy topic：`/kpi_window_stats`，消息类型为 `ros2_kpi_interfaces/msg/KpiWindowStats`
- dashboard topic：`/kpi_metrics`，消息类型为 `ros2_kpi_interfaces/msg/KpiWindowMetrics`

其中 `/kpi_metrics` 更适合被 PlotJuggler、Foxglove 或自定义 dashboard 直接订阅。为了遵循 ROS 2 消息字段命名规则，消息中的吞吐字段实现为 `throughput_bps`，语义等价于需求中的 `throughput_Bps`。

## 目录结构

```text
ros2_kpi_toolkit/
├── README.md
├── .gitignore
└── src/
    ├── ros2_kpi_interfaces/
    ├── ros2_kpi_probe/
    ├── ros2_kpi_collector/
    ├── ros2_kpi_exporter/
    └── ros2_kpi_bringup/
```

## `src/` 各软件包作用

### `ros2_kpi_interfaces`

这个包负责定义工具链内部使用的消息接口，是整个工程的数据契约层。

- `KpiProbe.msg`：UE 侧发出的探测消息
- `KpiSample.msg`：subscriber 计算出的单条采样结果
- `KpiWindowStats.msg`：兼容现有 exporter 的窗口统计消息
- `KpiWindowMetrics.msg`：面向 PlotJuggler / Foxglove / dashboard 的结构化窗口 KPI

### `ros2_kpi_probe`

这个包负责产生探测流量，并在接收端对探测流量或任意业务 topic 做逐条观测。

- `probe_publisher.py`：按配置频率和 payload 大小发布 `KpiProbe`
- `probe_subscriber.py`：订阅 `KpiProbe`，计算 `latency / inter_arrival / seq_gap / out_of_order`，并输出 `KpiSample`
- `topic_monitor.py`：订阅任意 ROS 2 message type，自动或按配置提取 `timestamp / sequence / serialized_size`，并输出 `KpiSample`

### `ros2_kpi_collector`

这个包负责对 `KpiSample` 做滑动窗口聚合，是 KPI 统计核心。

- `metrics_node.py`：计算 `avg / p95 / p99 / std / jitter / recv_rate / throughput / loss / out_of_order`
- 同时输出 legacy `KpiWindowStats` 和实时 `KpiWindowMetrics`

### `ros2_kpi_exporter`

这个包负责把窗口聚合结果持久化到文件。

- `csv_exporter.py`：订阅窗口统计，按 `run_id` 归档输出 CSV
- 支持 CSV rollover
- 为每次运行生成 `metadata.json`

### `ros2_kpi_bringup`

这个包负责统一启动整条工具链。

- `kpi_pipeline.launch.py`：集中管理 publisher / subscriber / collector / exporter 的启动参数
- 统一暴露 `measurement_mode / topic_type / timestamp_field / sequence_field / QoS / window / CSV exporter` 参数，便于实验切换

## 如何 Build

前提：

- Ubuntu 22.04
- ROS 2 Humble
- 已安装 `colcon`

构建命令：

```bash
source /opt/ros/humble/setup.bash
cd /path/to/anonymized_artifact/code/ros2_kpi_toolkit
colcon build --symlink-install
source install/setup.bash
```

可选检查：

```bash
colcon list
```

最小自检：

```bash
colcon test --packages-select ros2_kpi_probe ros2_kpi_collector ros2_kpi_exporter
colcon test-result --verbose
```

## 如何运行 Probe 模式 Demo

### 1. 机器 A：仅启动 UE 侧 publisher

```bash
source /opt/ros/humble/setup.bash
cd /path/to/anonymized_artifact/code/ros2_kpi_toolkit
source install/setup.bash
ros2 launch ros2_kpi_bringup kpi_pipeline.launch.py \
  enable_publisher:=true \
  enable_subscriber:=false \
  enable_collector:=false \
  enable_exporter:=false \
  topic_name:=/kpi_probe \
  publish_rate_hz:=20.0 \
  payload_size:=1024 \
  qos_reliability:=reliable \
  qos_history_depth:=10
```

### 2. 机器 B：启动 subscriber + collector + exporter

```bash
source /opt/ros/humble/setup.bash
cd /path/to/anonymized_artifact/code/ros2_kpi_toolkit
source install/setup.bash
ros2 launch ros2_kpi_bringup kpi_pipeline.launch.py \
  enable_publisher:=false \
  enable_subscriber:=true \
  enable_collector:=true \
  enable_exporter:=true \
  topic_name:=/kpi_probe \
  sample_topic_name:=/kpi_probe_samples \
  metrics_topic_name:=/kpi_window_stats \
  dashboard_metrics_topic_name:=/kpi_metrics \
  window_size_sec:=5.0 \
  csv_output_path:=./output/kpi_metrics.csv \
  max_file_size_mb:=10.0 \
  max_files_per_run:=10 \
  qos_reliability:=reliable \
  qos_history_depth:=10
```

## 如何监测任意业务 Topic

如果你要测的不是工具链自己发出的 `KpiProbe`，而是已经存在的业务 topic，那么直接切到 `generic_topic` 模式即可。

最小用法如下：

```bash
source /opt/ros/humble/setup.bash
cd /path/to/anonymized_artifact/code/ros2_kpi_toolkit
source install/setup.bash
ros2 launch ros2_kpi_bringup kpi_pipeline.launch.py \
  measurement_mode:=generic_topic \
  enable_publisher:=false \
  enable_subscriber:=true \
  enable_collector:=true \
  enable_exporter:=true \
  topic_name:=/your_business_topic \
  topic_type:=your_pkg/msg/YourMsg \
  timestamp_field:=header.stamp \
  sequence_field:=seq \
  qos_profile_mode:=match_publisher \
  sample_topic_name:=/your_business_topic_kpi_samples \
  metrics_topic_name:=/kpi_window_stats \
  dashboard_metrics_topic_name:=/kpi_metrics \
  window_size_sec:=5.0 \
  csv_output_path:=./output/kpi_metrics.csv
```

说明：

- `topic_type` 可以显式填写，例如 `sensor_msgs/msg/Imu`，也可以留空让工具链在发现 publisher 后自动识别
- `qos_profile_mode:=match_publisher` 会复用已发现 publisher 的 QoS，通常最适合直接观测现有业务 topic
- `timestamp_field` 默认值是 `auto`，会优先尝试 `header.stamp`、`stamp`、`source_stamp`
- `sequence_field` 默认值是 `auto`，会优先尝试 `seq`、`sequence`、`sequence_id`
- 如果业务消息没有时间戳，可以把 `timestamp_field` 置空；此时工具链仍然可以统计接收速率和吞吐，但 latency 相关窗口值会是 `NaN`
- 如果业务消息没有序号，可以把 `sequence_field` 置空；此时 loss / out-of-order 统计会保持为 `0`

例如直接观测一个只有 `std_msgs/msg/String` 的 topic：

```bash
ros2 launch ros2_kpi_bringup kpi_pipeline.launch.py \
  measurement_mode:=generic_topic \
  enable_publisher:=false \
  enable_subscriber:=true \
  enable_collector:=true \
  enable_exporter:=true \
  topic_name:=/chatter \
  topic_type:=std_msgs/msg/String \
  timestamp_field:='' \
  sequence_field:='' \
  qos_profile_mode:=match_publisher
```

### `/joint_states` 示例

`/joint_states` 在 ROS 2 里通常使用官方消息类型 `sensor_msgs/msg/JointState`。它的典型结构大致如下：

```text
std_msgs/Header header
string[] name
float64[] position
float64[] velocity
float64[] effort
```

对这个消息类型，工具链默认可以这样理解：

- 可以直接订阅，`topic_type` 填 `sensor_msgs/msg/JointState`
- 如果发布端正确填写了 `header.stamp`，就可以计算单向 `latency / jitter / p95 / p99`
- 因为 `JointState` 本身没有标准的单调递增序号字段，所以默认不能可靠计算 `loss / out_of_order`
- `recv_rate_hz` 和 `throughput_Bps` 可以正常统计

推荐的启动方式还是 `ros2 launch`，因为它会把 monitor、collector、exporter 一次性拉起来：

```bash
source /opt/ros/humble/setup.bash
cd /path/to/anonymized_artifact/code/ros2_kpi_toolkit
source install/setup.bash
ros2 launch ros2_kpi_bringup kpi_pipeline.launch.py \
  measurement_mode:=generic_topic \
  enable_publisher:=false \
  enable_subscriber:=true \
  enable_collector:=true \
  enable_exporter:=true \
  topic_name:=/joint_states \
  topic_type:=sensor_msgs/msg/JointState \
  timestamp_field:=header.stamp \
  sequence_field:='' \
  qos_profile_mode:=match_publisher \
  sample_topic_name:=/joint_states_kpi_samples \
  metrics_topic_name:=/kpi_window_stats \
  dashboard_metrics_topic_name:=/kpi_metrics \
  window_size_sec:=5.0 \
  csv_output_path:=./output/kpi_metrics.csv
```

如果你想拆开单独用 `ros2 run` 启动，也可以分三步：

1. 启动通用 topic monitor

```bash
source /opt/ros/humble/setup.bash
cd /path/to/anonymized_artifact/code/ros2_kpi_toolkit
source install/setup.bash
ros2 run ros2_kpi_probe topic_monitor --ros-args \
  -p topic_name:=/joint_states \
  -p sample_topic_name:=/joint_states_kpi_samples \
  -p topic_type:=sensor_msgs/msg/JointState \
  -p timestamp_field:=header.stamp \
  -p sequence_field:='' \
  -p qos_profile_mode:=match_publisher
```

2. 启动窗口统计 collector

```bash
source /opt/ros/humble/setup.bash
cd /path/to/anonymized_artifact/code/ros2_kpi_toolkit
source install/setup.bash
ros2 run ros2_kpi_collector metrics_node --ros-args \
  -p topic_name:=/joint_states \
  -p sample_topic_name:=/joint_states_kpi_samples \
  -p metrics_topic_name:=/kpi_window_stats \
  -p dashboard_metrics_topic_name:=/kpi_metrics \
  -p window_size_sec:=5.0 \
  -p metrics_publish_period_sec:=1.0
```

3. 启动 CSV exporter

```bash
source /opt/ros/humble/setup.bash
cd /path/to/anonymized_artifact/code/ros2_kpi_toolkit
source install/setup.bash
ros2 run ros2_kpi_exporter csv_exporter --ros-args \
  -p metrics_topic_name:=/kpi_window_stats \
  -p csv_output_path:=./output/kpi_metrics.csv \
  -p topic_name:=/joint_states \
  -p topic_type:=sensor_msgs/msg/JointState \
  -p measurement_mode:=generic_topic \
  -p timestamp_field:=header.stamp \
  -p sequence_field:=''
```

如果你的 `/joint_states` 发布端没有认真填写 `header.stamp`，或者它一直是零时间戳，那么：

- `avg_latency_ms / p95_latency_ms / p99_latency_ms / std_latency_ms / jitter_ms` 会变成 `NaN`
- `recv_rate_hz` 和 `throughput_Bps` 仍然可用
- `lost_count / loss_rate / out_of_order_count` 因为没有序号字段，默认会保持为 `0`

可以先用下面这条命令确认它到底有没有在更新时间戳：

```bash
ros2 topic echo /joint_states --once
```

### `/master/joint_states` 预设启动入口

如果你要测的是固定业务 topic `/master/joint_states`，并且消息结构里有
`header.stamp` 和 `seq`，仓库里额外提供了一个专用 launch 预设，避免每次重复
填写长参数列表。典型消息类型是 `so101_interfaces/msg/SequencedJointState`。
当前仓库也已经内置了这个消息定义；如果你的业务工作空间同样提供 `so101_interfaces`，
请按实际版本需求安排 `source` 顺序。

最简启动方式：

```bash
source /opt/ros/humble/setup.bash
source /path/to/your_business_ws/install/setup.bash
cd /path/to/anonymized_artifact/code/ros2_kpi_toolkit
source install/setup.bash
ros2 launch ros2_kpi_bringup master_joint_states_kpi.launch.py
```

这个预设等价于提前固定了以下配置：

- `measurement_mode:=generic_topic`
- `topic_name:=/master/joint_states`
- `topic_type:=` 留空时自动发现
- `timestamp_field:=header.stamp`
- `sequence_field:=seq`
- `sample_topic_name:=/master/joint_states_kpi_samples`
- `qos_profile_mode:=match_publisher`

如果你只想覆盖少数参数，也可以直接在后面追加，例如：

```bash
ros2 launch ros2_kpi_bringup master_joint_states_kpi.launch.py \
  window_size_sec:=10.0 \
  csv_output_path:=./output/master_joint_states_metrics.csv
```

如果你希望显式固定消息类型，也可以直接覆盖：

```bash
ros2 launch ros2_kpi_bringup master_joint_states_kpi.launch.py \
  topic_type:=so101_interfaces/msg/SequencedJointState
```

更完整的交付文档见：

- [docs/measure_master_joint_states.md](docs/measure_master_joint_states.md)

### 3. 实验前需要确认

- 两台机器使用相同的 `ROS_DOMAIN_ID`
- DDS 发现和 topic 通信在网络层可达
- 如果需要可信的跨机器 latency，系统时间必须同步，建议使用 NTP 或 PTP

### 4. 可选：使用 ros2 bag 录制实验数据

建议在机器 B 录制接收端观测结果，最常见的是同时录制原始被测 topic、单样本 topic 和窗口统计 topic：

```bash
mkdir -p bag
ros2 bag record -o bag/kpi_demo \
  /your_measured_topic \
  /your_measured_topic_kpi_samples \
  /kpi_window_stats \
  /kpi_metrics
```

如果你测的是 `/joint_states`，那就把上面两项换成：

```bash
/joint_states
/joint_states_kpi_samples
```

如果你只关心最终 KPI，也可以只录：

```bash
ros2 bag record -o bag/kpi_metrics_only /kpi_metrics
```

## QoS 实验切换

当前支持以下实验变量：

- `qos_reliability:=reliable | best_effort`
- `qos_history_depth:=<正整数>`

例如改成 best effort：

```bash
ros2 launch ros2_kpi_bringup kpi_pipeline.launch.py \
  enable_publisher:=true \
  enable_subscriber:=true \
  enable_collector:=true \
  enable_exporter:=true \
  qos_reliability:=best_effort \
  qos_history_depth:=20
```

说明：

- `probe_publisher` 和 `probe_subscriber` 使用同一组 QoS 参数
- `collector` 额外发布 dashboard 友好的 `/kpi_metrics`
- `collector` 和 `exporter` 的内部统计 topic 使用本地默认 reliable 配置

## 如何通过实时 Topic 观察 KPI

最直接的方式是先看 collector 的实时结构化输出：

```bash
ros2 topic echo /kpi_metrics
```

如果你使用 PlotJuggler 或 Foxglove，可以订阅 `/kpi_metrics`，重点观察这些字段：

- `avg_latency_ms`
- `p95_latency_ms`
- `p99_latency_ms`
- `jitter_ms`
- `recv_rate_hz`
- `throughput_bps`
- `loss_rate`
- `out_of_order_count`

快速确认 collector 发布节奏也可以执行：

```bash
ros2 topic hz /kpi_metrics
```

## 如何查看 CSV

当前 CSV exporter 不再把所有窗口统计持续追加到同一个文件，而是：

- 每次运行生成唯一 `run_id`
- 所有 CSV part 文件和 `metadata.json` 都归档到独立 run 目录
- 按 `max_file_size_mb` 进行滚动
- 同一个 run 目录内最多保留 `max_files_per_run` 个 part 文件

如果 `csv_output_path` 保持默认值 `./output/kpi_metrics.csv`，实际目录结构会类似：

```text
output/
└── kpi_metrics/
    └── run_<run_id>/
        ├── metadata.json
        ├── metrics_run_<run_id>_part_0001.csv
        ├── metrics_run_<run_id>_part_0002.csv
        └── ...
```

查看最近生成的文件可以这样做：

```bash
find output -name 'metrics_run_*_part_*.csv' | sort
```

跟踪最新 part 文件可以这样做：

```bash
tail -f "$(find output -name 'metrics_run_*_part_*.csv' | sort | tail -n 1)"
```

CSV 列包含：

- `timestamp_ns`
- `timestamp_iso_utc`
- `topic_name`
- `window_size_sec`
- `sample_count`
- `received_bytes`
- `avg_latency_ms`
- `p95_latency_ms`
- `p99_latency_ms`
- `std_latency_ms`
- `jitter_ms`
- `recv_rate_hz`
- `throughput_Bps`
- `lost_count`
- `loss_rate`
- `out_of_order_count`

示例输出如下，数值来自本机 loopback demo，仅作为格式参考：

```csv
timestamp_ns,timestamp_iso_utc,topic_name,window_size_sec,sample_count,received_bytes,avg_latency_ms,p95_latency_ms,p99_latency_ms,std_latency_ms,jitter_ms,recv_rate_hz,throughput_Bps,lost_count,loss_rate,out_of_order_count
1776667620665645810,2026-04-20T06:47:00.665646+00:00,/demo_kpi_probe,2.0,5,640,0.9700276000000001,1.244698,1.244698,0.21150786589685028,0.21150786589685028,2.5,320.0,0,0.0,0
1776667621665518359,2026-04-20T06:47:01.665518+00:00,/demo_kpi_probe,2.0,10,1280,0.8240489999999999,1.244698,1.244698,0.23849252780538013,0.23849252780538013,5.0,640.0,0,0.0,0
```

每个 run 还会附带一个 `metadata.json`，至少记录：

- `run_id`
- `measurement_mode`
- `topic_name`
- `topic_type`
- `publish_rate_hz`
- `payload_size`
- `qos_reliability`
- `qos_history_depth`
- `window_size_sec`
- `timestamp_field`
- `sequence_field`
- `hostname`
- `start_time`
- `use_sim_time`

## 被测话题需要带什么字段

这个工具链现在支持“任意 ROS 2 消息类型”，但不同消息里带不带关键字段，会直接决定你最后能拿到哪些 KPI。

### 完整 KPI 推荐消息模板

如果你从一开始就想把完整 KPI 设计进去，最推荐的消息骨架是：

```text
std_msgs/Header header
uint64 seq
<YourBusinessMsg> data
```

或者如果你不想额外包一层，也至少保证业务消息自身带：

```text
std_msgs/Header header
uint64 seq
...
```

推荐原因：

- `header.stamp` 可以稳定支持单向时延统计
- `seq` 可以稳定支持丢包和乱序统计
- 消息整体可以直接序列化估算字节数，不需要额外再提供 `payload_size`

字段与 KPI 的对应关系如下：

| 消息中的字段 | 作用 | 可支持的 KPI |
| --- | --- | --- |
| 任意可序列化 ROS 2 消息 | 基础接收观测 | `sample_count`、`received_bytes`、`recv_rate_hz`、`throughput_Bps` |
| `header.stamp` 或其他有效发送时间戳 | 发送时刻观测 | `latency_ms`、`avg_latency_ms`、`p95_latency_ms`、`p99_latency_ms`、`std_latency_ms`、`jitter_ms` |
| `seq` 或其他单调递增序号 | 序列连续性观测 | `lost_count`、`loss_rate`、`out_of_order_count` |

如果缺字段，会发生什么：

- 缺时间戳：latency 相关统计变成 `NaN`
- 缺序号：`lost_count / loss_rate / out_of_order_count` 保持为 `0`
- 两者都缺：仍然可以得到 `recv_rate_hz` 和 `throughput_Bps`

### 1. 只要是合法 ROS 2 message type

例如：

- `std_msgs/msg/String`
- `sensor_msgs/msg/JointState`
- `geometry_msgs/msg/Twist`
- 你自己的 `your_pkg/msg/YourMsg`

只要 monitor 能成功订阅并序列化消息，通常就能得到：

- `recv_rate_hz`
- `throughput_Bps`
- `sample_count`
- `received_bytes`

如果消息序列化失败，`payload_size` 会退化成 `0`，此时吞吐统计会偏小。

### 2. 如果消息里有“发送时间戳”

推荐字段形式：

- `header.stamp`
- `stamp`
- `source_stamp`
- 或者你自己通过 `timestamp_field:=your.path` 指定的字段

并且这个时间戳需要满足：

- 是真正发送前写入的时间
- 不是默认零值
- 发送端和接收端时钟在同一时间基准下可比较

这样就能额外得到：

- `latency_ms`
- `avg_latency_ms`
- `p95_latency_ms`
- `p99_latency_ms`
- `std_latency_ms`
- `jitter_ms`

如果没有这个字段，或者字段存在但值无效：

- 单条样本里的 `latency_ms` 会是 `NaN`
- 窗口里的 latency 相关统计会是 `NaN`
- 但接收速率和吞吐仍然可用

### 3. 如果消息里有“单调递增序号”

默认会自动尝试这些字段：

- `seq`
- `sequence`
- `sequence_id`

也可以手动指定，例如：

```bash
sequence_field:=meta.sequence_id
```

这个序号最好满足：

- 每发一条消息递增一次
- 同一个 topic 内单调递增
- 不要复用、回绕或随机变化

这样就能额外得到：

- `lost_count`
- `loss_rate`
- `out_of_order_count`

如果没有序号字段：

- 工具链不会报错
- `lost_count` 会保持为 `0`
- `loss_rate` 会保持为 `0`
- `out_of_order_count` 会保持为 `0`

### 4. 一张快速对照表

| 消息条件 | 能得到的 KPI |
| --- | --- |
| 任意可订阅 ROS 2 消息 | `recv_rate_hz`、`throughput_Bps`、`sample_count`、`received_bytes` |
| 再加有效时间戳 | 上面那些 + `latency_ms`、`avg/p95/p99/std/jitter` |
| 再加有效递增序号 | 上面那些 + `lost_count`、`loss_rate`、`out_of_order_count` |

### 4.1 一份可直接复用的完整 KPI 消息示例

```text
# your_pkg/msg/MeasuredBusinessMsg.msg
std_msgs/Header header
uint64 seq
string source_id
<YourOriginalBusinessMsg> data
```

推荐填写规则：

- `header.stamp` 在真正调用 `publish()` 之前写入
- `seq` 在发送端单调递增
- `source_id` 可选，用于区分不同发送源或设备
- `data` 保持原始业务负载，不影响现有业务语义

如果你按这个模板设计，通常就能直接测出完整 KPI：

- `recv_rate_hz`
- `throughput_Bps`
- `sample_count`
- `received_bytes`
- `latency_ms`
- `avg_latency_ms`
- `p95_latency_ms`
- `p99_latency_ms`
- `std_latency_ms`
- `jitter_ms`
- `lost_count`
- `loss_rate`
- `out_of_order_count`

### 5. 几个典型例子

`sensor_msgs/msg/JointState`

- 通常有 `header.stamp`
- 通常没有标准序号
- 所以一般能算 latency、rate、throughput
- 一般不能直接算 loss / out_of_order

`std_msgs/msg/String`

- 没有标准时间戳
- 没有标准序号
- 通常只能算 rate、throughput

自定义业务消息：

```text
std_msgs/Header header
uint64 seq
...
```

- 这是最适合完整 KPI 观测的一类消息
- 可以同时算 latency、rate、throughput、loss、out_of_order

## 适配现有业务消息

现在优先推荐先尝试 `generic_topic` 模式，只有在业务消息本身缺少关键观测字段时，再考虑增加轻量适配层。

### 场景 0：业务消息已经有时间戳和序号

这种情况下通常不需要 adapter，直接用 `generic_topic` 模式即可：

- `timestamp_field` 指向发送时间戳，例如 `header.stamp`
- `sequence_field` 指向单调递增序号，例如 `seq` / `meta.sequence_id`

### 场景 A：业务消息已经带 `std_msgs/Header`

如果业务消息本身已经有 `header.stamp`，但没有可用序号字段，那么有两种做法：

- 直接使用 `generic_topic` 模式，只统计 latency / recv_rate / throughput
- 如果你还需要 `loss / out_of_order`，就在业务发送侧补一个单调递增序号，或者做一层 adapter 再映射成 `KpiProbe`

如果你选择 adapter 路线，那么适配层只需要额外拿到一个外部 `seq`，然后映射成 `KpiProbe`：

- `KpiProbe.header = business_msg.header`
- `KpiProbe.seq = external_seq`
- `KpiProbe.payload_size = 业务负载字节数`
- `KpiProbe.payload = 可选的序列化字节，或者固定长度占位 payload`

这里的 `external_seq` 可以来自：

- 业务消息已有的单调递增序号字段
- 业务发送侧自己维护的计数器
- 与业务消息一一对应的配套序号源

推荐做法是在 UE 发送点附近新增一个轻量 adapter node，避免业务主链路大改。

### 场景 B：业务消息没有 Header

如果业务消息没有 `std_msgs/Header`，而你又需要可解释的 latency 或 loss 结果，推荐先在业务侧定义一个 wrapper message，在发送时补上发送时刻和序号，然后再接入 KPI 工具链。

推荐包装形式：

```text
std_msgs/Header header
uint64 seq
<YourBusinessMsg> data
```

建议规则：

- `header.stamp` 在真正调用 publish 之前填写
- `seq` 在发送侧单调递增
- `data` 保持原业务消息不变

然后 adapter node 再把 wrapper 中的 `header` 和 `seq` 映射到 `KpiProbe`。这样后续仍然可以复用现有的 subscriber、collector 和 exporter。

### 什么时候还建议保留 `KpiProbe` / adapter 路线

虽然现在已经支持直接观测任意 topic，但下面这些场景仍然建议保留 `KpiProbe` 或 adapter：

- 你需要严格可控的发送时刻，而业务消息当前没有可靠的发送时间戳
- 你需要稳定的 loss / out-of-order 统计，而业务消息没有序号字段
- 你希望实验流量和业务流量完全隔离，避免互相影响
- 你要对比不同 QoS、payload 大小和发包频率，探针模式更容易复现实验条件

## Known limitations

- 当前一次 launch 仍然只支持单向单 topic 测量
- `latency_ms` 使用发送端和接收端系统时间差，当前版本依赖跨主机时间同步
- 如果发送端和接收端系统时间未同步，单向 latency 会混入 clock offset
- 若无法保证跨主机时间同步，结果应标注为“近似单向时延”
- `loss` 基于 `seq` 跳号统计，若消息晚到并形成 out-of-order，当前版本不会回补之前的 loss
- `generic_topic` 模式下，latency 和 loss 统计能力取决于业务消息里是否真的存在可用时间戳和序号字段
- 当前只提供 CSV exporter
- 当前未接入无线侧、核心网或设备日志
- 当前未提供 GUI、Grafana、Prometheus

## 后续可扩展方向

- 多 topic / 多流并行测量
- 可插拔 exporter
- 更细粒度的 QoS 变量
- 统计结果发布到外部时序数据库
- 更严格的时钟同步与实验编排脚本
