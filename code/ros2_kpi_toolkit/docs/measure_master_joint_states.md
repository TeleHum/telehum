# `/master/joint_states` KPI 测量操作文档

本文档用于指导他人使用本仓库的 `ros2_kpi_toolkit`，对以下业务 topic 做 ROS 2 通信 KPI 测量：

- topic 名称：`/master/joint_states`
- topic type：`so101_interfaces/msg/SequencedJointState`

本文档按下面这类消息结构编写：

```text
std_msgs/Header header
uint64 seq
string[] name
float64[] position
float64[] velocity
float64[] effort
```

在这个前提下，工具可以直接提取：

- `header.stamp`：用于计算单向时延及其窗口统计
- `seq`：用于计算丢包、丢包率和乱序
- 整条消息序列化后的大小：用于估算吞吐

因此，这个 topic 可以覆盖本工具当前支持的完整 ROS 2 KPI 范围：

- `avg_latency_ms`
- `p95_latency_ms`
- `p99_latency_ms`
- `std_latency_ms`
- `jitter_ms`
- `recv_rate_hz`
- `throughput_bps`
- `lost_count`
- `loss_rate`
- `out_of_order_count`

## 1. 适用场景

推荐用于以下场景：

- 已经存在业务 topic `/master/joint_states`
- 不希望改动业务主链路
- 希望直接在接收端观测真实业务流量
- 希望导出 CSV 做实验记录或后处理

本方案使用的是 `generic_topic` 模式，不需要启动工具自带的 `probe_publisher`。

## 2. 前提条件

执行前请确认以下条件成立：

- 操作系统为 Ubuntu 22.04
- 已安装 ROS 2 Humble
- 已安装 `colcon`
- 当前机器可以访问 `/master/joint_states`
- 已构建并 source 当前仓库工作空间中的 `so101_interfaces`
- 发布端与接收端使用相同的 `ROS_DOMAIN_ID`

如果发布端和接收端不是同一台机器，还要额外确认：

- 两台机器网络互通
- DDS 发现正常
- 系统时间已同步

说明：

- 本工具中的 `latency_ms` 是按 `接收时间 - 消息中的发送时间戳` 计算的
- 如果两台机器没有做好时间同步，跨机单向时延会混入 clock offset
- 如果只能保证大致同步，建议把结果标注为“近似单向时延”

## 3. 测量前检查

先确认 topic 的类型和消息字段。

```bash
source /opt/ros/humble/setup.bash
ros2 topic type /master/joint_states
ros2 interface show so101_interfaces/msg/SequencedJointState
ros2 topic echo /master/joint_states --once
```

预期检查点：

- `ros2 topic type /master/joint_states` 输出通常为 `so101_interfaces/msg/SequencedJointState`
- `ros2 interface show` 中应能看到 `header` 和 `seq`
- `ros2 topic echo --once` 中应能看到 `header.stamp` 不是全零
- `seq` 应随着消息发送单调递增

如果你的业务环境里 `/master/joint_states` 使用的是别的自定义消息类型，也可以继续测，但至少要保证下面两点：

- 时间戳字段路径仍然能用 `header.stamp` 访问
- 序号字段路径仍然能用 `seq` 访问

如果 `header.stamp` 为零或没有更新：

- latency 相关 KPI 会变成 `NaN`
- rate 和 throughput 仍然可用

如果 `seq` 不是单调递增：

- `lost_count`、`loss_rate`、`out_of_order_count` 会失真

## 4. 构建工作空间

在仓库根目录执行：

```bash
source /opt/ros/humble/setup.bash
cd /path/to/anonymized_artifact/code/ros2_kpi_toolkit
colcon build --symlink-install
source install/setup.bash
```

可选自检：

```bash
colcon list
```

## 5. 推荐启动方式

为了避免每次都手动填写一长串参数，仓库里提供了一个针对 `/master/joint_states` 的专用 launch 预设：

- launch 文件：`master_joint_states_kpi.launch.py`
- 预设 topic：`/master/joint_states`
- `topic_type` 默认自动发现（典型值为 `so101_interfaces/msg/SequencedJointState`）
- 预设时间戳字段：`header.stamp`
- 预设序号字段：`seq`

最推荐使用统一 launch 文件，一次性拉起：

- topic monitor
- metrics collector
- CSV exporter

最简单启动命令如下：

```bash
source /opt/ros/humble/setup.bash
source /path/to/your_business_ws/install/setup.bash
cd /path/to/anonymized_artifact/code/ros2_kpi_toolkit
source install/setup.bash

ros2 launch ros2_kpi_bringup master_joint_states_kpi.launch.py
```

