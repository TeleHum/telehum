# LeRobot ROS 2 Workspace for SO101

这是一个面向 SO101 机械臂的 ROS 2 工作区，保留了现有 `colcon + ament_python + package.xml` 主构建链路，并在此基础上补齐了开发依赖入口、根级文档、最小 demo 和 smoke test，方便后续维护与扩展。

## 项目简介

当前仓库主要包含两类内容：

- ROS 2 Python 包：
  - `so101_mujoco_pkg`：提供 MuJoCo 可视化节点、无硬件 demo 发布节点，以及联动 launch。
  - `so101_master_pkg`：提供唯一的 SO101 主臂硬件接口节点，负责读取 Feetech 电机并发布 ROS 2 话题。
  - `so101_follower_pkg`：提供真实从臂执行节点，订阅主臂 `JointState` 并把命令写入 Feetech 电机。
- 机器人模型与资产：
  - `src/so101_6dof/`：SO101 的 MuJoCo / URDF 描述和 STL 资产。
  - `archive/`：历史模型与归档文件，不参与当前 ROS 2 构建。

## 当前架构说明

工作区仍然按标准 ROS 2 方式构建：

- `src/` 下每个带 `package.xml` 的目录都是一个独立 ROS 2 包。
- `colcon build` 仍然是主构建入口。
- `package.xml`、`setup.py`、`setup.cfg` 仍然是 ROS 包安装与发布的事实来源。
- 根目录 `pyproject.toml` 统一管理 Python 依赖，例如 `numpy`、`lerobot[feetech]`、`mujoco`、`youzi-robot`、`pytest`。
- `package.xml` 现在只保留 ROS 2 相关依赖，不再承载纯 Python 运行时依赖。
- `pyproject.toml` 不接管 ROS 2 包构建，也不替代 `colcon`。

推荐的数据流如下：

1. 真机模式：
   `so101_master_node` 从串口读取电机角度，发布到 `master/joint_states`。
2. 真机主从联动模式：
   `leader_follower.launch.py` 组合 `so101_master_pkg` 的主臂接口节点和 `so101_follower_pkg` 的从臂执行节点。
3. 真机联动模式：
   `control.launch.py` 组合 `so101_master_pkg` 的主臂接口节点和 `so101_mujoco_pkg` 的 MuJoCo 节点。
4. 可视化节点：
   `so101_mujoco_node` 订阅 `master/joint_states`，驱动 MuJoCo 模型可视化。
5. 无硬件 demo：
   `demo_joint_publisher` 直接生成一组周期性关节目标，供 `so101_mujoco_node` 使用。

## 目录结构说明

```text
.
├── README.md
├── pyproject.toml              # 工作区级 Python 依赖与 pytest 配置
├── scripts/
│   ├── install_deps.sh         # Python 依赖安装脚本
│   └── smoke_check.sh          # 根级静态 smoke check
├── tests/
│   └── test_workspace_smoke.py # 不依赖硬件的最小工作区测试
├── src/
│   ├── so101_mujoco_pkg/       # ROS 2 仿真/可视化包
│   │   ├── so101_mujoco_pkg/   # Python 源码
│   │   ├── launch/             # launch 文件
│   │   ├── config/             # MuJoCo 辅助脚本
│   │   └── test/               # 现有 ament lint 测试
│   ├── so101_master_pkg/       # ROS 2 主臂硬件接口包
│   │   ├── so101_master_pkg/
│   │   ├── launch/
│   │   └── config/             # 电机参数与硬件校准脚本
│   ├── so101_follower_pkg/     # ROS 2 真实从臂执行包
│   │   ├── so101_follower_pkg/
│   │   ├── launch/
│   │   └── config/             # 从臂串口与映射参数
│   └── so101_6dof/             # SO101 模型、MJCF、URDF、STL 资产
├── archive/                    # 历史模型，不参与当前构建
├── build/                      # colcon 中间产物
├── install/                    # colcon 安装产物
└── log/                        # colcon 构建/测试日志
```

## 各个源码包 / 模块 / 子目录的作用

### `src/so101_mujoco_pkg`

