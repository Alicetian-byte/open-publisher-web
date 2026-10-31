import type { CSSProperties } from "react";

export interface LightRaysProps {
  raysOrigin?: "top-center" | "top-left" | "top-right" | "left" | "right" | "bottom-center" | "bottom-left" | "bottom-right";
  raysColor?: string;
  raysSpeed?: number;
  lightSpread?: number;
  rayLength?: number;
  rayDensity?: number;
  tilt?: number;
  raySharpness?: number;
  glow?: number;
  haze?: number;
  atmosphere?: number;
  intensity?: number;
  pulsating?: boolean;
  fadeDistance?: number;
  saturation?: number;
  followMouse?: boolean;
  mouseInfluence?: number;
  cursorShadow?: boolean;
  clickPulse?: boolean;
  noiseAmount?: number;
  distortion?: number;
  intro?: boolean;
  lightMode?: boolean;
  opacity?: number;
  maxDevicePixelRatio?: number;
  className?: string;
  style?: CSSProperties;
}

export default function LightRays(props: LightRaysProps): import("react").ReactElement;
