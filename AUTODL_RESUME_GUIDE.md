# FastWAM 触觉训练 AutoDL 续训方案

> 目标：在 AutoDL 上续训之前跑完 15 万步的 FastWAM 触觉 checkpoint（`Tactile_FastWAM_Insert_The_Cylinder_h10_b8_s150000`）。
> 本地数据/权重/checkpoint 都在 Data2TB 数据盘，无需重新下载。

---

## 1. 服务器选型

| 项 | 要求 |
|---|---|
| GPU | A100-80G（或 H100-80G）|
| **NVIDIA 驱动** | **≥ 570.86**（cu128 硬门槛）|
| CUDA | 12.8（cu128）|
| Python | 3.12 |
| PyTorch | 2.7 ~ 2.11（建议 2.9+，cu128）|
| 系统 | Ubuntu 22.04（AutoDL 基础镜像）|
| 数据盘 | 200–300GB |

> 环境不用手动装，项目自带 `setup_fastwam_autodl.sh` 会自动配（复用 AutoDL base torch 或用 uv 装 Python 3.12 + torch cu128）。

---

## 2. 本地资源位置（Data2TB 数据盘）

数据盘挂载在 **`/media/mosense/Data2TB`**（注意不是 `/mnt`），兄弟项目：

```
/media/mosense/Data2TB/Projects/Mosense-LeRobot-Tactile/
├── datasets/raw/Tactile_FastWAM_Insert_The_Cylinder      # 数据集（2.9G）
└── outputs/checkpoints/
    ├── huggingface-cache/hub/
    │   ├── models--lerobot--fastwam_base                  # 预训练权重（12G）
    │   ├── models--Wan-AI--Wan2.2-TI2V-5B-Diffusers       # Wan 2.2 基座（14G）
    │   └── models--google--umt5-xxl                       # 文本编码器
    └── Tactile_FastWAM_Insert_The_Cylinder_h10_b8_s150000 # 已训 checkpoint（135G）
```

---

## 3. 搬运清单

| 内容 | 大小 | 方式 |
|---|---|---|
| checkpoint `last`（`pretrained_model` 12G + `training_state` 23G）| 35G | scp 上传 |
| 数据集 `Insert_Cylinder` | 2.9G | scp 上传 |
| 权重（fastwam_base + Wan2.2 + umt5）| ~26G | **HF 加速下载**（不用传）|
| 代码 | — | git clone |

> 续训只需搬 `last`（35G），中间 checkpoint（090k–105k，101G）是历史存档，不用搬。
> `training_state`（23G）必须搬——含优化器状态，否则无法恢复续训。

---

## 4. 操作步骤

```bash
# ① AutoDL 上拉代码
git clone https://github.com/MoSenseHK/Multimodal-Tactile-Sensing-for-Embodied-AI.git
cd Multimodal-Tactile-Sensing-for-Embodied-AI

# ② 下载权重（AutoDL HF 加速，含 fastwam_base + Wan2.2 + umt5）
bash scripts/autodl/setup_fastwam_autodl.sh
bash scripts/autodl/prepare_fastwam_models.sh

# ③ 上传数据集 + checkpoint last（本地执行）
scp -r -P <port> /media/mosense/Data2TB/Projects/Mosense-LeRobot-Tactile/datasets/raw/Tactile_FastWAM_Insert_The_Cylinder \
  root@<autodl-host>:~/autodl-tmp/mosense-lerobot/datasets/raw/

scp -r -P <port> /media/mosense/Data2TB/Projects/Mosense-LeRobot-Tactile/outputs/checkpoints/Tactile_FastWAM_Insert_The_Cylinder_h10_b8_s150000/checkpoints/last \
  root@<autodl-host>:~/autodl-tmp/mosense-lerobot/outputs/checkpoints/Tactile_FastWAM_Insert_The_Cylinder_h10_b8_s150000/checkpoints/

# ④ 续训
RESUME=1 bash scripts/autodl/train_fastwam_tactile.sh
```

---

## 5. 续训机制

- 脚本 `RESUME=1` 时读 `last/pretrained_model/train_config.json` 恢复配置，`--resume=true` 从 15 万步继续往上加；
- **注意**：上传目录名必须和脚本生成的 `RUN_NAME` 一致，否则找不到 checkpoint；可手动指定 `RUN_NAME` 环境变量对齐。

---

## 6. 关键版本依赖（pyproject.toml）

- Python `>=3.12`
- `torch>=2.7,<2.12.0` + `torchvision>=0.22.0,<0.27.0`（cu128 索引）
- CUDA 12.8，驱动 ≥ 570.86
- 其余：draccus、huggingface-hub、transformers、diffusers
