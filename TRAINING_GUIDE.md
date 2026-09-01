# FastWAM 触觉训练启动指南

> 对象仓库：[MoSenseHK/Multimodal-Tactile-Sensing-for-Embodied-AI](https://github.com/MoSenseHK/Multimodal-Tactile-Sensing-for-Embodied-AI)
> 对应训练脚本：`scripts/autodl/train_fastwam_tactile.sh` / `train_fastwam_no_tactile.sh`

---

## 1. 训练入口

触觉 FastWAM 训练就一条命令：

```bash
bash scripts/autodl/train_fastwam_tactile.sh
```

无触觉消融对照组：

```bash
bash scripts/autodl/train_fastwam_no_tactile.sh
```

---

## 2. 前置条件（脚本会硬检查，缺一个就退出）

| 条件 | 说明 |
|---|---|
| 环境 | `conda activate lerobot-tactile`（或 `uv sync` 后 `uv run`）|
| CUDA | 脚本检查 `torch.cuda.is_available()`，无 GPU 直接报错 |
| 数据集 | `DATASET_ROOT` 指向本地 LeRobot 数据集 |
| 预训练权重 | `TACTILE_PRETRAINED_POLICY_PATH` → `pretrained_fastwam_move_pen`（含 `config.json` + `model.safetensors`）|

---

## 3. 路径与参数来源（`scripts/autodl/autodl_env.sh`）

```bash
AUTODL_WORK_ROOT=$HOME/autodl-tmp/mosense-lerobot   # 工作根目录
DATASET_ROOT=$AUTODL_WORK_ROOT/datasets/raw/Tactile_FastWAM_Insert_The_Cylinder
DATASET_REPO_ID=local/Tactile_FastWAM_Insert_The_Cylinder
TACTILE_PRETRAINED_POLICY_PATH=$AUTODL_WORK_ROOT/pretrained_fastwam_move_pen
```

---

## 4. 关键训练参数（环境变量可覆盖）

```bash
STEPS=150000              BATCH_SIZE=8
TACTILE_HISTORY_STEPS=10  TACTILE_FUTURE_STEPS=48
LAMBDA_VIDEO=1.0  LAMBDA_ACTION=1.0  LAMBDA_HALL=0.2
TACTILE_CONTEXT_TOKENS=1  TACTILE_ENCODER_HIDDEN_DIM=256
FREEZE_VIDEO_EXPERT=false
ACTION_HORIZON=48  N_ACTION_STEPS=32  NUM_VIDEO_FRAMES=49  ACTION_VIDEO_FREQ_RATIO=4
```

覆盖示例：

```bash
STEPS=5000 LAMBDA_HALL=0.5 bash scripts/autodl/train_fastwam_tactile.sh
```

---

## 5. 稳妥起见，先 dry-run / 冒烟

```bash
bash scripts/autodl/train_fastwam_tactile.sh --dry-run      # 只打印完整命令，不执行
bash scripts/autodl/train_fastwam_tactile.sh --smoke-test   # 2 步冒烟，验证流程
```

---

## 6. 训练流程与产物

1. 先跑 `scripts/autodl/verify_fastwam_dataset.py` 校验数据集契约（图像 key、触觉字段、帧数）；
2. 再走 `lerobot-train`，触觉以 `--policy.tactile_history_steps=10` 等参数传入；
3. checkpoint 落到：

   ```
   outputs/checkpoints/<RUN_NAME>/checkpoints/last/pretrained_model/
   ```

---

## 7. 关键设计说明

- **`lambda_hall=0.2`**：触觉未来预测是辅助损失，主导仍是 video + action。
- **`tactile_future_steps=48`**：开启 `FutureHallHead`（Level 1 co-training）；设为 `0` 则退回 Level 0（仅触觉条件）。
- **迁移学习**：从 `pretrained_fastwam_move_pen` 迁移到 `Insert_The_Cylinder` 任务。

---

## 8. 注意事项

这套脚本是 **AutoDL 云环境专用**（路径写死在 `autodl-tmp` 下）。在本地/其他机器训练时，需改 `AUTODL_WORK_ROOT` 指向实际数据盘，或改用通用 `lerobot-train` 命令（`--policy.type=fastwam --policy.tactile_*`）。
