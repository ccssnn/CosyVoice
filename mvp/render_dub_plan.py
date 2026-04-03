#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

os.environ.setdefault('PYTORCH_ENABLE_MPS_FALLBACK', '1')
os.environ.setdefault('KMP_USE_SHM', '0')

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))
sys.path.append(str(ROOT_DIR / 'third_party' / 'Matcha-TTS'))


DEFAULT_PLAN = ROOT_DIR / 'mvp' / 'TheBestBreadStore' / 'dub_plan.json'
CROSS_LINGUAL_COSYVOICE3_PREFIX = 'You are a helpful assistant.<|endofprompt|>'


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Render a CosyVoice dubbing plan from JSON.')
    parser.add_argument('--plan', default=str(DEFAULT_PLAN), help='Path to the dubbing plan JSON.')
    parser.add_argument('--output-dir', default='', help='Override output directory from the plan.')
    parser.add_argument('--model-dir', default='', help='Override model directory from the plan.')
    parser.add_argument('--device', choices=['cpu', 'auto'], default='cpu', help='Runtime device selection. Default is cpu.')
    parser.add_argument('--indices', default='', help='Comma-separated entry indices to render, for example: 1,2,5')
    parser.add_argument('--skip-existing', action=argparse.BooleanOptionalAction, default=True, help='Skip rendering if the sentence wav already exists.')
    parser.add_argument('--merge', action=argparse.BooleanOptionalAction, default=True, help='Merge rendered sentences into one wav.')
    parser.add_argument('--dry-run', action=argparse.BooleanOptionalAction, default=False, help='Validate the plan without loading the model.')
    return parser.parse_args()


def resolve_repo_path(path_str: str) -> Path:
    path = Path(path_str)
    if path.is_absolute():
        return path
    return (ROOT_DIR / path).resolve()


def resolve_prompt_path(path_str: str, plan_path: Path) -> Path:
    path = Path(path_str)
    if path.is_absolute():
        return path
    plan_relative = (plan_path.parent / path).resolve()
    if plan_relative.exists():
        return plan_relative
    return resolve_repo_path(path_str)


def load_model(model_dir: Path):
    from cosyvoice.cli.cosyvoice import AutoModel

    return AutoModel(model_dir=str(model_dir))


def load_plan(plan_path: Path) -> dict:
    return json.loads(plan_path.read_text(encoding='utf-8'))


def configure_runtime_device(device: str) -> None:
    if device != 'cpu':
        return
    os.environ['CUDA_VISIBLE_DEVICES'] = ''
    os.environ['PYTORCH_ENABLE_MPS_FALLBACK'] = '0'

    import torch

    torch.cuda.is_available = lambda: False
    if hasattr(torch.backends, 'mps') and hasattr(torch.backends.mps, 'is_available'):
        torch.backends.mps.is_available = lambda: False
    if hasattr(torch.backends, 'mps') and hasattr(torch.backends.mps, 'is_built'):
        torch.backends.mps.is_built = lambda: False


def resolve_role_config(plan: dict, role: str) -> dict:
    roles = plan.get('roles', {})
    if role not in roles:
        raise ValueError(f'Role config not found for role: {role}')
    return roles[role]


def parse_indices(raw_indices: str) -> set[int]:
    if not raw_indices.strip():
        return set()
    indices = set()
    for part in raw_indices.split(','):
        item = part.strip()
        if not item:
            continue
        indices.add(int(item))
    return indices


def select_entries(entries: list[dict], selected_indices: set[int]) -> list[dict]:
    if not selected_indices:
        return entries
    return [entry for entry in entries if entry['index'] in selected_indices]


def validate_entry(plan: dict, entry: dict, plan_path: Path) -> None:
    for required_key in ['index', 'role', 'tts_text', 'api', 'output_wav', 'pause_ms_after']:
        if required_key not in entry:
            raise ValueError(f'Entry {entry.get("index", "?")} missing key: {required_key}')
    api = entry['api']
    for required_key in ['name', 'speed', 'stream', 'text_frontend']:
        if required_key not in api:
            raise ValueError(f'Entry {entry["index"]} api missing key: {required_key}')
    role_config = resolve_role_config(plan, entry['role'])
    prompt_wav = api.get('prompt_wav', role_config.get('prompt_wav'))
    if not prompt_wav:
        raise ValueError(f'Entry {entry["index"]} has no prompt_wav and role "{entry["role"]}" has no default prompt_wav')
    prompt_path = resolve_prompt_path(prompt_wav, plan_path)
    if not prompt_path.exists():
        raise FileNotFoundError(f'Entry {entry["index"]} prompt wav not found: {prompt_path}')
    zero_shot_spk_id = api.get('zero_shot_spk_id', role_config.get('zero_shot_spk_id', ''))
    if api['name'] == 'inference_instruct2' and not api.get('instruct_text'):
        raise ValueError(f'Entry {entry["index"]} requires api.instruct_text')
    if api['name'] == 'inference_zero_shot' and not zero_shot_spk_id and not api.get('prompt_text', role_config.get('prompt_text')):
        raise ValueError(f'Entry {entry["index"]} requires api.prompt_text')
    if zero_shot_spk_id and not role_config.get('prompt_text'):
        raise ValueError(f'Role "{entry["role"]}" uses zero_shot_spk_id but has no prompt_text')
    if api['name'] not in {'inference_instruct2', 'inference_zero_shot', 'inference_cross_lingual'}:
        raise ValueError(f'Entry {entry["index"]} has unsupported api: {api["name"]}')


