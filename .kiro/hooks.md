# Munshi — Kiro Hooks

## What are hooks
Hooks fire automatically when you save files. They catch things you forget.

## Hook 1: Auto-update requirements.txt
**Trigger:** When any .py file is saved in app/
**Action:** Check if any new imports are used that aren't in requirements.txt, and add them

## Hook 2: Remind about LangSmith tracing
**Trigger:** When any file in app/agents/ is saved
**Action:** Check if every function that calls llm_client has a LangSmith trace. If not, flag it.

## Hook 3: Type hint check
**Trigger:** When any .py file is saved
**Action:** Verify all function signatures have type hints. Flag any that don't.

## Hook 4: Env variable check
**Trigger:** When .env.example is modified
**Action:** Verify all variables in .env.example are also referenced in the code somewhere.
