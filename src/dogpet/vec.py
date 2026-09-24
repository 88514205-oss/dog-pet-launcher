"""XNA Vector2 / MathHelper 的最小复刻，供 AI 层直译源码使用。"""

import math

PI = math.pi
HALF_PI = math.pi / 2.0
TWO_PI = math.pi * 2.0


class V:
    __slots__ = ("x", "y")

    def __init__(self, x=0.0, y=0.0):
        self.x = float(x)
        self.y = float(y)

    def copy(self):
        return V(self.x, self.y)

    def __add__(self, o):
        return V(self.x + o.x, self.y + o.y)

    def __sub__(self, o):
        return V(self.x - o.x, self.y - o.y)

    def __mul__(self, s):
        return V(self.x * s, self.y * s)

    __rmul__ = __mul__

    def __truediv__(self, s):
        return V(self.x / s, self.y / s)

    def __neg__(self):
        return V(-self.x, -self.y)

    def __repr__(self):
        return f"V({self.x:.2f}, {self.y:.2f})"

    def length(self):
        return math.hypot(self.x, self.y)

    def length_sq(self):
        return self.x * self.x + self.y * self.y

    def normalized(self):
        n = math.hypot(self.x, self.y)
        if n < 1e-9:
            return V()
        return V(self.x / n, self.y / n)

    def to_rotation(self):
        return math.atan2(self.y, self.x)

    def rotated_by(self, rad):
        c, s = math.cos(rad), math.sin(rad)
        return V(self.x * c - self.y * s, self.x * s + self.y * c)

    def distance(self, o):
        return math.hypot(self.x - o.x, self.y - o.y)

    def distance_sq(self, o):
        dx, dy = self.x - o.x, self.y - o.y
        return dx * dx + dy * dy

    def direction_to(self, o):
        return (o - self).normalized()

    def angle_lerp(self, target, amount):
        r = to_rotation(self)
        return from_rotation(angle_lerp(r, target, amount))

    def lerp(self, o, t):
        return V(self.x + (o.x - self.x) * t, self.y + (o.y - self.y) * t)

    def move_towards(self, target, max_delta):
        dx, dy = target.x - self.x, target.y - self.y
        d = math.hypot(dx, dy)
        if d <= max_delta or d < 1e-9:
            return V(target.x, target.y)
        k = max_delta / d
        return V(self.x + dx * k, self.y + dy * k)


def from_rotation(rad):
    return V(math.cos(rad), math.sin(rad))


def to_rotation(v):
    return math.atan2(v.y, v.x)


def wrap_angle(rad):
    while rad < -PI:
        rad += TWO_PI
    while rad > PI:
        rad -= TWO_PI
    return rad


def angle_lerp(a, b, amount):
    return a + wrap_angle(b - a) * amount


def clamp(v, lo, hi):
    return lo if v < lo else (hi if v > hi else v)


def lerp(a, b, t):
    return a + (b - a) * t
