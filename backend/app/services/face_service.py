import logging
from pathlib import Path
from urllib.request import urlretrieve

import cv2
import insightface
import numpy as np
from insightface.app import FaceAnalysis

from app.config import Settings
from app.services.face_region import FaceRegionProcessor

logger = logging.getLogger("face-swap-worker.face_service")


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
        detection_size = settings.face_detection_size if provider == "CPUExecutionProvider" else 640
        self.face_analyzer.prepare(
            ctx_id=0 if provider != "CPUExecutionProvider" else -1,
            det_size=(detection_size, detection_size),
        )
        self._ensure_swapper_model()
        self.face_swapper = insightface.model_zoo.get_model(
            str(settings.inswapper_model_path),
            providers=[provider],
        )
        # Initialize face region processor for optimized processing
        self.region_processor = FaceRegionProcessor(
            processing_size=settings.face_processing_size,
            padding_ratio=settings.face_padding_ratio,
            blend_width=settings.face_blend_width,
        )
        logger.info(
            "FaceService initialized with processing_size=%d, padding_ratio=%.2f, blend_width=%d",
            settings.face_processing_size,
            settings.face_padding_ratio,
            settings.face_blend_width,
        )

    def _ensure_swapper_model(self) -> None:
        model_path = Path(self.settings.inswapper_model_path)
        if model_path.exists():
            return

        model_path.parent.mkdir(parents=True, exist_ok=True)
        candidate_urls = [
            self.settings.inswapper_model_url,
            "https://github.com/facefusion/facefusion-assets/releases/download/models/inswapper_128.onnx",
            "https://raw.githubusercontent.com/based9based/faceswapper/main/inswapper_128.onnx",
        ]
        last_error = None
        for candidate_url in candidate_urls:
            try:
                urlretrieve(candidate_url, model_path)
                if model_path.exists():
                    return
            except Exception as exc:  # noqa: BLE001
                last_error = exc

        raise FaceSwapError(
            "Unable to download the inswapper model automatically. Place inswapper_128.onnx in backend/models."
        ) from last_error

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
        """Swap faces using either region-based or full-image processing.

        Uses region-based processing by default (optimized for low-resource systems).
        Falls back to full-image processing if disabled in settings.

        Args:
            source_path: Path to source image (face to copy from).
            target_path: Path to target image (where to apply face).
            output_path: Path to save output image.

        Returns:
            Path to output image.
        """
        if self.settings.enable_face_region_processing:
            logger.info("Using region-based face swap processing")
            return self.swap_faces_region(source_path, target_path, output_path)
        else:
            logger.info("Using full-image face swap processing")
            return self._swap_faces_full_image(source_path, target_path, output_path)

    def swap_faces_region(self, source_path: str, target_path: str, output_path: str) -> str:
        """Swap faces using region-based processing (optimized for low-resource systems).

        This method processes only the face region, not the entire image:
        1. Detect faces in target image
        2. Extract face region (with padding)
        3. Resize to processing size (512x512)
        4. Perform swap on cropped face
        5. Scale back and blend into original image
        6. Save at original resolution

        Args:
            source_path: Path to source image (face to copy from).
            target_path: Path to target image (where to apply face).
            output_path: Path to save output image.

        Returns:
            Path to output image.

        Raises:
            FaceSwapError: If detection, swap, or processing fails.
        """
        logger.info("Starting region-based face swap: source=%s target=%s", source_path, target_path)

        # Load images
        source_image = self._read_image(source_path, "source")
        target_image = self._read_image(target_path, "target")
        logger.debug("Loaded images: source shape=%s, target shape=%s", source_image.shape, target_image.shape)

        # Detect faces
        logger.debug("Detecting faces in source image...")
        source_faces = self.face_analyzer.get(source_image)
        logger.debug("Detecting faces in target image...")
        target_faces = self.face_analyzer.get(target_image)

        if not source_faces:
            raise FaceSwapError("No face detected in source image.")
        if not target_faces:
            raise FaceSwapError("No face detected in target image.")

        source_face = self._largest_face(source_faces)
        target_face = self._largest_face(target_faces)

        logger.debug("Validating face sizes...")
        self._validate_face_size(source_face, "Source")
        self._validate_face_size(target_face, "Target")

        # Stage 1: Extract target face region
        logger.debug("Stage 1/6: Extracting target face region...")
        target_crop, region_info = self.region_processor.extract_face_region(
            target_image, target_face.bbox
        )

        if not self.region_processor.validate_face_region(target_crop):
            raise FaceSwapError("Extracted face region is too small for processing.")

        # Debug: Save cropped face if enabled
        if self.settings.debug_save_intermediates:
            debug_crop_path = Path(output_path).parent / f"{Path(output_path).stem}_01_cropped.jpg"
            cv2.imwrite(str(debug_crop_path), target_crop)
            logger.debug("Saved cropped face: %s", debug_crop_path)

        # Stage 2: Resize for processing
        logger.debug("Stage 2/6: Resizing face region to %d x %d...", self.settings.face_processing_size, self.settings.face_processing_size)
        target_resized, resize_info = self.region_processor.resize_face_for_processing(target_crop)

        # Stage 3: Perform face swap
        logger.debug("Stage 3/6: Performing face swap...")
        try:
            swapped_face_resized = self.face_swapper.get(
                target_resized.copy(),
                target_face,
                source_face,
                paste_back=True,
            )
        except Exception as e:
            raise FaceSwapError(f"Face swap inference failed: {str(e)}") from e

        if swapped_face_resized is None:
            raise FaceSwapError("Face swap failed during model inference.")

        swapped_face_resized = np.asarray(swapped_face_resized, dtype=np.uint8)
        logger.debug("Face swap completed, output shape=%s", swapped_face_resized.shape)

        # Debug: Save swapped face
        if self.settings.debug_save_intermediates:
            debug_swapped_path = Path(output_path).parent / f"{Path(output_path).stem}_02_swapped.jpg"
            cv2.imwrite(str(debug_swapped_path), swapped_face_resized)
            logger.debug("Saved swapped face: %s", debug_swapped_path)

        # Stage 4: Scale back to crop size
        logger.debug("Stage 4/6: Scaling face back to original crop size...")
        swapped_face_scaled = self.region_processor.scale_face_back(swapped_face_resized, resize_info)

        # Stage 5: Blend into original image
        logger.debug("Stage 5/6: Blending swapped face into original image...")
        result_image = self.region_processor.blend_faces(
            target_image, swapped_face_scaled, region_info
        )

        # Stage 6: Save output
        logger.debug("Stage 6/6: Saving output image...")
        destination = Path(output_path)
        destination.parent.mkdir(parents=True, exist_ok=True)

        success = cv2.imwrite(str(destination), result_image)
        if not success:
            raise FaceSwapError("Failed to write output image.")

        logger.info("Face swap completed successfully: output=%s", destination.resolve())
        return str(destination.resolve())

    def _swap_faces_full_image(self, source_path: str, target_path: str, output_path: str) -> str:
        """Original face swap method - processes entire image.

        This is kept for backward compatibility and fallback scenarios.
        Not recommended for low-resource systems.

        Args:
            source_path: Path to source image.
            target_path: Path to target image.
            output_path: Path to save output image.

        Returns:
            Path to output image.
        """
        logger.info("Starting full-image face swap: source=%s target=%s", source_path, target_path)

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

        logger.info("Full-image face swap completed: output=%s", destination.resolve())
        return str(destination.resolve())
