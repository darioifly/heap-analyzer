# Design System — Stile EVLOS (shadcn/ui + Tailwind CSS)

Questa applicazione DEVE seguire esattamente il design system EVLOS.
Stack frontend: **React + TypeScript + Vite + shadcn/ui + Tailwind CSS + Lucide React**.

## Font

- **Font principale:** Space Grotesk (Google Fonts) — weights: 300, 400, 500, 600, 700
- **Font monospace:** JetBrains Mono, Monaco, Courier, monospace
- **Import in index.html:**
```html
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;600;700&display=swap" rel="stylesheet">
Tailwind Config — tailwind.config.ts

import type { Config } from "tailwindcss";

export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Space Grotesk", "sans-serif"],
        mono: ["JetBrains Mono", "Monaco", "Courier", "monospace"],
      },
      colors: {
        evlos: {
          50:  "#E0E4EC",
          100: "#C1C8D9",
          200: "#A2ACC6",
          300: "#8491B3",
          400: "#6575A0",  // dark mode primary
          500: "#495A82",
          600: "#3B4967",  // light mode primary ← DEFAULT
          700: "#2D384C",  // header background
          800: "#1D283C",  // dark mode card bg
          900: "#101824",  // dark mode main bg
        },
        success: {
          50: "#ECFDF5", 100: "#D1FAE5", 200: "#A7F3D0", 300: "#6EE7B7",
          400: "#34D399", 500: "#10B981", 600: "#059669", 700: "#047857",
          800: "#065F46", 900: "#064E3B",
        },
        warning: {
          50: "#FFFBEB", 100: "#FEF3C7", 200: "#FDE68A", 300: "#FCD34D",
          400: "#FBBF24", 500: "#F59E0B", 600: "#D97706", 700: "#B45309",
          800: "#92400E", 900: "#78350F",
        },
        danger: {
          50: "#FEF2F2", 100: "#FEE2E2", 200: "#FECACA", 300: "#FCA5A5",
          400: "#F87171", 500: "#EF4444", 600: "#DC2626", 700: "#B91C1C",
          800: "#991B1B", 900: "#7F1D1D",
        },
      },
      borderRadius: {
        DEFAULT: "0.5rem",
      },
      boxShadow: {
        xs: "0 1px 2px 0 rgba(0, 0, 0, 0.05)",
        sm: "0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px -1px rgba(0, 0, 0, 0.1)",
        md: "0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -2px rgba(0, 0, 0, 0.1)",
        lg: "0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -4px rgba(0, 0, 0, 0.1)",
        xl: "0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.1)",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
} satisfies Config;
CSS Variables — globals.css
shadcn/ui usa CSS variables per i colori dei componenti. Configura così:


@import "tailwindcss";

@layer base {
  :root {
    /* Font */
    font-family: "Space Grotesk", sans-serif;

    /* shadcn/ui color tokens (formato HSL) */
    --background: 220 14% 96%;          /* #F3F4F6 */
    --foreground: 220 13% 9%;           /* #111827 */
    --card: 0 0% 100%;                  /* #FFFFFF */
    --card-foreground: 220 13% 9%;      /* #111827 */
    --popover: 0 0% 100%;              /* #FFFFFF */
    --popover-foreground: 220 13% 9%;   /* #111827 */
    --primary: 220 28% 32%;            /* #3B4967 — evlos-600 */
    --primary-foreground: 0 0% 100%;    /* #FFFFFF */
    --secondary: 220 14% 96%;          /* #F3F4F6 */
    --secondary-foreground: 220 13% 9%; /* #111827 */
    --muted: 220 14% 96%;              /* #F3F4F6 */
    --muted-foreground: 220 9% 46%;     /* #6B7280 */
    --accent: 220 14% 96%;             /* #F3F4F6 */
    --accent-foreground: 220 13% 9%;    /* #111827 */
    --destructive: 0 84% 60%;          /* #EF4444 */
    --destructive-foreground: 0 0% 100%;
    --border: 220 13% 91%;             /* #E5E7EB */
    --input: 220 13% 91%;              /* #E5E7EB */
    --ring: 220 28% 32%;               /* #3B4967 — evlos-600 */
    --radius: 0.5rem;

    /* Custom tokens EVLOS */
    --evlos-header: 216 26% 24%;       /* #2D384C — evlos-700 */
    --evlos-text-secondary: 220 9% 46%; /* #6B7280 */
    --evlos-text-tertiary: 220 9% 64%;  /* #9CA3AF */
  }

  .dark {
    --background: 216 30% 10%;          /* #101824 — evlos-900 */
    --foreground: 210 20% 98%;          /* #F9FAFB */
    --card: 216 28% 17%;               /* #1D283C — evlos-800 */
    --card-foreground: 210 20% 98%;     /* #F9FAFB */
    --popover: 216 28% 17%;            /* #1D283C */
    --popover-foreground: 210 20% 98%;  /* #F9FAFB */
    --primary: 220 22% 51%;            /* #6575A0 — evlos-400 */
    --primary-foreground: 0 0% 100%;    /* #FFFFFF */
    --secondary: 216 26% 24%;          /* #2D384C — evlos-700 */
    --secondary-foreground: 210 20% 98%;
    --muted: 216 26% 24%;              /* #2D384C */
    --muted-foreground: 220 9% 64%;     /* #9CA3AF */
    --accent: 216 26% 24%;             /* #2D384C */
    --accent-foreground: 210 20% 98%;
    --destructive: 0 84% 60%;
    --destructive-foreground: 0 0% 100%;
    --border: 220 28% 32%;             /* #3B4967 — evlos-600 */
    --input: 220 28% 32%;              /* #3B4967 */
    --ring: 220 22% 51%;               /* #6575A0 — evlos-400 */

    --evlos-header: 216 28% 17%;       /* #1D283C — evlos-800 */
    --evlos-text-secondary: 220 9% 64%; /* #9CA3AF */
    --evlos-text-tertiary: 220 9% 46%;  /* #6B7280 */
  }
}

@layer base {
  * {
    @apply border-border;
  }
  body {
    @apply bg-[hsl(var(--evlos-header))] text-foreground font-sans antialiased;
    margin: 0;
    padding: 0;
  }
  html, body, #root {
    height: 100%;
  }
  #root {
    width: 100%;
  }
}
Layout Struttura
L'app ha un header blu fisso (100px) e un'area contenuto con angoli arrotondati in alto:


// Layout.tsx
export function Layout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-screen flex-col">
      {/* Header — sempre blu EVLOS, testo bianco */}
      <header className="h-[100px] shrink-0 bg-evlos-700 dark:bg-evlos-800 flex items-center px-6">
        {/* Logo a sinistra */}
        <div className="flex-1">
          <img src="/logo-white.png" alt="Logo" className="h-10" />
        </div>
        {/* User menu a destra — testo sempre bianco */}
        <div className="text-white flex items-center gap-3">
          <span className="hidden sm:inline text-sm">{userEmail}</span>
          {/* Avatar / dropdown */}
        </div>
      </header>

      {/* Contenuto — sfondo chiaro/scuro con bordi arrotondati in alto */}
      <main className="flex-1 bg-evlos-700 dark:bg-evlos-800 overflow-auto">
        <div className="bg-background rounded-t-lg mx-4 sm:mx-2 min-h-full p-6">
          {children}
        </div>
      </main>
    </div>
  );
}
Punti chiave del layout:

body background = evlos-700 (blu header) → evita flash bianco su overscroll
Il <main> ha lo stesso sfondo blu dell'header
Il contenuto interno ha bg-background (grigio chiaro / blu scuro) con rounded-t-lg
Margine: mx-4 desktop, mx-2 mobile
Header: nessun bordo, altezza 100px
Regole Stile Componenti shadcn/ui
Bottoni

// Colore primario = evlos. Usa sempre "default" variant come principale.
<Button>Azione principale</Button>       {/* bg evlos-600, testo bianco */}
<Button variant="outline">Secondario</Button>
<Button variant="destructive">Elimina</Button>
font-weight: 500
border-radius: var(--radius) = 0.5rem
Card / Paper

<Card className="border border-border shadow-sm">
  <CardContent>...</CardContent>
</Card>
Background: bianco (light) / evlos-800 (dark) — automatico via CSS vars
Bordo: sempre 1px solid con border-border
Shadow: shadow-sm
Tabelle

<Table>
  <TableHeader>
    <TableRow>
      {/* Header: uppercase, piccolo, tracking largo, colore secondario */}
      <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
        Colonna
      </TableHead>
    </TableRow>
  </TableHeader>
  <TableBody>
    <TableRow>
      <TableCell>Valore</TableCell>
    </TableRow>
  </TableBody>
</Table>
Header: text-xs font-semibold uppercase tracking-wider text-muted-foreground
Celle: colore foreground di default
Input / Select
border-radius: 0.5rem (default)
border: border-input (#E5E7EB light / #3B4967 dark)
focus ring: colore evlos-600 (light) / evlos-400 (dark)
Menu / Dropdown
Shadow: shadow-md
Border: border border-border
Background: card color
Badge
border-radius: 0.5rem
Mappa Colori Rapida (classi Tailwind)
Uso	Light	Dark	Classe Tailwind
Header bg	#2D384C	#1D283C	bg-evlos-700 dark:bg-evlos-800
Page bg	#F3F4F6	#101824	bg-background
Card bg	#FFFFFF	#1D283C	bg-card
Card hover	—	#2D384C	dark:hover:bg-evlos-700
Primary btn	#3B4967	#6575A0	bg-primary
Bordo	#E5E7EB	#3B4967	border-border
Testo principale	#111827	#F9FAFB	text-foreground
Testo secondario	#6B7280	#9CA3AF	text-muted-foreground
Testo su header	#FFFFFF	#FFFFFF	text-white
Regole Generali da Seguire SEMPRE
Border radius: 0.5rem (8px) su tutto — card, button, input, badge, dropdown
Shadow: shadow-sm su card/paper, shadow-md su dropdown/popover
Bottoni primari: sfondo evlos-600, testo bianco, font-weight 500
Header tabelle: uppercase, text-xs, tracking-wider, font-semibold, colore muted-foreground
Input focus: ring colore primary (evlos-600 light / evlos-400 dark)
Testo su header blu: SEMPRE bianco #FFFFFF
Card: sempre con border border-border + shadow-sm
Icone: usa lucide-react, dimensione default 20px, stroke-width 1.75
Font: Space Grotesk ovunque, mai fallback su system font
Spaziatura: usa le scale Tailwind standard (p-4, gap-3, space-y-4, etc.)
Dipendenze npm

{
  "tailwindcss": "^4",
  "tailwindcss-animate": "latest",
  "lucide-react": "latest",
  "class-variance-authority": "latest",
  "clsx": "latest",
  "tailwind-merge": "latest"
}
shadcn/ui components installati via npx shadcn@latest add <component>.



---