# Stage 0 Knowledge-Base Registry

The source files supplied during initialization are treated as research references, not copied into this repository. This keeps the codebase small and avoids redistributing copyrighted material. Future claims should cite a source at the point of use and record whether the claim is direct evidence, a model assumption, or a design inference.

| ID | Supplied source | Stage 0 use |
|---|---|---|
| KB-01 | Aims and Hypotheses | Research framing |
| KB-02 | `s43856-025-01246-2` | Scientific literature reference |
| KB-03 | `twimahmodel.py` | Prior simulation patterns; requires refactoring before reuse |
| KB-04 | UIC titration protocol overview | Protein-glycation lab context |
| KB-05 | UIC titration protocol companion | Protein-glycation lab context |
| KB-06 | Ozempic reference | Medication context only; not delivery logic |
| KB-07 | Advanced Glycation End Products Food Reduction Diet | Food/AGE research context |
| KB-08 | Cooking AGE Lipids | Cooking and AGE research context |
| KB-09 | AGE/RAGE Signaling Path 1 | Pathway visualization reference |
| KB-10 | AGE/RAGE Signaling Path 2 | Pathway visualization reference |
| KB-11 | Semaglutide-bound GLP-1 receptor validation | Molecular reference |
| KB-12 | BRS Biochemistry, 2nd ed. | Biochemistry background |
| KB-13 | BRS Physiology | Physiology background |
| KB-14 | Smith's Patient-Centered Interviewing | Human-centered service context |
| KB-15 | Robbins Pathology, 7th ed. | Pathology background |
| KB-16 | Mosby's medical dictionary | Terminology reference |

## Evidence rules

1. Separate food-delivery operations from biomedical research claims.
2. Do not infer medical suitability of a meal from a delivery feasibility decision.
3. Label every numerical threshold as regulatory, empirically validated, stakeholder-selected, or provisional.
4. The Stage 0 battery floor and range reserve are provisional engineering defaults, not certified safety limits.
5. Do not commit personal health information, credentials, secrets, or copyrighted source files.

## Prior-code note

`twimahmodel.py` contains notebook shell directives, external-storage assumptions, and health simulation code. It is registered as a reference only. Any later reuse should extract dependency-free functions, remove credential/storage coupling, add provenance, and test scientific assumptions independently of delivery operations.
