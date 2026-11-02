# Normalization rules

The new portfolio resolver is intentionally conservative.

1. Every provided identifier is resolved independently. A malformed code is `unresolved`; two resolved identifiers pointing to different objects are `source_conflict`.
2. FIAS GUID, OKATO/OKTMO, country, region and locality name must be compatible with the same canonical candidate.
3. A unique identifier is authoritative only after every other provided geographic sign is checked.
4. Missing input is not a conflict. A supplied but unknown value is `unresolved`; a supplied value resolving to another object is `source_conflict`.
5. Without identifiers, country and region must resolve consistently before a locality name is evaluated inside that parent.
6. Several unresolved candidates remain `ambiguous` unless another supplied authoritative identifier selects one of them.
7. `source_conflict`, `ambiguous` and unresolved identifier outcomes never receive a canonical locality ID.

Different GUIDs are retained as different entities. The resolver never changes administrative parentage, ignores an unknown GUID in favour of a name, or chooses one of several same-name candidates arbitrarily.

These rules demonstrate safe behavior. They are not claimed to be the missing historical FIAS/ISO/OKATO/OKTMO ETL.

