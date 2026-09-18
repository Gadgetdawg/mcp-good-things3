"""FastMCP implementation of Things3 MCP server."""

import logging

from fastmcp import FastMCP


# Try to import relative, fall back to absolute for testing
try:
    from .applescript_handler import AppleScriptHandler
    from .config import Settings
except ImportError:
    from applescript_handler import AppleScriptHandler
    from config import Settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load .env file for development
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Create settings instance from environment
settings = Settings()

# Validate auth token on startup if provided
if settings.auth_token:
    logger.info("✅ Things3 auth token configured - update operations available")
else:
    logger.warning("⚠️ No auth token configured - update operations will fail")
    logger.info("To configure: Set THINGS3_AUTH_TOKEN environment variable")

# Create FastMCP app
mcp = FastMCP(
    name="mcp-server-things3-fast",
    instructions="""This server provides access to Things3 task management on macOS.
    
Authentication: Some operations require a Things3 auth token. Set THINGS3_AUTH_TOKEN 
environment variable or pass it in the Claude Desktop config."""
)


def format_date_readable(date_str: str) -> str:
    """Convert Things3 date format to human readable format."""
    if not date_str or date_str == "missing value":
        return ""
    
    # Remove time portion if present
    if " at " in date_str:
        date_part = date_str.split(" at ")[0]
        return date_part
    
    return date_str


@mcp.tool
def check_auth_status() -> str:
    """
    Check if Things3 authentication is configured.
    
    This tool helps verify that the auth token is properly configured
    via environment variable.
    """
    if settings.is_authenticated:
        return "✅ Things3 authentication is configured. Update operations will work."
    else:
        return """❌ Authentication not configured.

To configure authentication:
1. Via environment variable: export THINGS3_AUTH_TOKEN="your-token"
2. Via Claude Desktop config: Add to env section

To get your token:
1. Open Things3
2. Go to Settings → General → Enable Things URLs → Manage
3. Copy your token (device-specific)"""


@mcp.tool(name="view-projects")
def view_projects() -> str:
    """View all projects in Things3"""
    try:
        # Validate Things3 is accessible
        if not AppleScriptHandler.validate_things3_access():
            return "Things3 is not available. Please ensure Things3 is installed and running."
        
        projects = AppleScriptHandler.get_projects() or []
        if not projects:
            return "No projects found in Things3."

        response = ["Projects in Things3:"]
        for project in projects:
            project_id = project.get("id", "")
            title = project.get("title", "Untitled Project").strip()
            response.append(f"\n• {title} (id: {project_id})")

        return "\n".join(response)
    except Exception as e:
        logger.error(f"Error retrieving projects: {e}")
        return f"Failed to retrieve projects: {e!s}"


