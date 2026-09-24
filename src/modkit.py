"""桌宠模块系统：扫描 / 加载 / 生命周期。

模块放在 pets/<id>/ 下，一个模块 = 一个文件夹：

    pets/devourer_of_gods/
        pet.json     清单（名称、作者、版本、类型……）
        module.py    实现，必须提供 create(host)
        icon.png     可选，启动器里显示的图标

模块作者只要实现两个方法就能跑：

    def create(host):
        return MyPet(host)

    class MyPet:
        def update(self, ticks): ...     # 每 tick 调用（60 tick/s）
        def draw(self, painter): ...     # 每帧绘制，painter 已按屏幕坐标平移
        # 以下可选
        def recenter(self): ...          # 菜单里"召回"按钮
        def detach(self): ...            # 被卸载时清理
"""

import importlib.util
import json
import os
import sys
import traceback

MANIFEST = "pet.json"
DEFAULT_ENTRY = "module.py"

REQUIRED = ("id", "name")


class ModuleError(Exception):
    pass


class PetModule:
    """一个模块的元信息与工厂。"""

    def __init__(self, root, meta):
        self.root = os.path.abspath(root)
        self.meta = meta
        self.id = meta["id"]
        self.name = meta.get("name", self.id)
        self.name_en = meta.get("name_en", "")
        self.kind = meta.get("kind", "pet")
        self.version = meta.get("version", "1.0.0")
        self.author = meta.get("author", "未知")
        self.desc = meta.get("desc", "")
        self.entry = meta.get("entry", DEFAULT_ENTRY)
        self.icon_name = meta.get("icon", "")
        self.enabled = meta.get("enabled", True)
        self.error = None
        self._factory = None

    # ---- 元信息 ---------------------------------------------------------
    @property
    def path(self):
        return self.root

    def entry_path(self):
        return os.path.join(self.root, self.entry)

    def icon_path(self):
        if self.icon_name:
            p = os.path.join(self.root, self.icon_name)
            if os.path.isfile(p):
                return p
        for cand in ("icon.png", "icon.jpg", "icon.webp"):
            p = os.path.join(self.root, cand)
            if os.path.isfile(p):
                return p
        return None

    def kind_label(self):
        return {"pet": "桌宠", "minigame": "小游戏"}.get(self.kind, self.kind)

    # ---- 加载 -----------------------------------------------------------
    def load(self):
        """导入 entry 模块并取出 create()。失败时把错误记在 self.error。"""
        if self._factory is not None:
            return self._factory
        path = self.entry_path()
        if not os.path.isfile(path):
            raise ModuleError(f"缺少入口文件 {self.entry}")
        mod_name = f"dogpet_mod_{self.id}"
        spec = importlib.util.spec_from_file_location(mod_name, path)
        if spec is None or spec.loader is None:
            raise ModuleError(f"无法导入 {path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[mod_name] = module
        # 让模块内可以 import 本项目的东西
        src = os.path.join(os.path.dirname(os.path.dirname(self.root)), "src")
        if src not in sys.path:
            sys.path.insert(0, src)
        spec.loader.exec_module(module)
        factory = getattr(module, "create", None)
        if factory is None:
            cls = getattr(module, "Pet", None)
            if cls is None:
                raise ModuleError("模块里既没有 create(host) 也没有 Pet 类")
            factory = cls
        self._factory = factory
        return factory

    def create(self, host):
        factory = self.load()
        return factory(host)

    # ---- 校验 -----------------------------------------------------------
    def validate(self):
        """返回问题列表，空列表代表健康。"""
        problems = []
        for k in REQUIRED:
            if k not in self.meta:
                problems.append(f"pet.json 缺少字段 {k}")
        if not os.path.isfile(self.entry_path()):
            problems.append(f"找不到 {self.entry}")
        try:
            self.load()
        except Exception as exc:
            problems.append(f"加载失败：{type(exc).__name__}: {exc}")
            self.error = traceback.format_exc()
        return problems


def pets_root(base=None):
    """pets 目录：打包后优先用 exe 旁边的，方便用户直接丢模块进去。"""
    if base is None:
        if getattr(sys, "frozen", False):
            base = os.path.dirname(sys.executable)
        else:
            base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cand = os.path.join(base, "pets")
    if os.path.isdir(cand):
        return cand
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return os.path.join(meipass, "pets")
    return cand


def scan(root=None):
    """扫描所有模块，按 kind 排序返回 PetModule 列表。"""
    root = root or pets_root()
    out = []
    if not os.path.isdir(root):
        return out
    for name in sorted(os.listdir(root)):
        d = os.path.join(root, name)
        if not os.path.isdir(d) or name.startswith(("_", ".")):
            continue
        mf = os.path.join(d, MANIFEST)
        if not os.path.isfile(mf):
            continue
        try:
            with open(mf, "r", encoding="utf-8") as f:
                meta = json.load(f)
        except Exception:
            continue
        if not isinstance(meta, dict):
            continue
        meta.setdefault("id", name)
        if not meta.get("enabled", True):
            continue
        out.append(PetModule(d, meta))
    out.sort(key=lambda m: (0 if m.kind == "pet" else 1, m.name))
    return out


def find(module_id, root=None):
    for m in scan(root):
        if m.id == module_id:
            return m
    return None
