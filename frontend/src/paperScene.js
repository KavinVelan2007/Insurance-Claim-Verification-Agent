// Hero backdrop: floating claim "papers" linked by thin red verification threads.
// Lazy-loaded (keeps three.js out of the main bundle); pauses offscreen; static under reduced motion.
import {
  Scene, PerspectiveCamera, WebGLRenderer, PlaneGeometry, MeshLambertMaterial, Mesh,
  AmbientLight, DirectionalLight, CanvasTexture, DoubleSide, BufferGeometry, BufferAttribute,
  LineSegments, LineBasicMaterial, SRGBColorSpace,
} from 'three';

const RED = '#d7001f';

function pageTexture() {
  const c = document.createElement('canvas');
  const w = 256, h = 340, f = 54, r = 18;
  c.width = w; c.height = h;
  const g = c.getContext('2d');
  g.beginPath();
  g.moveTo(r, 2); g.lineTo(w - f, 2); g.lineTo(w - 2, f); g.lineTo(w - 2, h - r);
  g.quadraticCurveTo(w - 2, h - 2, w - r, h - 2); g.lineTo(r, h - 2);
  g.quadraticCurveTo(2, h - 2, 2, h - r); g.lineTo(2, r); g.quadraticCurveTo(2, 2, r, 2);
  g.closePath();
  g.fillStyle = '#ffffff'; g.fill();
  g.lineWidth = 4; g.strokeStyle = '#e6e1d8'; g.stroke();
  g.beginPath(); g.moveTo(w - f, 2); g.lineTo(w - f, f); g.lineTo(w - 2, f); g.closePath();
  g.fillStyle = '#f2eee7'; g.fill(); g.stroke();
  g.lineCap = 'round'; g.lineWidth = 9;
  g.strokeStyle = RED;
  [[36, 74, 150], [36, 100, 120]].forEach(([x, y, l]) => { g.beginPath(); g.moveTo(x, y); g.lineTo(x + l, y); g.stroke(); });
  g.strokeStyle = '#e4dfd6'; g.lineWidth = 7;
  for (let y = 146, i = 0; y < 310; y += 26, i++) {
    g.beginPath(); g.moveTo(36, y); g.lineTo(36 + [180, 150, 172, 120, 166, 96, 140][i % 7], y); g.stroke();
  }
  const t = new CanvasTexture(c);
  t.colorSpace = SRGBColorSpace;
  return t;
}

export function createPaperScene(canvas) {
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const renderer = new WebGLRenderer({ canvas, antialias: true, alpha: true, powerPreference: 'low-power' });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5));
  const scene = new Scene();
  const camera = new PerspectiveCamera(38, 1, 0.1, 50);
  camera.position.set(0, 0, 11);

  scene.add(new AmbientLight(0xffffff, 1.9));
  const sun = new DirectionalLight(0xffffff, 1.4);
  sun.position.set(-3, 4, 6);
  scene.add(sun);

  const tex = pageTexture();
  const geo = new PlaneGeometry(1.2, 1.6);
  const mat = new MeshLambertMaterial({ map: tex, side: DoubleSide, alphaTest: 0.5 });
  const sheets = [];
  const N = 14;
  for (let i = 0; i < N; i++) {
    const m = new Mesh(geo, mat);
    const s = {
      m,
      x: 2.5 + Math.random() * 9,
      y: -2.6 + Math.random() * 5.2,
      z: -4 + Math.random() * 4.5,
      rx: (Math.random() - 0.5) * 0.8, ry: (Math.random() - 0.5) * 1.2, rz: (Math.random() - 0.5) * 0.6,
      f: 0.4 + Math.random() * 0.6, p: Math.random() * Math.PI * 2,
    };
    const k = 0.75 + Math.random() * 0.5;
    m.scale.set(k, k, k);
    scene.add(m);
    sheets.push(s);
  }

  // Each sheet threads to its two nearest neighbours.
  const pairs = [];
  sheets.forEach((a, i) => {
    sheets.map((b, j) => [j, (a.x - b.x) ** 2 + (a.y - b.y) ** 2 + (a.z - b.z) ** 2])
      .filter(([j]) => j !== i).sort((u, v) => u[1] - v[1]).slice(0, 2)
      .forEach(([j]) => { if (!pairs.some(([p, q]) => p === j && q === i)) pairs.push([i, j]); });
  });
  const pos = new Float32Array(pairs.length * 6);
  const lineGeo = new BufferGeometry();
  lineGeo.setAttribute('position', new BufferAttribute(pos, 3));
  const lineMat = new LineBasicMaterial({ color: RED, transparent: true, opacity: 0.2 });
  scene.add(new LineSegments(lineGeo, lineMat));

  let time = 0, last = performance.now(), raf = 0, visible = true;
  let mx = 0, my = 0;

  function place() {
    sheets.forEach(s => {
      s.m.position.set(s.x, s.y + Math.sin(time * s.f + s.p) * 0.28, s.z);
      s.m.rotation.set(s.rx + Math.sin(time * 0.5 * s.f + s.p) * 0.3, s.ry + Math.cos(time * 0.4 * s.f + s.p) * 0.35, s.rz);
    });
    pairs.forEach(([i, j], k) => {
      const a = sheets[i].m.position, b = sheets[j].m.position;
      pos.set([a.x, a.y, a.z, b.x, b.y, b.z], k * 6);
    });
    lineGeo.attributes.position.needsUpdate = true;
  }

  function resize() {
    const w = canvas.clientWidth, h = canvas.clientHeight;
    if (!w || !h) return;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    // Narrow screens: pull back so the stack still fits.
    camera.position.z = w < 700 ? 15 : 11;
    camera.updateProjectionMatrix();
    if (reduced) render();
  }

  function render() {
    camera.position.x += (mx * 0.5 - camera.position.x) * 0.04;
    camera.position.y += (-my * 0.3 - camera.position.y) * 0.04;
    camera.lookAt(2.2, 0, 0);
    renderer.render(scene, camera);
  }

  function frame(now) {
    const dt = Math.min((now - last) / 1000, 0.05);
    last = now;
    time += dt;
    place();
    render();
    raf = visible ? requestAnimationFrame(frame) : 0;
  }

  const onMove = e => { mx = e.clientX / window.innerWidth - 0.5; my = e.clientY / window.innerHeight - 0.5; };
  const ro = new ResizeObserver(resize);
  ro.observe(canvas);
  const io = new IntersectionObserver(([e]) => {
    visible = e.isIntersecting;
    if (visible && !raf && !reduced) { last = performance.now(); raf = requestAnimationFrame(frame); }
  });
  io.observe(canvas);
  resize();
  place();
  if (reduced) render();
  else { window.addEventListener('pointermove', onMove); raf = requestAnimationFrame(frame); }

  return {
    dispose() {
      cancelAnimationFrame(raf);
      ro.disconnect(); io.disconnect();
      window.removeEventListener('pointermove', onMove);
      geo.dispose(); mat.dispose(); tex.dispose(); lineGeo.dispose(); lineMat.dispose();
      renderer.dispose();
    },
  };
}
