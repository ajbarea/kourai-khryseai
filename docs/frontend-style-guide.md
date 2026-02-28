# Frontend Style Guide

This guide documents best practices for React + TypeScript development in the **Kourai Khryseai** project. All frontend code should follow these conventions for maintainability and performance.

## Quick Reference

- **React version:** 19+ (functional components + hooks)
- **React Compiler:** Enabled (minimizes manual `useMemo`/`useCallback`)
- **TypeScript:** Strict mode enabled
- **Build tool:** Vite 7+
- **Line length:** 100 characters max
- **Formatting:** Prettier (2 spaces, single quotes, semicolons)

## Tools and Configuration

| Tool | Purpose | Config Location |
|------|---------|-----------------|
| TypeScript | Type safety and tooling | `tsconfig.json` |
| Vite | Build tool + dev server | `vite.config.ts` |
| ESLint | Linting | `eslint.config.js` |
| Prettier | Code formatting | `.prettierrc` |
| Vitest | Unit/component testing | `vitest.config.ts` |

## TypeScript Fundamentals

### Strict Mode Configuration

TypeScript strict mode must be enabled to catch errors at compile time.

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

### Type Safety Patterns

```typescript
// ✅ GOOD: Type safety with strict null checks
function getAgentName(agent: Agent | null): string {
  return agent?.name ?? 'Unknown Agent';
}
```

## Component Structure

### Component Anatomy

```typescript
import { useState, type ChangeEvent } from 'react';
import { StatusBadge } from '@/components/common/Badge/StatusBadge';

// 1. Type definitions
interface AgentCardProps {
  id: string;
  name: string;
  status: 'active' | 'idle' | 'failed';
}

// 2. Component function
export function AgentCard({ id, name, status }: AgentCardProps) {
  // 3. Hooks at the top
  const [isExpanded, setIsExpanded] = useState(false);

  // 4. Main JSX return
  return (
    <div className="agent-card">
      <h3>{name}</h3>
      <StatusBadge status={status} />
    </div>
  );
}
```

### Named Exports Only

**Google TypeScript Style Guide mandates no default exports.**

```typescript
// ✅ GOOD: Named exports
export function AgentList() { ... }

// ❌ BAD: Default exports
export default function AgentList() { ... }
```

## React Patterns

### Performance (2026 Standard)

With the **React Compiler** (standard in React 19), manual memoization is legacy.

```typescript
// ❌ LEGACY: Manual memoization
const filteredAgents = useMemo(
  () => agents.filter(a => a.active),
  [agents]
);

// ✅ MODERN: React Compiler handles optimization automatically
const filteredAgents = agents.filter(a => a.active);
```

### Server State (TanStack Query)

```typescript
// ✅ GOOD: Typed query with 2026 'isPending' syntax
export function useAgents() {
  return useQuery<Agent[]>({
    queryKey: ['agents'],
    queryFn: getAgents,
    staleTime: 30 * 1000,
  });
}
```

## Accessibility

### Semantic HTML

```typescript
// ✅ GOOD: Semantic elements with ARIA labels
export function CloseButton({ onClose }: CloseButtonProps) {
  return (
    <button
      type="button"
      aria-label="Close dialog"
      onClick={onClose}
    >
      <CloseIcon />
    </button>
  );
}
```

## Cleanup Checklist

1. ✅ Remove WHAT comments
2. ✅ Keep WHY comments (rationale, design decisions)
3. ✅ Named exports ONLY
4. ✅ Path aliases (`@/components`) instead of relative imports
5. ✅ Functional components (no class components)
6. ✅ TanStack Query for server state
7. ✅ No manual `useMemo`/`useCallback` (let the Compiler work)

## Cross-Reference

- [Google TypeScript Style Guide](https://google.github.io/styleguide/tsguide.html)
- [React Official Documentation](https://react.dev/)
- [Python Style Guide](python-style-guide.md)
- [Shell Style Guide](shell-style-guide.md)

---

*Last Updated: 2026-02-28*
