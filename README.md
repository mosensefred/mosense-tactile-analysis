# MoSense 触觉 LeRobot Fork —— 代码分析总结

> 对象仓库：[MoSenseHK/Multimodal-Tactile-Sensing-for-Embodied-AI](https://github.com/MoSenseHK/Multimodal-Tactile-Sensing-for-Embodied-AI)
> 分析分支：`codex/tactile-native-fork`
> 分析日期：2026-08-28

---

## 1. 仓库定位

这是 [LeRobot](https://github.com/huggingface/lerobot)（v0.6.0）的一个 fork，目标是把 **Mosense 霍尔触觉传感器** 原生集成进 LeRobot，而不是靠项目外的 wrapper 脚本。核心研究主线是：**FastWAM 世界模型 + 低维霍尔触觉 co-training**，用来解决视觉遮挡下的接触辨识与空抓判断（典型任务：笔袋取笔 / 圆柱插入）。

普通机器人类型（如 `so101_follower`）默认无触觉，只有显式传入 `tactile` 子配置（`--robot.tactile.port=/dev/ttyUSB0`）才启用触觉硬件。

---

## 2. 本地克隆要点（Windows）

- **5 个 PDF 文件名含 `:` / `?`**（如 `Fast-WAM: Do World Action Models Need Test-time Future Imagination?.pdf`），Windows 文件系统无法创建，用 pathspec 排除 `docs/paper/` 后 checkout。
- **LFS 大文件**（`.stl` / `.mp4` / `.safetensors` 等）用 `GIT_LFS_SKIP_SMUDGE=1` 跳过，媒体与数据集只落指针文件。
- 结果：1123 个文件中的 1118 个落地，代码完整。

---

## 3. 触觉数据链路（五层）

```
串口 45 字节包
  → 解析 (adapters/mosense_hall.py)
  → 信号处理 (processing.py / eflesh_processing.py)
  → 标定状态机 + 接触估计 (eflesh_processing.py)
  → LeRobot 观测注入 (sensors/mosense_hall.py → so_follower.py)
  → FastWAM 触觉 world-model (models/fastwam/tactile-world-model-design.md)
```

### 3.1 协议层

45 字节包：`[0]` 长度字节、`[1]` 状态位、`[2]=0xF0` response、`[3]=0x02` get-all，`[4:44]` 为 5 传感器 × 8 字节（`>Hhhh` = 保留字 + x/y/z 三个 int16）。`MosenseHallStreamDecoder.feed()` 做流式重同步：头部对不上就丢字节再试。

### 3.2 两条处理链

- **`TactileSignalProcessor`**（`processing.py`）：简单三段式——中位数/MAD 基线 → soft deadzone → EMA 低通。用于生成/加载标定 profile。
- **`EFleshProcessor`**（`eflesh_processing.py`）：富处理链，原生传感器实际使用。组件：HampelFilterBank（尖峰）→ MagneticInterferenceCompensator（共模磁干扰）→ AdaptiveLowPass → 归一化 → 死区 → ForceDecoupler → ContactEstimator。

### 3.3 标定状态机

`CalibrationState` 状态机：`DISCONNECTED → WARMUP → WAITING_FOR_STABLE_IDLE → COLLECTING_BASELINE → CALIBRATED_IDLE ⇄ CONTACT_ACTIVE → RELEASE_SETTLING`。

关键：**`frame_valid = calibration.calibrated`**——标定完成前所有触觉观测都标 `frame_valid=0`，下游据此掩掉无效帧。传感器需静止无负载才能完成标定。

### 3.4 接触估计

```
sensor_energy = ||normalized_filtered||₂           (5 维)
contact_score = sorted_energy[-1] + 0.30 * sorted_energy[-2]
```

最强传感器 + 30% 次强传感器，稳健且不被平均稀释。磁场补偿在无接触空闲时更新共模分量，另有 `magnetic_status_active` 异常标志。

### 3.5 观测输出（对齐 FastWAM）

| key | shape | 含义 |
|---|---|---|
| `observation.tactile.raw` | `(5,3)` | 原始霍尔读数 |
| `observation.tactile.processed` | `(5,3)` | 滤波+补偿后信号（训练用） |
| `observation.tactile.activations` | `(5,)` | 各传感器激活度 |
| `observation.tactile.contact_active` | `(1,)` | 是否接触 |
| `observation.tactile.frame_valid` | `(1,)` | 本帧是否有效 |

---

## 4. LeRobot 接入（两条路径）

1. **原生路径（主推）**：`MosenseHallTactileSensor` 作为 `so_follower` 可选成员（`config.tactile`），观测经 `observation_features` 注册，`get_observation()` 里合并。
2. **旧桥接路径**：`MosenseEFleshSerialBridge`（后台串口线程）+ `TactileObservationInjectorStep`（`ObservationProcessorStep`），来自上一工作区。

---

## 5. FastWAM 触觉训练实现（已落地）

**结论：不是设计稿，是成品。** 设计稿 §10 规划的 `src/mosense_lerobot/fastwam_tactile/` 未建，实际代码落在原生 LeRobot policy 路径：

- `src/lerobot/policies/fastwam/modeling_fastwam.py` —— `FastWAMPolicy` + `FutureHallHead`
- `src/lerobot/policies/tactile_utils.py` —— `TactileTemporalEncoder`
- `src/lerobot/policies/fastwam/configuration_fastwam.py` —— `FastWAMConfig`
- `scripts/autodl/train_fastwam_tactile.sh` / `train_fastwam_no_tactile.sh` —— 训练脚本（消融对照）
- `scripts/fastwam/check_tactile_usage.py` —— checkpoint/梯度验证

### 5.1 三个核心组件

**`TactileTemporalEncoder`**（TCN）：`frame_encoder(Linear+LN+GELU) → temporal_encoder(Conv1d×2) → output_projection`，用 `frame_valid` mask 加权池化，把 `[B,T,5,3]` 压成 context tokens。

**`FutureHallHead`**（MLP）：`LayerNorm → Linear → GELU(tanh) → Linear`，从 action hidden `[B,T,D]` 预测未来 `[B,future_steps,5,3]`。

**Loss**：
```
L_total = λ_video·L_video + λ_action·L_action + λ_hall·L_hall
L_hall  = masked MSE(pred_hall, observation.tactile.processed[t+1:t+H])
```

### 5.2 时间窗口机制（`tactile_delta_indices`）

配置声明触觉字段的独立密集窗口：

```python
tactile_delta_indices = range(1 - history_steps, 1 + future_steps)
# history=10, future=48 → [-9 .. 48]，共 58 帧
```

数据集端 `resolve_delta_timestamps` 给触觉 key 分派独立窗口（图像/state 走视频抽帧窗口）：

```
帧偏移 delta_indices ──÷fps──▶ delta_timestamps(秒) ──×fps+round──▶ 数据集帧索引
```

模型端按「前缀=历史，后缀=未来」切片：

```
sequence [B,58,5,3] ──┬── [:10] ──► 历史 [t-9..t] ──► TactileTemporalEncoder ──► context（训练+推理）
                      └── [10:58] ► 未来 [t+1..t+48] ─► FutureHallHead MSE 监督（仅训练）
```

无效未来帧由 `frame_valid` / `is_pad` mask 剔除。推理端用 `deque(maxlen=history_steps)` 维护历史，不运行 future head。

### 5.3 与设计稿的差异

- target 用「直接预测归一化低维 Hall 帧」，而非 `stop_gradient(HallEncoder(future))`（设计稿的 Level 1 最小可跑 fallback）。
- FutureHallHead 只喂 action hidden，未接 fused hidden。
- 任务从「笔袋取笔」变为 `Insert_The_Cylinder`，pretrained 用 `pretrained_fastwam_move_pen`。
- 训练默认 `lambda_video=1.0`、`freeze_video_expert=false`（真正的 world-model 配置，修正了旧例子的 action-only 问题）。

---

## 6. 关键结论

1. 触觉是**低维 5×3 霍尔时序**，不是触觉图；第一版不做触觉图像世界模型。
2. 触觉接入以**可选的 `robot.tactile` 子配置**实现，非触觉路径完全不受影响。
3. FastWAM 触觉训练侧已完整落地 Level 0（触觉条件）和 Level 1（future Hall head），配齐了 AutoDL 训练/验证脚本。
4. 核心创新点是 **world-model co-training**：训练时预测未来触觉、推理时只出动作，用未来 Hall loss 约束 MoT hidden 学「动作→接触变化」。
