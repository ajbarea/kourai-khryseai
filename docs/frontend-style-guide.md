# Frontend Style Guide

This guide documents best practices for React + TypeScript development in the IntelliFL project. All frontend code should follow these conventions to maintain consistency, type safety, and IEEE research artifact quality.

## Quick Reference

- React version: 19+ (functional components + hooks)
- TypeScript: Strict mode enabled
- Build tool: Vite 7+
- Line length: 100 characters max
- Formatting: Prettier (2 spaces, single quotes, semicolons)
- Linting: ESLint with TypeScript + React plugins
- Component style: Named function exports (PascalCase)
- Testing: Vitest + React Testing Library
- Exports: **Named exports only** (no default exports)
- Comments: WHY not WHAT

## Tools and Configuration

| Tool | Purpose | Config Location |
|------|---------|-----------------|
| TypeScript | Type safety and tooling | `tsconfig.json` |
| Vite | Build tool + dev server | `vite.config.ts` |
| ESLint | Linting | `eslint.config.js` |
| Prettier | Code formatting | `.prettierrc` |
| Vitest | Unit/component testing | `vitest.config.ts` |
| Playwright | E2E testing | `playwright.config.ts` |
| React Testing Library | Component test utilities | N/A (in-app) |

Commands:
```bash
npm run lint         # Run ESLint
npm run format       # Run Prettier
npm run dev          # Start dev server
npm run build        # Production build (type-checks)
npm run test         # Run Vitest tests
npm run test:e2e     # Run Playwright E2E tests
```

## TypeScript Fundamentals

### Strict Mode Configuration

TypeScript strict mode must be enabled to catch errors at compile time.

**tsconfig.json:**
```json
{
  "compilerOptions": {
    "strict": true,
    "target": "ESNext",
    "module": "ESNext",
    "lib": ["ES2023", "DOM", "DOM.Iterable"],
    "jsx": "react-jsx",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "allowImportingTsExtensions": true,
    "noEmit": true,
    "skipLibCheck": true,
    "esModuleInterop": true,
    "allowSyntheticDefaultImports": true,
    "forceConsistentCasingInFileNames": true,
    "isolatedModules": true,
    "noUncheckedIndexedAccess": true,
    "noImplicitReturns": true,
    "noFallthroughCasesInSwitch": true,
    "paths": {
      "@/*": ["./src/*"],
      "@components/*": ["./src/components/*"],
      "@hooks/*": ["./src/hooks/*"],
      "@api/*": ["./src/api/*"],
      "@utils/*": ["./src/utils/*"],
      "@constants/*": ["./src/constants/*"],
      "@contexts/*": ["./src/contexts/*"],
      "@pages/*": ["./src/pages/*"]
    }
  }
}
```

### Type Safety Patterns

```typescript
// ✅ GOOD: Type safety with strict null checks
function getUserName(user: User | null): string {
  return user?.name ?? 'Anonymous';
}

// ❌ BAD: Unsafe assumption
function getUserName(user: User): string {
  return user.name; // What if user is null?
}

// ✅ GOOD: Discriminated unions for state
type LoadingState =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'success'; data: Simulation[] }
  | { status: 'error'; error: Error };

function renderSimulations(state: LoadingState) {
  switch (state.status) {
    case 'loading':
      return <Spinner />;
    case 'success':
      return <SimulationList data={state.data} />;
    case 'error':
      return <ErrorMessage error={state.error} />;
    default:
      return null;
  }
}

// ❌ BAD: Loose types with runtime errors
function renderSimulations(loading: boolean, data: any, error: any) {
  if (loading) return <Spinner />;
  if (error) return <ErrorMessage error={error} />;
  return <SimulationList data={data} />; // data might be undefined
}
```

## Migration Path from JavaScript

**The codebase is being migrated from JavaScript to TypeScript.**

For a comprehensive migration strategy, see the dedicated [TypeScript Migration Plan](../TYPESCRIPT_MIGRATION_PLAN.md).

**Quick migration overview:**
1. Setup TypeScript infrastructure (tsconfig.json, Vitest, ESLint)
2. Migrate files incrementally (utilities → hooks → components)
3. Add type definitions for API responses and shared types
4. Enable strict mode and achieve 100% type coverage

This guide focuses on **what** the final TypeScript code should look like. The migration plan details **how** to get there from the current JavaScript codebase.

## Component Structure

### Component Anatomy

TypeScript components should follow this structure:

