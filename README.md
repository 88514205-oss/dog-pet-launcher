# 桌宠启动器 · Modular Pet Launcher

> **当前版本：v2.0.0（模块化 + 像素启动器）**
> 神吞桌宠已重构成「像素风启动器 + 可插拔模块」，神吞是自带的默认模块。
> 启动器是 Undertale 味道：纯黑底、硬边白框、中文像素字、红心光标、打字机文字。

一个可以**随便加桌宠 / 小游戏**的模块化启动器。把文件夹丢进 `pets/` 目录，
启动器就会在列表里扫到它。神吞（神明吞噬者）是自带的默认模块。

---

## 更新记录

### v2.0.0 · 模块化 + 像素启动器
- **重构成模块化启动器**：桌宠逻辑与宿主窗口解耦，模块可任意增删
- **神吞变成模块**：`pets/devourer_of_gods/`，作为默认自带模块
- **新增像素风启动器 UI**（Undertale 风格）：纯黑底、硬边像素框、Zpix 中文像素字、
  红心光标、打字机描述、键盘导航（↑↓ / Enter / R / 1-9 / Esc）
- 加入开源中文像素字体 **Zpix**（`assets/fonts/zpix.ttf`）
- 桌宠宿主新增「打开启动器」入口（悬浮球 / 托盘右键菜单里）

### v1.1.0 · 音乐修正
- **三首 BGM 换成官方原版**（此前误收了 B站的钢琴独奏与短版）：
  `Servants of the Scourge` 5:50 ／ `Scourge of the Universe` 7:38（完整版）／ `Universal Collapse` 4:16
- 新增 **14 个官方音效**：神吞生成/传送、激光墙出现/开火、吞食魔受伤/跳跃/死亡、体节破碎 ×4、紫色光束、笑声、教条激光
- **修复音效完全不响**（`QSoundEffect` 解不了这些 ogg，改 `QMediaPlayer`）
- 新增**鼠标受击**：神吞贴近鼠标会咬一口，爆粒子 + 放官方受击音效
- 修复 **Q版神吞只有半个身子**（`ChibiiDoggoFly` 没设 `projFrames`，80×70 是整张单帧）
- 修复**体节断裂**（段间距实测 30.9~375.8，应恒为 67.2；改用累计弧长 + 二分查找）
- 修复**卡顿**（定时器 16ms→8ms；窗口几何不再每帧 SetWindowPos）
- 新增**设置面板**与**悬浮球**控制球
- 新增**激光网**（官方 `DoGLaserWalls` 复刻）

### v1.0.0
- 初版：两形态、四模式、100 节链式虫体、传送门出场、屏幕外游动

---

## 一、怎么用

双击 `神吞桌宠.exe` 即可，不需要装 Python。

- **悬浮球**（右侧的紫色小圆球）：单击弹出全部控制菜单，按住可拖到任意位置；
  底部小圆点的颜色就是当前模式（青=跟随 / 红=攻击鼠标 / 紫=寻空 / 金=吞噬）
- **拖动宠物**：鼠标按住神吞本体直接拖
- **右键宠物**：同样的控制菜单
- **托盘图标**：同样的菜单，另有"召回宠物到屏幕中央"和"退出"
- 退出请用菜单里的"退出"（桌宠没有标题栏，Alt+F4 当然也行）
- **只允许开一只**：重复双击会提示"神吞已经在桌面上了"，不会再跑出第二只

设置存在 `%APPDATA%\DoGPet\settings.json`（含悬浮球位置），下次启动自动恢复。

---

## 二、两个形态

| 形态 | 说明 | 尺寸 |
|---|---|---|
| **神明吞噬者 · 本体** | 一阶段头 + 100 节体节 + 尾，链式蠕虫（默认） | 每游戏像素 1.5 个物理像素 |
| **Q版神吞 · Chibii Devourer** | 灾厄官方唯一的 DoG 宠物（召唤物：宇宙布偶 Cosmic Plushie） | 每游戏像素 3 个物理像素 |

---

## 三、四种模式

