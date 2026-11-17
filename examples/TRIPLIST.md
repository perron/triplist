# Demo reliability checklist

Demo data for the README and tests. The items, incident names and PR
numbers below are made up to show the format.

## resume-old-sessions
paths: src/session/**
added: ^\s*\w+\??:\s
check: Does the new field load safely from old saved sessions that do not have it?
why: Demo incident INC-12 (resume crashed on sessions saved before a field was added)

## migration-rollback
paths: migrations/**
check: Can this migration run twice, and is there a tested rollback?
why: Demo incident INC-7

## new-env-var
added: process\.env\.|os\.environ|getenv\(
exclude: **/*.test.ts, tests/**
check: Is the new setting documented, and does the app still start when it is missing?
why: Demo PR #41

## removed-feature-flag
removed: isEnabled\(["'](\w+)["']\)
check: Was the flag removed everywhere, including the flag service and old clients?
why: Demo PR #88

## logging-user-data
added: (log|logger|console)\.(info|warn|error|debug)\(.*\b(email|phone|token)\b
check: Does this log line write user data? Redact it or drop it.
why: Demo incident INC-3

## billing
paths: src/billing/**
check: Did billing owners review this change?
why: Demo policy