```typescript
import { useState, useMemo, useCallback, type ChangeEvent } from 'react';
import { Form } from 'react-bootstrap';
import { InfoTooltip } from '@components/common/Tooltip/InfoTooltip';

// 1. Type definitions
interface SelectFieldOption {
  value: string | number;
  label: string;
}

interface SelectFieldProps {
  name: string;
  label: string;
  value: string | number;
  onChange: (event: ChangeEvent<HTMLSelectElement>) => void;
  options: string[] | SelectFieldOption[];
  tooltip?: string;
  required?: boolean;
  className?: string;
}

// 2. Component function
export function SelectField({
  name,
  label,
  value,
  onChange,
  options,
  tooltip,
  required = false,
  className = '',
}: SelectFieldProps) {
  // 3. Hooks at the top
  const [isFocused, setIsFocused] = useState(false);

  // 4. Derived state / memoization
  const formattedOptions = useMemo<SelectFieldOption[]>(() => {
    return options.map(opt =>
      typeof opt === 'string' ? { value: opt, label: opt } : opt
    );
  }, [options]);

  // 5. Event handlers
  const handleFocus = useCallback(() => setIsFocused(true), []);
  const handleBlur = useCallback(() => setIsFocused(false), []);

  // 6. Render helpers (if needed)
  const renderLabel = () => {
    const labelElement = <Form.Label>{label}</Form.Label>;
    return tooltip ? (
      <InfoTooltip text={tooltip}>{labelElement}</InfoTooltip>
    ) : (
      labelElement
    );
  };

  // 7. Main JSX return
  return (
    <Form.Group className={`mb-3 ${className}`}>
      {renderLabel()}
      <Form.Select
        name={name}
        value={value}
        onChange={onChange}
        onFocus={handleFocus}
        onBlur={handleBlur}
        required={required}
      >
        {formattedOptions.map(option => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </Form.Select>
    </Form.Group>
  );
}
```

### Component Patterns

```typescript
// ❌ BAD: Avoid React.FC (implicit children prop causes issues)
export const SelectField: React.FC<SelectFieldProps> = ({ ... }) => { ... };

// ✅ GOOD: Explicit function declaration
export function SelectField({ ... }: SelectFieldProps) { ... }

// ❌ BAD: Class components (outdated)
class SelectField extends React.Component<SelectFieldProps> {
  render() { ... }
}

// ✅ GOOD: Functional components with hooks
export function SelectField({ ... }: SelectFieldProps) { ... }
```

## React Patterns

### Hooks Usage

```typescript
// ✅ GOOD: Hooks at top, correct dependencies
export function Dashboard() {
  const { data: simulations, isLoading, error, refetch } = useSimulations();
  const { statuses } = useSimulationStatus(simulations ?? []);
  const navigate = useNavigate();
  const [selectedIds, setSelectedIds] = useState<string[]>([]);

  // Memoization for expensive computation
  const completedSims = useMemo(
    () => simulations?.filter(s => statuses[s.id] === 'completed') ?? [],
    [simulations, statuses]
  );

  // Effect with correct dependencies
  useEffect(() => {
    if (error) {
      toast.error('Failed to load simulations');
    }
  }, [error]);

  return <div>{/* JSX */}</div>;
}

// ❌ BAD: Hooks inside conditionals
export function Dashboard() {
  const { data: simulations } = useSimulations();

  if (!simulations) {
    return <LoadingPage />;
  }

  const [selectedIds, setSelectedIds] = useState<string[]>([]); // Hook after return
}
```

### Custom Hooks

```typescript
// ✅ GOOD: Well-typed custom hook with TSDoc
interface DeviceInfo {
  gpuAvailable: boolean;
  gpuInfo: { name: string; vram_gb: number } | null;
  recommendedDevice: 'cpu' | 'gpu';
}

/**
 * Hook for detecting available training devices (CPU/GPU).
 * Caches device info for 5 minutes and provides graceful fallback to CPU.
 *
 * @returns Device information with loading and error states
 *
 * @example
 * ```tsx
 * const { gpuAvailable, recommendedDevice, isLoading } = useDeviceInfo();
 * if (gpuAvailable) {
 *   console.log(`Using ${recommendedDevice} for training`);
 * }
 * ```
 */
export function useDeviceInfo() {
  const { data, isPending, isError } = useQuery<DeviceInfo>({
    queryKey: ['system-devices'],
    queryFn: getSystemDevices,
    staleTime: 5 * 60 * 1000, // 5 minutes
    retry: 1, // Single retry, then graceful fallback
  });

  // Graceful fallback to CPU if error or no data
  return {
    gpuAvailable: data?.gpuAvailable ?? false,
    gpuInfo: data?.gpuInfo ?? null,
    recommendedDevice: isError ? 'cpu' : (data?.recommendedDevice ?? 'cpu'),
    isLoading: isPending,
  };
}
```

### Compound Components

Use compound components when components should belong and work together.

```typescript
// ✅ GOOD: Compound component pattern
interface TabsProps {
  children: React.ReactNode;
  defaultTab?: string;
}

interface TabProps {
  label: string;
  value: string;
  children: React.ReactNode;
}

export function Tabs({ children, defaultTab }: TabsProps) {
  const [activeTab, setActiveTab] = useState(defaultTab);
  return (
    <TabsContext.Provider value={{ activeTab, setActiveTab }}>
      {children}
    </TabsContext.Provider>
  );
}

export function Tab({ label, value, children }: TabProps) {
  const { activeTab } = useTabsContext();
  return activeTab === value ? <div>{children}</div> : null;
}

// Usage:
<Tabs defaultTab="config">
  <Tab label="Configuration" value="config">
    <ConfigPanel />
  </Tab>
  <Tab label="Results" value="results">
    <ResultsPanel />
  </Tab>
</Tabs>
```

## Type Definitions

### Props Interfaces

