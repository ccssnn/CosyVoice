#!/usr/bin/env python3
import argparse
import html
import json
import re
import sys
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from bs4 import BeautifulSoup

ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR))
sys.path.append(str(ROOT_DIR / "third_party" / "Matcha-TTS"))

SITE_URL = "https://funaudiollm.github.io/cosyvoice3/"
SYSTEM_PROMPT_PREFIX = "You are a helpful assistant.<|endofprompt|>"

SECTION_TITLES = {
    "zero_shot": "Zero-shot In-context Generation",
    "mixed_lingual": "Mixed-lingual In-context Generation",
    "emotion": "Emotionally Expressive Voice Generation",
    "dialect": "Chinese dialect Voice Generation",
    "cross_lingual": "Cross-lingual In-context Generation",
    "post_training": "Post-training",
    "hotfix": "Hotfix Capability",
    "instruct": "Instructed Voice Generation",
    "target_speaker_ce": "Target Speaker Fine-tune Models / Chinese and English",
    "target_speaker_minority": "Target Speaker Fine-tune Models / Minority Language",
    "target_speaker_transfer": "Target Speaker Fine-tune Models / Instruct ability transfer",
}

SECTION_DIRS = {
    "zero_shot": "01_zero_shot_in_context_generation",
    "mixed_lingual": "02_mixed_lingual_in_context_generation",
    "emotion": "03_emotionally_expressive_voice_generation",
    "dialect": "04_chinese_dialect_voice_generation",
    "cross_lingual": "05_cross_lingual_in_context_generation",
    "post_training": "06_post_training",
    "hotfix": "07_hotfix_capability",
    "instruct": "08_instructed_voice_generation",
    "target_speaker_ce": "09_target_speaker_fine_tune_models/01_chinese_and_english",
    "target_speaker_minority": "09_target_speaker_fine_tune_models/02_minority_language",
    "target_speaker_transfer": "09_target_speaker_fine_tune_models/03_instruct_ability_transfer",
}

ZERO_SHOT_SLUGS = [
    "zh",
    "hard_zh",
    "en",
    "hard_en",
    "ja",
    "ko",
    "de",
    "es",
    "fr",
    "it",
    "ru",
]

POST_TRAINING_SLUGS = ["zh", "en", "ja", "ko", "ru"]

CROSS_TARGET_LANGS = {
    "zh_m": ["ja", "ko", "ru", "fr"],
    "en_m": ["ja", "ko", "ru", "fr"],
    "ja_m": ["zh", "en", "ru", "fr"],
    "ko_m": ["zh", "en", "ru", "fr"],
    "zh_f": ["ja", "ko", "ru", "fr"],
    "en_f": ["ja", "ko", "ru", "fr"],
    "ja_f": ["zh", "en", "ru", "fr"],
    "ko_f": ["zh", "en", "ru", "fr"],
}

SLUG_OVERRIDES = {
    "中立": "neutral",
    "生气": "angry",
    "伤心": "sad",
    "高兴": "happy",
    "粤语": "cantonese",
    "细粒度控制": "fine_grained_control",
    "恐惧": "fearful",
    "重庆话": "chongqing_dialect",
    "轻声": "soft",
    "惊讶": "surprised",
    "西安话": "xian_dialect",
    "小猪佩奇": "peppa",
}

INSTRUCT_TEXT_MAP = {
    "生气": "You are a helpful assistant. 请非常生气地说一句话。<|endofprompt|>",
    "伤心": "You are a helpful assistant. 请非常伤心地说一句话。<|endofprompt|>",
    "粤语": "You are a helpful assistant. 请用广东话表达。<|endofprompt|>",
    "恐惧": "You are a helpful assistant. 请非常恐惧地说一句话。<|endofprompt|>",
    "高兴": "You are a helpful assistant. 请非常开心地说一句话。<|endofprompt|>",
    "重庆话": "You are a helpful assistant. 请用重庆话表达。<|endofprompt|>",
    "轻声": "You are a helpful assistant. Please say a sentence in a very soft voice.<|endofprompt|>",
    "惊讶": "You are a helpful assistant. 请非常惊讶地说一句话。<|endofprompt|>",
    "西安话": "You are a helpful assistant. 请用西安话表达。<|endofprompt|>",
    "小猪佩奇": "You are a helpful assistant. 我想体验一下小猪佩奇风格，可以吗？<|endofprompt|>",
    "Angry": "You are a helpful assistant. Please say a sentence as angrily as possible.<|endofprompt|>",
    "Fearful": "You are a helpful assistant. Please say a sentence in a very fearful tone.<|endofprompt|>",
    "Fast": "You are a helpful assistant. Please say a sentence as fast as possible.<|endofprompt|>",
    "Soft": "You are a helpful assistant. Please say a sentence in a very soft voice.<|endofprompt|>",
}