| 模式 | 行为 |
|---|---|
| **跟随** | 沿轨道环绕鼠标，鼠标移动时整条虫跟着平移 |
| **攻击鼠标** | 环绕提速，进入激进阶段后连续冲刺直扑光标 |
| **寻空游动** | 高空巡游，不追鼠标 |
| **吞噬** | 屏幕飘出星体光点，神吞游过去吞掉，**每吞一颗身体变长一节** |

本体形态下三种行为阶段会自动轮转，跟游戏里一样：
**被动（环绕）→ 激进（环绕提速 + 冲刺）→ 激光（激光阵 + 环绕）**，
计时用源码原值 `phaseLimit = 900` 帧（15 秒）/ 激光 `300` 帧（5 秒）。

### 屏幕外游动

神吞**不会被屏幕边缘挡住**：轨道中心可以越出屏幕，鼠标贴边时整条虫会游到屏幕外再绕回来，
就像从屏幕外面钻进来一样。只有跑出 300 逻辑像素以外才会被平滑拉回，**不反弹、不撞墙**。

---

## 四、性能

| 指标 | 数值 |
|---|---|
| 逻辑帧率 | **60 tick/s**（与泰拉瑞亚完全一致，固定步长） |
| 渲染帧率 | **47~60 FPS**（要求 ≥40 FPS，实测本体 100 节 56.4、Q版 59.4） |
| 动画帧率 | 按源码帧计数推进，不随渲染帧率漂移 |

为了达标做了三件事：按体节切脏区重绘、发光层减负、透明窗口按内容贴合。
脏区会把全部拖尾历史位置和粒子范围包进去，所以不会留残影。

---

## 五、代码来源对照表

所有数值都是翻官方仓库抠出来的，不是估的。

### 5.1 Q版形态

| 桌宠行为 | 官方来源 | 复刻的具体数值 |
|---|---|---|
| 地面移动 | `Terraria/Projectile.cs` → `AI_026()` 的 `type == 319`（黑猫）分支 | 加速度 `0.08`、速度上限 `6.5`、`|vx|>3.5` 后加速度 ×`0.25`、无输入摩擦 `×0.9` |
| 跳跃 | 同上，`WorldGen.SolidTile` 判定链 | `-5.1 / -7.1 / -9.1 / -10.1 / -11.1` 五档起跳速度 |
| 重力 | 同上 | `vy += 0.4`，上限 `10` |
| 动画帧语义 | 同上 | `frame 0`=待机、`1`=跳/落、`2..5`=行走、`6..10`=飞行 |
| 行走换帧 | 同上 | `frameCounter += int(|vx|) + 1`，超过 `8` 换帧 |
| 飞行换帧 | 同上 | 每 `6` tick 换帧，帧只取 `6..10` |
| 飞行倾角 | 同上 | `rotation = velocity.X * 0.05` |
| 飞/走切换 | `CalamityMod/Projectiles/Pets/ChibiiDoggo.cs` | 切换时爆 `77` 颗无重力尘，速度 ×1.5，贴图在 `ChibiiDoggo` / `ChibiiDoggoFly` 间换 |
| 拖尾 | `ChibiiDoggo.cs` / `ChibiiDoggoFly.cs` 的 `PreDraw` | 用单色层贴图倒序绘制，`num157`=8（飞 12）、步长 2、透明度 `(num157-i)/(TrailCacheLength*1.5)` |
| 缩放 | `ChibiiDoggo.SetDefaults` | `Projectile.scale = 0.8`，hitbox `38×46`（飞行 `24×46`） |
| 黑暗彩蛋 | `ChibiiDoggo.cs` 的 `notlocalai1` 段 | 上限 `120`、下限 `-3600`、触发阈值 `Main.rand.Next(30,120)`、触发后置 `-600`；会随机播 `Meowmere`/`ScaryScream` 或造成 `500` 伤害 |

### 5.2 本体形态