```typescript
// ✅ GOOD: Explicit required and optional props
interface ButtonProps {
  // Required props first
  label: string;
  onClick: () => void;

  // Optional props last (use sparingly - prefer required)
  variant?: 'primary' | 'secondary' | 'danger';
  size?: 'sm' | 'md' | 'lg';
  disabled?: boolean;
  className?: string;

  // Children (if component accepts them)
  children?: React.ReactNode;
}

// ⚠️ ACCEPTABLE: Extending HTML button props
interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  label: string;
  variant?: 'primary' | 'secondary' | 'danger';
}

// ❌ BAD: Everything optional (makes component hard to use correctly)
interface ButtonProps {
  label?: string;
  onClick?: () => void;
  variant?: string;
}
```

### Event Handlers

```typescript
// ✅ GOOD: Properly typed event handlers
import type { ChangeEvent, FormEvent, MouseEvent } from 'react';

interface FormComponentProps {
  onSubmit: (data: FormData) => void;
}

export function FormComponent({ onSubmit }: FormComponentProps) {
  const [value, setValue] = useState('');

  const handleChange = (event: ChangeEvent<HTMLInputElement>) => {
    setValue(event.target.value);
  };

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    onSubmit({ value });
  };

  const handleClick = (event: MouseEvent<HTMLButtonElement>) => {
    console.log('Button clicked at', event.clientX, event.clientY);
  };

  return (
    <form onSubmit={handleSubmit}>
      <input value={value} onChange={handleChange} />
      <button type="submit" onClick={handleClick}>Submit</button>
    </form>
  );
}
```

### Generics

```typescript
// ✅ GOOD: Generic hook with type safety
function useLocalStorage<T>(key: string, initialValue: T): [T, (value: T) => void] {
  const [storedValue, setStoredValue] = useState<T>(() => {
    const item = window.localStorage.getItem(key);
    return item ? (JSON.parse(item) as T) : initialValue;
  });

  const setValue = (value: T) => {
    setStoredValue(value);
    window.localStorage.setItem(key, JSON.stringify(value));
  };

  return [storedValue, setValue];
}

// Usage with type inference:
const [theme, setTheme] = useLocalStorage<'light' | 'dark'>('theme', 'light');
```

## State Management

### Local State (useState)

```typescript
// ✅ GOOD: Typed local state
const [selectedIds, setSelectedIds] = useState<string[]>([]);
const [modal, setModal] = useState<{ show: boolean; title: string }>({
  show: false,
  title: '',
});

// ✅ GOOD: Functional update for state dependent on previous value
setSelectedIds(prev =>
  prev.includes(simId) ? prev.filter(id => id !== simId) : [...prev, simId]
);

// ❌ BAD: Direct mutation
selectedIds.push(newId); // Never mutate state directly
setSelectedIds(selectedIds); // Won't trigger re-render
```

### Context API (Global UI State)

```typescript
// ✅ GOOD: Typed context with provider pattern
import { createContext, useContext, useState, type ReactNode } from 'react';

type Theme = 'light' | 'dark';

interface ThemeContextValue {
  theme: Theme;
  toggleTheme: () => void;
}

const ThemeContext = createContext<ThemeContextValue | null>(null);

export function useTheme(): ThemeContextValue {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error('useTheme must be used within ThemeProvider');
  }
  return context;
}

interface ThemeProviderProps {
  children: ReactNode;
}

export function ThemeProvider({ children }: ThemeProviderProps) {
  const [theme, setTheme] = useState<Theme>(() => {
    const saved = localStorage.getItem('theme');
    return (saved === 'light' || saved === 'dark') ? saved : 'light';
  });

  const toggleTheme = () => {
    setTheme(prev => (prev === 'light' ? 'dark' : 'light'));
  };

  const value: ThemeContextValue = { theme, toggleTheme };

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}
```

### Server State (TanStack Query)

```typescript
// ✅ GOOD: Typed query with proper configuration
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';

interface Simulation {
  id: string;
  name: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  createdAt: string;
}

export function useSimulations() {
  return useQuery<Simulation[]>({
    queryKey: ['simulations'],
    queryFn: getSimulations,
    staleTime: 30 * 1000, // 30 seconds
    refetchInterval: 5 * 1000, // Poll every 5 seconds
    refetchOnWindowFocus: true,
  });
}

// ✅ GOOD: Typed mutation with optimistic updates
export function useDeleteSimulation() {
  const queryClient = useQueryClient();

  return useMutation<void, Error, string>({
    mutationFn: deleteSimulation,
    onMutate: async (simId) => {
      // Cancel outgoing refetches
      await queryClient.cancelQueries({ queryKey: ['simulations'] });

      // Snapshot previous value
      const previous = queryClient.getQueryData<Simulation[]>(['simulations']);

      // Optimistically update
      queryClient.setQueryData<Simulation[]>(['simulations'], old =>
        old?.filter(sim => sim.id !== simId) ?? []
      );

      return { previous };
    },
    onError: (_err, _simId, context) => {
      // Rollback on error
      if (context?.previous) {
        queryClient.setQueryData(['simulations'], context.previous);
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ['simulations'] });
    },
  });
}
```

## Performance

### React Compiler (2026 Standard)

