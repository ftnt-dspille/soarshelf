/* Copyright start
   MIT License
   Copyright (c) 2026 Dylan Spille
   Copyright end */
"use strict";
(function () {
  const ns = (window.JinjaEditorWidget = window.JinjaEditorWidget || {});

  // Toggle verbose at runtime: localStorage.jinjaDebug = "1" then reload.
  const DEBUG =
    (typeof localStorage !== "undefined" &&
      localStorage.getItem("jinjaDebug") === "1") ||
    window.__JINJA_MONACO_DEBUG === true;
  function warn() {
    const args = Array.prototype.slice.call(arguments);
    args.unshift("[JinjaMonaco]");
    console.warn.apply(console, args);
  }

  // Shared parsed-JSON context used by the member-access completion provider.
  // The view controller pushes the Input pane's JSON in here on every change;
  // the provider reads from it when the user types `.` or `[` after a path.
  let currentInputContext = null;

  ns.monaco = {
    ensure: ensure,
    enhanceEditor: enhanceEditor,
    setInputContext: setInputContext,
  };

  // We never call `monaco.editor.create` ourselves — SOAR's `monacoEditor`
  // directive does that. All we need from Monaco is the global; SOAR
  // preloads it during app bootstrap (app.unmin.js initMonacoEditorService).
  // The dev harness preloads Monaco in dev/public/index.html before the
  // widget controller runs. A short poll covers the race between the
  // widget's mount and SOAR's preload completing.
  function ensure() {
    if (!window.__jinjaMonacoEnsurePromise) {
      window.__jinjaMonacoEnsurePromise = waitForExistingMonaco(500).then(
        (monaco) => {
          if (!monaco) {
            window.__jinjaMonacoEnsurePromise = null;
            throw new Error(
              "window.monaco is not available; host must preload Monaco"
            );
          }
          setupLanguage(monaco);
          disableJsonLanguageWorker(monaco);
          return monaco;
        }
      );
    } else {
      // Re-run language setup on cached resolution so a reinstalled widget's
      // updated definition replaces the previous registrations. setupLanguage
      // tracks disposables and tears down on re-entry, so this is idempotent.
      return window.__jinjaMonacoEnsurePromise.then((monaco) => {
        setupLanguage(monaco);
        disableJsonLanguageWorker(monaco);
        return monaco;
      });
    }
    return window.__jinjaMonacoEnsurePromise;
  }

  function waitForExistingMonaco(timeoutMs) {
    return new Promise((resolve) => {
      if (window.monaco) return resolve(window.monaco);
      const started = Date.now();
      const handle = setInterval(() => {
        if (window.monaco) {
          clearInterval(handle);
          resolve(window.monaco);
        } else if (Date.now() - started >= timeoutMs) {
          clearInterval(handle);
          resolve(null);
        }
      }, 50);
    });
  }

  function setInputContext(ctx) {
    currentInputContext =
      ctx && typeof ctx === "object" && !Array.isArray(ctx) ? ctx : null;
  }


  function setupLanguage(monaco) {
    // Tear down any registrations from a previous widget version so the
    // current ns.languageDefinition fully replaces them. Without this,
    // setMonarchTokensProvider / setLanguageConfiguration still replace,
    // but the completion/hover/signature providers stack and the older
    // language config sometimes lingers in Monaco's internal state.
    const prev = window.__jinjaMonacoRegistrations || [];
    for (const d of prev) {
      try {
        d && typeof d.dispose === "function" && d.dispose();
      } catch (_) {
        // best-effort teardown; a disposed provider throwing shouldn't
        // block re-registration.
      }
    }
    const disposables = (window.__jinjaMonacoRegistrations = []);
    const track = (d) => {
      if (d && typeof d.dispose === "function") disposables.push(d);
      return d;
    };
    warn("setupLanguage: (re)registering jinja language", {
      previousDisposables: prev.length,
      hasLanguageDef: !!ns.languageDefinition,
      languageId: ns.languageDefinition && ns.languageDefinition.id,
      hasFilterSignatures: !!ns.filterSignatures,
      filterCount: ns.filterSignatures ? Object.keys(ns.filterSignatures).length : 0,
      hasSnippets: !!ns.snippets,
      snippetCount: Array.isArray(ns.snippets) ? ns.snippets.length : 0,
    });

    const languageDef = ns.languageDefinition;
    const filterSignatures = ns.filterSignatures;
    const snippets = ns.snippets;

    if (!languageDef) {
      warn("setupLanguage: ABORT — ns.languageDefinition is missing; jinja language will not be registered");
      return;
    }

    monaco.languages.register({ id: languageDef.id });
    warn("setupLanguage: language registered", { id: languageDef.id });
    track(
      monaco.languages.setMonarchTokensProvider(languageDef.id, {
        tokenizer: languageDef.tokenizer,
      })
    );
    warn("setupLanguage: tokenizer set");
    if (languageDef.configuration) {
      track(
        monaco.languages.setLanguageConfiguration(
          languageDef.id,
          languageDef.configuration
        )
      );
      warn("setupLanguage: language configuration set");
    }
    monaco.editor.defineTheme(languageDef.theme.name, {
      base: languageDef.theme.base,
      inherit: languageDef.theme.inherit,
      rules: languageDef.theme.rules,
      colors: languageDef.theme.colors,
    });
    if (languageDef.themeLight) {
      monaco.editor.defineTheme(languageDef.themeLight.name, {
        base: languageDef.themeLight.base,
        inherit: languageDef.themeLight.inherit,
        rules: languageDef.themeLight.rules,
        colors: languageDef.themeLight.colors,
      });
    }
    warn("setupLanguage: theme defined", { themeName: languageDef.theme.name, themeLightName: languageDef.themeLight && languageDef.themeLight.name });

    track(registerSnippetProvider(monaco, languageDef, snippets));
    track(
      registerFilterCompletionProvider(monaco, languageDef, filterSignatures)
    );
    track(registerVariableCompletionProvider(monaco, languageDef));
    track(registerMemberCompletionProvider(monaco, languageDef));
    track(registerHoverProvider(monaco, languageDef, filterSignatures));
    track(
      registerSignatureHelpProvider(monaco, languageDef, filterSignatures)
    );
    warn("setupLanguage: all providers registered", {
      totalDisposables: disposables.length,
    });
  }

  // Monaco's json language spins up a web worker for validation, formatting,
  // and schema-driven IntelliSense. On SOAR its importScripts calls trip the
  // broken `default-src self` (missing quotes) CSP — the editor still works
  // but the console fills with CSP warnings. We only use the json editor as
  // a scratchpad for input JSON, and our own Format button handles pretty-
  // printing via JSON.parse/stringify, so we turn the worker-backed
  // features off. `tokens: true` keeps syntax highlighting, which runs on
  // the main thread.
  function disableJsonLanguageWorker(monaco) {
    const configure = () => {
      warn("disableJsonLanguageWorker: configure() invoked", {
        jsonLangPresent: !!monaco.languages.json,
        jsonDefaultsPresent: !!(monaco.languages.json && monaco.languages.json.jsonDefaults),
        hasSetModeConfiguration: !!(
          monaco.languages.json &&
          monaco.languages.json.jsonDefaults &&
          typeof monaco.languages.json.jsonDefaults.setModeConfiguration === "function"
        ),
        hasSetDiagnosticsOptions: !!(
          monaco.languages.json &&
          monaco.languages.json.jsonDefaults &&
          typeof monaco.languages.json.jsonDefaults.setDiagnosticsOptions === "function"
        ),
      });
      const defaults =
        monaco.languages.json && monaco.languages.json.jsonDefaults;
      if (!defaults) {
        warn("disableJsonLanguageWorker: jsonDefaults absent — json language module may not be loaded");
        return;
      }
      if (typeof defaults.setModeConfiguration === "function") {
        defaults.setModeConfiguration({
          documentFormattingEdits: false,
          documentRangeFormattingEdits: false,
          completionItems: false,
          hovers: false,
          documentSymbols: false,
          tokens: true,
          colors: false,
          foldingRanges: false,
          diagnostics: false,
          selectionRanges: false,
        });
        warn("disableJsonLanguageWorker: setModeConfiguration applied (tokens:true, all else off)");
      } else {
        warn("disableJsonLanguageWorker: setModeConfiguration not available on this Monaco version — skipping");
      }
      if (typeof defaults.setDiagnosticsOptions === "function") {
        defaults.setDiagnosticsOptions({
          validate: false,
          allowComments: true,
          schemas: [],
          enableSchemaRequest: false,
        });
        warn("disableJsonLanguageWorker: setDiagnosticsOptions applied (validate:false)");
      } else {
        warn("disableJsonLanguageWorker: setDiagnosticsOptions not available on this Monaco version — skipping");
      }
    };
    // json language is lazy-loaded; configure now if it's already loaded,
    // otherwise wait for its onLanguage event (fires when the first json editor is created).
    warn("disableJsonLanguageWorker: registering json worker suppression", {
      jsonAlreadyLoaded: !!monaco.languages.json,
      hasOnLanguage: typeof monaco.languages.onLanguage === "function",
    });
    if (monaco.languages.json) {
      configure();
    } else if (typeof monaco.languages.onLanguage === "function") {
      monaco.languages.onLanguage("json", configure);
      warn("disableJsonLanguageWorker: onLanguage('json') callback registered — will fire when first json editor is created");
    } else {
      warn("disableJsonLanguageWorker: neither json nor onLanguage available — worker suppression skipped");
    }
  }

  function rangeAt(position, word) {
    return {
      startLineNumber: position.lineNumber,
      endLineNumber: position.lineNumber,
      startColumn: word.startColumn,
      endColumn: word.endColumn,
    };
  }

  function registerSnippetProvider(monaco, languageDef, snippets) {
    return monaco.languages.registerCompletionItemProvider(languageDef.id, {
      provideCompletionItems: (model, position) => {
        const word = model.getWordUntilPosition(position);
        const range = rangeAt(position, word);
        return {
          suggestions: snippets.map((s) => ({
            label: s.label,
            kind: monaco.languages.CompletionItemKind.Snippet,
            insertText: s.insertText,
            detail: s.detail,
            documentation: s.detail,
            insertTextRules: s.asSnippet
              ? monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet
              : undefined,
            range: range,
          })),
        };
      },
    });
  }

  function buildFilterCompletionItem(monaco, key, signature, range) {
    const paramString = signature.parameters
      .map((p) => `${p.name}: ${p.type}`)
      .join(", ");
    const signatureString = `${key}(${paramString}) → ${signature.returnValue.type}`;
    return {
      label: key,
      kind: monaco.languages.CompletionItemKind.Function,
      documentation: {
        value: [
          "```jinja2",
          signatureString,
          "```",
          signature.documentation,
          "",
          "Parameters:",
          ...signature.parameters.map(
            (p) => `- ${p.name} (${p.type}): ${p.description}`
          ),
          "",
          "Returns:",
          `${signature.returnValue.type}: ${signature.returnValue.description}`,
        ].join("\n"),
      },
      detail: signature.documentation,
      insertText: signature.parameters.length > 0 ? `${key}($0)` : `${key} `,
      insertTextRules:
        monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet,
      range: range,
      command:
        signature.parameters.length > 0
          ? {
              id: "editor.action.triggerParameterHints",
              title: "Trigger Parameter Hints",
            }
          : undefined,
    };
  }

  function registerFilterCompletionProvider(monaco, languageDef, filterSignatures) {
    return monaco.languages.registerCompletionItemProvider(languageDef.id, {
      triggerCharacters: ["|", " "],
      provideCompletionItems: (model, position) => {
        const linePrefix = model
          .getLineContent(position.lineNumber)
          .substring(0, position.column - 1);
        if (!/\|\s*$/.test(linePrefix)) return { suggestions: [] };
        const word = model.getWordUntilPosition(position);
        const range = rangeAt(position, word);
        const suggestions = Object.entries(filterSignatures).map(
          ([key, signature]) =>
            buildFilterCompletionItem(monaco, key, signature, range)
        );
        return { suggestions: suggestions };
      },
    });
  }

  // Suggest common Jinja keywords and the `vars.input.records[0]` root inside
  // `{% %}` and `{{ }}` regions.
  function registerVariableCompletionProvider(monaco, languageDef) {
    const keywords = [
      "if", "elif", "else", "endif",
      "for", "in", "endfor",
      "set", "block", "endblock",
      "macro", "endmacro", "include", "extends",
      "with", "endwith", "filter", "endfilter",
      "raw", "endraw", "and", "or", "not", "is",
    ];
    const rootSuggestions = [
      { text: "vars", detail: "Top-level Jinja context" },
      { text: "vars.input", detail: "Widget input payload" },
      { text: "vars.input.records", detail: "Input record list" },
      { text: "vars.input.records[0]", detail: "First input record" },
      { text: "vars.steps", detail: "Previous playbook step outputs" },
      { text: "loop", detail: "Current loop context (index, first, last, …)" },
      { text: "loop.index", detail: "1-based loop index" },
      { text: "loop.index0", detail: "0-based loop index" },
      { text: "loop.first", detail: "True on the first iteration" },
      { text: "loop.last", detail: "True on the last iteration" },
    ];

    return monaco.languages.registerCompletionItemProvider(languageDef.id, {
      triggerCharacters: [" ", "{"],
      provideCompletionItems: (model, position) => {
        const lineUpTo = model
          .getLineContent(position.lineNumber)
          .substring(0, position.column - 1);
        const fullUpTo = model.getValueInRange({
          startLineNumber: 1,
          startColumn: 1,
          endLineNumber: position.lineNumber,
          endColumn: position.column,
        });
        // Only fire when the cursor is inside an open {{ … }} or {% … %} that
        // has not yet been closed.
        const insideExpr = hasOpenDelimiter(fullUpTo, "{{", "}}");
        const insideTag = hasOpenDelimiter(fullUpTo, "{%", "%}");
        if (!insideExpr && !insideTag) return { suggestions: [] };
        // Suppress if we're in the middle of a filter (| foo) — the filter
        // provider already handles that.
        if (/\|\s*[\w]*$/.test(lineUpTo)) return { suggestions: [] };

        const word = model.getWordUntilPosition(position);
        const range = rangeAt(position, word);
        const suggestions = [];
        rootSuggestions.forEach((s) => {
          suggestions.push({
            label: s.text,
            kind: monaco.languages.CompletionItemKind.Variable,
            insertText: s.text,
            detail: s.detail,
            range: range,
          });
        });
        if (insideTag) {
          keywords.forEach((kw) => {
            suggestions.push({
              label: kw,
              kind: monaco.languages.CompletionItemKind.Keyword,
              insertText: kw,
              range: range,
            });
          });
        }
        return { suggestions: suggestions };
      },
    });
  }

  // Offer completions for `foo.bar.<cursor>` and `foo['bar'][<cursor>` by
  // walking the user-provided input JSON. Fires on `.` and `[` triggers and
  // also while the user is typing a partial identifier after a dot.
  function registerMemberCompletionProvider(monaco, languageDef) {
    return monaco.languages.registerCompletionItemProvider(languageDef.id, {
      triggerCharacters: [".", "["],
      provideCompletionItems: (model, position) => {
        if (!currentInputContext) return { suggestions: [] };

        const fullUpTo = model.getValueInRange({
          startLineNumber: 1,
          startColumn: 1,
          endLineNumber: position.lineNumber,
          endColumn: position.column,
        });
        if (
          !hasOpenDelimiter(fullUpTo, "{{", "}}") &&
          !hasOpenDelimiter(fullUpTo, "{%", "%}")
        ) {
          return { suggestions: [] };
        }

        const lineUpTo = model
          .getLineContent(position.lineNumber)
          .substring(0, position.column - 1);
        const parsed = parseAccessorPath(lineUpTo);
        if (!parsed) return { suggestions: [] };

        const target = navigateObject(currentInputContext, parsed.tokens);
        if (target === undefined || target === null) {
          return { suggestions: [] };
        }

        const word = model.getWordUntilPosition(position);
        const range = rangeAt(position, word);
        return {
          suggestions: buildMemberSuggestions(
            monaco,
            target,
            parsed.separator,
            parsed.partial,
            range
          ),
        };
      },
    });
  }

  // Pulls the trailing member-access chain from the current line:
  //   "{{ vars.input.records[0].na"  →  tokens=[vars,input,records,[0]], separator=".", partial="na"
  //   "{{ vars.input.records["       →  tokens=[vars,input,records],      separator="[", partial=""
  //   "{{ vars.input."               →  tokens=[vars,input],              separator=".", partial=""
  // Returns null when the cursor is not at a member-access position.
  function parseAccessorPath(line) {
    const re =
      /((?:[A-Za-z_$][A-Za-z0-9_$]*)(?:\.[A-Za-z_$][A-Za-z0-9_$]*|\[(?:\d+|'[^']*'|"[^"]*")\])*)(\.|\[)([A-Za-z_$][A-Za-z0-9_$]*)?$/;
    const m = line.match(re);
    if (!m) return null;
    const chain = m[1];
    const separator = m[2];
    const partial = m[3] || "";

    const tokens = [];
    const tokRe =
      /([A-Za-z_$][A-Za-z0-9_$]*)|\[(\d+)\]|\['([^']*)'\]|\["([^"]*)"\]/g;
    let tm;
    while ((tm = tokRe.exec(chain)) !== null) {
      if (tm[1] !== undefined) tokens.push({ type: "key", value: tm[1] });
      else if (tm[2] !== undefined)
        tokens.push({ type: "index", value: parseInt(tm[2], 10) });
      else if (tm[3] !== undefined) tokens.push({ type: "key", value: tm[3] });
      else if (tm[4] !== undefined) tokens.push({ type: "key", value: tm[4] });
    }
    if (tokens.length === 0) return null;
    return { tokens: tokens, separator: separator, partial: partial };
  }

  function navigateObject(ctx, tokens) {
    let cur = ctx;
    for (const tok of tokens) {
      if (cur === null || cur === undefined) return undefined;
      if (tok.type === "key") {
        if (typeof cur !== "object" || Array.isArray(cur)) return undefined;
        cur = cur[tok.value];
      } else if (tok.type === "index") {
        if (!Array.isArray(cur)) return undefined;
        cur = cur[tok.value];
      }
    }
    return cur;
  }

  function buildMemberSuggestions(monaco, target, separator, partial, range) {
    const out = [];
    if (target === null || target === undefined) return out;

    if (Array.isArray(target)) {
      if (separator === "[") {
        const cap = Math.min(target.length, 50);
        for (let i = 0; i < cap; i++) {
          out.push({
            label: String(i),
            kind: monaco.languages.CompletionItemKind.Value,
            insertText: String(i),
            detail: describeValue(target[i]),
            sortText: String(i).padStart(6, "0"),
            range: range,
          });
        }
        // If the array holds objects, peek at the first element's keys so
        // the user can see what's available even before picking an index.
        if (target.length > 0 && isPlainObject(target[0])) {
          Object.keys(target[0]).forEach((key) => {
            out.push({
              label: "'" + key + "'",
              kind: monaco.languages.CompletionItemKind.Field,
              insertText: "'" + escapeSingleQuotes(key) + "'",
              detail:
                "first-element key — " + describeValue(target[0][key]),
              sortText: "zz_" + key,
              range: range,
            });
          });
        }
      }
      return out;
    }

    if (!isPlainObject(target)) return out;

    const keys = Object.keys(target);
    const partialLower = partial.toLowerCase();
    keys.forEach((key) => {
      if (partialLower && !key.toLowerCase().startsWith(partialLower)) return;
      const value = target[key];
      if (separator === ".") {
        if (!/^[A-Za-z_$][A-Za-z0-9_$]*$/.test(key)) return;
        out.push({
          label: key,
          kind: memberKind(monaco, value),
          insertText: key,
          detail: describeValue(value),
          range: range,
        });
      } else if (separator === "[") {
        out.push({
          label: "'" + key + "'",
          kind: memberKind(monaco, value),
          insertText: "'" + escapeSingleQuotes(key) + "'",
          detail: describeValue(value),
          range: range,
        });
      }
    });
    return out;
  }

  function memberKind(monaco, value) {
    if (Array.isArray(value)) {
      return monaco.languages.CompletionItemKind.Variable;
    }
    if (isPlainObject(value)) {
      return monaco.languages.CompletionItemKind.Module;
    }
    return monaco.languages.CompletionItemKind.Field;
  }

  function isPlainObject(v) {
    return v !== null && typeof v === "object" && !Array.isArray(v);
  }

  function escapeSingleQuotes(s) {
    return String(s).replace(/\\/g, "\\\\").replace(/'/g, "\\'");
  }

  function describeValue(v) {
    if (v === null) return "null";
    if (v === undefined) return "undefined";
    if (Array.isArray(v)) return "array (" + v.length + ")";
    if (typeof v === "object") {
      return "object (" + Object.keys(v).length + " keys)";
    }
    if (typeof v === "string") {
      const preview = v.length > 40 ? v.slice(0, 37) + "…" : v;
      return 'string "' + preview + '"';
    }
    return typeof v + ": " + v;
  }

  function hasOpenDelimiter(text, open, close) {
    const lastOpen = text.lastIndexOf(open);
    if (lastOpen === -1) return false;
    const lastClose = text.lastIndexOf(close);
    return lastClose < lastOpen;
  }

  function registerHoverProvider(monaco, languageDef, filterSignatures) {
    return monaco.languages.registerHoverProvider(languageDef.id, {
      provideHover: (model, position) => {
        const word = model.getWordAtPosition(position);
        if (!word) return null;
        const signature = filterSignatures[word.word];
        if (!signature) return null;
        const contents = [
          { value: `**Function:** \`${word.word}\`` },
          { value: `**Documentation:** ${signature.documentation}` },
          { value: `**Parameters:**` },
        ];
        signature.parameters.forEach((p) => {
          contents.push({
            value: `- **${p.name}** (*${p.type}*): ${p.description}`,
          });
        });
        contents.push({
          value: `**Returns:** \`${signature.returnValue.type}\`: ${signature.returnValue.description}`,
        });
        return {
          contents: contents,
          range: new monaco.Range(
            position.lineNumber,
            word.startColumn,
            position.lineNumber,
            word.endColumn
          ),
        };
      },
    });
  }

  function registerSignatureHelpProvider(monaco, languageDef, filterSignatures) {
    return monaco.languages.registerSignatureHelpProvider(languageDef.id, {
      signatureHelpTriggerCharacters: ["(", ","],
      provideSignatureHelp: (model, position) => {
        const textUntilPosition = model.getValueInRange({
          startLineNumber: 1,
          startColumn: 1,
          endLineNumber: position.lineNumber,
          endColumn: position.column,
        });
        const match = textUntilPosition.match(
          /([a-zA-Z0-9_]+)\s*\(([^)]*)$/
        );
        if (!match) return null;
        const [, functionName, paramsString] = match;
        const signature = filterSignatures[functionName];
        if (!signature) return null;
        const activeParameter = paramsString.split(",").length - 1;
        const signatureInfo = {
          label: `${functionName}(${signature.parameters
            .map((p) => `${p.name}: ${p.type}`)
            .join(", ")}) → ${signature.returnValue.type}`,
          documentation: signature.documentation,
          parameters: signature.parameters.map((p) => ({
            label: `${p.name}: ${p.type}`,
            documentation: p.description,
          })),
        };
        return {
          value: {
            signatures: [signatureInfo],
            activeSignature: 0,
            activeParameter: activeParameter,
          },
          dispose: () => {},
        };
      },
    });
  }

  // Wire per-editor behaviors that can't be expressed declaratively:
  //   - Auto-close the multi-character Jinja delimiters {{ }}, {% %}, {# #}.
  //   - After typing an opening block tag like `{% if x %}`, offer to insert
  //     the matching `{% endif %}` on the next line (Tab accepts).
  function enhanceEditor(editor) {
    if (!editor || editor.__jinjaEnhanced) return;
    editor.__jinjaEnhanced = true;

    const monaco = window.monaco;
    const blockTagPairs = ns.blockTagPairs || {};
    let suppressNext = false;

    const typeDisposable = editor.onDidType((ch) => {
      if (suppressNext) {
        suppressNext = false;
        return;
      }
      if (ch !== "{" && ch !== "%" && ch !== "#") return;

      const model = editor.getModel();
      if (!model || model.getLanguageId() !== "jinja") return;

      const position = editor.getPosition();
      const line = model.getLineContent(position.lineNumber);
      const col = position.column; // 1-based, points *after* the typed char
      const justTyped = line.substring(col - 3, col - 1); // two chars ending at the typed char

      let pair = null;
      if (justTyped === "{{") pair = { opener: "{{", closer: "}}" };
      else if (justTyped === "{%") pair = { opener: "{%", closer: "%}" };
      else if (justTyped === "{#") pair = { opener: "{#", closer: "#}" };
      if (!pair) return;

      // Skip if the closer is already present immediately after the cursor —
      // avoids doubling up when pasting or when the user types inside an
      // existing pair.
      const after = line.substring(col - 1, col - 1 + pair.closer.length);
      if (after === pair.closer) return;
      // Skip inside a comment block — {{ inside {# … #} should stay literal.
      // Don't apply this guard to {# itself: the comment was just opened by
      // the chars being typed, so insideComment would fire as a false positive.
      if (pair.opener !== "{#" && insideComment(model, position)) return;

      // Insert "  <closer>" — two spaces for readable padding, cursor between.
      const insert = "  " + pair.closer;
      suppressNext = true;
      editor.executeEdits("jinja-autoclose", [
        {
          range: new monaco.Range(
            position.lineNumber,
            position.column,
            position.lineNumber,
            position.column
          ),
          text: insert,
          forceMoveMarkers: true,
        },
      ]);
      editor.setPosition({
        lineNumber: position.lineNumber,
        column: position.column + 1, // land between the two padding spaces
      });
    });

    // After the user finishes a block-opening tag like `{% if cond %}` offer
    // the matching closer as a one-shot snippet on the next line.
    const blockCloseDisposable = editor.onDidType((ch) => {
      if (ch !== "}") return;
      const model = editor.getModel();
      if (!model || model.getLanguageId() !== "jinja") return;

      const position = editor.getPosition();
      const line = model.getLineContent(position.lineNumber);
      const upToCursor = line.substring(0, position.column - 1);
      if (!upToCursor.endsWith("%}")) return;

      // Match the tag name from the most recent `{% ... %}` on this line.
      const tagMatch = upToCursor.match(/\{%-?\s*(\w+)\b[^%]*-?%\}\s*$/);
      if (!tagMatch) return;
      const tagName = tagMatch[1];
      const closer = blockTagPairs[tagName];
      if (!closer) return;

      // Skip if the closer already exists somewhere after the cursor.
      const remaining = model.getValueInRange({
        startLineNumber: position.lineNumber,
        startColumn: position.column,
        endLineNumber: model.getLineCount(),
        endColumn: model.getLineMaxColumn(model.getLineCount()),
      });
      if (new RegExp("\\{%-?\\s*" + closer + "\\b").test(remaining)) return;

      // Insert "\n\t$0\n{% endX %}" as a snippet so the cursor lands on an
      // indented empty line between the tags.
      const contribution = editor.getContribution("snippetController2");
      if (!contribution || typeof contribution.insert !== "function") return;
      contribution.insert("\n\t$0\n{% " + closer + " %}");
    });

    // Each entry: chars to match left of cursor, chars to match right, total
    // width to delete. Padded form "{{ | }}" is checked first because the
    // auto-closer inserts two spaces and parks the cursor between them.
    const autoClosePairs = [
      { left: "{{ ", right: " }}", deleteLeft: 3, deleteRight: 3 },
      { left: "{% ", right: " %}", deleteLeft: 3, deleteRight: 3 },
      { left: "{# ", right: " #}", deleteLeft: 3, deleteRight: 3 },
      { left: "{{",  right: "}}",  deleteLeft: 2, deleteRight: 2 },
      { left: "{%",  right: "%}",  deleteLeft: 2, deleteRight: 2 },
      { left: "{#",  right: "#}",  deleteLeft: 2, deleteRight: 2 },
    ];

    const deleteDisposable = editor.onKeyDown((e) => {
      if (e.keyCode !== monaco.KeyCode.Backspace) return;
      if (e.ctrlKey || e.metaKey || e.altKey) return;
      const model = editor.getModel();
      if (!model || model.getLanguageId() !== "jinja") return;
      const sel = editor.getSelection();
      if (!sel.isEmpty()) return;
      const pos = editor.getPosition();
      const line = model.getLineContent(pos.lineNumber);
      const col = pos.column;
      const pair = autoClosePairs.find((p) =>
        line.substring(col - 1 - p.left.length, col - 1) === p.left &&
        line.substring(col - 1, col - 1 + p.right.length) === p.right
      );
      if (!pair) return;
      e.preventDefault();
      e.stopPropagation();
      editor.executeEdits("jinja-autodeletepair", [
        {
          range: new monaco.Range(
            pos.lineNumber, col - pair.deleteLeft,
            pos.lineNumber, col + pair.deleteRight
          ),
          text: "",
          forceMoveMarkers: true,
        },
      ]);
    });

    const disposeListener = editor.onDidDispose(() => {
      typeDisposable.dispose();
      blockCloseDisposable.dispose();
      deleteDisposable.dispose();
      disposeListener.dispose();
    });
  }

  function insideComment(model, position) {
    const textUntil = model.getValueInRange({
      startLineNumber: 1,
      startColumn: 1,
      endLineNumber: position.lineNumber,
      endColumn: position.column,
    });
    const lastOpen = textUntil.lastIndexOf("{#");
    if (lastOpen === -1) return false;
    const lastClose = textUntil.lastIndexOf("#}");
    return lastClose < lastOpen;
  }
})();
