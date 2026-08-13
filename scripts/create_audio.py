from __future__ import annotations
import argparse, os, re, subprocess
from pathlib import Path
from openai import OpenAI

ROOT=Path(__file__).resolve().parents[1]
LESSONS_DIR=ROOT/"lessons"
TTS_MODEL=os.getenv("TTS_MODEL","gpt-4o-mini-tts")
TTS_VOICE=os.getenv("TTS_VOICE","marin")
MAX_CHARS=3200
INSTRUCTIONS="""自然な日本語の教育Podcastとして話してください。落ち着いて聞きやすく、
通勤中の聞き流しでも理解しやすいテンポにしてください。重要語の前後は少し間を取り、
過剰な演出は避けてください。英字の専門用語は日本人に理解しやすく発音してください。"""

def spoken_text(t):
    return t.split("[SOURCES]",1)[0].strip()

def split_text(text,max_chars=MAX_CHARS):
    paras=[p.strip() for p in re.split(r"\n{2,}",text) if p.strip()]
    chunks=[]; cur=""
    for p in paras:
        parts=re.split(r"(?<=[。！？!?])",p) if len(p)>max_chars else [p]
        for s in parts:
            s=s.strip()
            if not s: continue
            cand=(cur+"\n\n"+s).strip()
            if len(cand)<=max_chars:
                cur=cand
            else:
                if cur: chunks.append(cur)
                while len(s)>max_chars:
                    chunks.append(s[:max_chars]); s=s[max_chars:]
                cur=s
    if cur: chunks.append(cur)
    return chunks

def concat(parts,out):
    lst=out.parent/"concat.txt"
    lst.write_text("\n".join(f"file '{str(p.resolve())}'" for p in parts),encoding="utf-8")
    subprocess.run(["ffmpeg","-y","-f","concat","-safe","0","-i",str(lst),"-c","copy",str(out)],check=True)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--lesson",default=None)
    args=ap.parse_args()
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not set")
    lesson=Path(args.lesson) if args.lesson else sorted(LESSONS_DIR.glob("day_*.txt"))[-1]
    text=spoken_text(lesson.read_text(encoding="utf-8"))
    chunks=split_text(text)
    partdir=LESSONS_DIR/f"{lesson.stem}_audio_parts"; partdir.mkdir(parents=True,exist_ok=True)
    client=OpenAI(); parts=[]
    for i,chunk in enumerate(chunks,1):
        pp=partdir/f"part_{i:03d}.mp3"
        print(f"TTS {i}/{len(chunks)}")
        with client.audio.speech.with_streaming_response.create(
            model=TTS_MODEL, voice=TTS_VOICE, input=chunk, instructions=INSTRUCTIONS
        ) as r:
            r.stream_to_file(pp)
        parts.append(pp)
    out=LESSONS_DIR/f"{lesson.stem}.mp3"
    concat(parts,out)
    print(out)

if __name__=="__main__": main()
