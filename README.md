# 蓝色小鲸鱼薪资桌宠 · Whale Salary Pet

一只常驻 Windows 桌面的圆润治愈系蓝色小鲸鱼：白肚皮、大眼睛、腮红、头顶喷水、
随机眨眼 / 摆尾 / 喷水动画。单击有鼓励语，双击开薪资面板，右键有完整菜单，
老板键 `Ctrl+Q` 一键隐身（无托盘、无任务栏，隐匿防老板）。

## 薪资规则（严格按需求实现，勿改）

- 月薪固定税前 **7000 元**；每周日不上班，但**周日计入薪资分摊**（按当月自然日平均）
- 时薪 = `7000 ÷ 当月自然日天数 ÷ 11`（薪资基准 **11 小时/天**）
  - 31 天月份 → ¥20.53/h；30 天 → ¥21.21/h；闰年 2 月 29 天自动识别
- 实际在岗三段 `08:30-11:00 / 13:00-16:30 / 17:30-19:30` 合计 **8 小时**，
  仅用于**工时展示**（面板按 8/11 折算显示"今日在岗 x/8h"）；
  **薪资计算基准仍为 11h/天，两者分开处理**
- 计时窗口 `8:30-19:30` 全程连续（午休晚饭也在公司照算钱），**8:30 自动开工、19:30 自动收工**
- 双口径统计严格分开、不重复相加：
  - **月薪进度累计**（主数字）= 月薪 ÷ 当月自然日 × 已过天数（周日照常累计，满勤=月薪）
  - **工时折算**（参考）= 时薪 × 实际计时分钟
- 月历把周日标记为休息日；跨天 / 跨月 / 闰年 / 重启均已处理

## 运行

### 方式一：源码运行（推荐日常使用）
```
双击 start_pet.pyw          # 静默启动，无黑窗
```
要求：本机装有 Python（含 tkinter，官方安装包默认带）。
贴图 `whale_*.png` 必须与脚本同目录（仓库已带，可用 `render_whale.py` 重新生成）。

### 方式二：开机自启（已配置）
启动项 vbs 位于
`%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\desktop_widget.vbs`，
静默拉起 pythonw，无需任何操作。

### 方式三：exe 单文件
见下方打包。

## 交互

| 操作 | 效果 |
|---|---|
| 单击鲸鱼 | 鼓励语 + 今日薪资（上班/下班/周日文案不同） |
| 双击鲸鱼 | 薪资面板（三卡+进度条+工时+月历+柱状图+明细） |
| 右键鲸鱼 | 菜单：展开/收起、暂停/开始计时、记一笔、面板、设置、隐身、退出 |
| 左键拖动 | 移动位置（自动记忆） |
| Ctrl+Q | 全局隐身 / 唤回 |
| 迷你小点 | 单击展开鲸鱼，内显当日收入与进度环 |

设置项：月薪、日薪口径（按自然日/按工作日）、休息日、计时时段（1-3 段）、
大小（小/中/大）、闲置 5 分钟自动收起、老板键、动画、胸前收入牌等。

## 数据

- 保存于同目录 `widget.cfg`（JSON，伪装成普通配置文件），原子写入
- 记录按月分桶（`records.2026-10.2026-10-20`），跨天/跨月自动切换
- 旧版配置（daily_salary/work_start/work_end）加载时自动迁移并写入 `model_v2_11h` 标记

## 单元测试

```
python test_petdata.py     # 数据层全部断言，不启动 GUI
```

覆盖：时薪公式（30/31/28/29 天）、双口径不重复相加、工时 8/11 折算、
计时窗口边界、周日不计时、封顶、跨月分桶、旧配置迁移、坏配置容错、贴图完整性。

## 重新生成贴图（可选）

```
pip install Pillow
python render_whale.py     # 重新渲染 13 帧 whale_*.png
```

## 打包 Windows exe

```
pip install pyinstaller
pyinstaller --onefile --noconsole --name WhaleSalaryPet ^
  --add-data "whale_idle0.png;."  --add-data "whale_idle1.png;." ^
  --add-data "whale_blink.png;."  --add-data "whale_happy.png;." ^
  --add-data "whale_sleepy.png;." --add-data "whale_off.png;." ^
  --add-data "whale_tail0.png;."  --add-data "whale_tail1.png;." ^
  --add-data "whale_tail2.png;."  --add-data "whale_spout0.png;." ^
  --add-data "whale_spout1.png;." --add-data "whale_spout2.png;." ^
  --add-data "whale_spout3.png;." desktop_pet.py
```

产物在 `dist/WhaleSalaryPet.exe`（约 12-18MB），双击即用，无需安装 Python。
数据文件 `widget.cfg` 生成在 exe 同目录。

## 文件结构

```
desktop_pet.py    主程序（tkinter，运行时零第三方依赖）
render_whale.py   小鲸鱼贴图渲染脚本（Pillow，离线一次性运行）
test_petdata.py   薪资数据层单元测试
whale_*.png       13 帧动画贴图（眨眼/摆尾/喷水/开心/犯困等）
start_pet.pyw     双击启动器
desktop_widget.vbs（Startup 目录）开机自启
```
