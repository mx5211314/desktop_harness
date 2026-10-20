# -*- coding: utf-8 -*-
"""render_whale.py —— 蓝色小鲸鱼桌宠贴图渲染（PIL 离线渲染，运行时零依赖加载）。

设计语言：圆润治愈系 Q 版小鲸鱼
  - 圆滚蛋形身体，浅蓝渐变（上亮下深），深蓝描边
  - 白色大肚皮、大眼睛（双高光）、粉紫腮红、头顶喷水
  - 淡紫色水珠点缀
帧集合（各帧独立 PNG，运行时 tk.PhotoImage 加载轮播）：
  whale_idle / whale_blink / whale_happy / whale_sleepy / whale_off
  whale_tail0..2（摆尾三帧）/ whale_spout0..3（喷水四帧）

用法：python render_whale.py   （需 Pillow：PYTHONPATH=C:\\Users\\49084\\.workbuddy\\binaries\\pylibs）
"""
import math
import os

from PIL import Image, ImageDraw, ImageFilter

BASE = os.path.dirname(os.path.abspath(__file__))
S = 4                      # 超采样倍数
W, H = 180, 150            # 逻辑画布
PW, PH = W * S, H * S

# ---- 配色（浅蓝+白+淡紫）----
BODY_TOP = (176, 216, 244)
BODY = (132, 186, 233)
BODY_BOT = (104, 164, 218)
OUTLINE = (62, 111, 160)
BELLY = (246, 251, 255)
BELLY_SHADE = (214, 233, 247)
CHEEK = (244, 197, 216)          # 粉紫腮红
CHEEK_A = 150
SPOUT = (150, 205, 245)
SPOUT_LIGHT = (196, 230, 250)
PURPLE = (196, 178, 232)         # 淡紫水珠
DARK = (46, 74, 102)
WHITE = (255, 255, 255)
SHADOW = (176, 190, 205)


def sc(v):
    return int(round(v * S))


def ellipse(d, box, **kw):
    d.ellipse([sc(box[0]), sc(box[1]), sc(box[2]), sc(box[3])], **kw)


def body_gradient(img, box, top, mid, bot, outline=None, width=3):
    """竖向三段渐变椭圆（用横向裁切条模拟竖向渐变）。"""
    x0, y0, x1, y1 = [sc(v) for v in box]
    grad = Image.new("RGB", (x1 - x0, y1 - y0), mid)
    gd = ImageDraw.Draw(grad)
    hgt = y1 - y0
    for yy in range(hgt):
        r = yy / max(1, hgt - 1)
        if r < 0.45:
            c = top
        elif r < 0.75:
            t = (r - 0.45) / 0.30
            c = tuple(int(top[i] + (bot[i] - top[i]) * t) for i in range(3))
        else:
            c = bot
        gd.line([(0, yy), (x1 - x0, yy)], fill=c)
    mask = Image.new("L", (x1 - x0, y1 - y0), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, x1 - x0 - 1, y1 - y0 - 1], fill=255)
    img.paste(grad, (x0, y0), mask)
    if outline:
        ImageDraw.Draw(img).ellipse([x0, y0, x1 - 1, y1 - 1],
                                    outline=outline, width=sc(width))