As of React 19 and the React Compiler v1.0 (October 2025), **manual memoization is becoming legacy practice**. The React Compiler automatically optimizes components at build time.

```typescript
// ❌ LEGACY: Manual memoization (pre-React Compiler)
const filteredSimulations = useMemo(
  () => simulations.filter(sim => sim.status === 'completed'),
  [simulations]
);

const handleDelete = useCallback((id: string) => {
  deleteSimulation(id);
}, []);

// ✅ MODERN: React Compiler handles optimization automatically
const filteredSimulations = simulations.filter(sim => sim.status === 'completed');

const handleDelete = (id: string) => {
  deleteSimulation(id);
};
```

**When to still use manual memoization:**
- Extremely expensive computations (complex algorithms, large datasets)
- When profiling shows a specific bottleneck
- Before React Compiler is fully enabled in the project

### Lazy Loading

```typescript
// ✅ GOOD: Code splitting for routes
import { lazy, Suspense } from 'react';
import { LoadingPage } from '@components/common/Loading/LoadingPage';

const Dashboard = lazy(() => import('@pages/Dashboard/Dashboard'));
const SimulationDetails = lazy(() => import('@pages/SimulationDetails/SimulationDetails'));

export function App() {
  return (
    <Suspense fallback={<LoadingPage />}>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/simulations/:id" element={<SimulationDetails />} />
      </Routes>
    </Suspense>
  );
}
```

## Import/Export Patterns

### Import Order

```typescript
// ✅ GOOD: Organized imports
// 1. React imports
import { useState, useEffect, useMemo, type ReactNode, type ChangeEvent } from 'react';

// 2. Third-party libraries
import { useQuery } from '@tanstack/react-query';
import { Form, Button } from 'react-bootstrap';
import { toast } from 'sonner';

// 3. Path alias imports (@ prefix)
import { InfoTooltip } from '@components/common/Tooltip/InfoTooltip';
import { useDeviceInfo } from '@hooks/useDeviceInfo';
import { getSimulations } from '@api/endpoints/simulations';
import { formatAccuracy } from '@utils/formatters';
import { CACHE_DURATION } from '@constants/ui';
import { useTheme } from '@contexts/ThemeContext';

// 4. Relative imports (avoid when possible - use aliases)
import { helper } from './utils';
import type { LocalType } from './types';
```

### Named Exports Only

**Google TypeScript Style Guide mandates no default exports.**

```typescript
// ✅ GOOD: Named exports
export function SelectField({ ... }: SelectFieldProps) { ... }
export function useDeviceInfo() { ... }
export type { SelectFieldProps, DeviceInfo };

// ✅ GOOD: Barrel exports (index.ts files)
// components/common/index.ts
export { Spinner } from './Loading/Spinner';
export { InfoTooltip } from './Tooltip/InfoTooltip';
export { StatusBadge } from './Badge/StatusBadge';

// ❌ BAD: Default exports (prohibited by Google style)
export default function SelectField() { ... }
export default SelectField;

// ❌ BAD: Importing default exports
import SelectField from './SelectField'; // Avoid this pattern
```

**Rationale:** Named exports ensure:
- Consistent import patterns across codebase
- Better IDE autocomplete and refactoring
- Clearer code ownership and searchability

### Type Imports

```typescript
// ✅ GOOD: Separate type imports when used only as types
import { useState } from 'react';
import type { ReactNode, ChangeEvent } from 'react';

// ✅ GOOD: Inline type imports (TypeScript 4.5+)
import { type ComponentProps, type FC } from 'react';

// ❌ BAD: Mixing value and type imports without distinction
import { useState, ReactNode, ChangeEvent } from 'react';
```

## File Organization

### Directory Structure

```
frontend/src/
├── api/                    # API client and endpoints
│   ├── client.ts          # Axios instance with interceptors
│   ├── endpoints/         # API endpoint functions
│   │   ├── simulations.ts
│   │   ├── datasets.ts
│   │   └── index.ts       # Barrel export
│   └── index.ts           # Barrel export
├── components/
│   ├── common/            # Reusable UI primitives
│   │   ├── Loading/       # Spinner.tsx, LoadingPage.tsx
│   │   ├── Modal/         # ConfirmModal.tsx, QueueChoiceModal.tsx
│   │   ├── Badge/         # StatusBadge.tsx
│   │   └── index.ts       # Barrel export
│   ├── features/          # Feature-specific components
│   │   ├── simulation-form/
│   │   │   ├── SimulationForm.tsx
│   │   │   ├── FormFields/
│   │   │   └── index.ts
│   │   ├── simulation-list/
│   │   └── experiment-queue/
│   ├── charts/            # Recharts visualizations
│   └── layout/            # PageContainer.tsx, PageHeader.tsx
├── contexts/              # React Context providers
│   ├── ThemeContext.tsx
│   ├── DeviceContext.tsx
│   └── ToastContext.tsx
├── hooks/                 # Custom React hooks
│   ├── useDeviceInfo.ts
│   ├── useSimulations.ts
│   └── useConfigValidation.ts
├── pages/                 # Route components
│   ├── Dashboard/
│   │   ├── Dashboard.tsx
│   │   └── index.ts
│   ├── NewSimulation/
│   └── SimulationDetails/
├── constants/             # Configuration constants
│   ├── ui.ts             # Colors, timing, dimensions
│   ├── attacks.ts
│   ├── datasets.ts
│   └── presets.ts
├── utils/                 # Utility functions
│   ├── formatters.ts
│   ├── errorMessages.ts
│   └── configValidation.ts
├── types/                 # Shared TypeScript types
│   ├── api.ts            # API response types
│   ├── simulation.ts
│   └── index.ts
├── App.tsx               # Root component with routing
├── main.tsx              # Entry point
└── vite-env.d.ts         # Vite type declarations
```

