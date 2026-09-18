import json
import subprocess
from pathlib import Path
from typing import Any


class AppleScriptHandler:
    """Handles AppleScript execution for Things3 data retrieval."""
    
    @staticmethod
    def get_script_path(script_name: str) -> Path:
        """Get the path to an AppleScript file in the applescript directory."""
        # Get the directory where this Python file is located
        current_dir = Path(__file__).parent
        return current_dir / "applescript" / script_name
    
    @staticmethod
    def run_script_file(script_name: str) -> str:
        """
        Executes an AppleScript file and returns its output.
        """
        script_path = AppleScriptHandler.get_script_path(script_name)
        
        if not script_path.exists():
            raise FileNotFoundError(f"AppleScript file not found: {script_path}")
        
        try:
            result = subprocess.run(
                ['osascript', str(script_path)],
                check=True,
                capture_output=True,
                text=True
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            error_msg = f"AppleScript failed: {script_name}\n"
            if e.stderr:
                error_msg += f"Error: {e.stderr}\n"
            if e.returncode:
                error_msg += f"Exit code: {e.returncode}"
            raise RuntimeError(error_msg)

    @staticmethod
    def run_script(script: str) -> str:
        """
        Executes an AppleScript and returns its output.
        """
        try:
            result = subprocess.run(
                ['osascript', '-e', script],
                check=True,
                capture_output=True,
                text=True
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            error_msg = "AppleScript execution failed\n"
            if e.stderr:
                error_msg += f"Error: {e.stderr}\n"
            error_msg += f"Script: {script[:100]}..."  # Show first 100 chars
            raise RuntimeError(error_msg)

    @staticmethod
    def safe_string_for_applescript(text: str) -> str:
        """
        Safely escape a string for use in AppleScript by handling quotes and special characters.
        """
        if not text:
            return ""
        
        # Replace backslashes first to avoid double escaping
        text = text.replace("\\", "\\\\")
        # Replace quotes with escaped quotes
        text = text.replace('"', '\\"')
        # Replace newlines with \\n
        text = text.replace("\n", "\\n")
        text = text.replace("\r", "\\r")
        
        return text
    
    @staticmethod
    def normalize_task(task: dict[str, Any]) -> dict[str, Any]:
        """
        Normalize task data from AppleScript by converting 'missing value' to None.
        """
        if not task:
            return task
            
        # Fields that can have "missing value"
        nullable_fields = ['due_date', 'when_date', 'when', 'notes', 'tags', 'list']
        
        for field in nullable_fields:
            if field in task and task[field] == "missing value":
                task[field] = None
                
        return task

    @staticmethod
    def get_todays_tasks() -> list[dict[str, Any]]:
        """
        Retrieves today's tasks from Things3 using AppleScript with JSON serialization.
        """
        try:
            # Use the new JSON-based AppleScript
            result = AppleScriptHandler.run_script_file("get_todays_tasks.applescript")
            
            # Parse JSON directly
            if not result:
                return []
            
            tasks = json.loads(result)
            
            # Normalize and ensure consistent field names
            normalized_tasks = []
            for task in tasks:
                if "when" in task and "when_date" not in task:
                    task["when_date"] = task["when"]
                normalized_tasks.append(AppleScriptHandler.normalize_task(task))
            
            return normalized_tasks
            
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON from today's tasks: {e}")
            return []
        except Exception as e:
            print(f"Error retrieving today's tasks: {e}")
            return []

    @staticmethod
    def get_projects() -> list[dict[str, str]]:
        """
        Retrieves all projects from Things3 using AppleScript with JSON serialization.
        """
        try:
            # Use the new JSON-based AppleScript
            result = AppleScriptHandler.run_script_file("get_projects.applescript")
            
            # Parse JSON directly
            if not result:
                return []
            
            return json.loads(result)
            
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON from projects: {e}")
            return []
        except Exception as e:
            print(f"Error retrieving projects: {e}")
            return []

    @staticmethod
    def validate_things3_access() -> bool:
        """
        Validate that Things3 is accessible and responsive.
        """
        try:
            script = '''
            tell application "Things3"
                return name of application "Things3"
            end tell
            '''
            result = AppleScriptHandler.run_script(script)
            return "Things3" in result
        except Exception:
            return False

    @staticmethod
    def complete_todo_by_id(todo_id: str) -> bool:
        """
        Mark a todo as completed by its ID.
        """
        script = f'''
        tell application "Things3"
            try
                set foundTodo to to do id "{AppleScriptHandler.safe_string_for_applescript(todo_id)}"
                set status of foundTodo to completed
                return "COMPLETED:" & name of foundTodo
            on error
                return "NOT_FOUND"
            end try
        end tell
        '''
        
        try:
            result = AppleScriptHandler.run_script(script)
            return result.startswith("COMPLETED:")
        except Exception:
            return False

    @staticmethod
    def search_todos(query: str) -> list[dict[str, Any]]:
        """
        Search for todos by title or content using JSON serialization.
        """
        try:
            # Use the new JSON-based AppleScript with query as argument
            result = subprocess.run(
                ['osascript', str(AppleScriptHandler.get_script_path("search_todos.applescript")), query],
                check=True,
                capture_output=True,
                text=True
            )
            
            # Parse JSON directly
            if not result.stdout.strip():
                return []
            
            todos = json.loads(result.stdout.strip())
            
            # Normalize and ensure consistent field names
            normalized_todos = []
            for todo in todos:
                if "when" in todo and "when_date" not in todo:
                    todo["when_date"] = todo["when"]
                normalized_todos.append(AppleScriptHandler.normalize_task(todo))
            
            return normalized_todos
            
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON from search: {e}")
            return []
        except Exception as e:
            print(f"Error searching todos: {e}")
            return []

    @staticmethod
    def get_today_count() -> int:
        """
        Returns count of tasks in Today list for overload warnings.
        """
        script = '''
        tell application "Things3"
            return count of to dos of list "Today"
        end tell
        '''
        
        try:
            result = AppleScriptHandler.run_script(script)
            return int(result)
        except Exception:
            return 0
    
    @staticmethod
    def get_todo_by_id(todo_id: str) -> dict[str, Any]:
        """
        Retrieves a single to-do record by id (A2).

        Returns an empty dict if not found. Raises RuntimeError on AppleScript
        failure.
        """
        if not todo_id:
            raise ValueError("todo_id is required")

        try:
            result = subprocess.run(
                [
                    'osascript',
                    str(AppleScriptHandler.get_script_path("get_todo_by_id.applescript")),
                    todo_id,
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            output = result.stdout.strip()
            if not output:
                return {}

            if output.startswith('{"error":'):
                error_data = json.loads(output)
                raise RuntimeError(error_data.get("error", "Unknown error"))

            todo = json.loads(output)
            if "when" in todo and "when_date" not in todo:
                todo["when_date"] = todo["when"]
            return AppleScriptHandler.normalize_task(todo)

        except json.JSONDecodeError as e:
            print(f"Error parsing JSON from get_todo_by_id: {e}")
            return {}
        except subprocess.CalledProcessError as e:
            error_msg = "AppleScript failed: get_todo_by_id\n"
            if e.stderr:
                error_msg += f"Error: {e.stderr}\n"
            if e.returncode:
                error_msg += f"Exit code: {e.returncode}"
            raise RuntimeError(error_msg)

    @staticmethod
    def get_project_details(project_id: str) -> dict[str, Any]:
        """
        Retrieves full project record by id (A4): notes, status, dates, area,
        headings, todo counts.
        """
        if not project_id:
            raise ValueError("project_id is required")

        try:
            result = subprocess.run(
                [
                    'osascript',
                    str(AppleScriptHandler.get_script_path("get_project_details.applescript")),
                    project_id,
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            output = result.stdout.strip()
            if not output:
                return {}

            if output.startswith('{"error":'):
                error_data = json.loads(output)
                raise RuntimeError(error_data.get("error", "Unknown error"))

            return json.loads(output)

        except json.JSONDecodeError as e:
            print(f"Error parsing JSON from project details: {e}")
            return {}
        except subprocess.CalledProcessError as e:
            error_msg = "AppleScript failed: get_project_details\n"
            if e.stderr:
                error_msg += f"Error: {e.stderr}\n"
            if e.returncode:
                error_msg += f"Exit code: {e.returncode}"
            raise RuntimeError(error_msg)

    @staticmethod
    def get_todos_for_project(project_id: str, include_completed: bool = False) -> list[dict[str, Any]]:
        """
        Retrieves all to-dos belonging to a specific project by id (A1).

        Args:
            project_id: The Things3 project id.
            include_completed: If True, also return completed/canceled todos.
                               Default False (open items only).
        """
        if not project_id:
            raise ValueError("project_id is required")

        try:
            flag = "1" if include_completed else "0"
            result = subprocess.run(
                [
                    'osascript',
                    str(AppleScriptHandler.get_script_path("get_todos_for_project.applescript")),
                    project_id,
                    flag,
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            output = result.stdout.strip()
            if not output:
                return []

            # Error sentinel from AppleScript
            if output.startswith('{"error":'):
                error_data = json.loads(output)
                raise RuntimeError(error_data.get("error", "Unknown error"))

            todos = json.loads(output)

            normalized_todos = []
            for todo in todos:
                if "when" in todo and "when_date" not in todo:
                    todo["when_date"] = todo["when"]
                normalized_todos.append(AppleScriptHandler.normalize_task(todo))

            return normalized_todos

        except json.JSONDecodeError as e:
            print(f"Error parsing JSON from project todos: {e}")
            return []
        except subprocess.CalledProcessError as e:
            error_msg = "AppleScript failed: get_todos_for_project\n"
            if e.stderr:
                error_msg += f"Error: {e.stderr}\n"
            if e.returncode:
                error_msg += f"Exit code: {e.returncode}"
            raise RuntimeError(error_msg)

    @staticmethod
    def create_tag(name: str, parent_name: str = None) -> dict[str, Any]:
        """
        Create a tag in the Things3 tag library (Gap 4 fix).

        Idempotent: if the tag already exists, returns its current state without
        error.  Optionally nests it under an existing parent tag.

        Returns a dict with keys:
            status   → "created" | "exists"
            name     → the tag name as stored by Things3
            parent   → parent tag name if one was set, else None
        Raises RuntimeError on AppleScript failure.
        """
        if not name:
            raise ValueError("name is required")

        safe_name = AppleScriptHandler.safe_string_for_applescript(name)
        safe_parent = AppleScriptHandler.safe_string_for_applescript(parent_name or "")

        if parent_name:
            script = f'''
            tell application "Things3"
                try
                    -- Check if tag already exists
                    set existingTags to tags whose name is "{safe_name}"
                    if (count of existingTags) > 0 then
                        return "EXISTS"
                    end if
                    -- Find parent tag
                    set parentTags to tags whose name is "{safe_parent}"
                    if (count of parentTags) = 0 then
                        return "PARENT_NOT_FOUND"
                    end if
                    set parentTag to item 1 of parentTags
                    -- Create nested tag
                    make new tag with properties {{name: "{safe_name}", parent tag: parentTag}}
                    return "CREATED"
                on error errMsg
                    return "ERROR:" & errMsg
                end try
            end tell
            '''
        else:
            script = f'''
            tell application "Things3"
                try
                    -- Check if tag already exists
                    set existingTags to tags whose name is "{safe_name}"
                    if (count of existingTags) > 0 then
                        return "EXISTS"
                    end if
                    -- Create top-level tag
                    make new tag with properties {{name: "{safe_name}"}}
                    return "CREATED"
                on error errMsg
                    return "ERROR:" & errMsg
                end try
            end tell
            '''

        try:
            result = AppleScriptHandler.run_script(script).strip()
        except RuntimeError as e:
            raise RuntimeError(f"create_tag AppleScript failed: {e}") from e

        if result == "CREATED":
            return {"status": "created", "name": name, "parent": parent_name}
        if result == "EXISTS":
            return {"status": "exists", "name": name, "parent": parent_name}
        if result == "PARENT_NOT_FOUND":
            raise RuntimeError(
                f"Parent tag '{parent_name}' not found in Things3 tag library. "
                "Create the parent first, then retry."
            )
        if result.startswith("ERROR:"):
            raise RuntimeError(result[len("ERROR:"):].strip())

        # Unexpected response — treat as error
        raise RuntimeError(f"Unexpected response from create_tag: {result!r}")

    @staticmethod
    def get_tasks_from_list(list_name: str) -> list[dict[str, Any]]:
        """
        Retrieves tasks from any Things3 list using JSON serialization.
        Valid lists: Today, Inbox, Anytime, Upcoming, Someday, Logbook, Trash
        """
        try:
            # Validate list name
            valid_lists = ["Today", "Inbox", "Anytime", "Upcoming", "Someday", "Logbook", "Trash"]
            if list_name not in valid_lists:
                raise ValueError(f"Invalid list name. Valid lists: {', '.join(valid_lists)}")
            
            # Use the new generic JSON-based AppleScript with list name as argument
            result = subprocess.run(
                ['osascript', str(AppleScriptHandler.get_script_path("get_list_tasks.applescript")), list_name],
                check=True,
                capture_output=True,
                text=True
            )
            
            # Parse JSON directly
            if not result.stdout.strip():
                return []
            
            # Check for error response
            output = result.stdout.strip()
            if output.startswith('{"error":'):
                error_data = json.loads(output)
                raise RuntimeError(error_data.get("error", "Unknown error"))
            
            tasks = json.loads(output)
            
            # Normalize and ensure consistent field names
            normalized_tasks = []
            for task in tasks:
                if "when" in task and "when_date" not in task:
                    task["when_date"] = task["when"]
                normalized_tasks.append(AppleScriptHandler.normalize_task(task))
            
            return normalized_tasks
            
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON from list tasks: {e}")
            return []
        except Exception as e:
            print(f"Error retrieving tasks from list '{list_name}': {e}")
            return []