@mcp.tool(name="view-todos")
def view_todos(list_name: str = "Today", show_notes: bool = True) -> str:
    """View todos from a specific Things3 list.
    
    Args:
        list_name: The list to view todos from. Valid options:
                  - Today (default): Tasks scheduled for today
                  - Inbox: Unprocessed tasks
                  - Anytime: Tasks without specific scheduling
                  - Upcoming: Tasks scheduled for future dates
                  - Someday: Tasks deferred indefinitely
                  - Logbook: Completed and canceled tasks
                  - Trash: Deleted tasks
        
        show_notes: Whether to display task notes (default: True).
                   - True: Shows notes for context when processing/deciding
                   - False: Cleaner view for scanning long lists
                   - Recommended: True for Inbox/Today, False for Anytime/Upcoming scans
    
    PHILOSOPHY BY LIST:
    
    Today:
    • For focused commitments, not wishlists (max ~4 items)
    • Tasks appear here on their scheduled date
    • If overloaded, move flexible items to Anytime
    
    Inbox:
    • For capture, not storage - process regularly
    • Decide: do it, delegate it, defer it, or delete it
    • Goal is inbox zero, not inbox storage
    
    Anytime:
    • Most tasks should live here - ready when you are
    • Having many tasks in Anytime is normal and good
    • Pull from here to Today as capacity allows
    • Tasks with deadlines (but no when date) stay here
    • Deadlines ≠ scheduling
    
    Upcoming:
    • Tasks scheduled for specific future dates (hibernating)
    • For "I can't/won't start this until X date"
    • Not everything needs a date - resist scheduling for scheduling's sake
    • Does NOT include tasks with deadlines but no start date
    
    Examples:
    - view_todos() - Shows Today list
    - view_todos("Inbox") - Shows unprocessed tasks
    - view_todos("Anytime") - Shows active unscheduled tasks
    - view_todos("Upcoming") - Shows future scheduled tasks
    """
    try:
        # Validate Things3 is accessible
        if not AppleScriptHandler.validate_things3_access():
            return "Things3 is not available. Please ensure Things3 is installed and running."
        
        todos = AppleScriptHandler.get_tasks_from_list(list_name) or []
        if not todos:
            return f"No todos found in {list_name} list."

        # Check for overload and set appropriate header
        todo_count = len(todos)
        if list_name == "Today":
            if todo_count > 4:
                response = [f"⚠️ Today's Focus ({todo_count} items - consider reviewing):"]
            else:
                response = [f"Today's Focus ({todo_count} items):"]
        elif list_name == "Inbox":
            response = [f"Inbox ({todo_count} items):"]
        elif list_name == "Anytime":
            response = [f"Anytime tasks ({todo_count} items):"]
            response.append("💡 These active tasks are ready whenever you are. Pull to Today as capacity allows.")
        elif list_name == "Upcoming":
            response = [f"Upcoming scheduled tasks ({todo_count} items):"]
            response.append("💡 These tasks are hibernating until their scheduled date arrives.")
        else:
            response = [f"{list_name} ({todo_count} items):"]
        
        # Format todos with enhanced Approach 1 style
        for todo in todos:
            todo_id = todo.get("id", "")
            title = todo.get("title", "Untitled Todo").strip()
            notes = todo.get("notes", "")
            tags = todo.get("tags", "")
            due_date = todo.get("due_date", "")
            when_date = todo.get("when_date", "") or todo.get("when", "")
            project_name = todo.get("list", "")
            # A3: distinct id/name fields for project and area
            project_id = todo.get("project_id", "")
            project_title = todo.get("project_title", "") or project_name
            area_id = todo.get("area_id", "")
            area_name = todo.get("area_name", "")
            list_type = todo.get("list_type", "")
            
            # Main title line
            response.append(f"\n• {title} (id: {todo_id})")
            
            # Build metadata line with relevant fields
            metadata_parts = []
            
            # When date
            if when_date:
                readable_when = format_date_readable(when_date)
                if readable_when:
                    metadata_parts.append(f"📅 When: {readable_when}")
            
            # Due date
            if due_date:
                readable_due = format_date_readable(due_date)
                if readable_due:
                    metadata_parts.append(f"Due: {readable_due}")
            
            # Tags
            if tags:
                metadata_parts.append(f"🏷️ {tags}")
            
            # Project/Area — A3 adds IDs so downstream automation can round-trip
            if project_id:
                metadata_parts.append(f"📁 {project_title} (project_id: {project_id})")
                if area_id:
                    metadata_parts.append(f"🗂 {area_name} (area_id: {area_id})")
            elif area_id:
                metadata_parts.append(f"🗂 {area_name} (area_id: {area_id})")
            elif project_name:
                # Fallback for older AppleScript output without id fields
                metadata_parts.append(f"📁 {project_name}")
            
            # Add metadata line if we have any metadata
            if metadata_parts:
                response.append(f"  {' | '.join(metadata_parts)}")
            
            # Add notes if enabled and present
            if show_notes and notes and notes != "missing value":
                notes_lines = notes.strip().split('\n')
                if len(notes_lines) == 1:
                    response.append(f"  📝 {notes_lines[0]}")
                else:
                    response.append("  📝 " + notes_lines[0])
                    for line in notes_lines[1:]:
                        response.append(f"     {line}")
        
        # Add philosophy reminders for specific lists
        if list_name == "Today" and todo_count > 4:
            response.append("\n💡 Today has more than 4 items. Consider:")
            response.append("• Which are truly TODAY vs. nice-to-have?")
            response.append("• Move flexible items to Anytime (update with when='')")
            response.append("• Use Evening section for time-specific tasks")
        elif list_name == "Inbox" and todo_count > 10:
            response.append("\n💡 Tip: Process your inbox - decide, don't just collect")
        
        return "\n".join(response)
    except ValueError as e:
        return str(e)
    except Exception as e:
        logger.error(f"Error retrieving todos from {list_name}: {e}")
        return f"Failed to retrieve todos from {list_name}: {e!s}"


@mcp.tool(
    name="get-things3-todo",
    description="""Return a single to-do's full record by id.

Essential for verify-after-write patterns — call this after any mutation to
confirm the todo landed with the expected fields.

RETURNS: id, title, notes, status, when_date, due_date, tags, list/list_type,
project_id/project_title, area_id/area_name, creation_date, modification_date,
and checklist[].
"""
)
def get_things3_todo(id: str) -> str:
    """Return a single todo's full record (A2)."""
    try:
        if not AppleScriptHandler.validate_things3_access():
            return "Things3 is not available. Please ensure Things3 is installed and running."

        if not id:
            return "id is required."

        try:
            todo = AppleScriptHandler.get_todo_by_id(id)
        except RuntimeError as e:
            return f"Failed to retrieve todo {id}: {e!s}"

        if not todo:
            return f"No todo found with id {id}."

        return _format_todo_record(todo)
    except Exception as e:
        logger.error(f"Error retrieving todo {id}: {e}")
        return f"Failed to retrieve todo: {e!s}"