### File Naming

```
// ✅ GOOD: PascalCase for components
SelectField.tsx
StatusBadge.tsx
InfoTooltip.tsx

// ✅ GOOD: camelCase for utilities/hooks
useDeviceInfo.ts
formatters.ts
errorMessages.ts

// ✅ GOOD: .tsx for components (JSX), .ts for utilities
Dashboard.tsx       # Has JSX
useSimulations.ts   # No JSX, just TypeScript

// ✅ GOOD: Directory structure for complex components
SimulationForm/
├── SimulationForm.tsx       # Main component
├── FormSections/            # Sub-components
│   ├── AttackSettings.tsx
│   └── DefenseSettings.tsx
├── types.ts                 # Local type definitions
└── index.ts                 # Barrel export
```

## API Integration

### Typed API Client

```typescript
// ✅ GOOD: Centralized error handling with interceptors
import axios, { type AxiosError } from 'axios';
import { toast } from 'sonner';
import { getErrorMessage } from '@utils/errorMessages';

export const apiClient = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30000,
});

apiClient.interceptors.response.use(
  response => response,
  (error: AxiosError) => {
    // Don't show toast for cancelled requests
    if (axios.isCancel(error) || error.config?.suppressToast) {
      return Promise.reject(error);
    }

    const message = getErrorMessage(error);
    const toastId = `api-error-${error.response?.status}-${message.slice(0, 50)}`;

    // Deduplication prevents toast spam
    toast.error(message, { id: toastId, duration: 5000 });

    return Promise.reject(error);
  }
);
```

### Typed Endpoint Functions

```typescript
// ✅ GOOD: Typed API endpoint functions
import type { AxiosResponse } from 'axios';
import { apiClient } from '@api/client';

interface Simulation {
  id: string;
  name: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  config: SimulationConfig;
  createdAt: string;
  updatedAt: string;
}

interface SimulationConfig {
  num_of_rounds: number;
  num_of_clients: number;
  dataset_keyword: string;
  aggregation_strategy_keyword: string;
}

export async function getSimulations(): Promise<Simulation[]> {
  const response = await apiClient.get<Simulation[]>('/simulations');
  return response.data;
}

export async function getSimulationDetails(simulationId: string): Promise<Simulation> {
  const response = await apiClient.get<Simulation>(`/simulations/${simulationId}`);
  return response.data;
}

export async function createSimulation(
  config: SimulationConfig,
  addToQueue: boolean | null = null
): Promise<Simulation> {
  const body = addToQueue !== null ? { ...config, add_to_queue: addToQueue } : config;
  const response = await apiClient.post<Simulation>('/simulations', body);
  return response.data;
}

export async function deleteSimulation(simulationId: string): Promise<void> {
  await apiClient.delete(`/simulations/${simulationId}`);
}
```

## Styling Approach

### Theme-Aware Constants

```typescript
// ✅ GOOD: Type-safe theme constants
export type Theme = 'light' | 'dark';

export interface ChartColors {
  primary: string;
  secondary: string;
  success: string;
  danger: string;
  warning: string;
  info: string;
}

/**
 * Colorblind-safe chart palettes (WCAG 2.1 AA compliant).
 * Extended to 12 colors for large federations.
 * @see https://jfly.uni-koeln.de/color/
 */
export const CHART_COLORS: Record<Theme, readonly string[]> = {
  light: [
    '#0072B2', '#D55E00', '#009E73', '#F0E442',
    '#56B4E9', '#E69F00', '#CC79A7', '#999999',
    '#000000', '#7570B3', '#66A61E', '#E7298A',
  ],
  dark: [
    '#56B4E9', '#E69F00', '#00D084', '#F4E864',
    '#0072B2', '#D55E00', '#D997CA', '#CCCCCC',
    '#FFFFFF', '#9B94C7', '#88C940', '#FF4FC0',
  ],
} as const;

export function getThemeColors(theme: Theme): ChartColors {
  const colors = CHART_COLORS[theme];
  return {
    primary: colors[0],
    secondary: colors[1],
    success: colors[2],
    danger: colors[3],
    warning: colors[4],
    info: colors[5],
  };
}
```

### Styled Components with Types

