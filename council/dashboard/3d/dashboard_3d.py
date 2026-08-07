"""
CouncilKey-Os 3D Dashboard with Three.js - 3D Visualization of Knowledge Graph + Agents + Particle Effects

"""

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

HTML_3D = """
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>CouncilKey-Os 3D Dashboard</title>
<script src="https://cdn.tailwindcss.com"></script>
<script src="https://unpkg.com/three@0.160.0/build/three.min.js"></script>
<script src="https://unpkg.com/three@0.160.0/examples/js/controls/OrbitControls.js"></script>
<style>
body { margin: 0; overflow: hidden; background: #0a0a0f; }
#canvas { width: 100%; height: 100vh; display: block; }
.ui-overlay { position: absolute; top: 20px; left: 20px; right: 20px; pointer-events: none; }
.ui-card { pointer-events: auto; backdrop-filter: blur(20px); background: rgba(26, 29, 41, 0.8); border: 1px solid rgba(99, 102, 241, 0.2); border-radius: 16px; padding: 20px; }
</style>
</head>
<body>
<canvas id="canvas"></canvas>

<div class="ui-overlay">
  <div class="ui-card max-w-md">
    <h1 class="text-2xl font-bold text-white">🗝️ CouncilKey-Os 3D Dashboard</h1>
    <p class="text-sm opacity-60 mt-2">Three.js - 3D knowledge graph, agent avatars and particle effects</p>
    <div class="mt-4 flex gap-2">
      <span class="px-3 py-1 rounded-full bg-green-900/30 text-green-300 border border-green-700/30 text-xs">3 Agents Live</span>
      <span class="px-3 py-1 rounded-full bg-blue-900/30 text-blue-300 border border-blue-700/30 text-xs">200 Nodes Knowledge Graph</span>
      <span class="px-3 py-1 rounded-full bg-purple-900/30 text-purple-300 border border-purple-700/30 text-xs">5GB Smart Initial</span>
    </div>
    <div class="mt-4">
      <p class="text-xs opacity-50">Use mouse: Drag to orbit, Scroll to zoom, Right-drag to pan</p>
      <p class="text-xs opacity-50 mt-1">Agents: 🧙 Hermes Sage (Memory), 🦞 OpenClaw Executor (Action), 🔧 OpenCode Builder (Code)</p>
    </div>
  </div>
</div>

<script>
// Three.js 3D Knowledge Graph with 200 nodes + 3 Agents as 3D avatars + particle effects
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x0a0a0f);

const camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
camera.position.set(0, 0, 50);

const renderer = new THREE.WebGLRenderer({ canvas: document.getElementById('canvas'), antialias: true, alpha: true });
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.setPixelRatio(window.devicePixelRatio);

// OrbitControls for mouse drag orbit, scroll zoom, right-drag pan
const controls = new THREE.OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.dampingFactor = 0.05;

// Lights
const ambientLight = new THREE.AmbientLight(0x6366f1, 0.5);
scene.add(ambientLight);
const directionalLight = new THREE.DirectionalLight(0xffffff, 0.8);
directionalLight.position.set(10, 10, 5);
scene.add(directionalLight);
const pointLight = new THREE.PointLight(0x6366f1, 1, 100);
pointLight.position.set(0, 0, 0);
scene.add(pointLight);

// Knowledge Graph with 200 nodes + 150 edges - 3D visualization
const nodes = [];
const nodeGeometry = new THREE.SphereGeometry(0.5, 16, 16);

// Create 200 nodes with random positions, colors based on type
for (let i = 0; i < 200; i++) {
  let color;
  let type = i % 3;
  if (type === 0) color = 0x10b981; // Hermes - green - memory
  else if (type === 1) color = 0x3b82f6; // OpenClaw - blue - action
  else color = 0x8b5cf6; // OpenCode - purple - builder

  const material = new THREE.MeshPhongMaterial({ color: color, emissive: color, emissiveIntensity: 0.2, shininess: 100 });
  const sphere = new THREE.Mesh(nodeGeometry, material);
  sphere.position.set(
    (Math.random() - 0.5) * 80,
    (Math.random() - 0.5) * 80,
    (Math.random() - 0.5) * 80
  );
  sphere.userData = { type: type, id: i };
  scene.add(sphere);
  nodes.push(sphere);
}

// Create 150 edges - lines between nodes
const edges = [];
for (let i = 0; i < 150; i++) {
  const from = nodes[Math.floor(Math.random() * nodes.length)];
  const to = nodes[Math.floor(Math.random() * nodes.length)];
  if (from === to) continue;
  
  const points = [from.position, to.position];
  const geometry = new THREE.BufferGeometry().setFromPoints(points);
  const material = new THREE.LineBasicMaterial({ color: 0x6366f1, opacity: 0.2, transparent: true });
  const line = new THREE.Line(geometry, material);
  scene.add(line);
  edges.push({ line, from, to });
}

// 3 Agents as 3D avatars - Hermes wizard, OpenClaw lobster, OpenCode builder - larger spheres with different colors and emissive
const agents = [
  { name: "Hermes Sage", color: 0x10b981, pos: new THREE.Vector3(-15, 10, 0), emoji: "🧙" },
  { name: "OpenClaw Executor", color: 0x3b82f6, pos: new THREE.Vector3(0, 10, 0), emoji: "🦞" },
  { name: "OpenCode Builder", color: 0x8b5cf6, pos: new THREE.Vector3(15, 10, 0), emoji: "🔧" }
];

agents.forEach(agent => {
  const geometry = new THREE.SphereGeometry(2, 32, 32);
  const material = new THREE.MeshPhongMaterial({ color: agent.color, emissive: agent.color, emissiveIntensity: 0.5, shininess: 200 });
  const sphere = new THREE.Mesh(geometry, material);
  sphere.position.copy(agent.pos);
  sphere.userData = { name: agent.name, isAgent: true };
  scene.add(sphere);
  
  // Add glow
  const glowGeometry = new THREE.SphereGeometry(3, 32, 32);
  const glowMaterial = new THREE.MeshBasicMaterial({ color: agent.color, transparent: true, opacity: 0.2 });
  const glow = new THREE.Mesh(glowGeometry, glowMaterial);
  glow.position.copy(agent.pos);
  scene.add(glow);
});

// Particle effects - 500 particles floating
const particleGeometry = new THREE.BufferGeometry();
const particleCount = 500;
const positions = new Float32Array(particleCount * 3);
for (let i = 0; i < particleCount * 3; i++) {
  positions[i] = (Math.random() - 0.5) * 100;
}
particleGeometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
const particleMaterial = new THREE.PointsMaterial({ color: 0x6366f1, size: 0.3, transparent: true, opacity: 0.6 });
const particles = new THREE.Points(particleGeometry, particleMaterial);
scene.add(particles);

// Animation loop with floating orbs + particle rotation + knowledge graph rotation
function animate() {
  requestAnimationFrame(animate);
  
  // Rotate knowledge graph slowly
  nodes.forEach((node, i) => {
    node.rotation.y += 0.01;
    // Float animation
    node.position.y += Math.sin(Date.now() * 0.001 + i) * 0.01;
  });
  
  // Update edges positions
  edges.forEach(edge => {
    const positions = edge.line.geometry.attributes.position;
    positions.setXYZ(0, edge.from.position.x, edge.from.position.y, edge.from.position.z);
    positions.setXYZ(1, edge.to.position.x, edge.to.position.y, edge.to.position.z);
    positions.needsUpdate = true;
  });
  
  // Rotate particles
  particles.rotation.y += 0.0005;
  particles.rotation.x += 0.0002;
  
  controls.update();
  renderer.render(scene, camera);
}

animate();

// Resize handler
window.addEventListener('resize', () => {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
});

// Add interactivity: click on node to show info
renderer.domElement.addEventListener('click', (event) => {
  // Interactive node selection can be added here
  console.log('3D dashboard clicked');
});
</script>

</body>
</html>
"""

def create_app_3d():
    app = FastAPI(title="CouncilKey-Os 3D Dashboard")
    
    @app.get("/", response_class=HTMLResponse)
    def root():
        return HTML_3D
    
    return app

if __name__ == "__main__":
    import uvicorn
    app = create_app_3d()
    uvicorn.run(app, host="0.0.0.0", port=8001)
