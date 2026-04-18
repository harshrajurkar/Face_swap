"""Face region extraction and blending utilities for efficient face swapping."""

import logging
from typing import Tuple

import cv2
import numpy as np

logger = logging.getLogger("face-swap-worker.face_region")


class FaceRegionProcessor:
    """Handles face region extraction, resizing, and seamless blending."""

    def __init__(
        self,
        processing_size: int = 512,
        padding_ratio: float = 0.4,
        blend_width: int = 40,
    ):
        """Initialize face region processor.

        Args:
            processing_size: Target size for face processing (512 or 768).
            padding_ratio: Padding around face bbox as ratio of bbox size.
            blend_width: Feathering width for seamless blending (pixels).
        """
        self.processing_size = processing_size
        self.padding_ratio = padding_ratio
        self.blend_width = blend_width

    def extract_face_region(
        self,
        image: np.ndarray,
        face_bbox: Tuple[float, float, float, float],
    ) -> Tuple[np.ndarray, dict]:
        """Extract face region with padding from image.

        Args:
            image: Input image (BGR, uint8).
            face_bbox: Face bounding box (x1, y1, x2, y2) from InsightFace.

        Returns:
            Tuple of (cropped_face_image, region_info_dict)
                region_info contains original coordinates and scaling factors.
        """
        h, w = image.shape[:2]
        x1, y1, x2, y2 = face_bbox
        bbox_w = x2 - x1
        bbox_h = y2 - y1

        # Calculate padding
        pad_x = int(bbox_w * self.padding_ratio / 2)
        pad_y = int(bbox_h * self.padding_ratio / 2)

        # Apply padding with image bounds
        crop_x1 = max(0, int(x1) - pad_x)
        crop_y1 = max(0, int(y1) - pad_y)
        crop_x2 = min(w, int(x2) + pad_x)
        crop_y2 = min(h, int(y2) + pad_y)

        # Extract region
        cropped = image[crop_y1:crop_y2, crop_x1:crop_x2].copy()

        region_info = {
            "original_bbox": (x1, y1, x2, y2),
            "crop_coords": (crop_x1, crop_y1, crop_x2, crop_y2),
            "crop_h": crop_y2 - crop_y1,
            "crop_w": crop_x2 - crop_x1,
            "original_image_shape": image.shape[:2],
        }

        logger.debug(
            "Extracted face region: crop_coords=%s, size=%dx%d",
            region_info["crop_coords"],
            region_info["crop_w"],
            region_info["crop_h"],
        )

        return cropped, region_info

    def resize_face_for_processing(self, face_image: np.ndarray) -> Tuple[np.ndarray, dict]:
        """Resize face region to processing size.

        Args:
            face_image: Extracted face region.

        Returns:
            Tuple of (resized_image, resize_info_dict).
        """
        h, w = face_image.shape[:2]
        original_size = (w, h)

        resized = cv2.resize(
            face_image,
            (self.processing_size, self.processing_size),
            interpolation=cv2.INTER_LANCZOS4,
        )

        scale_x = self.processing_size / w
        scale_y = self.processing_size / h

        resize_info = {
            "original_size": original_size,
            "target_size": (self.processing_size, self.processing_size),
            "scale_x": scale_x,
            "scale_y": scale_y,
        }

        logger.debug("Resized face: %s -> %s", original_size, self.processing_size)

        return resized, resize_info

    def scale_face_back(self, face_image: np.ndarray, resize_info: dict) -> np.ndarray:
        """Scale processed face back to original cropped region size.

        Args:
            face_image: Processed face image.
            resize_info: Info from resize_face_for_processing.

        Returns:
            Scaled face image matching original crop size.
        """
        orig_w, orig_h = resize_info["original_size"]
        scaled = cv2.resize(
            face_image,
            (orig_w, orig_h),
            interpolation=cv2.INTER_LANCZOS4,
        )
        return scaled

    def create_blend_mask(self, height: int, width: int) -> np.ndarray:
        """Create a feathered blending mask.

        Creates a smooth gradient mask for seamless blending.
        Edges are feathered to blend_width.

        Args:
            height: Mask height.
            width: Mask width.

        Returns:
            Blending mask (grayscale, 0-255).
        """
        blend_width = min(self.blend_width, height // 4, width // 4)
        mask = np.ones((height, width), dtype=np.float32) * 255

        # Feather edges
        for i in range(blend_width):
            alpha = i / blend_width
            mask[i, :] = mask[i, :] * alpha
            mask[height - 1 - i, :] = mask[height - 1 - i, :] * alpha
            mask[:, i] = mask[:, i] * alpha
            mask[:, width - 1 - i] = mask[:, width - 1 - i] * alpha

        return mask.astype(np.uint8)

    def blend_faces(
        self,
        original_image: np.ndarray,
        swapped_face: np.ndarray,
        region_info: dict,
    ) -> np.ndarray:
        """Seamlessly blend swapped face back into original image.

        Uses feathering-based blending for smooth integration.

        Args:
            original_image: Original high-resolution image (BGR, uint8).
            swapped_face: Processed swapped face (BGR, uint8).
            region_info: Region info from extract_face_region.

        Returns:
            Image with blended swapped face.
        """
        crop_x1, crop_y1, crop_x2, crop_y2 = region_info["crop_coords"]
        crop_h, crop_w = region_info["crop_h"], region_info["crop_w"]

        # Ensure swapped face matches crop size
        if swapped_face.shape[:2] != (crop_h, crop_w):
            swapped_face = cv2.resize(
                swapped_face,
                (crop_w, crop_h),
                interpolation=cv2.INTER_LANCZOS4,
            )

        # Create blending mask
        mask = self.create_blend_mask(crop_h, crop_w)
        mask_3ch = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR).astype(np.float32) / 255.0

        # Blend at crop region
        crop_region = original_image[crop_y1:crop_y2, crop_x1:crop_x2].astype(np.float32)
        swapped_face_f32 = swapped_face.astype(np.float32)

        blended_region = (
            crop_region * (1 - mask_3ch) + swapped_face_f32 * mask_3ch
        ).astype(np.uint8)

        # Copy back to original image
        result = original_image.copy()
        result[crop_y1:crop_y2, crop_x1:crop_x2] = blended_region

        logger.debug("Blended face region: %s", region_info["crop_coords"])

        return result

    def validate_face_region(self, face_image: np.ndarray, min_size: int = 80) -> bool:
        """Validate if extracted face region is large enough.

        Args:
            face_image: Extracted face region.
            min_size: Minimum allowed size in pixels.

        Returns:
            True if face is large enough.
        """
        h, w = face_image.shape[:2]
        return h >= min_size and w >= min_size