```typescript
// ✅ GOOD: Type-safe inline styles with data-driven values
interface StatusBadgeProps {
  status: 'pending' | 'running' | 'completed' | 'failed';
  className?: string;
}

const STATUS_COLORS: Record<StatusBadgeProps['status'], { bg: string; text: string }> = {
  pending: { bg: '#FEF3C7', text: '#92400E' },
  running: { bg: '#DBEAFE', text: '#1E40AF' },
  completed: { bg: '#D1FAE5', text: '#065F46' },
  failed: { bg: '#FEE2E2', text: '#991B1B' },
};

export function StatusBadge({ status, className = '' }: StatusBadgeProps) {
  const colors = STATUS_COLORS[status];

  return (
    <span
      className={`badge ${className}`}
      style={{
        backgroundColor: colors.bg,
        color: colors.text,
        padding: '0.25rem 0.5rem',
        borderRadius: '0.25rem',
      }}
    >
      {status}
    </span>
  );
}
```

## Error Handling

### Type-Safe Error Boundaries

```typescript
// ✅ GOOD: Error boundary with proper typing
import { Component, type ReactNode, type ErrorInfo } from 'react';

interface ErrorBoundaryProps {
  children: ReactNode;
  fallback?: (error: Error) => ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    // Only log in development
    if (import.meta.env.DEV) {
      console.error('ErrorBoundary caught error:', error, errorInfo);
    }
  }

  render(): ReactNode {
    if (this.state.hasError && this.state.error) {
      return this.props.fallback?.(this.state.error) ?? (
        <ErrorFallback error={this.state.error} />
      );
    }
    return this.props.children;
  }
}
```

### Discriminated Unions for Errors

```typescript
// ✅ GOOD: Type-safe error handling with discriminated unions
type ApiError =
  | { type: 'network'; message: string }
  | { type: 'validation'; field: string; message: string }
  | { type: 'server'; statusCode: number; message: string }
  | { type: 'timeout'; duration: number };

function handleApiError(error: ApiError): string {
  switch (error.type) {
    case 'network':
      return `Network error: ${error.message}`;
    case 'validation':
      return `Validation error on ${error.field}: ${error.message}`;
    case 'server':
      return `Server error (${error.statusCode}): ${error.message}`;
    case 'timeout':
      return `Request timed out after ${error.duration}ms`;
    default:
      // TypeScript exhaustiveness checking ensures all cases are handled
      const _exhaustive: never = error;
      return 'Unknown error';
  }
}
```

## Comment Quality

### Remove WHAT Comments

Comments that restate what the code does provide no value and should be removed.

```typescript
// ❌ BAD: Restates the code
// Set loading to true
setLoading(true);

// ❌ BAD: Obvious from JSX
// Render the button
return <Button>Submit</Button>;

// ❌ BAD: Obvious from function call
// Call the API
await fetchSimulations();

// ❌ BAD: Type already documents this
const [count, setCount] = useState<number>(0); // Initialize count to 0
```

### Keep WHY Comments

Comments that explain rationale, context, or design decisions are valuable.

```typescript
// ✅ GOOD: Explains rationale
// Disable buffering for SSE (text/event-stream) responses.
// This ensures events stream through immediately without accumulation.
if (contentType.includes('text/event-stream')) {
  proxyRes.headers['x-accel-buffering'] = 'no';
}

// ✅ GOOD: Research context (Krum Byzantine fault tolerance)
// Research: Krum requires n > 2f + 2 (Blanchard et al., NeurIPS 2017)
// https://proceedings.neurips.cc/paper_files/paper/2017/file/f4b9ec30ad9f68f89b29639786cb62ef-Paper.pdf
if (numMaliciousClients > maxMaliciousForKrum) {
  throw new Error('Too many malicious clients for Krum aggregation');
}

// ✅ GOOD: Accessibility context
// Formula: 5 seconds base + 1 second per 120 words (WCAG 2.1 AA)
// @see https://sheribyrnehaber.medium.com/designing-toast-messages-for-accessibility-fb610ac364be
export const TOAST_DURATION = {
  DEFAULT: 6000,
  LONG: 8000,
} as const;

// ✅ GOOD: Performance rationale
// React Compiler handles memoization automatically in production builds.
// Manual useMemo only needed for extremely expensive computations (profiled).
const filteredData = data.filter(item => item.status === 'completed');
```

## JSDoc/TSDoc

### When to Use TSDoc

Use TSDoc for:
- Complex generic types and constraints
- Non-obvious behavior or side effects
- Public API functions/hooks
- Algorithms with specific requirements

```typescript
// ✅ GOOD: TSDoc for complex utility with non-obvious behavior
/**
 * Extract attack phases from simulation config.
 * Handles both attack_schedule array and simple attack_type.
 *
 * @param config - Simulation configuration object
 * @param totalRounds - Total number of rounds in simulation
 * @returns Array of attack phase objects with normalized round indices
 *
 * @example
 * ```typescript
 * const phases = extractAttackPhases(
 *   { attack_schedule: [{ start_round: 1, end_round: 5, attack_type: 'label_flipping' }] },
 *   10
 * );
 * // Returns: [{ startRound: 1, endRound: 5, attackType: 'label_flipping', label: 'Label Flipping' }]
 * ```
 */
export function extractAttackPhases(
  config: SimulationConfig,
  totalRounds: number
): AttackPhase[] {
  // Implementation
}

// ✅ GOOD: TSDoc for hook with complex return type
/**
 * Hook for detecting available training devices (CPU/GPU).
 * Caches device info for 5 minutes and manages GPU notification state.
 *
 * @returns Device information object
 * @property gpuAvailable - Whether GPU is available on system
 * @property gpuInfo - GPU name and VRAM, or null if unavailable
 * @property recommendedDevice - 'cpu' or 'gpu' based on availability
 * @property isLoading - Whether device detection is in progress
 */
export function useDeviceInfo(): {
  gpuAvailable: boolean;
  gpuInfo: { name: string; vram_gb: number } | null;
  recommendedDevice: 'cpu' | 'gpu';
  isLoading: boolean;
} {
  // Implementation
}

// ❌ BAD: Unnecessary TSDoc for simple component
/**
 * A button component that renders a button element
 * @param props - The component props
 * @returns A JSX element
 */
export function Button(props: ButtonProps) {
  return <button {...props} />;
}
```

