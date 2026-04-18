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
        print(f"[DEBUG] Checking GFPGAN model at: {model_path}")
        
        if model_path.exists():
            print(f"[DEBUG] GFPGAN model exists")
            return

        print(f"[DEBUG] GFPGAN model not found, creating directory and downloading...")
        model_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            print(f"[DEBUG] Downloading from {self.settings.gfpgan_model_url}")
            urlretrieve(self.settings.gfpgan_model_url, model_path)
            print(f"[SUCCESS] ✓ GFPGAN model downloaded")
        except Exception as exc:  # noqa: BLE001
            print(f"[ERROR] Failed to download GFPGAN model: {str(exc)}")
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
            print(f"[DEBUG] Enhancer already loaded, returning cached instance")
            return self._enhancer

        print(f"[DEBUG] Initializing GFPGAN enhancer...")
        self._install_torchvision_compat()
        print(f"[DEBUG] Torchvision compatibility installed")

        try:
            print(f"[DEBUG] Importing GFPGANer...")
            from gfpgan import GFPGANer
            print(f"[DEBUG] GFPGANer imported successfully")
        except ImportError as exc:  # noqa: BLE001
            print(f"[ERROR] GFPGANer import failed: {exc}")
            raise FaceSwapError(
                f'GFPGAN import failed: {exc}'
            ) from exc

        self._ensure_model()
        device = 'cuda' if self.settings.execution_provider == 'CUDAExecutionProvider' else 'cpu'
        print(f"[DEBUG] Creating GFPGANer with device={device}")
        self._enhancer = GFPGANer(
            model_path=str(self.settings.gfpgan_model_path),
            upscale=1,
            arch='clean',
            channel_multiplier=2,
            bg_upsampler=None,
            device=device,
        )
        print(f"[DEBUG] GFPGANer initialized successfully")
        return self._enhancer

    def enhance_image(self, input_path: str, output_path: str) -> str:
        print(f"\n[DEBUG] enhance_image() starting")
        print(f"[DEBUG] Input: {input_path}, Output: {output_path}")
        
        image = cv2.imread(input_path, cv2.IMREAD_COLOR)
        if image is None:
            print(f"[ERROR] Failed to read swapped image for enhancement")
            raise FaceSwapError('Unable to read swapped image for enhancement.')
        print(f"[DEBUG] Image loaded, shape={image.shape}")

        print(f"[DEBUG] Getting GFPGAN enhancer...")
        enhancer = self._get_enhancer()
        print(f"[DEBUG] Running enhancement...")
        
        _, _, restored_image = enhancer.enhance(
            image,
            has_aligned=False,
            only_center_face=False,
            paste_back=True,
        )
        print(f"[DEBUG] Enhancement complete")

        if restored_image is None:
            print(f"[ERROR] GFPGAN enhancement failed - returned None")
            raise FaceSwapError('GFPGAN enhancement failed.')

        print(f"[DEBUG] Writing enhanced image to {output_path}")
        success = cv2.imwrite(output_path, restored_image)
        if not success:
            print(f"[ERROR] Failed to write enhanced output image")
            raise FaceSwapError('Failed to write enhanced output image.')

        print(f"[SUCCESS] ✓ Enhancement saved successfully")
        return output_path
