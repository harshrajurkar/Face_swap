from pathlib import Path

import cv2
import insightface
import numpy as np
from insightface.app import FaceAnalysis

from app.config import Settings


class FaceSwapError(Exception):
    """Raised when face swap processing fails."""


class FaceService:
    MIN_FACE_SIZE = 40
    PREFERRED_TARGET_FACE_SIZE = 96
    SOURCE_CROP_PADDING = 0.45
    TARGET_CROP_PADDING = 0.35
    MAX_TARGET_UPSCALE = 2.0
    DEBUG_PREVIEW_SIZE = 320

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        provider = settings.execution_provider
        self.face_analyzer = FaceAnalysis(
            name=settings.insightface_model_name,
            root=str(settings.insightface_model_dir),
            providers=[provider],
        )
        self.face_analyzer.prepare(ctx_id=0 if provider != 'CPUExecutionProvider' else -1, det_size=(640, 640))
        self.face_swapper = insightface.model_zoo.get_model(
            str(settings.inswapper_model_path),
            providers=[provider],
        )

    def _read_image(self, path: str, label: str) -> np.ndarray:
        image = cv2.imread(path, cv2.IMREAD_COLOR)
        if image is None:
            raise FaceSwapError(f'Unable to read {label} image.')
        return image

    @staticmethod
    def _largest_face(faces: list) -> object:
        return max(faces, key=lambda face: (face.bbox[2] - face.bbox[0]) * (face.bbox[3] - face.bbox[1]))

    @staticmethod
    def _face_dimensions(face: object) -> tuple[float, float]:
        width = float(face.bbox[2] - face.bbox[0])
        height = float(face.bbox[3] - face.bbox[1])
        return width, height

    @classmethod
    def _face_size(cls, face: object) -> float:
        width, height = cls._face_dimensions(face)
        return min(width, height)

    def _validate_face_size(self, face: object, label: str) -> None:
        if self._face_size(face) < self.MIN_FACE_SIZE:
            raise FaceSwapError(
                f'{label} face is too small for a clean swap. Use a closer, sharper image with a clearer frontal face.'
            )

    def _extract_face_crop(self, image: np.ndarray, face: object, padding: float) -> np.ndarray:
        height, width = image.shape[:2]
        x1, y1, x2, y2 = face.bbox.astype(int)
        face_width = x2 - x1
        face_height = y2 - y1
        pad_x = int(face_width * padding)
        pad_y = int(face_height * padding)
        crop_x1 = max(0, x1 - pad_x)
        crop_y1 = max(0, y1 - pad_y)
        crop_x2 = min(width, x2 + pad_x)
        crop_y2 = min(height, y2 + pad_y)
        return image[crop_y1:crop_y2, crop_x1:crop_x2].copy()

    def _prepare_debug_preview(self, crop: np.ndarray) -> np.ndarray:
        if crop.size == 0:
            raise FaceSwapError('Failed to prepare debug face crop.')

        height, width = crop.shape[:2]
        scale = min(self.DEBUG_PREVIEW_SIZE / width, self.DEBUG_PREVIEW_SIZE / height)
        resized = cv2.resize(crop, (max(1, int(width * scale)), max(1, int(height * scale))), interpolation=cv2.INTER_CUBIC)
        canvas = np.full((self.DEBUG_PREVIEW_SIZE, self.DEBUG_PREVIEW_SIZE, 3), 245, dtype=np.uint8)
        y_offset = (self.DEBUG_PREVIEW_SIZE - resized.shape[0]) // 2
        x_offset = (self.DEBUG_PREVIEW_SIZE - resized.shape[1]) // 2
        canvas[y_offset:y_offset + resized.shape[0], x_offset:x_offset + resized.shape[1]] = resized
        return canvas

    def _detect_largest_face(self, image: np.ndarray, label: str) -> object:
        faces = self.face_analyzer.get(image)
        if not faces:
            raise FaceSwapError(f'No face detected in {label} image.')
        return self._largest_face(faces)

    def _prepare_source_face(self, source_image: np.ndarray) -> tuple[object, np.ndarray]:
        source_face = self._detect_largest_face(source_image, 'source')
        self._validate_face_size(source_face, 'Source')

        source_crop = self._extract_face_crop(source_image, source_face, self.SOURCE_CROP_PADDING)
        refined_faces = self.face_analyzer.get(source_crop)
        if refined_faces:
            refined_face = self._largest_face(refined_faces)
            if self._face_size(refined_face) >= self.MIN_FACE_SIZE:
                return refined_face, source_crop

        return source_face, source_crop

    def _prepare_target_image(self, target_image: np.ndarray) -> tuple[np.ndarray, object, float, np.ndarray]:
        target_face = self._detect_largest_face(target_image, 'target')
        target_crop = self._extract_face_crop(target_image, target_face, self.TARGET_CROP_PADDING)

        scale_factor = 1.0
        target_size = self._face_size(target_face)
        if target_size < self.PREFERRED_TARGET_FACE_SIZE:
            scale_factor = min(self.MAX_TARGET_UPSCALE, self.PREFERRED_TARGET_FACE_SIZE / max(target_size, 1.0))

        working_image = target_image
        working_face = target_face

        if scale_factor > 1.01:
            working_image = cv2.resize(target_image, None, fx=scale_factor, fy=scale_factor, interpolation=cv2.INTER_CUBIC)
            working_face = self._detect_largest_face(working_image, 'target')

        self._validate_face_size(working_face, 'Target')
        return working_image, working_face, scale_factor, target_crop

    @staticmethod
    def _cosine_similarity(source_face: object, target_face: object) -> float:
        source_embedding = np.asarray(source_face.normed_embedding, dtype=np.float32)
        target_embedding = np.asarray(target_face.normed_embedding, dtype=np.float32)
        similarity = float(np.dot(source_embedding, target_embedding))
        return max(-1.0, min(1.0, similarity))

    def _build_recommendations(self, similarity: float, source_size: float, target_size: float) -> list[str]:
        recommendations: list[str] = []
        if similarity < 0.2:
            recommendations.append('The two faces are structurally far apart. Try a source photo with a more similar angle, expression, and lighting.')
        elif similarity < 0.4:
            recommendations.append('The identity gap is moderate. A source image with more similar face shape and hairstyle should improve realism.')
        else:
            recommendations.append('The faces are reasonably close for this model. Fine-tuning image choice should improve the match more than changing prompts.')

        if source_size < 72:
            recommendations.append('Use a tighter, sharper source portrait so the source identity embedding is stronger.')
        if target_size < 72:
            recommendations.append('Crop the target image closer to the face or use a higher-resolution target for a cleaner blend.')

        recommendations.append('For best results, keep both faces front-facing with similar camera distance and natural lighting.')
        return recommendations

    def analyze_pair(
        self,
        source_path: str,
        target_path: str,
        source_preview_path: str | None = None,
        target_preview_path: str | None = None,
    ) -> dict[str, object]:
        source_image = self._read_image(source_path, 'source')
        target_image = self._read_image(target_path, 'target')

        source_face, source_crop = self._prepare_source_face(source_image)
        target_face = self._detect_largest_face(target_image, 'target')
        self._validate_face_size(target_face, 'Target')
        target_crop = self._extract_face_crop(target_image, target_face, self.TARGET_CROP_PADDING)

        similarity = self._cosine_similarity(source_face, target_face)
        similarity_percent = round(((similarity + 1.0) / 2.0) * 100.0, 1)
        source_size = round(self._face_size(source_face), 1)
        target_size = round(self._face_size(target_face), 1)

        if source_preview_path:
            preview = self._prepare_debug_preview(source_crop)
            Path(source_preview_path).parent.mkdir(parents=True, exist_ok=True)
            cv2.imwrite(source_preview_path, preview)
        if target_preview_path:
            preview = self._prepare_debug_preview(target_crop)
            Path(target_preview_path).parent.mkdir(parents=True, exist_ok=True)
            cv2.imwrite(target_preview_path, preview)

        return {
            'similarity_score': round(similarity, 4),
            'similarity_percent': similarity_percent,
            'source_face_size': source_size,
            'target_face_size': target_size,
            'recommendations': self._build_recommendations(similarity, source_size, target_size),
        }

    def swap_faces(self, source_path: str, target_path: str, output_path: str) -> str:
        source_image = self._read_image(source_path, 'source')
        target_image = self._read_image(target_path, 'target')

        source_face, _ = self._prepare_source_face(source_image)
        working_target_image, working_target_face, scale_factor, _ = self._prepare_target_image(target_image)

        swapped_image = self.face_swapper.get(
            working_target_image.copy(),
            working_target_face,
            source_face,
            paste_back=True,
        )

        if swapped_image is None:
            raise FaceSwapError('Face swap failed during model inference.')

        output = np.asarray(swapped_image, dtype=np.uint8)
        if scale_factor > 1.01:
            output = cv2.resize(output, (target_image.shape[1], target_image.shape[0]), interpolation=cv2.INTER_LANCZOS4)

        destination = Path(output_path)
        destination.parent.mkdir(parents=True, exist_ok=True)

        success = cv2.imwrite(str(destination), output)
        if not success:
            raise FaceSwapError('Failed to write output image.')

        return str(destination.resolve())