说明：

- 当前仓库已经内置 `so101_interfaces/msg/SequencedJointState`
- 如果你的业务工作空间也提供了同名包，请确认实际需要的版本并注意 `source` 顺序

这个命令已经默认完成以下配置：

- `measurement_mode:=generic_topic`
- `enable_publisher:=false`
- `enable_subscriber:=true`
- `enable_collector:=true`
- `enable_exporter:=true`
- `topic_name:=/master/joint_states`
- `topic_type:=` 留空时自动发现
- `timestamp_field:=header.stamp`
- `sequence_field:=seq`
- `qos_profile_mode:=match_publisher`
- `sample_topic_name:=/master/joint_states_kpi_samples`
- `metrics_topic_name:=/kpi_window_stats`
- `dashboard_metrics_topic_name:=/kpi_metrics`
- `window_size_sec:=5.0`
- `metrics_publish_period_sec:=1.0`
- `csv_output_path:=./output/kpi_metrics.csv`

如果只想改少数几个参数，也可以覆盖默认值。例如：

```bash
ros2 launch ros2_kpi_bringup master_joint_states_kpi.launch.py \
  window_size_sec:=10.0 \
  csv_output_path:=./output/master_joint_states_metrics.csv
```

如果你希望显式固定消息类型，也可以手动覆盖：

```bash
ros2 launch ros2_kpi_bringup master_joint_states_kpi.launch.py \
  topic_type:=so101_interfaces/msg/SequencedJointState
```

如果你需要完全自定义所有参数，仍然可以继续使用通用入口 `kpi_pipeline.launch.py`。

## 6. 运行后如何查看结果

### 6.1 查看实时 KPI

实时窗口统计会发布到 `/kpi_metrics`：

```bash
source /opt/ros/humble/setup.bash
cd /path/to/anonymized_artifact/code/ros2_kpi_toolkit
source install/setup.bash
ros2 topic echo /kpi_metrics
```

重点关注字段：

- `avg_latency_ms`
- `p95_latency_ms`
- `p99_latency_ms`
- `jitter_ms`
- `recv_rate_hz`
- `throughput_bps`
- `lost_count`
- `loss_rate`
- `out_of_order_count`

### 6.2 查看中间单样本数据

如果要排查单条消息的计算是否正常，可以看内部样本 topic：

```bash
source /opt/ros/humble/setup.bash
cd /path/to/anonymized_artifact/code/ros2_kpi_toolkit
source install/setup.bash
ros2 topic echo /master/joint_states_kpi_samples
```

这个 topic 适合确认：

- 工具是否正确提取了 `source_stamp`
- 工具是否正确提取了 `seq`
- 单条消息的 `latency_ms`
- 单条消息的 `seq_gap`
- 是否出现 `out_of_order`

### 6.3 查看 CSV 文件

CSV exporter 会在 `output/` 下为每次运行创建独立目录。

可以用下面的命令查看：

```bash
find output -name 'metrics_run_*_part_*.csv' | sort
```

查看最新一个 CSV part：

```bash
tail -f "$(find output -name 'metrics_run_*_part_*.csv' | sort | tail -n 1)"
```

通常目录会类似这样：

```text
output/
  kpi_metrics/
    run_<run_id>/
      metadata.json
      metrics_run_<run_id>_part_0001.csv
```

## 7. 可选：拆开分步启动

如果需要分别排查 monitor、collector、exporter，也可以分三步单独启动。

### 7.1 启动 topic monitor

```bash
source /opt/ros/humble/setup.bash
cd /path/to/anonymized_artifact/code/ros2_kpi_toolkit
source install/setup.bash

ros2 run ros2_kpi_probe topic_monitor --ros-args \
  -p topic_name:=/master/joint_states \
  -p sample_topic_name:=/master/joint_states_kpi_samples \
  -p topic_type:=so101_interfaces/msg/SequencedJointState \
  -p timestamp_field:=header.stamp \
  -p sequence_field:=seq \
  -p qos_profile_mode:=match_publisher
```

### 7.2 启动 metrics collector

```bash
source /opt/ros/humble/setup.bash
cd /path/to/anonymized_artifact/code/ros2_kpi_toolkit
source install/setup.bash

ros2 run ros2_kpi_collector metrics_node --ros-args \
  -p topic_name:=/master/joint_states \
  -p sample_topic_name:=/master/joint_states_kpi_samples \
  -p metrics_topic_name:=/kpi_window_stats \
  -p dashboard_metrics_topic_name:=/kpi_metrics \
  -p window_size_sec:=5.0 \
  -p metrics_publish_period_sec:=1.0
```

