"""
ComfyUI 3D Viewer Node
A node that embeds an interactive 3D viewer based on index.html
"""

import numpy as np
import hashlib


# Module-level cache to support multiple node instances independently
_cache = {}
_max_cache_size = 50  # Limit cache entries to prevent memory growth


class ComfyUI3DViewerNode:
    """
    3D Viewer Node
    Embeds an interactive 3D viewer widget that can display images
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "camera_x": ("FLOAT", {
                    "default": -4.0,
                    "min": -20.0,
                    "max": 20.0,
                    "step": 0.1,
                    "display": "slider"
                }),
                "camera_y": ("FLOAT", {
                    "default": 3.5,
                    "min": -10.0,
                    "max": 20.0,
                    "step": 0.1,
                    "display": "slider"
                }),
                "camera_z": ("FLOAT", {
                    "default": 4.0,
                    "min": -20.0,
                    "max": 20.0,
                    "step": 0.1,
                    "display": "slider"
                }),
                "fov": ("INT", {
                    "default": 75,
                    "min": 10,
                    "max": 120,
                    "step": 1,
                    "display": "slider"
                }),
            },
            "optional": {
            },
            "hidden": {
                "unique_id": "UNIQUE_ID",
            }
        }
    RETURN_TYPES = ("STRING","STRING","STRING","STRING","STRING")
    RETURN_NAMES = ("prompt","view_label","direction_degrees","distance_description","angle_description")
    FUNCTION = "generate_prompt"
    CATEGORY = "🔵BB 3DViewer"
    OUTPUT_NODE = True
    def _compute_image_hash(self, image):
        """Compute a hash of the image tensor for cache key comparison."""
        if image is None:
            return None
        try:
            # Get numpy array and create a hashable representation
            if hasattr(image, 'cpu'):
                img_tensor = image[0] if len(image.shape) == 4 else image
                img_np = img_tensor.cpu().numpy()
            elif hasattr(image, 'numpy'):
                img_np = image.numpy()
                if len(img_np.shape) == 4:
                    img_np = img_np[0]
            else:
                img_np = image
                if len(img_np.shape) == 4:
                    img_np = img_np[0]
            # Use bytes of the array for hashing
            return hashlib.md5(img_np.tobytes()).hexdigest()
        except Exception:
            return str(hash(str(image)))

    def generate_prompt(self, camera_x, camera_y, camera_z, fov, unique_id=None):
        # Validate input ranges
        camera_x = max(-20.0, min(20.0, float(camera_x)))
        camera_y = max(-10.0, min(20.0, float(camera_y)))
        camera_z = max(-20.0, min(20.0, float(camera_z)))
        fov = max(10, min(120, int(fov)))

        cache_key = str(unique_id) if unique_id else "default"
        cached = _cache.get(cache_key, {})
        if (cached.get('camera_x') == camera_x and
            cached.get('camera_y') == camera_y and
            cached.get('camera_z') == camera_z and
            cached.get('fov') == fov):
            return cached['result']

        # Use the same target as the viewer so angles match the frontend.
        # The viewer's model center is at (0, 0.6, 0).
        target = np.array([0.0, 0.6, 0.0])
        cam = np.array([camera_x, camera_y, camera_z])
        direction = cam - target

        # horizontal angle (around Y axis), 0-360
        horizontal_angle = np.degrees(np.arctan2(direction[0], direction[2]))
        horizontal_angle = float(((horizontal_angle % 360) + 360) % 360)

        # vertical angle (angle relative to horizontal plane)
        dist_xz = float(np.sqrt(direction[0] ** 2 + direction[2] ** 2))
        vertical_angle = float(np.degrees(np.arctan2(direction[1], dist_xz)))

        # approximate zoom mapping based on distance
        distance = float(np.linalg.norm(direction))
        minDist = 2.0
        maxDist = 20.0
        d = max(minDist, min(maxDist, distance))
        t = (d - minDist) / (maxDist - minDist)
        gamma = 1.8
        zoom = float(max(0.0, min(10.0, (1 - t) ** gamma * 10)))

        # Map to prompt strings following index.html / viewer mappings
        h = horizontal_angle
        if h < 22.5 or h >= 337.5:
            h_direction = "front"
        elif h < 67.5:
            h_direction = "front-right"
        elif h < 112.5:
            h_direction = "right side"
        elif h < 157.5:
            h_direction = "back-right"
        elif h < 202.5:
            h_direction = "back"
        elif h < 247.5:
            h_direction = "back-left"
        elif h < 292.5:
            h_direction = "left side"
        else:
            h_direction = "front-left"

        if vertical_angle < -60:
            v_direction = "bottom-up view"
        elif vertical_angle < -15:
            v_direction = "low-angle shot"
        elif vertical_angle < 15:
            v_direction = "eye-level shot"
        elif vertical_angle < 60:
            v_direction = "elevated shot"
        elif vertical_angle < 85:
            v_direction = "high-angle shot"
        else:
            v_direction = "top-down view"

        if zoom < 2:
            distance_desc = "wide shot"
        elif zoom < 4:
            distance_desc = "medium shot"
        elif zoom < 6:
            distance_desc = "close shot"
        else:
            distance_desc = "close-up"

        # Build concise camera info string containing only requested fields:
        # Location, Horizontal angle, Vertical angle, FOV
        camera_info_str = (
            f"Location: X:{camera_x:.2f}, Y:{camera_y:.2f}, Z:{camera_z:.2f}; "
            f"Horizontal angle: {horizontal_angle:.2f}°; Vertical angle: {vertical_angle:.2f}°; FOV: {fov:.1f}"
        )

        # view_label (English): map horizontal octants to English phrases
        h_map = {
            "front": "front",
            "front-right": "front-right",
            "right side": "right",
            "back-right": "back-right",
            "back": "back",
            "back-left": "back-left",
            "left side": "left",
            "front-left": "front-left"
        }

        # Determine primary horizontal axis (right/left/front/back) for vertical combination rules
        if "right" in h_direction:
            primary_h = "right"
        elif "left" in h_direction:
            primary_h = "left"
        elif "front" in h_direction:
            primary_h = "front"
        else:
            primary_h = "back"

        # Determine vertical label based on camera Y position and vertical angle
        dy = camera_y - float(target[1])
        y_threshold = 0.5  # if camera is this far above/below target, consider it upper/lower

        # Check for top-down and bottom-up special cases
        if vertical_angle >= 85:
            v_label = "top-down"
        elif vertical_angle <= -60:
            v_label = "bottom-up"
        elif dy > y_threshold:
            v_label = "upper"
        elif dy < -y_threshold:
            v_label = "lower"
        else:
            v_label = ""

        # If vertical significant, prefer vertical-first style
        if v_label:
            view_label = f"{v_label}-{primary_h}"
        else:
            # No vertical emphasis: use the full horizontal mapping
            view_label = h_map.get(h_direction, h_direction)

        # Build directional degrees output: angular difference between camera horizontal angle
        # and canonical direction centers (0,45,90,...). Also include vertical angle.
        centers = [
            ("front", 0.0),
            ("front-right", 45.0),
            ("right", 90.0),
            ("back-right", 135.0),
            ("back", 180.0),
            ("back-left", 225.0),
            ("left", 270.0),
            ("front-left", 315.0)
        ]

        def angular_diff(a, b):
            diff = abs(((a - b + 180.0) % 360.0) - 180.0)
            return diff

        # Return only the closest horizontal direction and its angular difference
        closest = min(centers, key=lambda nc: angular_diff(horizontal_angle, nc[1]))
        closest_name, closest_center = closest
        closest_diff = angular_diff(horizontal_angle, closest_center)
        direction_degrees = f"{closest_name}: {closest_diff:.2f}°"

        result = {"ui": {"image_base64": [""]}, "result": (camera_info_str, view_label, direction_degrees, distance_desc, v_direction)}

        _cache[cache_key] = {
            'camera_x': camera_x,
            'camera_y': camera_y,
            'camera_z': camera_z,
            'fov': fov,
            'result': result
        }
        if len(_cache) > _max_cache_size:
            keys_to_remove = list(_cache.keys())[:len(_cache) - _max_cache_size]
            for key in keys_to_remove:
                del _cache[key]

        return result

    @classmethod
    def IS_CHANGED(cls, camera_x, camera_y, camera_z, fov, unique_id=None):
        # Return a hash of inputs so node only re-runs when inputs actually change
        try:
            return f"{camera_x}_{camera_y}_{camera_z}_{fov}"
        except Exception:
            return f"{camera_x}_{camera_y}_{camera_z}_{fov}"


NODE_CLASS_MAPPINGS = {
    "ComfyUI3DViewerNode": ComfyUI3DViewerNode,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "ComfyUI3DViewerNode": "🔵BB 3D空间提示词",
}