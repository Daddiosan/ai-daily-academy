from __future__ import annotations
import argparse
import os
import re
import subprocess
from pathlib import Path
from openai import OpenAI

ROOT = Path(__file__).resolve().parents[1]
LESSONS_DIR = ROOT / "lessons"
TTS_MODEL = os.getenv("TTS_MODEL", "gpt-4o-mini-tts")
TTS_VOICE = os.getenv("TTS_VOICE", "marin")
MAX_CHARS = 1600
AUDIO_SPEED = 1.1

TTS_INSTRUCTIONS = """
自然な日本語の教育Podcastとして話してください。
通勤中に聞き流しても理解できるように、落ち着いた、聞き取りやすいテンポで話してください。
重要な専門用語の前後では少し間を取ってください。
明るく親しみやすい雰囲気にしてください。
ただし、ラジオDJのような過剰な演出は避けてください。
英字の専門用語は、日本人が理解しやすいように自然に発音してください。
箇条書きや見出しについても、文章として自然に聞こえるように読んでください。
"""

def audio_text(text: str) -> str:
    return text.split("[SOURCES]", 1)[0].strip()

def split_long_sentence(sentence: str, max_chars: int) -> list[str]:
    if len(sentence) <= max_chars:
        return [sentence]
    pieces = re.split(r"(?<=[、，,；;：:])", sentence)
    results=[]
    current=""
    for piece in pieces:
        piece=piece.strip()
        if not piece:
            continue
        candidate=(current+piece).strip()
        if len(candidate)<=max_chars:
            current=candidate
            continue
        if current:
            results.append(current)
        while len(piece)>max_chars:
            results.append(piece[:max_chars])
            piece=piece[max_chars:]
        current=piece
    if current:
        results.append(current)
    return results

def split_text(text: str, max_chars: int = MAX_CHARS) -> list[str]:
    paragraphs=[p.strip() for p in re.split(r"\n{2,}",text) if p.strip()]
    chunks=[]
    current=""
    for paragraph in paragraphs:
        sentences=re.split(r"(?<=[。！？!?])",paragraph)
        for sentence in sentences:
            sentence=sentence.strip()
            if not sentence:
                continue
            for safe_sentence in split_long_sentence(sentence,max_chars):
                candidate=current+"\n\n"+safe_sentence if current else safe_sentence
                if len(candidate)<=max_chars:
                    current=candidate
                else:
                    if current:
                        chunks.append(current)
                    current=safe_sentence
    if current:
        chunks.append(current)
    return chunks

def concat_mp3(parts: list[Path], output: Path) -> None:
    list_file=output.parent/"concat.txt"
    lines=[]
    for part in parts:
        path=str(part.resolve()).replace("'","'\\''")
        lines.append(f"file '{path}'")
    list_file.write_text("\n".join(lines),encoding="utf-8")
    subprocess.run(["ffmpeg","-y","-f","concat","-safe","0","-i",str(list_file),"-c","copy",str(output)],check=True)
    list_file.unlink(missing_ok=True)

def change_audio_speed(input_path: Path, output_path: Path) -> None:
    subprocess.run(["ffmpeg","-y","-i",str(input_path),"-filter:a",f"atempo={AUDIO_SPEED}","-vn",str(output_path)],check=True)

def main() -> None:
    parser=argparse.ArgumentParser()
    parser.add_argument("--lesson",required=True,help="Path to lesson txt.")
    args=parser.parse_args()

    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not set.")

    lesson_path=Path(args.lesson)
    if not lesson_path.exists():
        raise RuntimeError(f"Lesson not found: {lesson_path}")

    raw_text=lesson_path.read_text(encoding="utf-8")
    text=audio_text(raw_text)
    chunks=split_text(text)

    for index,chunk in enumerate(chunks,start=1):
        if len(chunk)>MAX_CHARS:
            raise RuntimeError(f"Chunk exceeded MAX_CHARS: {index}")

    output_dir=LESSONS_DIR/(lesson_path.stem+"_audio_parts")
    output_dir.mkdir(parents=True,exist_ok=True)
    client=OpenAI()
    parts=[]

    for index,chunk in enumerate(chunks,start=1):
        part_path=output_dir/f"part_{index:03d}.mp3"
        print(f"TTS {index}/{len(chunks)}")
        with client.audio.speech.with_streaming_response.create(
            model=TTS_MODEL,
            voice=TTS_VOICE,
            input=chunk,
            instructions=TTS_INSTRUCTIONS,
        ) as response:
            response.stream_to_file(part_path)
        parts.append(part_path)

    normal_path=LESSONS_DIR/(lesson_path.stem+"_normal_speed.mp3")
    final_path=LESSONS_DIR/(lesson_path.stem+".mp3")
    concat_mp3(parts,normal_path)
    change_audio_speed(normal_path,final_path)
    normal_path.unlink(missing_ok=True)

    print(f"MP3_PATH={final_path}")
    print(f"AUDIO_SPEED={AUDIO_SPEED}")

if __name__=="__main__":
    main()
