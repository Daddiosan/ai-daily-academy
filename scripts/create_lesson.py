from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from openai import OpenAI


ROOT = Path(__file__).resolve().parents[1]

CURRICULUM_PATH = ROOT / "curriculum" / "curriculum.json"
PROGRESS_PATH = ROOT / "curriculum" / "progress.json"
LESSONS_DIR = ROOT / "lessons"

MODEL = os.getenv("LESSON_MODEL", "gpt-5.6-terra")
TZ = ZoneInfo("Asia/Tokyo")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def reset_progress() -> None:
    """
    AI Daily Academy の進捗を Day1 開始前の状態へ戻す。
    既存教材ファイルは削除しない。
    """

    progress = {
        "current_day": 0,
        "last_completed_date": None,
        "completed": [],
    }

    save_json(PROGRESS_PATH, progress)

    print("========================================")
    print("AI Daily Academy progress reset.")
    print("Next automatic lesson will be Day 1.")
    print("========================================")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create AI Daily Academy lesson."
    )

    parser.add_argument(
        "--day",
        type=int,
        default=None,
        help="Generate a specific curriculum day without changing progress.",
    )

    parser.add_argument(
        "--reset",
        action="store_true",
        help="Reset curriculum progress to Day 0 before generation.",
    )

    args = parser.parse_args()

    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not set")

    if not CURRICULUM_PATH.exists():
        raise RuntimeError(
            f"Curriculum file not found: {CURRICULUM_PATH}"
        )

    #
    # RESET
    #
    if args.reset:
        reset_progress()

    #
    # Load curriculum
    #
    curriculum = load_json(CURRICULUM_PATH)

    if "days" not in curriculum:
        raise RuntimeError(
            "curriculum.json does not contain 'days'."
        )

    #
    # Load or create progress
    #
    if PROGRESS_PATH.exists():
        progress = load_json(PROGRESS_PATH)
    else:
        progress = {
            "current_day": 0,
            "last_completed_date": None,
            "completed": [],
        }

        save_json(PROGRESS_PATH, progress)

    #
    # Determine day
    #
    override = args.day is not None

    if override:
        day = args.day
        print(f"Creating specified curriculum Day {day}.")
    else:
        day = int(progress.get("current_day", 0)) + 1
        print(f"Creating next curriculum Day {day} automatically.")

    if day < 1 or day > len(curriculum["days"]):
        raise RuntimeError(
            f"Day {day} is outside curriculum range "
            f"1-{len(curriculum['days'])}."
        )

    item = curriculum["days"][day - 1]

    #
    # Previous lessons
    #
    previous_items = curriculum["days"][
        max(0, day - 4): day - 1
    ]

    previous_text = "\n".join(
        f"Day {x['day']}: {x['topic']}"
        for x in previous_items
    )

    if not previous_text:
        previous_text = "なし（初回）"

    #
    # Date
    #
    today = datetime.now(TZ).strftime("%Y-%m-%d")

    #
    # Lesson prompt
    #
    prompt = f"""
あなたは『AI Daily Academy』の主任講師兼編集者です。

日本時間の今日の日付は {today}。

今回のカリキュラム:

Week {item['week']}
「{item['week_title']}」

Day {day}
「{item['topic']}」

直近の学習:

{previous_text}


==============================
教材の目的
==============================

通勤中に聞き流しながら理解できる、
日本語約30分の音声教材を作成してください。

AI初心者でも理解でき、
毎日少しずつAIの基礎・応用・実務活用・最新動向を
体系的に学べる内容にしてください。


==============================
必須構成
==============================

1. オープニング

2. 前回の復習
   ※Day1の場合は
   「AI Daily Academyとは何か」
   「このコースで何を学ぶのか」
   を説明してください。

3. 今日の基礎講義

4. 仕組み・応用

5. 身近な具体例

6. 実務での実用例

7. 実装例

8. 今日のAI最新情報 3〜5件

9. 今日の要点整理

10. 1分理解チェック 3〜5問

11. 次回予告


==============================
最新AI情報のルール
==============================

必ずWeb検索を使用してください。

以下を守ってください。

・一次情報を最優先する
・公式発表を優先する
・発表日を確認する
・古い情報を今日のニュースとして扱わない
・不確かな点は断定しない
・今日の学習テーマとの関係を説明する
・同じニュースを重複して紹介しない


==============================
音声教材としてのルール
==============================

・自然な日本語の話し言葉

・専門用語は必ず分かりやすく説明する

・初心者にも理解できる説明にする

・単なる箇条書きではなく、
  実際の講義のように話す

・目安8,000〜10,000日本語文字

・URLを本文で読み上げない

・長いコードを本文で読み上げない

・コードは考え方を中心に説明する

・冒頭に必ず

「この音声はAI生成音声でお届けします」

と短く明示する

・過度な煽り表現を避ける

・事実と推測を明確に分ける


==============================
参考情報
==============================

教材本文の最後に、
読み上げ対象外の参考情報を付けてください。

必ず

[SOURCES]

から開始してください。

各ニュースについて、

タイトル
発行元
発表日
URL

を記載してください。


==============================
出力
==============================

完成した教材本文だけを出力してください。

説明文や前置きは不要です。
"""

    #
    # OpenAI
    #
    print(
        f"Generating Day {day} lesson "
        f"with model: {MODEL}"
    )

    client = OpenAI()

    response = client.responses.create(
        model=MODEL,
        tools=[
            {
                "type": "web_search",
            }
        ],
        input=prompt,
    )

    lesson = response.output_text.strip()

    if not lesson:
        raise RuntimeError(
            "OpenAI returned an empty lesson."
        )

    #
    # Save lesson
    #
    LESSONS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    stem = f"day_{day:03d}_{today}"

    text_path = LESSONS_DIR / f"{stem}.txt"
    meta_path = LESSONS_DIR / f"{stem}.json"

    text_path.write_text(
        lesson,
        encoding="utf-8",
    )

    metadata = {
        "day": day,
        "week": item["week"],
        "week_title": item["week_title"],
        "topic": item["topic"],
        "date_jst": today,
        "model": MODEL,
        "lesson_file": text_path.name,
    }

    save_json(
        meta_path,
        metadata,
    )

    #
    # Update progress
    #
    if not override:
        progress["current_day"] = day
        progress["last_completed_date"] = today

        completed = progress.setdefault(
            "completed",
            [],
        )

        if not any(
            x.get("day") == day
            for x in completed
        ):
            completed.append(
                {
                    "day": day,
                    "date": today,
                    "topic": item["topic"],
                }
            )

        save_json(
            PROGRESS_PATH,
            progress,
        )

    #
    # GitHub Actions output
    #
    print("")
    print("========================================")
    print("AI Daily Academy lesson created.")
    print("========================================")
    print(f"DAY={day}")
    print(f"DATE={today}")
    print(f"TOPIC={item['topic']}")
    print(f"LESSON_PATH={text_path}")
    print(f"META_PATH={meta_path}")
    print("========================================")


if __name__ == "__main__":
    main()
