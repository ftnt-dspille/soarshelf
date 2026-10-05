// Who is signed in. Loaded once in the browser; prerendered HTML always shows
// the signed-out state, then the header updates after hydration.
import { getMe, logout, type Me } from './api';

class Session {
  me = $state<Me | null>(null);
  loaded = $state(false);
  #pending: Promise<Me | null> | null = null;

  load(force = false): Promise<Me | null> {
    if (!force && this.#pending) return this.#pending;
    this.#pending = getMe().then((m) => {
      this.me = m;
      this.loaded = true;
      return m;
    });
    return this.#pending;
  }

  async signOut() {
    await logout();
    this.me = null;
  }
}

export const session = new Session();