def _format_todo_record(todo: dict) -> str:
    """Shared renderer for a single full todo record (used by A2 and B1)."""
    todo_id = todo.get("id", "")
    title = (todo.get("title") or "Untitled Todo").strip()
    status = todo.get("status", "open")
    notes = todo.get("notes", "")
    tags = todo.get("tags", "")
    when_date = todo.get("when_date") or todo.get("when", "")
    due_date = todo.get("due_date", "")
    project_id = todo.get("project_id", "")
    project_title = todo.get("project_title", "")
    area_id = todo.get("area_id", "")
    area_name = todo.get("area_name", "")
    creation_date = todo.get("creation_date", "")
    modification_date = todo.get("modification_date", "")
    checklist = todo.get("checklist") or []

    status_icon = "✅" if status == "completed" else ("🚫" if status == "canceled" else "⏳")
    lines = [f"{status_icon} {title} (id: {todo_id})"]

    meta = [f"status: {status}"]
    if when_date:
        readable_when = format_date_readable(when_date)
        if readable_when:
            meta.append(f"📅 When: {readable_when}")
    if due_date:
        readable_due = format_date_readable(due_date)
        if readable_due:
            meta.append(f"Due: {readable_due}")
    if tags:
        meta.append(f"🏷️ {tags}")
    lines.append("  " + " | ".join(meta))

    if project_id:
        lines.append(f"  📁 {project_title} (project_id: {project_id})")
    if area_id:
        label = "Area" if not project_id else "Area (via project)"
        lines.append(f"  🗂 {label}: {area_name} (area_id: {area_id})")

    if notes and notes != "missing value":
        lines.append("\n📝 Notes:")
        for line in notes.strip().split("\n"):
            lines.append(f"  {line}")

    if checklist:
        lines.append(f"\n☑️ Checklist ({len(checklist)}):")
        for item in checklist:
            item_status = item.get("status", "open")
            mark = "[x]" if item_status == "completed" else "[ ]"
            item_title = (item.get("title") or "").strip()
            lines.append(f"  {mark} {item_title} (id: {item.get('id', '')})")

    if creation_date or modification_date:
        stamps = []
        if creation_date:
            stamps.append(f"created: {format_date_readable(creation_date)}")
        if modification_date:
            stamps.append(f"modified: {format_date_readable(modification_date)}")
        lines.append("\n🕑 " + " | ".join(stamps))

    return "\n".join(lines)


@mcp.tool(
    name="get-things3-project-details",
    description="""Return full details for a specific Things3 project by id.

Includes: title, notes, status, when/due dates, area (id + name), tags, headings,
and open/total todo counts. Complements get-things3-todos-for-project (which lists
only the todos).

TYPICAL USES:
• Deep-context project review — notes + headings + outstanding work in one call
• Sweeper logic — inspect headings before placing the ➡ next-action marker
• Automation — round-trip project metadata without multiple lookups

RETURNS structured text. To inspect at machine-readable level, use the underlying
AppleScriptHandler.get_project_details() directly.
"""
)
def get_things3_project_details(project_id: str) -> str:
    """Return full project record by id (A4)."""
    try:
        if not AppleScriptHandler.validate_things3_access():
            return "Things3 is not available. Please ensure Things3 is installed and running."

        if not project_id:
            return "project_id is required. Find it with view-projects."

        try:
            project = AppleScriptHandler.get_project_details(project_id)
        except RuntimeError as e:
            return f"Failed to retrieve project {project_id}: {e!s}"

        if not project:
            return f"No project found with id {project_id}."

        return _format_project_record(project)
    except Exception as e:
        logger.error(f"Error retrieving project details for {project_id}: {e}")
        return f"Failed to retrieve project details: {e!s}"


@mcp.tool(
    name="get-things3-todos-for-project",
    description="""Return all to-dos belonging to a specific Things3 project, by project id.

This is the per-project view that fills the gap left by view-todos (which only
supports the built-in lists: Today, Inbox, Anytime, Upcoming, Someday, Logbook, Trash).

ARGS:
    project_id: The Things3 project id. Find it with view-projects or search.
    include_completed: If True, return completed/canceled to-dos too.
                       Default False → open items only.
    show_notes: Whether to display task notes (default True).

TYPICAL USES:
• Next-action sweeper — list open todos in one project without scanning Anytime
• Project review — see what's outstanding before a planning session
• Automation — feed todos into downstream processing by project

RETURNS: Each todo includes id, title, status, when_date, due_date, tags,
and (new in A3) project_id, project_title, area_id, area_name.
"""
)
def get_things3_todos_for_project(
    project_id: str,
    include_completed: bool = False,
    show_notes: bool = True,
) -> str:
    """View all todos belonging to a specific project by id (A1)."""
    try:
        if not AppleScriptHandler.validate_things3_access():
            return "Things3 is not available. Please ensure Things3 is installed and running."

        if not project_id:
            return "project_id is required. Find it with view-projects or search-things3-todos."

        try:
            todos = AppleScriptHandler.get_todos_for_project(
                project_id, include_completed=include_completed
            )
        except RuntimeError as e:
            return f"Failed to retrieve todos for project {project_id}: {e!s}"

        # Best-effort: look up project title so we can include it in the header
        project_title = None
        if todos:
            project_title = todos[0].get("project_title") or todos[0].get("list") or None

        count = len(todos)
        header_title = project_title or project_id
        suffix = "" if include_completed else " (open only)"
        if count == 0:
            return f"No todos found in project '{header_title}'{suffix}."

        response = [f"Project '{header_title}' — {count} todo(s){suffix}:"]

        for todo in todos:
            todo_id = todo.get("id", "")
            title = (todo.get("title") or "Untitled Todo").strip()
            notes = todo.get("notes", "")
            tags = todo.get("tags", "")
            status = todo.get("status", "open")
            due_date = todo.get("due_date", "")
            when_date = todo.get("when_date", "") or todo.get("when", "")

            status_icon = "✅" if status == "completed" else ("🚫" if status == "canceled" else "⏳")
            response.append(f"\n{status_icon} {title} (id: {todo_id})")

            metadata_parts = []
            if when_date:
                readable_when = format_date_readable(when_date)
                if readable_when:
                    metadata_parts.append(f"📅 When: {readable_when}")
            if due_date:
                readable_due = format_date_readable(due_date)
                if readable_due:
                    metadata_parts.append(f"Due: {readable_due}")
            if tags:
                metadata_parts.append(f"🏷️ {tags}")
            if metadata_parts:
                response.append(f"  {' | '.join(metadata_parts)}")

            if show_notes and notes and notes != "missing value":
                notes_lines = notes.strip().split("\n")
                if len(notes_lines) == 1:
                    response.append(f"  📝 {notes_lines[0]}")
                else:
                    response.append("  📝 " + notes_lines[0])
                    for line in notes_lines[1:]:
                        response.append(f"     {line}")

        return "\n".join(response)
    except Exception as e:
        logger.error(f"Error retrieving todos for project {project_id}: {e}")
        return f"Failed to retrieve todos for project {project_id}: {e!s}"


