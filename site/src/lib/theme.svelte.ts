export type Theme = 'light' | 'dark';

const KEY = 'soarshelf-theme';

function stored(): Theme | null {
  try {
    const v = localStorage.getItem(KEY);
    return v === 'light' || v === 'dark' ? v : null;
  } catch {
    return null;
  }
}

function system(): Theme {
  return typeof matchMedia !== 'undefined' && matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

class ThemeState {
  current = $state<Theme>('light');

  init() {
    this.current = (document.documentElement.dataset.theme as Theme) || stored() || system();
    matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
      if (!stored()) this.apply(system(), false);
    });
  }

  toggle() {
    this.apply(this.current === 'dark' ? 'light' : 'dark', true);
  }

  private apply(t: Theme, persist: boolean) {
    this.current = t;
    document.documentElement.dataset.theme = t;
    if (persist) {
      try {
        localStorage.setItem(KEY, t);
      } catch {
        /* storage unavailable: theme still applies for this page view */
      }
    }
  }
}

export const theme = new ThemeState();
