import * as React from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { MeshoptDecoder } from 'meshoptimizer';


type GLTFViewerProps = {};


export function GLTFViewer({}: GLTFViewerProps) {
  React.useEffect(() => {
    let disposed = false

    const scene = new THREE.Scene()
    const raycaster = new THREE.Raycaster()
    const pointer = new THREE.Vector2()

    const viewerContainer = document.getElementById("viewer-container") as HTMLElement
  
    const camera = new THREE.OrthographicCamera(-5, 5, 5, -5, 0.1, 1000)
    camera.position.set(5, 5, 5)
    camera.lookAt(0, 0, 0)
    
  
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

    const handlePointerDown = (event: PointerEvent) => {
      const bounds = viewerContainer.getBoundingClientRect()
      pointer.x = ((event.clientX - bounds.left) / bounds.width) * 2 - 1
      pointer.y = -(((event.clientY - bounds.top) / bounds.height) * 2 - 1)

      raycaster.setFromCamera(pointer, camera)

      const intersects = raycaster.intersectObjects(scene.children, true)
      const hit = intersects.find((intersection) => intersection.object !== axes)

      if (!hit) {
        return
      }

      focusOnObject(hit.object)
    }

    viewerContainer.addEventListener("pointerdown", handlePointerDown)
  
    function renderScene() {
      directionalLight.position.copy(camera.position)
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

          const maxDimension = Math.max(size.x, size.y, size.z, 1)
          camera.zoom = Math.min(1, 10 / maxDimension)
          camera.position.set(5, 5, 5)
          camera.lookAt(0, 0, 0)
          cameraControls.target.set(0, 0, 0)
          cameraControls.update()
          camera.updateProjectionMatrix()
        })
      })
    }

    loadModels()

    return () => {
      disposed = true
      window.removeEventListener("resize", resizeViewer)
      viewerContainer.removeEventListener("pointerdown", handlePointerDown)
      renderer.dispose()
      cameraControls.dispose()
      viewerContainer.removeChild(renderer.domElement)
    }
  
  }, [])

  return (
    <div style={{ width: "100%", height: "calc(100vh - 60px)" }}>
      <div
        id="viewer-container"
        style={{height:"100%"}}
      />
    </div>
  )
}
