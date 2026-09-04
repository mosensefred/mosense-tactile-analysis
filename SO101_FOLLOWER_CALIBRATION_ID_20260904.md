# SO-101 follower 校准 id 踩坑 —— 两套校准文件混淆

> 日期：2026-09-04 ｜ 状态：**已解决 ✅**
> 一句话：FastWAM 真机 rollout 用 `--robot.id=mosense_follower` 会加载到**错误的校准文件**（另一套 homing_offset），跟电机里存的**正确 7/24 值** mismatch，卡在交互式校准提示 `input()` 上，后台跑直接 `EOFError` 崩溃。改用 `--robot.id=mosense_follower_arm` 即匹配。

---

## 1. 现象

`lerobot-rollout`（FastWAM 触觉模型，105K checkpoint）首次启动失败，退出码 1：

```
INFO  follower.py:117 Mismatch between calibration values in the motor
      and the calibration file or no calibration file found
ERROR follower.py:145 Failed to connect mosense_follower SOFollower
...
  File "so_follower.py", line 158, in calibrate
    user_input = input(...)
EOFError: EOF when reading a line
Press ENTER to use provided calibration file ... or type 'c' ... to run calibration:
```

两个问题叠加：

1. **校准 mismatch** —— 电机里的校准值 ≠ 校准文件里的值。
2. **交互式 `input()` 卡死** —— `calibrate()` 会问「按 ENTER 用校准文件 / 按 c 重新校准」，后台跑没有 stdin，抛 `EOFError`。

## 2. 根因

`~/.cache/huggingface/lerobot/calibration/robots/so_follower/` 下存在**两个 follower 校准文件**，值完全不同：

| 文件 | 性质 |
|---|---|
| `mosense_follower.json` | **另一套错误值**（来历不明，非 7/24 训练坐标系）|
| `mosense_follower_arm.json` | **正确的 7/24 训练值**（= 权威项目路径副本）|

rollout 用了 `--robot.id=mosense_follower`，加载到错误的那套；而**电机里存的其实是正确的 7/24 值**，于是 mismatch。

## 3. 两套校准值对比（homing_offset）

| 关节 | `mosense_follower`（错）| `mosense_follower_arm`（对）| 电机实际 |
|---|---|---|---|
| shoulder_pan | -799 ❌ | -1869 ✅ | -1869 |
| shoulder_lift | -1294 ❌ | -914 ✅ | -914 |
| elbow_flex | -1391 ❌ | -1934 ✅ | -1934 |
| wrist_flex | -1754 ❌ | -1940 ✅ | -1940 |
| wrist_roll | -1626 ❌ | -1748 ✅ | -1748 |
| gripper | 1053 ❌ | 1038 ✅ | 1038 |

## 4. 解决

把 rollout 命令的 `--robot.id` 从 `mosense_follower` 改为 **`mosense_follower_arm`**。

`is_calibrated` 比较电机值 vs 校准文件值，匹配后不再触发 `calibrate()` 的 `input()`，既解了 mismatch，也顺带消掉了 EOFError。

> ⚠️ **危险点**：如果当时按 ENTER，会用 `mosense_follower.json` 的**错误值 `write_calibration` 覆盖电机**，重演 [CALIBRATION_CORRUPTION_POSTMORTEM](CALIBRATION_CORRUPTION_POSTMORTEM_20260904.md) 的坐标系损坏。必须先读电机确认，不能盲目回车。

## 5. 教训

1. **follower 校准 id 一律用 `mosense_follower_arm`**，`mosense_follower`（无 `_arm` 后缀）是错误值，任何 rollout/record 都不要用。
2. **权威校准在项目路径** `/media/mosense/Data2TB/Projects/Mosense-LeRobot/configs/lerobot/calibration/`，`~/.cache` 只是缓存副本，可能被改坏或出现多套。
3. **校准 mismatch 时先读电机实际值**再决定动作，读法见下。

## 6. 读电机校准值（快速验证）

```bash
cd /media/mosense/Data2TB/Projects/Mosense-LeRobot-Tactile
conda run -n lerobot-tactile python -c "
from lerobot.motors import Motor, MotorNormMode
from lerobot.motors.feetech import FeetechMotorsBus
bus = FeetechMotorsBus(port='/dev/ttyACM0', motors={
  'shoulder_pan': Motor(1,'sts3215',MotorNormMode.DEGREES),
  'shoulder_lift': Motor(2,'sts3215',MotorNormMode.DEGREES),
  'elbow_flex': Motor(3,'sts3215',MotorNormMode.DEGREES),
  'wrist_flex': Motor(4,'sts3215',MotorNormMode.DEGREES),
  'wrist_roll': Motor(5,'sts3215',MotorNormMode.DEGREES),
  'gripper': Motor(6,'sts3215',MotorNormMode.RANGE_0_100)}, calibration={})
bus.connect()
for n,c in bus.read_calibration().items():
    print(n, c.homing_offset, [c.range_min, c.range_max])
bus.disconnect()"
```

## 7. 关联

- [CALIBRATION_CORRUPTION_POSTMORTEM_20260904.md](CALIBRATION_CORRUPTION_POSTMORTEM_20260904.md) —— 校准零点被手动改坏的复盘（根因不同，同属校准线）
- [FASTWAM_150K_REPORT_20260904.md](FASTWAM_150K_REPORT_20260904.md) —— 150K 训练完成报告
- [AGENT_GUIDE.md](../Multimodal-Tactile-Sensing-for-Embodied-AI/AGENT_GUIDE.md) §4.11 —— FastWAM 触觉 rollout 命令模板（`--robot.id` 需改为 `mosense_follower_arm`）
