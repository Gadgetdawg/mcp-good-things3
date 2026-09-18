use framework "Foundation"
use scripting additions

-- A4: Return full project record (id, title, notes, area, headings, counts)
-- for a given project id. Complements A1 (which lists todos only).

on run argv
    if (count of argv) < 1 then
        error "Project id required as argument"
    end if

    set projectId to item 1 of argv
    return my get_project_details(projectId)
end run

on project_to_dict(theProject)
    set theDict to current application's NSMutableDictionary's dictionary()

    tell application "Things3"
        theDict's setValue:(id of theProject) forKey:"id"
        theDict's setValue:(name of theProject) forKey:"title"

        if notes of theProject is not missing value then
            theDict's setValue:(notes of theProject) forKey:"notes"
        else
            theDict's setValue:"" forKey:"notes"
        end if

        -- Status: active / completed / canceled
        set projStatus to status of theProject as string
        theDict's setValue:projStatus forKey:"status"

        -- Dates
        if due date of theProject is not missing value then
            theDict's setValue:((due date of theProject) as string) forKey:"due_date"
        else
            theDict's setValue:"" forKey:"due_date"
        end if

        if activation date of theProject is not missing value then
            theDict's setValue:((activation date of theProject) as string) forKey:"when_date"
        else
            theDict's setValue:"" forKey:"when_date"
        end if

        -- Area info (A3 shape)
        if area of theProject is not missing value then
            theDict's setValue:(id of area of theProject) forKey:"area_id"
            theDict's setValue:(name of area of theProject) forKey:"area_name"
        else
            theDict's setValue:"" forKey:"area_id"
            theDict's setValue:"" forKey:"area_name"
        end if

        -- Tags
        set tagList to tag names of theProject
        if tagList is not {} then
            set AppleScript's text item delimiters to ","
            set tagText to tagList as string
            set AppleScript's text item delimiters to ""
            theDict's setValue:tagText forKey:"tags"
        else
            theDict's setValue:"" forKey:"tags"
        end if

        -- Todo counts
        set allTodos to to dos of theProject
        set totalCount to count of allTodos
        set openCount to 0
        repeat with aTodo in allTodos
            if status of aTodo is open then
                set openCount to openCount + 1
            end if
        end repeat
        theDict's setValue:totalCount forKey:"todo_count_total"
        theDict's setValue:openCount forKey:"todo_count_open"

        -- Headings in the project
        set headingArray to current application's NSMutableArray's array()
        try
            set allHeadings to headings of theProject
            repeat with aHeading in allHeadings
                set hDict to current application's NSMutableDictionary's dictionary()
                hDict's setValue:(id of aHeading) forKey:"id"
                hDict's setValue:(name of aHeading) forKey:"title"
                -- Headings can be archived
                try
                    hDict's setValue:(archived of aHeading) forKey:"archived"
                on error
                    hDict's setValue:false forKey:"archived"
                end try
                headingArray's addObject:hDict
            end repeat
        on error
            -- Older Things3 may not expose headings; leave empty
        end try
        theDict's setValue:headingArray forKey:"headings"
    end tell

    return theDict
end project_to_dict

on get_project_details(projectId)
    tell application "Things3"
        try
            set theProject to project id projectId
        on error
            return "{\"error\": \"Project not found with id " & projectId & "\"}"
        end try
    end tell

    set projDict to my project_to_dict(theProject)

    set {jsonData, theError} to current application's NSJSONSerialization's dataWithJSONObject:projDict options:0 |error|:(reference)

    if jsonData is missing value then
        error (theError's localizedDescription() as text)
    end if

    set jsonString to current application's NSString's alloc()'s initWithData:jsonData encoding:(current application's NSUTF8StringEncoding)

    return jsonString as text
end get_project_details
