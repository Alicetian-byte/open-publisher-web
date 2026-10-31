import { useEffect, useRef } from "react";

const vertex = `#version 300 es
void main() {
  vec2 p = vec2(float((gl_VertexID << 1) & 2), float(gl_VertexID & 2));
  gl_Position = vec4(p * 2.0 - 1.0, 0.0, 1.0);
}`;
const fragment = `#version 300 es
precision highp float;
uniform sampler2D uImage;
uniform sampler2D uMask;
uniform vec2 uView;
uniform vec2 uImageSize;
uniform vec3 uPointer;
uniform vec4 uInteraction;
uniform vec4 uDrag;
uniform vec2 uPixel;
uniform float uTime;
uniform float uEnabled;
out vec4 outColor;
void main() {
  vec2 screen = vec2(gl_FragCoord.x, uView.y - gl_FragCoord.y) / uView;
  float cover = max(uView.x / uImageSize.x, uView.y / uImageSize.y);
  vec2 crop = uView / (uImageSize * cover);
  vec2 uv = (screen - 0.5) * crop + 0.5;
  float mask = texture(uMask, uv).a;
  // Use the supplied SlicedWaves two-wave rhythm to move the actual artwork.
  float phase = uv.x < 0.4 ? 0.0 : 2.1;
  float wave = 0.62 * sin(uv.y * 7.0 - uTime * 0.55 + phase)
    + 0.38 * sin(uv.y * 13.3 + uTime * 0.82 + phase);
  vec2 offset = vec2(wave * 0.0038, sin(uTime * 0.42 + phase) * 0.0023);
  vec2 delta = uPointer.xy - uv;
  float nearMouse = exp(-dot(delta, delta) / 0.0075) * uPointer.z;
  offset -= clamp(delta, vec2(-0.10), vec2(0.10)) * nearMouse * 0.08;
  // Texture-space displacement keeps the printed lettering attached to the paper.
  float dragRegion = exp(-dot(uv - uDrag.xy, uv - uDrag.xy) / 0.012);
  offset = offset * mask - uDrag.zw * dragRegion * mask * uInteraction.w;
  float foreground = smoothstep(0.56, 0.78, uv.y);
  float leftPaper = foreground * (1.0 - smoothstep(0.25, 0.4, uv.x));
  float rightPaper = foreground * smoothstep(0.62, 0.78, uv.x);
  float leftLift = 1.6 * sin(uTime * 0.48) + 4.0 * uInteraction.y;
  float rightLift = 1.5 * sin(uTime * 0.39 + 2.1) + 4.0 * uInteraction.z;
  offset.y += uPixel.y * (leftPaper * leftLift + rightPaper * rightLift);
  vec2 sampleAt = clamp(uv + offset * uEnabled, vec2(0.001), vec2(0.999));
  outColor = texture(uImage, sampleAt);
  outColor.rgb += vec3(1.0, 0.82, 0.5) * uEnabled * (
    mask * nearMouse * uInteraction.x * 0.045
    + (leftPaper * uInteraction.y + rightPaper * uInteraction.z) * 0.018);
}`;

