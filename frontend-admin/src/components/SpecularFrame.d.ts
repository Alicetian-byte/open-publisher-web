import type { CSSProperties, ReactElement } from "react";

interface SpecularFrameProps {
  radius?: number;
  lineColor?: string;
  baseColor?: string;
  intensity?: number;
  idleIntensity?: number;
  shineSize?: number;
  shineFade?: number;
  thickness?: number;
  glow?: number;
  speed?: number;
  followMouse?: boolean;
  proximity?: number;
  autoAnimate?: boolean;
  disabled?: boolean;
  className?: string;
  style?: CSSProperties;
}

export default function SpecularFrame(props: SpecularFrameProps): ReactElement;
