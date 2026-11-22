# Project Naming Conventions

**Status:** Working standard for new and revised project work  
**Applies to:** The I-ITSM project, including its frontend and any future domain, API, or persistence code  
**Companion document:** [Project overview](./PROJECT_OVERVIEW.md)

This document defines how to choose one clear, consistent name for each project concept. Apply it to new work first. Rename existing files or symbols only as part of a deliberate change that updates every import, reference, test, and relevant document.

## 1. The naming test

Before choosing a name, answer these questions in order:

1. **What is it?** Use the project’s canonical domain term.
2. **What does it do or represent?** Add a specific noun or verb that describes its responsibility.
3. **What scope does it belong to?** Add a feature, page, or layer qualifier only when needed to distinguish it.
4. **Which case does its kind require?** Follow the table below.
5. **Is the name already used for the same concept?** Reuse it; do not introduce a synonym.

Prefer the shortest name that answers those questions without relying on surrounding context. A name should be understandable in search results, imports, logs, tests, and code review.

## 2. Canonical project vocabulary

Use these terms consistently in code, UI, tests, documentation, and data:

| Concept | Canonical term | Guidance |
|---|---|---|
| The product | **Intelligent IT Service Management & Incident Resolution System (I-ITSM)** | Use the full name on first mention in formal documents; use **I-ITSM** afterwards. |
| A reported IT disruption or unexpected service issue | **incident** | Use `incident` in identifiers and user-facing language. Do not call the same record a `ticket`, `case`, `issue`, or `request`. |
| A person reporting an incident | **employee** | Use `reporter` only for the incident’s reporter relationship or field. |
| A person investigating or resolving incidents | **technician** | `support engineer` may be used in explanatory prose, but code and data use `technician`. |
| A person configuring and monitoring the system | **administrator** | Use `IT manager` only when that is a distinct, explicitly modeled role. |
| A business or technical system affected by an incident | **service** | Distinguish it from the application itself where needed: `affectedService`. |
| A response and resolution commitment | **SLA** / **SLA policy** | Expand SLA to “Service Level Agreement” on first use in formal prose. |
| A recorded change or action in incident history | **audit event** | Use `auditLog` for a collection or view, not as a synonym for the event itself. |
| The complete incident process | **incident lifecycle** | Use the lifecycle sequence defined in the project overview. |

Avoid inventing abbreviations, alternate spellings, or shortened forms such as `inc`, `tech`, `usr`, and `svc` in names. Established terms from libraries and protocols (for example, `URL`, `HTTP`, and `SLA`) are acceptable.

## 3. Case and format by artifact

