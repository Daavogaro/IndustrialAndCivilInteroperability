import * as React from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { MeshoptDecoder } from 'meshoptimizer';


type GLTFViewerProps = {
  uri: string | null;
};


export function GLTFViewer({ uri }: GLTFViewerProps) {
  const [loadedFiles, setLoadedFiles] = React.useState<string[]>([])
  const [visibleFiles, setVisibleFiles] = React.useState<Record<string, boolean>>({})
  const sceneRef = React.useRef<THREE.Scene | null>(null)
  const loadedObjectsRef = React.useRef<Record<string, THREE.Object3D>>({})

  const toggleModelVisibility = (url: string, isVisible: boolean) => {
    const object = loadedObjectsRef.current[url]
    if (!object) {
      return
    }

    object.visible = isVisible
    setVisibleFiles((prev) => ({ ...prev, [url]: isVisible }))
  }

  React.useEffect(() => {
    let disposed = false

    const scene = new THREE.Scene()
    sceneRef.current = scene
    const raycaster = new THREE.Raycaster()
    const pointer = new THREE.Vector2()
    let hoveredMesh: THREE.Mesh | null = null

    const viewerContainer = document.getElementById("viewer-container") as HTMLElement
  
    const camera = new THREE.OrthographicCamera(-5, 5, 5, -5, 0.1, 1000)
    camera.position.set(5, 5, 5)
    camera.lookAt(0, 0, 0)

    const initialCameraPosition = new THREE.Vector3(5, 5, 5)
    const initialCameraTarget = new THREE.Vector3(0, 0, 0)
    let initialCameraZoom = camera.zoom
    
  
    const renderer = new THREE.WebGLRenderer({alpha: true, antialias: true})
    renderer.outputColorSpace = THREE.SRGBColorSpace
    renderer.shadowMap.enabled = false
    viewerContainer.append(renderer.domElement)
  
    function resizeViewer() {
      const containerDimensions = viewerContainer.getBoundingClientRect()
      renderer.setSize(containerDimensions.width, containerDimensions.height)
      const aspectRatio = containerDimensions.width / containerDimensions.height
      const frustumSize = 10

      camera.left = (-frustumSize * aspectRatio) / 2
      camera.right = (frustumSize * aspectRatio) / 2
      camera.top = frustumSize / 2
      camera.bottom = -frustumSize / 2
      camera.updateProjectionMatrix()
    }
  
    window.addEventListener("resize", resizeViewer)
  
    resizeViewer()
  
    const ambientLight = new THREE.AmbientLight(0xffffff, 2.2)
    const hemisphereLight = new THREE.HemisphereLight(0xffffff, 0xf2f6ff, 1.3)
    hemisphereLight.position.set(0, 10, 0)

    const directionalLight = new THREE.DirectionalLight(0xffffff, 1.2)
    directionalLight.position.set(5, 8, 5)
    
  
    scene.add(ambientLight, hemisphereLight, directionalLight)
  
    const cameraControls = new OrbitControls(camera, viewerContainer)
    cameraControls.zoomSpeed = 2.5
    cameraControls.target.set(0, 0, 0)
    cameraControls.update()

    const resetToInitialView = () => {
      camera.zoom = initialCameraZoom
      camera.position.copy(initialCameraPosition)
      cameraControls.target.copy(initialCameraTarget)
      camera.lookAt(initialCameraTarget)
      camera.updateProjectionMatrix()
      cameraControls.update()
    }

    const focusOnObject = (object: THREE.Object3D) => {
      const box = new THREE.Box3().setFromObject(object)
      const center = box.getCenter(new THREE.Vector3())
      const size = box.getSize(new THREE.Vector3())
      const maxDimension = Math.max(size.x, size.y, size.z, 1)

      cameraControls.target.copy(center)
      camera.zoom = Math.min(2, 10 / maxDimension)
      camera.position.set(center.x + 5, center.y + 5, center.z + 5)
      camera.lookAt(center)
      camera.updateProjectionMatrix()
      cameraControls.update()
    }

    const getHitMesh = (event: PointerEvent): THREE.Mesh | null => {
      const bounds = viewerContainer.getBoundingClientRect()
      pointer.x = ((event.clientX - bounds.left) / bounds.width) * 2 - 1
      pointer.y = -(((event.clientY - bounds.top) / bounds.height) * 2 - 1)

      raycaster.setFromCamera(pointer, camera)

      const intersects = raycaster.intersectObjects(scene.children, true)
      const hit = intersects.find((intersection) => intersection.object instanceof THREE.Mesh)

      return (hit?.object as THREE.Mesh) ?? null
    }

    const buildHighlightMaterial = (material: THREE.Material): THREE.Material => {
      const highlighted = material.clone()
      const shaded = highlighted as THREE.MeshStandardMaterial

      if ("emissive" in shaded) {
        shaded.emissive = new THREE.Color("#3a8bff")
        shaded.emissiveIntensity = 0.35
      }

      if ("color" in shaded) {
        shaded.color = shaded.color.clone().multiplyScalar(1.08)
      }

      return highlighted
    }

    const setHoverHighlight = (mesh: THREE.Mesh | null) => {
      if (hoveredMesh === mesh) {
        return
      }

      if (hoveredMesh) {
        const original = hoveredMesh.userData.originalMaterial as THREE.Material | THREE.Material[] | undefined
        if (original) {
          hoveredMesh.material = original
          delete hoveredMesh.userData.originalMaterial
        }
      }

      hoveredMesh = mesh

      if (!hoveredMesh) {
        return
      }

      hoveredMesh.userData.originalMaterial = hoveredMesh.material
      hoveredMesh.material = Array.isArray(hoveredMesh.material)
        ? hoveredMesh.material.map((material) => buildHighlightMaterial(material))
        : buildHighlightMaterial(hoveredMesh.material)
    }

    const handlePointerMove = (event: PointerEvent) => {
      const hitMesh = getHitMesh(event)
      setHoverHighlight(hitMesh)
    }

    const handlePointerLeave = () => {
      setHoverHighlight(null)
    }

    const handlePointerDown = (event: PointerEvent) => {
      const hitMesh = getHitMesh(event)

      if (!hitMesh) {
        return
      }

      if (event.button === 0) {
        console.log("Clicked object:", hitMesh || "(unnamed object)")
      }

      if (event.button === 2) {
        event.preventDefault()
        focusOnObject(hitMesh)
      }
    }

    const handleContextMenu = (event: MouseEvent) => {
      event.preventDefault()
    }

    viewerContainer.addEventListener("pointermove", handlePointerMove)
    viewerContainer.addEventListener("pointerleave", handlePointerLeave)
    viewerContainer.addEventListener("pointerdown", handlePointerDown)
    viewerContainer.addEventListener("contextmenu", handleContextMenu)

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        resetToInitialView()
      }
    }

    window.addEventListener("keydown", handleKeyDown)
  
    function renderScene() {
      renderer.render(scene, camera)
      requestAnimationFrame(renderScene)
    }
  
    renderScene()
  
    const axes = new THREE.AxesHelper()
    const grid = new THREE.GridHelper()
    grid.material.transparent = true
    grid.material.opacity = 0.4
    grid.material.color = new THREE.Color("#808080")
  
    scene.add(axes)
  
  
    
    const gltfLoader = new GLTFLoader()
    gltfLoader.setMeshoptDecoder(MeshoptDecoder);
    const loadModels = async () => {
      const res = await fetch("/api/gltf-upload", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ files: [] }),
      })

      const data: { files: string[] } = await res.json()

      data.files.forEach((url: string) => {
        gltfLoader.load(url, (gltf) => {
          if (disposed) {
            return
          }

          const box = new THREE.Box3().setFromObject(gltf.scene)
          const size = box.getSize(new THREE.Vector3())

          scene.add(gltf.scene)
          loadedObjectsRef.current[url] = gltf.scene
          setLoadedFiles((prev) => (prev.includes(url) ? prev : [...prev, url]))
          setVisibleFiles((prev) => ({ ...prev, [url]: true }))

          const maxDimension = Math.max(size.x, size.y, size.z, 1)
          camera.zoom = Math.min(1, 10 / maxDimension)
          camera.position.set(5, 5, 5)
          camera.lookAt(0, 0, 0)
          cameraControls.target.set(0, 0, 0)
          cameraControls.update()
          camera.updateProjectionMatrix()

          initialCameraPosition.copy(camera.position)
          initialCameraTarget.copy(cameraControls.target)
          initialCameraZoom = camera.zoom
        })
      })
    }

    loadModels()

    return () => {
      disposed = true
      setLoadedFiles([])
      setVisibleFiles({})
      loadedObjectsRef.current = {}
      sceneRef.current = null
      window.removeEventListener("resize", resizeViewer)
      window.removeEventListener("keydown", handleKeyDown)
      viewerContainer.removeEventListener("pointermove", handlePointerMove)
      viewerContainer.removeEventListener("pointerleave", handlePointerLeave)
      viewerContainer.removeEventListener("pointerdown", handlePointerDown)
      viewerContainer.removeEventListener("contextmenu", handleContextMenu)
      setHoverHighlight(null)
      renderer.dispose()
      cameraControls.dispose()
      viewerContainer.removeChild(renderer.domElement)
    }
  
  }, [])

  return (
    <div style={{ width: "100%", height: "50vh", position: "relative" }}>
      <div
        id="viewer-container"
        style={{height:"100%"}}
      />
      <div
        style={{
          position: "absolute",
          top: 12,
          right: 12,
          width: 280,
          maxHeight: "70%",
          overflowY: "auto",
          background: "var(--background-200)",
          border: "1px solid #d6d6d6",
          borderRadius: 8,
          padding: 10,
          boxShadow: "0 6px 24px rgba(0,0,0,0.12)",
          zIndex: 10,
        }}
      >
        <div style={{ fontWeight: 600, marginBottom: 8 }}>Loaded GLB</div>
        {loadedFiles.length === 0 && (
          <div style={{ fontSize: 13, color: "#666" }}>No files loaded.</div>
        )}
        {loadedFiles.map((url) => (
          <div
            key={url}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              marginBottom: 6,
            }}
          >
            <input
              type="checkbox"
              checked={visibleFiles[url] ?? true}
              onChange={(event) => toggleModelVisibility(url, event.target.checked)}
            />
            <span
              style={{
                fontSize: 12,
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
                flex: 1,
              }}
              title={url}
            >
              {url.split("/").pop() || url}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}
