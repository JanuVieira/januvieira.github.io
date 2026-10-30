/*
 * DNA helix for the hero, ported from PrivDNA's DNAHelix/DNAScene
 * (React Three Fiber) to a dependency-free 2D canvas with the same
 * geometry, camera, colours, flywheel drag and mouse tilt.
 *
 * Copyright (c) 2026 PrivDNA
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy
 * of this software and associated documentation files (the "Software"), to deal
 * in the Software without restriction, including without limitation the rights
 * to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 * copies of the Software, and to permit persons to whom the Software is
 * furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all
 * copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 * OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
 * SOFTWARE.
 */
(() => {
  const canvas = document.querySelector('.hero__dna');
  if (!canvas || !canvas.getContext) return;
  const ctx = canvas.getContext('2d');
  if (!ctx) return;

  // Resolve qualquer cor CSS válida (incluindo var(), hex curto e rgb()) para
  // canais RGB usados pelas strings rgba() do canvas.
  const colorToken = getComputedStyle(canvas).getPropertyValue('--helix').trim() || '#00e8c8';
  const colorProbe = document.createElement('span');
  colorProbe.hidden = true;
  colorProbe.style.color = '#00e8c8';
  colorProbe.style.color = colorToken;
  document.body.append(colorProbe);
  const resolvedColor = getComputedStyle(colorProbe).color;
  colorProbe.remove();
  const colorChannels = (resolvedColor.match(/[\d.]+/g) || [])
    .slice(0, 3)
    .map(Number);
  const COLOR = colorChannels.length === 3 && colorChannels.every(Number.isFinite)
    ? colorChannels.join(', ')
    : '0, 232, 200';
  // Motion, per 60 fps frame. Scaled by the real frame time in tick(), so
  // the pace is the same on 60 and 120 Hz screens and a dropped frame
  // doesn't jump. Calm but visible, with eased starts and stops: the spin
  // accelerates in on load, the tilt follows the mouse with damping and a
  // drag glides back to the idle pace.
  const BASE_SPEED = 0.0014; // idle spin, radians (one turn ≈ 75 s)
  const PARTICLE_DRIFT = 0.0012; // particle rise, scene units
  const INTRO_MS = 1600; // spin eases in from rest over this time
  const FRICTION = 0.96; // flywheel glide after a drag (~1 s back to idle)
  const TILT_EASE = 0.03; // how fast the tilt follows the mouse (damped)
  const TILT_X = 0.05; // max tilt from the mouse, radians
  const TILT_Z = -0.03;
  const DRAG_GAIN = 0.003; // spin per pixel dragged
  const DRAG_EASE = 0.25; // smoothing of the drag speed
  const CAMERA_Z = 6;
  const FOV = (50 * Math.PI) / 180;
  // Fixed screen-plane tilt of the helix axis (negative leans it like "/").
  const TILT = (-20 * Math.PI) / 180;
  // Particle size in scene units (the original used 0.03).
  const PARTICLE_SIZE = 0.05;
  // Zoom applied on top of the original camera (1 = original size).
  // The --dna-scale CSS token overrides it (e.g. a smaller helix on phones).
  const SCALE = 1.4;

  // Geometry: two strands, a rung every 10th point, floating particles.
  const turns = 4;
  const totalPoints = turns * 60;
  const radius = 1.2;
  const height = 8;
  const strand1 = [];
  const strand2 = [];
  const rungs = [];
  for (let i = 0; i < totalPoints; i++) {
    const t = i / (totalPoints - 1);
    const angle = t * 2 * Math.PI * turns;
    const y = -height / 2 + t * height;
    const p1 = [Math.cos(angle) * radius, y, Math.sin(angle) * radius];
    const p2 = [
      Math.cos(angle + Math.PI) * radius,
      y,
      Math.sin(angle + Math.PI) * radius,
    ];
    strand1.push(p1);
    strand2.push(p2);
    if (i % 10 === 0) rungs.push([p1, p2]);
  }
  const halfH = (height * 1.5) / 2;
  let particleCount = 0;
  let particles = [];
  const createParticles = (count) => {
    particleCount = count;
    particles = Array.from({ length: count }, () => [
      (Math.random() - 0.5) * 6,
      (Math.random() - 0.5) * height * 1.5,
      (Math.random() - 0.5) * 6,
    ]);
    canvas.dataset.particles = String(count);
  };

  const rotation = { x: 0, y: 0, z: 0 };
  const mouse = { x: 0, y: 0 };
  const drag = {
    isDragging: false,
    lastX: 0,
    startX: 0,
    startY: 0,
    axis: null,
    pointerType: '',
    velocity: 0, // starts at rest and eases in (see INTRO_MS)
  };
  const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)');
  const listenMediaChange = (listener) => {
    if (typeof reducedMotion.addEventListener === 'function') {
      reducedMotion.addEventListener('change', listener);
    } else {
      reducedMotion.addListener(listener);
    }
  };
  let visible = true;
  let width = 0;
  let heightPx = 0;
  let dpr = 1;
  let centerX = 0;
  let scale = SCALE;

  const resize = () => {
    dpr = Math.min(window.devicePixelRatio || 1, 1.5);
    width = canvas.clientWidth;
    heightPx = canvas.clientHeight;
    const center = parseFloat(getComputedStyle(canvas).getPropertyValue('--dna-center'));
    centerX = width * (Number.isNaN(center) ? 0.5 : center);
    const zoom = parseFloat(getComputedStyle(canvas).getPropertyValue('--dna-scale'));
    scale = Number.isNaN(zoom) ? SCALE : zoom;
    const requestedParticles = parseInt(
      getComputedStyle(canvas).getPropertyValue('--dna-particles'),
      10,
    );
    const nextCount = Number.isNaN(requestedParticles) ? 200 : requestedParticles;
    if (nextCount !== particleCount) createParticles(nextCount);
    canvas.width = Math.round(width * dpr);
    canvas.height = Math.round(heightPx * dpr);
  };

  // Sines and cosines of the current rotation, computed once per frame in
  // draw() instead of once per point (~700 points a frame).
  const COS_TILT = Math.cos(TILT);
  const SIN_TILT = Math.sin(TILT);
  const TAN_HALF_FOV = Math.tan(FOV / 2);
  const view = { cx: 1, sx: 0, cy: 1, sy: 0, cz: 1, sz: 0, focal: 1 };

  // Euler XYZ (Three.js default order), then a perspective camera at z = 6.
  const project = ([x, y, z]) => {
    const { cx, sx, cy, sy, cz, sz, focal } = view;
    const x1 = x * cz - y * sz;
    const y1 = x * sz + y * cz;
    const x2 = x1 * cy + z * sy;
    const z2 = -x1 * sy + z * cy;
    const y3 = y1 * cx - z2 * sx;
    const z3 = y1 * sx + z2 * cx;
    const depth = CAMERA_Z - z3;
    const x4 = x2 * COS_TILT - y3 * SIN_TILT;
    const y4 = x2 * SIN_TILT + y3 * COS_TILT;
    return [
      centerX + (x4 * focal) / depth,
      heightPx / 2 - (y4 * focal) / depth,
      depth,
    ];
  };

  const strokePath = (points, alpha) => {
    ctx.beginPath();
    points.forEach((point, i) => {
      const [sx, sy] = project(point);
      if (i) ctx.lineTo(sx, sy);
      else ctx.moveTo(sx, sy);
    });
    ctx.strokeStyle = `rgba(${COLOR}, ${alpha})`;
    ctx.stroke();
  };

  const draw = () => {
    view.cx = Math.cos(rotation.x);
    view.sx = Math.sin(rotation.x);
    view.cy = Math.cos(rotation.y);
    view.sy = Math.sin(rotation.y);
    view.cz = Math.cos(rotation.z);
    view.sz = Math.sin(rotation.z);
    view.focal = (scale * heightPx) / 2 / TAN_HALF_FOV;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, width, heightPx);
    ctx.lineWidth = 1;
    strokePath(strand1, 0.6);
    strokePath(strand2, 0.6);
    ctx.beginPath();
    rungs.forEach(([a, b]) => {
      const [ax, ay] = project(a);
      const [bx, by] = project(b);
      ctx.moveTo(ax, ay);
      ctx.lineTo(bx, by);
    });
    ctx.strokeStyle = `rgba(${COLOR}, 0.2)`;
    ctx.stroke();
    // All particles in one path and a single fill.
    ctx.fillStyle = `rgba(${COLOR}, 0.9)`;
    ctx.beginPath();
    particles.forEach((point) => {
      const [sx, sy, depth] = project(point);
      // Size attenuation as in THREE.PointsMaterial, with larger round points.
      const r = Math.max(1.5, (PARTICLE_SIZE * heightPx) / 2 / depth) / 2;
      ctx.moveTo(sx + r, sy);
      ctx.arc(sx, sy, r, 0, Math.PI * 2);
    });
    ctx.fill();
  };

  let frame = 0;
  let lastTime = 0;
  let introStart = 0;
  const canAnimate = () => visible && !document.hidden && !reducedMotion.matches;
  const stop = () => {
    cancelAnimationFrame(frame);
    frame = 0;
    lastTime = 0;
  };
  const start = () => {
    if (canAnimate() && !frame) frame = requestAnimationFrame(tick);
  };
  const tick = (now) => {
    frame = 0;
    if (!canAnimate()) return;
    // Frame time in 60 fps frames, capped so a long pause doesn't jump.
    const dt = lastTime ? Math.min((now - lastTime) / (1000 / 60), 3) : 1;
    lastTime = now;
    // Idle pace eases in from rest on the first frames (ease-out cubic).
    if (!introStart) introStart = now;
    const intro = Math.min((now - introStart) / INTRO_MS, 1);
    const idle = BASE_SPEED * (1 - (1 - intro) ** 3);
    if (!drag.isDragging) {
      // Flywheel decay back toward the idle pace.
      drag.velocity = idle + (drag.velocity - idle) * FRICTION ** dt;
    }
    rotation.y += drag.velocity * dt;
    const ease = 1 - (1 - TILT_EASE) ** dt;
    rotation.x += (mouse.y * TILT_X - rotation.x) * ease;
    rotation.z += (mouse.x * TILT_Z - rotation.z) * ease;
    particles.forEach((point) => {
      point[1] += PARTICLE_DRIFT * dt;
      if (point[1] > halfH) point[1] = -halfH;
    });
    draw();
    frame = requestAnimationFrame(tick);
  };

  listenMediaChange(() => {
    if (reducedMotion.matches) stop();
    else start();
    draw();
  });
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) stop();
    else start();
  });

  window.addEventListener('mousemove', (event) => {
    mouse.x = (event.clientX / window.innerWidth) * 2 - 1;
    mouse.y = -(event.clientY / window.innerHeight) * 2 + 1;
  });
  canvas.addEventListener('pointerdown', (event) => {
    drag.isDragging = true;
    drag.lastX = event.clientX;
    drag.startX = event.clientX;
    drag.startY = event.clientY;
    drag.axis = event.pointerType === 'mouse' ? 'x' : null;
    drag.pointerType = event.pointerType;
    if (drag.axis === 'x') {
      canvas.setPointerCapture(event.pointerId);
      canvas.classList.add('is-dragging');
    }
  });
  canvas.addEventListener('pointermove', (event) => {
    if (!drag.isDragging) return;
    if (drag.pointerType !== 'mouse' && !drag.axis) {
      const dx = Math.abs(event.clientX - drag.startX);
      const dy = Math.abs(event.clientY - drag.startY);
      if (Math.max(dx, dy) < 8) return;
      if (dy >= dx) {
        drag.isDragging = false;
        return;
      }
      drag.axis = 'x';
      canvas.setPointerCapture(event.pointerId);
      canvas.classList.add('is-dragging');
    }
    const target = (event.clientX - drag.lastX) * DRAG_GAIN;
    drag.velocity += (target - drag.velocity) * DRAG_EASE;
    drag.lastX = event.clientX;
  });
  const release = () => {
    drag.isDragging = false;
    drag.axis = null;
    canvas.classList.remove('is-dragging');
  };
  canvas.addEventListener('pointerup', release);
  canvas.addEventListener('pointercancel', release);
  canvas.addEventListener('pointerleave', release);

  // Pause while the hero is off-screen.
  new IntersectionObserver(([entry]) => {
    visible = entry.isIntersecting;
    if (visible) start();
    else stop();
  }).observe(canvas);
  new ResizeObserver(() => {
    resize();
    draw();
  }).observe(canvas);

  resize();
  draw();
  start();
  // Next frame, so the CSS fade-in starts from the hidden state.
  requestAnimationFrame(() => canvas.classList.add('is-ready'));
})();
