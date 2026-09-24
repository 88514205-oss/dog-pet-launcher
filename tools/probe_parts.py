import os
import numpy as np
from PIL import Image

GD = os.path.join(os.environ['USERPROFILE'], 'Desktop', 'GOD', 'Textures')

FILES = [
    ('P1 head', 'DoG_phase1_v2.0.7.2/DevourerofGodsHead.png'),
    ('P1 body', 'DoG_phase1_v2.0.7.2/DevourerofGodsBody.png'),
    ('P1 tail', 'DoG_phase1_v2.0.7.2/DevourerofGodsTail.png'),
    ('P2 head', 'DoG_phase2_v2.0.7.2/DevourerofGodsHeadS.png'),
    ('P2 body', 'DoG_phase2_v2.0.7.2/DevourerofGodsBodyS.png'),
    ('P2 tail', 'DoG_phase2_v2.0.7.2/DevourerofGodsTailS.png'),
]


def analyse(label, rel):
    p = os.path.join(GD, rel.replace('/', os.sep))
    im = Image.open(p).convert('RGBA')
    a = np.array(im)
    mask = a[..., 3] > 40
    h, w = mask.shape
    ys, xs = np.nonzero(mask)
    cx, cy = xs.mean(), ys.mean()
    print(f'--- {label}  {w}x{h}  px={mask.sum()}  质心=({cx:.1f},{cy:.1f}) 中心=({w/2:.1f},{h/2:.1f})')
    cov = np.cov(np.vstack([xs - cx, ys - cy]))
    val, vec = np.linalg.eigh(cov)
    major = vec[:, np.argmax(val)]
    ang = np.degrees(np.arctan2(major[1], major[0])) % 180
    ratio = np.sqrt(max(val) / max(min(val), 1e-6))
    print(f'    主轴角度={ang:.1f}° 长宽比={ratio:.2f} 标准差=({np.sqrt(val[0]):.1f},{np.sqrt(val[1]):.1f})')
    proj = (xs - cx) * major[0] + (ys - cy) * major[1]
    print(f'    沿主轴投影范围 [{proj.min():.1f}, {proj.max():.1f}] 长度={proj.max()-proj.min():.1f}')
    perp = vec[:, np.argmin(val)]
    proj2 = (xs - cx) * perp[0] + (ys - cy) * perp[1]
    print(f'    垂直轴宽度={proj2.max()-proj2.min():.1f}')

    rows = mask.sum(axis=1)
    cols = mask.sum(axis=0)
    nz_r = np.nonzero(rows)[0]
    nz_c = np.nonzero(cols)[0]
    print(f'    bbox 行[{nz_r.min()}..{nz_r.max()}] 列[{nz_c.min()}..{nz_c.max()}]')
    q = max(1, h // 8)
    band = [int(rows[i*q:(i+1)*q].sum()) for i in range(8)]
    print(f'    行分带(上→下) {band}')
    q2 = max(1, w // 8)
    band2 = [int(cols[i*q2:(i+1)*q2].sum()) for i in range(8)]
    print(f'    列分带(左→右) {band2}')
    # 末端宽度：判断哪一端是"细"的（尾巴/前段）
    top = mask[:max(1, h//6)].sum()
    bot = mask[-max(1, h//6):].sum()
    left = mask[:, :max(1, w//6)].sum()
    right = mask[:, -max(1, w//6):].sum()
    print(f'    上={top} 下={bot} 左={left} 右={right}')


for lbl, rel in FILES:
    analyse(lbl, rel)
