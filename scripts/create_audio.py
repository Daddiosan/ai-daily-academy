from __future__ import annotations

import argparse
import os
import re
import subprocess
from pathlib import Path

from openai import OpenAI


ROOT = Path(__file__).resolve().parents[1]
LESSONS_DIR = ROOT / "lessons"

TTS_MODEL = os.getenv(
    "TTS_MODEL",
    "gpt-4o-mini-tts",
)

TTS_VOICE = os.getenv(
    "TTS_VOICE",
    "marin",
)

# TTS API の入力上限に十分な余裕を持たせる
MAX_CHARS = 1600


TTS_INSTRUCTIONS = """
自然な日本語の教育Podcastとして話してください。

通勤中に聞き流しても理解できるように、
落ち着いた、聞き取りやすいテンポで話してください。

重要な専門用語の前後では少し間を取ってください。

明るく親しみやすい雰囲気にしてください。
ただし、ラジオDJのような過剰な演出は避けてください。

英字の専門用語は、日本人が理解しやすいように
自然に発音してください。

箇条書きや見出しについても、
文章として自然に聞こえるように読んでください。
"""


def audio_text(text: str) -> str:
    """
    [SOURCES] 以降は参考情報なので音声化しない。
    """

    return text.split(
        "[SOURCES]",
        1,
    )[0].strip()


def split_long_sentence(
    sentence: str,
    max_chars: int,
) -> list[str]:

    """
    1文だけで上限を超えた場合の安全処理。
    読点などを利用して、できるだけ自然に分割する。
    """

    if len(sentence) <= max_chars:
        return [sentence]

    pieces = re.split(
        r"(?<=[、，,；;：:])",
        sentence,
    )

    results = []
    current = ""

    for piece in pieces:

        piece = piece.strip()

        if not piece:
            continue

        candidate = (
            current + piece
        ).strip()

        if len(candidate) <= max_chars:
            current = candidate
            continue

        if current:
            results.append(current)

        # それでも長すぎる場合は
        # 最終手段として文字数で分割
        while len(piece) > max_chars:

            results.append(
                piece[:max_chars]
            )

            piece = piece[
                max_chars:
            ]

        current = piece

    if current:
        results.append(current)

    return results


def split_text(
    text: str,
    max_chars: int = MAX_CHARS,
) -> list[str]:

    """
    教材本文をTTS用の安全なサイズへ分割する。

    優先順位:
    1. 段落
    2. 文末
    3. 読点
    4. 文字数
    """

    paragraphs = [
        p.strip()
        for p in re.split(
            r"\n{2,}",
            text,
        )
        if p.strip()
    ]

    chunks = []
    current = ""

    for paragraph in paragraphs:

        sentences = re.split(
            r"(?<=[。！？!?])",
            paragraph,
        )

        for sentence in sentences:

            sentence = sentence.strip()

            if not sentence:
                continue

            safe_sentences = split_long_sentence(
                sentence,
                max_chars,
            )

            for safe_sentence in safe_sentences:

                if current:

                    candidate = (
                        current
                        + "\n\n"
                        + safe_sentence
                    )

                else:

                    candidate = safe_sentence

                if len(candidate) <= max_chars:

                    current = candidate

                else:

                    if current:
                        chunks.append(current)

                    current = safe_sentence

    if current:
        chunks.append(current)

    return chunks


def concat_mp3(
    parts: list[Path],
    output: Path,
) -> None:

    """
    ffmpegを使用してMP3パーツを
    1本のMP3へ結合する。
    """

    list_file = (
        output.parent
        / "concat.txt"
    )

    lines = []

    for part in parts:

        path = str(
            part.resolve()
        )

        # ffmpeg concat用
        path = path.replace(
            "'",
            "'\\''",
        )

        lines.append(
            f"file '{path}'"
        )

    list_file.write_text(
        "\n".join(lines),
        encoding="utf-8",
    )

    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(list_file),
            "-c",
            "copy",
            str(output),
        ],
        check=True,
    )


def main() -> None:

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--lesson",
        default=None,
        help=(
            "Path to lesson txt. "
            "Newest lesson is used "
            "if omitted."
        ),
    )

    args = parser.parse_args()

    if not os.getenv(
        "OPENAI_API_KEY"
    ):

        raise RuntimeError(
            "OPENAI_API_KEY is not set."
        )

    # -------------------------
    # 教材ファイル取得
    # -------------------------

    if args.lesson:

        lesson_path = Path(
            args.lesson
        )

    else:

        candidates = sorted(
            LESSONS_DIR.glob(
                "day_*.txt"
            )
        )

        if not candidates:

            raise RuntimeError(
                "No lesson txt found."
            )

        lesson_path = candidates[-1]

    print(
        f"Lesson: {lesson_path}"
    )

    # -------------------------
    # 教材読み込み
    # -------------------------

    raw_text = (
        lesson_path.read_text(
            encoding="utf-8"
        )
    )

    text = audio_text(
        raw_text
    )

    # -------------------------
    # TTS用分割
    # -------------------------

    chunks = split_text(
        text
    )

    print(
        f"Total characters: "
        f"{len(text)}"
    )

    print(
        f"TTS chunks: "
        f"{len(chunks)}"
    )

    # 安全チェック
    for index, chunk in enumerate(
        chunks,
        start=1,
    ):

        print(
            f"Chunk {index}: "
            f"{len(chunk)} chars"
        )

        if len(chunk) > MAX_CHARS:

            raise RuntimeError(
                "Chunk exceeded "
                f"MAX_CHARS: {index}"
            )

    # -------------------------
    # 音声パーツ保存先
    # -------------------------

    output_dir = (
        LESSONS_DIR
        / (
            lesson_path.stem
            + "_audio_parts"
        )
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    # -------------------------
    # OpenAI
    # -------------------------

    client = OpenAI()

    parts = []

    # -------------------------
    # TTS生成
    # -------------------------

    for index, chunk in enumerate(
        chunks,
        start=1,
    ):

        part_path = (
            output_dir
            / f"part_{index:03d}.mp3"
        )

        print(
            f"TTS "
            f"{index}/{len(chunks)}"
        )

        with (
            client.audio.speech
            .with_streaming_response
            .create(
                model=TTS_MODEL,
                voice=TTS_VOICE,
                input=chunk,
                instructions=(
                    TTS_INSTRUCTIONS
                ),
            )
        ) as response:

            response.stream_to_file(
                part_path
            )

        parts.append(
            part_path
        )

    # -------------------------
    # MP3結合
    # -------------------------

    final_path = (
        LESSONS_DIR
        / (
            lesson_path.stem
            + ".mp3"
        )
    )

    concat_mp3(
        parts,
        final_path,
    )

    print("")
    print(
        "========================="
    )
    print(
        "AI Daily Academy MP3"
    )
    print(
        "successfully created."
    )
    print(
        "========================="
    )
    print(
        final_path
    )


if __name__ == "__main__":
    main()
