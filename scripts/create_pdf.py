from __future__ import annotations
import argparse
import html
import re
from pathlib import Path
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak

ROOT=Path(__file__).resolve().parents[1]
LESSONS_DIR=ROOT/"lessons"
pdfmetrics.registerFont(UnicodeCIDFont("HeiseiKakuGo-W5"))
pdfmetrics.registerFont(UnicodeCIDFont("HeiseiMin-W3"))

def clean_line(text:str)->str:
    text=text.strip()
    text=re.sub(r"^#{1,6}\s*","",text)
    text=re.sub(r"^\*\*(.*?)\*\*$",r"\1",text)
    return text

def is_heading(line:str)->bool:
    original=line.strip()
    if original.startswith("#"): return True
    if re.match(r"^\d+[\.．、]\s*",original): return True
    if re.match(r"^(オープニング|前回の復習|今日の|まとめ|要点|理解チェック|次回予告|最新AI)",original): return True
    return False

def make_pdf(lesson_path:Path)->Path:
    text=lesson_path.read_text(encoding="utf-8")
    output=LESSONS_DIR/f"{lesson_path.stem}.pdf"
    title=lesson_path.stem.replace("_"," ")
    lines=text.splitlines()

    title_style=ParagraphStyle("title",fontName="HeiseiKakuGo-W5",fontSize=20,leading=28,alignment=TA_CENTER,spaceAfter=10)
    subtitle_style=ParagraphStyle("subtitle",fontName="HeiseiMin-W3",fontSize=9,leading=14,alignment=TA_CENTER,spaceAfter=18)
    heading_style=ParagraphStyle("heading",fontName="HeiseiKakuGo-W5",fontSize=13,leading=20,spaceBefore=10,spaceAfter=6)
    body_style=ParagraphStyle("body",fontName="HeiseiMin-W3",fontSize=10.5,leading=18,spaceAfter=7)
    source_style=ParagraphStyle("source",fontName="HeiseiMin-W3",fontSize=8.5,leading=14,spaceAfter=5)

    doc=SimpleDocTemplate(str(output),pagesize=A4,leftMargin=18*mm,rightMargin=18*mm,topMargin=18*mm,bottomMargin=18*mm,title="AI Daily Academy",author="AI Daily Academy")
    story=[
        Paragraph("AI Daily Academy",title_style),
        Paragraph(html.escape(title),subtitle_style),
        Paragraph("通勤用音声教材の文字版 - 最新情報の参照元は末尾に掲載",subtitle_style),
        Spacer(1,4),
    ]

    in_sources=False
    for raw in lines:
        line=raw.strip()
        if not line:
            story.append(Spacer(1,4))
            continue
        if line=="[SOURCES]":
            in_sources=True
            story.append(PageBreak())
            story.append(Paragraph("参考情報・一次情報",heading_style))
            continue
        safe=html.escape(clean_line(line))
        url_match=re.search(r"(https?://[^\s]+)",line)
        if in_sources and url_match:
            url=url_match.group(1).rstrip(").,")
            before=html.escape(line.replace(url_match.group(1),"").strip(" -/"))
            safe=f'{before}<br/><link href="{html.escape(url)}">{html.escape(url)}</link>'
            story.append(Paragraph(safe,source_style))
        elif is_heading(raw):
            story.append(Paragraph(safe,heading_style))
        else:
            story.append(Paragraph(safe,body_style))
    doc.build(story)
    print(f"PDF_PATH={output}")
    return output

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--lesson",required=True)
    args=parser.parse_args()
    lesson_path=Path(args.lesson)
    if not lesson_path.exists():
        raise RuntimeError(f"Lesson not found: {lesson_path}")
    make_pdf(lesson_path)

if __name__=="__main__":
    main()
