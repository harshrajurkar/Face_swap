from pathlib import Path
from urllib.request import urlretrieve
import sys
import types

import cv2

from app.config import Settings
from app.services.face_service import FaceSwapError


class EnhancementService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._enhancer = None

    def _ensure_model(self) -> None:
        model_path = Path(self.settings.gfpgan_model_path)
        if model_path.exists():
            return

        model_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            urlretrieve(self.settings.gfpgan_model_url, model_path)
        except Exception as exc:  # noqa: BLE001
            raise FaceSwapError(
                "Unable to download GFPGAN model automatically. Place GFPGANv1.3.pth in the models directory."
            ) from exc

    @staticmethod
    def _install_torchvision_compat() -> None:
        module_name = 'torchvision.transforms.functional_tensor'
        if module_name in sys.modules:
            return

        try:
            from torchvision.transforms.functional import rgb_to_grayscale
        except Exception as exc:  # noqa: BLE001
            raise FaceSwapError(
                'Torchvision compatibility layer failed to load. Check your torch and torchvision installation.'
            ) from exc

        compat_module = types.ModuleType(module_name)
        compat_module.rgb_to_grayscale = rgb_to_grayscale
        sys.modules[module_name] = compat_module

    def _get_enhancer(self):
        if self._enhancer is not None:
            return self._enhancer

        self._install_torchvision_compat()

        try:
            from gfpgan import GFPGANer
        except ImportError as exc:  # noqa: BLE001
            raise FaceSwapError(
                f'GFPGAN import failed: {exc}'
            ) from exc

        self._ensure_model()
        device = 'cuda' if self.settings.execution_provider == 'CUDAExecutionProvider' else 'cpu'
        self._enhancer = GFPGANer(
            model_path=str(self.settings.gfpgan_model_path),
            upscale=1,
            arch='clean',
            channel_multiplier=2,
            bg_upsampler=None,
            device=device,
        )
        return self._enhancer

    def enhance_image(self, input_path: str, output_path: str) -> str:
        image = cv2.imread(input_path, cv2.IMREAD_COLOR)
        if image is None:
            raise FaceSwapError('Unable to read swapped image for enhancement.')

        enhancer = self._get_enhancer()
        _, _, restored_image = enhancer.enhance(
            image,
            has_aligned=False,
            only_center_face=False,
            paste_back=True,
        )

        if restored_image is None:
            raise FaceSwapError('GFPGAN enhancement failed.')

        success = cv2.imwrite(output_path, restored_image)
        if not success:
            raise FaceSwapError('Failed to write enhanced output image.')

        return output_path
