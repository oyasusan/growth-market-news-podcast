import asyncio
import logging
import os
import re
import subprocess
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)


def _clean_for_tts(text: str) -> str:
    """TTS向けにテキストをクリーニング"""
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"【(.+?)】", r"\1。", text)
    text = re.sub(r"■.+?\n", "", text)
    text = re.sub(r"\[?\d+\]", "", text)
    text = re.sub(r"[*・]", "", text)
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = text.strip()
    return text


async def _edge_tts_generate(text: str, output_path: str, voice: str,
                              rate: str, volume: str) -> bool:
    try:
        import edge_tts
        communicate = edge_tts.Communicate(text, voice, rate=rate, volume=volume)
        await communicate.save(output_path)
        return True
    except Exception as e:
        logger.error(f"edge-tts生成失敗: {e}")
        return False


class TTSEngine:
    def __init__(self, settings: dict):
        tts_cfg = settings.get("tts", {})
        self.voice = os.getenv("TTS_VOICE", tts_cfg.get("voice", "ja-JP-NanamiNeural"))
        self.rate = os.getenv("TTS_RATE", tts_cfg.get("rate", "+10%"))
        self.volume = os.getenv("TTS_VOLUME", tts_cfg.get("volume", "+0%"))
        self.section_pause_ms = tts_cfg.get("section_pause_ms", 1000)

    def generate(self, script: str, output_path: str) -> bool:
        """台本をMP3に変換（edge-tts使用）"""
        cleaned = _clean_for_tts(script)
        logger.info(f"TTS生成開始: {len(cleaned)}文字 -> {output_path}")

        sections = re.split(r"\n\n+", cleaned)
        sections = [s.strip() for s in sections if s.strip()]

        if not sections:
            logger.error("変換するテキストがありません")
            return False

        temp_files = []
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                for i, section in enumerate(sections):
                    tmp_path = str(Path(tmpdir) / f"section_{i:04d}.mp3")
                    success = asyncio.run(
                        _edge_tts_generate(
                            section, tmp_path, self.voice, self.rate, self.volume
                        )
                    )
                    if success and Path(tmp_path).exists():
                        temp_files.append(tmp_path)
                    else:
                        logger.warning(f"セクション{i}の生成失敗: {section[:50]}...")

                if not temp_files:
                    return False

                if len(temp_files) == 1:
                    import shutil
                    shutil.copy2(temp_files[0], output_path)
                else:
                    self._concatenate_mp3(temp_files, output_path, tmpdir)

        except Exception as e:
            logger.error(f"TTS生成エラー: {e}")
            return False

        if Path(output_path).exists() and Path(output_path).stat().st_size > 0:
            logger.info(f"TTS生成完了: {output_path}")
            return True

        logger.error(f"TTS出力ファイルが空または存在しない: {output_path}")
        return False

    def _concatenate_mp3(self, mp3_files: list[str], output_path: str,
                         tmpdir: str) -> None:
        """複数MP3を結合（FFmpeg使用）"""
        list_file = Path(tmpdir) / "concat_list.txt"
        with open(list_file, "w") as f:
            for fp in mp3_files:
                f.write(f"file '{fp}'\n")

        cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(list_file),
            "-c", "copy",
            output_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.error(f"MP3結合失敗: {result.stderr}")
            raise RuntimeError(f"ffmpeg concat failed: {result.stderr}")
        logger.info(f"{len(mp3_files)}ファイルを結合")

    def generate_silence(self, duration_ms: int, output_path: str) -> bool:
        """無音MP3を生成（セクション間パウズ用）"""
        duration_sec = duration_ms / 1000.0
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", f"anullsrc=channel_layout=stereo:sample_rate=44100",
            "-t", str(duration_sec),
            "-c:a", "libmp3lame",
            "-b:a", "128k",
            output_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.returncode == 0