/** Warp a single copy of the artwork: no duplicate static paper beneath it. */
export default function ManuscriptFloat({ enabled }: { enabled: boolean }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const enabledRef = useRef(enabled);
  enabledRef.current = enabled;

  useEffect(() => {
    const canvas = canvasRef.current;
    const gl = canvas?.getContext("webgl2", { alpha: true, antialias: false, depth: false });
    if (!canvas || !gl) return;
    const shaders: WebGLShader[] = [];
    const program = gl.createProgram();
    if (!program) return;
    for (const [type, source] of [[gl.VERTEX_SHADER, vertex], [gl.FRAGMENT_SHADER, fragment]] as const) {
      const shader = gl.createShader(type);
      if (!shader) { gl.deleteProgram(program); return; }
      shaders.push(shader);
      gl.shaderSource(shader, source);
      gl.compileShader(shader);
      gl.attachShader(program, shader);
    }
    gl.linkProgram(program);
    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
      shaders.forEach((shader) => gl.deleteShader(shader));
      gl.deleteProgram(program);
      return; // The original CSS background remains visible if WebGL is unavailable.
    }
    const uniforms = Object.fromEntries(["uImage", "uMask", "uView", "uImageSize", "uPointer", "uInteraction", "uDrag", "uPixel", "uTime", "uEnabled"]
      .map((name) => [name, gl.getUniformLocation(program, name)]));
    const textures = [gl.createTexture(), gl.createTexture()];
    const images = [new Image(), new Image()];
    let loaded = 0;
    let disposed = false;
    let raf = 0;
    let previous = 0;
    let time = 0;
    let strength = 0;
    const pointer = { x: 0.5, y: 0.5, inside: false };
    const smooth = { x: 0.5, y: 0.5, presence: 0 };
    const interaction = { flow: 0, left: 0, right: 0, dragging: 0 };
    const drag = { x: 0.5, y: 0.5, dx: 0, dy: 0, active: false };
    const dragSmooth = { dx: 0, dy: 0 };
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)");
    const resize = () => {
      const ratio = Math.min(window.devicePixelRatio || 1, 1.25);
      canvas.width = Math.max(1, Math.round(canvas.clientWidth * ratio));
      canvas.height = Math.max(1, Math.round(canvas.clientHeight * ratio));
      wake();
    };
    const render = (now: number) => {
      raf = 0;
      if (disposed || document.hidden || loaded < 2) return;
      const dt = previous ? Math.min((now - previous) / 1000, 0.05) : 1 / 60;
      previous = now;
      const moving = enabledRef.current && !reduce.matches;
      if (moving) time += dt;
      const ease = 1 - Math.exp(-dt * 5);
      strength += ((moving ? 1 : 0) - strength) * ease;
      smooth.x += (pointer.x - smooth.x) * ease;
      smooth.y += (pointer.y - smooth.y) * ease;
      smooth.presence += ((pointer.inside && moving ? 1 : 0) - smooth.presence) * ease;
      const backdrop = canvas.closest(".whale-login-backdrop");
      const paper = backdrop?.getAttribute("data-paper-hover");
      interaction.flow += ((moving && backdrop?.classList.contains("has-scroll-hover") ? 1 : 0) - interaction.flow) * ease;
      interaction.left += ((moving && paper === "left" ? 1 : 0) - interaction.left) * ease;
      interaction.right += ((moving && paper === "right" ? 1 : 0) - interaction.right) * ease;
      interaction.dragging += ((moving && drag.active ? 1 : 0) - interaction.dragging) * ease;
      dragSmooth.dx += ((drag.active ? drag.dx : 0) - dragSmooth.dx) * ease;
      dragSmooth.dy += ((drag.active ? drag.dy : 0) - dragSmooth.dy) * ease;
      gl.viewport(0, 0, canvas.width, canvas.height);
      gl.useProgram(program);
      textures.forEach((texture, i) => {
        gl.activeTexture(gl.TEXTURE0 + i);
        gl.bindTexture(gl.TEXTURE_2D, texture);
      });
      gl.uniform1i(uniforms.uImage, 0);
      gl.uniform1i(uniforms.uMask, 1);
      gl.uniform2f(uniforms.uView, canvas.width, canvas.height);
      gl.uniform2f(uniforms.uImageSize, images[0].naturalWidth, images[0].naturalHeight);
      gl.uniform3f(uniforms.uPointer, smooth.x, smooth.y, smooth.presence);
      gl.uniform4f(uniforms.uInteraction, interaction.flow, interaction.left, interaction.right, interaction.dragging);
      gl.uniform4f(uniforms.uDrag, drag.x, drag.y, dragSmooth.dx, dragSmooth.dy);
      const fit = Math.max(canvas.clientWidth / images[0].naturalWidth, canvas.clientHeight / images[0].naturalHeight);
      gl.uniform2f(uniforms.uPixel, 1 / (images[0].naturalWidth * fit), 1 / (images[0].naturalHeight * fit));
      gl.uniform1f(uniforms.uTime, time);
      gl.uniform1f(uniforms.uEnabled, reduce.matches ? 0 : strength);
      gl.drawArrays(gl.TRIANGLES, 0, 3);
      canvas.dataset.ready = "true";
      if (moving || strength > 0.001) raf = requestAnimationFrame(render);
    };
    function wake() {
      if (!raf && !disposed && loaded === 2 && !document.hidden) raf = requestAnimationFrame(render);
    }
    images.forEach((image, index) => {
      image.onload = () => {
        if (disposed) return;
        gl.activeTexture(gl.TEXTURE0 + index);
        gl.bindTexture(gl.TEXTURE_2D, textures[index]);
        gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, image);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
        loaded++;
        wake();
      };
      image.src = index === 0 ? "/gaoliu-library-login.jpg" : "/gaoliu-manuscript-mask.svg";
    });
    const move = (event: PointerEvent) => {
      if (loaded < 2) return;
      const rect = canvas.getBoundingClientRect();
      const fit = Math.max(rect.width / images[0].naturalWidth, rect.height / images[0].naturalHeight);
      pointer.x = (event.clientX - rect.left - rect.width / 2) / (images[0].naturalWidth * fit) + 0.5;
      pointer.y = (event.clientY - rect.top - rect.height / 2) / (images[0].naturalHeight * fit) + 0.5;
      const backdrop = canvas.closest(".whale-login-backdrop");
      pointer.inside = Boolean(backdrop?.classList.contains("has-scroll-hover") || backdrop?.classList.contains("is-scroll-dragging"))
        && !(event.target instanceof Element && event.target.closest(".auth-card"));
      if (drag.active) {
        // Clamp traction to six screen pixels; it never stretches the whole scene.
        drag.dx = Math.max(-6, Math.min(6, (pointer.x - drag.x) * images[0].naturalWidth * fit)) / (images[0].naturalWidth * fit);
        drag.dy = Math.max(-6, Math.min(6, (pointer.y - drag.y) * images[0].naturalHeight * fit)) / (images[0].naturalHeight * fit);
      }
      wake();
    };
    const down = (event: PointerEvent) => {
      if (event.button !== 0 || !enabledRef.current || reduce.matches || !(event.target instanceof Element) || !event.target.closest(".whale-login-backdrop__flow-hit")) return;
      move(event);
      drag.x = pointer.x;
      drag.y = pointer.y;
      drag.dx = drag.dy = 0;
      drag.active = true;
      wake();
    };
    const up = () => { drag.active = false; wake(); };
    const leave = () => { pointer.inside = false; drag.active = false; wake(); };
    const visibility = () => { previous = 0; if (document.hidden) leave(); wake(); };
    const observer = new ResizeObserver(resize);
    observer.observe(canvas);
    window.addEventListener("pointermove", move, { passive: true });
    window.addEventListener("pointerdown", down, { passive: true });
    window.addEventListener("pointerup", up);
    window.addEventListener("pointercancel", up);
    window.addEventListener("blur", leave);
    document.documentElement.addEventListener("pointerleave", leave);
    document.addEventListener("visibilitychange", visibility);
    reduce.addEventListener("change", wake);
    // The existing animation switch changes the parent class, including while idle.
    const mutation = new MutationObserver(wake);
    if (canvas.closest(".whale-login-backdrop")) mutation.observe(canvas.closest(".whale-login-backdrop")!, { attributes: true, attributeFilter: ["class", "data-paper-hover"] });
    resize();
    return () => {
      disposed = true;
      cancelAnimationFrame(raf);
      observer.disconnect();
      mutation.disconnect();
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerdown", down);
      window.removeEventListener("pointerup", up);
      window.removeEventListener("pointercancel", up);
      window.removeEventListener("blur", leave);
      document.documentElement.removeEventListener("pointerleave", leave);
      document.removeEventListener("visibilitychange", visibility);
      reduce.removeEventListener("change", wake);
      images.forEach((image) => { image.onload = null; });
      textures.forEach((texture) => gl.deleteTexture(texture));
      shaders.forEach((shader) => gl.deleteShader(shader));
      gl.deleteProgram(program);
    };
  }, []);

  return <canvas ref={canvasRef} className="manuscript-float" aria-hidden="true" />;
}