## Testing Patterns

### Vitest + Testing Library (Unit/Component Tests)

Vitest is the modern standard for Vite projects - significantly faster than Jest with native ESM support.

**Setup (vitest.config.ts):**
```typescript
import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './tests/setup.ts',
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html'],
    },
  },
});
```

**Component Tests:**
```typescript
// ✅ GOOD: Focus on user behavior, not implementation
import { render, screen } from '@testing-library/react';
import { userEvent } from '@testing-library/user-event';
import { describe, it, expect, vi } from 'vitest';
import { SelectField } from './SelectField';

describe('SelectField', () => {
  it('calls onChange when option is selected', async () => {
    const handleChange = vi.fn();
    const user = userEvent.setup();

    render(
      <SelectField
        name="test"
        label="Test Field"
        value=""
        onChange={handleChange}
        options={['option1', 'option2']}
      />
    );

    // Use role-based queries (accessible)
    const select = screen.getByRole('combobox', { name: /test field/i });
    await user.selectOptions(select, 'option1');

    expect(handleChange).toHaveBeenCalledOnce();
  });

  it('displays tooltip when provided', () => {
    render(
      <SelectField
        name="test"
        label="Test Field"
        value=""
        onChange={vi.fn()}
        options={['option1']}
        tooltip="This is a helpful tooltip"
      />
    );

    // Tooltip should be accessible
    expect(screen.getByText(/helpful tooltip/i)).toBeInTheDocument();
  });

  it('marks field as required when required prop is true', () => {
    render(
      <SelectField
        name="test"
        label="Test Field"
        value=""
        onChange={vi.fn()}
        options={['option1']}
        required
      />
    );

    expect(screen.getByRole('combobox')).toBeRequired();
  });
});
```

### Playwright E2E Tests

```typescript
// ✅ GOOD: E2E test with accessibility-focused selectors
import { test, expect } from '@playwright/test';

test('should submit simulation form with valid data', async ({ page }) => {
  await page.goto('/simulations/new');

  // Use accessible selectors
  await page.getByRole('combobox', { name: /aggregation strategy/i })
    .selectOption('fedavg');
  await page.getByRole('spinbutton', { name: /number of rounds/i })
    .fill('10');
  await page.getByRole('spinbutton', { name: /number of clients/i })
    .fill('5');

  await page.getByRole('button', { name: /submit/i }).click();

  // Verify success
  await expect(page.getByText('Simulation created successfully')).toBeVisible();
  await expect(page).toHaveURL(/\/simulations\/\w+/);
});

test('should display validation errors for invalid data', async ({ page }) => {
  await page.goto('/simulations/new');

  // Submit without required fields
  await page.getByRole('button', { name: /submit/i }).click();

  // Check for validation messages
  await expect(page.getByText(/required/i)).toBeVisible();
});
```

## Accessibility

### Semantic HTML

```typescript
// ✅ GOOD: Semantic elements with ARIA labels
export function DeleteButton({ onDelete, simulationName }: DeleteButtonProps) {
  return (
    <button
      type="button"
      aria-label={`Delete simulation ${simulationName}`}
      onClick={onDelete}
    >
      <TrashIcon />
    </button>
  );
}

// ✅ GOOD: Semantic navigation
export function MainNav() {
  return (
    <nav aria-label="Main navigation">
      <Link to="/">Dashboard</Link>
      <Link to="/simulations/new">New Simulation</Link>
    </nav>
  );
}

// ❌ BAD: Non-semantic divs for interactive elements
<div onClick={handleClick}>Click me</div> // Use <button>
```

### Keyboard Navigation

```typescript
// ✅ GOOD: Keyboard accessible custom interactions
export function Card({ onClick }: CardProps) {
  const handleKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      onClick();
    }
  };

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onClick}
      onKeyDown={handleKeyDown}
      aria-label="Simulation card"
    >
      {/* Card content */}
    </div>
  );
}
```

### WCAG 2.1 AA Compliance

