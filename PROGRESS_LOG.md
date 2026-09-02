# AutoDL 续训执行日志（✅ 续训已启动，2026-09-02 17:08）

> 目标：在云端续训 FastWAM 触觉 checkpoint（15 万步 → 更多步），避免与本机 LingBot 抢 GPU。
> 本文档记录实际执行进度，与 AUTODL_RESUME_GUIDE.md（方案）、AUTODL_RESUME_REPORT.md（完成报告）配套。
>
> **当前状态：五步全部完成，续训运行中。105K → 150K 步，2.84s/step，ETA ~36h（9/4 早）。详见 AUTODL_RESUME_REPORT.md。**

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

```mermaid
flowchart LR
    I1["实例① 端口 51021<br/>A800 · 驱动 590 ✅ · 盘 50G ⚠️"]
    I2["实例② 端口 51635<br/>A800 · 驱动 550 ❌ · 盘 50G ⚠️"]
    I3["实例③ 端口 44252 ✅<br/>A800 · 驱动 580.82 ✅ · 盘 350G ✅"]

    I1 -->|"9/1 22:00 平台侧 SSH 失联<br/>实例消失，代码环境全丢"| I2
    I2 -->|"驱动 &lt; 570.86<br/>带不动 torch cu128"| I3
    style I1 stroke-dasharray: 5 5,opacity:0.6
    style I2 stroke-dasharray: 5 5,opacity:0.6
```

1. ~~端口 51021：驱动 590 ✅ 但数据盘仅 50G；9/1 晚 22 点 SSH 断开，实例消失~~
2. ~~端口 51635：驱动 550 ❌（<570.86，cu128 不达标），数据盘 50G；已弃用~~
3. **端口 44252：全达标，当前使用**（密码每次变，见控制台）

---

## 五步流程进度（✅ 全部完成，2026-09-02 17:17 快照）

| # | 任务 | 大小 | 状态 | 备注 |
|---|---|---|---|---|
| ① | 代码上传 | 310M | ✅ 完成 | GitHub 直连不通（ghfast.top 镜像也超时），改用 `git archive` 打包 scp |
| ② | 环境安装 | ~8G | ✅ 完成 15:16 | torch 2.11.0+cu130 装好，CUDA 冒烟测试通过 |
| ③ | 数据集上传 | 2.9G | ✅ 完成 | `datasets/raw/Tactile_FastWAM_Insert_The_Cylinder` 已就位 |
| ④ | checkpoint last 上传 | 34G | ✅ 完成 | 12G 模型 + 23G 优化器状态，`du -sh` 核对一致 |
| ⑤ | 权重下载 | ~26G | ✅ 完成 15:49 | hf-mirror.com 8MB/s，fastwam_base 12G + Wan2.2 14G + umt5 |
| ⑥ | 续训启动 | — | ✅ **17:08 启动** | `RESUME=1 bash scripts/autodl/train_fastwam_tactile.sh`，GPU 100%，loss 0.26→0.18 |

**任务依赖与关键路径**（三线并行，checkpoint 上传是最长杆）：

```mermaid
flowchart TD
    code["① 代码上传 ✅"]
    env["② 环境安装 🔄<br/>uv + torch 2.11 cu128"]
    data["③ 数据集上传 2.9G ✅"]
    ckpt["④ checkpoint 上传 34G 🔄<br/>12G 模型 + 23G 优化器状态<br/>~2.2MB/s ← 关键路径"]
    weights["⑤ 权重下载 26G ⏳<br/>hf-mirror 8MB/s"]
    verify["数据校验 ⏳<br/>verify_fastwam_dataset.py"]
    train["⑥ RESUME=1 续训 ⏳<br/>从 150k 步接续"]

    code --> env
    env -->|"装完后启动"| weights
    data --> verify
    ckpt --> train
    weights --> train
    verify --> train

    style ckpt stroke-width:3px
    style train stroke-dasharray: 5 5
```

**服务器目录布局**：
- 代码：`/root/autodl-tmp/Multimodal-Tactile-Sensing-for-Embodied-AI/`（venv 在其下 `.venv/`）
- 数据/输出：`/root/autodl-tmp/mosense-lerobot/`（`datasets/raw/...` 与 `outputs/checkpoints/...`）

**本地源**（Data2TB 数据盘，勿动）：

```mermaid
flowchart LR
    subgraph local["本机 Data2TB（/media/mosense/Data2TB）"]
        ds["数据集 2.9G<br/>datasets/raw/Tactile_FastWAM_…"]
        ck["checkpoint last 34G<br/>pretrained_model 12G<br/>training_state 23G"]
    end
    subgraph server["AutoDL 实例（autodl-tmp 350G）"]
        repo["代码仓库<br/>Multimodal-Tactile-…<br/>+.venv 环境"]
        sds["数据集 ✅"]
        sck["checkpoint 🔄"]
        w["HF 权重 ⏳<br/>hf-mirror.com"]
        run["续训 run ⏳"]
    end

    ds -->|"scp 2.2MB/s ✅"| sds
    ck -->|"scp 2.2MB/s 🔄 关键路径"| sck
    hfm["hf-mirror.com<br/>fastwam_base + Wan2.2 + umt5"]
    hfm -->|"8MB/s ⏳"| w
    repo --> run
    sds --> run
    sck --> run
    w --> run
    run -->|"$RESUME=1$ 从 150k 步接续"| run

    style ck stroke-width:2px
    style run stroke-dasharray: 5 5
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

## 下一步（训练完成后，预计 9/4 早上）

1. 确认 150K 完成：`grep 'step:' /root/train.log | tail`，并看 W&B 曲线
2. 下载最终 checkpoint（只需 pretrained_model 12G）
3. 跑 eval 扩展评测（adjust_bottle 5/5 基础上）
4. 清理服务器：删 090k–105k 中间 checkpoint、关机/无卡模式停止计费
5. 收尾更新 AUTODL_RESUME_REPORT.md 与本文档
