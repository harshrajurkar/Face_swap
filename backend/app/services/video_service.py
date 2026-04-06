import json
import shutil
import subprocess
from collections.abc import Awaitable, Callable
from fractions import Fraction
from pathlib import Path

import cv2
import numpy as np

from app.config import Settings
from app.services.enhancement_service import EnhancementService
from app.services.face_service import FaceService, FaceSwapError
from app.services.storage_service import StorageService


class VideoProcessingError(Exception):
    """Raised when video extraction or rebuilding fails."""


class VideoService:
    FRAME_PATTERN = 'frame_%04d.png'

    def __init__(
        self,
        settings: Settings,
        face_service: FaceService,
        enhancement_service: EnhancementService,
        storage_service: StorageService,
    ) -> None:
        self.settings = settings
        self.face_service = face_service
        self.enhancement_service = enhancement_service
        self.storage_service = storage_service

    def prepare_job_directories(self, job_id: str) -> tuple[Path, Path, Path]:
        return self.storage_service.build_temp_job_directories(job_id)

    def validate_video(self, video_path: str) -> dict[str, float | int]:
        metadata = self._probe_video(video_path)
        duration = float(metadata['duration'])
        if self.settings.max_video_duration_seconds > 0 and duration > self.settings.max_video_duration_seconds:
            raise VideoProcessingError(
                f'Video is too long. Limit uploads to {self.settings.max_video_duration_seconds} seconds.'
            )
        return metadata

    def extract_frames(self, video_path: str, output_dir: str | Path) -> dict[str, float | int]:
        metadata = self.validate_video(video_path)
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        duration = max(float(metadata['duration']), 1.0)
        source_fps = float(metadata['fps']) or float(self.settings.max_video_fps)
        adaptive_fps = min(
            source_fps,
            float(self.settings.max_video_fps),
            max(1.0, self.settings.max_video_frames / duration),
        )
        fps = max(1, int(adaptive_fps))
        scale_filter = (
            f"scale=w='min({self.settings.max_video_width},iw)':"
            f"h='min({self.settings.max_video_height},ih)':"
            "force_original_aspect_ratio=decrease"
        )
        video_filter = f"fps={fps},{scale_filter}"

        command = [
            self.settings.ffmpeg_binary,
            '-y',
            '-i',
            str(video_path),
            '-vf',
            video_filter,
            str(output_path / self.FRAME_PATTERN),
        ]
        self._run_command(command, 'Failed to extract video frames with ffmpeg.')

        frame_count = len(sorted(output_path.glob('frame_*.png')))
        if frame_count == 0:
            raise VideoProcessingError('No frames were extracted from the uploaded video.')

        metadata['fps'] = fps
        metadata['frame_count'] = frame_count
        return metadata

    async def process_frames(
        self,
        job_id: str,
        source_path: str,
        frames_dir: str | Path,
        processed_dir: str | Path,
        *,
        enhance_face: bool,
        progress_callback: Callable[[int, int, int], Awaitable[None]] | None = None,
    ) -> dict[str, int]:
        frame_paths = sorted(Path(frames_dir).glob('frame_*.png'))
        processed_path = Path(processed_dir)
        processed_path.mkdir(parents=True, exist_ok=True)

        processed_count = 0
        skipped_count = 0
        total_frames = len(frame_paths)

        for index, frame_path in enumerate(frame_paths, start=1):
            output_path = processed_path / frame_path.name
            self._normalize_frame_resolution(frame_path)

            try:
                final_output = self.face_service.swap_faces(source_path, str(frame_path), str(output_path))
                if enhance_face:
                    final_output = self.enhancement_service.enhance_image(final_output, final_output)
                self._apply_video_finish(Path(final_output))
                processed_count += 1
            except FaceSwapError:
                shutil.copy2(frame_path, output_path)
                skipped_count += 1

            if progress_callback is not None:
                await progress_callback(index, total_frames, skipped_count)

        if processed_count == 0 and skipped_count == 0:
            raise VideoProcessingError(f'Video job {job_id} produced no processed frames.')

        return {
            'processed_frame_count': processed_count,
            'skipped_frame_count': skipped_count,
            'frame_count': len(frame_paths),
        }

    def rebuild_video(
        self,
        frames_dir: str | Path,
        output_path: str,
        *,
        framerate: int,
        source_video_path: str | None = None,
    ) -> str:
        frames_input = str(Path(frames_dir) / self.FRAME_PATTERN)
        command = [
            self.settings.ffmpeg_binary,
            '-y',
            '-framerate',
            str(framerate),
            '-i',
            frames_input,
        ]

        if source_video_path:
            command.extend(['-i', str(source_video_path), '-map', '0:v:0', '-map', '1:a:0?'])

        command.extend(['-c:v', 'libx264', '-pix_fmt', 'yuv420p'])

        if source_video_path:
            command.extend(['-c:a', 'aac', '-shortest'])

        command.append(str(output_path))
        self._run_command(command, 'Failed to rebuild the output video with ffmpeg.')
        return str(Path(output_path).resolve())

    def cleanup_job(self, job_id: str) -> None:
        root = self.settings.temp_frames_dir / job_id
        if root.exists():
            shutil.rmtree(root, ignore_errors=True)

    def _probe_video(self, video_path: str) -> dict[str, float | int]:
        command = [
            self.settings.ffprobe_binary,
            '-v',
            'error',
            '-select_streams',
            'v:0',
            '-show_entries',
            'stream=width,height,avg_frame_rate,r_frame_rate,duration',
            '-show_entries',
            'format=duration',
            '-of',
            'json',
            str(video_path),
        ]
        result = self._run_command(command, 'Failed to inspect uploaded video with ffprobe.')
        payload = json.loads(result.stdout)
        stream = (payload.get('streams') or [{}])[0]
        duration = float(stream.get('duration') or payload.get('format', {}).get('duration') or 0.0)
        fps_raw = stream.get('avg_frame_rate') or stream.get('r_frame_rate') or '0/1'
        fps = float(Fraction(fps_raw)) if fps_raw not in {'0/0', '0'} else float(self.settings.max_video_fps)
        return {
            'duration': duration,
            'fps': fps,
            'width': int(stream.get('width') or 0),
            'height': int(stream.get('height') or 0),
        }

    def _run_command(self, command: list[str], error_message: str) -> subprocess.CompletedProcess[str]:
        try:
            return subprocess.run(command, check=True, capture_output=True, text=True)
        except FileNotFoundError as exc:
            raise VideoProcessingError('ffmpeg/ffprobe was not found on this machine. Install ffmpeg first.') from exc
        except subprocess.CalledProcessError as exc:
            stderr = (exc.stderr or '').strip()
            detail = f' {stderr}' if stderr else ''
            raise VideoProcessingError(f'{error_message}{detail}') from exc

    def _normalize_frame_resolution(self, frame_path: Path) -> None:
        frame = cv2.imread(str(frame_path), cv2.IMREAD_COLOR)
        if frame is None:
            raise VideoProcessingError(f'Unable to read extracted frame {frame_path.name}.')

        height, width = frame.shape[:2]
        scale = min(
            self.settings.max_video_width / max(width, 1),
            self.settings.max_video_height / max(height, 1),
            1.0,
        )
        if scale >= 1.0:
            return

        resized = cv2.resize(
            frame,
            (max(1, int(width * scale)), max(1, int(height * scale))),
            interpolation=cv2.INTER_AREA,
        )
        cv2.imwrite(str(frame_path), resized)

    def _apply_video_finish(self, frame_path: Path) -> None:
        frame = cv2.imread(str(frame_path), cv2.IMREAD_COLOR)
        if frame is None:
            raise VideoProcessingError(f'Unable to post-process frame {frame_path.name}.')

        if self.settings.video_blur_sigma > 0:
            frame = cv2.GaussianBlur(frame, (3, 3), self.settings.video_blur_sigma)

        if self.settings.video_noise_strength > 0:
            noise = np.random.normal(0, self.settings.video_noise_strength, frame.shape).astype(np.float32)
            frame = np.clip(frame.astype(np.float32) + noise, 0, 255).astype(np.uint8)

        if self.settings.video_jpeg_quality < 100:
            ok, encoded = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, self.settings.video_jpeg_quality])
            if ok:
                decoded = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
                if decoded is not None:
                    frame = decoded

        cv2.imwrite(str(frame_path), frame)
