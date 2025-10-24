# Capability: Evidence Bookmark & Playback

## ADDED Requirements
- Requirement: The system MUST support evidence bookmarks on targets (annotation|task|plan) with actions: bookmark, playback, export, attach.
- Requirement: Playback MUST accept duration_sec and return a reconstructable timeline window.
- Requirement: The system MUST log an explicit confirmation "READY TO CALL JAVA API" for any third-party endpoint; actual calls are TODO in this phase.

#### Scenario: Bookmark and playback a task
Input: "为任务#T1打书签并回放过去300秒。"
Action: Create bookmark; return bookmark_id; accept playback window request.
Expected: Bookmark created; playback returns a timeline slice; external export remains TODO with logging confirmation.
