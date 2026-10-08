import { useContext } from "react";
import { ThemeContext, type ThemeContextValue } from "../context/themeContext";

/** Access the active colour theme and the control to toggle it. */
export function useTheme(): ThemeContextValue {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error("useTheme must be used within a ThemeProvider");
  }
  return context;
}