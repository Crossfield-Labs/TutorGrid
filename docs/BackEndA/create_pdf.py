# -*- coding: utf-8 -*-
import os
from reportlab.lib.pagesizes import A4
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor, white, black
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.platypus.doctemplate import PageTemplate
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# ── Register CJK Font ──────────────────────────────────
FONT_PATH = r"C:\Windows\Fonts\msyh.ttc"
FONT_BOLD_PATH = r"C:\Windows\Fonts\msyhbd.ttf"

pdfmetrics.registerFont(TTFont('CJK', FONT_PATH, subfontIndex=0))
pdfmetrics.registerFont(TTFont('CJKBold', FONT_BOLD_PATH))
# Map family for easy use
from reportlab.pdfbase.pdfmetrics import registerFontFamily
registerFontFamily('CJK', normal='CJK', bold='CJKBold')

# ── Colors ──────────────────────────────────────────────
PRIMARY     = HexColor('#1a237e')
SECONDARY   = HexColor('#3949ab')
ACCENT      = HexColor('#ff6f00')
LIGHT_BG    = HexColor('#f5f5f5')
MID_BG      = HexColor('#e8eaf6')
DARK_TEXT    = HexColor('#212121')
MED_TEXT     = HexColor('#424242')
LIGHTER_TEXT = HexColor('#9e9e9e')
WHITE       = white

# ── Custom Styles ───────────────────────────────────────
styles = getSampleStyleSheet()

styles.add(ParagraphStyle(
    name='SectionTitle', fontName='CJKBold', fontSize=17, leading=24,
    textColor=PRIMARY, spaceBefore=10*mm, spaceAfter=5*mm,
))

styles.add(ParagraphStyle(
    name='SubSectionTitle', fontName='CJKBold', fontSize=12, leading=18,
    textColor=SECONDARY, spaceBefore=6*mm, spaceAfter=3*mm,
))

styles.add(ParagraphStyle(
    name='BodyCN', fontName='CJK', fontSize=10.5, leading=18,
    textColor=DARK_TEXT, alignment=TA_JUSTIFY,
    spaceAfter=4*mm, firstLineIndent=21,
))

styles.add(ParagraphStyle(
    name='QuoteBlock', fontName='CJK', fontSize=10, leading=17,
    textColor=MED_TEXT, alignment=TA_JUSTIFY,
    leftIndent=12*mm, rightIndent=12*mm,
    spaceBefore=5*mm, spaceAfter=5*mm,
    borderColor=ACCENT, borderWidth=1.5, borderPadding=10,
    backColor=HexColor('#fff8e1'),
))

styles.add(ParagraphStyle(
    name='BulletItem', fontName='CJK', fontSize=10.5, leading=18,
    textColor=DARK_TEXT, leftIndent=8*mm, bulletIndent=3*mm,
    spaceAfter=3*mm,
))

styles.add(ParagraphStyle(
    name='Caption', fontName='CJK', fontSize=8.5, leading=12,
    textColor=LIGHTER_TEXT, alignment=TA_CENTER,
    spaceBefore=3*mm, spaceAfter=6*mm,
))

styles.add(ParagraphStyle(
    name='Footer', fontName='CJK', fontSize=8, leading=10,
    textColor=LIGHTER_TEXT, alignment=TA_CENTER,
))

W, H = A4

# ── Page Template ───────────────────────────────────────
class BodyPageTemplate(PageTemplate):
    def __init__(self):
        from reportlab.platypus.frames import Frame
        frame = Frame(22*mm, 22*mm, W-44*mm, H-50*mm, id='main')
        super().__init__(id='body', frames=[frame])

    def afterDrawPage(self, canv, doc):
        canv.saveState()
        canv.setStrokeColor(HexColor('#e0e0e0'))
        canv.setLineWidth(0.5)
        canv.line(22*mm, 18*mm, W-22*mm, 18*mm)
        canv.setFont('CJK', 8)
        canv.setFillColor(LIGHTER_TEXT)
        canv.drawCentredString(W/2, 12*mm, f"— {doc.page} —")
        canv.setFont('CJKBold', 8)
        canv.setFillColor(SECONDARY)
        canv.drawString(22*mm, H - 16*mm, "深度工作 · Deep Work")
        canv.drawRightString(W-22*mm, H-16*mm, "Cal Newport")
        canv.restoreState()


# ── Build ───────────────────────────────────────────────
output_path = os.path.join(os.path.dirname(__file__), "Deep_Work_深度工作.pdf")
doc = SimpleDocTemplate(
    output_path, pagesize=A4,
    leftMargin=22*mm, rightMargin=22*mm,
    topMargin=22*mm, bottomMargin=22*mm,
    title="Deep Work: 深度工作的艺术",
    author="Cal Newport · 核心思想精要",
)
doc.addPageTemplates([BodyPageTemplate()])