- `so101_mujoco_pkg/so101_mujoco_node.py`
  订阅关节目标并驱动 MuJoCo 模型显示。
- `so101_mujoco_pkg/demo_joint_publisher.py`
  无硬件 demo，用周期信号生成关节目标。
- `launch/control.launch.py`
  组合 `so101_master_pkg` 的真机主臂节点和 MuJoCo 节点联动启动。
- `launch/sim_demo.launch.py`
  demo 发布节点 + MuJoCo 节点联动启动。
- `config/`
  只保留 MuJoCo 手动查看等仿真辅助脚本。

### `src/so101_master_pkg`

- 提供独立的 SO101 主臂接口节点、参数文件、硬件校准脚本和最小 launch。
- `so101_mujoco_pkg` 的 `control.launch.py` 直接复用这个包，不再保留重复接口实现。

### `src/so101_follower_pkg`

- 提供真实从臂执行节点、主从联动 launch 和从臂参数文件。
- `so101_follower_node` 订阅 `master/joint_states`，按从臂自己的 `offsets/inverts` 反算 `Goal_Position` 并写入 Feetech 电机。
- 可选发布 `follower/joint_states` 作为从臂回读反馈。

## `scripts/` 目录说明

- `scripts/install_deps.sh`
  安装工作区级 Python 依赖。它会优先创建 `.venv/`，然后从根目录 `pyproject.toml` 安装依赖分组。
  常见用途：快速准备开发环境、按需加上 `--with-mujoco` 或 `--with-test`。
- `scripts/smoke_check.sh`
  做一轮快速静态自检。它会执行 `compileall`、`colcon list` 和根级 `pytest tests`，用来判断仓库结构、导入路径和基础测试是否还自洽。
  常见用途：改完代码后先跑一遍，快速发现明显问题。

### `src/so101_6dof`

- 存放 SO101 的 MJCF / URDF / 网格文件。
- 不是 ROS 2 包，但会被 `so101_mujoco_pkg` 在运行时查找和使用。

### `archive/`

- 历史 SO100 模型资料，仅作参考。
- 不属于当前主流程，不建议新逻辑继续依赖这里的文件。

## 依赖安装

### 1. ROS 2 依赖

建议先安装并 source 你的 ROS 2 发行版，例如：

```bash
source /opt/ros/humble/setup.bash
```

然后在工作区根目录安装 ROS 依赖：

```bash
rosdep install --from-paths src --ignore-src -r -y
```

说明：

- `rosdep` 这里只负责 ROS 2 依赖，例如 `rclpy`、`sensor_msgs`、`launch_ros`。
- `numpy`、`lerobot[feetech]`、`mujoco`、`youzi-robot`、`pytest` 统一由根级 `pyproject.toml` 管理。
- 真机相关的 `hardware` 依赖会一并安装 `feetech-servo-sdk`；它对应的 Python 模块名是 `scservo_sdk`。
- 例外：`so101_mujoco_pkg/package.xml` 保留 `python3-pytest`，仅用于让 `colcon test` 正常发现现有 ament pytest 测试。

### 2. Python 依赖

推荐使用仓库自带脚本：

```bash
scripts/install_deps.sh --with-test
```

如果需要 MuJoCo 仿真相关能力：

```bash
scripts/install_deps.sh --with-mujoco --with-test
```

脚本会优先创建 `.venv/`，也支持 `--system` 和 `--conda`。

如果你更想直接用 `pip`，也可以使用根目录 `pyproject.toml` 提供的可选依赖分组：

```bash
pip install -e ".[hardware,test]"
pip install -e ".[hardware,sim,test]"
```

注意：

- 这里的 `pyproject.toml` 负责工作区级 Python 依赖管理。
- 真正的 ROS 2 包构建仍然依赖 `package.xml + setup.py + colcon`。

## Build / 启动 / 运行

### Build

```bash
source /opt/ros/humble/setup.bash
colcon build --symlink-install
source install/setup.bash
```

### 启动主臂接口包

```bash
ros2 launch so101_master_pkg so101_master.launch.py
```

### 启动主臂 + MuJoCo 联动

