# F5 PDF Runtime Decision: reportlab

## Decision

Use **`reportlab`** (Platypus) for PDF generation.

## Comparison

| Criterion | reportlab | WeasyPrint |
|---|---|---|
| **Windows install** | Pure pip install, no system deps | Requires Cairo + Pango + GTK — painful on Windows, often fails |
| **Layout** | Imperative flowables, manual positioning — verbose but deterministic | CSS Grid/Flexbox — elegant but debugging layout is harder |
| **Font bundling** | Ships DejaVu fonts (serif + sans) — works offline out of the box | Relies on system fonts; explicit bundling needed for reproducibility |
| **Table rendering** | `Table` flowable with `TableStyle` — verbose but pixel-perfect control | HTML `<table>` — simpler syntax but less precise styling |
| **Chart embedding** | Embed matplotlib PNGs as `Image` flowables — straightforward | Same approach (embed PNGs in `<img>` tags) |
| **Page templates** | `PageTemplate` + `BaseDocTemplate` — full control over headers/footers/frames | `@page` CSS rules — powerful but less intuitive for programmatic content |
| **TOC generation** | Built-in `TableOfContents` flowable with `afterFlowable` notify | Manual — would need JS or two-pass HTML generation |
| **PyInstaller packaging** | Clean — pure Python, no native libs to bundle beyond reportlab itself | Cairo/Pango/GObject DLLs must be bundled — known source of PyInstaller failures on Windows |
| **Maturity** | 20+ years, widely used for automated PDF generation | Mature for web-to-PDF, less common in desktop app pipelines |

## Rationale

1. **Windows packaging**: In F8 we ship via electron-builder + PyInstaller. WeasyPrint's Cairo/Pango dependency chain is notoriously fragile under PyInstaller on Windows. reportlab is pure Python with a small C extension — bundles cleanly.
2. **Offline operation**: reportlab ships DejaVu fonts. No network, no system font assumptions.
3. **Deterministic layout**: The report has strict Italian text, exact table formats, and precise page structure. reportlab's imperative model gives full control.
4. **TOC support**: reportlab's `TableOfContents` + `afterFlowable` handles two-pass page number resolution natively.
5. **No additional system dependencies**: `pip install reportlab` — done.

## Trade-offs accepted

- **More verbose code**: reportlab's Platypus API requires more boilerplate than HTML/CSS. Acceptable for a structured report with fixed layout.
- **No CSS**: Layout is code, not markup. This is actually a benefit for programmatic reports where content varies.
- **Learning curve**: Platypus flowables have quirks (KeepTogether, Table splitting). Well-documented.

## Implementation

- Add `reportlab>=4.0` to `pyproject.toml` dev/runtime dependencies
- Add `pypdf>=4.0` as test dependency (PDF validation)
- Use `SimpleDocTemplate` with custom `PageTemplate` for header/footer
- Charts rendered as matplotlib PNGs, embedded as `Image` flowables
- TOC via `TableOfContents` with `afterFlowable` callback for page number resolution
