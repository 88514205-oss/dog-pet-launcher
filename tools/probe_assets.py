import os, sys
import numpy as np
from PIL import Image

GD = os.path.join(os.environ['USERPROFILE'], 'Desktop', 'GOD')
SP = os.path.join(GD, '精灵图原图')
SINGLE = os.path.join(GD, '透明底单帧')


def info(p):
    if not os.path.exists(p):
        print('MISSING', p)
        return None
    im = Image.open(p)
    a = np.array(im.convert('RGBA'))
    print(f'{os.path.basename(p):40s} {im.size} mode={im.mode} alpha_min={a[...,3].min()} '
          f'opaque_px={(a[...,3]>8).sum()}')
    return a


print('=== sprite sheets ===')
for n in ['ChibiiDoggo.png', 'ChibiiDoggoMonochrome.png', 'ChibiiDoggoFly.png',
          'ChibiiDoggoFlyMonochrome.png', 'ChibiiDoGBuff.png', 'CosmicPlushie.png']:
    info(os.path.join(SP, n))

print()
print('=== land sheet frame split ===')
land = info(os.path.join(SP, 'ChibiiDoggo.png'))
h = land.shape[0]
for nf in (11,):
    fh = h // nf
    frames = [land[i*fh:(i+1)*fh] for i in range(nf)]
    print(f'frame size {land.shape[1]}x{fh}')
    for i, f in enumerate(frames):
        ys, xs = np.where(f[..., 3] > 8)
        bb = (xs.min(), ys.min(), xs.max(), ys.max()) if len(xs) else None
        print(f'  f{i:02d} opaque={(f[...,3]>8).sum():5d} bbox={bb}')
    print('  adjacent frame mean abs diff (RGBA):')
    d = [float(np.abs(frames[i].astype(int) - frames[i+1].astype(int)).mean()) for i in range(nf-1)]
    d.append(float(np.abs(frames[-1].astype(int) - frames[0].astype(int)).mean()))
    print('   ', ' '.join(f'{x:.2f}' for x in d))

print()
print('=== fly sheet ===')
fly = info(os.path.join(SP, 'ChibiiDoggoFly.png'))
for nf in (2,):
    fw = fly.shape[1] // nf
    print(f'hypothesis {nf} frames -> {fw}x{fly.shape[0]}')
    for i in range(nf):
        f = fly[:, i*fw:(i+1)*fw]
        ys, xs = np.where(f[..., 3] > 8)
        bb = (xs.min(), ys.min(), xs.max(), ys.max()) if len(xs) else None
        print(f'  f{i} opaque={(f[...,3]>8).sum():5d} bbox={bb}')

print()
print('=== dogchan frames ===')
ds = sorted(os.listdir(SINGLE)) if os.path.isdir(SINGLE) else []
print('files:', ds)
prev = None
for n in ds:
    a = np.array(Image.open(os.path.join(SINGLE, n)).convert('RGBA'))
    ys, xs = np.where(a[..., 3] > 8)
    bb = (int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())) if len(xs) else None
    line = f'{n} {a.shape[1]}x{a.shape[0]} opaque={(a[...,3]>8).sum():6d} bbox={bb}'
    if prev is not None and prev.shape == a.shape:
        line += f' diff={np.abs(a.astype(int)-prev.astype(int)).mean():.2f}'
    print(line)
    prev = a

print()
print('=== DoG body parts ===')
for d in ['DoG_phase1_v2.0.7.2', 'DoG_phase2_v2.0.7.2']:
    p = os.path.join(GD, 'Textures', d)
    if os.path.isdir(p):
        for n in sorted(os.listdir(p)):
            info(os.path.join(p, n))
