"""神吞桌面宠物 · 游戏参数总表

所有数值直接取自官方源码，来源标注在每节注释里。
"""

APP_NAME = "神吞桌宠"
APP_ID = "Baitang.DoGPet"
VERSION = "1.1.0"

# ===========================================================================
# 一、原版 Terraria 宠物 AI（aiStyle 26 / ProjAIStyleID.Pet）
#     实测目标：Projectile type 319「Black Cat」——ChibiiDevourer 通过
#     ChibiiDoggo.PreAI() 把 type 伪装成 319 来借用这套 AI。
#     来源：Terraria 1.4.x 反编译 Projectile.AI_026()
# ===========================================================================

PET_TICK_HZ = 60.0            # Terraria 逻辑帧率：60 ticks / second

PET_ACCEL = 0.08              # num162：水平加速度
PET_MAX_SPEED = 6.5           # num163：水平速度上限
PET_TURN_THRESHOLD = 3.5      # |vx| 超过 3.5 后加速度衰减为 0.25 倍
PET_TURN_FALLOFF = 0.25       # 衰减系数
PET_FRICTION = 0.9            # 无方向输入时 velocity.X *= 0.9
PET_STOP_EPS = PET_ACCEL      # |vx| <= accel 时归零

PET_GRAVITY = 0.4             # velocity.Y += 0.4（地面宠物）
PET_MAX_FALL = 10.0           # velocity.Y 上限

PET_NEAR_DIST = 85            # num3 默认：宠物与玩家水平死区基准
PET_DEADZONE = 5.0            # 目标在 ±5px 内不产生方向输入

# 撞墙起跳速度表（WorldGen.SolidTile 判定链，自上而下取第一个命中）
PET_JUMP_TABLE = (
    (1, -5.1),                # 前方 1~2 格无实心块
    (2, -7.1),                # 前方 2 格无实心块
    (5, -11.1),               # 前方 5 格实心
    (4, -10.1),               # 前方 4 格实心
)
PET_JUMP_DEFAULT = -9.1       # 兜底跳跃速度
PET_WALL_LOOKAHEAD = 1        # 撞墙检测偏移格数

# 动画：帧索引语义（type 319 专属分支）
#   frame 0     : 原地待机（落地静止）
#   frame 1     : 跳跃 / 下落中
#   frame 2..5  : 行走循环
#   frame 6..10 : 飞行循环
PET_FRAME_IDLE = 0
PET_FRAME_JUMP = 1
PET_WALK_RANGE = (2, 5)
PET_FLY_RANGE = (6, 10)

PET_LAND_VY_MAX = 0.8         # 判定「贴地」的竖直速度上限
PET_WALK_VX_MIN = 0.8         # 判定「移动中」的水平速度阈值
PET_WALK_FRAME_GATE = 8       # frameCounter += |vx| + 1，超过 8 换帧
PET_FLY_FRAME_GATE = 6        # 飞行每 6 tick 换一帧
PET_FLY_ROT_FACTOR = 0.05     # rotation = velocity.X * 0.05

PET_TELEPORT_DIST = 2000.0    # 超出后直接传送到目标身边

# ===========================================================================
# 二、Calamity · Chibii Devourer（Q 版宠物）
#     来源：CalamityModPublic / Projectiles/Pets/ChibiiDoggo.cs
#           CalamityModPublic / Projectiles/Pets/ChibiiDoggoFly.cs
#           CalamityModPublic / Projectiles/Pets/CosmicPlushie.cs
# ===========================================================================

CHIBII_FRAMES = 11            # Main.projFrames = 11
CHIBII_HITBOX = (38, 46)      # ChibiiDoggo 本体 hitbox
CHIBII_FLY_HITBOX = (24, 46)  # ChibiiDoggoFly hitbox
CHIBII_FRAME_SIZE = (38, 44)  # 贴图单帧 38 x 484 / 11
CHIBII_FLY_FRAME_SIZE = (80, 70)
# ChibiiDoggoFly.cs 的 SetStaticDefaults 没有设置 Main.projFrames，
# 所以飞行贴图是「整张单帧」，切两帧只会得到半个身子。
CHIBII_FLY_FRAMES = 1
CHIBII_SCALE = 0.8            # Projectile.scale = 0.8

TRAIL_LAND_LEN = 10           # TrailCacheLength = 10
TRAIL_FLY_LEN = 12            # ChibiiDoggoFly TrailCacheLength = 12
TRAIL_ALPHA_DIV = 1.5         # color *= (num157 - i) / (TrailCacheLength * 1.5)
TRAIL_LAND_START = 8          # num157
TRAIL_FLY_START = 12
TRAIL_STEP = 2                # num158

STATE_SWITCH_DUST = 77        # 陆地/飞行切换时爆出的尘埃数

# 黑暗彩蛋（ChibiiDoggo.AI 的 companion cube 段）
EASTER_DARK_LIGHT = 0.15      # 光照向量长度阈值
EASTER_DARK_MAX = 120.0       # notlocalai1 上限
EASTER_DARK_MIN = -3600.0     # notlocalai1 下限
EASTER_TRIGGER_MIN = 30       # Main.rand.Next(30, 120)
EASTER_TRIGGER_MAX = 120
EASTER_COOLDOWN = -600.0      # 触发后 notlocalai1 = -600
EASTER_STAB_DAMAGE = 500      # player.Hurt(..., 500, ...)