@dataclass(frozen=True)
class DemoCase:
    section_key: str
    section_title: str
    relative_output_dir: str
    file_stem: str
    mode: str
    tts_text: str
    prompt_site_path: str = ""
    prompt_text: str = ""
    prompt_label: str = ""
    instruct_text: str = ""
    speaker: str = ""
    reference_site_path: str = ""
    notes: str = ""


@dataclass
class CaseResult:
    case_id: str
    section_key: str
    section_title: str
    relative_output_dir: str
    mode: str
    status: str
    reason: str = ""
    prompt_source: str = ""
    prompt_path: str = ""
    speaker: str = ""
    reference_source: str = ""
    output_paths: list[str] | None = None
    notes: str = ""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Reproduce all examples from https://funaudiollm.github.io/cosyvoice3 in categorized folders."
    )
    parser.add_argument("--model-dir", default="pretrained_models/Fun-CosyVoice3-0.5B")
    parser.add_argument("--output-dir", default="outputs/demo_all")
    parser.add_argument(
        "--site-html-cache",
        default="outputs/demo_all_site/cosyvoice3.html",
        help="Local cache for the downloaded demo page HTML.",
    )
    parser.add_argument(
        "--refresh-site-html",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Refresh the cached CosyVoice3 demo HTML before parsing.",
    )
    parser.add_argument(
        "--prompt-cache-dir",
        default="asset/cosyvoice3_prompts",
        help="Cache directory for source prompt audio downloaded from the demo site.",
    )
    parser.add_argument(
        "--sections",
        nargs="*",
        default=["all"],
        choices=["all", *SECTION_TITLES.keys()],
    )
    parser.add_argument(
        "--download-site-prompts",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Download prompt audio from the CosyVoice3 demo website when needed.",
    )
    parser.add_argument(
        "--download-reference-audio",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="When a case cannot be synthesized locally, download the website reference audio if available.",
    )
    parser.add_argument(
        "--allow-fallback-prompts",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Use --fallback-prompt-wav when a site prompt cannot be resolved.",
    )
    parser.add_argument(
        "--fallback-prompt-wav",
        default="asset/zero_shot_prompt.wav",
        help="Fallback prompt wav for tables without an exposed prompt or when download fails.",
    )
    parser.add_argument("--speed", type=float, default=1.0)
    parser.add_argument(
        "--skip-existing",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Skip a case if its main output file already exists.",
    )
    parser.add_argument("--max-cases", type=int, default=0)
    parser.add_argument(
        "--dry-run",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Parse the site and write the manifest only, without loading the model.",
    )
    parser.add_argument(
        "--transfer-speaker",
        default="",
        help="Optional speaker id for the 'Instruct ability transfer' subgroup.",
    )
    return parser.parse_args()


def clean_heading(text: str) -> str:
    return " ".join(text.replace("\xa0", " ").split())


def slugify(text: str) -> str:
    text = text.lower().replace("&", "and")
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text or "item"


def safe_slug(text: str) -> str:
    return SLUG_OVERRIDES.get(text, slugify(text))


