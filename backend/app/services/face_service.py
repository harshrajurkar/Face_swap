from pathlib import Path

import cv2
import insightface
import numpy as np
from insightface.app import FaceAnalysis

from app.config import Settings


class FaceSwapError(Exception):
    """Raised when face swap processing fails."""


class FaceService:
    MIN_FACE_SIZE = 80

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        provider = settings.execution_provider
        self.face_analyzer = FaceAnalysis(
            name=settings.insightface_model_name,
            root=str(settings.insightface_model_dir),
            providers=[provider],
        )
        self.face_analyzer.prepare(ctx_id=0 if provider != "CPUExecutionProvider" else -1, det_size=(640, 640))
        self.face_swapper = insightface.model_zoo.get_model(
            str(settings.inswapper_model_path),
            providers=[provider],
        )

    def _read_image(self, path: str, label: str) -> np.ndarray:
        image = cv2.imread(path, cv2.IMREAD_COLOR)
        if image is None:
            raise FaceSwapError(f"Unable to read {label} image.")
        return image

    @staticmethod
    def _largest_face(faces: list) -> object:
        return max(faces, key=lambda face: (face.bbox[2] - face.bbox[0]) * (face.bbox[3] - face.bbox[1]))

    def _validate_face_size(self, face: object, label: str) -> None:
        width = face.bbox[2] - face.bbox[0]
        height = face.bbox[3] - face.bbox[1]
        if width < self.MIN_FACE_SIZE or height < self.MIN_FACE_SIZE:
            raise FaceSwapError(
                f"{label} face is too small for a clean swap. Use a closer, sharper image with a clear frontal face."
            )

    def swap_faces(self, source_path: str, target_path: str, output_path: str) -> str:
        source_image = self._read_image(source_path, "source")
        target_image = self._read_image(target_path, "target")

        source_faces = self.face_analyzer.get(source_image)
        target_faces = self.face_analyzer.get(target_image)

        if not source_faces:
            raise FaceSwapError("No face detected in source image.")
        if not target_faces:
            raise FaceSwapError("No face detected in target image.")

        source_face = self._largest_face(source_faces)
        target_face = self._largest_face(target_faces)

        self._validate_face_size(source_face, "Source")
        self._validate_face_size(target_face, "Target")

        swapped_image = self.face_swapper.get(
            target_image.copy(),
            target_face,
            source_face,
            paste_back=True,
        )

        if swapped_image is None:
            raise FaceSwapError("Face swap failed during model inference.")

        output = np.asarray(swapped_image, dtype=np.uint8)
        destination = Path(output_path)
        destination.parent.mkdir(parents=True, exist_ok=True)

        success = cv2.imwrite(str(destination), output)
        if not success:
            raise FaceSwapError("Failed to write output image.")

        return str(destination.resolve())
