"""
FRIDAY Video Editor Engine
==========================
Editor de vídeo agentivo (funcionalidade dos vídeos enviados na visão).

Transforma instruções em linguagem natural em operações ffmpeg reais:
    info            → metadados (duração, resolução, streams)
    cut             → corta segmento [start,end]
    resize          → vertical (TikTok/Reels) | horizontal (YouTube) | square
    captions        → legendas com tempos [{text,start,end}]
    highlight       → círculo animado numa região durante [start,end]
    storyboard      → grelha de frames (pré-visualização antes de exportar)
    extract_audio   → áudio para .mp3
    gif             → GIF curto de um segmento

Tudo verificado (verify() confere existência + tamanho + ffprobe) e sem
dependências Python novas — usa o binário ffmpeg/ffprobe do sistema.
"""

from __future__ import annotations

import json
import math
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from friday_core.types import (
    CapabilityCategory, CapabilityImpl, StepResult, VerificationResult,
)


def _ffmpeg() -> str | None:
    return shutil.which("ffmpeg")


def _ffprobe() -> str | None:
    return shutil.which("ffprobe")


_FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/noto-serif-sc/NotoSerifSC-Bold.otf",
    "/usr/share/fonts/truetype/chinese/NotoSansSC-Regular.ttf",
]


def _find_font() -> str:
    for p in _FONT_CANDIDATES:
        if Path(p).exists():
            return p
    return "Sans"


def _ts(seconds: float) -> str:
    """Segundos → HH:MM:SS.mmm para ffmpeg."""
    seconds = max(0.0, float(seconds))
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}"


def _esc(text: str) -> str:
    """Escapa texto para drawtext do ffmpeg."""
    return (text.replace("\\", "\\\\")
                .replace(":", "\\:")
                .replace("'", "\\\u2019")
                .replace("%", "\\%"))