def contains_cjk(text: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", text))


def decode_style_text(text: str) -> str:
    return text.replace("&lt", "<").replace("&gt", ">")


def ensure_endofprompt(text: str) -> str:
    return text if "<|endofprompt|>" in text else f"{SYSTEM_PROMPT_PREFIX}{text}"


def html_fragment_to_plain(fragment: str) -> str:
    text = html.unescape(fragment)
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("\xa0", " ")
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    return text.strip()


def split_first_line(fragment: str) -> tuple[str, str, str]:
    parts = [part.strip() for part in fragment.split("\n") if part.strip()]
    if not parts:
        return "", "", ""
    label = html_fragment_to_plain(parts[0])
    body_html = "\n".join(parts[1:]).strip()
    body_text = html_fragment_to_plain(body_html)
    return label, body_text, body_html


def site_url(relative_path: str) -> str:
    return SITE_URL.rstrip("/") + "/" + relative_path.lstrip("/")


def read_or_download_text(url: str, cache_path: Path, refresh: bool) -> str:
    if cache_path.exists() and not refresh:
        return cache_path.read_text()
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        content = response.read().decode("utf-8")
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(content)
    return content


def clean_cell_html(td) -> str:
    fragment = BeautifulSoup(str(td), "html.parser")
    td_node = fragment.find("td")
    for audio in td_node.find_all("audio"):
        audio.decompose()
    for br in td_node.find_all("br"):
        br.replace_with("\n")
    return td_node.decode_contents(formatter="html").strip()


def cell_payload(td) -> dict:
    source = td.find("source")
    cell_html = clean_cell_html(td)
    return {
        "text": html_fragment_to_plain(cell_html),
        "html": cell_html,
        "audio_src": source["src"] if source else None,
        "rowspan": int(td.get("rowspan", "1")),
    }


def expand_table(table) -> tuple[list[str], list[list[dict]]]:
    rows: list[list[dict]] = []
    span_map: dict[int, dict] = {}
    trs = table.find_all("tr")
    headers = [clean_heading(th.get_text(" ", strip=True)) for th in trs[0].find_all("th")]
    for tr in trs[1:]:
        row: list[dict] = []
        col_idx = 0
        while span_map.get(col_idx):
            info = span_map[col_idx]
            row.append(info["cell"])
            info["remaining"] -= 1
            if info["remaining"] == 0:
                del span_map[col_idx]
            col_idx += 1
        for td in tr.find_all("td", recursive=False):
            while span_map.get(col_idx):
                info = span_map[col_idx]
                row.append(info["cell"])
                info["remaining"] -= 1
                if info["remaining"] == 0:
                    del span_map[col_idx]
                col_idx += 1
            cell = cell_payload(td)
            row.append(cell)
            rowspan = int(td.get("rowspan", "1"))
            if rowspan > 1:
                span_map[col_idx] = {"cell": cell, "remaining": rowspan - 1}
            col_idx += 1
        rows.append(row)
    return headers, rows


def find_section_table(soup: BeautifulSoup, title: str):
    for h2 in soup.find_all("h2"):
        if clean_heading(h2.get_text(" ", strip=True)) == title:
            return h2.find_next("table")
    raise ValueError(f"section not found: {title}")


def parse_site_snapshot(site_html: str) -> dict:
    soup = BeautifulSoup(site_html, "html.parser")
    snapshot = {
        "site_url": SITE_URL,
        "zero_shot": [],
        "mixed_lingual": {"prompt_site_path": "", "prompt_text": "", "texts": []},
        "emotion": [],
        "dialect": [],
        "cross_lingual": [],
        "post_training": [],
        "hotfix": [],
        "instruct": [],
        "target_speaker": {
            "chinese_and_english": [],
            "minority_language": [],
            "instruct_transfer": [],
        },
    }

    _, rows = expand_table(find_section_table(soup, "Zero-shot In-context Generation"))
    for row in rows:
        snapshot["zero_shot"].append(
            {
                "label": row[0]["text"],
                "prompt_site_path": row[1]["audio_src"],
                "prompt_text": row[1]["text"],
                "tts_text": row[2]["text"],
            }
        )

    _, rows = expand_table(find_section_table(soup, "Mixed-lingual In-context Generation"))
    snapshot["mixed_lingual"]["prompt_site_path"] = rows[0][0]["audio_src"]
    snapshot["mixed_lingual"]["prompt_text"] = rows[0][0]["text"]
    for row in rows:
        snapshot["mixed_lingual"]["texts"].append(row[1]["text"])

    _, rows = expand_table(find_section_table(soup, "Emotionally Expressive Voice Generation"))
    for row in rows:
        snapshot["emotion"].append(
            {
                "emotion": row[0]["text"],
                "prompt_site_path": row[1]["audio_src"],
                "prompt_text": row[1]["text"],
                "tts_text": row[2]["text"],
            }
        )

    _, rows = expand_table(find_section_table(soup, "Chinese dialect Voice Generation"))
    for row in rows:
        snapshot["dialect"].append(
            {
                "dialect": row[0]["text"],
                "prompt_site_path": row[1]["audio_src"],
                "prompt_text": row[1]["text"],
                "tts_text": row[2]["text"],
            }
        )

    _, rows = expand_table(find_section_table(soup, "Cross-lingual In-context Generation"))
    for row in rows:
        snapshot["cross_lingual"].append(
            {
                "gender": row[0]["text"],
                "prompt_id": Path(row[1]["audio_src"]).stem,
                "prompt_site_path": row[1]["audio_src"],
                "prompt_text": row[1]["text"],
                "tts_texts": [cell["text"] for cell in row[2:6]],
            }
        )

    _, rows = expand_table(find_section_table(soup, "Post-training"))
    for row in rows:
        snapshot["post_training"].append(
            {
                "prompt_site_path": row[0]["audio_src"],
                "prompt_text": row[0]["text"],
                "tts_text": row[1]["text"],
            }
        )

    _, rows = expand_table(find_section_table(soup, "Hotfix Capability"))
    for idx, row in enumerate(rows, 1):
        snapshot["hotfix"].append(
            {
                "id": f"hotfix_{idx:02d}",
                "before_text": row[0]["text"],
                "after_text": row[2]["text"],
            }
        )

    _, rows = expand_table(find_section_table(soup, "Instructed Voice Generation"))
    for idx, row in enumerate(rows, 1):
        prompt_label, prompt_text, _ = split_first_line(row[0]["html"])
        variants = []
        for cell in row[1:]:
            label, text, body_html = split_first_line(cell["html"])
            variants.append(
                {
                    "label": label,
                    "text": body_html if label == "细粒度控制" else text,
                }
            )
        snapshot["instruct"].append(
            {
                "group_id": f"group_{idx}",
                "prompt_label": prompt_label,
                "prompt_site_path": row[0]["audio_src"],
                "prompt_text": prompt_text,
                "variants": variants,
            }
        )

    target_h2 = None
    for h2 in soup.find_all("h2"):
        if clean_heading(h2.get_text(" ", strip=True)) == "Target Speaker Fine-tune Models":
            target_h2 = h2
            break
    if target_h2 is None:
        raise ValueError("Target Speaker Fine-tune Models section not found")

    chinese_table = target_h2.find_next("h3").find_next("table")
    _, rows = expand_table(chinese_table)
    for row in rows:
        snapshot["target_speaker"]["chinese_and_english"].append(
            {
                "speaker": row[0]["text"],
                "tts_text": row[1]["text"],
                "reference_site_path": row[2]["audio_src"],
            }
        )

    minority_table = chinese_table.find_next("h3").find_next("table")
    _, rows = expand_table(minority_table)
    for row in rows:
        snapshot["target_speaker"]["minority_language"].append(
            {
                "language": row[0]["text"],
                "tts_text": row[1]["text"],
                "speakers": [
                    {"speaker": "longwan", "reference_site_path": row[2]["audio_src"]},
                    {"speaker": "longshu", "reference_site_path": row[3]["audio_src"]},
                ],
            }
        )

    transfer_table = minority_table.find_next("h3").find_next("table")
    _, rows = expand_table(transfer_table)
    for idx, row in enumerate(rows, 1):
        snapshot["target_speaker"]["instruct_transfer"].append(
            {
                "id": f"transfer_{idx:02d}",
                "styled_text": decode_style_text(row[0]["text"]),
                "reference_site_path": row[1]["audio_src"],
            }
        )

    return snapshot


def build_cases(snapshot: dict, transfer_speaker: str) -> list[DemoCase]:
    cases: list[DemoCase] = []

    for idx, item in enumerate(snapshot["zero_shot"], 1):
        cases.append(
            DemoCase(
                section_key="zero_shot",
                section_title=SECTION_TITLES["zero_shot"],
                relative_output_dir=SECTION_DIRS["zero_shot"],
                file_stem=f"{idx:02d}_{ZERO_SHOT_SLUGS[idx - 1]}",
                mode="zero_shot",
                tts_text=item["tts_text"],
                prompt_site_path=item["prompt_site_path"],
                prompt_text=item["prompt_text"],
                prompt_label=item["label"],
                reference_site_path="",
            )
        )

    mixed = snapshot["mixed_lingual"]
    for idx, text in enumerate(mixed["texts"], 1):
        cases.append(
            DemoCase(
                section_key="mixed_lingual",
                section_title=SECTION_TITLES["mixed_lingual"],
                relative_output_dir=SECTION_DIRS["mixed_lingual"],
                file_stem=f"{idx:02d}_mix_{idx:02d}",
                mode="zero_shot",
                tts_text=text,
                prompt_site_path=mixed["prompt_site_path"],
                prompt_text=mixed["prompt_text"],
                reference_site_path="",
            )
        )

    emotion_counts: dict[str, int] = {}
    for item in snapshot["emotion"]:
        emotion_slug = slugify(item["emotion"])
        emotion_counts[emotion_slug] = emotion_counts.get(emotion_slug, 0) + 1
        lang = "zh" if contains_cjk(item["prompt_text"]) or contains_cjk(item["tts_text"]) else "en"
        cases.append(
            DemoCase(
                section_key="emotion",
                section_title=SECTION_TITLES["emotion"],
                relative_output_dir=f"{SECTION_DIRS['emotion']}/{emotion_slug}",
                file_stem=f"{emotion_counts[emotion_slug]:02d}_{lang}",
                mode="zero_shot",
                tts_text=item["tts_text"],
                prompt_site_path=item["prompt_site_path"],
                prompt_text=item["prompt_text"],
                prompt_label=item["emotion"],
                reference_site_path="",
            )
        )

    for idx, item in enumerate(snapshot["dialect"], 1):
        cases.append(
            DemoCase(
                section_key="dialect",
                section_title=SECTION_TITLES["dialect"],
                relative_output_dir=SECTION_DIRS["dialect"],
                file_stem=f"{idx:02d}_{slugify(item['dialect'])}",
                mode="zero_shot",
                tts_text=item["tts_text"],
                prompt_site_path=item["prompt_site_path"],
                prompt_text=item["prompt_text"],
                prompt_label=item["dialect"],
                reference_site_path="",
            )
        )

    for group in snapshot["cross_lingual"]:
        prompt_lang = group["prompt_id"].split("_", 1)[0]
        gender = group["gender"].lower()
        relative_dir = f"{SECTION_DIRS['cross_lingual']}/{gender}_{prompt_lang}"
        for idx, (target_lang, text) in enumerate(zip(CROSS_TARGET_LANGS[group["prompt_id"]], group["tts_texts"]), 1):
            cases.append(
                DemoCase(
                    section_key="cross_lingual",
                    section_title=SECTION_TITLES["cross_lingual"],
                    relative_output_dir=relative_dir,
                    file_stem=f"{idx:02d}_to_{target_lang}",
                    mode="cross_lingual",
                    tts_text=text,
                    prompt_site_path=group["prompt_site_path"],
                    prompt_label=group["prompt_text"],
                    reference_site_path="",
                    notes=f"Prompt transcript: {group['prompt_text']}",
                )
            )

    for idx, item in enumerate(snapshot["post_training"], 1):
        cases.append(
            DemoCase(
                section_key="post_training",
                section_title=SECTION_TITLES["post_training"],
                relative_output_dir=SECTION_DIRS["post_training"],
                file_stem=f"{idx:02d}_{POST_TRAINING_SLUGS[idx - 1]}",
                mode="zero_shot",
                tts_text=item["tts_text"],
                prompt_site_path=item["prompt_site_path"],
                prompt_text=item["prompt_text"],
                reference_site_path="",
            )
        )

    for idx, item in enumerate(snapshot["hotfix"], 1):
        for variant_name, text in [("before", item["before_text"]), ("after", item["after_text"])]:
            cases.append(
                DemoCase(
                    section_key="hotfix",
                    section_title=SECTION_TITLES["hotfix"],
                    relative_output_dir=SECTION_DIRS["hotfix"],
                    file_stem=f"{idx:02d}_{variant_name}",
                    mode="cross_lingual",
                    tts_text=text,
                    reference_site_path="",
                    notes="Uses the fallback prompt wav because the website does not expose a dedicated prompt for this table.",
                )
            )

    for group in snapshot["instruct"]:
        relative_dir = f"{SECTION_DIRS['instruct']}/{group['group_id']}_{safe_slug(group['prompt_label'])}"
        for idx, variant in enumerate(group["variants"], 1):
            label = variant["label"]
            mode = "cross_lingual" if label == "细粒度控制" else "instruct2"
            cases.append(
                DemoCase(
                    section_key="instruct",
                    section_title=SECTION_TITLES["instruct"],
                    relative_output_dir=relative_dir,
                    file_stem=f"{idx:02d}_{safe_slug(label)}",
                    mode=mode,
                    tts_text=variant["text"],
                    prompt_site_path=group["prompt_site_path"],
                    prompt_text=group["prompt_text"],
                    prompt_label=group["prompt_label"],
                    instruct_text=INSTRUCT_TEXT_MAP.get(label, ""),
                    reference_site_path="",
                )
            )

    for idx, item in enumerate(snapshot["target_speaker"]["chinese_and_english"], 1):
        cases.append(
            DemoCase(
                section_key="target_speaker_ce",
                section_title=SECTION_TITLES["target_speaker_ce"],
                relative_output_dir=SECTION_DIRS["target_speaker_ce"],
                file_stem=f"{idx:02d}_{slugify(item['speaker'])}",
                mode="sft",
                tts_text=item["tts_text"],
                speaker=item["speaker"],
                reference_site_path=item["reference_site_path"],
            )
        )

    minority_counts = {"longwan": 0, "longshu": 0}
    for item in snapshot["target_speaker"]["minority_language"]:
        language_slug = slugify(item["language"])
        for speaker_item in item["speakers"]:
            speaker = speaker_item["speaker"]
            minority_counts[speaker] += 1
            cases.append(
                DemoCase(
                    section_key="target_speaker_minority",
                    section_title=SECTION_TITLES["target_speaker_minority"],
                    relative_output_dir=SECTION_DIRS["target_speaker_minority"],
                    file_stem=f"{minority_counts[speaker]:02d}_{speaker}_{language_slug}",
                    mode="sft",
                    tts_text=item["tts_text"],
                    speaker=speaker,
                    reference_site_path=speaker_item["reference_site_path"],
                )
            )

    transfer_counts: dict[str, int] = {}
    for item in snapshot["target_speaker"]["instruct_transfer"]:
        match = re.match(r"<([a-zA-Z0-9_]+)>", item["styled_text"])
        style = match.group(1).lower() if match else "style"
        transfer_counts[style] = transfer_counts.get(style, 0) + 1
        suffix = f"_{transfer_counts[style]:02d}" if transfer_counts[style] > 1 else ""
        cases.append(
            DemoCase(
                section_key="target_speaker_transfer",
                section_title=SECTION_TITLES["target_speaker_transfer"],
                relative_output_dir=SECTION_DIRS["target_speaker_transfer"],
                file_stem=f"{style}{suffix}",
                mode="sft" if transfer_speaker else "unsupported",
                tts_text=item["styled_text"],
                speaker=transfer_speaker,
                reference_site_path=item["reference_site_path"],
                notes="Needs a target-speaker fine-tuned model. Pass --transfer-speaker to attempt these cases with an available speaker id.",
            )
        )

    return cases


def should_run_section(requested: set[str], section_key: str) -> bool:
    return "all" in requested or section_key in requested


def prompt_cache_path(cache_dir: Path, relative_path: str) -> Path:
    return cache_dir / relative_path


def download_file(url: str, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        return destination
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        destination.write_bytes(response.read())
    return destination


def download_reference_audio(case: DemoCase, target_path: Path) -> tuple[bool, str]:
    if not case.reference_site_path:
        return False, "reference audio is unavailable"
    try:
        download_file(site_url(case.reference_site_path), target_path)
        return True, "site_reference"
    except (urllib.error.URLError, OSError, ValueError) as exc:
        return False, f"failed to download site reference audio: {exc}"


def ensure_prompt_path(case: DemoCase, args: argparse.Namespace) -> tuple[Optional[Path], str, str]:
    if case.mode == "sft":
        return None, "speaker", ""
    if case.prompt_site_path:
        cached = prompt_cache_path(Path(args.prompt_cache_dir), case.prompt_site_path)
        if cached.exists():
            return cached, "site_cache", ""
        if args.download_site_prompts:
            try:
                return download_file(site_url(case.prompt_site_path), cached), "site_download", ""
            except (urllib.error.URLError, OSError, ValueError) as exc:
                if not args.allow_fallback_prompts:
                    return None, "", f"failed to download site prompt: {exc}"
        if args.allow_fallback_prompts:
            fallback = Path(args.fallback_prompt_wav)
            if fallback.exists():
                return fallback, "fallback", "using fallback prompt wav instead of the site prompt"
        return None, "", "prompt wav is unavailable"
    fallback = Path(args.fallback_prompt_wav)
    if fallback.exists():
        return fallback, "fallback", ""
    return None, "", "fallback prompt wav does not exist"


def available_speaker_map(cosyvoice) -> dict[str, str]:
    try:
        speakers = cosyvoice.list_available_spks()
    except Exception:
        return {}
    return {speaker.lower(): speaker for speaker in speakers}


def resolve_speaker(speaker_map: dict[str, str], requested: str) -> Optional[str]:
    return speaker_map.get(requested.lower())


def save_outputs(base_output: Path, outputs, sample_rate: int) -> list[str]:
    import torchaudio

    outputs = list(outputs)
    if not outputs:
        return []
    if len(outputs) == 1:
        target = base_output.with_suffix(".wav")
        torchaudio.save(str(target), outputs[0]["tts_speech"], sample_rate)
        return [str(target)]
    saved_paths = []
    for idx, item in enumerate(outputs, 1):
        target = base_output.parent / f"{base_output.name}__part{idx:02d}.wav"
        torchaudio.save(str(target), item["tts_speech"], sample_rate)
        saved_paths.append(str(target))
    return saved_paths


def run_case(cosyvoice, speaker_map: dict[str, str], case: DemoCase, args: argparse.Namespace) -> CaseResult:
    case_id = f"{case.relative_output_dir}/{case.file_stem}"
    result = CaseResult(
        case_id=case_id,
        section_key=case.section_key,
        section_title=case.section_title,
        relative_output_dir=case.relative_output_dir,
        mode=case.mode,
        status="pending",
        output_paths=[],
        reference_source="",
        notes=case.notes,
    )

    output_dir = Path(args.output_dir) / case.relative_output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    base_output = output_dir / case.file_stem
    main_output = base_output.with_suffix(".wav")
    if args.skip_existing and main_output.exists():
        result.status = "skipped"
        result.reason = "output already exists"
        result.output_paths = [str(main_output)]
        return result

    if case.mode == "unsupported":
        if args.download_reference_audio:
            ok, ref_info = download_reference_audio(case, main_output)
            if ok:
                result.status = "downloaded_reference"
                result.reference_source = ref_info
                result.output_paths = [str(main_output)]
                result.reason = case.notes or "downloaded website reference audio"
                return result
            result.reference_source = "reference_failed"
            result.reason = ref_info
        result.status = "skipped"
        result.reason = result.reason or case.notes or "unsupported in the current open-source API"
        return result

    prompt_path, prompt_source, prompt_error = ensure_prompt_path(case, args)
    result.prompt_source = prompt_source
    result.prompt_path = str(prompt_path) if prompt_path else ""
    if prompt_error:
        result.reason = prompt_error

    try:
        if case.mode == "sft":
            resolved_speaker = resolve_speaker(speaker_map, case.speaker)
            if not resolved_speaker:
                result.speaker = case.speaker
                if args.download_reference_audio:
                    ok, ref_info = download_reference_audio(case, main_output)
                    if ok:
                        result.status = "downloaded_reference"
                        result.reference_source = ref_info
                        result.output_paths = [str(main_output)]
                        result.reason = f'speaker id "{case.speaker}" is not available locally; downloaded website reference audio'
                        return result
                    result.reference_source = "reference_failed"
                    result.reason = ref_info
                result.status = "skipped"
                result.reason = result.reason or f'speaker id "{case.speaker}" is not available in the loaded model'
                return result
            result.speaker = resolved_speaker
            outputs = cosyvoice.inference_sft(
                case.tts_text,
                resolved_speaker,
                stream=False,
                speed=args.speed,
                text_frontend=False,
            )
        elif case.mode == "zero_shot":
            if not prompt_path:
                result.status = "skipped"
                result.reason = result.reason or "zero-shot case has no prompt wav"
                return result
            outputs = cosyvoice.inference_zero_shot(
                case.tts_text,
                ensure_endofprompt(case.prompt_text),
                str(prompt_path),
                stream=False,
                speed=args.speed,
                text_frontend=False,
            )
        elif case.mode == "cross_lingual":
            if not prompt_path:
                result.status = "skipped"
                result.reason = result.reason or "cross-lingual case has no prompt wav"
                return result
            outputs = cosyvoice.inference_cross_lingual(
                ensure_endofprompt(case.tts_text),
                str(prompt_path),
                stream=False,
                speed=args.speed,
                text_frontend=False,
            )
        elif case.mode == "instruct2":
            if not prompt_path:
                result.status = "skipped"
                result.reason = result.reason or "instruct case has no prompt wav"
                return result
            outputs = cosyvoice.inference_instruct2(
                case.tts_text,
                case.instruct_text,
                str(prompt_path),
                stream=False,
                speed=args.speed,
                text_frontend=False,
            )
        else:
            result.status = "skipped"
            result.reason = f"unknown mode: {case.mode}"
            return result

        saved_paths = save_outputs(base_output, outputs, cosyvoice.sample_rate)
        if not saved_paths:
            result.status = "skipped"
            result.reason = "no audio returned by the model"
            return result
        result.status = "generated"
        result.output_paths = saved_paths
        return result
    except Exception as exc:
        result.status = "failed"
        result.reason = f"{type(exc).__name__}: {exc}"
        return result


def write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    return path


def main() -> None:
    args = parse_args()

    site_html = read_or_download_text(
        SITE_URL,
        Path(args.site_html_cache),
        refresh=args.refresh_site_html,
    )
    snapshot = parse_site_snapshot(site_html)
    output_dir = Path(args.output_dir)
    snapshot_path = write_json(output_dir / "site_snapshot.json", snapshot)

    requested_sections = set(args.sections)
    cases = [case for case in build_cases(snapshot, args.transfer_speaker) if should_run_section(requested_sections, case.section_key)]
    if args.max_cases > 0:
        cases = cases[: args.max_cases]

    results: list[CaseResult] = []
    if args.dry_run:
        for case in cases:
            results.append(
                CaseResult(
                    case_id=f"{case.relative_output_dir}/{case.file_stem}",
                    section_key=case.section_key,
                    section_title=case.section_title,
                    relative_output_dir=case.relative_output_dir,
                    mode=case.mode,
                    status="planned",
                    notes=case.notes,
                )
            )
    else:
        from cosyvoice.cli.cosyvoice import AutoModel

        cosyvoice = AutoModel(model_dir=args.model_dir)
        speaker_map = available_speaker_map(cosyvoice)
        for case in cases:
            result = run_case(cosyvoice, speaker_map, case, args)
            results.append(result)
            print(f"[{result.status}] {result.case_id}")
            if result.reason:
                print(f"  reason: {result.reason}")

    manifest = {
        "site_url": SITE_URL,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "model_dir": args.model_dir,
        "site_html_cache": str(Path(args.site_html_cache)),
        "prompt_cache_dir": str(Path(args.prompt_cache_dir)),
        "site_snapshot_path": str(snapshot_path),
        "download_site_prompts": args.download_site_prompts,
        "allow_fallback_prompts": args.allow_fallback_prompts,
        "dry_run": args.dry_run,
        "case_count": len(cases),
        "summary": {
            "generated": sum(item.status == "generated" for item in results),
            "downloaded_reference": sum(item.status == "downloaded_reference" for item in results),
            "skipped": sum(item.status == "skipped" for item in results),
            "failed": sum(item.status == "failed" for item in results),
            "planned": sum(item.status == "planned" for item in results),
        },
        "items": [asdict(item) for item in results],
    }
    manifest_path = write_json(output_dir / "manifest.json", manifest)
    print(f"site snapshot written to {snapshot_path}")
    print(f"manifest written to {manifest_path}")


if __name__ == "__main__":
    main()
