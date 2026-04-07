# Schools spec — canonical flow & data model (Shajara)

**Status:** specification only — not implemented in code yet.  
**Purpose:** single source of truth for HODs, schools, multi-school teachers, private lessons, and visibility.

**Related:** [TERMS_AND_GOALS_SPEC.md](./TERMS_AND_GOALS_SPEC.md) — school terms, **calendar periods** for private lessons, **rubric goals**, checkbox progress, %, and **audit trails** visible to teacher, student, parent, and HOD (school-scoped goals only).

---

## 1. Glossary

| Term | Definition |
|------|------------|
| **School** | An organizational unit in the platform (name, settings, lifecycle). |
| **HOD (Head of Department)** | A user role that **creates and manages one or more schools**. |
| **School membership** | A user (teacher or student) is **linked to a school** with a role and optional metadata (e.g. joined date, status). |
| **Assignment** | Within a given school: **which students are assigned to which teachers** for teaching and monitoring. HODs configure this. |
| **Private lesson** | A lesson (note / lesson record) where the **teacher is not operating in the context of any school** — i.e. no school applies to that lesson. Private lessons are grouped in time by a **calendar period** (see TERMS_AND_GOALS_SPEC). Teachers may run **only** private work, **only** school work, or **both**. |
| **Edge case (dual track)** | The same **student** and the same **teacher** may have **both** school-scoped lessons (under a school where both are members and assigned) **and** private lessons (no school on the lesson). These are parallel tracks and must remain distinguishable. |

---

## 2. Cardinality & rules (decided)

| Question | Answer |
|----------|--------|
| HOD ↔ schools | **One HOD can manage multiple schools.** |
| Student ↔ schools | **A student can belong to multiple schools** (separate memberships per school). |
| Teacher ↔ schools | A teacher can work under **zero, one, or many schools**, and/or **independently** (private-only). |
| Private lessons | Lessons **not** tied to a school; naming is **“Private lessons”** in product copy. They use a **calendar period** (not a school term) for grouping and goals. |
| Edge case | **Allowed:** same student + same teacher with school-linked lessons **and** private lessons. |

---

## 3. Actors & goals

### 3.1 HOD

- Create and manage **multiple schools** they are responsible for.
- For each school: **add or invite teachers** and **students** into that school (membership).
- **Assign students to teachers** *within that school* (who teaches whom in this school).
- **Monitor** lessons and student progress **only in the scope of schools they manage** — i.e. school-scoped lessons for that school’s teacher–student pairs (according to policy below).

### 3.2 Teacher

- May be a member of **multiple schools** (each membership is independent).
- May teach **private lessons** with students **without** any school on those lessons.
- May **combine**: e.g. School A + School B + private clients.
- Sees **rosters and lessons** split by **context**: per school (assigned students in that school) vs **private** (no school).

### 3.3 Student (and parents, if applicable)

- May belong to **multiple schools** (separate enrollments).
- May also have **private** lesson relationships with teachers outside any school context.
- Sees their own lessons; UI should clarify **which school** (if any) applies, vs **private**.

---

## 4. Canonical visibility rules

These rules prevent data leaks and define what each role may see.

| Actor | May see |
|-------|---------|
| **HOD** | Only schools they manage. Within each: members (teachers, students), assignments, and **lessons that belong to that school** (school-scoped lessons for teacher–student pairs that are valid in that school per assignments). **Does not** see private lessons unless a future product decision explicitly grants that (default: **no**). For **school-scoped student goals** (rubric, progress, audit), HOD visibility is defined in TERMS_AND_GOALS_SPEC. |
| **Teacher** | All schools they belong to (per-school assigned students) **plus** all **private** lessons they teach. Lessons must be queryable by **school context or private**. |
| **Student / parent** | Lessons and progress relevant to them; must distinguish **per-school** vs **private**. |

**Dual-track edge case:** For the same teacher and student, **school-scoped** lessons are visible to the HOD of that school (subject to assignment rules); **private** lessons between them are **not** visible to any HOD (unless policy changes later).

---

## 5. Flows (user journeys)