@mcp.tool(name="search-things3-todos")
def search_things3_todos(query: str) -> str:
    """Search for todos in Things3 by title or content"""
    try:
        # Validate Things3 is accessible
        if not AppleScriptHandler.validate_things3_access():
            return "Things3 is not available. Please ensure Things3 is installed and running."

        todos = AppleScriptHandler.search_todos(query)
        if not todos:
            return f"No todos found matching '{query}'"

        response = [f"Found {len(todos)} todo(s) matching '{query}':"]
        for todo in todos:
            todo_id = todo.get("id", "")
            title = todo.get("title", "Untitled Todo")
            status = todo.get("status", "unknown")
            tags = todo.get("tags", "")
            project_id = todo.get("project_id", "")
            project_title = todo.get("project_title", "")
            area_id = todo.get("area_id", "")
            area_name = todo.get("area_name", "")
            list_type = todo.get("list_type", "")
            status_icon = "✅" if status == "completed" else "⏳"

            # Build response line
            line = f"\n{status_icon} {title}"
            if tags:
                line += f" #{tags.replace(',', ' #')}"
            line += f" (id: {todo_id})"

            response.append(line)

            # A3: surface parent project/area with IDs for downstream automation
            parent_bits = []
            if project_id:
                parent_bits.append(f"project: {project_title} (project_id: {project_id})")
            if area_id:
                label = "area" if list_type != "project" else "area (via project)"
                parent_bits.append(f"{label}: {area_name} (area_id: {area_id})")
            if parent_bits:
                response.append("  📁 " + " | ".join(parent_bits))

        return "\n".join(response)
    except Exception as e:
        logger.error(f"Error searching todos: {e}")
        return f"Failed to search todos: {e!s}"


@mcp.tool(
    name="complete-things3-todo",
    description="""Mark a todo as completed. Requires the todo's ID (find it using search or view tools first).

NOTE: Completion is final - tasks move to Logbook. If you might need it again, consider:
• Rescheduling instead (update with when="tomorrow")
• Moving to Someday (update with when="someday")
• Adding a "waiting" tag instead"""
)
def complete_things3_todo(id: str) -> str:
    """Complete a todo by ID."""
    try:
        # Validate Things3 is accessible
        if not AppleScriptHandler.validate_things3_access():
            return "Things3 is not available. Please ensure Things3 is installed and running."

        success = AppleScriptHandler.complete_todo_by_id(id)
        if success:
            # B1: verify-after-write — return the full resulting record
            try:
                verified = AppleScriptHandler.get_todo_by_id(id)
            except Exception as e:
                logger.warning(f"verify-after-write get_todo_by_id failed: {e}")
                verified = {}
            if verified:
                return "✅ Completed todo:\n\n" + _format_todo_record(verified)
            return "✅ Successfully completed todo"
        else:
            return f"""❌ Todo not found with ID: {id}

This might happen if:
• The todo was deleted
• The ID was copied incorrectly
• The todo is in Trash/Logbook

Try searching for the task first:
- Use 'search-things3-todos' with keywords from the title"""
    except Exception as e:
        logger.error(f"Error completing todo: {e}")
        return f"Failed to complete todo: {e!s}"


@mcp.tool(name="create-things3-project")
def create_things3_project(
    title: str,
    notes: str = None,
    area: str = None,
    when: str = None,
    deadline: str = None,
    tags: list[str] = None
) -> str:
    """Create a new project in Things3"""
    try:
        # Validate Things3 is available
        if not AppleScriptHandler.validate_things3_access():
            return "Things3 is not running or not installed. Please start Things3 and try again."

        # Build the Things3 URL with proper encoding
        base_url = "things:///add-project"
        params = {"title": title}
        
        # Optional parameters
        if notes:
            params["notes"] = notes
        if area:
            params["area"] = area
        if when:
            params["when"] = when
        if deadline:
            params["deadline"] = deadline
        if tags:
            params["tags"] = tags
        
        url = build_things_url(base_url, params)
        logger.info(f"Creating project with URL: {url}")

        call_things_url(url)

        # B1: verify-after-write — find the just-created project by title
        verified = _find_recently_created_project(title=title)
        if verified:
            return "✅ Created project:\n\n" + _format_project_record(verified)
        return (
            f"Created project '{title}' in Things3 "
            "(verify-after-write: could not locate just-created record; use "
            "view-projects to confirm)."
        )
    except Exception as e:
        logger.error(f"Error creating project: {e}")
        return f"Failed to create project in Things3: {e!s}"


