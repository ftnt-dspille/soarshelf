export type Theme = 'light' | 'dark';
/** Colour palette, independent of light/dark. 'docs' matches the FortiSOAR API docs. */
export type Palette = 'default' | 'docs';

const KEY = 'soarshelf-theme';
const PALETTE_KEY = 'soarshelf-palette';

function read(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function write(key: string, value: string | null) {
  try {
    if (value === null) localStorage.removeItem(key);
    else localStorage.setItem(key, value);
  } catch {
    /* storage unavailable: the choice still applies for this page view */
  }
}

function stored(): Theme | null {
  const v = read(KEY);
  return v === 'light' || v === 'dark' ? v : null;
}

function system(): Theme {
  return typeof matchMedia !== 'undefined' && matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

class ThemeState {
  current = $state<Theme>('light');
  palette = $state<Palette>('default');

  init() {
    this.current = (document.documentElement.dataset.theme as Theme) || stored() || system();
    this.palette = document.documentElement.dataset.palette === 'docs' ? 'docs' : 'default';
    matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
      if (!stored()) this.apply(system(), false);
    });
  }

  toggle() {
    this.apply(this.current === 'dark' ? 'light' : 'dark', true);
  }

  set(t: Theme) {
    this.apply(t, true);
  }

  setPalette(p: Palette) {
    this.palette = p;
    if (p === 'default') delete document.documentElement.dataset.palette;
    else document.documentElement.dataset.palette = p;
    write(PALETTE_KEY, p === 'default' ? null : p);
  }

  private apply(t: Theme, persist: boolean) {
    this.current = t;
    document.documentElement.dataset.theme = t;
    if (persist) write(KEY, t);
  }
}

export const theme = new ThemeState();
