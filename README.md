# 快跳守护 · autoskip_guard

给 [快跳 AutoSkip](https://github.com/pxlwjp0425/autoskip) 兜底的 KernelSU / Magisk 模块。

快跳是一个**纯无障碍服务**的跳过开屏广告工具。麻烦出在这儿：HyperOS / MIUI 上被「一键清理」或
`force-stop` 之后，系统会**连带把无障碍开关记录一起清掉**，服务就此下线，
得手动回设置里重新勾选才恢复。

本模块就是一个常驻 shell 守护，专门盯这件事 —— 坏了自动修回来。

| 实测项 | 结果 |
| --- | --- |
| `force-stop` → 完全恢复 | **十几秒**（实测 10~17 秒，取决于落在轮询周期的哪个位置） |
| 重启后自动接管 | 开机约 40 秒后全链路恢复，无需任何手动干预 |
| 守护自己会不会被回收 | 不会 —— 自身也锁 `oom_score_adj = -1000` |
| 会不会起出两个守护 | 不会 —— 单实例锁 |

---

## 一、它到底做了什么

主循环每 **20 秒**看一眼，**只在真的坏了的时候才动手**：

| 症状 | 动作 |
| --- | --- |
| 无障碍开关记录里已经没有快跳 | 把快跳那一段从列表里摘掉再写回去，逼系统走一遍 `updateServices` 重新绑定 |
| 快跳进程不在了 | `am start-foreground-service -n com.laopeng.autoskip/.GuardService` 静默拉起（不弹界面） |
| 进程在但服务没绑定上 | 同上，强制重连 |
| 内存优先级被系统改回去 | 重新写 `-1000`（连守护自己一起） |
| 模块目录被删掉 | 认为用户关掉了 root 增强，清掉锁文件后自行退出 |

开机时还会做一次加固：放开 `ACCESS_RESTRICTED_SETTINGS` / `RUN_ANY_IN_BACKGROUND` / `WAKE_LOCK`
三个 appop，并把快跳加进 `dumpsys deviceidle whitelist`。

### 为什么是「只在坏了的时候才动手」

`settings put secure enabled_accessibility_services` 会让系统**重新绑定**无障碍服务，
中间有几百毫秒的闪断。正常状态下每 20 秒无脑写一遍，反而比不写更不稳。

所以健康的那一轮只做两件不痛不痒的事：看一眼开关、锁一下内存优先级。**一次设置都不碰。**

### rebind 只动自己那一段

写回开关列表时，先把快跳自己的条目摘掉、剩下的原样保留再拼回去 ——
所以机器上同时装着 GKD、TalkBack 之类的无障碍服务不会被殃及。

---

## 二、安装

### 方式一：从快跳 App 里装（推荐）

快跳 → 设置 → **root 增强** → 开启。

App 会自己把模块写进 `/data/adb/modules/autoskip_guard/` 并**立刻启动一次，不用重启**。

> 这条路径的模块内容内嵌在 App 里（`GuardModule.java` 的三个模板常量），
> 本仓库是同一份内容的独立发布口。**改脚本要两边同步**，以 App 侧模板为准。

### 方式二：手动刷 zip

从 [Releases](https://github.com/pxlwjp0425/autoskip_guard/releases) 下载
`autoskip_guard-v1.1.zip`：

- KernelSU 管理器 → 模块 → 从本地安装；
- 或命令行：`ksud module install autoskip_guard-v1.1.zip`。

**⚠️ 手动刷入后要重启** —— 开机脚本 `service.sh` 只在 `late_start` 阶段执行一次。

不想重启就先手动拉起来：

```bash
su
nohup sh /data/adb/modules/autoskip_guard/bin/guard.sh </dev/null >/dev/null 2>&1 &
```

---

## 三、验证

```bash
su

# 1) 模块在不在
ls /data/adb/modules/autoskip_guard/

# 2) 守护进程（正常恰好 1 个）
pgrep -af 'autoskip_guard/bin/guard.sh'

# 3) 守护自己的内存优先级（应为 -1000）
cat /proc/$(pgrep -f 'autoskip_guard/bin/guard.sh' | head -1)/oom_score_adj

# 4) 快跳的内存优先级（应为 -1000）
for p in $(pidof com.laopeng.autoskip); do cat /proc/$p/oom_score_adj; done

# 5) 无障碍开关记录里有没有快跳
settings get secure enabled_accessibility_services

# 6) 日志
tail -20 /data/adb/autoskip_guard.log
```

**日志正常时是安静的** —— 只在真的修过什么的时候才会多一行。
如果它每隔 20 秒刷一条，说明有东西在反复破坏状态，那才是要查的问题。

只做语法检查（不起进程）：

```bash
su
sh -n /data/adb/modules/autoskip_guard/service.sh
sh -n /data/adb/modules/autoskip_guard/bin/guard.sh
```

---

## 四、卸载

KernelSU 管理器里删掉模块，或：

```bash
su
ksud module uninstall autoskip_guard
```

**不影响快跳本体** —— 快跳照常跳过广告，只是不再有自动修复：
开关记录再被系统清掉时，得手动回设置里重新勾选。

卸载时 `uninstall.sh` 会停掉守护、清掉日志与锁文件，并把快跳的 `oom_score_adj` 恢复成 `0`。

---

## 五、目录结构

```
autoskip_guard/
├── module.prop        模块描述，KernelSU 管理器据此识别
├── service.sh         开机 late_start 阶段跑一次，把守护挂到后台
├── uninstall.sh       卸载时清理
├── bin/
│   └── guard.sh       真正干活的长驻循环
├── pack.py            打包成可刷入的 zip
└── README.md
```

运行期产生的文件（不在本目录）：

| 路径 | 用途 |
| --- | --- |
| `/data/adb/modules/autoskip_guard/` | 模块安装位置 |
| `/data/adb/autoskip_guard.log` | 日志，超过 300 行自动压到 120 行 |
| `/data/adb/autoskip_guard.lock` | 单实例锁，存守护自己的 pid |

### 打包

```bash
python pack.py     # 产出 autoskip_guard-v1.1.zip（顶层直接是 module.prop）
```

---

## 六、边界与已知限制

- **本模块是「事后修复」，不是「预防」。** 真想让它不被一键清理掉，唯一的办法是
  在最近任务卡片里**下拉 → 点锁头**（这步系统没给命令接口，只能手点）。
  两者配合才完整。
- 模块靠包名 `com.laopeng.autoskip` 定位目标，**没装快跳时它什么都不做**（找不到进程就空转）。
- > **`oom_score_adj = -1000` 只对内核的 LMK 有效** —— 用户层的「一键清理」和 `force-stop`
  不看这个值。所以进程还是会被杀，靠的是杀完之后再拉起来。
- 只在**已 root** 的设备上有意义（KernelSU 实测通过，含内置 LKM）。
- 手动刷 zip 之后**必须重启**，否则守护不会自己起来（见上面方式二）。
- Magisk 的 `module.prop` / `service.sh` / `uninstall.sh` 规范与此相同，理论可用，但**未实测**。

---

## 七、版本

| 版本 | 变更 |
| --- | --- |
| **v1.1** | 新增单实例锁；守护自身也锁 oom；`MODDIR` 改为自适应路径（兼容首次安装落在 `modules_update/`）；退出时清锁文件 |
| v1.0 | 首版：开关记录补回、进程静默拉起、服务强制重连、内存优先级锁定 |

> 发布包里的 `bin/guard.sh` 是 `3903 字节 / md5 前缀 6123fcee`。
> 设备上实测跑过的 v1.1 是 `3798 字节 / 42d83e0b`，两个版本**只差注释**
> （多两行说明、去掉两处 `──` 装饰），功能完全一致 —— 这里以 App 侧模板为准，保持两边同源。

---

## 八、许可

暂未附带 `LICENSE` 文件 —— 默认**保留所有权利**（All Rights Reserved），即未授予他人任何使用许可。

本模块内容（shell 脚本 + 模块描述）**全部是原创**，不含任何第三方代码或数据，
不存在 [快跳主仓库](https://github.com/pxlwjp0425/autoskip) 里那种规则数据授权问题。

请仅用于提升个人设备的日常使用体验，不要用于刷量、外挂、爬取等用途。