story = []

# ═════ COVER ═════
# Blue header bar
cover_header = Table([[""]], colWidths=[W+44*mm], rowHeights=[H*0.38])
cover_header.setStyle(TableStyle([
    ('BACKGROUND', (0,0), (-1,-1), PRIMARY),
]))
story.append(cover_header)

story.append(Spacer(1, H*0.04))
story.append(Paragraph("DEEP  WORK", ParagraphStyle(
    'cover_title', fontName='CJKBold', fontSize=32, leading=38,
    textColor=PRIMARY, alignment=TA_CENTER,
)))
story.append(Spacer(1, 5*mm))
story.append(Paragraph("深度工作的艺术", ParagraphStyle(
    'cover_sub', fontName='CJKBold', fontSize=18, leading=26,
    textColor=SECONDARY, alignment=TA_CENTER,
)))
story.append(Spacer(1, 10*mm))
story.append(HRFlowable(width="25%", thickness=2, color=ACCENT, spaceAfter=8*mm))
story.append(Paragraph("如何在分心世界中重获专注力", ParagraphStyle(
    'cover_tag', fontName='CJK', fontSize=11, leading=16,
    textColor=MED_TEXT, alignment=TA_CENTER,
)))
story.append(Spacer(1, 8*mm))
story.append(Paragraph("Cal Newport 著　·　核心思想精要", ParagraphStyle(
    'cover_meta', fontName='CJK', fontSize=9, leading=13,
    textColor=LIGHTER_TEXT, alignment=TA_CENTER,
)))
story.append(Spacer(1, H*0.16))
story.append(HRFlowable(width="100%", thickness=0.5, color=HexColor('#e0e0e0'), spaceAfter=8*mm))

# ═════ ABOUT ═════
story.append(Paragraph("关于本书", styles['SectionTitle']))
story.append(Paragraph(
    "在注意力经济时代，<b>深度工作</b>（Deep Work）已成为一种稀缺而极具价值的能力。"
    "Cal Newport 在本书中系统阐述了深度工作的概念——在无干扰的状态下进行专注的职业活动，"
    "使认知能力达到极限。这种努力能够创造新价值，提升技能，并且难以被复制。",
    styles['BodyCN']
))
story.append(Paragraph(
    "与之相对的是<b>浮浅工作</b>（Shallow Work）——非高认知需求、事务性的任务，"
    "通常在注意力分散的状态下进行。浮浅工作不会为世界创造太多新价值，且容易被替代。"
    "在数字化转型加速的今天，理解并实践深度工作比以往任何时候都更为重要。",
    styles['BodyCN']
))

# ═════ SECTION 1 ═════
story.append(Paragraph("一、深度工作的四大准则", styles['SectionTitle']))

story.append(Paragraph("准则一：拥抱无聊", styles['SubSectionTitle']))
story.append(Paragraph(
    "不要不断地用手机填满每一个焦躁的时刻，训练大脑对无聊的容忍度。"
    "定期安排远离网络的时段，让大脑适应长时间不受干扰的思考。"
    "研究表明，持续的多任务切换不仅降低效率，还会对大脑产生长期的负面结构改变。"
    "学会与无聊共处，是培养深度专注力的第一步。",
    styles['BodyCN']
))

story.append(Paragraph("准则二：减少浮浅工作", styles['SubSectionTitle']))
story.append(Paragraph(
    "限制那些不需要深度思考的事务性工作。问自己：\"要培训一个聪明的大学毕业生多久才能完成这个任务？\""
    "如果答案很短，那它很可能就是浮浅工作，应该尽量减少、自动化或者委派。"
    "将精力集中在那些真正需要你的专业知识和判断力的事项上。",
    styles['BodyCN']
))

story.append(Paragraph("准则三：关键少数法则", styles['SubSectionTitle']))
story.append(Paragraph(
    "应用 80/20 法则：为职业和个人目标中最重要的 20% 活动投入深度工作，"
    "这能产生 80% 的结果。学会对许多好机会说\"不\"，以便对极少数真正重要的事情说\"是\"。"
    "这不仅是一种时间管理策略，更是一种人生哲学——有选择地深度投入。",
    styles['BodyCN']
))

story.append(Paragraph("准则四：不要用网络来娱乐自己", styles['SubSectionTitle']))
story.append(Paragraph(
    "很多人把业余时间消磨在网络内容的被动消费上。相反，你应该刻意地安排高品质的休闲活动，"
    "如学习一门技能、阅读有深度的书籍、进行有意义的面对面社交。"
    "高质量的休闲能够为下一轮深度工作储备精神能量，形成良性循环。",
    styles['BodyCN']
))