| Artifact | Convention | Example |
|---|---|---|
| React component, page component, TypeScript class | `PascalCase`; singular concept | `IncidentDetailsPage`, `Incident`, `SlaPolicy` |
| TypeScript type, interface, or type alias | `PascalCase`; name the modeled concept | `IncidentSummary`, `TechnicianAssignment` |
| Enum type, if one is justified | `PascalCase` singular | `IncidentStatus` |
| Function, method, hook, local variable, parameter | `camelCase`; functions start with an action when applicable | `calculateIncidentPriority`, `useIncidentFilters`, `selectedIncident` |
| React event handler | `handle` + event/action + context | `handleIncidentSubmit`, `handlePriorityChange` |
| Callback prop | `on` + event/action | `onIncidentSelect`, `onStatusChange` |
| Module-level constant | `UPPER_SNAKE_CASE` only for fixed configuration or domain constants | `DEFAULT_PAGE_SIZE`, `MAX_INCIDENT_DESCRIPTION_LENGTH` |
| Boolean | Phrase as a true/false question or state | `isAssigned`, `hasSlaViolation`, `canCloseIncident` |
| React component file | Match exported component in `PascalCase.tsx` | `IncidentDetailsPage.tsx` |
| Non-component TypeScript module | `kebab-case.ts` | `incident-priority.ts`, `sla-policy.ts` |
| React component stylesheet | Match component with `.module.css` | `IncidentDetailsPage.module.css` |
| Shared/global stylesheet | `kebab-case.css`; name its scope | `index.css`, `theme.css`, `print-layout.css` |
| CSS class | `kebab-case`; use the component structure below | `.incident-card__priority-badge` |
| Folder | `kebab-case`; use plural for collections of peer features/items | `incident-management/`, `components/`, `pages/` |
| Image, icon, font, or other static asset | `kebab-case` plus an accurate extension | `incident-empty-state.svg`, `brand-mark.svg` |
| Java package | Lowercase dot-separated path, no abbreviations | `com.example.itsm.incidents` |
| Java class, record, interface, enum | `PascalCase`; singular concept | `Incident`, `IncidentReport`, `IncidentStatus` |
| Java method, field, parameter, local variable | `camelCase`; methods start with an action when applicable | `assignTechnician`, `responseDeadline` |
| Java constant | `UPPER_SNAKE_CASE` | `DEFAULT_PAGE_SIZE` |
| Python module or package | `snake_case`; concise domain name | `incident_priority.py`, `incidents/` |
| Python class, model, form, serializer | `PascalCase`; singular concept | `Incident`, `IncidentSerializer`, `SlaPolicy` |
| Python function, method, variable, parameter | `snake_case`; functions start with an action when applicable | `assign_technician`, `response_deadline` |
| Python constant | `UPPER_SNAKE_CASE` | `DEFAULT_PAGE_SIZE` |
| Test file | Source name plus `.test` before extension | `IncidentDetailsPage.test.tsx`, `incident-priority.test.ts` |
| Route path | Lowercase, plural resource nouns, kebab-case segments | `/incidents`, `/sla-policies` |
| Route parameter | `:singularResourceId` | `/incidents/:incidentId` |
| User-visible label | Plain language; spell out terms unless the acronym is familiar to the audience | `Affected service`, `SLA deadline` |

### TypeScript and React

- Name exported components for what they render, not how they are implemented: `IncidentList`, `IncidentDetailsPage`.
- Use `Page` for route-level screens, `Dialog` for modal workflows, `Form` for data-entry surfaces, and `Table` or `List` only when that is the actual presentation.
- Name a custom hook `use` + the capability or state it exposes: `useIncidentDetails`, `useSlaCountdown`.
- Name a component prop interface `<ComponentName>Props`: `IncidentCardProps`.
- Prefer precise domain types over generic names such as `Data`, `Info`, `Item`, `Record`, or `Response`. Use `IncidentSummary`, `IncidentFilter`, or `IncidentApiResponse` when those distinctions matter.
- Use `interface` or `type` following the project’s existing and library-compatible style; do not create both for the same shape.
- Prefer string-literal union types for a small, fixed set of serializable values unless a real need calls for a TypeScript `enum`. Keep the value spelling stable and separate display text from stored values.
- Use `id` for a local entity identifier only when the entity is unambiguous in that scope; otherwise use a specific name such as `incidentId` or `technicianId`.
- Name date/time values for their meaning and unit: `createdAt`, `responseDeadline`, `elapsedMinutes`. Avoid ambiguous `date`, `time`, or numeric fields without units.
- Name errors by the failed operation or domain condition: `IncidentNotFoundError`, `SlaPolicyValidationError`.

### Java (if retained as part of the deliverable)

- Use one public top-level type per file and name the file exactly after that type: `Incident.java` contains `Incident`.
- Use `PascalCase` for classes, records, interfaces, and enum types; use singular domain names (`Incident`, `Technician`, `SlaPolicy`).
- Use `camelCase` for methods and fields. Give methods action names (`calculatePriority`, `assignTechnician`) and booleans question/state names (`isAvailable`, `hasOpenIncidents`).
- Use lowercase package segments organized by domain, not default-package classes for production code. Example: `com.example.itsm.incidents`.
- Use `UPPER_SNAKE_CASE` for `static final` constants whose values are truly constant. Do not make ordinary fields look like constants.
- Keep enum type names singular and values meaningful (`IncidentStatus.OPEN`); if values are serialized or persisted, define and preserve an explicit stable representation instead of relying on display text.
- Use the same canonical domain terms and lifecycle vocabulary as the TypeScript application. Avoid introducing a second Java-only vocabulary.

### Python and Django