```bash
ros2 launch so101_mujoco_pkg control.launch.py
```

### 启动真实从臂执行节点

```bash
ros2 launch so101_follower_pkg so101_follower.launch.py
```

### 启动主臂 + 真实从臂联动

```bash
ros2 launch so101_follower_pkg leader_follower.launch.py
```

### 启动无硬件 demo + MuJoCo

```bash
ros2 launch so101_mujoco_pkg sim_demo.launch.py
```

常用可覆盖参数示例：

```bash
ros2 launch so101_mujoco_pkg control.launch.py params_file:=/abs/path/to/motors.yaml
ros2 launch so101_mujoco_pkg control.launch.py joint_states_topic:=master/joint_states
ros2 launch so101_mujoco_pkg control.launch.py publish_delay_ms:=25.0
ros2 launch so101_follower_pkg leader_follower.launch.py follower_params_file:=/abs/path/to/follower_motors.yaml
ros2 launch so101_follower_pkg leader_follower.launch.py master_publish_delay_ms:=25.0
ros2 launch so101_follower_pkg leader_follower.launch.py follower_topic:=follower/joint_states
ros2 launch so101_mujoco_pkg sim_demo.launch.py amplitude:=0.25 period:=6.0
```

## 如何做最小验证

### 根级静态 smoke check

```bash
bash scripts/smoke_check.sh
```

该检查会做三件事：

1. 对三个 ROS 包做 `compileall` 语法检查。
2. 用 `colcon list` 验证工作区能识别到预期 ROS 包。
3. 运行根级 `pytest tests` 静态 smoke tests，检查项目是否又引入了重复实现或依赖边界回退。

### 构建验证

```bash
source /opt/ros/humble/setup.bash
colcon build --symlink-install --packages-select so101_mujoco_pkg so101_master_pkg so101_follower_pkg
```

### 最小运行验证

如果本机安装了 MuJoCo 且有图形环境，可以使用无硬件 demo 做最小联调：

```bash
source /opt/ros/humble/setup.bash
source install/setup.bash
ros2 launch so101_mujoco_pkg sim_demo.launch.py
```

## 输出文件位置和含义

- `build/`
  `colcon` 的中间构建目录，可安全清理后重建。
- `install/`
  `colcon` 的安装产物，包含 `lib/`、`share/` 等运行时目录。
- `log/`
  构建与测试日志目录，便于排查 `colcon build/test` 问题。

这些目录均属于生成产物，不建议手工编辑，也已在 `.gitignore` 中忽略。

## 已知限制

- `lerobot[feetech]`、`mujoco`、`youzi-robot` 不是标准 ROS 2 `rosdep` 依赖，仍需额外 `pip` 安装。
- `sim_demo.launch.py` 需要图形环境；在无显示设备的终端环境中通常无法完整打开 MuJoCo viewer。
- 真机接口节点依赖 `/dev/ttyACM0` 或你实际的串口设备，以及正确的电机参数和校准值。
- 从臂节点默认参数文件中的 `serial_port`、`offsets`、`inverts` 需要你先按真实从臂填写，否则节点会直接报错退出。
- 校准脚本当前只保留在 `so101_master_pkg/config/so101_calib.py`，默认偏置值与 `motors.yaml` 保持一致；如果你改了参数，最好同步更新两处。
- `src/so101_6dof` 当前是工作区资源目录而不是独立 ROS 包，因此资源查找依然保留了向上搜索工作区路径的兼容逻辑。
- 仓库当前没有单独提供根级 `LICENSE` 文件；包级元数据已统一，但正式开源前建议补齐仓库级许可证文件。

## 后续扩展建议

1. 为 `src/so101_6dof` 增加独立资源包封装，减少运行时路径搜索逻辑。
2. 把 `motors.yaml` 和校准脚本中的重复偏置参数进一步提炼成单一配置来源。
3. 补充 CI，至少自动执行 `scripts/smoke_check.sh` 和 `colcon build`。
4. 增加更细粒度的参数校验测试，例如校准值长度、话题名称和模型路径检查。
5. 补齐仓库级 `LICENSE`、发布说明和版本变更记录。
