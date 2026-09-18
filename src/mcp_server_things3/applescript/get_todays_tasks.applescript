use framework "Foundation"
use scripting additions

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
            theDict's setValue:((activation date of theTodo) as string) forKey:"when"
        else
            theDict's setValue:"" forKey:"when"
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
        
        -- Check if it's in evening
        set isEvening to false
        -- This is a simplification - detecting evening tasks is complex in AppleScript
        theDict's setValue:isEvening forKey:"is_evening"

        -- Get project/area info (A3: expose distinct id + name fields)
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
        set todoDict to todo_to_dict(aTodo)
        todoArray's addObject:todoDict
    end repeat
    
    set {jsonData, theError} to current application's NSJSONSerialization's dataWithJSONObject:todoArray options:0 |error|:(reference)
    
    if jsonData is missing value then
        error (theError's localizedDescription() as text)
    end if
    
    set jsonString to current application's NSString's alloc()'s initWithData:jsonData encoding:(current application's NSUTF8StringEncoding)
    
    return jsonString as text
end todos_to_json

tell application "Things3"
    set todayTodos to to dos of list "Today"
    
    if (count of todayTodos) is 0 then
        return "[]"
    else
        return my todos_to_json(todayTodos)
    end if
end tell