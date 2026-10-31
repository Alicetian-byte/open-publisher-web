import type { ComponentType, CSSProperties, ReactNode } from "react";

interface CursorGridProps {
  cellSize?: number;
  color?: string;
  gridColor?: string;
  radius?: number;
  maxOpacity?: number;
  fillOpacity?: number;
  gridOpacity?: number;
  spotlight?: number;
  holdTime?: number;
  fadeDuration?: number;
  clickPulse?: boolean;
  intro?: boolean;
  edgeFade?: number;
  dpr?: number;
  children?: ReactNode;
  className?: string;
  style?: CSSProperties;
}

declare const CursorGrid: ComponentType<CursorGridProps>;
export default CursorGrid;
