// Model switcher — Reasonix-style model selector: a button showing the active
// model with a popover list of providers (brand + id + key status).

import React from "react";
import { Check, ChevronDown } from "lucide-react";
import type { ProviderConfigStatusEntry } from "../contracts/types";

export const ModelSwitcher: React.FC<{
  models: ProviderConfigStatusEntry[];
  value: string;
  onChange: (provider: string) => void;
  disabled?: boolean;
}> = ({ models, value, onChange, disabled = false }) => {
  const [open, setOpen] = React.useState(false);
  const rootRef = React.useRef<HTMLDivElement>(null);

  const current = models.find((item) => item.provider === value) ?? models[0];
  const label = current ? (current.brand ?? current.provider) : "default";

  React.useEffect(() => {
    if (!open) return;
    const onPointerDown = (event: PointerEvent) => {
      if (rootRef.current && !rootRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("pointerdown", onPointerDown);
    return () => document.removeEventListener("pointerdown", onPointerDown);
  }, [open]);

  return (
    <div className="model-switcher" ref={rootRef}>
      <button
        type="button"
        className="model-switcher__trigger"
        disabled={disabled || models.length === 0}
        aria-haspopup="listbox"
        aria-expanded={open}
        onClick={() => setOpen((previous) => !previous)}
      >
        <span className="model-switcher__label">{label}</span>
        <ChevronDown size={13} aria-hidden="true" />
      </button>
      {open && (
        <div className="model-switcher__menu" role="listbox" aria-label="Session model">
          {models.length === 0 && (
            <div className="model-switcher__empty">No providers configured</div>
          )}
          {models.map((item) => {
            const active = item.provider === value;
            const keyState = item.requires_api_key
              ? item.has_api_key
                ? `key ${item.key_fingerprint ?? ""}`
                : "key missing"
              : "no key needed";
            return (
              <button
                key={item.provider}
                type="button"
                role="option"
                aria-selected={active}
                className={`model-switcher__item${active ? " model-switcher__item--active" : ""}`}
                onClick={() => {
                  onChange(item.provider);
                  setOpen(false);
                }}
              >
                <span className="model-switcher__item-main">
                  <span className="model-switcher__item-name">{item.brand ?? item.provider}</span>
                  <span className="model-switcher__item-id">{item.provider}</span>
                  <span className={`model-switcher__item-key${item.requires_api_key && !item.has_api_key ? " model-switcher__item-key--missing" : ""}`}>
                    {keyState}
                  </span>
                </span>
                {active && <Check size={14} aria-hidden="true" className="model-switcher__check" />}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
};