# ===========================================================================
# 三、Calamity · 神明吞噬者本体（蠕虫链式跟随）
#     来源：CalamityModPublic / NPCs/DevourerofGods/DevourerofGodsHead.cs
#           CalamityModPublic / NPCs/BaseWormNPC.cs
# ===========================================================================

DOG_TURN_SPEED = 0.3          # turnSpeed 基础值（死亡 0.33）
DOG_HOMING_SPEED = 24.0       # homingSpeed 基础值（死亡 30）
DOG_CHARGE_VELOCITY = 20.0    # chargeVelocity 基础值（专家 22 / 复仇 24 / 死亡 26）
DOG_SEGMENT_VELOCITY = 16.0   # segmentVelocity 基础值（死亡 17.5）
DOG_CHARGE_DIST = 1800.0      # maxChargeDistance（源码实测 1800f）
DOG_LIFE_SCALING = 12.0       # 追踪速度增幅：12 * (1 - (lifeRatio*0.75 + 0.25))
DOG_TURN_SCALING = 0.06       # 转向增幅：0.06 * (1 - (lifeRatio*0.75 + 0.25))
DOG_SEG_VEL_SCALING = 4.0     # 段速增幅：4 * (1 - (lifeRatio*0.75 + 0.25))
DOG_IDLE_COUNTER = 300        # idleCounterMax
DOG_CHARGE_MULT = 2.25        # chargeVelocity *= 2.25（非死亡模式）

DOG_PHASE_PASSIVE = 900       # 被动阶段 15s
DOG_PHASE_AGGRESSIVE = 900    # 激进阶段 15s
DOG_PHASE_LASER = 300         # 激光阶段 5s
DOG_CATCHUP_DIST = 2400.0     # 150 tiles：超出后强制切激进
DOG_PHASE_MIN = 180           # phaseLimit 下限

DOG_SEGMENT_MIN = 100         # minLength（源码实测）
DOG_SEGMENT_MAX = 101         # maxLength（源码实测）
DOG_SEGMENT_RIGIDITY = 0.08   # DevourerofGodsBody.cs：WrapAngle 差 * 0.08f
DOG_SEGMENT_ANGLE_LERP = 0.25 # BaseWormNPC.RegularSegmentLogic 角度插值系数
DOG_SEGMENT_SPACING = 56.0    # 段间距 = NPC.scale * NPC.width（Body NPC.width = 104? 否，56）
DOG_SEGMENT_SPACING_P2 = 80.0 # 二阶段：源码写死 NPC.scale * 80
DOG_HEAD_HITBOX = 104         # Head NPC.width / height
DOG_BODY_HITBOX = 56          # Body NPC.width / height
DOG_SEGMENT_COUNT = 100       # 桌宠取 minLength~maxLength 区间：100 节
DOG_SEGMENT_TRAIL_DESKTOP = 100

# 脏区：体节矩形合并阈值与最小外扩（逻辑像素）
REGION_MERGE_FACTOR = 1.10
REGION_PAD = 12
GLOW_SEGMENTS = 8             # 只给头尾附近体节叠发光层，控制 plus 混合开销

DOG_P1_SCALE = 0.42           # 一阶段贴图缩放（106x120 头）
DOG_P2_SCALE = 0.34           # 二阶段贴图缩放（134x196 头）

DOG_LASER_VELOCITY = 5.0      # laserVelocity
DOG_LASER_ACTIVE = 240        # FireLaserWalls 300 帧内约 4 秒开火
DOG_TAIL_IFRAME = 720         # 尾巴 720 帧无敌

# ===========================================================================
# 四、桌宠运行时
# ===========================================================================

RENDER_FPS = 60               # 渲染帧率（要求 >= 40）
RENDER_MS = 8                 # 定时器周期：取半个逻辑步长，保证每 tick 都能及时上屏不跳帧
ANIM_SPEED_SCALE = 1.0        # 动画速度倍率（1.0 = 与游戏一致）

WINDOW_PADDING = 48           # 跟随窗口的额外边距
WINDOW_MIN_SIZE = (140, 140)

TRAY_NAME = "神吞桌宠"

MODE_FOLLOW = "follow"
MODE_HUNT = "hunt"
MODE_SKY = "sky"
MODE_DEVOUR = "devour"

MODE_LABELS = {
    MODE_FOLLOW: "跟随",
    MODE_HUNT: "攻击鼠标",
    MODE_SKY: "寻空游动",
    MODE_DEVOUR: "吞噬",
}

FORM_CHIBII = "chibii"
FORM_DOG = "dog"

FORM_LABELS = {
    FORM_CHIBII: "Q版神吞 · Chibii Devourer",
    FORM_DOG: "神明吞噬者 · 本体",
}

# 尺寸：数值 = 每个游戏像素占多少物理像素（整数比 → 像素完美不糊）
SIZE_OPTIONS = {
    FORM_CHIBII: (("小 2x", 2.0), ("中 3x", 3.0), ("大 4x", 4.0), ("特大 6x", 6.0)),
    FORM_DOG: (("小 1x", 1.0), ("中 1.5x", 1.5), ("大 2x", 2.0), ("特大 3x", 3.0)),
}
DOG_DEFAULT_SCALE = 1.5

ANIM_OPTIONS = (("游戏原速 1x", 1.0), ("2x", 2.0), ("3x", 3.0))
