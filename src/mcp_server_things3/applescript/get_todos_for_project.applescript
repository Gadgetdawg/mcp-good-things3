use framework "Foundation"
use scripting additions

-- A1: Return all to-dos belonging to a given project, by project id.
-- This is the core enhancement that unblocks the Next-Action Sweeper and
-- any per-project automation. Same JSON shape as get_list_tasks.applescript.

on run argv
    if (count of argv) < 1 then
        error "Project id required as argument"
    end if

    set projectId to item 1 of argv

    -- Optional flag: include-completed=1 pulls cancelled/completed items too.
    set includeCompleted to false
    if (count of argv) >= 2 then
        if item 2 of argv is "1" or item 2 of argv is "true" then
            set includeCompleted to true
        end if
    end if

    return my get_todos_for_project(projectId, includeCompleted)
end run

on todo_to_dict(theTodo)
    set theDict to current application's NSMutableDictionary's dictionary()

    tell application "Things3"
        theDict's setValue:(id of theTodo) forKey:"id"
        theDict's setValue:(name of theTodo) forKey:"title"

        if notes of theTodo is not missing value then
            theDict's setValue:(notes of theTodo) forKey:"notes"
        else
            theDict's setValue:"" forKey:"notes"
        end if

        if due date of theTodo is not missing value then
            theDict's setValue:((due date of theTodo) as string) forKey:"due_date"
        else
            theDict's setValue:"" forKey:"due_date"
        end if

        -- Add status
        if status of theTodo is completed then
            theDict's setValue:"completed" forKey:"status"
        else if status of theTodo is canceled then
            theDict's setValue:"canceled" forKey:"status"
        else
            theDict's setValue:"open" forKey:"status"
        end if

        -- Add when date for scheduled tasks
        if activation date of theTodo is not missing value then
            theDict's setValue:((activation date of theTodo) as string) forKey:"when_date"
        else
            theDict's setValue:"" forKey:"when_date"
        end if

        set tagList to tag names of theTodo
        if tagList is not {} then
            set AppleScript's text item delimiters to ","
            set tagText to tagList as string
            set AppleScript's text item delimiters to ""
            theDict's setValue:tagText forKey:"tags"
        else
            theDict's setValue:"" forKey:"tags"
        end if

        -- Project/area info (A3 shape, shared with get_list_tasks)
        set parentList to ""
        set parentType to ""
        set projectIdVal to ""
        set projectTitleVal to ""
        set areaIdVal to ""
        set areaNameVal to ""
        if project of theTodo is not missing value then
            set parentList to name of project of theTodo
            set parentType to "project"
            set projectIdVal to id of project of theTodo
            set projectTitleVal to name of project of theTodo
            if area of project of theTodo is not missing value then
                set areaIdVal to id of area of project of theTodo
                set areaNameVal to name of area of project of theTodo
            end if
        else if area of theTodo is not missing value then
            set parentList to name of area of theTodo
            set parentType to "area"
            set areaIdVal to id of area of theTodo
            set areaNameVal to name of area of theTodo
        end if
        theDict's setValue:parentList forKey:"list"
        theDict's setValue:parentType forKey:"list_type"
        theDict's setValue:projectIdVal forKey:"project_id"
        theDict's setValue:projectTitleVal forKey:"project_title"
        theDict's setValue:areaIdVal forKey:"area_id"
        theDict's setValue:areaNameVal forKey:"area_name"
    end tell

    return theDict
end todo_to_dict

on todos_to_json(theTodos)
    set todoArray to current application's NSMutableArray's array()

    repeat with aTodo in theTodos
        set todoDict to my todo_to_dict(aTodo)
        todoArray's addObject:todoDict
    end repeat

    set {jsonData, theError} to current application's NSJSONSerialization's dataWithJSONObject:todoArray options:0 |error|:(reference)

    if jsonData is missing value then
        error (theError's localizedDescription() as text)
    end if

    set jsonString to current application's NSString's alloc()'s initWithData:jsonData encoding:(current application's NSUTF8StringEncoding)

    return jsonString as text
end todos_to_json

on get_todos_for_project(projectId, includeCompleted)
    tell application "Things3"
        try
            set theProject to project id projectId
        on error
            return "{\"error\": \"Project not found with id " & projectId & "\"}"
        end try

        try
            if includeCompleted then
                set theTodos to to dos of theProject
            else
                -- Open tasks only: exclude completed and canceled
                set theTodos to (to dos of theProject whose status is open)
            end if

            if (count of theTodos) is 0 then
                return "[]"
            else
                return my todos_to_json(theTodos)
            end if
        on error errMsg
            return "{\"error\": \"" & errMsg & "\"}"
        end try
    end tell
end get_todos_for_project
