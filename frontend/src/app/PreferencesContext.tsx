import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import {
  clearPreferences,
  DEFAULT_PREFERENCES,
  readPreferences,
  writePreferences,
  type FrontendPreferences,
} from '../storage/preferencesStorage';

interface PreferencesContextValue {
  readonly preferences: FrontendPreferences;
  readonly persistenceAvailable: boolean;
  update(patch: Partial<FrontendPreferences>): void;
  reset(): void;
}

const PreferencesContext = createContext<PreferencesContextValue | null>(null);

export function PreferencesProvider({ children }: { readonly children: ReactNode }) {
  const [preferences, setPreferences] = useState(readPreferences);
  const [persistenceAvailable, setPersistenceAvailable] = useState(true);

  const update = useCallback((patch: Partial<FrontendPreferences>) => {
    const next = { ...preferences, ...patch };
    setPreferences(next);
    setPersistenceAvailable(writePreferences(next));
  }, [preferences]);

  const reset = useCallback(() => {
    setPersistenceAvailable(clearPreferences());
    setPreferences(DEFAULT_PREFERENCES);
  }, []);

  useEffect(() => {
    const root = document.documentElement;
    root.dataset.theme = preferences.theme;
    root.dataset.density = preferences.density;
    root.dataset.motion = preferences.motion;
    root.dataset.timeFormat = preferences.timeFormat;
    return () => {
      delete root.dataset.theme;
      delete root.dataset.density;
      delete root.dataset.motion;
      delete root.dataset.timeFormat;
    };
  }, [preferences.density, preferences.motion, preferences.theme, preferences.timeFormat]);

  const value = useMemo(() => ({ preferences, persistenceAvailable, update, reset }), [persistenceAvailable, preferences, reset, update]);
  return <PreferencesContext value={value}>{children}</PreferencesContext>;
}

export function usePreferences(): PreferencesContextValue {
  const value = useContext(PreferencesContext);
  if (value === null) throw new Error('usePreferences must be used inside PreferencesProvider.');
  return value;
}