| 桌宠行为 | 官方来源 | 复刻的具体数值 |
|---|---|---|
| 体节跟随 | `BaseWormNPC.cs` 的 `ExactSegmentLogic` | 记录头部走过的路径点，体节按固定弧长沿路径排布；路径不够长时沿末端切线外推 |
| 段间距 | `DevourerofGodsBody.cs` | `NPC.scale × NPC.width`；Body 的 `NPC.width = 56`（不是贴图宽度），二阶段写死 `80` |
| 体节数量 | `DevourerofGodsHead.cs` | `minLength = 100`、`maxLength = 101` → 桌宠取 **100 节** |
| 头部转向 | `DevourerofGodsHead.cs` 第 1674~1752 行 | `turnSpeedCopy *= Distance / 1000`；同向/反向两套分支、`×1.1` 与 `×2` 过冲补偿全部照搬 |
| 转向速度 | 同上 | `turnSpeed = 0.3`（死亡 `0.33`），增幅 `+0.06×(1-(lifeRatio×0.75+0.25))` |
| 追踪速度 | 同上 | `homingSpeed = 24`（死亡 `30`），增幅 `+12×…` |
| 冲刺速度 | 同上 | `chargeVelocity = 20`（专家 22 / 复仇 24 / 死亡 26），再 `×2.25` |
| 冲刺距离 | 同上 | `maxChargeDistance = 1800`，冲完 `postTeleportTimer = 1800 / chargeVelocity` |
| 三态循环 | 同上 | `phaseLimit = 900`、`idleCounterMax = 300`、激光 `300` 帧、距离超过 `150 tiles` 强制切激进 |
| 头部尺寸 | 同上 | Head `NPC.width/height = 104` |
| 传送门出场 | `DoGTeleportRift.cs` / `DoGBeamPortal.png` | 先开裂缝再从中钻出，出场用一段直冲把虫身抽出来 |
| **激光网（弹幕网）** | `Projectiles/Boss/DoGLaserWalls.cs` | `laserCount = 6000/laserDist`、`laserLength = laserDist*count/2`、`attackTime = 30`、`attackSpeed = 0.5`、开火瞬间 `laserFX = 3`、`storedTime+10` 帧后消失、颜色 `Lerp(Cyan, Magenta, LerpValue²)`、六种阵型 `laserType 0~5`（含 +45°/十字/斜向交叉），全部照抄 |

### 5.3 音效

音效**全部取自灾厄维基的官方 ogg**（`assets/sfx/`），对应游戏里的 SoundStyle 位置：

| 时机 | 音效文件 | 官方对应 |
|---|---|---|
| 传送门出场 | `dog_spawn.ogg` + `dog_teleport.ogg` | 神吞生成 / 神吞传送 |
| 激光网展开 | `dog_laserwall_spawn.ogg` | `DoGLaserWallSpawn` |
| 激光网开火 | `dog_laserwall_fire.ogg` | `DoGLaserWallLightAttack` |
| **咬到鼠标（受击）** | `dog_hurt.ogg` + 随机 `dog_seg1~4.ogg` | 吞食魔受伤 / 体节破碎 |
| 冲刺 | `dog_jump.ogg` | 吞食魔跳跃 |
| 激光阶段 | `dog_beam.ogg` | 神吞紫色光束 |
| 吞噬 | `dog_death.ogg` | 吞食魔死亡 |
| 平时随机 | `DoGLaugh.ogg` / `dog_hurt` / `dog_jump` | 神吞笑声等 |

> **坑**：这些 ogg 用 `QSoundEffect` 全部解码失败（只在控制台静默报错，音效根本不响），
> 已一律改用 `QMediaPlayer`（走 FFmpeg）。player 是懒加载 + 预热，第一次播到才建。

**鼠标受击**：神吞头贴近鼠标到 `56 × scale` 内就会咬一口 —— 在鼠标位置爆粒子 + 播受击音效，
冷却 58 帧。Q版形态的判定距离是 `38 × scale`。

**音乐**：右键神吞或点悬浮球 →「🎵 音乐」，或打开设置面板的「音乐」区。

三首主题曲槽位按文件名关键词自动对号入座，曲名写成什么样都能认：

| 槽位 | 文件名命中关键词 |
|---|---|
| 灾祸之仆 | `chaos` / `servant` |
| 寰宇灾劫 | `cosmic` / `disgust` / `calamity` |
| 寰宇破碎 | `collapse` / `universe` / `reality` / `break` |

