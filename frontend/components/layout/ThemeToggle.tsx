"use client";

import { useEffect, useState } from "react";

export type AppTheme = "dark" | "light";

const STORAGE_KEY = "autoplay-theme";

function readStoredTheme(): AppTheme {
  if (typeof window === "undefined") return "dark";
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (stored === "light" || stored === "dark") return stored;
  } catch {
    /* ignore */
  }
  return "dark";
}

function applyTheme(theme: AppTheme) {
  document.documentElement.setAttribute("data-theme", theme);
  document.documentElement.style.colorScheme = theme;
}

export function ThemeToggle() {
  const [theme, setTheme] = useState<AppTheme>("dark");
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const initial = readStoredTheme();
    setTheme(initial);
    applyTheme(initial);
    setReady(true);
  }, []);

  function toggle() {
    const next: AppTheme = theme === "dark" ? "light" : "dark";
    setTheme(next);
    applyTheme(next);
    try {
      window.localStorage.setItem(STORAGE_KEY, next);
    } catch {
      /* ignore */
    }
  }

  const isLight = theme === "light";

  return (
    <button
      type="button"
      className="themeToggle"
      onClick={toggle}
      aria-pressed={isLight}
      aria-label={isLight ? "Nachtmodus aktivieren" : "Tagmodus aktivieren"}
      title={isLight ? "Nachtmodus" : "Tagmodus"}
      disabled={!ready}
    >
      <span className="themeToggleIcon" aria-hidden="true">
        {isLight ? (
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75">
            <path d="M21 14.5A8.5 8.5 0 1 1 9.5 3 7 7 0 0 0 21 14.5Z" />
          </svg>
        ) : (
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75">
            <circle cx="12" cy="12" r="4" />
            <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
          </svg>
        )}
      </span>
      <span className="themeToggleLabel">{isLight ? "Nacht" : "Tag"}</span>
    </button>
  );
}
