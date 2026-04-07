# Terms, calendar periods & student goals — canonical spec (Shajara)

**Status:** specification only — not implemented in code yet.  
**Companion:** [SCHOOLS_SPEC.md](./SCHOOLS_SPEC.md) (schools, HOD, private vs school lessons).

This document defines **how lessons are grouped in time**, how **student goals** are scoped and structured (**rubric**), how **progress** is tracked (**checkboxes → percentage**), who may **edit** goals, and how **audit history** is exposed.

---

## 1. Glossary

| Term | Definition |
|------|------------|
| **School term** | A **time-bounded period** belonging to a **school** (e.g. “Term 1 2026”). Used to group **school-scoped** lessons and **school-scoped** goals. |
| **Calendar period** | A **time-bounded period** **not** tied to a school (Option B for **private** lessons). Used to group **private** lessons and **private** goals. Has label + start/end dates (and optional timezone policy at implementation). |
| **Goal scope (key)** | A goal applies to a unique combination of **student + teacher + context**. **Context** is either **(school + school term)** or **(calendar period only, no school)** for private. Two teachers in the same school ⇒ **two separate goals** for that student in that term if both teach them (e.g. different subjects). |
| **Goal set** | The **rubric** for one scope: a **header** (metadata) + an ordered **list of outcome items** to achieve within that period. |
| **Rubric item** | One row in the list: short **label/description**, **order**, **completed** boolean (or equivalent). |
| **Completion %** | Derived from rubric items: by default **equal weight** — `(number of items marked complete) / (total items) × 100`. Total items must be > 0 for a meaningful %; edge case: zero items — **product rule TBD** (hide % or disallow empty rubric). |
| **Goal audit entry** | An **append-only** record of a change to the goal set or rubric (create / update / delete item, toggle completion, edit text). **All** such changes are logged. |

---

## 2. Decided rules (this spec)

| Topic | Decision |
|-------|----------|
| Private lessons & time | **Option B:** private lessons are tied to a **calendar period** (not a school term). |
| Who sets/edits goals | **Teachers only** create and edit goal sets and rubric items (including ticking completion). |
| Goal granularity | **Per student, per teacher**, and **per school where applicable** — i.e. one goal set per **(student, teacher, school or private, period)**. Same student with two teachers (same school, different subjects) ⇒ **two goal sets** for that term. Same teacher + student in two schools ⇒ **two goal sets** (one per school-term). |
| Goal shape | **Rubric-style:** a **list of items** to achieve in the period. |
| Progress tracking | **Checkboxes** on each rubric item; teacher marks complete. **Percentage** derived from completed vs total items (equal weight per item unless a later spec adds weights). |
| Audit | **All** changes to goals (structure and completion state) are **tracked** and **visible** to **teacher**, **student**, and **parent** as below. **HOD** visibility is **school-scoped** only (see §5). |

---

## 3. Periods: two parallel concepts

### 3.1 School term

- Belongs to exactly **one school**.
- Fields (conceptual): name, start date, end date, display order, active flag.
- **School-scoped lessons** and **school-scoped goal sets** reference **school term** + **school** (school may be implied by term).

### 3.2 Calendar period (private)

- **Not** tied to a school.
- Used only for **private** lesson grouping and **private** goal sets.
- Fields (conceptual): name/label, start date, end date.
- May be **defined globally** (admin), **per deployment**, or **created per teacher/student** — **implementation choice**; minimum is a reusable period entity with dates so lessons and goals can point to it.

### 3.3 Lessons and period

| Lesson type | Period field |
|-------------|----------------|
| School-scoped | **School term** (required once terms exist; optional grace for migration). |
| Private | **Calendar period** (required once Option B is implemented for that lesson). |

---

## 4. Goal set: identity and rubric

### 4.1 Scope key (must be unique)

A **goal set** is uniquely identified by:

- `student_id`
- `teacher_id`
- **Either:**
  - `school_id` + `school_term_id` (school context), **or**
  - `calendar_period_id` with **no** school (private context)

**Not** unique across subjects by default: if the same teacher teaches two subjects to the same student in the same school/term, the product either:

- **One combined goal set** per (student, teacher, school, term), **or**
- **Subject/discipline field** on the goal set to split — **defer** unless needed; default spec: **one goal set per (student, teacher, school, term)**; if two subjects need two rubrics, add optional `subject` or `goal_stream` later.

*(User’s example: two different teachers ⇒ two goals naturally; two subjects **one** teacher ⇒ one rubric unless you add subject later.)*

### 4.2 Rubric structure

- Ordered list of **items** (display order integer).
- Each item: **title/text**, **sort order**, **is_completed** (boolean), **timestamps** optional for when marked complete.
- Teacher may **add, remove, reorder, edit text** of items (all audited — see §6).

### 4.3 Percentage

- \( \text{completion\_percent} = \lfloor 100 \times \frac{\text{completed items}}{\text{total items}} \rfloor \) or rounded per product rules; **equal weight** per item in v1.

---

## 5. Visibility

| Role | School-scoped goal sets | Private goal sets |
|------|-------------------------|-------------------|
| **Teacher** who owns the teaching relationship | Full: view, edit, checkboxes, **audit history** | Same |
| **Student** | View rubric, %, **full audit history** | Same |
| **Parent** (linked to student) | View rubric, %, **full audit history** | Same |
| **HOD** (manages the school) | View rubric, %, **full audit history** for goals in **their** schools | **No** access by default (aligns with private lesson visibility in SCHOOLS_SPEC); private goals same as private lessons |

**Rationale:** HOD sees everything that supports **governance** inside schools they manage, including **who changed what** on goals. Private tracks remain between teacher, student, and parent unless policy changes.

---

## 6. Audit trail (required behaviour)

### 6.1 What is logged

**Append-only** events, at minimum:

- Goal set **created** / **archived** (if soft-delete).
- Rubric item **added** / **removed** / **text or order changed**.
- Checkbox **completed** / **uncompleted** (toggle).
- **Actor** (user id), **timestamp**, **summary** or structured **before/after** for text fields.

### 6.2 Who can see the log

- **Teacher** (involved), **student**, **parent**: always for goals they are party to.
- **HOD**: for **school-scoped** goals only, for schools they manage.

### 6.3 Implementation note

- Store enough detail that disputes (“who cleared this checkbox?”) are answerable without ambiguity.

---

## 7. UX touchpoints (high level)

| Surface | Behaviour |
|---------|-----------|
| **Teacher — add/edit note for a student** | Show **current goal set** for the **active context** (school + term, or private + calendar period matching the lesson). Prominent rubric + %; link to full history. |
| **Teacher — goal management** | Edit rubric items; tick/untick; changes write audit + update %. |
| **Student / parent** | Dashboard or section: per school-term and per private period, rubric + % + **change history**. |
| **HOD** | School view: per teacher–student (in assignments), goal + % + **audit** for **school-scoped** goals only. |

---

## 8. Relationship to [SCHOOLS_SPEC.md](./SCHOOLS_SPEC.md)

- **Dual-track:** The same **student + teacher** may have a **school goal set** (school term) **and** a **private goal set** (calendar period) in parallel; do not merge.
- **Private lessons** use **calendar period**; **school lessons** use **school term**.
- Visibility of **private** goals follows the same boundary as **private lessons** for HOD (no default access).

---

## 9. Open decisions (defer to implementation)

- Who **creates** school terms and calendar periods (HOD vs global admin vs teacher for private periods).
- Whether **lessons** without a period are allowed during migration (temporary null).
- Rounding rules for **%**; behaviour when **zero** rubric items.
- Optional **weights** on rubric items (not in v1).

---

## 10. Non-goals

- No SQL or API design in this file.
- No UI mockups.

---

*End of terms and goals spec.*