- Use `snake_case` for Python modules, packages, functions, methods, variables, and Django app packages; use `PascalCase` for classes, models, forms, serializers, and exception types.
- Name a Django app for a cohesive domain capability, in plural where it represents a collection (for example, `incidents`, `technicians`, or `notifications`). Avoid generic app names such as `core` unless the contents are genuinely shared infrastructure.
- Keep Django model names singular (`Incident`) and let Django derive plural database table names unless a deliberate `db_table` override is required.
- Name model fields for their meaning and use Django/Python conventions (`created_at`, `assigned_technician`). Use explicit foreign-key names such as `reporter` and `assigned_technician`; do not encode a redundant `_id` in a Django relation field name.
- Name serializers, forms, views, and tests for the represented domain and responsibility (`IncidentSerializer`, `IncidentCreateView`, `test_assigns_available_technician`).
- Use resource-oriented plural API paths and canonical domain terms, such as `/api/incidents/` and `/api/sla-policies/`. Keep external JSON field casing consistent with the chosen API convention and document any translation from Python `snake_case`.
- Use `UPPER_SNAKE_CASE` for module-level constants and Django settings. Keep environment-specific settings and secret values out of source control.
- Keep Python domain rules and replaceable policies (such as assignment strategies) separate from HTTP request handling where practical. Do not add layers without a concrete responsibility.
- Use the same incident, technician, priority, and lifecycle terminology across Python, TypeScript, API payloads, tests, and documentation.

### CSS

- Use CSS Modules for new component-specific stylesheets when the component owns the styles. Keep genuinely global resets, typography, and design tokens in global stylesheets.
- Use a small BEM-style structure within a component: `block__element--modifier`. Example: `.incident-card__status--overdue`.
- A block is a component or a clearly scoped region. Elements describe parts of that block; modifiers describe a meaningful variation or state.
- Use state prefixes consistently: `is-` for a state (`is-selected`, `is-loading`); `has-` for a present condition (`has-validation-error`). Prefer the component’s state/props over manually toggling unrelated classes.
- Name classes for meaning, not implementation or appearance: prefer `.incident-priority-badge` to `.red-text`, `.left-box`, or `.large-margin`.
- Use design tokens for repeated colors, spacing, and typography; name tokens by role, such as `--color-priority-critical` or `--space-section`, rather than by incidental appearance.
- Avoid IDs for styling, element selectors that reach into unrelated components, and abbreviations whose meaning is not obvious.

### Files, folders, and assets

- Keep a component’s implementation, styles, and tests together when that matches the surrounding feature structure. A stylesheet and test must clearly identify their owning component.
- Use **feature-first** names for feature areas: `features/incidents/`, `features/technicians/`, and `features/sla/`. Keep shared application-wide building blocks in clearly named shared folders.
- Put reusable UI in `components/`; route-level screens in `pages/`; shared static files in `assets/`. Do not create a folder for a single file without a clear organizational benefit.
- Give assets names that identify both subject and purpose when that distinction is useful: `brand-mark.svg`, `login-illustration.svg`, `incident-empty-state.svg`.
- Do not use names such as `new.svg`, `final2.svg`, `image1.png`, `test.css`, `temp.ts`, or names containing personal initials.
- Use a deliberate version in an asset name only when multiple versions must coexist, not as a substitute for replacing an outdated file.

### Domain processes, API, and persistence

- Name operations with an action followed by the domain object: `createIncident`, `assignTechnician`, `resolveIncident`, `closeIncident`.
- Use a process/workflow noun for a coordinated multi-step process: `incidentLifecycle`, `technicianAssignment`, `slaMonitoring`. Reserve `Strategy` for a replaceable implementation of a decision algorithm, such as `LoadBasedAssignmentStrategy`.
- Name domain events in past tense because the event describes something that happened: `IncidentReported`, `TechnicianAssigned`, `IncidentResolved`. Include the entity in the event name.
- If an API is introduced, use resource-oriented plural paths and the same domain terms as the UI: `/incidents`, `/technicians`, `/sla-policies`. Use the same field names across request and response models unless a documented boundary requires translation.
- If a database is introduced, use `snake_case` for table and column names, plural table names for collections (`incidents`, `technicians`), and explicit foreign-key names (`reporter_id`, `assigned_technician_id`). Keep database naming separate from TypeScript casing.
- Do not encode UI labels, colors, or translated text as a stored domain value. For example, store a stable priority value and map it to a display label and visual treatment.
- Keep process names, status values, route names, type names, and documentation aligned to the same canonical vocabulary.

