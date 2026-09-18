use framework "Foundation"
use scripting additions

-- A2: Return a single to-do record by id. Same dict shape as A1/A3.

on run argv
    if (count of argv) < 1 then
        error "Todo id required as argument"
    end if

    set todoId to item 1 of argv
    return my get_todo_by_id(todoId)
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

        if activation date of theTodo is not missing value then
            theDict's setValue:((activation date of theTodo) as string) forKey:"when_date"
        else
            theDict's setValue:"" forKey:"when_date"
        end if

        -- Status
        if status of theTodo is completed then
            theDict's setValue:"completed" forKey:"status"
        else if status of theTodo is canceled then
            theDict's setValue:"canceled" forKey:"status"
        else
            theDict's setValue:"open" forKey:"status"
        end if

        -- Creation/modification stamps — useful for verify-after-write
        try
            if creation date of theTodo is not missing value then
                theDict's setValue:((creation date of theTodo) as string) forKey:"creation_date"
            end if
        end try
        try
            if modification date of theTodo is not missing value then
                theDict's setValue:((modification date of theTodo) as string) forKey:"modification_date"
            end if
        end try

        -- Tags
        set tagList to tag names of theTodo
        if tagList is not {} then
            set AppleScript's text item delimiters to ","
            set tagText to tagList as string
            set AppleScript's text item delimiters to ""
            theDict's setValue:tagText forKey:"tags"
        else
            theDict's setValue:"" forKey:"tags"
        end if

        -- Project/area (A3 shape)
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

        -- Checklist items: Things3's AppleScript dictionary doesn't expose
        -- checklist items as a readable collection (write-only via URL scheme),
        -- so we return an empty array for shape compatibility.
        set clArray to current application's NSMutableArray's array()
        theDict's setValue:clArray forKey:"checklist"
    end tell

    return theDict
end todo_to_dict

on get_todo_by_id(todoId)
    tell application "Things3"
        try
            set theTodo to to do id todoId
        on error
            return "{\"error\": \"Todo not found with id " & todoId & "\"}"
        end try
    end tell

    set todoDict to my todo_to_dict(theTodo)

    set {jsonData, theError} to current application's NSJSONSerialization's dataWithJSONObject:todoDict options:0 |error|:(reference)

    if jsonData is missing value then
        error (theError's localizedDescription() as text)
    end if

    set jsonString to current application's NSString's alloc()'s initWithData:jsonData encoding:(current application's NSUTF8StringEncoding)

    return jsonString as text
end get_todo_by_id