def _find_recently_created_project(title: str) -> dict:
    """
    B1 helper: after create-project URL call, find the newest project with the
    given title and return its full details.
    """
    try:
        import time
        time.sleep(0.4)
        projects = AppleScriptHandler.get_projects() or []
        matches = [p for p in projects if (p.get("title") or "").strip() == title.strip()]
        if not matches:
            return {}
        # view-projects order is not guaranteed chronological, so we pull details
        # for each match and pick the one with the newest modification_date.
        # Projects don't currently expose a creation_date from get_projects, but
        # get_project_details reads the full record — we use id-ordering as a
        # last-resort tiebreaker (Things3 ids are approximately monotonic).
        if len(matches) == 1:
            return AppleScriptHandler.get_project_details(matches[0].get("id", ""))
        # Sort by id descending as a best-effort "most recent" proxy
        matches.sort(key=lambda p: p.get("id", ""), reverse=True)
        return AppleScriptHandler.get_project_details(matches[0].get("id", ""))
    except Exception as e:
        logger.warning(f"verify-after-write (project) lookup failed: {e}")
        return {}


@mcp.tool(name="create-things3-todo")
def create_things3_todo(
    title: str,
    notes: str = None,
    when: str = None,
    deadline: str = None,
    checklist: list[str] = None,
    tags: list[str] = None,
    list: str = None,
    list_id: str = None,
    heading: str = None,
    heading_id: str = None,
) -> str:
    """Create a new to-do in Things3.

    B2: Prefer list_id (project or area id) over list (name). IDs avoid collisions
    with repeating-template duplicates that share a name.
    """
    try:
        # Validate Things3 is available
        if not AppleScriptHandler.validate_things3_access():
            return "Things3 is not running or not installed. Please start Things3 and try again."

        # Build the Things3 URL with proper encoding
        base_url = "things:///add"
        params = {"title": title}

        # Optional parameters
        if notes:
            params["notes"] = notes
        if when:
            params["when"] = when
        if deadline:
            params["deadline"] = deadline
        if checklist:
            params["checklist"] = "\n".join(checklist)
        if tags:
            params["tags"] = tags
        # B2: id takes precedence over name to avoid same-name collisions
        if list_id:
            params["list-id"] = list_id
        elif list:
            params["list"] = list
        if heading_id:
            params["heading-id"] = heading_id
        elif heading:
            params["heading"] = heading

        url = build_things_url(base_url, params)
        logger.info(f"Creating todo with URL: {url}")

        call_things_url(url)

        # B1: verify-after-write — look up the most-recently-created matching todo
        verified = _find_recently_created_todo(title=title, list_id=list_id, when=when, list_name=list)
        if verified:
            return "✅ Created to-do:\n\n" + _format_todo_record(verified)
        return (
            f"Created to-do '{title}' in Things3 "
            "(verify-after-write: could not locate just-created record; try "
            "search-things3-todos or get-things3-todo to confirm)."
        )
    except Exception as e:
        logger.error(f"Error creating todo: {e}")
        return f"Failed to create to-do in Things3: {e!s}"


def _scopes_for_new_todo(when: str = None, list_name: str = None) -> list:
    """Which BOUNDED lists could a just-created to-do be in, most likely first.

    The `when` value passed to things:///add determines where Things files the item, so the destination is
    always knowable before we look. This is what lets verification read one small list instead of the
    entire database.
    """
    w = (when or "").strip().lower()
    if w in ("today", "evening"):
        return ["Today"]
    if w == "someday":
        return ["Someday"]
    if w == "anytime":
        return ["Anytime"]
    if w:
        # A date, "tomorrow", "next week" — Things files these under Upcoming. Today is checked too
        # because a date of today lands there instead.
        return ["Upcoming", "Today"]
    if list_name:
        # A project/area was named but not by id. Its todos are not in a built-in list, so fall back to the
        # small built-ins a stray item would land in rather than scanning everything.
        return ["Inbox", "Anytime", "Today"]
    return ["Inbox"]


def _best_by_title(candidates: list, title: str) -> dict:
    """Pick the newest candidate whose title matches exactly, and read its full record — ONE lookup.

    The previous implementation called get_todo_by_id() for EVERY candidate to compare timestamps, which
    spawns an osascript process per candidate. Ordering by the id Things assigns is a good enough proxy
    (Things ids are approximately monotonic), so only the winner is fetched.
    """
    exact = [t for t in candidates if (t.get("title") or "").strip() == title.strip()]
    if not exact:
        return {}
    exact.sort(key=lambda t: t.get("id", ""), reverse=True)
    return AppleScriptHandler.get_todo_by_id(exact[0].get("id", "")) or {}


