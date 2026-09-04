# 排障记录：遥操作录制「自己结束」问题（未解决）

> 记录时间：2026-09-04
> 状态：**待解决**（暂停调试，先固化上下文）
> 现象：`lerobot-record` 遥操作录制演示时，无法稳定录完一个完整 episode——要么启动即崩，要么开始后几秒自动结束。

---

## 一、问题全貌

目标：用 leader（`/dev/ttyACM1`）遥操作 follower（`/dev/ttyACM0`）录制「方块入杯」演示（1 episode / 60s）。

**唯一成功参照**：`cube_in_cup_demo_1154`（11:55，759 帧 / ~25s），用 `setsid nohup ... &` 后台启动，**未做 stdin 重定向**，一次成功。

之后所有重试都失败，且失败模式随启动方式不同而不同。

## 二、三个独立故障层

### 层①：校准提示阻塞（EOFError）

启动时 leader/follower 都有校准文件，`calibrate()` 会 `input()` 弹提示：

```
Press ENTER to use provided calibration file associated with the id XXX,
or type 'c' and press ENTER to run calibration:
```

后台/管道 stdin 读不到输入 → `EOFError: EOF when reading a line` → 崩溃退出。

- 定位：`src/lerobot/robots/so_follower/so_follower.py:158`、`src/lerobot/teleoperators/so_leader/so_leader.py:111`
- 相关日志特征：`Mismatch between calibration values ... Press ENTER to use provided calibration`

### 层②：喂回车的副作用（3 秒「录制结束」）

为解决层①，管道喂回车（`printf '\n\n'`）。但多余的回车被**键盘监听器**捕获，映射为「右箭头 = 结束录制」→ `exit_early=True`，导致：

```
开始录制第 0 条   →  3 秒后  录制结束
```

- 定位：`src/lerobot/utils/keyboard_input.py` 的 `apply_recording_control()`（`"right"` → `exit_early=True`）与 `create_key_listener()`
- 键盘后端：X11 下用 `pynput` **全局监听**（`pynput_can_capture()`），真实键盘按键也会触发；非 TTY stdin 时退回 `None`
- 关键陷阱：pynput 全局监听是**抓真实物理键盘**的，遥操作时用户手在操作机械臂，理论上不该触发，但喂的 stdin 回车会走 terminal 后端被误判

### 层③：follower sync_read 通信失败（demo6）

避开键盘监听改用 `< /dev/null` 启动后，崩溃点变成 follower 读位置失败：

```
so_follower.py:225 get_observation()
  → bus.sync_read("Present_Position", num_retry=...)
  → motors_bus.py:1190 ConnectionError: Failed to sync read 'Present_Position'
    on ids=[1,2,3,4,5,6] after 3 tries. [TxRxResult] There is no status packet!
```

- 这是 follower 电机总线（`/dev/ttyACM0`）的**组播读**失败，重试 3 次无状态包返回
- 与 demo1 成功时（759 帧正常）状态已变化；疑与中途多次 `write_calibration` 手动写电机、`disable_torque` 相关
- 注意区分：`sync_read` 在**未注册校准**时报的是 `RuntimeError: has no calibration registered`（这是另一回事）；这里报 `ConnectionError: no status packet` 才是真通信失败

## 三、已尝试过的启动方式（均失败）

| 方式 | 结果 |
|---|---|
| `setsid nohup ... &`（无 stdin 重定向）| ✅ demo1 成功（759帧）|
| 管道 `printf '\n'`（1 个回车）| leader 提示吃不到第二个回车 → 卡死 |
| 管道 `printf '\n\n'`（2 个回车）| 第二个回车被键盘监听吃 → 3秒结束 |
| pty 包装 `auto_record.py` | 引号嵌套损坏 cameras YAML → 参数错误 |
| `pexpect` spawn bash -c | 双层引号剥掉 YAML 内双引号 → 参数错误 |
| `< /dev/null` | 层③：follower sync_read 通信失败 |

## 四、关键文件与命令

```bash
# 校准提示位置
src/lerobot/robots/so_follower/so_follower.py:158   # calibrate() input()
src/lerobot/teleoperators/so_leader/so_leader.py:111 # calibrate() input()

# 键盘监听（结束录制逻辑）
src/lerobot/utils/keyboard_input.py
  apply_recording_control(): "right"→exit_early, "esc"→stop_recording
  create_key_listener(): pynput 全局监听 (X11) / TerminalKeyListener (TTY) / None

# sync_read 失败点
src/lerobot/motors/motors_bus.py:1157 sync_read / :1190 _sync_read

# 校准文件（两处路径，注意区分！）
~/.cache/huggingface/lerobot/calibration/teleoperators/so_leader/mosense_leader.json
~/.cache/huggingface/lerobot/calibration/robots/so_follower/mosense_follower_arm.json
# 用户指出的另一处（项目内，主动臂）：
/media/mosense/Data2TB/Projects/Mosense-LeRobot/configs/lerobot/calibration/teleoperators/so_leader
```

## 五、待办 / 下一步方向

1. 先查清层③：follower 电机当前 `sync_read` 为何「no status packet」——逐个电机 ping、`GroupSyncRead` 原始 SDK 读、检查是否我手动 `write_calibration` 把电机写进异常状态
2. 层②的根治：让 `calibrate()` 的提示**不弹**（校准已写入电机且文件匹配时跳过），或给 record 加「自动确认校准」的开关；查是否有 `--robot.calibration_dir` 之类参数能指向已就绪的校准
3. 层①参考 demo1 成功路径，复现其确切的 stdin 环境

## 六、关联

- 云端 FastWAM 训练（150K）与「方块入杯」真实实验的依赖项——本问题不解，无法采到遥操作演示数据
- 用户给的参考：GitHub `MoSenseHK/Multimodal-Tactile-Sensing-for-Embodied-AI` 分支 `codex/tactile-native-fork` 下 `docs/paper`
