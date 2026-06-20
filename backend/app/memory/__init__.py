"""Per-crew cross-run memory.

The boundary is enforced by import discipline: only the Manager node imports
`read`, and only the Leader node imports `write`. Workers never touch memory.
"""
