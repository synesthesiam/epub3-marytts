#!/usr/bin/env python3
import sys
import os
import re
import json
import math
import shutil
import argparse
import logging
import subprocess
from zipfile import ZipFile
from collections import defaultdict
from pathlib import Path

from lxml import etree
from praatio import tgio
from praatio.praatio_scripts import splitAudioOnTier

# -----------------------------------------------------------------------------

TIME_PATTERN = re.compile(r"(\d+):(\d+):(\d+).(\d+)")
REGEX_SUBS = {"default": [(r"’", "'"), (r"[^a-zA-Z0-9.,?!']", " ")]}
SMIL_NAMESPACE = "{http://www.w3.org/ns/SMIL}"

logger = logging.getLogger("prepare")

# -----------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(prog="prepare.py")
    parser.add_argument("epub", help="Path to ePub 3 audio-ebook")
    parser.add_argument("output_dir", help="Path to output directory")
    parser.add_argument(
        "--subs", default="default", help="Name of regex substitution profile"
    )
    parser.add_argument(
        "--debug", action="store_true", help="Print DEBUG messages to console"
    )
    args = parser.parse_args()

    if args.debug:
        logging.basicConfig(level=logging.DEBUG)

    logger.debug(args)

    epub_path = Path(args.epub)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Extract ePub
    logger.info(f"Extracting {epub_path} to {output_dir}")
    with ZipFile(args.epub) as zip_file:
        members = [p for p in zip_file.namelist() if p.startswith("OEBPS")]
        for member in members:
            dest_path = output_dir / member[6:]
            if dest_path.exists():
                logger.debug(f"Skipping {member} ({dest_path} already exists)")
                continue

            logger.debug(f"Extracting {member} to {dest_path}")

            dest_path.parent.mkdir(parents=True, exist_ok=True)
            dest_path.write_bytes(zip_file.read(member))

    # Convert to WAV files
    logger.info("Converting audio")
    audio_dir = output_dir / "Audio"
    wav_dir = output_dir / "Wave"
    mp3_to_wav(audio_dir, wav_dir)

    # Compute intervals
    logger.info("Computing intervals")
    text_dir = output_dir / "Text"
    intervals = get_intervals(text_dir, subs=REGEX_SUBS.get(args.subs, []))

    # TextGrid alignments
    logger.info("Writing alignments")
    align_dir = output_dir / "Align"
    align_dir.mkdir(parents=True, exist_ok=True)
    write_intervals(wav_dir, align_dir, intervals)

    # MaryTTS project
    mary_dir = output_dir / "marytts"
    mary_dir.mkdir(parents=True, exist_ok=True)

    # build/text
    mary_text_dir = mary_dir / "build" / "text"
    mary_text_dir.mkdir(parents=True, exist_ok=True)

    for src_text_path in align_dir.glob("**/*.txt"):
        dest_text_path = mary_text_dir / src_text_path.name
        if dest_text_path.exists():
            dest_text_path.unlink()

        dest_text_path.symlink_to(src_text_path.absolute())
        logger.debug(f"{dest_text_path} -> {src_text_path}")

    # wav
    mary_wav_dir = mary_dir / "wav"
    mary_wav_dir.mkdir(parents=True, exist_ok=True)

    for src_wav_path in align_dir.glob("**/*.wav"):
        dest_wav_path = mary_wav_dir / src_wav_path.name

        if dest_wav_path.exists():
            dest_wav_path.unlink()

        dest_wav_path.symlink_to(src_wav_path.absolute())
        logger.debug(f"{dest_wav_path} -> {src_wav_path}")

# -----------------------------------------------------------------------------


def mp3_to_wav(audio_dir, wav_dir):
    for mp3_path in audio_dir.glob("*.mp3"):
        if not mp3_path.is_file():
            continue

        wav_path = wav_dir / f"{mp3_path.stem}.wav"
        if wav_path.exists():
            logger.debug(f"Skipping {wav_path} (already exists)")
            continue

        wav_path.parent.mkdir(parents=True, exist_ok=True)

        ffmpeg_cmd = [
            "ffmpeg",
            "-i",
            str(mp3_path),
            "-acodec",
            "pcm_s16le",
            "-ar",
            "16000",
            "-ac",
            "1",
            wav_path,
        ]

        logger.debug(ffmpeg_cmd)
        subprocess.check_call(ffmpeg_cmd)


def get_intervals(text_dir, subs):
    intervals = defaultdict(list)
    for smil_path in text_dir.glob("*.smil"):
        with open(smil_path, "r") as smil_file:
            smil_root = etree.parse(smil_file)

        xhtml_path = text_dir / f"{smil_path.stem}"
        with open(xhtml_path, "r") as xhtml_file:
            xhtml_root = etree.parse(xhtml_file)

        for par in smil_root.findall(f"//{SMIL_NAMESPACE}par"):
            src = par.find(f"{SMIL_NAMESPACE}text").attrib["src"]
            src_id = src.split("#")[1]
            audio = par.find(f"{SMIL_NAMESPACE}audio")

            audio_path = Path(audio.attrib["src"])
            start_time = to_time(audio.attrib["clipBegin"])
            end_time = to_time(audio.attrib["clipEnd"])

            if end_time > start_time:
                span = xhtml_root.xpath(f"//*[@id='{src_id}']")[0]
                text = span.text.strip()

                # Do substitutions
                for sub in subs:
                    text = re.sub(sub[0], sub[1], text)

                interval = tgio.Interval(start_time, end_time, text)
                intervals[audio_path.stem].append(interval)

    return intervals


def write_intervals(wav_dir, align_dir, intervals):
    for audio_name, entries in intervals.items():
        audio_align_dir = align_dir / audio_name
        audio_align_dir.mkdir(parents=True, exist_ok=True)

        grid = tgio.Textgrid()
        tier = tgio.IntervalTier("sentences", entries)
        grid.addTier(tier)

        grid_path = audio_align_dir / f"{audio_name}.TextGrid"
        grid.save(str(grid_path))
        logger.debug(f"Wrote {grid_path}")

        # Split audio
        wav_path = wav_dir / f"{audio_name}.wav"
        audio_wav_dir = audio_align_dir / "wav"
        logger.debug(f"Splitting {wav_path}")
        splitAudioOnTier(str(wav_path), str(grid_path), "sentences", str(audio_wav_dir))

        # Write transcriptions
        text_align_dir = audio_align_dir / "text"
        text_align_dir.mkdir(parents=True, exist_ok=True)

        num_zeros = int(math.ceil(math.log10(len(entries))))
        n_format = "{0:0" + str(num_zeros) + "d}"
        for i, interval in enumerate(entries):
            n = n_format.format(i)
            text_path = text_align_dir / f"{audio_name}_{n}.txt"
            text_path.write_text(interval.label.strip())
            logger.debug(f"Wrote {text_path}")


def to_time(time_str):
    match = TIME_PATTERN.match(time_str.strip())
    minutes = int(match.group(2))
    seconds = int(match.group(3))
    milliseconds = int(match.group(4))
    return (minutes * 60) + seconds + (milliseconds / 1000)


# -----------------------------------------------------------------------------

if __name__ == "__main__":
    main()
