# -*- coding: utf-8 -*-
"""小鲸鱼薪资桌宠 · 双击启动器（薄壳，实际逻辑在 desktop_pet.py）。

双击本文件 = 用 pythonw 静默启动桌宠，无控制台黑窗。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import desktop_pet

if __name__ == "__main__":
    desktop_pet.main()