def draw_whale(action="idle", frame=0):
    """画一帧小鲸鱼，返回 RGBA 图。action: idle/blink/happy/sleepy/off/tail/spout"""
    img = Image.new("RGBA", (PW, PH), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    tail_ang = 0
    if action == "tail":
        tail_ang = (-18, 0, 18)[frame % 3]
    spout_t = -1.0
    if action == "spout":
        spout_t = frame / 3.0            # 0..1 水柱升起->消散
    breathe = 0
    if action == "idle":
        breathe = frame % 2               # 微幅呼吸（身体整体上下 1px）

    oy = sc(breathe * 0.8)
    cy = 84 + breathe * 0.8               # 身体中心 y（逻辑坐标）

    # ---- 脚下影子 ----
    ellipse(d, (36, 138, 144, 147), fill=(SHADOW[0], SHADOW[1], SHADOW[2], 120))

    # ---- 尾鳍（右侧两瓣，独立图层旋转）----
    tail = Image.new("RGBA", (sc(70), sc(70)), (0, 0, 0, 0))
    td = ImageDraw.Draw(tail)
    # 上瓣
    td.ellipse([sc(6), sc(2), sc(58), sc(40)], fill=BODY + (255,),
               outline=OUTLINE + (255,), width=sc(2.6))
    td.ellipse([sc(14), sc(9), sc(46), sc(30)], fill=BODY_TOP + (255,))
    # 下瓣
    td.ellipse([sc(2), sc(30), sc(52), sc(66)], fill=BODY_BOT + (255,),
               outline=OUTLINE + (255,), width=sc(2.6))
    td.ellipse([sc(9), sc(38), sc(40), sc(56)], fill=BODY + (255,))
    tail = tail.rotate(tail_ang, resample=Image.BICUBIC, expand=True)
    tx, ty = sc(128), sc(64)   # 尾鳍粘贴位置（身体右后）
    img.alpha_composite(tail, (tx - (tail.width - sc(70)) // 2, ty))

    # ---- 身体（圆润蛋形，竖向渐变）----
    body_box = (14, cy - 46, 148, cy + 52)
    body_gradient(img, body_box, BODY_TOP, BODY, BODY_BOT, outline=OUTLINE, width=2.8)
    bx0, by0, bx1, by1 = [sc(v) for v in body_box]
    body_mask = Image.new("L", (PW, PH), 0)
    ImageDraw.Draw(body_mask).ellipse([bx0, by0, bx1 - 1, by1 - 1], fill=255)

    # ---- 头顶背鳍（圆润小弧）----
    fin = Image.new("RGBA", (PW, PH), (0, 0, 0, 0))
    fd = ImageDraw.Draw(fin)
    fd.pieslice([sc(58), sc(cy - 78), sc(116), sc(cy - 20)], 180, 320,
                fill=BODY_TOP + (255,), outline=OUTLINE + (255,), width=sc(2.2))
    fin_mask = Image.new("L", (PW, PH), 0)
    ImageDraw.Draw(fin_mask).ellipse([bx0, by0, bx1 - 1, by1 - 1], fill=255)
    fin.putalpha(Image.composite(fin.getchannel("A"),
                                 Image.new("L", (PW, PH), 0), body_mask))
    img.alpha_composite(fin)

    # ---- 白肚皮 ----
    belly = Image.new("RGBA", (PW, PH), (0, 0, 0, 0))
    bd = ImageDraw.Draw(belly)
    bd.ellipse([sc(34), sc(cy + 2), sc(126), sc(cy + 52)],
               fill=BELLY + (255,), outline=BELLY_SHADE + (255,), width=sc(1.6))
    # 肚皮纹理线（两条淡弧）
    bd.arc([sc(46), sc(cy + 16), sc(114), sc(cy + 54)], 200, 340,
           fill=BELLY_SHADE + (255,), width=sc(1.4))
    # 用身体形状裁剪肚皮（交集）
    belly.putalpha(Image.composite(belly.getchannel("A"),
                                   Image.new("L", (PW, PH), 0), body_mask))
    img.alpha_composite(belly)

    # ---- 眼睛 ----
    ey = cy - 12
    eye_l, eye_r = (58, 84), (102, 128)   # 左右眼 x 中心
    er = 11
    if action == "happy":
        for ex in (eye_l[0], eye_r[0]):
            d.arc([sc(ex - er), sc(ey - er), sc(ex + er), sc(ey + er)],
                  190, 350, fill=DARK + (255,), width=sc(3.4))
    elif action == "blink" or action == "off":
        for ex in (eye_l[0], eye_r[0]):
            d.arc([sc(ex - er), sc(ey - 2), sc(ex + er), sc(ey + er + 2)],
                  30, 150, fill=DARK + (255,), width=sc(3.2))
    elif action == "sleepy":
        for ex in (eye_l[0], eye_r[0]):
            d.arc([sc(ex - er), sc(ey - er), sc(ex + er), sc(ey + er)],
                  20, 160, fill=DARK + (255,), width=sc(3.2))
    else:
        for ex in (eye_l[0], eye_r[0]):
            ellipse(d, (ex - er, ey - er, ex + er, ey + er),
                    fill=DARK + (255,))
            ellipse(d, (ex - er + 3, ey - er + 2, ex - er + 12, ey - er + 11),
                    fill=WHITE + (255,))
            ellipse(d, (ex + 2, ey + 3, ex + 8, ey + 9),
                    fill=(255, 255, 255, 190))

    # ---- 腮红（粉紫半透明）----
    for cx in (42, 130):
        ellipse(d, (cx - 13, cy + 6, cx + 13, cy + 20),
                fill=CHEEK + (185,))

    # ---- 嘴 ----
    mx = 93
    if action == "happy":
        d.pieslice([sc(mx - 10), sc(cy + 2), sc(mx + 10), sc(cy + 18)],
                   0, 180, fill=DARK + (255,))
        d.pieslice([sc(mx - 7), sc(cy + 4), sc(mx + 7), sc(cy + 17)],
                   0, 180, fill=(238, 130, 150, 255))
    elif action in ("off", "sleepy"):
        d.line([sc(mx - 7), sc(cy + 9), sc(mx + 7), sc(cy + 9)],
               fill=DARK + (255,), width=sc(2.2))
    else:
        d.arc([sc(mx - 9), sc(cy - 2), sc(mx + 9), sc(cy + 12)],
              25, 155, fill=DARK + (255,), width=sc(2.4))

    # ---- 头顶喷水 ----
    if spout_t >= 0:
        hgt = math.sin(min(1.0, spout_t * 1.6) * math.pi / 2) * 26
        fade = max(0.15, 1.0 - spout_t * 0.85)
        top_y = cy - 66 - hgt
        # 水柱（梯形）
        d.polygon([(sc(89), sc(cy - 52)), (sc(97), sc(cy - 52)),
                   (sc(100 + 6 * (1 - spout_t)), sc(top_y)),
                   (sc(86 - 6 * (1 - spout_t)), sc(top_y))],
                  fill=SPOUT + (int(220 * fade),))
        # 顶端水花：1 大 + 2 小水珠（淡蓝+淡紫）
        wx = 93
        ellipse(d, (wx - 7, top_y - 12, wx + 7, top_y + 2),
                fill=SPOUT_LIGHT + (int(235 * fade),))
        ellipse(d, (wx - 15, top_y - 2, wx - 7, top_y + 6),
                fill=SPOUT + (int(200 * fade),))
        ellipse(d, (wx + 7, top_y - 4, wx + 15, top_y + 4),
                fill=PURPLE + (int(200 * fade),))
        ellipse(d, (wx - 3, top_y - 20, wx + 3, top_y - 14),
                fill=PURPLE + (int(190 * fade),))
    else:
        # 静态：喷水孔
        ellipse(d, (88, cy - 62, 98, cy - 54), fill=BODY_BOT + (255,),
                outline=OUTLINE + (255,), width=sc(1.6))

    # ---- 呆毛/水珠点缀（淡紫小圆，body 左上）----
    if action != "off":
        ellipse(d, (30, cy - 52, 38, cy - 44), fill=PURPLE + (210,))
        ellipse(d, (140, cy - 30, 146, cy - 24), fill=PURPLE + (170,))

    return img


def save(img, name):
    """4x 超采样 -> LANCZOS 缩小 -> alpha 轻微平滑后二值化（避免 Tk 半透明发灰）。"""
    small = img.resize((W, H), Image.LANCZOS)
    r, g, b, a = small.split()
    a = a.filter(ImageFilter.GaussianBlur(0.6))
    a = a.point(lambda v: 255 if v >= 128 else 0)
    out = Image.merge("RGBA", (r, g, b, a))
    out.save(os.path.join(BASE, name))
    print("saved", name)


def main():
    frames = [("idle", 0), ("idle", 1),
              ("blink", 0),
              ("happy", 0),
              ("sleepy", 0),
              ("off", 0)]
    for a, f in frames:
        save(draw_whale(a, f), "whale_{}.png".format(a if a != "idle" else
                                                     ("idle0" if f == 0 else "idle1")))
    for f in range(3):
        save(draw_whale("tail", f), "whale_tail{}.png".format(f))
    for f in range(4):
        save(draw_whale("spout", f), "whale_spout{}.png".format(f))
    print("done")


if __name__ == "__main__":
    main()
