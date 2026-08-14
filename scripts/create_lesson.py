from __future__ import annotations
import argparse, json, os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from openai import OpenAI

ROOT=Path(__file__).resolve().parents[1]
CURRICULUM_PATH=ROOT/"curriculum"/"curriculum.json"
PROGRESS_PATH=ROOT/"curriculum"/"progress.json"
LESSONS_DIR=ROOT/"lessons"
MODEL=os.getenv("LESSON_MODEL","gpt-5.6-terra")
TZ=ZoneInfo("Asia/Tokyo")

def load_json(p): return json.loads(p.read_text(encoding="utf-8"))
def save_json(p,d): p.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding="utf-8")

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--day",type=int,default=None)
    args=ap.parse_args()
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not set")

    c=load_json(CURRICULUM_PATH)
    p=load_json(PROGRESS_PATH)
    override=args.day is not None
    day=args.day if override else int(p.get("current_day",0))+1

    if day<1 or day>len(c["days"]):
        raise RuntimeError("day out of range")

    item=c["days"][day-1]
    prev=c["days"][max(0,day-4):day-1]
    today=datetime.now(TZ).strftime("%Y-%m-%d")
    prevtxt="\n".join(f"Day {x['day']}: {x['topic']}" for x in prev) or "なし（初回）"

    prompt=f"""
あなたは『AI Daily Academy』の主任講師兼編集者です。日本時間の今日の日付は {today}。
Week {item['week']}「{item['week_title']}」 / Day {day}「{item['topic']}」
直近の学習:
{prevtxt}

通勤中に聞き流して理解できる、日本語約30分の音声教材を作ってください。
必須構成:
1. オープニング
2. 前回の復習（初回ならコース説明）
3. 今日の基礎講義
4. 仕組み・応用
5. 身近な具体例
6. 実務での実用例
7. 実装例
8. 今日のAI最新情報 3〜5件
9. 今日の要点整理
10. 1分理解チェック 3〜5問
11. 次回予告

最新情報:
- 必ずWeb検索を使う
- 一次情報を最優先
- 発表日を確認
- 古い情報を今日のニュース扱いしない
- 不確かな点は断定しない
- 今日の学習テーマとの関係を説明

音声向け:
- 自然な日本語の話し言葉
- 目安8,000〜10,000日本語文字
- URLや長いコードを本文で読み上げない
- 冒頭に『この音声はAI生成音声でお届けします』と短く明示
- 過度な煽りを避ける

最後に読み上げ対象外の参考情報を付け、必ず [SOURCES] から開始。
各ニュースについて「タイトル / 発行元 / 発表日 / URL」を列挙。
完成した教材本文だけを出力してください。
"""
    client=OpenAI()
    r=client.responses.create(model=MODEL,tools=[{"type":"web_search"}],input=prompt)
    lesson=r.output_text.strip()

    LESSONS_DIR.mkdir(exist_ok=True)
    stem=f"day_{day:03d}_{today}"
    txt=LESSONS_DIR/f"{stem}.txt"
    meta=LESSONS_DIR/f"{stem}.json"
    txt.write_text(lesson,encoding="utf-8")
    save_json(meta,{"day":day,"week":item["week"],"week_title":item["week_title"],"topic":item["topic"],"date_jst":today,"model":MODEL,"lesson_file":txt.name})

    if not override:
        p["current_day"]=day
        p["last_completed_date"]=today
        completed=p.setdefault("completed",[])
        if not any(x.get("day")==day for x in completed):
            completed.append({"day":day,"date":today,"topic":item["topic"]})
        save_json(PROGRESS_PATH,p)

    print(f"LESSON_PATH={txt}")
    print(f"META_PATH={meta}")

if __name__=="__main__":
    main()