### Tests and developer-facing process names

- Name a test after the behavior and condition it verifies: `assigns an available technician when an incident is created`.
- Use `describe` blocks for the unit or capability and `it`/`test` cases for observable behavior. Avoid test titles such as `works`, `test 1`, or a restatement of the function name alone.
- Name test data after its role: `criticalPaymentIncident`, `availableNetworkTechnician`. Avoid generic fixture names such as `foo`, `data1`, or `mockThing`.
- Name npm scripts after an action or lifecycle stage (`test`, `build`, `start`, `typecheck`) and keep to the package manager’s established conventions. Do not create multiple aliases for the same task.
- Name branches and commits so their purpose can be understood from a list. If the team adopts a required format, record it here before applying it consistently; no branch or commit format is currently prescribed.

## 4. Naming patterns for this project

Use these as patterns when the corresponding feature is implemented:

| Purpose | Pattern | Example |
|---|---|---|
| Incident page | `Incident<Concern>Page` | `IncidentListPage` |
| Shared incident UI | `Incident<Concern>` | `IncidentPriorityBadge` |
| Incident model | `Incident` | `Incident` |
| Incident service operation | `<verb>Incident` | `assignIncident` |
| Priority calculation | `calculateIncidentPriority` | `calculateIncidentPriority` |
| Assignment policy/strategy | `<Criterion>BasedAssignmentStrategy` | `SkillBasedAssignmentStrategy` |
| SLA operation | `<verb>Sla<Concern>` | `calculateSlaDeadline`, `checkSlaCompliance` |
| Search/filter state | `incidentFilters`, `IncidentSearchCriteria` | `IncidentSearchCriteria` |
| Audit entry | `IncidentAuditEvent` | `IncidentAuditEvent` |
| Incident CSS block | `.incident-<component>` | `.incident-card` |
| Incident route | `/incidents/<resource-or-action>` | `/incidents/:incidentId` |

The patterns are guides, not permission to add unused layers or abstractions. Choose names that fit the actual responsibility.

## 5. Avoid these ambiguity patterns

Do not:

- use several names for one concept (`ticket` in one feature and `incident` in another);
- make unrelated concepts share an overloaded name (`status`, `type`, `data`, `manager`) when a precise name is available;
- repeat context unnecessarily (`IncidentIncidentDetails`, `incidentIncidentId`);
- encode an implementation detail that may change (`BlueButton`, `LeftPanel`, `AxiosIncidentService`) unless that detail is the actual distinction;
- use unexplained abbreviations, arbitrary numbers, or temporary-state words (`v2`, `new`, `old`, `temp`, `final`);
- name a file after a broad container when it has a specific purpose (`helpers.ts`, `common.ts`, `misc.ts`);
- give two different responsibilities the same name merely because both are “services”; qualify by domain responsibility (`incidentQueryService`, `notificationService`).

## 6. Existing names and adoption

The current React scaffold contains starter names and files that do not yet follow every convention, including `App.css`, `Themes.tsx`, `helpers/history.ts`, and `logo.svg`. Treat those as existing names, not as precedent for new feature code. Do not rename them in isolation; when a future change touches one, update all imports, tests, and related references together.

Before adding a new name:

1. Search the codebase and these documents for the concept.
2. Reuse the canonical term and existing owner/scope if they match.
3. If the concept is genuinely new, choose a name using the test in section 1.
4. If two names could reasonably refer to the same thing, resolve the vocabulary first and update this document.

## 7. Updating this standard

Change this document when the project makes a durable naming decision or adds a technology with naming rules not covered here. Keep the examples consistent with the rule being introduced. Record unsettled choices as open decisions in the [project overview](./PROJECT_OVERVIEW.md), rather than presenting guesses as established facts.