def _find_recently_created_todo(title: str, list_id: str = None, when: str = None,
                                list_name: str = None, window_seconds: int = 15) -> dict:
    """
    B1 helper: immediately after a create URL call, locate the just-created todo by title.

    SCOPED LOOKUP — DO NOT REINTRODUCE THE FULL SCAN (2026-09-18).
    The previous fallback called AppleScriptHandler.search_todos(title), whose AppleScript does:

        set allTodos to to dos          -- EVERY to-do ever, Logbook included
        repeat with aTodo in allTodos
            set taskTitle to name of aTodo    -- one Apple Event round trip PER PROPERTY PER ITEM

    That is a full-database scan with tens of thousands of IPC round trips, run after every single create, to
    find a record Things had just created. On a database with years of Logbook history it did not complete
    in over two minutes and left Things3 unresponsive to all AppleScript — including reads — until it
    finished. Measured on Kevin's Mini, 2026-09-18.

    The scan was never necessary: `when` and `list_id` determine where Things files the new item, so the
    destination is known before we look. This reads ONE bounded list instead.

    Verification itself is worth keeping — `open things:///...` returns exit 0 whether or not anything
    happened (wrong token, URL scheme disabled, malformed params all look like success), so without a
    read-back a failed write is silent. The instinct was right; only the lookup was expensive.

    Returns the full todo dict from get_todo_by_id(), or {} if not found. NOT FINDING IT IS A VALID
    RESULT — the caller says so plainly rather than falling back to a scan.
    """
    try:
        # Small delay so Things3 has a chance to commit the write
        import time
        time.sleep(0.4)

        # Most precise case: an explicit project/area id. One bounded read.
        if list_id:
            try:
                project_todos = AppleScriptHandler.get_todos_for_project(list_id, include_completed=False)
            except Exception:
                project_todos = []
            found = _best_by_title(project_todos, title)
            if found:
                return found
            # fall through to the built-in lists: `when` can override where an item is filed

        for scope in _scopes_for_new_todo(when=when, list_name=list_name):
            try:
                todos = AppleScriptHandler.get_tasks_from_list(scope) or []
            except Exception as e:
                logger.warning(f"verify-after-write: could not read list {scope}: {e}")
                continue
            found = _best_by_title(todos, title)
            if found:
                return found
        return {}
    except Exception as e:
        logger.warning(f"verify-after-write lookup failed: {e}")
        return {}


@mcp.tool(
    name="update-things3-todo",
    description="""Update an existing to-do in Things3. Requires the todo's ID (use search or view tools first).

SCHEDULING PHILOSOPHY:
• when="today" → Use sparingly. Today is for focused commitments, not a wishlist
• when="2024-12-25" → Task hibernates in Upcoming until this date
• when=null → Moves to Anytime (can tackle whenever). Good default for most tasks
• when="" → Clears date, returns to Anytime
• deadline → Task stays in Anytime even with deadline (can start anytime, must finish by date)

TIPS:
• Don't reschedule repeatedly - might mean task needs breaking down
• Clearing a date (when="") often better than pushing to tomorrow
• Use tags for priority rather than scheduling everything for today"""
)
def update_things3_todo(
    id: str,
    title: str = None,
    notes: str = None,
    when: str = None,
    deadline: str = None,
    tags: list[str] = None,
    checklist: list[str] = None,
    list: str = None,
    list_id: str = None,
    heading: str = None,
    heading_id: str = None,
    completed: bool = None,
    canceled: bool = None,
) -> str:
    """Update an existing todo.

    B2: Prefer list_id / heading_id (project/area/heading ids) over list / heading
    names. IDs avoid collisions with repeating-template duplicates that share a name.
    """
    # Check auth token
    if not settings.is_authenticated:
        return """❌ Authentication Required

The THINGS3_AUTH_TOKEN environment variable is not set.

To get your token:
1. Open Things3
2. Go to Settings → General → Enable Things URLs → Manage
3. Copy your token
4. Set environment variable: export THINGS3_AUTH_TOKEN="your-token-here"

Note: Each device has its own token."""
    
    try:
        # Validate Things3 is available
        if not AppleScriptHandler.validate_things3_access():
            return "Things3 is not running or not installed. Please start Things3 and try again."
        
        # Build URL with special handling for empty strings
        base_url = "things:///update"
        params = {
            "id": id,
            "auth-token": settings.auth_token
        }
        
        # Handle fields that can be cleared with empty string
        if when is not None:
            params["when"] = when or ""
        if deadline is not None:
            params["deadline"] = deadline or ""
        
        # Normal fields
        if title is not None:
            params["title"] = title
        if notes is not None:
            params["notes"] = notes
        if tags is not None:
            params["tags"] = tags  # Will be joined with commas by build_url
        if checklist is not None:
            params["checklist-items"] = "\n".join(checklist)
        # B2: id takes precedence over name for list/heading
        if list_id is not None:
            params["list-id"] = list_id
        elif list is not None:
            params["list"] = list
        if heading_id is not None:
            params["heading-id"] = heading_id
        elif heading is not None:
            params["heading"] = heading
        if completed is not None:
            params["completed"] = str(completed).lower()
        if canceled is not None:
            params["canceled"] = str(canceled).lower()

        url = build_things_url(base_url, params)
        logger.info(f"Updating todo with URL: {url}")

        call_things_url(url)

        # B1: verify-after-write — read the todo back
        try:
            import time
            time.sleep(0.3)
            verified = AppleScriptHandler.get_todo_by_id(id)
        except Exception as e:
            logger.warning(f"verify-after-write get_todo_by_id failed: {e}")
            verified = {}

        # Build smart response
        response_parts = ["✅ Updated todo"]
        if verified:
            response_parts.append("")
            response_parts.append(_format_todo_record(verified))
        
        # Check for overload if scheduled for today
        if when == "today":
            today_count = AppleScriptHandler.get_today_count()
            if today_count > 4:
                response_parts.append(f"\n⚠️ Today now has {today_count} items. Stay focused on what's truly important today.")
        
        # Explain deadline behavior
        if deadline and not when:
            response_parts.append("\n💡 Task remains in Anytime (active but unscheduled) since only deadline was set. It will show a countdown but won't appear in Today until you explicitly schedule it.")
        
        # Warn about someday
        if when == "someday":
            response_parts.append("\n📦 Moved to Someday - this task won't appear in active lists until you're ready to act on it.")
        
        return "\n".join(response_parts)
    except Exception as e:
        logger.error(f"Error updating todo: {e}")
        return f"Failed to update todo: {e!s}"


