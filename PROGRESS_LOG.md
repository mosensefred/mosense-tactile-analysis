# AutoDL 续训执行日志（进行中）

> 目标：在云端续训 FastWAM 触觉 checkpoint（15 万步 → 更多步），避免与本机 LingBot 抢 GPU。
> 本文档记录实际执行进度，与 AUTODL_RESUME_GUIDE.md（方案）配套。

---

## 当前服务器（第 3 台，最终版）✅

```
ssh -p 44252 root@connect.nma1.seetacloud.com   # 免密已配置
```

| 项 | 值 | 达标 |
|---|---|---|
| GPU | A800 80GB PCIe | ✅ |
| 驱动 | 580.82.07（≥570.86）| ✅ cu128 可用 |
| 数据盘 | **350G**（/root/autodl-tmp）| ✅ 充裕 |
| 内存/CPU | 1007G / 112 核 | ✅ |
| 镜像 | miniconda3 + Python 3.12.3 + torch 2.5.1+cu124（base）| setup 脚本会另建 venv 装 torch 2.11 |

**实例更换历史**（SeetaCloud 每次重开机换端口换密码，root@connect.nma1.seetacloud.com 不变）：
1. ~~端口 51021：驱动 590 ✅ 但数据盘仅 50G；9/1 晚 22 点 SSH 断开，实例消失~~
2. ~~端口 51635：驱动 550 ❌（<570.86，cu128 不达标），数据盘 50G；已弃用~~
3. **端口 44252：全达标，当前使用**（密码每次变，见控制台）

---

## 五步流程进度（2026-09-02 更新）

| # | 任务 | 大小 | 状态 | 备注 |
|---|---|---|---|---|
| ① | 代码上传 | 310M | ✅ 完成 | GitHub 直连不通（ghfast.top 镜像也超时），改用 `git archive` 打包 scp |
| ② | 环境安装 | ~8G | 🔄 进行中 | `setup_fastwam_autodl.sh` nohup 后台跑，log `/root/setup.log`；uv 已装好，正在下 torch 2.11 (530M)，速度 ~1.7MB/s |
| ③ | 数据集上传 | 2.9G | ✅ 完成 | `datasets/raw/Tactile_FastWAM_Insert_The_Cylinder` 已就位 |
| ④ | checkpoint last 上传 | 34G | 🔄 进行中 | scp 后台跑（12G 模型 + 23G 优化器状态），速度 ~2.2MB/s，预计 ~4h；坑：目录必须带 `-r` |
| ⑤ | 权重下载 | ~26G | ⏳ 待启动 | 等环境装完跑 `prepare_fastwam_models.sh`，走 hf-mirror.com（实测 8MB/s）|
| ⑥ | 续训启动 | — | ⏳ 待启动 | `RESUME=1 bash scripts/autodl/train_fastwam_tactile.sh` |

**服务器目录布局**：
- 代码：`/root/autodl-tmp/Multimodal-Tactile-Sensing-for-Embodied-AI/`（venv 在其下 `.venv/`）
- 数据/输出：`/root/autodl-tmp/mosense-lerobot/`（`datasets/raw/...` 与 `outputs/checkpoints/...`）

**本地源**（Data2TB 数据盘，勿动）：
```
/media/mosense/Data2TB/Projects/Mosense-LeRobot-Tactile/
├── datasets/raw/Tactile_FastWAM_Insert_The_Cylinder          # 2.9G
└── outputs/checkpoints/Tactile_FastWAM_Insert_The_Cylinder_h10_b8_s150000/
    └── checkpoints/last/{pretrained_model 12G, training_state 23G}
```

---

## 关键坑与经验

1. **SeetaCloud 实例不稳定**：第一台一晚上 SSH 就没了（平台侧问题），代码/环境全丢。务必 **nohup + setsid** 在服务器本地跑长任务；关键进度本地留档。
2. **每台实例密码不同**：旧密码不能复用，新实例要重新装免密公钥（本地 `~/.ssh/id_ed25519.pub`）。
3. **GitHub 服务器直连不通**：连镜像也不稳。代码用 `git archive HEAD` 打 tar.gz（310M，不含 .git）scp 上去最快。
4. **scp 目录必须 `-r`**：传 checkpoint 目录忘了 `-r` 会报 "not a regular file"。
5. **pip 阿里云源速度看实例**：第一台 130KB/s，这台 1.7MB/s——慢别急着换源，先实测。
6. **hf-mirror 权重下载**：resolve 大文件会 302 到 us.aws.cdn.hf.co（xet CDN），实测 8MB/s，26G 约 1h。
7. **驱动是硬门槛**：torch cu128 需驱动 ≥570.86。第二台 550 驱动直接不合格，选实例先看驱动版本。
8. **checkpoint 结构**：每个 step 目录 = pretrained_model(12G) + training_state(23G) 共 34G；`last` 是指向 step 目录的软链接；续训必须带 training_state（优化器状态）。

---

## 训练参数备忘（train_fastwam_tactile.sh 默认值）

- RUN_NAME：`Tactile_FastWAM_Insert_The_Cylinder_h10_b8_s150000`（上传目录名必须与之一致才能 RESUME 找到）
- SAVE_FREQ=5000（每 5 千步存 34G，350G 盘约可存 9 个，注意清理）
- 续训：`RESUME=1`，从 `last/pretrained_model/train_config.json` 读配置，`--resume=true` 接着 15 万步往上训

## 下一步（环境装完后）

1. 跑 `prepare_fastwam_models.sh` 下 26G 权重（HF_ENDPOINT=https://hf-mirror.com）
2. 跑 `verify_fastwam_dataset.py` 校验数据集完整性
3. 等 checkpoint 传完 → 确认 `du -sh` 对得上 34G
4. `RESUME=1 bash scripts/autodl/train_fastwam_tactile.sh` 起训（同样 nohup 保护）
