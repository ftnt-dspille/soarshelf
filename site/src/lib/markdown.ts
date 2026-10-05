import { Marked, type Tokens } from 'marked';
import DOMPurify from 'dompurify';

const SAFE_HREF = /^(https?:|mailto:|#|\/(?!\/))/i;

function escapeHtml(s: string): string {
  return s.replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]!);
}

// Raw HTML in contributor markdown is never rendered (it is shown as text), and links
// are limited to http(s)/mailto/relative. This holds during prerender, where DOMPurify
// has no DOM; in the browser DOMPurify runs on top as a second layer.
const md = new Marked({
  gfm: true,
  breaks: false,
  renderer: {
    html({ text }: Tokens.HTML | Tokens.Tag) {
      return escapeHtml(text);
    },
    link({ href, title, tokens }: Tokens.Link) {
      const text = this.parser.parseInline(tokens);
      if (!SAFE_HREF.test(href)) return text;
      const ext = /^https?:/i.test(href);
      const t = title ? ` title="${escapeHtml(title)}"` : '';
      return `<a href="${escapeHtml(href)}"${t}${ext ? ' rel="nofollow noopener noreferrer" target="_blank"' : ''}>${text}</a>`;
    },
    image({ text }: Tokens.Image) {
      // No remote images from contributors: avoids tracking pixels and hot-linked content.
      return escapeHtml(text);
    }
  }
});

export function renderMarkdown(src: string): string {
  const html = md.parse(src ?? '', { async: false }) as string;
  if (typeof window !== 'undefined' && DOMPurify.isSupported) {
    return DOMPurify.sanitize(html, { ADD_ATTR: ['target'] });
  }
  return html;
}
