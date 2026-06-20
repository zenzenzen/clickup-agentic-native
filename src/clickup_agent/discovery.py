"""Lightweight discovery metadata for curated ClickUp wrappers."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CuratedWrapper:
    """Discovery metadata for one curated wrapper."""

    name: str
    summary: str
    operation_ids: tuple[str, ...]
    is_write: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "summary": self.summary,
            "operation_ids": list(self.operation_ids),
            "is_write": self.is_write,
        }


CURATED_WRAPPERS: tuple[CuratedWrapper, ...] = (
    CuratedWrapper(
        name="search",
        summary="Search and filter tasks across a workspace or list.",
        operation_ids=("GetFilteredTeamTasks", "GetTasks"),
        is_write=False,
    ),
    CuratedWrapper(
        name="list-hierarchy",
        summary="List workspace, space, folder, and list names and IDs.",
        operation_ids=("GetAuthorizedTeams", "GetSpaces", "GetFolders", "GetLists", "GetFolderlessLists"),
        is_write=False,
    ),
    CuratedWrapper(
        name="get-task",
        summary="Fetch a task with optional summary or field projection output.",
        operation_ids=("GetTask",),
        is_write=False,
    ),
    CuratedWrapper(
        name="task-statuses",
        summary="Discover valid statuses for a task or list.",
        operation_ids=("GetTask", "GetList"),
        is_write=False,
    ),
    CuratedWrapper(
        name="create-task",
        summary="Create a task in a ClickUp list.",
        operation_ids=("CreateTask",),
        is_write=True,
    ),
    CuratedWrapper(
        name="create-subtask",
        summary="Create a subtask under a parent task.",
        operation_ids=("CreateTask",),
        is_write=True,
    ),
    CuratedWrapper(
        name="set-status",
        summary="Update a task status with wrapper status validation.",
        operation_ids=("UpdateTask",),
        is_write=True,
    ),
    CuratedWrapper(
        name="set-description",
        summary="Update a task description, preferring markdown_content for rich formatting.",
        operation_ids=("UpdateTask",),
        is_write=True,
    ),
    CuratedWrapper(
        name="update-task",
        summary="Update common task fields, including status validation.",
        operation_ids=("UpdateTask",),
        is_write=True,
    ),
    CuratedWrapper(
        name="assign",
        summary="Add, remove, or replace task assignees.",
        operation_ids=("GetTask", "UpdateTask"),
        is_write=True,
    ),
    CuratedWrapper(
        name="assign-me",
        summary="Assign the authorized user to a task.",
        operation_ids=("GetAuthorizedUser", "UpdateTask"),
        is_write=True,
    ),
    CuratedWrapper(
        name="set-due-date",
        summary="Set or clear a task due date.",
        operation_ids=("UpdateTask",),
        is_write=True,
    ),
    CuratedWrapper(
        name="comment",
        summary="Add a single comment to a task.",
        operation_ids=("CreateTaskComment",),
        is_write=True,
    ),
    CuratedWrapper(
        name="comments",
        summary="List task comments, or add one.",
        operation_ids=("GetTaskComments", "CreateTaskComment"),
        is_write=True,
    ),
    CuratedWrapper(
        name="edit-comment",
        summary="Edit an existing comment.",
        operation_ids=("UpdateComment",),
        is_write=True,
    ),
    CuratedWrapper(
        name="create-checklist",
        summary="Create a checklist on a task, optionally with initial items.",
        operation_ids=("CreateChecklist",),
        is_write=True,
    ),
    CuratedWrapper(
        name="create-checklist-item",
        summary="Add an item to a checklist.",
        operation_ids=("CreateChecklistItem",),
        is_write=True,
    ),
    CuratedWrapper(
        name="check-item",
        summary="Edit a checklist item (resolve, rename, reparent, reassign).",
        operation_ids=("EditChecklistItem",),
        is_write=True,
    ),
    CuratedWrapper(
        name="sync-checklist",
        summary="Create or update checklist items from a non-destructive item list.",
        operation_ids=("GetTask", "CreateChecklist", "CreateChecklistItem", "EditChecklistItem"),
        is_write=True,
    ),
    CuratedWrapper(
        name="dev-sync",
        summary="Sync GitHub branch/PR development state into a ClickUp task.",
        operation_ids=(
            "GetTask",
            "GetTaskComments",
            "UpdateTask",
            "CreateTaskComment",
            "UpdateComment",
            "CreateChecklist",
            "CreateChecklistItem",
            "EditChecklistItem",
        ),
        is_write=True,
    ),
    CuratedWrapper(
        name="work-log",
        summary="Upsert agent action-item or verification checklist state.",
        operation_ids=("GetTask", "CreateChecklist", "CreateChecklistItem", "EditChecklistItem"),
        is_write=True,
    ),
    CuratedWrapper(
        name="decision-log",
        summary="Append a decision record comment to a task.",
        operation_ids=("CreateTaskComment",),
        is_write=True,
    ),
    CuratedWrapper(
        name="hotfix-doc",
        summary="Create a completed documentation task for a merged hotfix PR.",
        operation_ids=("CreateTask", "CreateChecklist", "CreateChecklistItem"),
        is_write=True,
    ),
    CuratedWrapper(
        name="subtasks",
        summary="Fetch a task with its subtasks expanded.",
        operation_ids=("GetTask",),
        is_write=False,
    ),
    CuratedWrapper(
        name="tags",
        summary="Add or remove tags on a task.",
        operation_ids=("AddTagToTask", "RemoveTagFromTask"),
        is_write=True,
    ),
    CuratedWrapper(
        name="timer",
        summary="Inspect, start, or stop the running timer.",
        operation_ids=("Getrunningtimeentry", "StartatimeEntry", "StopatimeEntry"),
        is_write=True,
    ),
)

CURATED_WRAPPERS_BY_NAME: dict[str, CuratedWrapper] = {wrapper.name: wrapper for wrapper in CURATED_WRAPPERS}
CURATED_WRAPPER_NAMES: frozenset[str] = frozenset(CURATED_WRAPPERS_BY_NAME)


def curated_wrapper_dicts() -> list[dict[str, object]]:
    return [wrapper.to_dict() for wrapper in CURATED_WRAPPERS]
