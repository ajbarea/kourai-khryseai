# Frontend Style Guide

!!! note "Future Reference"
    Kourai Khryseai's current GUI is a Pygame desktop client. This guide establishes standards for a future web UI.

Standards for React + TypeScript development in Kourai Khryseai.

## Quick Reference

| | |
|---|---|
| **React** | 19+ (functional components + hooks) |
| **React Compiler** | Enabled — no manual `useMemo`/`useCallback` |
| **TypeScript** | Strict mode |
| **Build tool** | Vite 7+ |
| **Line length** | 100 characters |
| **Formatter** | Prettier (2 spaces, single quotes, semicolons) |

| Tool | Config |
|------|--------|
| TypeScript | `tsconfig.json` |
| Vite | `vite.config.ts` |
| ESLint | `eslint.config.js` |
| Prettier | `.prettierrc` |
| Vitest | `vitest.config.ts` |

---

## TypeScript

### Strict mode required

```json
{
  "compilerOptions": {
    "strict": true,
    "target": "ESNext",
    "module": "ESNext",
    "jsx": "react-jsx"
  }
}
```

### Type safety patterns

```typescript
// ✅ Null-safe access
function getAgentName(agent: Agent | null): string {
  return agent?.name ?? 'Unknown Agent';
}

// ✅ Discriminated unions for agent states
type AgentStatus =
  | { state: 'idle' }
  | { state: 'working'; taskId: string }
  | { state: 'failed'; error: string };
```

---

## Components

### Structure

```typescript
import { useState } from 'react';
import { StatusBadge } from '@/components/StatusBadge';

// 1. Types
interface AgentCardProps {
  name: string;
  port: number;
  status: 'active' | 'idle' | 'failed';
}

// 2. Component (named export only)
export function AgentCard({ name, port, status }: AgentCardProps) {
  // 3. Hooks at the top
  const [expanded, setExpanded] = useState(false);

  // 4. Return JSX
  return (
    <div className="agent-card">
      <h3>{name}</h3>
      <StatusBadge status={status} />
      <code>:{port}</code>
    </div>
  );
}
```

### Named exports only

```typescript
// ✅ Named export
export function AgentList() { ... }

// ❌ No default exports
export default function AgentList() { ... }
```

---

## React Patterns

### Performance — let the Compiler work

With **React Compiler** (React 19 standard), manual memoization is legacy:

```typescript
// ❌ Legacy
const filtered = useMemo(() => agents.filter(a => a.active), [agents]);

// ✅ Modern — Compiler handles optimization
const filtered = agents.filter(a => a.active);
```

### Server state — TanStack Query

```typescript
export function useAgents() {
  return useQuery<Agent[]>({
    queryKey: ['agents'],
    queryFn: fetchAgents,
    staleTime: 30_000,
  });
}

// Use isPending, not isLoading
const { data, isPending, error } = useAgents();
```

---

## Accessibility

Semantic HTML with ARIA labels on interactive elements:

```typescript
export function CloseButton({ onClose }: { onClose: () => void }) {
  return (
    <button type="button" aria-label="Close dialog" onClick={onClose}>
      <CloseIcon />
    </button>
  );
}
```

---

## Cleanup Checklist

- [x] Remove WHAT comments
- [x] Keep WHY comments (rationale, design decisions)
- [x] Named exports only
- [x] Path aliases (`@/components`) instead of relative imports
- [x] Functional components (no class components)
- [x] TanStack Query for server state
- [x] No manual `useMemo`/`useCallback`
- [x] `isPending` not `isLoading`

---

**References:** [Google TypeScript Style Guide](https://google.github.io/styleguide/tsguide.html) · [React Docs](https://react.dev/) · [Python Guide](python-style-guide.md) · [Shell Guide](shell-style-guide.md)
