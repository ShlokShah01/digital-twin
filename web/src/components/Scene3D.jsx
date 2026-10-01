import { useEffect, useRef } from "react";
import { useReducedMotion } from "motion/react";

const threePromise = import("three");

function mulberry32(seed) {
  let a = seed >>> 0;
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export default function Scene3D({ className = "", seed = 7 }) {
  const mountRef = useRef(null);
  const prefersReduced = useReducedMotion();

  useEffect(() => {
    const mount = mountRef.current;
    if (!mount) return;

    let alive = true;
    let cleanup = () => {};

    threePromise.then((THREE) => {
      if (!alive || !mount || !THREE) return;

      const reduced = prefersReduced === true;
      const css = getComputedStyle(document.documentElement);
      const accent = css.getPropertyValue("--accent").trim() || "#cba96b";
      const dim = css.getPropertyValue("--muted").trim() || "#a49cab";

      const width = mount.clientWidth || 480;
      const height = mount.clientHeight || 360;

      const scene = new THREE.Scene();
      const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 100);
      camera.position.set(0, 0, 7.5);

      const renderer = new THREE.WebGLRenderer({
        alpha: true,
        antialias: true,
        powerPreference: "low-power",
      });
      renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
      renderer.setSize(width, height);
      mount.appendChild(renderer.domElement);

      const group = new THREE.Group();

      const rand = mulberry32(seed);
      const N = 96;
      const positions = new Float32Array(N * 3);
      const speeds = [];
      for (let i = 0; i < N; i++) {
        const r = 2 + rand() * 1.8;
        const theta = rand() * Math.PI * 2;
        const phi = Math.acos(2 * rand() - 1);
        positions[i * 3] = r * Math.sin(phi) * Math.cos(theta);
        positions[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta);
        positions[i * 3 + 2] = r * Math.cos(phi);
        speeds.push(0.1 + rand() * 0.35);
      }

      const pointsGeo = new THREE.BufferGeometry();
      pointsGeo.setAttribute("position", new THREE.BufferAttribute(positions, 3));
      const pointsMat = new THREE.PointsMaterial({
        color: accent,
        size: 0.055,
        transparent: true,
        opacity: 0.65,
        sizeAttenuation: true,
      });
      const points = new THREE.Points(pointsGeo, pointsMat);
      group.add(points);

      const shellGeo = new THREE.IcosahedronGeometry(2.9, 1);
      const shellMat = new THREE.MeshBasicMaterial({
        color: dim,
        wireframe: true,
        transparent: true,
        opacity: 0.16,
      });
      const shell = new THREE.Mesh(shellGeo, shellMat);
      group.add(shell);

      const coreGeo = new THREE.IcosahedronGeometry(1.2, 0);
      const coreMat = new THREE.MeshBasicMaterial({
        color: accent,
        wireframe: true,
        transparent: true,
        opacity: 0.4,
      });
      const core = new THREE.Mesh(coreGeo, coreMat);
      group.add(core);

      scene.add(group);

      let raf;
      const t0 = performance.now();

      const render = (now) => {
        const t = (now - t0) / 1000;
        group.rotation.y = t * 0.14;
        group.rotation.x = Math.sin(t * 0.07) * 0.35;
        core.rotation.z = t * 0.3;
        core.rotation.y = t * 0.2;
        for (let i = 0; i < N; i++) {
          positions[i * 3 + 1] += Math.sin(t * speeds[i]) * 0.0025;
        }
        pointsGeo.attributes.position.needsUpdate = true;
        renderer.render(scene, camera);
      };

      if (reduced) {
        render(t0);
      } else {
        const loop = (now) => {
          if (!alive) return;
          render(now);
          raf = requestAnimationFrame(loop);
        };
        raf = requestAnimationFrame(loop);
      }

      const onResize = () => {
        const w = mount.clientWidth || width;
        const h = mount.clientHeight || height;
        camera.aspect = w / h;
        camera.updateProjectionMatrix();
        renderer.setSize(w, h);
      };
      window.addEventListener("resize", onResize);

      cleanup = () => {
        cancelAnimationFrame(raf);
        window.removeEventListener("resize", onResize);
        pointsGeo.dispose();
        pointsMat.dispose();
        shellGeo.dispose();
        shellMat.dispose();
        coreGeo.dispose();
        coreMat.dispose();
        renderer.dispose();
        if (renderer.domElement.parentNode === mount) {
          mount.removeChild(renderer.domElement);
        }
      };
    });

    return () => {
      alive = false;
      cleanup();
    };
  }, [prefersReduced, seed]);

  return (
    <div
      ref={mountRef}
      aria-hidden="true"
      data-slot="scene3d"
      className={className}
    />
  );
}