```typescript
// ✅ GOOD: WCAG-compliant toast durations
/**
 * Toast notification durations based on WCAG 2.1 AA accessibility research.
 * Formula: 5 seconds base + 1 second per 120 words.
 * @see https://sheribyrnehaber.medium.com/designing-toast-messages-for-accessibility-fb610ac364be
 */
export const TOAST_DURATION = {
  /** Default duration for info/success toasts (6 seconds) */
  DEFAULT: 6000,
  /** Short duration for quick confirmations (4 seconds) */
  SHORT: 4000,
  /** Extended duration for important messages (8 seconds) */
  LONG: 8000,
  /** No auto-dismiss - user must close manually */
  PERSISTENT: 0,
} as const;

// ✅ GOOD: Color contrast for status badges (WCAG AA: 4.5:1 for text)
export const STATUS_COLORS = {
  light: {
    pending: { bg: '#FEF3C7', text: '#92400E' }, // 7.8:1 contrast
    running: { bg: '#DBEAFE', text: '#1E40AF' }, // 6.2:1 contrast
    completed: { bg: '#D1FAE5', text: '#065F46' }, // 7.1:1 contrast
    failed: { bg: '#FEE2E2', text: '#991B1B' }, // 6.5:1 contrast
  },
} as const;
```

## Code Quality

### ESLint Rules for TypeScript

```javascript
// eslint.config.js
import tseslint from '@typescript-eslint/eslint-plugin';
import tsparser from '@typescript-eslint/parser';
import reactHooks from 'eslint-plugin-react-hooks';
import reactRefresh from 'eslint-plugin-react-refresh';

export default [
  {
    files: ['**/*.{ts,tsx}'],
    languageOptions: {
      parser: tsparser,
      ecmaVersion: 2023,
      sourceType: 'module',
      parserOptions: {
        ecmaFeatures: { jsx: true },
      },
    },
    plugins: {
      '@typescript-eslint': tseslint,
      'react-hooks': reactHooks,
      'react-refresh': reactRefresh,
    },
    rules: {
      // TypeScript
      '@typescript-eslint/no-explicit-any': 'error',
      '@typescript-eslint/no-unused-vars': ['error', {
        argsIgnorePattern: '^_',
        varsIgnorePattern: '^_',
      }],
      '@typescript-eslint/explicit-function-return-type': 'off', // Use type inference
      '@typescript-eslint/explicit-module-boundary-types': 'off',

      // React Hooks
      'react-hooks/rules-of-hooks': 'error',
      'react-hooks/exhaustive-deps': 'warn',

      // React Refresh (Vite HMR)
      'react-refresh/only-export-components': ['warn', {
        allowConstantExport: true,
      }],
    },
  },
];
```

### No `any` Types

```typescript
// ❌ BAD: Using any defeats TypeScript's purpose
function processData(data: any) {
  return data.map((item: any) => item.value); // No type safety
}

// ✅ GOOD: Proper types
interface DataItem {
  id: string;
  value: number;
}

function processData(data: DataItem[]): number[] {
  return data.map(item => item.value);
}

// ✅ GOOD: Use unknown for truly unknown types, then narrow
function processUnknown(data: unknown): number {
  if (typeof data === 'number') {
    return data * 2;
  }
  throw new Error('Expected number');
}
```

## Cleanup Checklist

When reviewing or migrating frontend code to TypeScript:

1. ✅ Remove WHAT comments (restating code)
2. ✅ Keep WHY comments (rationale, design decisions, accessibility context)
3. ✅ Replace PropTypes with TypeScript interfaces
4. ✅ Named exports ONLY (no default exports)
5. ✅ Path aliases (@components, @hooks) instead of relative imports
6. ✅ Hooks at top of components (not conditional)
7. ✅ Functional components (no class components except ErrorBoundary)
8. ✅ TanStack Query for server state (not useState)
9. ✅ Context API for global UI state (not client-state library)
10. ✅ Remove manual useMemo/useCallback (React Compiler handles it)
11. ✅ Type-safe error handling (discriminated unions, not any)
12. ✅ User-friendly error messages (not technical stack traces)
13. ✅ Accessibility: semantic HTML, ARIA labels, keyboard navigation
14. ✅ WCAG 2.1 AA compliance (color contrast, toast timing)
15. ✅ Constants in separate files (no magic numbers)
16. ✅ TSDoc for complex types/algorithms only
17. ✅ Vitest + Testing Library for component tests
18. ✅ No marketing language ("comprehensive", "robust")
19. ✅ Enable TypeScript strict mode
20. ✅ Achieve 100% type coverage (no any types)

## Cross-Reference

This style guide aligns with:

- [Google TypeScript Style Guide](https://google.github.io/styleguide/tsguide.html) - TypeScript conventions
- [React Official Documentation](https://react.dev/) - React patterns and best practices
- [React TypeScript Cheatsheet](https://react-typescript-cheatsheet.netlify.app/) - React + TypeScript patterns
- [Vitest Documentation](https://vitest.dev/) - Modern testing framework
- [React Testing Library](https://testing-library.com/react) - User-centric testing
- [WCAG 2.1 Guidelines](https://www.w3.org/WAI/WCAG21/quickref/) - Accessibility standards
- [Patterns.dev React 2026](https://www.patterns.dev/react/react-2026/) - Modern React patterns
- [Python Style Guide](../../docs/style/PYTHON_STYLE_GUIDE.md) - Backend companion guide
- [Shell Style Guide](../../docs/style/SHELL_STYLE_GUIDE.md) - Scripts companion guide

---

*Last Updated: 2026-01-11*