story.append(Paragraph(
    "如果你不决定如何安排你的时间，别人就会替你安排。",
    styles['QuoteBlock']
))

# ═════ SECTION 2 ═════
story.append(Paragraph("二、四种深度工作策略", styles['SectionTitle']))

table_data = [
    [Paragraph('<b>策略</b>', ParagraphStyle('th', fontName='CJKBold', fontSize=9.5, leading=14, textColor=WHITE, alignment=TA_CENTER)),
     Paragraph('<b>模式</b>', ParagraphStyle('th', fontName='CJKBold', fontSize=9.5, leading=14, textColor=WHITE, alignment=TA_CENTER)),
     Paragraph('<b>适合人群</b>', ParagraphStyle('th', fontName='CJKBold', fontSize=9.5, leading=14, textColor=WHITE, alignment=TA_CENTER)),
     Paragraph('<b>代表人物</b>', ParagraphStyle('th', fontName='CJKBold', fontSize=9.5, leading=14, textColor=WHITE, alignment=TA_CENTER))],
    [Paragraph('修道院式', ParagraphStyle('td', fontName='CJK', fontSize=9, leading=13, textColor=DARK_TEXT, alignment=TA_CENTER)),
     Paragraph('完全隔绝外界干扰', ParagraphStyle('td', fontName='CJK', fontSize=9, leading=13, textColor=DARK_TEXT, alignment=TA_CENTER)),
     Paragraph('需要极高创造力的人', ParagraphStyle('td', fontName='CJK', fontSize=9, leading=13, textColor=DARK_TEXT, alignment=TA_CENTER)),
     Paragraph('Neal Stephenson', ParagraphStyle('td', fontName='CJK', fontSize=9, leading=13, textColor=DARK_TEXT, alignment=TA_CENTER))],
    [Paragraph('双模式式', ParagraphStyle('td', fontName='CJK', fontSize=9, leading=13, textColor=DARK_TEXT, alignment=TA_CENTER)),
     Paragraph('在深度期与浮浅期之间切换', ParagraphStyle('td', fontName='CJK', fontSize=9, leading=13, textColor=DARK_TEXT, alignment=TA_CENTER)),
     Paragraph('学术研究者', ParagraphStyle('td', fontName='CJK', fontSize=9, leading=13, textColor=DARK_TEXT, alignment=TA_CENTER)),
     Paragraph('Carl Jung', ParagraphStyle('td', fontName='CJK', fontSize=9, leading=13, textColor=DARK_TEXT, alignment=TA_CENTER))],
    [Paragraph('节奏式', ParagraphStyle('td', fontName='CJK', fontSize=9, leading=13, textColor=DARK_TEXT, alignment=TA_CENTER)),
     Paragraph('每天固定时间段深入工作', ParagraphStyle('td', fontName='CJK', fontSize=9, leading=13, textColor=DARK_TEXT, alignment=TA_CENTER)),
     Paragraph('大多数知识工作者', ParagraphStyle('td', fontName='CJK', fontSize=9, leading=13, textColor=DARK_TEXT, alignment=TA_CENTER)),
     Paragraph('Jerry Seinfeld', ParagraphStyle('td', fontName='CJK', fontSize=9, leading=13, textColor=DARK_TEXT, alignment=TA_CENTER))],
    [Paragraph('记者式', ParagraphStyle('td', fontName='CJK', fontSize=9, leading=13, textColor=DARK_TEXT, alignment=TA_CENTER)),
     Paragraph('随时利用碎片时间深入工作', ParagraphStyle('td', fontName='CJK', fontSize=9, leading=13, textColor=DARK_TEXT, alignment=TA_CENTER)),
     Paragraph('日程安排不固定的人', ParagraphStyle('td', fontName='CJK', fontSize=9, leading=13, textColor=DARK_TEXT, alignment=TA_CENTER)),
     Paragraph('Walter Isaacson', ParagraphStyle('td', fontName='CJK', fontSize=9, leading=13, textColor=DARK_TEXT, alignment=TA_CENTER))],
]

table = Table(table_data, colWidths=[W*0.14, W*0.26, W*0.24, W*0.20])
table.setStyle(TableStyle([
    ('BACKGROUND', (0, 0), (-1, 0), PRIMARY),
    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [WHITE, LIGHT_BG]),
    ('GRID', (0, 0), (-1, -1), 0.5, HexColor('#e0e0e0')),
    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ('TOPPADDING', (0, 0), (-1, -1), 7),
    ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
    ('LEFTPADDING', (0, 0), (-1, -1), 6),
    ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ('LINEBELOW', (0, 0), (-1, 0), 1.5, ACCENT),
]))
story.append(table)
story.append(Paragraph("表1：深度工作四种策略对比", styles['Caption']))