@mcp.tool(
    name="update-things3-project",
    description="""Update an existing Things3 project by id (rename, reschedule, reassign area, re-tag).

Requires the THINGS3_AUTH_TOKEN environment variable.

ARGS:
    id: Project id (required).
    title: New title.
    notes: New notes (replaces existing).
    when: Schedule date (ISO or "today", "tomorrow"; use "" to clear).
    deadline: Due date (use "" to clear).
    tags: List of tags (replaces existing).
    area: New area name (B2: prefer area_id).
    area_id: New area id (preferred over area name).
    completed: True to mark complete.
    canceled: True to mark canceled.
"""
)
def update_things3_project(
    id: str,
    title: str = None,
    notes: str = None,
    when: str = None,
    deadline: str = None,
    tags: list[str] = None,
    area: str = None,
    area_id: str = None,
    completed: bool = None,
    canceled: bool = None,
) -> str:
    """Update an existing project by id (A9)."""
    if not settings.is_authenticated:
        return """❌ Authentication Required

The THINGS3_AUTH_TOKEN environment variable is not set. update-things3-project
requires the token. See check_auth_status for setup instructions."""

    try:
        if not AppleScriptHandler.validate_things3_access():
            return "Things3 is not running or not installed. Please start Things3 and try again."

        if not id:
            return "id is required."

        base_url = "things:///update-project"
        params = {"id": id, "auth-token": settings.auth_token}

        if when is not None:
            params["when"] = when or ""
        if deadline is not None:
            params["deadline"] = deadline or ""

        if title is not None:
            params["title"] = title
        if notes is not None:
            params["notes"] = notes
        if tags is not None:
            params["tags"] = tags
        # B2: id takes precedence over name
        if area_id is not None:
            params["area-id"] = area_id
        elif area is not None:
            params["area"] = area
        if completed is not None:
            params["completed"] = str(completed).lower()
        if canceled is not None:
            params["canceled"] = str(canceled).lower()

        url = build_things_url(base_url, params)
        logger.info(f"Updating project with URL: {url}")
        call_things_url(url)

        # B1: verify-after-write
        try:
            import time
            time.sleep(0.3)
            project = AppleScriptHandler.get_project_details(id)
        except Exception as e:
            logger.warning(f"verify-after-write get_project_details failed: {e}")
            project = {}

        if not project:
            return f"✅ Update sent for project {id}. (verify-after-write: could not read back; use get-things3-project-details to confirm.)"

        # Render full record (reuse the A4 formatter inline)
        return "✅ Updated project:\n\n" + _format_project_record(project)
    except Exception as e:
        logger.error(f"Error updating project: {e}")
        return f"Failed to update project: {e!s}"


def _format_project_record(project: dict) -> str:
    """Render a full project record (shared with A4 and A9)."""
    project_id = project.get("id", "")
    title = (project.get("title") or "Untitled").strip()
    status = project.get("status", "open")
    notes = project.get("notes", "")
    tags = project.get("tags", "")
    area_id = project.get("area_id", "")
    area_name = project.get("area_name", "")
    when_date = project.get("when_date", "")
    due_date = project.get("due_date", "")
    total = project.get("todo_count_total", 0)
    open_count = project.get("todo_count_open", 0)
    headings = project.get("headings") or []

    lines = [f"📁 {title} (id: {project_id})"]
    meta = [f"status: {status}", f"open: {open_count}/{total} todos"]
    if when_date:
        readable_when = format_date_readable(when_date)
        if readable_when:
            meta.append(f"📅 When: {readable_when}")
    if due_date:
        readable_due = format_date_readable(due_date)
        if readable_due:
            meta.append(f"Due: {readable_due}")
    if tags:
        meta.append(f"🏷️ {tags}")
    lines.append("  " + " | ".join(meta))

    if area_id:
        lines.append(f"  🗂 Area: {area_name} (area_id: {area_id})")

    if notes and notes != "missing value":
        lines.append("\n📝 Notes:")
        for line in notes.strip().split("\n"):
            lines.append(f"  {line}")

    if headings:
        lines.append(f"\n📌 Headings ({len(headings)}):")
        for h in headings:
            h_id = h.get("id", "")
            h_title = (h.get("title") or "").strip() or "(untitled)"
            archived_mark = " [archived]" if h.get("archived") else ""
            lines.append(f"  • {h_title}{archived_mark} (id: {h_id})")

    return "\n".join(lines)