### 5.1 HOD: create and run a school

1. HOD creates a **school** (metadata, settings).
2. HOD **adds teachers** to the school (invite / approve / link existing users — mechanism TBD at implementation).
3. HOD **adds students** to the school.
4. HOD **assigns students to teachers** within this school (who teaches whom).
5. HOD opens **monitoring views**: by school → teachers → lessons / progress for **school-scoped** activity only.

*Repeat for additional schools under the same HOD.*

### 5.2 Teacher: work across schools and private

1. Teacher joins or is added to **School A** and optionally **School B**.
2. For each school, teacher sees **only students assigned to them in that school** for school-context teaching.
3. Teacher may add **private** students / lessons: **no school** on those lesson records.
4. **James example:** School A roster + School B roster + separate **private** list; lesson creation picks **school context** or **private**.

### 5.3 Student: multiple schools + optional private

1. Student is enrolled in **School X** and **School Y** (two memberships).
2. Student may have different teachers per school per assignments.
3. Student may also take **private** lessons with a teacher (including one who also teaches them in a school — **dual track**).

---

## 6. Data concepts (implementation-agnostic)

Implementation may use tables/joins differently; this section defines **what must be representable**.

### 6.1 Entities

- **User** — authentication; **role** may include `hod`, `teacher`, `student`, `parent` (existing roles extended).
- **School** — owned or administered by an HOD (see 6.2).
- **SchoolTeacher** — teacher `T` is a member of school `S` (with optional metadata).
- **SchoolStudent** — student `St` is a member of school `S`.
- **SchoolAssignment** — within school `S`, student `St` is assigned to teacher `T` (for teaching in that school). Uniqueness: typically `(S, St, T)` or `(S, St)` with one primary teacher per subject — **product decision at implementation**; minimum is “HOD can assign student to teacher in school.”
- **Lesson / note** — must support:
  - **`school_id` nullable:** `null` ⇒ **private lesson**; non-null ⇒ lesson belongs to that school and must satisfy membership + assignment rules for that school.
  - **Time grouping:** school-scoped lessons use a **school term**; private lessons use a **calendar period** (see TERMS_AND_GOALS_SPEC).

### 6.2 HOD ↔ School

- **HOD manages many schools.** Model as: `School` has `hod_id` (FK to user with HOD role), **or** a join `HODSchool` if co-HOD is ever needed. Default spec: **each school has exactly one managing HOD** unless you later add delegation.

### 6.3 Private lesson (definition)

- A lesson is **private** iff it is **not** attributed to any school (`school_id` is null / equivalent).
- Private lessons still associate **teacher** and **student** (and existing note content, files, etc.).
- In addition, private lessons reference a **calendar period** for time grouping (see TERMS_AND_GOALS_SPEC).

### 6.4 Dual-track (edge case)

- Same `(teacher, student)` may have:
  - Lessons with `school_id = S` (only if both are members of `S` and assignment allows).
  - Lessons with `school_id` null (private).
- No merging these into one stream for HOD visibility: **school lessons** and **private lessons** are **separate** at the data level.

---

## 7. Dashboards & UX (high level)

| Role | Primary surfaces |
|------|------------------|
| **HOD** | List of **my schools** → per school: members, assignments matrix or list, monitoring (lessons/progress, school-scoped). |
| **Teacher** | **Context switcher** or sections: **School 1**, **School 2**, …, **Private**. Create lesson: choose **school** or **private** explicitly. |
| **Student** | Views filtered by **school** vs **private** where relevant. |

---

## 8. Open decisions (defer to implementation phase)

- Exact **invitation** flow (email token vs admin add-by-username).
- Whether a **student in a school** must be assigned before any school-scoped lesson, or HOD can allow “pool” teachers.
- **Parent** visibility across multiple schools for the same child (mirror student rules).
- **Analytics** beyond rubric % and audit (see TERMS_AND_GOALS_SPEC for goal progress).

---

## 9. Non-goals (this spec)

- Does not prescribe SQL, framework, or migration steps.
- Does not change existing auth until implementation follows this spec.

---

*End of schools spec.*