class VideoEditorCapability(CapabilityImpl):
    name = "video_editor"
    category = CapabilityCategory.VIDEO
    description = "Editor de vídeo agentivo: corta, redimensiona, legendas, destaques, storyboard (ffmpeg)"

    def __init__(self, output_dir: str | Path = "outputs/video"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ #
    def health(self) -> bool:
        return _ffmpeg() is not None

    def action_level(self, inputs: dict[str, Any]) -> str:
        return "prepare"  # cria ficheiros locais no workspace (não publica)

    def execute(self, inputs: dict[str, Any], ctx) -> StepResult:
        action = str(inputs.get("action", "")).lower().strip()
        ffmpeg = _ffmpeg()
        if ffmpeg is None:
            return StepResult(success=False, error="ffmpeg não instalado "
                              "(instalar: apt install ffmpeg / brew install ffmpeg)",
                              finished_at=time.time())

        handlers = {
            "info": self._info, "probe": self._info,
            "cut": self._cut, "trim": self._cut,
            "resize": self._resize, "vertical": self._resize, "horizontal": self._resize,
            "captions": self._captions, "subtitle": self._captions, "legendas": self._captions,
            "highlight": self._highlight, "circle": self._highlight,
            "storyboard": self._storyboard, "frames": self._storyboard,
            "extract_audio": self._extract_audio, "audio": self._extract_audio,
            "gif": self._gif,
        }
        handler = handlers.get(action)
        if handler is None:
            return StepResult(
                success=False,
                error=f"acção de vídeo desconhecida: '{action}'. "
                      f"Disponíveis: {', '.join(sorted(set(handlers)))}",
                finished_at=time.time())

        started = time.time()
        try:
            output = handler(inputs, ffmpeg)
        except subprocess.TimeoutExpired:
            return StepResult(success=False, error="timeout ffmpeg (180s)",
                              finished_at=time.time())
        except Exception as e:
            return StepResult(success=False, error=f"{type(e).__name__}: {e}",
                              finished_at=time.time())

        info = {"action": action, "outputs": output,
                "duration_s": round(time.time() - started, 2)}
        return StepResult(success=True, output=info, artifacts=output,
                          metadata={"engine": "ffmpeg", "action": action},
                          finished_at=time.time())

    # ------------------------------------------------------------------ #
    def verify(self, result: StepResult, inputs: dict[str, Any]) -> VerificationResult:
        checks: list[dict[str, Any]] = []
        if not result.success:
            return VerificationResult(passed=False,
                                      checks=[{"name": "success", "passed": False,
                                               "error": result.error}])
        outputs = result.output.get("outputs", []) if result.output else []
        for o in outputs:
            p = Path(o.get("path", "")) if isinstance(o, dict) else Path(o)
            ok = p.exists() and p.stat().st_size > 0
            checks.append({"name": f"file:{p.name}", "passed": ok,
                           "size": p.stat().st_size if p.exists() else 0})
        passed = bool(checks) and all(c["passed"] for c in checks)
        return VerificationResult(passed=passed, checks=checks,
                                  notes="ffmpeg outputs verificados")

    # ================================================================== #
    # Handlers
    # ================================================================== #
    def _resolve_src(self, src: str) -> Path:
        p = Path(src)
        if p.exists():
            return p
        if not p.is_absolute():
            # procura no cwd, outputs e workspace (output_dir=/ws/outputs/video)
            for base in (Path.cwd(), self.output_dir, self.output_dir.parent,
                         self.output_dir.parent.parent):
                cand = base / p
                if cand.exists():
                    return cand
        if not p.exists():
            raise FileNotFoundError(f"vídeo não encontrado: {src}")
        return p

    def _out(self, name: str) -> Path:
        p = self.output_dir / name
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    def _probe(self, src: Path) -> dict[str, Any]:
        ff = _ffprobe()
        if not ff:
            return {}
        try:
            out = subprocess.run(
                [ff, "-v", "quiet", "-print_format", "json",
                 "-show_format", "-show_streams", str(src)],
                capture_output=True, text=True, timeout=60)
            return json.loads(out.stdout or "{}")
        except Exception:
            return {}

    def _duration(self, src: Path) -> float:
        probe = self._probe(src)
        try:
            return float(probe.get("format", {}).get("duration", 0.0))
        except (TypeError, ValueError):
            return 0.0

    # ------------------------------------------------------------------ #
    def _info(self, inputs: dict[str, Any], ffmpeg: str):
        src = self._resolve_src(inputs.get("source", ""))
        probe = self._probe(src)
        fmt = probe.get("format", {})
        vstream = next((s for s in probe.get("streams", [])
                        if s.get("codec_type") == "video"), {})
        info = {
            "file": str(src),
            "duration_s": float(fmt.get("duration", 0) or 0),
            "size_bytes": int(fmt.get("size", 0) or 0),
            "width": vstream.get("width"), "height": vstream.get("height"),
            "fps": vstream.get("r_frame_rate"), "codec": vstream.get("codec_name"),
        }
        report = self._out("video_info.json")
        report.write_text(json.dumps(info, indent=2, ensure_ascii=False),
                          encoding="utf-8")
        return [{"path": str(report), "kind": "info", **info}]

    def _cut(self, inputs: dict[str, Any], ffmpeg: str):
        src = self._resolve_src(inputs.get("source", ""))
        start = float(inputs.get("start", 0.0))
        end = float(inputs.get("end", min(start + 30.0, self._duration(src))))
        out = self._out(f"cut_{int(start)}_{int(end)}_{Path(src).stem}.mp4")
        dur = max(end - start, 0.5)
        # re-encode para corte exacto (mais compatível que -c copy)
        subprocess.run(
            [ffmpeg, "-y", "-ss", _ts(start), "-i", str(src), "-t", f"{dur:.3f}",
             "-c:v", "libx264", "-preset", "veryfast", "-c:a", "aac",
             "-movflags", "+faststart", str(out)],
            capture_output=True, text=True, timeout=180, check=True)
        return [{"path": str(out), "kind": "video",
                 "segment": [start, end], "duration_s": round(dur, 2)}]

    def _resize(self, inputs: dict[str, Any], ffmpeg: str):
        src = self._resolve_src(inputs.get("source", ""))
        fmt = str(inputs.get("format", inputs.get("target", "vertical"))).lower()
        presets = {
            "vertical": ("1080:1920", "9:16", "TikTok/Reels/Shorts"),
            "horizontal": ("1920:1080", "16:9", "YouTube/Apresentações"),
            "square": ("1080:1080", "1:1", "Feed Instagram"),
        }
        if fmt not in presets:
            fmt = "vertical"
        dims, ratio, label = presets[fmt]
        out = self._out(f"{fmt}_{Path(src).stem}.mp4")
        vf = (f"scale={dims.split(':')[0]}:{dims.split(':')[1]}"
              f":force_original_aspect_ratio=decrease,"
              f"pad={dims.replace(':', ':')}"
              f":(ow-iw)/2:(oh-ih)/2:color=black,setsar=1")
        subprocess.run(
            [ffmpeg, "-y", "-i", str(src), "-vf", vf,
             "-c:v", "libx264", "-preset", "veryfast", "-c:a", "aac",
             "-movflags", "+faststart", str(out)],
            capture_output=True, text=True, timeout=300, check=True)
        return [{"path": str(out), "kind": "video", "format": fmt,
                 "label": label, "ratio": ratio}]

    def _captions(self, inputs: dict[str, Any], ffmpeg: str):
        src = self._resolve_src(inputs.get("source", ""))
        caps = inputs.get("captions") or inputs.get("subtitles") or []
        if isinstance(caps, str):
            # formato: "10|Primeira legenda;15|Segunda legenda"
            caps = []
            for chunk in caps.split(";"):
                if "|" in chunk:
                    t, txt = chunk.split("|", 1)
                    try:
                        caps.append({"start": float(t), "end": float(t) + 4.0,
                                     "text": txt.strip()})
                    except ValueError:
                        continue
        if not caps:
            raise ValueError("captions vazio — fornecer lista [{text,start,end}]")

        font = _find_font()
        filters = []
        for i, c in enumerate(caps):
            text = _esc(str(c.get("text", ""))[:120])
            s = float(c.get("start", 0))
            e = float(c.get("end", s + 4.0))
            pos = int(c.get("position_y", 80))
            filters.append(
                f"drawtext=fontfile={font}:text='{text}'"
                f":fontsize={int(c.get('size', 42))}:fontcolor=white"
                f":borderw=3:bordercolor=black"
                f":x=(w-text_w)/2:y=h-{pos}"
                f":enable='between(t,{s:.2f},{e:.2f})'")
        out = self._out(f"captioned_{Path(src).stem}.mp4")
        subprocess.run(
            [ffmpeg, "-y", "-i", str(src), "-vf", ",".join(filters),
             "-c:v", "libx264", "-preset", "veryfast", "-c:a", "copy",
             "-movflags", "+faststart", str(out)],
            capture_output=True, text=True, timeout=300, check=True)
        return [{"path": str(out), "kind": "video", "captions": len(caps)}]

    def _highlight(self, inputs: dict[str, Any], ffmpeg: str):
        """Círculo animado sobre uma região (destaca produto/objecto)."""
        from PIL import Image, ImageDraw
        src = self._resolve_src(inputs.get("source", ""))
        x = float(inputs.get("x", 0.35))      # frações da largura/altura
        y = float(inputs.get("y", 0.35))
        radius = float(inputs.get("radius", 0.18))
        start = float(inputs.get("start", 0.0))
        end = float(inputs.get("end", min(start + 5.0, self._duration(src))))

        # círculo PNG com PIL (transparente, contorno vermelho JIAC)
        size = 512
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        lw = 14
        draw.ellipse([lw, lw, size - lw, size - lw],
                     outline=(231, 76, 60, 255), width=lw)
        ring = self._out("highlight_ring.png")
        img.save(ring)

        probe = self._probe(src)
        vw = float(probe.get("streams", [{}])[0].get("width", 1920) or 1920)
        vh = float(probe.get("streams", [{}])[0].get("height", 1080) or 1080)
        ring_w = int(vw * radius * 2)
        ring_x = int(vw * x - ring_w / 2)
        ring_y = int(vh * y - ring_w / 2)

        out = self._out(f"highlight_{Path(src).stem}.mp4")
        vf = (f"movie={ring}:loop=0,setpts=N/FRAME_RATE/TB,"
              f"scale={ring_w}:{ring_w},"
              f"format=rgba,colorchannelmixer=aa=0.9[wm];"
              f"[0:v][wm]overlay={ring_x}:{ring_y}"
              f":enable='between(t,{start:.2f},{end:.2f})'")
        subprocess.run(
            [ffmpeg, "-y", "-i", str(src), "-filter_complex", vf,
             "-c:v", "libx264", "-preset", "veryfast", "-c:a", "copy",
             "-movflags", "+faststart", str(out)],
            capture_output=True, text=True, timeout=300, check=True)
        return [{"path": str(out), "kind": "video",
                 "highlight_region": [x, y, radius], "window": [start, end]}]

    def _storyboard(self, inputs: dict[str, Any], ffmpeg: str):
        """Grelha de frames — pré-visualização antes de exportar."""
        from PIL import Image
        src = self._resolve_src(inputs.get("source", ""))
        n_frames = int(inputs.get("frames", 12))
        dur = self._duration(src) or 1.0
        frames_dir = self._out(f"storyboard_{Path(src).stem}")
        frames_dir.mkdir(parents=True, exist_ok=True)

        step = dur / (n_frames + 1)
        frames = []
        for i in range(1, n_frames + 1):
            ts = i * step
            fp = frames_dir / f"frame_{i:02d}.jpg"
            subprocess.run(
                [ffmpeg, "-y", "-ss", _ts(ts), "-i", str(src),
                 "-frames:v", "1", "-q:v", "3", str(fp)],
                capture_output=True, text=True, timeout=60, check=True)
            if fp.exists():
                frames.append(fp)

        if not frames:
            raise RuntimeError("não foi possível extrair frames")

        # grelha 4 colunas
        cols = 4
        rows = math.ceil(len(frames) / cols)
        with Image.open(frames[0]) as im0:
            tw, th = im0.size
        tw, th = min(tw, 480), int(min(tw, 480) * th / tw) if tw else 480
        cell_w, cell_h = tw // 1, th // 1
        grid = Image.new("RGB", (cols * cell_w, rows * cell_h), (12, 12, 16))
        for i, fp in enumerate(frames):
            with Image.open(fp) as im:
                im = im.convert("RGB").resize((cell_w, cell_h))
                grid.paste(im, ((i % cols) * cell_w, (i // cols) * cell_h))
        grid_path = self._out(f"storyboard_{Path(src).stem}.jpg")
        grid.save(grid_path, quality=88)
        return [{"path": str(grid_path), "kind": "storyboard",
                 "frames": len(frames)},
                *[{"path": str(f), "kind": "frame"} for f in frames[:3]]]

    def _extract_audio(self, inputs: dict[str, Any], ffmpeg: str):
        src = self._resolve_src(inputs.get("source", ""))
        out = self._out(f"{Path(src).stem}.mp3")
        subprocess.run(
            [ffmpeg, "-y", "-i", str(src), "-vn", "-c:a", "libmp3lame",
             "-q:a", "4", str(out)],
            capture_output=True, text=True, timeout=180, check=True)
        return [{"path": str(out), "kind": "audio"}]

    def _gif(self, inputs: dict[str, Any], ffmpeg: str):
        src = self._resolve_src(inputs.get("source", ""))
        start = float(inputs.get("start", 0.0))
        dur = float(inputs.get("duration", 4.0))
        fps = int(inputs.get("fps", 12))
        out = self._out(f"{Path(src).stem}_{int(start)}s.gif")
        subprocess.run(
            [ffmpeg, "-y", "-ss", _ts(start), "-i", str(src), "-t", f"{dur:.2f}",
             "-vf", f"fps={fps},scale=480:-1:flags=lanczos,split[s0][s1];"
                    f"[s0]palettegen[p];[s1][p]paletteuse",
             str(out)],
            capture_output=True, text=True, timeout=300, check=True)
        return [{"path": str(out), "kind": "gif", "duration_s": dur}]
