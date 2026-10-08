/**
 * The theme context object and its types, kept separate from the provider.
 *
 * Split out for the same reason as `authContext.ts`: the provider module
 * exports only a component, so React Fast Refresh keeps working during
 * development, and `hooks/useTheme.ts` can reach the context without
 * importing the provider.
 */

import { createContext } from "react";

export type Theme = "light" | "dark";

export interface ThemeContextValue {
  theme: Theme;
  toggleTheme: () => void;
}

export const ThemeContext = createContext<ThemeContextValue | undefined>(
  undefined,
);