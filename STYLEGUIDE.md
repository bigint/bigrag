# bigRAG Platform Style Guide

A comprehensive guide for writing clean, maintainable, and type-safe code for the bigRAG application.

## Breaking the Rules

**Every rule can and will be broken in certain cases.** When you deviate from these guidelines:

1. ✅ **Document the reason outside source code** in the commit message, PR description, or docs
2. ✅ **Make it intentional** - not accidental
3. ✅ **Document the trade-off** - what you gained vs what you gave up

```typescript
function processLargeDataset(data: unknown) {
  if (!isLargeDataset(data)) {
    throw new Error("Invalid dataset")
  }
  return transform(data)
}
```

**Rule breaks should always be intentional, not accidental.** Do not add explanatory source comments or docstrings under `api/bigrag/`, `sdks/typescript/src/`, `app/`, or `website/`; use clearer names, smaller functions, or external review notes instead. Functional tool directives such as `# type: ignore`, `# ruff:`, `// @ts-...`, `// biome-ignore`, and `// eslint-...` are allowed when the tool requires them.

## Table of Contents

- [Core Principles](#core-principles)
- [Rule Severity](#rule-severity)
- [Tech Stack Overview](#tech-stack-overview)
- [File Structure \& Organization](#file-structure--organization)
- [Naming Conventions](#naming-conventions)
- [TypeScript Usage](#typescript-usage)
- [React Patterns](#react-patterns)
- [State Management](#state-management)
- [Business Logic Extraction](#business-logic-extraction)
- [Data Fetching with TanStack Query](#data-fetching-with-tanstack-query)
- [Component Composition](#component-composition)
- [Performance Guidelines](#performance-guidelines)
- [Error Boundaries](#error-boundaries)
- [Styling with Tailwind CSS](#styling-with-tailwind-css)
- [Routing with TanStack Router](#routing-with-tanstack-router)
- [Accessibility](#accessibility)
- [General TypeScript/JavaScript Coding Guidelines](#general-typescriptjavascript-coding-guidelines)
- [Code Formatting \& Linting with Biome](#code-formatting--linting-with-biome)
- [Python Backend](#python-backend)
- [FastAPI Patterns](#fastapi-patterns)
- [Database \& Async Patterns](#database--async-patterns)
- [Caching with Redis](#caching-with-redis)
- [TypeScript SDK Design](#typescript-sdk-design)
- [Summary](#summary)
- [References](#references)

## Core Principles

The bigRAG codebase is built on these fundamental principles:

### 1. Thin React Layer

**Keep React components focused on presentation and user interaction, not business logic.**

Components should:
- Render UI based on props and state
- Handle user events by calling external functions
- Manage simple UI state (modals, form inputs)

Components should NOT:
- Contain complex business logic
- Include data transformation logic

### 2. Code Co-location

**Place code next to where it's used, not grouped by technical type.**

✅ **DO**: Place helper files next to the single component that uses them
❌ **DON'T**: Create shared folders for single-use code
✅ **DO**: Only use shared folders when code is used by 2+ files

### 3. Explicit Over Implicit

**Make data flow visible and dependencies clear.**

- Use pattern matching over conditional operators
- Pass dependencies as explicit parameters
- Avoid hiding business rules in control flow

### 4. Functional-Light Programming

**Embrace functional programming principles pragmatically:**

- **Immutability**: Transform data, don't mutate it (🔴 Must)
- **Pure functions**: Same input → same output, no side effects (🟡 Default)
- **Composition**: Build complex operations from simple ones (🟡 Default)
- **Prefer array methods**: Use `map`, `filter`, `reduce` over loops (🟢 Guideline)
  - Loops are allowed when: Early exit is required, performance is critical, or readability is improved

### 5. Type Safety First

**Leverage TypeScript to catch errors at compile time:**

- Strict mode enabled
- Explicit type annotations for function signatures
- No `any` types (use `unknown` if needed)
- Use discriminated unions for state management

## Rule Severity

Not all rules are equally important. Use these tiers to guide your decisions:

### 🔴 Must (Violations require strong justification)

These rules protect against bugs, security issues, or severe maintainability problems:

- **Thin React Layer** - Business logic must be extracted from components
- **Type safety** - No `any` types, use `unknown` + type guards (use `Record<string, unknown>` for objects)
- **Immutability** - Don't mutate data structures
- **Never use useEffect for data fetching** - Always use TanStack Query

### 🟡 Default (Follow unless there is a clear reason not to)

These rules represent best practices but allow pragmatic exceptions:

- **TanStack Query for async data** - Don't manually manage loading/error states with useState
- **Extract useEffect** - Effects in components should be in custom hooks (≤5 lines can stay inline)
- **Avoid query waterfalls** - Split dependent queries into separate components
- **Handle query states independently** - Don't group loading/error states with `||`
- **Use useQueries for parallel queries** - More concise than multiple useQuery calls
- **Use generics to preserve types** - Don't lose type information in utility functions
- **Pattern matching over conditionals** - Use ts-pattern for complex conditions
- **Readonly modifiers** - Mark data as readonly when it won't change
- **Custom hooks for logic** - Avoid custom hooks for business logic (use for DOM/framework APIs)
- **Pure functions** - Extract logic to pure functions

### 🟢 Guideline (Preferable, not mandatory)

These rules improve code quality but are stylistic preferences:

- **Array methods over loops** - Prefer `map`/`filter`/`reduce` (loops OK for performance/clarity)
- **Component size** - Keep components under 80 lines (flexible based on complexity)
- **Co-location** - Place code next to usage (balance with reusability)
- **Explaining variables** - Extract complex expressions (use judgment)

**When in doubt**: Follow existing patterns and prioritize clarity over dogma. If a rule seems wrong for your case, document why and discuss with the team.

## Tech Stack Overview

The app uses modern web technologies:

### Core Framework
- **React 19** - UI framework with modern hooks and concurrent features
- **TypeScript 6** - Type-safe JavaScript with strict mode
- **Vite** - Client-side React build tool and dev server for the admin UI

### API & Data Management
- **FastAPI** - Python backend framework (API server, in `api/` directory)
- **TanStack Query v5** - Async state management for data fetching
- **TanStack Form** - Headless form state, validation, reset, and submit handling for complex admin UI forms
- **asyncpg** - Fast PostgreSQL driver (Python backend uses asyncpg, not Drizzle)
- **Zod** - Runtime schema validation for API inputs and form data

### Routing
- **TanStack Router** - File-based client-side routing for the admin UI

### UI & Styling
- **Tailwind CSS 4** - Utility-first CSS framework
- **Base UI** - Unstyled, accessible component primitives
- **Lucide Icons** - Clean icon library
- **Recharts** - Composable charting library

### Quality
- **Biome** - Fast formatter and linter
- **Vitest** - Fast unit and integration testing

### File Naming Conventions

- **React Components**: `snake-case.tsx` (e.g., `user-profile.tsx`)
- **Utility Files**: `kebab-case.ts` (e.g., `format-date.ts`)
- **Hooks**: `use-*.ts` (e.g., `use-profile.ts`)
- **Types**: `*.types.ts` (e.g., `profile.types.ts`)
- **Route Files**: TanStack Router file route conventions in `app/src/routes/` (e.g., `_dashboard.collections.$name.documents.tsx`)

## Naming Conventions

### Variables and Functions

Use descriptive, intention-revealing names:

```typescript
// Good
const getUserProfile = (name: string): Promise<Profile> => { ... }
const isNameAvailable = (name: string): boolean => { ... }
const MAX_BIO_LENGTH = 500

// Avoid
const gUP = (n: string): Promise<Profile> => { ... }
const check = (n: string): boolean => { ... }
const x = 500
```

### Boolean Naming

Prefix with `is`, `has`, `should`, or `can`:

```typescript
// Good
const isLoading = status === 'pending'
const hasAvatar = !!avatarUrl
const canEditProfile = checkPermission(user, 'edit')
const shouldShowBanner = isExpiringSoon && !dismissed

// Avoid
const loading = status === 'pending'
const avatar = !!avatarUrl
const editProfile = checkPermission(user, 'edit')
```

### Type and Interface Naming

```typescript
// Use PascalCase for types and interfaces
interface UserProfile {
  name: string
  email: string
}

type ProfileStatus = 'loading' | 'success' | 'error'

// Use descriptive names for generics
function getProperty<TObject, TKey extends keyof TObject>(
  obj: TObject,
  key: TKey
): TObject[TKey] {
  return obj[key]
}

// Props interfaces: <ComponentName>Props
interface ProfileCardProps {
  name: string
  username: string
}
```

### Constants

Use `UPPER_SNAKE_CASE` for true constants:

```typescript
// Constants that represent fixed values
const MAX_NAME_LENGTH = 253
const MAX_FILE_SIZE = 10_485_760
const API_BASE_URL = 'https://api.bigrag.xyz' as const
```

## TypeScript Usage

### Strict Type Annotations

Always define types for function parameters and return values:

```typescript
// Good
interface GetProfileParams {
  readonly name: string
  readonly includeRecords?: boolean
}

function getProfile(params: GetProfileParams): Promise<Profile> {
  // ...
}

// Avoid
function getProfile(params) {
  // ...
}
```

### Use Readonly for Immutability

```typescript
// Good
interface UserProfile {
  readonly name: string
  readonly tags: readonly string[]
}

const processTags = (tags: readonly string[]): readonly string[] => {
  return tags.filter(isValid)
}

// Avoid
interface UserProfile {
  name: string
  tags: string[]
}

const processTags = (tags: string[]): string[] => {
  return tags.filter(isValid)
}
```

### Type Narrowing

Use type guards and discriminated unions:

```typescript
// Good - Discriminated union
type RequestState =
  | { status: 'idle' }
  | { status: 'pending'; requestId: string }
  | { status: 'success'; requestId: string; data: unknown }
  | { status: 'error'; error: Error }

function handleRequest(state: RequestState) {
  if (state.status === 'success') {
    // TypeScript knows state.data exists
    console.log(state.data)
  }
}

// Type guard
function isEmail(value: unknown): value is string {
  return typeof value === 'string' && /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)
}
```

### Avoid `any`, Use `unknown` 🔴 Must

```typescript
// ❌ AVOID - any bypasses type checks
function parseData(data: any) {
  return data.value
}

// ✅ CORRECT - unknown with type guard
function parseData(data: unknown): string {
  if (typeof data === 'object' && data !== null && 'value' in data) {
    return String(data.value)
  }
  throw new Error('Invalid data')
}

// ✅ CORRECT - Record for unknown object shapes
function processConfig(config: Record<string, unknown>) {
  // Type-safe access to object properties
  const name = typeof config.name === 'string' ? config.name : 'default'
  return name
}

// ✅ ACCEPTABLE - Record<string, any> when structure is truly unknown
// Use sparingly, prefer Record<string, unknown> for stricter type safety
function processApiResponse(response: Record<string, any>) {
  // When you need flexibility but know it's an object
  return response
}
```

**Guidelines:**
- ✅ **Use `unknown`** - For values of unknown type (requires type guards)
- ✅ **Use `Record<string, unknown>`** - For objects with unknown shape (stricter)
- ⚠️ **Use `Record<string, any>`** - Only when you need flexibility and know it's an object
- ❌ **Never use `any`** - Bypasses all type safety

### Use Generics to Preserve Types 🟡 Default

When working with strongly typed objects, use generics to preserve type information:

```typescript
// ✅ CORRECT - Generic preserves type
function getObjectValue<T extends object, K extends keyof T>(
  obj: T,
  key: K
): T[K] {
  return obj[key]
}

// Usage - return type is automatically inferred
interface User {
  name: string
  age: number
}

const user: User = { name: 'Alice', age: 30 }
const userName = getObjectValue(user, 'name') // Type: string
const userAge = getObjectValue(user, 'age')   // Type: number

// ✅ CORRECT - Generic with constraints
function mapObject<T extends object, R>(
  obj: T,
  mapper: (value: T[keyof T], key: keyof T) => R
): R[] {
  return Object.entries(obj).map(([key, value]) => 
    mapper(value as T[keyof T], key as keyof T)
  )
}

// ❌ AVOID - Loses type information
function getObjectValue(obj: object, key: string): unknown {
  return (obj as any)[key] // No type safety
}
```

**Benefits:**
- ✅ **Type preservation** - Return types inferred from input types
- ✅ **IntelliSense support** - Better autocomplete
- ✅ **Compile-time safety** - Catch errors before runtime

## React Patterns

### Component Definition

**Use arrow functions for React components:**

```typescript
// Good - Arrow function export (standard pattern)
export const ProfileCard = ({ name, address }: ProfileCardProps) => {
  return (
    <div>
      <h2>{name}</h2>
      <p>{address}</p>
    </div>
  )
}

// Avoid - Function declaration for components (use for utilities only)
export function ProfileCard({ name, address }: ProfileCardProps) {
  return <div>...</div>
}

// Avoid - Function expression
export const ProfileCard = function({ name, address }: ProfileCardProps) {
  return <div>...</div>
}
```

**Note**: Function declarations (`function`) are reserved for utility functions and helpers, not React components.

### Component Props

Define props interfaces next to the component:

```typescript
// Good - Named interface with arrow function
interface ProfileCardProps {
  readonly name: string
  readonly username: string
  readonly onEdit?: () => void
}

export const ProfileCard = ({ name, username, onEdit }: ProfileCardProps) => {
  return <div>...</div>
}

// Good - Inline type for simple components
export const Button = ({
  children,
  variant = 'default',
  ...props
}: React.ComponentProps<'button'> & { variant?: 'default' | 'outline' }) => {
  return <button {...props}>{children}</button>
}

// Good - Destructuring with type annotation
export const NameProfileCard = ({ name }: { name: string }) => {
  return <div>{name}</div>
}
```

### Pattern Matching for Conditional Rendering (🟡 Default)

Use `ts-pattern` for complex conditional logic over ternaries or `&&` operators:

> **Performance Note**: `ts-pattern` has some overhead due to JIT compilation ([benchmark details](https://github.com/bdbaraban/ts-pattern-benchmark/pull/1)). For simple conditions or hot paths, native conditionals may be faster. Measure if performance is critical (see [Performance Guidelines](#performance-guidelines)).

```typescript
import { match } from 'ts-pattern'
import { P } from 'ts-pattern'

// Good - Explicit pattern matching
export const ProfileStatus = ({ status }: { status: ProfileStatus }) => {
  return match(status)
    .with({ type: 'loading' }, () => <LoadingSpinner />)
    .with({ type: 'error', error: P.select() }, (error) => (
      <ErrorMessage error={error} />
    ))
    .with({ type: 'success', data: P.select() }, (data) => (
      <ProfileCard profile={data} />
    ))
    .exhaustive()
}

// Avoid - Nested ternaries
export const ProfileStatus = ({ status }) => {
  return status.type === 'loading' 
    ? <LoadingSpinner />
    : status.type === 'error'
    ? <ErrorMessage error={status.error} />
    : <ProfileCard profile={status.data} />
}

// Avoid - && operators with potential falsy bugs
export const ShowCount = ({ count }) => {
  return count && <div>Count: {count}</div>  // Breaks if count is 0
}

// Good - Explicit nullish check
export const ShowCount = ({ count }: { count: number | null }) => {
  return match({ count })
    .with({ count: P.not(P.nullish) }, ({ count }) => (
      <div>Count: {count}</div>
    ))
    .otherwise(() => null)
}
```

### Extract Static Values and Pure Functions

Keep component bodies clean by extracting static values:

```typescript
// Avoid - Recreated on every render
export const SettingsForm = () => {
  const MAX_FILE_SIZE = 10_485_760
  const config = {
    maxSize: MAX_FILE_SIZE,
    allowedTypes: ['image/png', 'image/jpeg'],
  }

  const validateFile = (file: File) => {
    // validation logic
  }

  return <form>...</form>
}

// Good - Extracted outside component
const MAX_FILE_SIZE = 10_485_760

const UPLOAD_CONFIG = {
  maxSize: MAX_FILE_SIZE,
  allowedTypes: ['image/png', 'image/jpeg'],
} as const

function validateFileUpload(
  file: File,
  maxSize: number
): boolean {
  return file.size <= maxSize
}

export const SettingsForm = () => {
  return <form>...</form>
}
```

### Never Use useEffect for Data Fetching 🔴 Must

**Always use TanStack Query for data fetching** - never fetch data in `useEffect`.

```typescript
// ❌ NEVER DO THIS - Data fetching in useEffect
export const ProfilePage = ({ name }: { name: string }) => {
  const [profile, setProfile] = useState<Profile | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<Error | null>(null)
  
  useEffect(() => {
    let cancelled = false
    
    async function fetchProfile() {
      setLoading(true)
      try {
        const data = await getProfile(name)
        if (!cancelled) {
          setProfile(data)
          setError(null)
        }
      } catch (e) {
        if (!cancelled) setError(e as Error)
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    
    fetchProfile()
    return () => { cancelled = true }
  }, [name])
  
  if (loading) return <LoadingSpinner />
  if (error) return <ErrorMessage error={error} />
  return <ProfileView profile={profile} />
}

// ✅ ALWAYS DO THIS - Use TanStack Query
export const ProfilePage = ({ name }: { name: string }) => {
  const { data: profile, isLoading, error } = useQuery(getProfileQueryOptions(name))
  
  if (isLoading) return <LoadingSpinner />
  if (error) return <ErrorMessage error={error} />
  if (!profile) return null
  return <ProfileView profile={profile} />
}
```

**Why useEffect is problematic for data fetching:**
- ❌ **Waterfalls** - Dependencies cause sequential fetches
- ❌ **Race conditions** - React 18+ concurrent mode can race effects
- ❌ **No caching** - Same data fetched multiple times
- ❌ **Messy error handling** - Manual state management
- ❌ **No retry logic** - Must implement yourself
- ❌ **No stale data** - Can't show stale while revalidating

**TanStack Query solves all of these** - use it for ALL data fetching.

### useEffect Usage Policy (🟡 Default)

**Default rule**: In components, extract `useEffect` into a named custom hook to document intent and keep components readable.

**Valid use cases for useEffect:**
- DOM manipulation (focus, scroll, resize observers)
- Setting up/tearing down subscriptions
- Syncing with external systems (localStorage, WebSocket)
- Side effects triggered by prop/state changes

```typescript
// ❌ AVOID: Naked useEffect in component
export const ModalComponent = ({ isOpen }: { isOpen: boolean }) => {
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden'
    }
    return () => {
      document.body.style.overflow = ''
    }
  }, [isOpen])
  
  return <div>...</div>
}

// ✅ CORRECT: Extract into named hook
function useLockBodyScroll(isLocked: boolean) {
  useEffect(() => {
    if (isLocked) {
      document.body.style.overflow = 'hidden'
    }
    return () => {
      document.body.style.overflow = ''
    }
  }, [isLocked])
}

export const ModalComponent = ({ isOpen }: { isOpen: boolean }) => {
  useLockBodyScroll(isOpen)
  return <div>...</div>
}

export const ProfilePage = ({ name }: { name: string }) => {
  const [profile, setProfile] = useState<Profile | null>(null)
  
  useProfileData(name, setProfile)
  
  return <div>...</div>
}
```

**Why extract effects?**
- Hook name documents the purpose
- Component body stays focused on rendering
- Easier to reuse across components

**Allowed exceptions** (must stay trivial):
- ≤ 5 lines of code
- No async logic
- No domain or multi-branch logic  
  (trivial guards like `if (!ref.current) return` are fine)
- No external dependencies

```typescript
// ✅ Acceptable: Simple DOM sync effect
export const AutoFocusInput = () => {
  const ref = useRef<HTMLInputElement>(null)
  
  useEffect(() => {
    ref.current?.focus()
  }, [])
  
  return <input ref={ref} />
}
```

**If an effect grows beyond these constraints, extract it immediately.**

**Note**: This rule applies to components only. Inside custom hooks, `useEffect` is expected and does not need further extraction—that's where effects belong.

### Component Size and Complexity (🟢 Guideline)

**Split components based on complexity, not arbitrary line counts.**

**When to split:**
- ✅ Component has multiple concerns (data fetching + rendering + form logic)
- ✅ Logic is reusable across multiple parents
- ✅ Component is hard to understand due to complexity (not size)
- ✅ Different parts change for different reasons

**When NOT to split:**
- ❌ Component is mostly static JSX (navigation would take longer than reading)
- ❌ Split components are 50% type definitions and props drilling
- ❌ You're only splitting to hit a line count target

```typescript
// ❌ Over-split - Harder to follow, mostly definitions
const ProfileHeader = ({ name, avatar }: ProfileHeaderProps) => {
  return (
    <header className="flex items-center gap-4">
      <Avatar src={avatar} />
      <h1>{name}</h1>
    </header>
  )
}

// ✅ Good - Split when there's actual complexity
const ProfileRecordsEditor = ({ records, onChange }: Props) => {
  const [editMode, setEditMode] = useState(false)
  const { writeContractAsync } = useWriteContract()
  
  const handleSave = async () => {
    // 30+ lines of validation, encoding, transaction logic
  }
  
  return editMode ? <Editor /> : <Display />
}

const ProfilePage = ({ name }: ProfilePageProps) => {
  const { data: profile } = useQuery(getProfileQueryOptions(name))
  
  return (
    <div>
      {/* ✅ Static header stays inline - easy to read */}
      <header className="flex items-center gap-4">
        <Avatar src={profile.avatar} />
        <h1>{profile.name}</h1>
      </header>
      
      {/* ✅ Complex editor extracted - manages its own state and logic */}
      <ProfileRecordsEditor 
        records={profile.records}
        onChange={handleUpdate}
      />
    </div>
  )
}
```

**Rule of thumb**: If finding the split component takes longer than scanning the original, don't split it.

## Data Fetching with TanStack Query

### Query Structure

```typescript
import { useQuery, queryOptions } from '@tanstack/react-query'

// 1. Create the data fetching function
async function getProfile(name: string): Promise<Profile> {
  const response = await fetch(`/api/profiles/${name}`)
  if (!response.ok) throw new Error('Failed to fetch profile')
  return response.json()
}

// 2. Create query options factory
export const getProfileQueryOptions = (name: string) =>
  queryOptions({
    queryKey: ['profile', { name }],
    queryFn: () => getProfile(name),
  })
```

**Why no custom hook wrapper?**
- ✅ **Works with all query hooks** - `useQuery`, `useSuspenseQuery`, `useQueries`
- ✅ **Preloading in router loaders** - Can use options directly in `loader`
- ✅ **Customizable per use case** - Add `staleTime`, `enabled`, etc. in component
- ✅ **Simpler types** - No need to handle custom option overrides

### Query Key Patterns 🟡 Default

**Use object-based params for type-safe, invalidation-friendly keys:**

```typescript
// ✅ Good - Object params, easy to invalidate
queryKey: ['profile', { name }]

// Invalidate ALL profile queries
queryClient.invalidateQueries({ queryKey: ['profile'] })

// Invalidate specific profile
queryClient.invalidateQueries({
  queryKey: ['profile', { name: 'alice' }]
})
```

**Query Key Best Practices:**

1. ✅ **Object for params** - Enables partial matching for invalidation
2. ✅ **Named properties** - `{ name }` not just `name`
3. ✅ **Consider scope-based keys** - Group related queries for easier invalidation

```typescript
// ✅ Good - Object params, invalidation-friendly
queryKey: ['channels', { name: 'alice', includeBlocks: true }]

// ❌ Avoid - Positional params, hard to invalidate partially
queryKey: ['channels', name, includeBlocks]

// ❌ Avoid - Reversed order
queryKey: [name, 'channels']
```

### Using Queries in Components

**Standard pattern:**

```typescript
// ✅ Basic usage
export const ProfileCard = ({ name }: { name: string }) => {
  const { data, isLoading, error } = useQuery(getProfileQueryOptions(name))

  if (isLoading) return <LoadingMessage />

  if (error) {
    const message = error.message || 'Could not load profile'
    return <ErrorMessage title="Profile unavailable" description={message} />
  }

  if (!data) {
    return <ErrorMessage title="Profile unavailable" description="No data returned" />
  }

  return <ProfileDetails profile={data} />
}

// ✅ With custom options
export const LiveProfileCard = ({ name }: { name: string }) => {
  const { data, isLoading, error } = useQuery({
    ...getProfileQueryOptions(name),
    staleTime: 5000, // Refetch every 5s
    refetchInterval: 5000,
  })
  
  if (isLoading) return <LoadingSpinner />
  if (error) return <ErrorMessage title="Error" description={error.message} />
  if (!data) return null
  
  return <ProfileDetails records={data.records} />
}

// ✅ With suspense
export const SuspenseProfileCard = ({ name }: { name: string }) => {
  const { data, error } = useSuspenseQuery(getProfileQueryOptions(name))
  // No loading state needed - suspense handles it
  
  if (error) return <ErrorMessage error={error} />
  if (!data) return null
  
  return <ProfileDetails records={data.records} />
}

// ✅ Multiple queries with useQueries
export const MultiProfileCard = ({ names }: { names: string[] }) => {
  const queries = useQueries({
    queries: names.map(name => getProfileQueryOptions(name)),
  })
  
  return (
    <div>
      {queries.map((q, i) => {
        if (q.isLoading) return <LoadingSpinner key={names[i]} />
        if (q.error) return <ErrorMessage key={names[i]} error={q.error} />
        if (!q.data) return null
        return <ProfileCard key={names[i]} data={q.data} />
      })}
    </div>
  )
}

// ✅ Route component receives typed params from TanStack Router
export const Route = createFileRoute('/collections/$name/documents')({
  component: RecordsPage,
})

function RecordsPage() {
  const { name } = Route.useParams()
  return <ProfilePage name={name} />
}
```

**Key points**:
- ✅ Always check `isLoading`, `error`, and `!data` before using `data`
- ✅ Access error details via `error.message`

### Avoid Query Waterfalls 🟡 Default

**Don't run dependent queries in the same component** - move them to separate components.

```typescript
// ❌ AVOID - Waterfall queries in same component
export const ProfilePage = ({ name }: { name: string }) => {
  const { data: profile, isLoading: isLoadingProfile, error: profileError } = 
    useQuery(getProfileQueryOptions(name))
  
  // This waits for profile to load before fetching
  const { data: channels, isLoading: isLoadingChannels, error: channelsError } =
    useQuery({
      ...getChannelsQueryOptions(profile?.id),
      enabled: !!profile?.id, // Dependent query
    })
  
  // Now you have 4 states to manage: 2 loading, 2 errors
  if (isLoadingProfile || isLoadingChannels) return <LoadingSpinner />
  if (profileError || channelsError) return <ErrorMessage />
  
  return <div>{/* Complex state management */}</div>
}

// ✅ CORRECT - Split into separate components
export const ProfilePage = ({ name }: { name: string }) => {
  const { data: profile, isLoading, error } = useQuery(getProfileQueryOptions(name))
  
  if (isLoading) return <LoadingSpinner />
  if (error) return <ErrorMessage error={error} />
  if (!profile) return null
  
  // Pass profile to child component that handles channels
  return <ProfileWithChannels profile={profile} />
}

export const ProfileWithChannels = ({ profile }: { profile: Profile }) => {
  const { data: channels, isLoading, error } = useQuery(
    getChannelsQueryOptions(profile.id)
  )

  if (isLoading) return <LoadingSpinner />
  if (error) return <ErrorMessage error={error} />
  if (!channels) return null

  return <ChannelsView profile={profile} channels={channels} />
}
```

**Benefits of splitting**:
- ✅ **Clearer state management** - One query per component
- ✅ **Better loading UX** - Show profile while records load
- ✅ **Easier error handling** - Each error is specific to its data
- ✅ **Better composability** - Components are more reusable

### Handle Query States Independently 🟡 Default

**Don't group error or loading states** - handle each query separately.

```typescript
// ❌ AVOID - Grouped loading/error states
export const DashboardPage = () => {
  const { data: profile, isLoading: isLoadingProfile, error: profileError } = 
    useQuery(getProfileQueryOptions())
  const { data: names, isLoading: isLoadingNames, error: namesError } = 
    useQuery(getNamesQueryOptions())
  
  // This hides which data is loading/erroring
  if (isLoadingProfile || isLoadingNames) return <LoadingSpinner />
  if (profileError || namesError) return <ErrorMessage />
  
  return <Dashboard profile={profile} names={names} />
}

// ✅ CORRECT - Handle each query independently
export const DashboardPage = () => {
  const { data: profile, isLoading: isLoadingProfile, error: profileError } = 
    useQuery(getProfileQueryOptions())
  const { data: names, isLoading: isLoadingNames, error: namesError } = 
    useQuery(getNamesQueryOptions())
  
  return (
    <div>
      {/* Show profile section state independently */}
      {isLoadingProfile ? (
        <LoadingSpinner />
      ) : profileError ? (
        <ErrorMessage error={profileError} />
      ) : (
        <ProfileSection profile={profile} />
      )}
      
      {/* Show names section state independently */}
      {isLoadingNames ? (
        <LoadingSpinner />
      ) : namesError ? (
        <ErrorMessage error={namesError} />
      ) : (
        <NamesSection names={names} />
      )}
    </div>
  )
}
```

**Why this matters**:
- ✅ **Different errors mean different things** - Profile error ≠ names error
- ✅ **Show partial data** - Display profile even if names fails
- ✅ **Better UX** - User sees some content immediately
- ✅ **Specific error messages** - Tell user exactly what failed

### Use useQueries for Parallel Queries 🟡 Default

**For multiple parallel queries, use `useQueries`** - cleaner and more concise.

```typescript
// ❌ AVOID - Multiple parallel useQuery calls
export const MultiProfilePage = ({ names }: { names: string[] }) => {
  const profile1 = useQuery(getProfileQueryOptions(names[0]))
  const profile2 = useQuery(getProfileQueryOptions(names[1]))
  const profile3 = useQuery(getProfileQueryOptions(names[2]))
  
  // Verbose state management
  const isLoading = profile1.isLoading || profile2.isLoading || profile3.isLoading
  const errors = [profile1.error, profile2.error, profile3.error].filter(Boolean)
  
  if (isLoading) return <LoadingSpinner />
  if (errors.length > 0) return <ErrorMessage />
  
  return <div>...</div>
}

// ✅ CORRECT - Use useQueries
export const MultiProfilePage = ({ names }: { names: string[] }) => {
  const queries = useQueries({
    queries: names.map(name => getProfileQueryOptions(name)),
  })
  
  return (
    <div>
      {queries.map((query, i) => {
        if (query.isLoading) return <LoadingSpinner key={names[i]} />
        if (query.error) return <ErrorMessage key={names[i]} error={query.error} />
        if (!query.data) return null
        return <ProfileCard key={names[i]} data={query.data} />
      })}
    </div>
  )
}

// ✅ ALSO GOOD - Aggregate states when appropriate
export const MultiProfilePage = ({ names }: { names: string[] }) => {
  const queries = useQueries({
    queries: names.map(name => getProfileQueryOptions(name)),
  })
  
  const isLoading = queries.some(q => q.isLoading)
  const errors = queries.filter(q => q.error).map(q => q.error)
  const allData = queries.every(q => q.data) ? queries.map(q => q.data) : null
  
  if (isLoading) return <LoadingSpinner />
  if (errors.length > 0) return <ErrorList errors={errors} />
  if (!allData) return null
  
  return <ProfileList profiles={allData} />
}
```

**Benefits**:
- ✅ **Less verbose** - One hook instead of many
- ✅ **Dynamic** - Works with variable-length arrays
- ✅ **Type-safe** - Proper TypeScript inference
- ✅ **Consistent pattern** - Standard way to handle parallel queries

### File Organization for Queries

```
features/
└── profile/
    ├── hooks/
    │   ├── use-profile.ts      # getProfile + getProfileQueryOptions
    │   ├── use-channels.ts     # getChannels + getChannelsQueryOptions
    │   └── use-blocks.ts       # getBlocks + getBlocksQueryOptions
    └── components/
        └── ProfileCard.tsx      # useQuery(getProfileQueryOptions(...))
```

**File naming**: Keep `use*.ts` convention even though they export query options, not hooks. This maintains consistency and groups query-related code in the `hooks/` folder.

## Component Composition

### Composition Over Configuration

Build flexible components through composition:

```typescript
// Good - Composition
export const ProfilePage = ({ name }: { name: string }) => {
  const { data: profile } = useQuery(getProfileQueryOptions(name))
  
  return (
    <Card>
      <CardHeader>
        <Avatar src={profile.avatar} />
        <h1>{profile.name}</h1>
      </CardHeader>
      <CardBody>
        <ProfileRecords records={profile.records} />
      </CardBody>
      <CardFooter>
        <Button onClick={handleEdit}>Edit</Button>
      </CardFooter>
    </Card>
  )
}

// Avoid - Configuration props
export const ProfileCard = ({
  profile,
  showAvatar,
  showRecords,
  showEditButton,
  onEdit,
}: ProfileCardProps) => {
  return (
    <div>
      {showAvatar && <Avatar />}
      {showRecords && <Records />}
      {showEditButton && <Button onClick={onEdit} />}
    </div>
  )
}
```

### Using Base UI Primitives

```typescript
import { Dialog } from '@base-ui/react/dialog'

// Good - Compose Base UI primitives with custom styling
export const EditProfileDialog = ({ children }: { children: React.ReactNode }) => {
  return (
    <Dialog.Root>
      <Dialog.Trigger>Edit Profile</Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Backdrop className="fixed inset-0 bg-black/50" />
        <Dialog.Popup className="fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2">
          <Dialog.Title>Edit Profile</Dialog.Title>
          {children}
        </Dialog.Popup>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
```

### Render Props Pattern

```typescript
// Good - Render prop for flexibility
interface DataTableProps<T> {
  data: readonly T[]
  renderRow: (item: T) => React.ReactNode
  renderEmpty?: () => React.ReactNode
}

export const DataTable = <T,>({ data, renderRow, renderEmpty }: DataTableProps<T>) => {
  if (data.length === 0) {
    return renderEmpty?.() ?? <p>No data</p>
  }
  
  return (
    <table>
      <tbody>
        {data.map((item, index) => (
          <tr key={index}>{renderRow(item)}</tr>
        ))}
      </tbody>
    </table>
  )
}

// Usage
<DataTable
  data={profiles}
  renderRow={(profile) => (
    <>
      <td>{profile.name}</td>
      <td>{profile.address}</td>
    </>
  )}
/>
```

## Performance Guidelines

React 19 and our stack are fast by default. **Optimize only when proven necessary.**

### Philosophy (🟢 Guideline)

- **Measure before optimizing** - Use React DevTools Profiler to identify actual bottlenecks
- **Favor clarity over micro-optimizations** - Premature optimization obscures intent
- **Trust React's defaults** - React 19's concurrent features handle most scenarios
- **Optimize for bundle size first** - Smaller bundles → faster initial load

### When to Use Memoization

```typescript
// ❌ Premature optimization - No benefit
export const Button = ({ label }: { label: string }) => {
  const text = useMemo(() => label.toUpperCase(), [label]) // Unnecessary
  return <button>{text}</button>
}

// ✅ Good - Expensive calculation
export const NameValidator = ({ name }: { name: string }) => {
  const isValid = useMemo(() => {
    // Expensive regex or normalization
    return validateENSName(name) // Only recompute when name changes
  }, [name])
  
  return <div>{isValid ? '✓' : '✗'}</div>
}

// ✅ Good - Referential stability for dependencies
export const UserList = () => {
  const filters = useMemo(() => ({ active: true, verified: true }), [])
  const users = useQuery(getUsersQueryOptions(filters)) // Prevents refetch on re-render
  return <div>...</div>
}
```

### When to Use useCallback

```typescript
// ❌ Unnecessary - Simple inline handler
<button onClick={() => setCount(c => c + 1)}>Increment</button>

// ✅ Good - Passed to memoized child
const MemoizedChild = memo(Child)

export const Parent = () => {
  const handleSave = useCallback((data: FormData) => {
    // Save logic
  }, [])
  
  return <MemoizedChild onSave={handleSave} />
}
```

### Performance Checklist

Before optimizing, check these first:

1. **Code splitting** - Use route-based code splitting with TanStack Router and Vite
2. **Bundle analysis** - Remove unused dependencies (`pnpm why <package>`)
3. **Image optimization** - Use WebP, lazy loading, proper sizing
4. **Query management** - Set appropriate `staleTime` and `gcTime` for TanStack Query
5. **Avoid prop drilling** - Use composition instead of passing props through many layers

### Measuring Performance

```typescript
// Use React DevTools Profiler
import { Profiler } from 'react'

<Profiler id="UserList" onRender={(id, phase, actualDuration) => {
  console.log(`${id} (${phase}) took ${actualDuration}ms`)
}}>
  <UserList />
</Profiler>
```

**Key metrics:**
- **Initial render** - Should be < 100ms for most components
- **Re-render time** - Should be < 16ms (60fps)
- **Bundle size** - Keep route chunks under 200KB (gzipped)

## Error Boundaries

### When to Use Error Boundaries (🟡 Default)

Error boundaries catch rendering errors that escape normal error handling.

```typescript
import { ErrorBoundary } from 'react-error-boundary'

function NameError({ error, reset }: { error: Error; reset: () => void }) {
  return (
    <div role="alert" className="p-4">
      <h2>Something went wrong</h2>
      <pre className="text-sm">{error.message}</pre>
      <button onClick={reset}>Try again</button>
    </div>
  )
}

// Or use react-error-boundary for component-level boundaries
// within a page or layout
```

### Error Types

**Expected errors ≠ Rendering errors (Error Boundaries)**

| Error Type                | Handling                       | Example                       |
| ------------------------- | ------------------------------ | ----------------------------- |
| **Data fetching errors**  | TanStack Query error state     | API failure, network error    |
| **Business logic errors** | try-catch + early returns      | Invalid input, auth failure   |
| **Rendering errors**      | Error Boundary                 | Component crash, ref error    |
| **Unexpected errors**     | Error Boundary + logging       | Third-party lib bugs          |

### Error Boundary Implementation

```typescript
import { type FallbackProps } from 'react-error-boundary'

const ErrorFallback = ({ error, resetErrorBoundary }: FallbackProps) => {
  return (
    <div role="alert" className="p-4">
      <h2>Something went wrong</h2>
      <pre className="text-sm">{error.message}</pre>
      <button onClick={resetErrorBoundary}>Try again</button>
    </div>
  )
}

// Use at route or feature level
export const ProfilePage = () => {
  return (
    <ErrorBoundary FallbackComponent={ErrorFallback}>
      <ProfileContent />
    </ErrorBoundary>
  )
}
```

### Best Practices

- ✅ **Use route-level boundaries** - Isolate errors to specific routes
- ✅ **Log errors** - Send to monitoring service (Sentry, LogRocket)
- ✅ **Provide recovery** - Give users a way to retry or navigate away
- ✅ **Never swallow errors** - Always log or display them
- ❌ **Don't use for control flow** - Use try-catch for expected errors
- ❌ **Don't catch all errors globally** - Granular boundaries are better

## Styling with Tailwind CSS

### Utility-First Approach

```typescript
// Good - Utility classes
export const Button = ({ children }: { children: React.ReactNode }) => {
  return (
    <button className="rounded-sm bg-primary px-4 py-2 text-white hover:bg-primary/90">
      {children}
    </button>
  )
}
```

### Component Variants with CVA

Use `class-variance-authority` for type-safe variants:

```typescript
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/lib/utils'

const buttonVariants = cva(
  'inline-flex items-center justify-center rounded-sm font-medium transition-colors',
  {
    variants: {
      variant: {
        default: 'bg-primary text-white hover:bg-primary/90',
        outline: 'border border-input bg-background hover:bg-accent',
        ghost: 'hover:bg-accent hover:text-accent-foreground',
      },
      size: {
        default: 'h-9 px-4 py-2',
        sm: 'h-8 px-3',
        lg: 'h-10 px-6',
        icon: 'size-9',
      },
    },
    defaultVariants: {
      variant: 'default',
      size: 'default',
    },
  }
)

interface ButtonProps 
  extends React.ComponentProps<'button'>,
    VariantProps<typeof buttonVariants> {}

export const Button = ({ className, variant, size, ...props }: ButtonProps) => {
  return (
    <button
      className={cn(buttonVariants({ variant, size, className }))}
      {...props}
    />
  )
}
```

> **Note**: For complex multi-part components (e.g., Card with separate Header, Body, Footer styles), consider [tailwind-variants](https://www.tailwind-variants.org/) which extends CVA with slots and built-in class merging. For single-part components, CVA + `cn()` is sufficient.

### Conditional Classes and Class Helpers 🟡 Default

**Pick one approach (`clsx`/`cn` or `tw`/`twm`) and use it consistently across the codebase.**

#### Using `clsx` and `cn`

`clsx` merges class names conditionally. `cn` wraps `clsx` with `tailwind-merge` to resolve conflicting Tailwind utilities (e.g., `bg-red-500` vs `bg-blue-500`, `p-2` vs `p-4`).

```typescript
import { cn } from '@/lib/utils'
import clsx from 'clsx'

// Use clsx when you just need to merge classes without Tailwind conflict resolution
const simpleClasses = clsx('text-sm', isActive && 'font-bold')

// Use cn when you need Tailwind conflict resolution
export const Card = ({ isActive, className }: CardProps) => {
  return (
    <div
      className={cn(
        'rounded-lg border p-4',
        isActive && 'border-primary bg-primary/5',
        className
      )}
    >
      ...
    </div>
  )
}
```

**When to use `clsx` vs `cn`:**
- Use `clsx` when you just need to merge classes and don't have conflicting Tailwind utilities
- Use `cn` when composing classes that might conflict (e.g., different padding/margin values, different background colors)

#### Using `tw` and `twm` (Alternative)

`tw` and `twm` are custom utilities that provide a single API for all class name use cases. They handle single strings, template literals, and `clsx`-style function calls, choosing the most efficient method based on input.

```typescript
import { tw, twm } from '@/utils/tailwind'

// tw: Single string (returns directly, no clsx overhead)
<Button className={tw`px-4 py-2`} />

// tw: Tagged template with interpolations
<Button className={tw`px-4 py-2 ${isActive ? 'bg-primary' : ''}`} />

// tw: Function call form (clsx-compatible)
<Button className={tw('px-4 py-2', isActive && 'bg-primary')} />

// twm: Same as tw but with tailwind-merge for conflict resolution
<Button className={twm('px-4 py-2', isActive && 'bg-primary')} />
```

**About `tw` and `twm`:**
- `tw` is a unified utility that handles all use cases: single strings, template literals, and `clsx` function syntax
- **Performance-optimized**: Only invokes `clsx` when there are multiple inputs; single string inputs are returned directly
- Supports all `clsx` features: strings, arrays, objects, conditionals, nested structures
- `twm` adds `twMerge` for Tailwind-aware conflict resolution (equivalent to `cn` but with the same unified API)
- Prefer `tw` by default for the lightest helper; use `twm` when you need conflict resolution

**Note**: Autocomplete is the same for `clsx`, `cn`, `tw`, and `twm` - they're all configured identically in the Tailwind config. The benefit of `tw`/`twm` is the unified API that enables Tailwind autocomplete even for simple string assignments where you'd normally just use a plain string:

```typescript
// No intellisense
const myVar = "text-red-500"

// Intellisense enabled from var name
const className = "text-red-500"

// Intellisense manually enabled (works everywhere)
const myVar = tw`text-red-500`
```

**Benefits of consistency:**
- ✅ **One import** - Team knows where to look
- ✅ **Better IDE support** - Configure once
- ✅ **Easier onboarding** - One pattern to learn
- ✅ **Biome integration** - `useSortedClasses` works with `tw` helper

### Avoid Arbitrary Values 🟡 Default

**Use design system tokens instead of arbitrary values.** Only use arbitrary values when justified.

```typescript
// ❌ AVOID - Arbitrary values break design system
<div className="w-[37px] h-[23px] text-[#3B82F6]" />

// ✅ CORRECT - Use design tokens
<div className="size-9 text-blue-500" />
<div className="w-8 h-6 text-primary" />

// ✅ ACCEPTABLE - When design system doesn't have the value
<div 
  className="w-[120px]"
/>
```

**Why avoid arbitrary values:**
- ❌ **Breaks consistency** - Diverges from design system
- ❌ **Hard to maintain** - Magic numbers scattered everywhere
- ❌ **No type safety** - Easy to make typos
- ❌ **Larger bundle** - Each arbitrary value adds CSS

**When arbitrary values are justified:**
- ✅ Interfacing with third-party components with fixed dimensions
- ✅ Dynamic values from props/API that can't use tokens
- ✅ One-off exceptions that don't fit the design system

**Always ask**: "Could this use a design token instead?"

### Icon Sizing with Lucide

```typescript
import { CalendarIcon } from 'lucide-react'

// Good - Use Tailwind size classes
<CalendarIcon className="size-4" />
<CalendarIcon className="size-3.5" />
<CalendarIcon className="size-6" />

// Avoid - Don't use props
<CalendarIcon width={16} height={16} />
<CalendarIcon size={16} />
```

## Routing with TanStack Router

### File-Based Routing

The admin UI uses TanStack Router file-based routing in `app/src/routes/`:

```
src/routes/
├── __root.tsx                                      # Root providers and outlet
├── index.tsx                                       # /
├── _auth.tsx                                       # Pathless auth layout
├── _auth.login.tsx                                 # /login
├── _auth.setup.tsx                                 # /setup
├── _dashboard.tsx                                  # Pathless dashboard layout
├── _dashboard.overview.tsx                         # /overview
├── _dashboard.collections.tsx                      # /collections
├── _dashboard.collections.$name.tsx                # /collections/:name layout
├── _dashboard.collections.$name.documents.tsx      # /collections/:name/documents
└── _dashboard.collections.$name.documents.$docId.tsx
```

### Route Groups And Params

Use `_`-prefixed pathless routes for layouts that should not add URL segments, and `$` segments for dynamic params:

```
_dashboard.tsx
_dashboard.collections.$name.tsx
_dashboard.collections.$name.documents.$docId.tsx
```

### Page Components

```typescript
import { createFileRoute } from '@tanstack/react-router'

export const Route = createFileRoute('/_dashboard/collections/$name/search')({
  component: SearchPage,
})

function SearchPage() {
  const { name } = Route.useParams()

  return <CollectionSearch name={name} />
}
```

### Layouts

```typescript
import { Outlet, createFileRoute } from '@tanstack/react-router'

export const Route = createFileRoute('/_dashboard/collections/$name')({
  component: CollectionLayout,
})

function CollectionLayout() {
  const { name } = Route.useParams()

  return (
    <div>
      <CollectionHeader name={name} />
      <Outlet />
    </div>
  )
}
```

### Navigation

```typescript
import { Link, useNavigate } from '@tanstack/react-router'

export const Navigation = () => {
  const navigate = useNavigate()

  return (
    <nav>
      <Link to="/collections/$name" params={{ name: 'docs' }}>
        View collection
      </Link>
      <button
        type="button"
        onClick={() => {
          navigate({ to: '/collections/$name/documents', params: { name: 'docs' } })
        }}
      >
        Go to documents
      </button>
    </nav>
  )
}
```

## Accessibility

Use WCAG 2 guidelines wherever possible (prefer WCAG 2.2).

Quick references:
- WCAG overview: https://www.w3.org/WAI/standards-guidelines/wcag/
- How to Meet WCAG 2.2 (Quick Reference): https://www.w3.org/WAI/WCAG22/quickref/

### WCAG 2 Examples

#### Focus Visible (WCAG 2.4.7)

Never remove focus styles without a clear replacement. Prefer `:focus-visible` so mouse users don’t get distracting rings.

```typescript
// Good - visible keyboard focus ring
<button
  type="button"
  className="rounded-sm px-3 py-2 outline-none focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50"
>
  Save
</button>

// Avoid - removing outlines with no replacement
<button type="button" className="outline-none">
  Save
</button>
```

### Semantic HTML

Use semantic HTML elements:

```typescript
// Good
<nav>
  <ul>
    <li><a href="/">Home</a></li>
  </ul>
</nav>

<main>
  <article>
    <h1>Title</h1>
    <p>Content</p>
  </article>
</main>

// Avoid
<div className="nav">
  <div className="nav-list">
    <div><span onClick={goHome}>Home</span></div>
  </div>
</div>
```

### ARIA Attributes

```typescript
// Good - Accessible button
<button
  type="button"
  aria-label="Close dialog"
  aria-pressed={isPressed}
>
  <XIcon className="size-4" />
</button>

// Good - Accessible form
<form>
  <label htmlFor="name-input">
    ENS Name
  </label>
  <input
    id="name-input"
    type="text"
    aria-describedby="name-help"
    aria-invalid={hasError}
  />
  <p id="name-help">Enter your ENS name</p>
</form>
```

### Keyboard Navigation

Ensure all interactive elements are keyboard accessible:

```typescript
export const MenuItem = ({ onClick }: { onClick: () => void }) => {
  return (
    <button
      type="button"
      onClick={onClick}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault()
          onClick()
        }
      }}
    >
      Menu Item
    </button>
  )
}
```

## General TypeScript/JavaScript Coding Guidelines

### Core Patterns

**Use Explaining Variables** - Extract complex expressions into named variables for clarity:

```typescript
// Good
const isEligible = user.age >= 18 && user.hasVerifiedEmail && !user.isBanned
if (isEligible) { /* ... */ }

// Avoid
if (user.age >= 18 && user.hasVerifiedEmail && !user.isBanned) { /* ... */ }
```

**Avoid Magic Values** - Replace magic numbers and strings with named constants:

```typescript
// Good
const MAX_UPLOAD_SIZE = 10_485_760
const ALLOWED_IMAGE_TYPES = ['image/png', 'image/jpeg'] as const

// Avoid
if (file.size > 10485760) { /* ... */ }
```

**Prefer Array Methods** (🟢 Guideline) - Use `map`, `filter`, `reduce` for transformations:

```typescript
// Good - Declarative transformations
const activeUsers = users.filter(user => user.isActive)
const userNames = users.map(user => user.name)
const totalScore = users.reduce((sum, user) => sum + user.score, 0)

// Also Good - Loop with early exit
function findFirstExpired(items: Expirable[]): Expirable | null {
  for (const item of items) {
    if (item.expiresAt < Date.now()) return item
  }
  return null
}
```

**Immutable Transformations** - Create new values instead of mutating:

```typescript
// Good
const addItem = <T,>(items: readonly T[], newItem: T) => [...items, newItem]
const updateItem = <T extends { id: string }>(items: readonly T[], id: string, updates: Partial<T>) =>
  items.map(item => item.id === id ? { ...item, ...updates } : item)

// Avoid mutation
items.push(newItem) // ❌
```

## Code Formatting & Linting with Biome

### Why Biome?

Biome is a fast, unified toolchain for formatting and linting. It replaces ESLint and Prettier with a single tool:

- **Fast**: Written in Rust, 10-100x faster than ESLint
- **Unified**: One tool for formatting and linting
- **Zero config**: Works out of the box with sensible defaults
- **Import sorting**: Built-in `organizeImports` feature
- **IDE support**: First-class support in VSCode/Cursor

### Biome Configuration

Project uses Biome for formatting and linting. See `biome.jsonc` in the root.

**Key Settings:**
- **Formatter**: 2 spaces, double quotes, semicolons always
- **Linter**: All recommended rules + custom a11y rules
- **Auto-organize imports**: Enabled

### Formatting Rules

- **Indentation**: 2 spaces
- **Quotes**: Double quotes
- **Semicolons**: Always
- **Import Organization**: Automatic (type imports → external → internal)

```typescript
// Format example
const name = "alice";
const config = { timeout: 5000, retries: 3 };

// Imports auto-organized
import type { Profile } from "@bigrag/db";
import { useQuery } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
```

### Key Linting Rules

| Rule                           | Purpose                                       | Fix                               |
| ------------------------------ | --------------------------------------------- | --------------------------------- |
| `noExplicitAny`                | Avoid `any` types                             | Use `unknown` + type guards       |
| `noNonNullAssertion`           | Avoid `!` operator                            | Use `?.` or type guards           |
| `useButtonType`                | Explicit button types                         | Add `type="button"`               |
| `useKeyWithClickEvents`        | Keyboard accessibility                        | Add `onKeyDown` or use `<button>` |
| `noNestedComponentDefinitions` | Don't nest components                         | Define outside parent             |
| `noForEach`                    | Prefer `for...of` loops over `Array.forEach`  | Use `for...of`                    |
| `noUselessElse`                | Avoid unnecessary else blocks after returns   | Prefer early returns              |
| `noUnusedTemplateLiteral`      | Avoid template literals without interpolation | Use regular strings               |
| `noNegationElse`               | Avoid negated conditions with else branches   | Invert the condition              |

### Running Biome

```bash
pnpm biome check --write .  # Format + lint + fix
pnpm biome format --write . # Format only
```

### IDE Setup

Install Biome extension and set as default formatter. Enable format-on-save and organize imports.

### Ignoring Biome Rules

Use sparingly for legitimate cases:

```typescript
// Ignore specific line
// biome-ignore lint/suspicious/noExplicitAny: Third-party types unavailable
const data: any = externalLibrary.getData()
```

**When to ignore**: Third-party type issues, generated files, documented edge cases  
**When NOT to ignore**: To avoid fixing real issues, skip proper typing, suppress a11y warnings

## Summary

### Golden Rules

#### Architecture & Design

1. **Keep React thin** - Components for UI, not business logic (🔴 Must)
2. **Co-locate code** - Keep files next to their usage (🟢 Guideline)
3. **Be explicit** - Make data flow and dependencies clear (🟡 Default)
4. **Separation of concerns** - Business logic separate from presentation (🔴 Must)
5. **File naming conventions** - Use `*.handlers.ts`, `*.machine.ts`, `*.mock.ts` (🟡 Default)
6. **Mock data policy** - All mocks in `*.mock.ts` files, gated by dev flags (🟡 Default)

#### TypeScript & Code Quality

7. **Type everything** - Leverage TypeScript's strict mode (🔴 Must)
8. **No `any` types** - Use `unknown` or `Record<string, unknown>` for type-safe handling (🔴 Must)
9. **Use generics** - Preserve type information in utility functions (🟡 Default)
10. **Use readonly** - Enforce immutability at type level (🟡 Default)
11. **Discriminated unions** - For state management and variants (🟡 Default)

#### Functional Programming

12. **Pure functions** - Same input → same output, no side effects (🟡 Default)
13. **Immutability** - Transform data, don't mutate (🔴 Must)
14. **Prefer array methods** - Use `map`, `filter`, `reduce` (🟢 Guideline)
15. **Composition** - Build complex operations from simple ones (🟡 Default)

#### React Patterns

16. **Never useEffect for data fetching** - Always use TanStack Query (🔴 Must)
17. **Extract effects** - Extract `useEffect` in components to custom hooks (🟡 Default, ≤5 lines OK)
18. **Pattern match** - Use ts-pattern over conditionals (🟡 Default)
19. **Custom hooks for APIs** - Only for DOM/framework APIs, not business logic (🟡 Default)
20. **Component composition** - Build flexible UIs with composition (🟢 Guideline)
21. **Avoid prop drilling** - Use hooks/context for app state, props for local data (🟡 Default)

#### State Management & Data Fetching

22. **React state for UI** - Forms, toggles, simple caching
23. **XState for workflows** - Complex multi-step flows
24. **TanStack Query for async data** - Don't reinvent loading/error states with useState (🟡 Default)
25. **Avoid query waterfalls** - Split dependent queries into separate components (🟡 Default)
26. **Handle query states independently** - Don't group loading/error states with `||` (🟡 Default)
27. **Use useQueries for parallel queries** - More concise than multiple useQuery calls (🟡 Default)
28. **Object-based query keys** - Use singular object for params to enable partial invalidation (🟡 Default)

#### Performance & Reliability

29. **Measure before optimizing** - Use React DevTools Profiler (🟢 Guideline)
30. **Avoid premature memoization** - Only memoize when proven necessary (🟢 Guideline)
31. **Route-level error boundaries** - Catch rendering errors (🟡 Default)

#### Styling & UI

32. **Choose one class helper** - Use `cn` or `tw` consistently (🟡 Default)
33. **Avoid arbitrary values** - Use design tokens, not `w-[37px]` (🟡 Default)

#### Code Formatting

34. **Use Biome** - Format and lint with one tool (🔴 Must)
35. **Double quotes** - For string literals (🟢 Guideline)
36. **2-space indentation** - Consistent formatting (🟢 Guideline)
37. **Organize imports** - Let Biome handle import sorting (🟢 Guideline)

### Decision Framework

Ask yourself these questions when writing code:

#### Separation of Concerns
- Can this logic work outside React? → **Extract to helper function**
- Does this have side effects? → **Use `useEffect` in custom hook**

#### State Management
- Is this async data fetching? → **Use TanStack Query, not useState**
- Is this UI state or business state? → **React state vs XState**
- Does this need to be cached? → **Use TanStack Query**
- Is this a multi-step flow? → **Use XState machine**
- Creating a query key? → **Use object params for easy invalidation**

#### Type Safety
- Am I using `any`? → **Use `unknown` or proper types**
- Can this fail? → **Use try-catch or throw**
- Are there multiple variants? → **Use discriminated union**

#### Code Clarity
- Am I hiding complexity? → **Make it explicit**
- Is the data flow clear? → **Add types and explaining variables**
- Will new developers understand this? → **Document intent with names**

#### Error Handling
- Can this operation fail? → **Use try-catch or custom error classes**
- Do I need multiple error types? → **Use custom error classes with discriminated unions**
- Am I composing multiple operations? → **Chain async/await with try-catch**

#### Accessibility
- Can keyboard users access this? → **Add keyboard handlers**
- Is this element semantic? → **Use proper HTML elements**
- Are labels associated? → **Connect labels to inputs**

### Common Pitfalls to Avoid

#### ❌ Anti-Patterns

1. **Business logic in components** - Extract to helpers
2. **Data fetching in useEffect** - Use TanStack Query
3. **Naked `useEffect` in components** - Create custom hooks
4. **Query waterfalls in one component** - Split into separate components
5. **Grouping query loading/error states** - Handle independently
6. **Using `any` type** - Use `unknown` or `Record<string, unknown>`
7. **Losing type information** - Use generics to preserve types
8. **Mutating data** - Use immutable transformations
9. **Swallowing errors silently** - Always handle or rethrow
10. **Non-null assertions (`!`)** - Use type guards or optional chaining
11. **Complex nested conditionals** - Use pattern matching
12. **Magic numbers and strings** - Extract to named constants
13. **Direct dependency imports** - Use dependency injection

#### ✅ Best Practices

1. **Pure functions** - Explicit inputs and outputs
2. **Discriminated unions** - For type-safe state management
3. **Custom error classes** - For typed error handling
4. **Pattern matching** - For conditional logic
5. **Component composition** - Build flexible UIs
6. **Explaining variables** - Clarify complex expressions
7. **readonly modifiers** - Enforce immutability
8. **Custom error classes** - Typed errors for pattern matching
9. **Dependency injection** - Pass dependencies as parameters

## Python Backend

Rules for the `api/` codebase. Python 3.12+, FastAPI, asyncpg, Pydantic v2.

### File-Level Rules

Every Python file must start with future annotations:

```python
from __future__ import annotations
```

Package boundary modules that intentionally re-export symbols define `__all__`:

```python
__all__ = ["EventBus", "IngestionEvent", "event_bus"]
```

Never use `print()` in production code. Use structlog:

```python
from bigrag.logging import get_logger

logger = get_logger("bigrag.services.queue")

# Structured key-value pairs, not f-strings in logger calls
logger.info("job complete", job_id=job_id, chunks=total, elapsed=round(elapsed, 2))
```

### Naming

| Element | Convention | Example |
|---------|-----------|---------|
| Functions, variables | `snake_case` | `get_collection`, `total_chunks` |
| Classes | `PascalCase` | `EventBus`, `IngestionJob` |
| Constants | `UPPER_SNAKE_CASE` | `QUEUE_KEY`, `DEFAULT_TIMEOUT` |
| Private | `_leading_underscore` | `_cache`, `_process_job` |
| Files | `snake_case.py` | `event_bus.py`, `redis_cache.py` |
| Pydantic request models | `*Request` | `CreateCollectionRequest` |
| Pydantic response models | `*Response` | `CollectionResponse` |

### Type Annotations

Public APIs, service boundaries, and non-trivial helpers must have type annotations on parameters and return values. Route handlers must type parameters and declare `response_model` or `response_class`; return annotations are preferred when they add information beyond the decorator. Small framework callbacks may use the framework's conventional signature when annotation would add noise:

```python
# GOOD
async def get_or_404(name: str) -> dict:
    ...

def build_request_kwargs(job: dict) -> dict[str, Any]:
    ...

# BAD - missing return type
async def get_or_404(name: str):
    ...
```

Use modern union syntax:

```python
# GOOD
def connect(url: str | None = None) -> None: ...
endpoint_url: str | None

# BAD
from typing import Optional
def connect(url: Optional[str] = None) -> None: ...
```

Use lowercase generics:

```python
# GOOD
items: list[str]
config: dict[str, Any]
ids: set[int]

# BAD
from typing import List, Dict, Set
items: List[str]
```

### Imports

Order: stdlib, third-party, local. Enforced by ruff `I` rule.

```python
from __future__ import annotations

import asyncio
import uuid
from pathlib import Path

import orjson
from fastapi import APIRouter, Depends, HTTPException

from bigrag.config import settings
from bigrag.database import db
from bigrag.services.event_bus import event_bus
```

Prefer deferred imports for heavy or circular dependencies:

```python
async def _process_job(self, worker_id: int, job: IngestionJob) -> None:
    # Import at use-site to avoid circular imports and speed up module loading
    from bigrag.services.vector_store import vector_store
```

### Error Handling

Domain exceptions live in `exceptions.py`. Services raise domain exceptions, never `HTTPException`:

```python
# exceptions.py
class BigRAGError(Exception): ...
class NotFoundError(BigRAGError):
    def __init__(self, resource: str, identifier: str): ...
class ConflictError(BigRAGError): ...
class ValidationError(BigRAGError): ...
```

Exception handlers in `main.py` translate domain errors to HTTP:

```python
# main.py
@app.exception_handler(NotFoundError)
async def not_found_handler(request, exc):
    return JSONResponse(status_code=404, content={"detail": str(exc)})
```

Routers may raise `HTTPException` directly for HTTP-specific concerns (auth, content-type), but services must never import it:

```python
# GOOD - router layer
@router.post("")
async def create_collection(body: CreateCollectionRequest):
    existing = await db.fetchrow("SELECT id FROM collections WHERE name = $1", body.name)
    if existing:
        raise HTTPException(status_code=409, detail="Collection already exists")

# BAD - service layer raising HTTPException
class IngestionQueue:
    async def enqueue(self, job):
        if depth >= max_depth:
            raise HTTPException(status_code=429)  # Don't do this
```

### Pydantic Models

Use `Field()` with constraints aggressively:

```python
class CreateCollectionRequest(BaseModel):
    name: str = Field(min_length=1, max_length=128, pattern=r"^[a-zA-Z][a-zA-Z0-9_]*$")
    description: str = ""
    chunk_size: int = Field(default=512, ge=64, le=10000)
    chunk_overlap: int = Field(default=50, ge=0, le=5000)

    @model_validator(mode="after")
    def validate_overlap(self):
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("chunk_overlap must be less than chunk_size")
        return self
```

Keep request and response models separate. Never reuse the same model for both directions:

```python
# GOOD - separate models
class CreateCollectionRequest(BaseModel):
    name: str
    description: str = ""

class CollectionResponse(BaseModel):
    id: str
    name: str
    document_count: int
    created_at: datetime
```

### Service Layer Architecture

Use the Strategy pattern with abstract base classes for pluggable implementations:

```python
class EmbeddingModel(ABC):
    @abstractmethod
    async def embed(self, texts: list[str], *, input_type: str = "document") -> list[list[float]]: ...

    @property
    @abstractmethod
    def dimension(self) -> int: ...

class OpenAIEmbedding(EmbeddingModel): ...
class CohereEmbedding(EmbeddingModel): ...
```

Use the Factory pattern with caching for model selection:

```python
_models: dict[str, EmbeddingModel] = {}

def get_embedding_model(provider: str, model_name: str, ...) -> EmbeddingModel:
    cache_key = f"{provider}:{model_name}:{key_hash}"
    if cache_key in _models:
        return _models[cache_key]
    model = _create_model(provider, model_name, ...)
    _models[cache_key] = model
    return model
```

## FastAPI Patterns

### Route Handlers

Always use `async def`. Always set `response_model` on JSON endpoints. Streaming, redirect, and file-response endpoints should instead declare the appropriate response class or return a concrete `Response`. Use `Depends()` for shared concerns:

```python
@router.get("", response_model=CollectionListResponse)
async def list_collections(
    name: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    _: dict = Depends(get_current_user),
):
    ...
```

Path parameters for resource identity, query parameters for filtering:

```python
# GOOD
GET /v1/collections/{name}/documents?status=ready&limit=50

# BAD
GET /v1/collections?name=mydata&action=list_documents&status=ready
```

### Lifespan Management

Use the FastAPI lifespan context manager for startup/shutdown. Initialize services in order of dependency:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: connect in dependency order
    await db.connect(s.database_url)
    await redis_cache.connect(s.redis_url)
    await event_bus.connect(s.redis_url)
    await ingestion_queue.connect(s.redis_url)
    await ingestion_queue.start(db=db)

    yield

    # Shutdown: close in reverse order
    await ingestion_queue.stop()
    await event_bus.close()
    await redis_cache.close()
    await db.close()
```

### Dependency Injection

Store service instances on `app.state` during lifespan. Access via `Request`:

```python
# deps.py
def get_db(request: Request) -> Database:
    return request.app.state.db

# router
@router.get("/health/ready")
async def readiness(request: Request):
    db = request.app.state.db
```

For cross-cutting concerns (auth, validation), use `Depends()`:

```python
from bigrag.middleware.auth import get_current_user

@router.post("", response_model=CollectionResponse)
async def create_collection(
    body: CreateCollectionRequest,
    _: dict = Depends(get_current_user),
):
    ...
```

## Database & Async Patterns

### Never Block the Event Loop

Never call blocking I/O inside `async def`. Use `asyncio.to_thread()` for blocking libraries:

```python
# GOOD - offload blocking vector-store client call
result = await asyncio.to_thread(self.client.search, collection_name, data, ...)

# GOOD - offload blocking Docling conversion
result = await asyncio.to_thread(_write_and_convert)

# BAD - blocking call in async function
result = self.client.search(collection_name, data, ...)  # blocks event loop
```

### Timeouts on All External Calls

Every external call (HTTP, database, Redis, embeddings) must have a timeout:

```python
# GOOD
result = await asyncio.wait_for(model.embed(texts), timeout=30)
resp = await asyncio.wait_for(s3.get_object(Bucket=bucket, Key=key), timeout=120)

# BAD - no timeout, can hang forever
result = await model.embed(texts)
```

### Concurrency Control

Use `asyncio.Semaphore` to limit concurrent operations:

```python
sem = asyncio.Semaphore(10)

async def _download_and_ingest(obj: dict) -> None:
    async with sem:
        resp = await s3.get_object(Bucket=bucket, Key=key)
        content = await resp["Body"].read()
        await _ingest_file(content)
```

Use `asyncio.gather()` for parallel I/O, but always handle per-task errors:

```python
async def _download(obj: dict) -> None:
    try:
        ...
    except asyncio.CancelledError:
        raise  # let cancellation propagate
    except Exception as e:
        logger.warning("download failed", key=obj["Key"], error=str(e))
        skipped += 1

await asyncio.gather(*(_download(o) for o in objects))
```

### SQL Safety

Always use parameterized queries. Never interpolate user input into SQL:

```python
# GOOD
row = await db.fetchrow("SELECT * FROM collections WHERE name = $1", name)

# BAD - SQL injection risk
row = await db.fetchrow(f"SELECT * FROM collections WHERE name = '{name}'")
```

Exception: trusted internal values like interval strings can be interpolated with f-strings if validated:

```python
# OK - interval is from a hardcoded list, not user input
interval = "24 hours"  # from ["24 hours", "7 days", "30 days"]
await db.fetchrow(f"... AND created_at > now() - interval '{interval}'", collection_name)
```

### Background Tasks

Use `asyncio.create_task()` for fire-and-forget work. Always store the task reference:

```python
# GOOD
task = asyncio.create_task(_run_job(job))
_tasks[job_id] = task
task.add_done_callback(lambda _: _tasks.pop(job_id, None))

# BAD - task can be garbage collected
asyncio.create_task(_run_job(job))  # no reference stored
```

## Caching with Redis

All caches go through `redis_cache` module. Never use in-memory dicts for caching:

```python
from bigrag.services import redis_cache

# Read
cached = await redis_cache.get("collection:mydata")

# Write with TTL
await redis_cache.set("collection:mydata", data, ttl=30)

# Invalidate
await redis_cache.delete("collection:mydata")
await redis_cache.delete_pattern("analytics:*")
```

Key naming convention: `{domain}:{identifier}`. Examples:

| Key | TTL | Purpose |
|-----|-----|---------|
| `collection:{name}` | 30s | Collection metadata |
| `health:embedding:{provider}` | 60s | Embedding provider health |
| `webhooks:active` | 60s | Active webhook list |
| `stats:platform` | 15s | Platform-wide stats |
| `analytics:{collection}` | 5min | Collection query analytics |

Always invalidate on mutations:

```python
async def update_collection(name: str, body: UpdateCollectionRequest):
    row = await db.fetchrow(sql, *params)
    await invalidate_collection_cache(name)  # invalidate after write
    return row
```

For event streaming, use Redis pub/sub (not in-memory queues):

```python
# Publishing
event_bus.publish(IngestionEvent(
    document_id=doc_id,
    step="complete",
    status="complete",
    message="Done",
    collection_name=collection_name,
))

# Subscribing (collection-level)
q = event_bus.subscribe(f"collection:{name}")
```

## TypeScript SDK Design

The SDK follows the resource namespace pattern (like Stripe, Anthropic):

### Client Architecture

```typescript
// Transport layer (handles HTTP, retries, auth)
export class BigRAGCore implements RequestClient {
  readonly apiKey: string;
  readonly baseUrl: string;
  readonly timeout: number;
  readonly maxRetries: number;
}

// Client with resource namespaces
export class BigRAG extends BigRAGCore {
  readonly collections: CollectionsResource;
  readonly documents: DocumentsResource;
  readonly queries: QueryResource;
}
```

### Resource Classes

Resources receive a `RequestClient` interface, not the concrete class. Public method names and types should be self-explanatory; keep detailed API guidance in the docs site instead of JSDoc under `sdks/typescript/src/`:

```typescript
export class CollectionsResource {
  constructor(private readonly _client: RequestClient) {}

  list(options?: CollectionListOptions): Promise<CollectionListResponse> {
    return this._client._request("GET", "/v1/collections", { params });
  }
}
```

### Error Hierarchy

Map HTTP status codes to typed error classes:

```typescript
export class BigRAGError extends Error {}
export class APIError extends BigRAGError {
  readonly status: number;
  readonly code: string | undefined;
}
export class BadRequestError extends APIError {}     // 400
export class AuthenticationError extends APIError {}  // 401
export class NotFoundError extends APIError {}        // 404
export class RateLimitError extends APIError {}       // 429
export class InternalServerError extends APIError {}  // 500

// Connection-level errors (no HTTP status)
export class APIConnectionError extends BigRAGError {}
export class APITimeoutError extends BigRAGError {}
```

### Retry Policy

Retry on connection errors, 5xx responses, and infrastructure 429 responses. Never retry timeouts:

```typescript
// Retryable
if (response.status >= 500 && attempt < this.maxRetries) continue;
if (response.status === 429 && attempt < this.maxRetries) continue;

// Not retryable - fail immediately
if (lastError.name === "TimeoutError" || lastError.name === "AbortError") {
  throw new APITimeoutError(lastError.message);
}
```

### SSE Streaming

Use async generators for SSE endpoints:

```typescript
async *streamEvents(name: string): AsyncGenerator<ProgressEvent> {
  const response = await this._client._fetch(url, { method: "GET", headers });
  if (!response.ok) throw errorForStatus(response.status, response.statusText);
  yield* parseSSEStream(response);
}
```

## References

### Core Concepts

- **Functional-Light JS**: [GitHub - getify/Functional-Light-JS](https://github.com/getify/Functional-Light-JS)
- **Clean Code JavaScript**: [GitHub - ryanmcdermott/clean-code-javascript](https://github.com/ryanmcdermott/clean-code-javascript)
- **SOLID Principles in TypeScript**: [LogRocket Blog](https://blog.logrocket.com/applying-solid-principles-typescript/)

### Libraries & Tools

- **FastAPI**: [fastapi.tiangolo.com](https://fastapi.tiangolo.com/)
- **Pydantic v2**: [docs.pydantic.dev](https://docs.pydantic.dev/)
- **asyncpg**: [magicstack.github.io/asyncpg](https://magicstack.github.io/asyncpg/)
- **structlog**: [structlog.org](https://www.structlog.org/)
- **Ruff**: [docs.astral.sh/ruff](https://docs.astral.sh/ruff/)
- **React 19**: [react.dev](https://react.dev)
- **TypeScript**: [typescriptlang.org](https://www.typescriptlang.org/)
- **Vite**: [vite.dev](https://vite.dev/)
- **TanStack Router**: [tanstack.com/router](https://tanstack.com/router/latest)
- **TanStack Query**: [tanstack.com/query](https://tanstack.com/query/latest)
- **Tailwind CSS**: [tailwindcss.com](https://tailwindcss.com/)
- **Base UI**: [base-ui.com](https://base-ui.com/)
- **Biome**: [biomejs.dev](https://biomejs.dev/)

### Internal Documentation

- `CLAUDE.md` - Main development guidelines
- `docs/CODING_GUIDELINES.md` - Coding philosophy

---

*This style guide is a living document. As bigRAG evolves, so should these guidelines. When in doubt, follow existing patterns in the codebase and prioritize clarity and maintainability.*
