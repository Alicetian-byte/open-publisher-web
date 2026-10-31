import { useEffect, useRef, useState, type PointerEvent as ReactPointerEvent } from "react";
import Particles from "./Particles";
import ManuscriptFloat from "./ManuscriptFloat";
import LightRays from "./LightRays";
import "./ManuscriptWaves.css";

const PARTICLE_COLORS = ["#f5dfb2", "#d8efff", "#a9d4f6"];

export function WhaleLoginBackdrop() {
  const [enabled, setEnabled] = useState(() => {
    try {
      return localStorage.getItem("opw.login-motion.v2") !== "off"
        && !window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    } catch {
      return true;
    }
  });
  const [scrollHovered, setScrollHovered] = useState(false);
  const [scrollDragging, setScrollDragging] = useState(false);
  const backdropRef = useRef<HTMLDivElement>(null);
  const draggingRef = useRef(false);

  useEffect(() => {
    // Update CSS once per frame instead of re-rendering every canvas on mousemove.
    let frame = 0;
    let x = 0;
    let y = 0;
    const flush = () => {
      frame = 0;
      const style = backdropRef.current?.style;
      style?.setProperty("--nebula-pull-x", `${x * 0.045}px`);
      style?.setProperty("--nebula-pull-y", `${y * 0.045}px`);
    };
    const schedule = () => { if (!frame) frame = requestAnimationFrame(flush); };
    const onPointerMove = (event: PointerEvent) => {
      if (!enabled || event.pointerType === "touch") return;
      x = (event.clientX / window.innerWidth - 0.5) * Math.min(window.innerWidth * 0.22, 180);
      y = (event.clientY / window.innerHeight - 0.5) * Math.min(window.innerHeight * 0.18, 130);
      schedule();
    };
    window.addEventListener("pointermove", onPointerMove, { passive: true });
    const resetPointer = () => {
      x = y = 0;
      draggingRef.current = false;
      setScrollDragging(false);
      setScrollHovered(false);
      backdropRef.current?.removeAttribute("data-paper-hover");
      schedule();
    };
    resetPointer();
    document.documentElement.addEventListener("pointerleave", resetPointer);
    window.addEventListener("blur", resetPointer);
    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener("pointermove", onPointerMove);
      document.documentElement.removeEventListener("pointerleave", resetPointer);
      window.removeEventListener("blur", resetPointer);
    };
  }, [enabled]);

  useEffect(() => {
    const preference = window.matchMedia("(prefers-reduced-motion: reduce)");
    const reduceMotion = () => { if (preference.matches) setEnabled(false); };
    preference.addEventListener("change", reduceMotion);
    return () => preference.removeEventListener("change", reduceMotion);
  }, []);

  const updateFlowPointer = (event: ReactPointerEvent<SVGPathElement>) => {
    const backdrop = backdropRef.current;
    if (!backdrop) return;
    const rect = backdrop.getBoundingClientRect();
    backdrop.style.setProperty("--flow-x", `${event.clientX - rect.left}px`);
    backdrop.style.setProperty("--flow-y", `${event.clientY - rect.top}px`);
  };

  const beginFlowDrag = (event: ReactPointerEvent<SVGPathElement>) => {
    if (!enabled || event.button !== 0) return;
    draggingRef.current = true;
    setScrollDragging(true);
    event.currentTarget.setPointerCapture(event.pointerId);
    updateFlowPointer(event);
  };

  const endFlowDrag = (event?: ReactPointerEvent<SVGPathElement>) => {
    draggingRef.current = false;
    setScrollDragging(false);
    setScrollHovered(false);
    if (event?.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
  };

  const toggle = () => {
    setEnabled((current) => {
      const next = !current;
      try { localStorage.setItem("opw.login-motion.v2", next ? "on" : "off"); } catch { /* preference is still active for this session */ }
      return next;
    });
  };

  return (
    <div
      ref={backdropRef}
      className={`whale-login-backdrop${enabled ? " is-animated" : ""}${scrollHovered ? " has-scroll-hover" : ""}${scrollDragging ? " is-scroll-dragging" : ""}`}
    >
      <div className="whale-login-backdrop__art">
        <ManuscriptFloat enabled={enabled} />
      </div>
      {/* The canvas observes window pointer events without intercepting the form. */}
      {enabled && <LightRays
        className="whale-login-backdrop__light-rays"
        raysOrigin="top-center"
        raysColor="#f5dfb2"
        raysSpeed={0.28}
        lightSpread={0.65}
        rayLength={2.4}
        rayDensity={1.2}
        raySharpness={0.22}
        glow={0.22}
        haze={0.3}
        atmosphere={0.35}
        intensity={0.85}
        opacity={0.46}
        followMouse
        mouseInfluence={0.32}
        cursorShadow
        clickPulse
        maxDevicePixelRatio={1.25}
      />}
      <div className="whale-login-backdrop__orbit-clouds" aria-hidden="true">
        <i className="whale-login-backdrop__cloud whale-login-backdrop__cloud--left" />
        <i className="whale-login-backdrop__cloud whale-login-backdrop__cloud--right" />
        <i className="whale-login-backdrop__cloud whale-login-backdrop__cloud--bottom" />
      </div>
      <div className="whale-login-backdrop__nebula">
        <i /><i /><i /><i /><i />
        <b /><b /><b />
      </div>
      <svg className="whale-login-backdrop__writing-flow" viewBox="0 0 1824 960" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
        <g transform="scale(1.824 1.708185)">
        <defs>
          <linearGradient id="writing-flow-gold" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0" stopColor="#f4dca9" stopOpacity="0" />
            <stop offset="0.48" stopColor="#fff0c9" stopOpacity="0.82" />
            <stop offset="1" stopColor="#f2d38e" stopOpacity="0" />
          </linearGradient>
          <filter id="writing-flow-glow" x="-40%" y="-40%" width="180%" height="180%">
            <feGaussianBlur stdDeviation="3" result="blur" />
            <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
          </filter>
        </defs>
        <path className="whale-login-backdrop__flow-track whale-login-backdrop__flow-track--one" d="M 190 -34 C 244 64 348 111 468 190 C 580 264 669 282 731 203 C 802 112 700 91 620 142 C 536 196 560 273 704 326 C 814 368 904 330 1035 267" />
        <path className="whale-login-backdrop__flow-track whale-login-backdrop__flow-track--two" d="M 422 -38 C 376 82 466 133 573 176 C 710 232 756 309 685 377 C 600 458 457 385 374 337 C 285 285 217 351 156 492" />
        <path pathLength="100" className="whale-login-backdrop__flow-light whale-login-backdrop__flow-light--one" d="M 190 -34 C 244 64 348 111 468 190 C 580 264 669 282 731 203 C 802 112 700 91 620 142 C 536 196 560 273 704 326 C 814 368 904 330 1035 267" />
        <path pathLength="100" className="whale-login-backdrop__flow-light whale-login-backdrop__flow-light--two" d="M 422 -38 C 376 82 466 133 573 176 C 710 232 756 309 685 377 C 600 458 457 385 374 337 C 285 285 217 351 156 492" />
        <path
          className="whale-login-backdrop__flow-hit"
          d="M 190 -34 C 244 64 348 111 468 190 C 580 264 669 282 731 203 C 802 112 700 91 620 142 C 536 196 560 273 704 326 C 814 368 904 330 1035 267"
          onPointerEnter={() => setScrollHovered(true)}
          onPointerLeave={() => { if (!draggingRef.current) setScrollHovered(false); }}
          onPointerDown={beginFlowDrag}
          onPointerMove={(event) => { if (draggingRef.current) updateFlowPointer(event); }}
          onPointerUp={endFlowDrag}
          onPointerCancel={endFlowDrag}
          onLostPointerCapture={endFlowDrag}
        />
        <circle className="whale-login-backdrop__flow-particle" r="2.2">
          <animateMotion dur="28s" repeatCount="indefinite" path="M 190 -34 C 244 64 348 111 468 190 C 580 264 669 282 731 203 C 802 112 700 91 620 142 C 536 196 560 273 704 326 C 814 368 904 330 1035 267" />
        </circle>
        <circle className="whale-login-backdrop__flow-particle whale-login-backdrop__flow-particle--second" r="1.6">
          <animateMotion dur="36s" begin="-17s" repeatCount="indefinite" path="M 422 -38 C 376 82 466 133 573 176 C 710 232 756 309 685 377 C 600 458 457 385 374 337 C 285 285 217 351 156 492" />
        </circle>
        <path
          className="whale-login-backdrop__flow-hit"
          d="M 422 -38 C 376 82 466 133 573 176 C 710 232 756 309 685 377 C 600 458 457 385 374 337 C 285 285 217 351 156 492"
          onPointerEnter={() => setScrollHovered(true)}
          onPointerLeave={() => { if (!draggingRef.current) setScrollHovered(false); }}
          onPointerDown={beginFlowDrag}
          onPointerMove={(event) => { if (draggingRef.current) updateFlowPointer(event); }}
          onPointerUp={endFlowDrag}
          onPointerCancel={endFlowDrag}
          onLostPointerCapture={endFlowDrag}
        />
        </g>
      </svg>
      <div className="whale-login-backdrop__paper-hotspots" aria-hidden="true">
        <span
          className="whale-login-backdrop__paper-glow whale-login-backdrop__paper-glow--left"
          onPointerEnter={() => backdropRef.current?.setAttribute("data-paper-hover", "left")}
          onPointerLeave={() => backdropRef.current?.removeAttribute("data-paper-hover")}
        />
        <span
          className="whale-login-backdrop__paper-glow whale-login-backdrop__paper-glow--right"
          onPointerEnter={() => backdropRef.current?.setAttribute("data-paper-hover", "right")}
          onPointerLeave={() => backdropRef.current?.removeAttribute("data-paper-hover")}
        />
      </div>
      <span className="whale-login-backdrop__flow-cursor" aria-hidden="true" />
      <div className="whale-login-backdrop__streaks"><i /><i /><i /><i /></div>
      <Particles
        alphaParticles
        className="whale-login-backdrop__particles"
        clickBurst={false}
        connectionDistance={96}
        connections
        depthOfField={0}
        drift="forward"
        driftSpeed={0.055}
        glow={0.25}
        hoverEffect="attract"
        hoverRadius={165}
        intro
        moveParticlesOnHover
        opacity={0.92}
        particleBaseSize={52}
        particleColors={PARTICLE_COLORS}
        particleCount={520}
        particleHoverFactor={0.1}
        particleSpread={5.5}
        paused={!enabled}
        pixelRatio={1.25}
        speed={0.11}
        twinkle={0.34}
        cameraDistance={22}
      />
      <button
        aria-checked={enabled}
        aria-label={enabled ? "关闭登录页动画" : "开启登录页动画"}
        className="whale-login-backdrop__toggle"
        onClick={toggle}
        role="switch"
        type="button"
      >
        <span className="whale-login-backdrop__toggle-dot" />
        <span>{enabled ? "动态背景" : "静态背景"}</span>
      </button>
    </div>
  );
}
