# -*- coding: utf-8 -*-
"""桌宠猫咪贴图离线渲染脚本（构建工具，运行时零依赖）。

风格参考 DeepSeek 小鲸鱼：单一柔蓝、极简圆润、干净描边、脸上东西少。
渲染：4x 超采样 -> LANCZOS 缩小 -> alpha 二值化。
边缘处理：body 类形状额外画一圈放大的「深蓝描边」底（bleed 层），
半透明边缘像素混到描边色而非黑色/浅色，得到干净利落的边（深浅桌面都不泛光）。
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFilter

S = 4
W, H = 170, 190
BW, BH = W * S, H * S
B = 10                 # bleed 扩张量（4x 像素）

# 单一柔蓝系（明亮柔和，不发黄不发黑）
BODY    = (120, 168, 222, 255)   # 主体柔蓝
BELLY   = (200, 224, 245, 255)   # 肚皮/爪/内耳：更浅一档，柔和过渡
OUTLINE = (63, 116, 178, 255)    # 描边深蓝（干净收边，避免深色桌面泛光晕）
DARK    = (58, 78, 108, 255)     # 五官：柔和藏蓝，不刺眼
WHITE   = (255, 255, 255, 255)
BLACK   = (0, 0, 0, 255)


class Painter:
    def __init__(self):
        self.shape = Image.new("RGBA", (BW, BH), (0, 0, 0, 0))
        self.bleed = Image.new("RGBA", (BW, BH), (0, 0, 0, 0))
        self.d = ImageDraw.Draw(self.shape)
        self.db = ImageDraw.Draw(self.bleed)

    def ellipse(self, box, fill, bleed=OUTLINE):
        self.d.ellipse(box, fill=fill)
        x0, y0, x1, y1 = box
        self.db.ellipse((x0 - B, y0 - B, x1 + B, y1 + B), fill=bleed)

    def polygon(self, pts, fill, bleed=OUTLINE, grow=0.08):
        self.d.polygon(pts, fill=fill)
        cx = sum(p[0] for p in pts) / len(pts)
        cy = sum(p[1] for p in pts) / len(pts)
        self.db.polygon([((x - cx) * (1 + grow) + cx, (y - cy) * (1 + grow) + cy)
                         for x, y in pts], fill=bleed)

    def line(self, pts, fill, width, bleed=OUTLINE):
        self.d.line(pts, fill=fill, width=width, joint="curve")
        self.db.line(pts, fill=bleed, width=width + 2 * B, joint="curve")

    def arc(self, box, start, end, fill, width, bleed=OUTLINE):
        self.d.arc(box, start, end, fill=fill, width=width)
        self.db.arc(box, start, end, fill=bleed, width=width + 2 * B)

    def save(self, path):
        comp = Image.alpha_composite(self.bleed, self.shape)
        rgb = comp.convert("RGB").resize((W, H), Image.LANCZOS)
        # 轻微高斯模糊后再阈值，消除边缘锯齿点
        mask = (self.shape.split()[3].resize((W, H), Image.LANCZOS)
                .filter(ImageFilter.GaussianBlur(0.6)))
        out = Image.merge("RGBA", (*rgb.split(), mask))
        px = out.load()
        for y in range(H):
            for x in range(W):
                r, g, b, a = px[x, y]
                px[x, y] = (r, g, b, 255) if a >= 128 else (0, 0, 0, 0)
        out.save(path)
        print("saved", path)


def draw_cat(mood, path):
    p = Painter()
    # 尾巴：圆球绒毛尾（chibi 经典），短连接段 + 圆球，干净不尖锐
    p.line([(508, 566), (616, 498)], BODY, 56)
    p.ellipse((584, 448, 668, 532), BODY)
    # 耳朵（圆润小三角）
    p.polygon([(168, 186), (224, 84), (322, 162)], BODY)
    p.polygon([(532, 186), (476, 84), (378, 162)], BODY)
    # 身体（单一柔蓝大圆角块）
    p.ellipse((92, 120, 588, 692), BODY)
    # 极简内耳（柔和浅蓝，融入）
    p.polygon([(200, 168), (228, 112), (286, 158)], BELLY, bleed=BELLY, grow=0.12)
    p.polygon([(500, 168), (472, 112), (414, 158)], BELLY, bleed=BELLY, grow=0.12)
    # 柔和肚皮 + 前爪（无硬白边）
    p.ellipse((222, 452, 458, 666), BELLY, bleed=BODY)
    p.ellipse((214, 600, 326, 692), BELLY, bleed=BODY)
    p.ellipse((354, 600, 466, 692), BELLY, bleed=BODY)
    # 表情：极简
    if mood == "off":       # 收工：垂眼 + 平嘴
        p.arc((236, 300, 296, 360), 20, 160, DARK, 12)
        p.arc((404, 300, 464, 360), 20, 160, DARK, 12)
        p.line([(322, 433), (358, 433)], DARK, 8)
    elif mood == "happy":   # 工作中：弯月眼 + 小微笑
        p.arc((236, 304, 296, 360), 180, 360, DARK, 13)
        p.arc((404, 304, 464, 360), 180, 360, DARK, 13)
        p.arc((318, 420, 362, 450), 20, 160, DARK, 8)
    else:                   # 平静：小而圆的眼 + 一点高光 + 微笑
        for ex in (240, 408):
            p.ellipse((ex, 300, ex + 44, 360), DARK)
            p.ellipse((ex + 8, 312, ex + 24, 328), WHITE, bleed=WHITE)
        p.ellipse((330, 398, 350, 412), DARK)          # 小鼻子
        p.arc((318, 418, 362, 450), 20, 160, DARK, 8)
    p.save(path)


if __name__ == "__main__":
    out_dir = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__))
    for mood in ("idle", "happy", "off"):
        draw_cat(mood, os.path.join(out_dir, "cat_{}.png".format(mood)))