### 7.3 启动 CSV exporter

```bash
source /opt/ros/humble/setup.bash
cd /path/to/anonymized_artifact/code/ros2_kpi_toolkit
source install/setup.bash

ros2 run ros2_kpi_exporter csv_exporter --ros-args \
  -p metrics_topic_name:=/kpi_window_stats \
  -p csv_output_path:=./output/kpi_metrics.csv \
  -p topic_name:=/master/joint_states \
  -p topic_type:=so101_interfaces/msg/SequencedJointState \
  -p measurement_mode:=generic_topic \
  -p timestamp_field:=header.stamp \
  -p sequence_field:=seq
```

## 8. 可选：录制 ros2 bag

如果实验需要回放或复盘，建议同时录以下 topic：

```bash
mkdir -p bag
ros2 bag record -o bag/master_joint_states_kpi \
  /master/joint_states \
  /master/joint_states_kpi_samples \
  /kpi_window_stats \
  /kpi_metrics
```

如果只关心最终 KPI，也可以只录：

```bash
ros2 bag record -o bag/master_joint_states_metrics_only /kpi_metrics
```

## 9. 常见问题排查

### 问题 1：`Unknown package 'so101_interfaces'`

说明当前终端还没有 source 到包含 `so101_interfaces` 的环境，或者当前工作空间还没完成构建。

处理方法：

- 先在本仓库根目录执行 `colcon build --symlink-install`
- source 本仓库的 `install/setup.bash`
- 如果业务工作空间也有同名包，再按实际需要补充 source 对应业务工作空间

一个常见顺序如下：

```bash
source /opt/ros/humble/setup.bash
cd /path/to/anonymized_artifact/code/ros2_kpi_toolkit
colcon build --symlink-install
source install/setup.bash
```

### 问题 2：`Unknown topic '/master/joint_states'`

说明当前没有发布端，或者 DDS 发现未成功。

处理方法：

- 确认业务节点已经启动
- 确认 `ROS_DOMAIN_ID` 一致
- 确认网络连通和 DDS 发现正常

### 问题 3：`latency` 全是 `NaN`

通常原因如下：

- `header.stamp` 没有填写
- `header.stamp` 为零
- `timestamp_field` 配置错误

优先检查：

```bash
ros2 topic echo /master/joint_states --once
```

### 问题 4：`loss_rate` 一直为 `0`

通常原因如下：

- `seq` 没有正确填充
- `seq` 不是单调递增
- `sequence_field` 配置错误

优先检查：

```bash
ros2 topic echo /master/joint_states --once
ros2 topic echo /master/joint_states_kpi_samples --once
```

### 问题 5：收不到数据但 topic 明明存在

可能是 QoS 不匹配。

优先建议：

- 保持 `qos_profile_mode:=match_publisher`
- 不要手动改成 `manual`，除非已经明确知道发布端 QoS

### 问题 6：终端窗口统计全部是 `0`

这通常不是 `header.stamp` 或 `seq` 的问题，而是 collector 根本没有收到
`/master/joint_states_kpi_samples`。

优先检查：

```bash
ros2 topic echo /master/joint_states_kpi_samples --once
ros2 topic type /master/joint_states
```

如果 `kpi_samples` 没数据，优先排查下面几项：

- `topic_monitor` 节点是否正常运行
- `/master/joint_states` 的实际 `topic type` 是否和你启动时固定的 `topic_type` 完全一致
- 当前终端是否已经 source 到实际消息类型所在的工作空间
- 发布端 QoS 是否真的能被 `match_publisher` 正确复用

## 10. 交付给他人时建议说明

把本仓库交给别人使用时，建议一并说明下面几点：

- 这个工具测的是 ROS 2 层通信 KPI，不是 5G 无线链路 KPI
- `latency_ms` 依赖消息内的发送时间戳质量
- 跨机测单向时延时必须做好时间同步
- `loss` 和 `out_of_order` 依赖 `seq` 是否真实、单调且连续
- `throughput_bps` 使用的是消息序列化大小估算值

## 11. 一条命令版

如果对方只想最快跑通，可以直接给他下面这条命令：

```bash
source /opt/ros/humble/setup.bash
source /path/to/your_business_ws/install/setup.bash
cd /path/to/anonymized_artifact/code/ros2_kpi_toolkit
source install/setup.bash

ros2 launch ros2_kpi_bringup master_joint_states_kpi.launch.py
```
