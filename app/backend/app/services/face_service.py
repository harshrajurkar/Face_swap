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
        print("\n[DEBUG] FaceService.__init__() starting...")
        self.settings = settings
        provider = settings.execution_provider
        print(f"[DEBUG] Execution provider: {provider}")
        
        print(f"[DEBUG] Loading FaceAnalysis with model_name={settings.insightface_model_name}")
        self.face_analyzer = FaceAnalysis(
            name=settings.insightface_model_name,
            root=str(settings.insightface_model_dir),
            providers=[provider],
        )
        print(f"[DEBUG] FaceAnalysis loaded")
        
        detection_size = settings.face_detection_size if provider == "CPUExecutionProvider" else 640
        print(f"[DEBUG] Detection size: {detection_size}x{detection_size}")
        self.face_analyzer.prepare(
            ctx_id=0 if provider != "CPUExecutionProvider" else -1,
            det_size=(detection_size, detection_size),
        )
        print(f"[DEBUG] FaceAnalysis prepared")
        
        print(f"[DEBUG] Ensuring swapper model exists...")
        self._ensure_swapper_model()
        print(f"[DEBUG] Loading face swapper model from {settings.inswapper_model_path}")
        self.face_swapper = insightface.model_zoo.get_model(
            str(settings.inswapper_model_path),
            providers=[provider],
        )
        print(f"[DEBUG] Face swapper model loaded")
        
        # Initialize face region processor for optimized processing
        print(f"[DEBUG] Initializing FaceRegionProcessor...")
        self.region_processor = FaceRegionProcessor(
            processing_size=settings.face_processing_size,
            padding_ratio=settings.face_padding_ratio,
            blend_width=settings.face_blend_width,
        )
        print(f"[DEBUG] FaceRegionProcessor initialized")
        print(f"[DEBUG] FaceService.__init__() complete\n")
        
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
        print(f"[DEBUG] Reading {label} image from: {path}")
        image = cv2.imread(path, cv2.IMREAD_COLOR)
        if image is None:
            print(f"[ERROR] Failed to read {label} image from {path}")
            raise FaceSwapError(f"Unable to read {label} image.")
        print(f"[DEBUG] {label} image read successfully - shape: {image.shape}")
        return image

    @staticmethod
    def _largest_face(faces: list) -> object:
        print(f"[DEBUG] Finding largest face among {len(faces)} detected face(s)")
        largest = max(faces, key=lambda face: (face.bbox[2] - face.bbox[0]) * (face.bbox[3] - face.bbox[1]))
        bbox = largest.bbox
        width = bbox[2] - bbox[0]
        height = bbox[3] - bbox[1]
        print(f"[DEBUG] Largest face: width={width:.1f}, height={height:.1f}, bbox={bbox}")
        return largest

    def _validate_face_size(self, face: object, label: str) -> None:
        width = face.bbox[2] - face.bbox[0]
        height = face.bbox[3] - face.bbox[1]
        print(f"[DEBUG] Validating {label} face size: {width:.1f}x{height:.1f} (min required: {self.MIN_FACE_SIZE}x{self.MIN_FACE_SIZE})")
        if width < self.MIN_FACE_SIZE or height < self.MIN_FACE_SIZE:
            print(f"[ERROR] {label} face is too small!")
            raise FaceSwapError(
                f"{label} face is too small for a clean swap. Use a closer, sharper image with a clear frontal face."
            )
        print(f"[DEBUG] {label} face size validation passed")

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
        print(f"\n[DEBUG] swap_faces() called")
        print(f"[DEBUG] enable_face_region_processing={self.settings.enable_face_region_processing}")
        if self.settings.enable_face_region_processing:
            print(f"[DEBUG] Using region-based face swap processing")
            logger.info("Using region-based face swap processing")
            return self.swap_faces_region(source_path, target_path, output_path)
        else:
            print(f"[DEBUG] Using full-image face swap processing")
            logger.info("Using full-image face swap processing")
            return self._swap_faces_full_image(source_path, target_path, output_path)

    def swap_faces_region(self, source_path: str, target_path: str, output_path: str) -> str:
        print(f"\n[DEBUG] swap_faces_region() starting")
        logger.info("Starting region-based face swap: source=%s target=%s", source_path, target_path)

        source_image = self._read_image(source_path, "source")
        target_image = self._read_image(target_path, "target")

        # Detect faces
        print(f"[DEBUG] Stage: face_detection - Detecting faces in source image...")
        source_faces = self.face_analyzer.get(source_image)
        print(f"[DEBUG] Found {len(source_faces)} face(s) in source image")
        
        print(f"[DEBUG] Stage: face_detection - Detecting faces in target image...")
        target_faces = self.face_analyzer.get(target_image)
        print(f"[DEBUG] Found {len(target_faces)} face(s) in target image")

        if not source_faces:
            print(f"[ERROR] No face detected in source image")
            raise FaceSwapError("No face detected in source image.")
        if not target_faces:
            print(f"[ERROR] No face detected in target image")
            raise FaceSwapError("No face detected in target image.")

        source_face = self._largest_face(source_faces)
        target_face = self._largest_face(target_faces)

        self._validate_face_size(source_face, "Source")
        self._validate_face_size(target_face, "Target")

        # -------- Stage 1: Extract region --------
        print(f"[DEBUG] Stage: face_extraction (progress: 25-35%) - Extracting face region from target image...")
        target_crop, region_info = self.region_processor.extract_face_region(
            target_image, target_face.bbox
        )
        print(f"[DEBUG] Region extracted, shape={target_crop.shape}")

        if not self.region_processor.validate_face_region(target_crop):
            print(f"[ERROR] Face region validation failed")
            raise FaceSwapError("Face region too small.")
        print(f"[DEBUG] Region validation passed")

        # -------- Stage 2: Resize --------
        print(f"[DEBUG] Stage: face_extraction (progress: 30%) - Resizing face region for processing...")
        target_resized, resize_info = self.region_processor.resize_face_for_processing(target_crop)
        print(f"[DEBUG] Resized to {target_resized.shape}")

        # -------- Stage 3: RE-DETECT FACE (CRITICAL FIX) --------
        print(f"[DEBUG] Stage: face_detection (progress: 35%) - Re-detecting face in resized region...")
        resized_faces = self.face_analyzer.get(target_resized)
        print(f"[DEBUG] Found {len(resized_faces)} face(s) in resized image")

        if not resized_faces:
            print(f"[ERROR] No face detected in resized region")
            raise FaceSwapError("No face detected in resized region.")

        resized_target_face = self._largest_face(resized_faces)

        # -------- Stage 4: SWAP --------
        print(f"[DEBUG] Stage: face_swapping (progress: 40-55%) - Performing face swap...")
        try:
            swapped_face_resized = self.face_swapper.get(
                target_resized.copy(),
                resized_target_face,
                source_face,
                paste_back=True,
            )
        except Exception as e:
            print(f"[ERROR] Face swap failed: {str(e)}")
            raise FaceSwapError(f"Swap failed: {str(e)}")

        if swapped_face_resized is None:
            print(f"[ERROR] Face swapper returned None")
            raise FaceSwapError("Swap returned None.")
        print(f"[DEBUG] Face swap completed")

        swapped_face_resized = np.asarray(swapped_face_resized, dtype=np.uint8)

        # -------- Stage 5: SCALE BACK --------
        print(f"[DEBUG] Stage: blending (progress: 55-65%) - Scaling face back to original size...")
        swapped_face_scaled = self.region_processor.scale_face_back(
            swapped_face_resized,
            resize_info
        )
        print(f"[DEBUG] Scaled to {swapped_face_scaled.shape}")

        # -------- Stage 6: BLEND --------
        print(f"[DEBUG] Stage: blending (progress: 65-75%) - Blending faces for seamless result...")
        result_image = self.region_processor.blend_faces(
            target_image,
            swapped_face_scaled,
            region_info
        )
        print(f"[DEBUG] Blending complete")

        # -------- Stage 7: SAVE --------
        print(f"[DEBUG] Stage: saving (progress: 75%) - Saving output image to {output_path}...")
        destination = Path(output_path)
        destination.parent.mkdir(parents=True, exist_ok=True)

        if not cv2.imwrite(str(destination), result_image):
            print(f"[ERROR] Failed to save output image")
            raise FaceSwapError("Failed to save output image.")

        print(f"[SUCCESS] ✓ Face swap complete: {destination}")
        logger.info("Face swap done: %s", destination)
        return str(destination)

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
