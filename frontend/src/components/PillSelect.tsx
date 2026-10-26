import { useEffect, useRef, useState } from "react";
import { Check, ChevronDown } from "lucide-react";

// 工具栏药丸下拉：原生 select 的选项列表由操作系统渲染（直角、无法定制），
// 与药丸形按钮观感冲突，故统一替换为自绘圆角菜单。
interface PillSelectOption<T extends string> {
  id: T;
  label: string;
}

interface PillSelectProps<T extends string> {
  ariaLabel?: string;
  label: string;
  onChange: (value: T) => void;
  options: Array<PillSelectOption<T>>;
  title?: string;
  value: T;
  /** "field"：表单字段样式（全宽带边框，弹窗内使用）；默认药丸样式。 */
  variant?: "pill" | "field";
}

export function PillSelect<T extends string>({
  ariaLabel,
  label,
  onChange,
  options,
  title,
  value,
  variant = "pill",
}: PillSelectProps<T>) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (event: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(event.target as Node)) setOpen(false);
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  const current = options.find((option) => option.id === value)?.label ?? value;

  return (
    <div
      className={`creation-pill-select${variant === "field" ? " creation-pill-select--field" : " creation-toolbar__choice"}${open ? " is-open" : ""}`}
      ref={rootRef}
      title={title}
    >
      <button
        aria-expanded={open}
        aria-haspopup="listbox"
        aria-label={ariaLabel ?? label}
        className="creation-pill-select__trigger"
        onClick={() => setOpen((v) => !v)}
        type="button"
      >
        {variant === "pill" && <span>{label}</span>}
        <strong>{current}</strong>
        <ChevronDown aria-hidden="true" size={14} />
      </button>
      {open && (
        <div className="creation-pill-select__menu" role="listbox">
          {options.map((option) => (
            <button
              aria-selected={option.id === value}
              className={`creation-pill-select__item${option.id === value ? " is-selected" : ""}`}
              key={option.id}
              onClick={() => {
                onChange(option.id);
                setOpen(false);
              }}
              role="option"
              type="button"
            >
              <span>{option.label}</span>
              {option.id === value && <Check aria-hidden="true" size={14} />}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
