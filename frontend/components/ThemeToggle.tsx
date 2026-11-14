"use client";

import { useEffect, useState } from "react";

export function ThemeToggle() {
  const [dark, setDark] = useState(true);
  useEffect(() => {
    setDark(!document.documentElement.classList.contains("light-off") && document.documentElement.classList.contains("dark"));
  }, []);
  function toggle() {
    const next = !dark;
    setDark(next);
    document.documentElement.classList.toggle("dark", next);
    try {
      localStorage.setItem("finn-theme", next ? "dark" : "light");
    } catch {}
  }
  return (
    <button
      onClick={toggle}
      aria-label="Toggle theme"
      className="chip flex items-center gap-1.5"
    >
      {dark ? "☾" : "☀"}
    </button>
  );
}