@mcp.tool(
    name="complete-things3-project",
    description="""Mark a Things3 project completed (or canceled). Requires auth token.

ARGS:
    id: Project id (required).
    canceled: If True, mark canceled instead of completed.

NOTE: Completion is final — the project moves to Logbook. Open todos under the
project are also marked completed/canceled. If you might need it later, consider
re-scheduling via update-things3-project(when="someday") instead.
"""
)
def complete_things3_project(id: str, canceled: bool = False) -> str:
    """Mark a project completed or canceled (A10)."""
    if not settings.is_authenticated:
        return """❌ Authentication Required

The THINGS3_AUTH_TOKEN environment variable is not set. complete-things3-project
requires the token. See check_auth_status for setup instructions."""

    try:
        if not AppleScriptHandler.validate_things3_access():
            return "Things3 is not running or not installed. Please start Things3 and try again."

        if not id:
            return "id is required."

        base_url = "things:///update-project"
        params = {"id": id, "auth-token": settings.auth_token}
        if canceled:
            params["canceled"] = "true"
        else:
            params["completed"] = "true"

        url = build_things_url(base_url, params)
        logger.info(f"Completing project with URL: {url}")
        call_things_url(url)

        # B1: verify-after-write
        try:
            import time
            time.sleep(0.3)
            project = AppleScriptHandler.get_project_details(id)
        except Exception as e:
            logger.warning(f"verify-after-write get_project_details failed: {e}")
            project = {}

        verb = "canceled" if canceled else "completed"
        if not project:
            return f"✅ Project {id} marked {verb}. (verify-after-write: could not read back.)"
        return f"✅ Project marked {verb}:\n\n" + _format_project_record(project)
    except Exception as e:
        logger.error(f"Error completing project: {e}")
        return f"Failed to complete project: {e!s}"


@mcp.tool(
    name="create-things3-tag",
    description="""Create a new tag in the Things3 tag library.

Idempotent: if the tag already exists, returns its current state without error.
Optionally nest it under an existing parent tag.

ARGS:
    name: The tag name to create (required).
    parent_name: Optional parent tag name. The parent must already exist.

TYPICAL USES:
• Gap 4 fix — create tags like "KIZ-Resolved" before applying them via
  update-things3-todo, so they are never silently dropped.
• Bootstrapping tag hierarchies for new automation workflows.

RETURNS: confirmation of "created" or "already exists", with the tag name.
"""
)
def create_things3_tag(name: str, parent_name: str = None) -> str:
    """Create a tag in the Things3 tag library (Gap 4 fix)."""
    try:
        if not AppleScriptHandler.validate_things3_access():
            return "Things3 is not available. Please ensure Things3 is installed and running."

        if not name or not name.strip():
            return "name is required."

        try:
            result = AppleScriptHandler.create_tag(name.strip(), parent_name=parent_name)
        except RuntimeError as e:
            return f"❌ Failed to create tag '{name}': {e!s}"

        status = result.get("status", "unknown")
        tag_name = result.get("name", name)
        parent = result.get("parent")

        if status == "created":
            msg = f"✅ Tag created: '{tag_name}'"
            if parent:
                msg += f" (nested under '{parent}')"
            msg += "\nYou can now apply this tag via update-things3-todo without silent drop."
            return msg

        if status == "exists":
            msg = f"✅ Tag '{tag_name}' already exists in Things3 tag library"
            if parent:
                msg += f" (under '{parent}')"
            msg += " — no action needed."
            return msg

        return f"⚠️ Unexpected status '{status}' for tag '{tag_name}'."

    except Exception as e:
        logger.error(f"Error creating tag '{name}': {e}")
        return f"Failed to create tag: {e!s}"


# Main entry point for script
def main():
    """Main entry point for the FastMCP server."""
    mcp.run()


# Centralized X-Callback-URL handling
def build_things_url(base_url: str, params: dict) -> str:
    """Build a properly encoded Things3 URL."""
    if not params:
        return base_url
    
    from urllib.parse import quote
    encoded_params = []
    for key, value in params.items():
        if value is not None:
            # Handle list values (like tags)
            if isinstance(value, list):
                value = ",".join(str(v) for v in value)
            # Use quote() instead of quote_plus() - Things3 prefers %20 over +
            encoded_params.append(f"{key}={quote(str(value), safe='')}")
    
    return f"{base_url}?{'&'.join(encoded_params)}"


def call_things_url(url: str) -> None:
    """Execute a Things3 URL using the 'open' command."""
    import subprocess
    try:
        subprocess.run(['open', url], check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to execute x-callback-url: {e}")


# Run the server
if __name__ == "__main__":
    main()