# ═════ SECTION 3 ═════
story.append(Paragraph("三、执行节奏与仪式", styles['SectionTitle']))
story.append(Paragraph(
    "要养成深度工作的习惯，需要在以下四个方面做出精心安排：",
    styles['BodyCN']
))

story.append(Paragraph(
    "\u2022  <b>地点（Where）</b>：选择一个固定的工作场所。可以是书房、"
    "咖啡馆，甚至是公司里某个安静的角落。关键是建立\"在这里就是工作\"的心理联结。",
    styles['BulletItem']
))
story.append(Paragraph(
    "\u2022  <b>时间（When）</b>：设定明确的时间块。例如每天上午 "
    "9:00 - 11:30 为深度工作时间，在此期间关闭所有通讯工具和通知。",
    styles['BulletItem']
))
story.append(Paragraph(
    "\u2022  <b>方式（How）</b>：建立启动仪式。比如泡一杯特定的茶、"
    "整理桌面、写三句当天的意图——这些仪式信号告诉大脑\"深度工作即将开始\"。",
    styles['BulletItem']
))
story.append(Paragraph(
    "\u2022  <b>支持（Support）</b>：对身体的基本关照——保持充足睡眠、"
    "定期运动、健康饮食。深度工作需要大量的精神能量，没有身体基础是不可能持续的。",
    styles['BulletItem']
))

story.append(Spacer(1, 8*mm))

# ═════ SECTION 4 ═════
story.append(Paragraph("四、深度工作的产出衡量", styles['SectionTitle']))
story.append(Paragraph(
    "知识工作者的产出不应以\"工作了多少小时\"来衡量，而应该用以下公式来理解：",
    styles['BodyCN']
))

# Formula highlight
formula_table = Table(
    [[Paragraph("高产出 = 投入时间 × 专注强度", ParagraphStyle(
        'formula', fontName='CJKBold', fontSize=14, leading=20,
        textColor=PRIMARY, alignment=TA_CENTER,
    ))]],
    colWidths=[W*0.58]
)
formula_table.setStyle(TableStyle([
    ('BACKGROUND', (0, 0), (-1, -1), MID_BG),
    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ('TOPPADDING', (0, 0), (-1, -1), 12),
    ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
    ('LINEABOVE', (0, 0), (-1, -1), 1.5, ACCENT),
    ('LINEBELOW', (0, 0), (-1, -1), 1.5, ACCENT),
]))

story.append(Spacer(1, 5*mm))
story.append(formula_table)
story.append(Spacer(1, 5*mm))

story.append(Paragraph(
    "关键洞察：<b>三到四小时的深度专注工作，其产出远超八小时的浮浅工作。</b>"
    "你的大脑在一天中能够进行深度工作的时间是有限的——通常不超过四个小时。"
    "因此，保护这段黄金时间至关重要，它是你真正创造价值的窗口。",
    styles['BodyCN']
))

# ═════ SECTION 5 ═════
story.append(Paragraph("五、结语：选择你的深度", styles['SectionTitle']))
story.append(Paragraph(
    "深度工作不是一种天赋，而是一种可以训练的技能。在一个越来越浮浅的世界里，"
    "那些能够进行深度工作的人将成为稀缺资源，并因此获得丰厚的回报——"
    "无论是经济上的，还是精神上的。",
    styles['BodyCN']
))
story.append(Paragraph(
    "这不仅仅是关于生产力的提升，更是关于生活的质量。当你能够在自己的专业领域"
    "中深入、专注地工作时，你会体验到一种<b>流动状态</b>（Flow），"
    "这是人类幸福感的重要来源之一。",
    styles['BodyCN']
))
story.append(Paragraph(
    "从今天开始，尝试每天留出一个小时的绝对无干扰时间。关掉通知，关掉浏览器，"
    "只做一件事。坚持一周，你会发现自己能做到的远比想象中更多。"
    "深度工作是一门手艺，而你是自己时间唯一的匠人。",
    styles['BodyCN']
))

story.append(Spacer(1, 12*mm))
story.append(HRFlowable(width="100%", thickness=1.2, color=ACCENT, spaceAfter=8*mm))
story.append(Paragraph(
    "深度生活是好的生活。　——　Cal Newport",
    styles['QuoteBlock']
))

# ── Build PDF ──
doc.build(story)
print(f"PDF generated successfully: {output_path}")
print(f"File size: {os.path.getsize(output_path)} bytes")
