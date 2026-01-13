/**
 * Inline HTML for the 3D Viewer
 * Contains the complete Three.js scene for camera control
 */
export const VIEWER_HTML = `
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            width: 100%;
            height: 100vh;
            overflow: hidden;
            background: #000;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        }

        #container {
            width: 100%;
            height: 100%;
            position: relative;
        }

        #threejs-container {
            width: 100%;
            height: 100%;
        }

        #info {
            position: absolute;
            top: 8px;
            left: 8px;
            display: none;
            color: white;
            background: rgba(0, 0, 0, 0.5);
            padding: 8px;
            border-radius: 5px;
            font-size: 12px;
        }

        #controls {
            position: absolute;
            top: 8px;
            right: 8px;
            color: white;
            background: rgba(0, 0, 0, 0.5);
            padding: 8px;
            border-radius: 5px;
            font-size: 12px;
            display: none; /* 隐藏右上角的模型/控制信息 */
        }

        #camera-info {
            position: absolute;
            bottom: 8px;
            left: 8px;
            right: 8px;
            background: rgba(0, 0, 0, 0.7);
            border: 1px solid rgba(100, 100, 255, 0.3);
            border-radius: 6px;
            padding: 8px 12px;
            font-size: 11px;
            color: #e0e0e0;
            display: flex;
            justify-content: space-around;
            backdrop-filter: blur(4px);
        }

        .info-row {
            margin: 3px 0;
            display: flex;
            justify-content: space-between;
        }

        .info-row span:first-child {
            color: #888;
            font-size: 10px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        .info-row span:last-child {
            color: #00ff00;
            font-weight: 600;
            font-size: 11px;
        }

        .fov-control {
            margin-top: 8px;
            text-align: center;
        }

        .fov-control label {
            display: block;
            margin-bottom: 3px;
            color: #888;
            font-size: 10px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        .fov-control input[type="range"] {
            width: 100%;
            height: 4px;
            border-radius: 2px;
            background: #333;
            outline: none;
        }

        .fov-control input[type="range"]::-webkit-slider-thumb {
            appearance: none;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            background: #00ff00;
            cursor: pointer;
        }

        .fov-control .value {
            font-weight: bold;
            color: #00ff00;
            font-size: 13px;
        }

        #reset-btn {
            position: absolute;
            right: 8px;
            bottom: 8px;
            width: 24px;
            height: 24px;
            border-radius: 4px;
            border: 1px solid rgba(100, 100, 255, 0.4);
            background: rgba(0, 0, 0, 0.8);
            color: #00ff00;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 14px;
            transition: all 0.2s ease;
        }

        #reset-btn:hover {
            background: rgba(100, 100, 255, 0.2);
            border-color: #00ff00;
        }

        #reset-btn:active {
            transform: scale(0.95);
        }
    </style>
</head>
<body>
    <div id="container">
        <div id="threejs-container"></div>
        <div id="info">
            <h3>3D查看器</h3>
            <p>鼠标左键拖拽：旋转视角</p>
            <p>鼠标滚轮：缩放</p>
            <p>鼠标右键拖拽：平移</p>
        </div>
        <div id="controls">
            <p>模型：小人</p>
            <p>控制：轨道控制</p>
        </div>

        <div id="camera-info">
            <div class="info-row">
                <span>相机位置 X:</span>
                <span id="camera-x">0.00</span>
            </div>
            <div class="info-row">
                <span>相机位置 Y:</span>
                <span id="camera-y">0.00</span>
            </div>
            <div class="info-row">
                <span>相机位置 Z:</span>
                <span id="camera-z">0.00</span>
            </div>
            <div class="fov-control">
                <label for="fov-slider">焦距 (FOV): <span class="value" id="fov-value">75</span>°</label>
                <input type="range" id="fov-slider" min="10" max="120" value="75" step="1">
            </div>
            <button id="reset-btn" title="重置到默认值">↺</button>
        </div>
    </div>

    <!-- Three.js CDN -->
    <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
    <!-- OrbitControls -->
    <script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js"></script>

    <script>
        // State
        let state = {
            cameraX: -4.0,
            cameraY: 3.5,
            cameraZ: 4.0,
            fov: 75,
            imageUrl: null
        };

        let threeScene = null;

        // DOM Elements
        const container = document.getElementById('threejs-container');
        const cameraXEl = document.getElementById('camera-x');
        const cameraYEl = document.getElementById('camera-y');
        const cameraZEl = document.getElementById('camera-z');
        const fovValueEl = document.getElementById('fov-value');
        const fovSliderEl = document.getElementById('fov-slider');

        function updateDisplay() {
            cameraXEl.textContent = state.cameraX.toFixed(2);
            cameraYEl.textContent = state.cameraY.toFixed(2);
            cameraZEl.textContent = state.cameraZ.toFixed(2);
            fovValueEl.textContent = state.fov;
            fovSliderEl.value = state.fov;

            // Do not call controls.update() here — OrbitControls emits 'change'
            // events that call updateDisplay(), calling controls.update() inside
            // updateDisplay() causes an infinite recursion and stack overflow.
            // Keep DOM updates only.
            // Note: Do not reset target here as it would interfere with panning
        }

        function sendCameraUpdate() {
            window.parent.postMessage({
                type: 'CAMERA_UPDATE',
                cameraX: Math.round(state.cameraX * 100) / 100,
                cameraY: Math.round(state.cameraY * 100) / 100,
                cameraZ: Math.round(state.cameraZ * 100) / 100,
                fov: Math.round(state.fov)
            }, '*');
        }

        function resetToDefaults() {
            state.cameraX = -4.045072549097186;
            state.cameraY = 3.5591969500617946;
            state.cameraZ = 4.159183210195669;
            state.fov = 75;

            if (threeScene) {
                threeScene.camera.position.set(state.cameraX, state.cameraY, state.cameraZ);
                threeScene.camera.fov = state.fov;
                threeScene.camera.updateProjectionMatrix();
                threeScene.controls.target.set(0, 0.6, 0);
                threeScene.controls.update();
            }

            updateDisplay();
            sendCameraUpdate();
        }

        // Reset button handler
        document.getElementById('reset-btn').addEventListener('click', resetToDefaults);

        // FOV slider handler
        fovSliderEl.addEventListener('input', function() {
            const newFov = parseInt(this.value);
            state.fov = newFov;
            if (threeScene) {
                threeScene.camera.fov = newFov;
                threeScene.camera.updateProjectionMatrix();
            }
            updateDisplay();
            sendCameraUpdate();
        });

        function initThreeJS() {
            const width = container.clientWidth;
            const height = container.clientHeight;

            // Scene
            const scene = new THREE.Scene();
            scene.background = new THREE.Color(0x1a1a1a);

            // Camera
            const camera = new THREE.PerspectiveCamera(state.fov, width / height, 0.1, 1000);
            camera.position.set(state.cameraX, state.cameraY, state.cameraZ);

            // Renderer
            const renderer = new THREE.WebGLRenderer({ antialias: true });
            renderer.setSize(width, height);
            renderer.shadowMap.enabled = true;
            renderer.shadowMap.type = THREE.PCFSoftShadowMap;
            container.appendChild(renderer.domElement);

            // OrbitControls
            const controls = new THREE.OrbitControls(camera, renderer.domElement);
            controls.enableDamping = true;
            controls.dampingFactor = 0.05;
            controls.enableZoom = true;
            controls.enablePan = true;
            controls.panSpeed = 2.0; // Increase pan speed for better responsiveness
            controls.minDistance = 2;
            controls.maxDistance = 20;

            // Fix right-click menu conflict by allowing context menu for right-click pan
            // Only prevent default for actual dragging operations, not for context menu
            let isRightMouseDown = false;
            let hasRightMouseMoved = false;

            renderer.domElement.addEventListener('contextmenu', (event) => {
                // Only prevent context menu if user actually dragged (panned)
                // Allow context menu if it was just a right-click without dragging
                if (hasRightMouseMoved) {
                    event.preventDefault();
                }
                isRightMouseDown = false;
                hasRightMouseMoved = false;
            });

            renderer.domElement.addEventListener('mousedown', (event) => {
                if (event.button === 2) { // Right mouse button
                    isRightMouseDown = true;
                    hasRightMouseMoved = false;
                }
            });

            renderer.domElement.addEventListener('mousemove', (event) => {
                if (isRightMouseDown && event.buttons & 2) { // Right mouse button is pressed
                    hasRightMouseMoved = true;
                }
            });

            renderer.domElement.addEventListener('mouseup', (event) => {
                if (event.button === 2) { // Right mouse button
                    isRightMouseDown = false;
                }
            });

            // Set initial target to the center of the human model (0, 0.6, 0)
            controls.target.set(0, 0.6, 0);
            controls.update();

            // Lighting
            const ambientLight = new THREE.AmbientLight(0x404040, 0.6);
            scene.add(ambientLight);

            const directionalLight = new THREE.DirectionalLight(0xffffff, 0.8);
            directionalLight.position.set(5, 10, 5);
            directionalLight.castShadow = true;
            directionalLight.shadow.mapSize.width = 2048;
            directionalLight.shadow.mapSize.height = 2048;
            scene.add(directionalLight);

            const pointLight = new THREE.PointLight(0x00ff00, 0.3, 100);
            pointLight.position.set(-5, 5, -5);
            scene.add(pointLight);

            // Ground
            const groundGeometry = new THREE.PlaneGeometry(20, 20);
            const groundMaterial = new THREE.MeshLambertMaterial({ color: 0x666666 });
            const ground = new THREE.Mesh(groundGeometry, groundMaterial);
            ground.rotation.x = -Math.PI / 2;
            ground.receiveShadow = true;
            scene.add(ground);

            // Human Model
            const humanModel = createHumanModel();
            scene.add(humanModel);

            // Camera change handler
            controls.addEventListener('change', () => {
                state.cameraX = camera.position.x;
                state.cameraY = camera.position.y;
                state.cameraZ = camera.position.z;
                updateDisplay();
            });

            controls.addEventListener('end', () => {
                sendCameraUpdate();
            });

            // Animation loop
            let time = 0;
            let isVisible = true;

            // Handle visibility change
            document.addEventListener('visibilitychange', () => {
                isVisible = !document.hidden;
            });

            function animate() {
                requestAnimationFrame(animate);

                if (!isVisible) return;

                time += 0.01;

                // Update controls
                controls.update();

                // Render scene
                renderer.render(scene, camera);
            }
            animate();

            // Resize
            function onResize() {
                const w = container.clientWidth;
                const h = container.clientHeight;
                camera.aspect = w / h;
                camera.updateProjectionMatrix();
                renderer.setSize(w, h);
            }
            window.addEventListener('resize', onResize);

            // Public API
            threeScene = {
                scene: scene,
                camera: camera,
                renderer: renderer,
                controls: controls,
                humanModel: humanModel,
                updateImage: (url) => {
                    if (url && humanModel && humanModel.children.length > 0) {
                        const frontFace = humanModel.children.find(child =>
                            child.geometry && child.geometry.type === 'BoxGeometry'
                        );
                        if (frontFace && frontFace.material && frontFace.material.length >= 5) {
                            const img = new Image();
                            if (!url.startsWith('data:')) {
                                img.crossOrigin = 'anonymous';
                            }

                            img.onload = () => {
                                const tex = new THREE.Texture(img);
                                tex.needsUpdate = true;
                                tex.encoding = THREE.sRGBEncoding;
                                frontFace.material[4].map = tex;
                                frontFace.material[4].color.set(0xffffff);
                                frontFace.material[4].needsUpdate = true;
                            };

                            img.onerror = () => {
                                frontFace.material[4].map = null;
                                frontFace.material[4].color.set(0xff6b6b);
                                frontFace.material[4].needsUpdate = true;
                            };

                            img.src = url;
                        }
                    }
                }
            };
        }

        function createHumanModel() {
            const humanModel = new THREE.Group();

            // Create materials for 6 faces
            const materials = [
                new THREE.MeshLambertMaterial({ color: 0xff6b6b }), // Front - red
                new THREE.MeshLambertMaterial({ color: 0x4ecdc4 }), // Back - cyan
                new THREE.MeshLambertMaterial({ color: 0x45b7d1 }), // Right - blue
                new THREE.MeshLambertMaterial({ color: 0x96ceb4 }), // Left - green
                new THREE.MeshLambertMaterial({ color: 0xfeca57 }), // Top - yellow
                new THREE.MeshLambertMaterial({ color: 0xff9ff3 })  // Bottom - pink
            ];

            // Create box
            const boxGeometry = new THREE.BoxGeometry(1.2, 1.2, 1.2, 1, 1, 1);
            const box = new THREE.Mesh(boxGeometry, materials);
            box.castShadow = true;
            humanModel.add(box);

            // Add face features
            // Eyes
            const eyeGeometry = new THREE.SphereGeometry(0.08, 16, 16);
            const eyeMaterial = new THREE.MeshLambertMaterial({ color: 0x000000 });

            const leftEye = new THREE.Mesh(eyeGeometry, eyeMaterial);
            leftEye.position.set(-0.2, 0.2, 0.61);
            humanModel.add(leftEye);

            const rightEye = new THREE.Mesh(eyeGeometry, eyeMaterial);
            rightEye.position.set(0.2, 0.2, 0.61);
            humanModel.add(rightEye);

            // Mouth
            const mouthGeometry = new THREE.TorusGeometry(0.15, 0.03, 8, 16, Math.PI);
            const mouthMaterial = new THREE.MeshLambertMaterial({ color: 0x000000 });
            const mouth = new THREE.Mesh(mouthGeometry, mouthMaterial);
            mouth.position.set(0, -0.1, 0.61);
            mouth.rotation.x = Math.PI / 2;
            mouth.scale.set(1, 0.5, 1);
            humanModel.add(mouth);

            // Position the model
            humanModel.position.y = 0.6;

            return humanModel;
        }

        // Message handler
        window.addEventListener('message', (event) => {
            const data = event.data;

            if (data.type === 'INIT') {
                state.cameraX = data.cameraX || -4.0;
                state.cameraY = data.cameraY || 3.5;
                state.cameraZ = data.cameraZ || 4.0;
                state.fov = data.fov || 75;
                if (threeScene) {
                    threeScene.camera.position.set(state.cameraX, state.cameraY, state.cameraZ);
                    threeScene.camera.fov = state.fov;
                    threeScene.camera.updateProjectionMatrix();
                    // Only set target on initialization, not on camera sync to preserve panning
                    if (!threeScene.controls.target.equals(new THREE.Vector3(0, 0.6, 0))) {
                        threeScene.controls.target.set(0, 0.6, 0);
                        threeScene.controls.update();
                    }
                }
                updateDisplay();
            } else if (data.type === 'SYNC_CAMERA') {
                // Only update camera position and FOV, preserve current target (panning state)
                state.cameraX = data.cameraX || -4.0;
                state.cameraY = data.cameraY || 3.5;
                state.cameraZ = data.cameraZ || 4.0;
                state.fov = data.fov || 75;
                if (threeScene) {
                    threeScene.camera.position.set(state.cameraX, state.cameraY, state.cameraZ);
                    threeScene.camera.fov = state.fov;
                    threeScene.camera.updateProjectionMatrix();
                    // Do not reset target here to preserve panning
                    threeScene.controls.update();
                }
                updateDisplay();
            } else if (data.type === 'UPDATE_IMAGE') {
                state.imageUrl = data.imageUrl;
                if (threeScene) {
                    threeScene.updateImage(data.imageUrl);
                }
            }
        });

        // Initialize
        initThreeJS();

        // Notify parent that we're ready
        window.parent.postMessage({ type: 'VIEWER_READY' }, '*');

        // Initial display update
        updateDisplay();
    </script>
</body>
</html>
`;