def validate_plan(plan: dict, plan_path: Path, entries: list[dict]) -> None:
    for key in ['model_dir', 'output_dir', 'entries', 'roles']:
        if key not in plan:
            raise ValueError(f'Plan missing key: {key}')
    if not entries:
        raise ValueError('No entries selected from plan')
    seen_outputs = set()
    for entry in entries:
        validate_entry(plan, entry, plan_path)
        output_wav = entry['output_wav']
        if output_wav in seen_outputs:
            raise ValueError(f'Duplicate output_wav in plan: {output_wav}')
        seen_outputs.add(output_wav)


def resolve_tts_text(model, api_name: str, tts_text: str) -> str:
    if api_name != 'inference_cross_lingual':
        return tts_text
    if '<|endofprompt|>' in tts_text:
        return tts_text
    if model.__class__.__name__ == 'CosyVoice3':
        return f'{CROSS_LINGUAL_COSYVOICE3_PREFIX}{tts_text}'
    return tts_text


def register_zero_shot_roles(model, plan: dict, plan_path: Path) -> dict[str, dict]:
    role_caches: dict[str, dict] = {}
    for role, config in plan.get('roles', {}).items():
        zero_shot_spk_id = config.get('zero_shot_spk_id', '')
        if not zero_shot_spk_id:
            continue
        prompt_text = config.get('prompt_text', '')
        prompt_wav = config.get('prompt_wav', '')
        if not prompt_text or not prompt_wav:
            raise ValueError(f'Role "{role}" must provide prompt_text and prompt_wav for zero_shot_spk_id')
        prompt_path = resolve_prompt_path(prompt_wav, plan_path)
        model.add_zero_shot_spk(prompt_text, str(prompt_path), zero_shot_spk_id)
        base_input = model.frontend.frontend_zero_shot('', prompt_text, str(prompt_path), model.sample_rate, '')
        del base_input['text']
        del base_input['text_len']
        role_caches[role] = {
            'zero_shot_spk_id': zero_shot_spk_id,
            'prompt_path': str(prompt_path),
            'base_input': base_input,
        }
    return role_caches


def inference_instruct2_with_role_cache(model, tts_text: str, instruct_text: str, role_cache: dict, stream: bool, speed: float, text_frontend: bool):
    from cosyvoice.utils.file_utils import logging

    instruct_text = model.frontend.text_normalize(instruct_text, split=False, text_frontend=text_frontend)
    for chunk_text in model.frontend.text_normalize(tts_text, split=True, text_frontend=text_frontend):
        model_input = {**role_cache['base_input']}
        text_token, text_token_len = model.frontend._extract_text_token(chunk_text)
        instruct_token, instruct_token_len = model.frontend._extract_text_token(instruct_text)
        model_input['text'] = text_token
        model_input['text_len'] = text_token_len
        model_input['prompt_text'] = instruct_token
        model_input['prompt_text_len'] = instruct_token_len
        model_input.pop('llm_prompt_speech_token', None)
        model_input.pop('llm_prompt_speech_token_len', None)
        start_time = time.time()
        logging.info('synthesis text {}'.format(chunk_text))
        for model_output in model.model.tts(**model_input, stream=stream, speed=speed):
            speech_len = model_output['tts_speech'].shape[1] / model.sample_rate
            logging.info('yield speech len {}, rtf {}'.format(speech_len, (time.time() - start_time) / speech_len))
            yield model_output
            start_time = time.time()


