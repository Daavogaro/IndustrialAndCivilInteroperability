import * as React from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { RoomEnvironment } from "three/examples/jsm/environments/RoomEnvironment.js";
import { MeshoptDecoder } from "meshoptimizer";
import { useProject } from "../../context/ProjectContext";

type ProductGLTFViewerProps = {
  productLabel: string;
  hoveredUri?: string | null;
  rootUri?: string | null;
};

const normalizeName = (value: unknown): string => {
  if (typeof value !== "string") return "";
  return value
    .replace(/_/g, "")
    .replace(/\./g, "")
    .replace(/\s+/g, "")
    .replace(/-/g, "")
    .toLowerCase();
};

export function ProductGLTFViewer({
  productLabel,
  hoveredUri = null,
  rootUri = null,
}: ProductGLTFViewerProps) {
  const { activeProject } = useProject();
  const projectId = activeProject?.id ?? null;

  // Keep a ref so the async GLTF-load callback can read the latest rootUri
  // without being in the main useEffect's dependency array.
  const rootUriRef = React.useRef<string | null>(rootUri);
  rootUriRef.current = rootUri;

  const [loadedFiles, setLoadedFiles] = React.useState<string[]>([]);
  const sceneRef = React.useRef<THREE.Scene | null>(null);
  const loadedObjectsRef = React.useRef<Record<string, THREE.Object3D>>({});
  const highlightedMeshesRef = React.useRef<
    Record<string, THREE.Material | THREE.Material[]>
  >({});
  const dimmedMeshesRef = React.useRef<
    Record<string, THREE.Material | THREE.Material[]>
  >({});

  const clearUriHighlight = React.useCallback(() => {
    Object.entries(highlightedMeshesRef.current).forEach(([uuid, original]) => {
      const mesh = sceneRef.current?.getObjectByProperty(
        "uuid",
        uuid,
      ) as THREE.Mesh | undefined;
      if (mesh) mesh.material = original;
    });
    Object.entries(dimmedMeshesRef.current).forEach(([uuid, original]) => {
      const mesh = sceneRef.current?.getObjectByProperty(
        "uuid",
        uuid,
      ) as THREE.Mesh | undefined;
      if (mesh) mesh.material = original;
    });
    highlightedMeshesRef.current = {};
    dimmedMeshesRef.current = {};
  }, []);

  const buildUriHighlightMaterial = React.useCallback(
    (material: THREE.Material): THREE.Material => {
      const highlighted = material.clone();
      const shaded = highlighted as THREE.MeshStandardMaterial;
      if ("emissive" in shaded) {
        shaded.emissive = new THREE.Color("#ffd54f");
        shaded.emissiveIntensity = 0.55;
      }
      if ("color" in shaded) shaded.color = shaded.color.clone().multiplyScalar(1.1);
      return highlighted;
    },
    [],
  );

  const buildDimmedMaterial = React.useCallback(
    (material: THREE.Material): THREE.Material => {
      const dimmed = material.clone();
      if ("opacity" in dimmed) {
        dimmed.transparent = true;
        (dimmed as THREE.MeshStandardMaterial).opacity = 0.12;
        dimmed.depthWrite = false;
      }
      return dimmed;
    },
    [],
  );

  const applyUriHighlight = React.useCallback(
    (inputUri: string | null) => {
      clearUriHighlight();
      if (!inputUri) return;

      const uriFragment = inputUri.includes("#")
        ? inputUri.split("#")[1]
        : inputUri;
      const targetName =
        typeof uriFragment === "string" ? uriFragment.replace(/_/g, " ") : "";
      if (!targetName) return;

      const normalizedTargetName = normalizeName(targetName);
      if (!normalizedTargetName) return;

      const hasNamedAncestor = (object: THREE.Object3D, name: string) => {
        let parent: THREE.Object3D | null = object.parent;
        const normalizedName = normalizeName(name);
        if (!normalizedName) return false;
        while (parent) {
          if (
            normalizeName(parent.userData?.name) &&
            normalizeName(parent.userData?.name) === normalizedName
          )
            return true;
          parent = parent.parent;
        }
        return false;
      };

      const matchedUuids = new Set<string>();
      Object.values(loadedObjectsRef.current).forEach((root) => {
        root.traverse((obj) => {
          if (!(obj instanceof THREE.Mesh)) return;
          const own = obj.userData?.name;
          const isMatch =
            normalizeName(own) === normalizedTargetName ||
            hasNamedAncestor(obj, targetName);
          if (isMatch) matchedUuids.add(obj.uuid);
        });
      });

      if (matchedUuids.size === 0) return;

      Object.values(loadedObjectsRef.current).forEach((root) => {
        root.traverse((obj) => {
          if (!(obj instanceof THREE.Mesh)) return;
          if (matchedUuids.has(obj.uuid)) {
            highlightedMeshesRef.current[obj.uuid] = obj.material;
            obj.material = Array.isArray(obj.material)
              ? obj.material.map(buildUriHighlightMaterial)
              : buildUriHighlightMaterial(obj.material);
          } else {
            dimmedMeshesRef.current[obj.uuid] = obj.material;
            obj.material = Array.isArray(obj.material)
              ? obj.material.map(buildDimmedMaterial)
              : buildDimmedMaterial(obj.material);
          }
        });
      });
    },
    [buildDimmedMaterial, buildUriHighlightMaterial, clearUriHighlight],
  );

  React.useEffect(() => {
    let disposed = false;

    const scene = new THREE.Scene();
    sceneRef.current = scene;
    const raycaster = new THREE.Raycaster();
    const pointer = new THREE.Vector2();
    let hoveredMesh: THREE.Mesh | null = null;

    const viewerContainer = document.getElementById(
      "product-viewer-container",
    ) as HTMLElement;

    const camera = new THREE.OrthographicCamera(-5, 5, 5, -5, 0.1, 1000);
    camera.position.set(5, 5, 5);
    camera.lookAt(0, 0, 0);

    const initialCameraPosition = new THREE.Vector3(5, 5, 5);
    const initialCameraTarget = new THREE.Vector3(0, 0, 0);
    let initialCameraZoom = camera.zoom;

    const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 0.85;
    renderer.shadowMap.enabled = false;
    viewerContainer.append(renderer.domElement);

    const pmremGenerator = new THREE.PMREMGenerator(renderer);
    scene.environment = pmremGenerator.fromScene(new RoomEnvironment()).texture;
    scene.environmentIntensity = 0.35;
    pmremGenerator.dispose();

    function resizeViewer() {
      const dims = viewerContainer.getBoundingClientRect();
      if (dims.width === 0 || dims.height === 0) return;
      renderer.setSize(dims.width, dims.height);
      const aspect = dims.width / dims.height;
      const frustum = 10;
      camera.left = (-frustum * aspect) / 2;
      camera.right = (frustum * aspect) / 2;
      camera.top = frustum / 2;
      camera.bottom = -frustum / 2;
      camera.updateProjectionMatrix();
    }

    window.addEventListener("resize", resizeViewer);
    resizeViewer();

    const ambientLight = new THREE.AmbientLight(0xffffff, 1.2);
    const hemisphereLight = new THREE.HemisphereLight(0xffffff, 0xf2f6ff, 0.5);
    hemisphereLight.position.set(0, 10, 0);
    const directionalLight = new THREE.DirectionalLight(0xffffff, 0.5);
    directionalLight.position.set(5, 8, 5);
    scene.add(ambientLight, hemisphereLight, directionalLight);

    const cameraControls = new OrbitControls(camera, viewerContainer);
    cameraControls.zoomSpeed = 2.5;
    cameraControls.target.set(0, 0, 0);
    cameraControls.update();

    const resetToInitialView = () => {
      camera.zoom = initialCameraZoom;
      camera.position.copy(initialCameraPosition);
      cameraControls.target.copy(initialCameraTarget);
      camera.lookAt(initialCameraTarget);
      camera.updateProjectionMatrix();
      cameraControls.update();
    };

    const focusOnObject = (object: THREE.Object3D) => {
      const box = new THREE.Box3().setFromObject(object);
      const center = box.getCenter(new THREE.Vector3());
      const size = box.getSize(new THREE.Vector3());
      const maxDimension = Math.max(size.x, size.y, size.z, 1);
      cameraControls.target.copy(center);
      camera.zoom = Math.min(2, 10 / maxDimension);
      camera.position.set(center.x + 5, center.y + 5, center.z + 5);
      camera.lookAt(center);
      camera.updateProjectionMatrix();
      cameraControls.update();
    };

    const isolateProduct = (label: string) => {
      // Use the rootUri fragment (e.g. "PSI_SLS2_Girder_Superbend.2") when available
      // so the correct instance is found in the project-specific GLB file.
      const uri = rootUriRef.current;
      const objectName = uri
        ? (uri.includes("#") ? uri.split("#")[1] : uri)
        : label + ".1";
      const target = normalizeName(objectName);
      if (!target) return;

      let productRoot: THREE.Object3D | null = null;
      scene.traverse((obj) => {
        if (!productRoot && normalizeName(obj.userData?.name) === target) {
          productRoot = obj;
        }
      });

      if (!productRoot) return;

      // Collect all nodes in the product subtree
      const productSet = new Set<THREE.Object3D>();
      (productRoot as THREE.Object3D).traverse((obj) => productSet.add(obj));

      // Collect all ancestors up to the scene root
      const ancestorSet = new Set<THREE.Object3D>();
      let current: THREE.Object3D | null = (productRoot as THREE.Object3D).parent;
      while (current) {
        ancestorSet.add(current);
        current = current.parent;
      }

      // Hide everything outside the product subtree and its ancestors
      scene.traverse((obj) => {
        if (!productSet.has(obj) && !ancestorSet.has(obj)) {
          obj.visible = false;
        }
      });

      // Centre and frame the camera on the product
      focusOnObject(productRoot as THREE.Object3D);

      // Update initial pose so Escape-to-reset returns to this product view
      initialCameraPosition.copy(camera.position);
      initialCameraTarget.copy(cameraControls.target);
      initialCameraZoom = camera.zoom;
    };

    const getHitMesh = (event: PointerEvent): THREE.Mesh | null => {
      const bounds = viewerContainer.getBoundingClientRect();
      pointer.x = ((event.clientX - bounds.left) / bounds.width) * 2 - 1;
      pointer.y = -(((event.clientY - bounds.top) / bounds.height) * 2 - 1);
      raycaster.setFromCamera(pointer, camera);
      const intersects = raycaster.intersectObjects(scene.children, true);
      const hit = intersects.find((i) => i.object instanceof THREE.Mesh);
      return (hit?.object as THREE.Mesh) ?? null;
    };

    const buildHighlightMaterial = (material: THREE.Material): THREE.Material => {
      const highlighted = material.clone();
      const shaded = highlighted as THREE.MeshStandardMaterial;
      if ("emissive" in shaded) {
        shaded.emissive = new THREE.Color("#3a8bff");
        shaded.emissiveIntensity = 0.35;
      }
      if ("color" in shaded)
        shaded.color = shaded.color.clone().multiplyScalar(1.08);
      return highlighted;
    };

    const setHoverHighlight = (mesh: THREE.Mesh | null) => {
      if (hoveredMesh === mesh) return;
      if (hoveredMesh) {
        const original = hoveredMesh.userData
          .originalMaterial as THREE.Material | THREE.Material[] | undefined;
        if (original) {
          hoveredMesh.material = original;
          delete hoveredMesh.userData.originalMaterial;
        }
      }
      hoveredMesh = mesh;
      if (!hoveredMesh) return;
      hoveredMesh.userData.originalMaterial = hoveredMesh.material;
      hoveredMesh.material = Array.isArray(hoveredMesh.material)
        ? hoveredMesh.material.map(buildHighlightMaterial)
        : buildHighlightMaterial(hoveredMesh.material);
    };

    const handlePointerMove = (e: PointerEvent) => setHoverHighlight(getHitMesh(e));
    const handlePointerLeave = () => setHoverHighlight(null);
    const handlePointerDown = (e: PointerEvent) => {
      const hit = getHitMesh(e);
      if (!hit) return;
      if (e.button === 2) {
        e.preventDefault();
        focusOnObject(hit);
      }
    };
    const handleContextMenu = (e: MouseEvent) => e.preventDefault();
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") resetToInitialView();
    };

    viewerContainer.addEventListener("pointermove", handlePointerMove);
    viewerContainer.addEventListener("pointerleave", handlePointerLeave);
    viewerContainer.addEventListener("pointerdown", handlePointerDown);
    viewerContainer.addEventListener("contextmenu", handleContextMenu);
    window.addEventListener("keydown", handleKeyDown);

    let animFrameId: number;
    function renderScene() {
      animFrameId = requestAnimationFrame(renderScene);
      renderer.render(scene, camera);
    }
    renderScene();

    scene.add(new THREE.AxesHelper());

    const gltfLoader = new GLTFLoader();
    gltfLoader.setMeshoptDecoder(MeshoptDecoder);

    const loadModels = async () => {
      const res = await fetch("/api/gltf-upload", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ files: [], projectId }),
      });
      const data: { files: string[] } = await res.json();

      data.files.forEach((url: string) => {
        gltfLoader.load(url, (gltf) => {
          if (disposed) return;

          scene.add(gltf.scene);
          loadedObjectsRef.current[url] = gltf.scene;
          setLoadedFiles((prev) => (prev.includes(url) ? prev : [...prev, url]));

          isolateProduct(productLabel);
        });
      });
    };

    loadModels();

    return () => {
      disposed = true;
      cancelAnimationFrame(animFrameId);

      // Dispose all GPU-side objects (geometries, materials, textures)
      scene.traverse((obj) => {
        if (obj instanceof THREE.Mesh) {
          obj.geometry?.dispose();
          const mats = Array.isArray(obj.material) ? obj.material : [obj.material];
          mats.forEach((m: THREE.Material) => {
            Object.values(m).forEach((val) => {
              if (val instanceof THREE.Texture) val.dispose();
            });
            m.dispose();
          });
        }
      });

      // Dispose cloned highlight/dim materials still held in refs
      const disposeMatMap = (map: Record<string, THREE.Material | THREE.Material[]>) => {
        Object.values(map).forEach((m) => {
          const arr = Array.isArray(m) ? m : [m];
          arr.forEach((mat) => mat.dispose());
        });
      };
      disposeMatMap(highlightedMeshesRef.current);
      disposeMatMap(dimmedMeshesRef.current);
      highlightedMeshesRef.current = {};
      dimmedMeshesRef.current = {};

      if (scene.environment) {
        scene.environment.dispose();
        scene.environment = null;
      }
      scene.clear();

      setLoadedFiles([]);
      loadedObjectsRef.current = {};
      sceneRef.current = null;
      window.removeEventListener("resize", resizeViewer);
      window.removeEventListener("keydown", handleKeyDown);
      viewerContainer.removeEventListener("pointermove", handlePointerMove);
      viewerContainer.removeEventListener("pointerleave", handlePointerLeave);
      viewerContainer.removeEventListener("pointerdown", handlePointerDown);
      viewerContainer.removeEventListener("contextmenu", handleContextMenu);
      setHoverHighlight(null);
      renderer.dispose();
      cameraControls.dispose();
      if (viewerContainer.contains(renderer.domElement)) {
        viewerContainer.removeChild(renderer.domElement);
      }
    };
  }, [clearUriHighlight, productLabel, projectId]);

  React.useEffect(() => {
    applyUriHighlight(hoveredUri ?? null);
  }, [hoveredUri, loadedFiles, applyUriHighlight]);

  return (
    <div style={{ width: "100%", height: "100%", position: "relative" }}>
      <div id="product-viewer-container" style={{ height: "100%" }} />
    </div>
  );
}
