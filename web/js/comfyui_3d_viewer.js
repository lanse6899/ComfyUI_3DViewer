import { app } from "../../../../scripts/app.js";
import { VIEWER_HTML } from "./viewer_inline.js";

/**
 * ComfyUI Extension for 3D Viewer Node
 * Provides an embedded 3D viewer widget
 */
app.registerExtension({
    name: "comfyui.3d.viewer",

    async beforeRegisterNodeDef(nodeType, nodeData, app) {
        if (nodeData.name === "ComfyUI3DViewerNode") {
            const onNodeCreated = nodeType.prototype.onNodeCreated;

            nodeType.prototype.onNodeCreated = function () {
                const r = onNodeCreated ? onNodeCreated.apply(this, arguments) : undefined;
                const node = this;

                // Create iframe for 3D viewer
                const iframe = document.createElement("iframe");
                iframe.style.width = "100%";
                iframe.style.height = "100%";
                iframe.style.border = "none";
                iframe.style.backgroundColor = "#000";
                iframe.style.borderRadius = "8px";
                iframe.style.display = "block";

                // Create blob URL from inline HTML
                const blob = new Blob([VIEWER_HTML], { type: 'text/html' });
                const blobUrl = URL.createObjectURL(blob);
                iframe.src = blobUrl;

                iframe.addEventListener('load', () => {
                    iframe._blobUrl = blobUrl;
                });

                // Add widget (use same viewer type as qwenmultiangle so iframe gets proper interaction)
                const widget = this.addDOMWidget("viewer", "CAMERA_3D_VIEW", iframe, {
                    getValue() { return ""; },
                    setValue(v) { }
                });

                widget.computeSize = function (width) {
                    const w = width || 320;
                    return [w, 400];
                };

                widget.element = iframe;
                // Ensure iframe receives pointer events and can be focused
                iframe.style.pointerEvents = 'auto';
                iframe.style.zIndex = '1';
                iframe.setAttribute('tabindex', '0');
                // Allow pointer-lock if the viewer ever uses it
                iframe.allow = 'pointer-lock;';
                // Make sure parent widget doesn't block pointer events
                try {
                    if (widget && widget.element) {
                        widget.element.style.pointerEvents = 'auto';
                        widget.element.tabIndex = 0;
                        // Focus iframe when user presses mouse down on the widget area
                        widget.element.addEventListener('mousedown', (e) => {
                            try {
                                iframe.contentWindow && iframe.contentWindow.focus && iframe.contentWindow.focus();
                            } catch (err) {
                                // ignore
                            }
                        }, { passive: true });
                    }
                } catch (err) {
                    // ignore
                }
                this._viewerIframe = iframe;
                this._viewerReady = false;

                // Message handler
                const onMessage = (event) => {
                    if (event.source !== iframe.contentWindow) return;
                    const data = event.data;

                    if (data.type === 'VIEWER_READY') {
                        this._viewerReady = true;
                        // Send pending image if any
                        if (this._pendingImageSend) {
                            this._pendingImageSend();
                            delete this._pendingImageSend;
                        }
                        // Send initial values
                        const cameraXWidget = node.widgets.find(w => w.name === "camera_x");
                        const cameraYWidget = node.widgets.find(w => w.name === "camera_y");
                        const cameraZWidget = node.widgets.find(w => w.name === "camera_z");
                        const fovWidget = node.widgets.find(w => w.name === "fov");

                        iframe.contentWindow.postMessage({
                            type: "INIT",
                            cameraX: cameraXWidget?.value || -4.0,
                            cameraY: cameraYWidget?.value || 3.5,
                            cameraZ: cameraZWidget?.value || 4.0,
                            fov: fovWidget?.value || 75
                        }, "*");
                    } else if (data.type === 'CAMERA_UPDATE') {
                        // Update node widgets from 3D view
                        const cameraXWidget = node.widgets.find(w => w.name === "camera_x");
                        const cameraYWidget = node.widgets.find(w => w.name === "camera_y");
                        const cameraZWidget = node.widgets.find(w => w.name === "camera_z");
                        const fovWidget = node.widgets.find(w => w.name === "fov");

                        if (cameraXWidget) cameraXWidget.value = data.cameraX;
                        if (cameraYWidget) cameraYWidget.value = data.cameraY;
                        if (cameraZWidget) cameraZWidget.value = data.cameraZ;
                        if (fovWidget) fovWidget.value = data.fov;

                        // Mark graph as changed
                        app.graph.setDirtyCanvas(true, true);
                    }
                };
                window.addEventListener('message', onMessage);

                // Resize handling
                const notifyIframeResize = () => {
                    if (iframe.contentWindow) {
                        const rect = iframe.getBoundingClientRect();
                        iframe.contentWindow.postMessage({
                            type: 'RESIZE',
                            width: rect.width,
                            height: rect.height
                        }, '*');
                    }
                };

                // ResizeObserver for responsive updates
                let resizeTimeout = null;
                let lastSize = { width: 0, height: 0 };
                const resizeObserver = new ResizeObserver((entries) => {
                    const entry = entries[0];
                    const newWidth = entry.contentRect.width;
                    const newHeight = entry.contentRect.height;

                    if (Math.abs(newWidth - lastSize.width) < 1 && Math.abs(newHeight - lastSize.height) < 1) {
                        return;
                    }
                    lastSize = { width: newWidth, height: newHeight };

                    if (resizeTimeout) {
                        clearTimeout(resizeTimeout);
                    }
                    resizeTimeout = setTimeout(() => {
                        notifyIframeResize();
                    }, 50);
                });
                resizeObserver.observe(iframe);

                // Sync slider widgets to 3D view
                const syncTo3DView = () => {
                    if (!this._viewerReady || !iframe.contentWindow) return;

                    const cameraXWidget = node.widgets.find(w => w.name === "camera_x");
                    const cameraYWidget = node.widgets.find(w => w.name === "camera_y");
                    const cameraZWidget = node.widgets.find(w => w.name === "camera_z");
                    const fovWidget = node.widgets.find(w => w.name === "fov");

                    iframe.contentWindow.postMessage({
                        type: "SYNC_CAMERA",
                        cameraX: cameraXWidget?.value || -4.0,
                        cameraY: cameraYWidget?.value || 3.5,
                        cameraZ: cameraZWidget?.value || 4.0,
                        fov: fovWidget?.value || 75
                    }, "*");
                };

                // Override widget callback to sync
                const origCallback = this.onWidgetChanged;
                this.onWidgetChanged = function (name, value, old_value, widget) {
                    if (origCallback) {
                        origCallback.apply(this, arguments);
                    }
                    if (name === "camera_x" || name === "camera_y" || name === "camera_z" || name === "fov") {
                        syncTo3DView();
                    }
                };

                // Handle execution - receive image from backend
                const onExecuted = this.onExecuted;
                this.onExecuted = function (message) {
                    onExecuted?.apply(this, arguments);

                    // Support both array-style image_base64 (["data:..."]) and single-string
                    const imgBase64Arr = message?.image_base64;
                    let imageData = null;
                    if (imgBase64Arr) {
                        if (Array.isArray(imgBase64Arr) && imgBase64Arr.length > 0) {
                            imageData = imgBase64Arr[0];
                        } else if (typeof imgBase64Arr === 'string' && imgBase64Arr.length > 0) {
                            imageData = imgBase64Arr;
                        }
                    }

                    if (imageData) {
                        const sendImage = () => {
                            if (iframe.contentWindow) {
                                iframe.contentWindow.postMessage({
                                    type: "UPDATE_IMAGE",
                                    imageUrl: imageData
                                }, "*");
                            }
                        };

                        if (this._viewerReady) {
                            sendImage();
                        } else {
                            this._pendingImageSend = sendImage;
                        }
                    }
                };

                // Clean up on node removal
                const originalOnRemoved = this.onRemoved;
                this.onRemoved = function () {
                    resizeObserver.disconnect();
                    window.removeEventListener('message', onMessage);
                    if (resizeTimeout) {
                        clearTimeout(resizeTimeout);
                    }
                    delete this._pendingImageSend;
                    if (iframe._blobUrl) {
                        URL.revokeObjectURL(iframe._blobUrl);
                    }
                    if (originalOnRemoved) {
                        originalOnRemoved.apply(this, arguments);
                    }
                };

                // Set initial node size
                this.setSize([350, 550]);

                return r;
            };
        }
    }
});