把 `.ogg/.mp3/.wav` 丢进 `assets/music/` 即可。**该目录为空时，桌宠会自动去读
Terraria 的音乐缓存** `%USERPROFILE%\Documents\My Games\Terraria\tModLoader\TrackedMusic\`
——tModLoader 会把游戏里播放过的音乐缓存到那里，所以进游戏打一次神明吞噬者就能拿到它的曲子。

### 5.3 屏幕外游动

源码里 NPC 没有"屏幕边界"这个概念，所以桌宠也**不设硬墙**：
头部可以越过屏幕边缘继续游、虫身常常大部分延展在屏幕外，
只有真的跑丢（离屏幕 1600px 以上）才会瞬移回来或开传送门重来。
**撞到屏幕边缘不会被弹开**。

### 5.3 素材

全部来自桌面上的官方资源包（`CalamityTeam/CalamityModPublic`，1.4-release / v1.4.4 / v2.0.7.2）：

- `assets/chibii/` — ChibiiDoggo 11 帧、单色层、飞行 2 帧、Buff 图标、宇宙布偶
- `assets/dog/phase1|phase2/` — 头 / 身 / 尾 + Glow 发光遮罩
- `assets/dog/projectiles/` — DoGBeam / DoGFire / DoGBeamPortal / DoGDeath
- `assets/sfx/` — DoGLaugh.ogg、DogmaLasersFire.ogg

---

## 六、目录

```
DoGPet/
├─ 神吞桌宠.exe          ← 双击运行
├─ src/
│   ├─ main.py           入口（--selftest 可无交互自检）
│   └─ dogpet/
│       ├─ config.py     ★ 所有游戏参数的原值总表
│       ├─ ai_pet.py     Q版：AI_026 + ChibiiDoggo 复刻
│       ├─ ai_worm.py    本体：头部行为 + 链式体节
│       ├─ modes.py      四种模式
│       ├─ window.py     透明置顶窗口 / 主循环 / 托盘
│       ├─ fx.py         尘埃、拖尾、发光、激光
│       ├─ world.py      屏幕几何、鼠标、实心判定
│       └─ vec.py        XNA Vector2 复刻
├─ tools/                自检脚本（性能 / 抖动 / 几何 / 素材探针）
├─ preview/              预览图
└─ assets/               官方素材
```

### 自检命令

```powershell
python src\main.py --selftest 300 --form dog --mode follow   # 跑 300 帧看输出
python tools\perf.py dog 1.5 follow                          # 分项耗时
python tools\jitter.py 1.5 follow                            # 抖动量化
python tools\diag.py dog 1.5 follow --edge                    # 几何 + 越界检查
```

`tools/jitter.py` 当前结果：速度恒定 15.84 px/tick、|Δv| 最大 0.05、体节越界 0/900 帧。

---

## 七、与源码的两处有意偏差

为了桌面观感，只有两处没有照抄，都写在代码注释里：

1. **贴脸转向下限**：源码 `turnSpeedCopy *= Distance / 1000`，贴脸时转向力趋近 0 会让虫头停住发抖；
   桌宠加了 `clamp(0.28~1.0)` 的下限，并在 34px 内平滑收速停住。
2. **出场演出**：从传送门钻出后有一段强制直冲（把虫身从门里抽出来），
   这段不受追踪目标控制；演出一结束立刻回到源码追踪逻辑。

其余（移动、转向、冲刺、三态计时、体节弧长排布、段间距、段数）全部是源码原值。

### 已修掉的坑（留给以后查）

- **体节断裂**：段间距实测在 30.9~375.8 之间跳（应为恒定 67.2），根因是路径累积弧长的
  游标写法有偏差；换成「累计弧长数组 + 二分查找」后中位=最大=67.2，零断裂。
- **卡顿**：定时器 16ms 与 60Hz 逻辑步长（16.67ms）不同步，会出现"有时不画、有时突击"；
  改成 8ms。另外窗口几何每帧 SetWindowPos + 全窗重绘也卡，改成只在装不下时才扩、几乎不收缩。
- **缩成一团**：`set_scale` 里误用了螺旋初始化，每次改大小都把虫身揉成球；已改为直线铺开。
  路径不够长时体节沿末端切线外推，保证虫身始终是长蛇。
