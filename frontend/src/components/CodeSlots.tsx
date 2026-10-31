import { useEffect, useRef, useState, type CSSProperties, type MouseEvent } from "react";
import { motion, useMotionValue, useReducedMotion, useTransform } from "motion/react";
import { Check } from "lucide-react";
import "./CodeSlots.css";

type CodeStatus = "idle" | "error" | "success";

interface CodeSlotsProps {
  length: number;
  value: string;
  status?: CodeStatus;
  onChange: (value: string) => void;
  disabled?: boolean;
  mask?: boolean;
  ariaLabel?: string;
  slotSize?: number;
  gap?: number;
  autoComplete?: "current-password" | "new-password";
}

export function CodeSlots({
  length,
  value,
  status = "idle",
  onChange,
  disabled = false,
  mask = false,
  ariaLabel = "8位数字密码",
  slotSize = 36,
  gap = 7,
  autoComplete = "current-password",
}: CodeSlotsProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const rowRef = useRef<HTMLDivElement>(null);
  const reduceMotion = useReducedMotion();
  const [focused, setFocused] = useState(false);
  const [active, setActive] = useState(Math.min(value.length, length - 1));
  const activeMotion = useMotionValue(active);
  const caretX = useTransform(activeMotion, (index) => index * (slotSize + gap));
  const safeValue = value.replace(/\D/g, "").slice(0, length);

  useEffect(() => {
    activeMotion.set(Math.min(safeValue.length, length - 1));
    setActive(Math.min(safeValue.length, length - 1));
  }, [activeMotion, length, safeValue.length]);

  useEffect(() => {
    if (status !== "error") return;
    const timer = window.setTimeout(() => onChange(""), reduceMotion ? 0 : 520);
    return () => window.clearTimeout(timer);
  }, [onChange, reduceMotion, status]);

  const commit = (raw: string) => {
    const next = raw.replace(/\D/g, "").slice(0, length);
    onChange(next);
    const nextActive = Math.min(next.length, length - 1);
    setActive(nextActive);
    activeMotion.set(nextActive);
  };

  // Keep a real, named password field so password managers can fill the form.
  // Both native input and React change events replace the complete value.
  const syncInput = (input: HTMLInputElement) => {
    if (disabled || status === "success") return;
    const next = input.value.replace(/\D/g, "").slice(0, length);
    if (next !== safeValue) commit(next);
    if (input.value !== next) input.value = next;
  };

  const syncSelection = () => {
    const next = Math.min(inputRef.current?.selectionStart ?? safeValue.length, length - 1);
    setActive(next);
    activeMotion.set(next);
  };

  const handleRowMouseDown = (event: MouseEvent<HTMLDivElement>) => {
    if (disabled || status === "success") return;
    event.preventDefault();
    const row = rowRef.current;
    if (row) {
      const cell = (event.clientX - row.getBoundingClientRect().left) / (row.getBoundingClientRect().width / length);
      const next = Math.max(0, Math.min(Math.floor(cell), safeValue.length));
      inputRef.current?.focus();
      inputRef.current?.setSelectionRange(next, next);
      setActive(next);
      activeMotion.set(next);
    }
    inputRef.current?.focus();
  };

  const slots = Array.from({ length }, (_, index) => safeValue[index] ?? "");
  const cssVars = {
    "--code-slot-size": `${slotSize}px`,
    "--code-slot-gap": `${gap}px`,
  } as CSSProperties;

  return (
    <div className="code-slots" style={cssVars}>
      <div
        ref={rowRef}
        className="code-slots__row"
        data-status={status}
        data-disabled={disabled ? "" : undefined}
        data-focused={focused ? "" : undefined}
        onMouseDown={handleRowMouseDown}
      >
        <input
          ref={inputRef}
          className="code-slots__input"
          id="auth-password"
          name="password"
          type={mask ? "password" : "text"}
          inputMode="numeric"
          autoComplete={autoComplete}
          pattern={`[0-9]{${length}}`}
          maxLength={length}
          required
          value={safeValue}
          aria-label={ariaLabel}
          aria-invalid={status === "error"}
          disabled={disabled}
          readOnly={status === "success"}
          onInput={(event) => syncInput(event.currentTarget)}
          onChange={(event) => syncInput(event.currentTarget)}
          onSelect={syncSelection}
          onAnimationStart={(event) => {
            if (event.animationName === "code-slots-autofill") syncInput(event.currentTarget);
          }}
          onFocus={(event) => { setFocused(true); syncInput(event.currentTarget); }}
          onBlur={(event) => { setFocused(false); syncInput(event.currentTarget); }}
        />
        {slots.map((digit, index) => (
          <span className="code-slots__slot" data-filled={digit ? "" : undefined} key={index}>
            <motion.span
              className="code-slots__fill"
              initial={false}
              animate={{ scale: digit ? 1 : 0 }}
              transition={reduceMotion ? { duration: 0 } : { type: "spring", duration: 0.3, bounce: 0.2, delay: Math.max(0, index - Math.max(0, safeValue.length - 1)) * 0.018 }}
            />
            {digit && (
              <motion.span
                className="code-slots__digit"
                initial={reduceMotion ? false : { opacity: 0, y: 7 }}
                animate={{ opacity: 1, y: 0 }}
                transition={reduceMotion ? { duration: 0 } : { duration: 0.22, ease: [0.23, 1, 0.32, 1] }}
              >
                {mask ? "•" : digit}
              </motion.span>
            )}
          </span>
        ))}
        <motion.span
          className="code-slots__caret"
          aria-hidden="true"
          style={{ x: caretX }}
          data-visible={focused && !disabled && safeValue.length < length ? "" : undefined}
        >
          <span />
        </motion.span>
        {status === "success" && <span className="code-slots__success"><Check size={18} /></span>}
      </div>
      <span className="code-slots__count" aria-live="polite">{safeValue.length} / {length}</span>
    </div>
  );
}