def synthesize_entry(model, plan: dict, entry: dict, plan_path: Path, output_path: Path, role_caches: dict[str, dict]):
    import torch
    import torchaudio

    api = entry['api']
    role_config = resolve_role_config(plan, entry['role'])
    prompt_path = resolve_prompt_path(api.get('prompt_wav', role_config['prompt_wav']), plan_path)
    zero_shot_spk_id = api.get('zero_shot_spk_id', role_config.get('zero_shot_spk_id', ''))
    role_cache = role_caches.get(entry['role'])
    common_kwargs = {
        'tts_text': resolve_tts_text(model, api['name'], entry['tts_text']),
        'stream': api['stream'],
        'speed': api['speed'],
        'text_frontend': api['text_frontend'],
    }
    if api['name'] == 'inference_instruct2':
        if zero_shot_spk_id and role_cache is not None:
            outputs = inference_instruct2_with_role_cache(
                model=model,
                tts_text=common_kwargs['tts_text'],
                instruct_text=api['instruct_text'],
                role_cache=role_cache,
                stream=api['stream'],
                speed=api['speed'],
                text_frontend=api['text_frontend'],
            )
        else:
            outputs = model.inference_instruct2(
                instruct_text=api['instruct_text'],
                prompt_wav=str(prompt_path),
                zero_shot_spk_id=zero_shot_spk_id,
                **common_kwargs,
            )
    elif api['name'] == 'inference_zero_shot':
        outputs = model.inference_zero_shot(
            prompt_text=api.get('prompt_text', role_config['prompt_text']),
            prompt_wav=str(prompt_path),
            zero_shot_spk_id=zero_shot_spk_id,
            **common_kwargs,
        )
    else:
        outputs = model.inference_cross_lingual(
            prompt_wav=str(prompt_path),
            zero_shot_spk_id=zero_shot_spk_id,
            **common_kwargs,
        )
    chunks = [result['tts_speech'].cpu() for result in outputs]
    if not chunks:
        raise RuntimeError(f'No audio returned for entry {entry["index"]}')
    audio = torch.cat(chunks, dim=1)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    torchaudio.save(str(output_path), audio, model.sample_rate)
    return audio


def load_audio(audio_path: Path, sample_rate: int) -> torch.Tensor:
    import torchaudio

    audio, current_sample_rate = torchaudio.load(str(audio_path))
    if current_sample_rate != sample_rate:
        audio = torchaudio.functional.resample(audio, current_sample_rate, sample_rate)
    return audio


def merge_audio(entries: list[dict], output_dir: Path, merge_name: str, sample_rate: int) -> str:
    import torch
    import torchaudio

    merged_parts = []
    for entry in entries:
        sentence_path = output_dir / entry['output_wav']
        merged_parts.append(load_audio(sentence_path, sample_rate))
        pause_samples = int(sample_rate * entry['pause_ms_after'] / 1000)
        merged_parts.append(torch.zeros(1, pause_samples))
    if merged_parts:
        merged_parts.pop()
    merged = torch.cat(merged_parts, dim=1) if merged_parts else torch.zeros(1, 0)
    merged_path = output_dir / merge_name
    torchaudio.save(str(merged_path), merged, sample_rate)
    return str(merged_path.relative_to(output_dir))


def detect_device() -> str:
    try:
        import torch
    except Exception:
        return 'unknown'

    if torch.cuda.is_available():
        return 'cuda'
    if hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
        return 'mps'
    return 'cpu'


def build_render_manifest(plan_path: Path, output_dir: Path, model_dir: Path, entries: list[dict], sample_rate: int, merged_output: str, dry_run: bool, device: str) -> dict:
    return {
        'plan_path': str(plan_path),
        'output_dir': str(output_dir),
        'model_dir': str(model_dir),
        'device': device,
        'sample_rate': sample_rate,
        'merged_output_wav': merged_output,
        'dry_run': dry_run,
        'rendered_entries': [
            {
                'index': entry['index'],
                'role': entry['role'],
                'tts_text': entry['tts_text'],
                'api_name': entry['api']['name'],
                'output_wav': entry['output_wav'],
            }
            for entry in entries
        ],
    }


def main() -> None:
    args = parse_args()
    configure_runtime_device(args.device)
    plan_path = Path(args.plan).resolve()
    plan = load_plan(plan_path)
    selected_indices = parse_indices(args.indices)
    entries = select_entries(plan['entries'], selected_indices)
    validate_plan(plan, plan_path, entries)

    output_dir_value = args.output_dir or plan['output_dir']
    model_dir_value = args.model_dir or plan['model_dir']
    output_dir = resolve_repo_path(output_dir_value)
    model_dir = resolve_repo_path(model_dir_value)
    output_dir.mkdir(parents=True, exist_ok=True)
    if not args.dry_run and not model_dir.exists():
        raise FileNotFoundError(f'Model directory not found: {model_dir}')

    if args.dry_run:
        manifest = build_render_manifest(plan_path, output_dir, model_dir, entries, 0, '', True, 'not_loaded')
        (output_dir / 'render_manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f'Validated {len(entries)} entries from {plan_path}')
        return

    model = load_model(model_dir)
    role_caches = register_zero_shot_roles(model, plan, plan_path)
    for entry in entries:
        output_path = output_dir / entry['output_wav']
        if args.skip_existing and output_path.exists():
            continue
        synthesize_entry(model, plan, entry, plan_path, output_path, role_caches)

    merged_output = ''
    if args.merge:
        merged_output = merge_audio(entries, output_dir, plan.get('merge_output_wav', 'full_book.wav'), model.sample_rate)

    manifest = build_render_manifest(plan_path, output_dir, model_dir, entries, model.sample_rate, merged_output, False, detect_device())
    (output_dir / 'render_manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'Rendered {len(entries)} entries into {output_dir}')
    if merged_output:
        print(f'Merged audio: {output_dir / merged_output}')


if __name__ == '__main__':
    main()
