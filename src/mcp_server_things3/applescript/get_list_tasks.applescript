use framework "Foundation"
use scripting additions

(*
get_list_tasks_bulk.applescript — same JSON as get_list_tasks.applescript, at a fraction of the Apple Events.

WHAT WAS WRONG. The original reads 23 properties per to-do, and every one of those reads is a separate Apple
Event round trip to Things3, inside a per-item loop. Measured: Anytime — which holds every to-do of every
active project — took 81.1 seconds. Today, at 10 items, took 1.7s and has therefore never looked like a
problem. things_snapshot.py timed out past 130s reading the lists in order and dying on Anytime.
The list you look at first is the one that does not hurt.

THE FIX, in two parts.

1. FLAT PROPERTIES ARE FETCHED IN BULK. `id of to dos of list "Anytime"` is ONE Apple Event that returns the
   whole column. Seven such fetches replace 7 x N reads. Everything after that is local list arithmetic,
   which costs nothing. Measured: Anytime 81.1s -> 5.0s.

2. PARENTAGE IS RESOLVED BY INVERSION. The expensive field is "which project or area owns this to-do",
   because `project of theTodo` is a per-item chain. This walks the other way: ask each PROJECT for its
   to-do ids once and build a todo-id -> parent map. Tens of events instead of thousands.

WHAT WAS MEASURED, AND WHY THE OBVIOUS SHORTCUTS ARE NOT USED HERE.
See ops/measurements/bulkprobe_*.txt and bulkprobe2_*.txt. Each of these was tried and rejected on evidence,
not on taste:

  * `id of project of to dos of list L` DOES work — and silently DROPS the missing values. Ten to-dos in
    Today, six results. That column cannot be zipped against the id column, and code that tried would
    attach one to-do's project to a different to-do's id. Unusable, and wrong in a way that looks right.
  * `to dos of list L whose project is not missing value` — which would make both sides drop the same rows
    and therefore line up — fails: "Can't make project into type specifier." Things3 does not filter on
    object-valued properties. `projects whose area is not missing value` fails the same way.
  * `projects of area id X` fails: "Can't get every project of area." `projects` is not an element of
    `area`. Assuming that it was is precisely what emptied area_id and area_name on 1,010 to-dos in the
    first draft of this file, which the equivalence gate caught.
  * Bulk gets work only against a LIVE element reference. `tag names of to dos of list L` is fine;
    `tag names of {...a materialised list of specifiers...}` is error -1728.

So each project's area is fetched individually — one event, with the area NAME resolved from an in-memory
table rather than a second round trip. Two events per project, once per invocation, is what getting the
answer right actually costs here.

TAG ORDER — A DELIBERATE, DOCUMENTED CONTRACT CHANGE. This is the one place the output is NOT identical to
the old reader's, and it is a change made on evidence rather than a bug worked around.

`tag names` returns a comma-joined STRING, not a list — "KIZ, Audrey, KIZ-Resolved". The bulk path
(`tag names of to dos of list L`) and the per-item path (`tag names of to do id X`) do not always return
that string in the same order. Measured across the whole database: Upcoming 68 tagged to-dos, all identical;
Someday 3, all identical; Inbox, Today and Anytime each contain to-dos where the two paths disagree.

My first attempt assumed the disagreement was a clean reversal — four cases looked like one — and it is not:
68 of 68 identical in Upcoming refutes a universal reversal outright. There is no order to preserve here.
A Things to-do's tags are a SET, the app exposes no ordering the user controls, and the two access paths
disagreeing is itself the proof that whatever order comes back is an artifact of the API rather than data.

Preserving an artifact would cost one Apple Event per tagged to-do, forever, to reproduce something
meaningless. So the tags are SORTED, case-insensitively. That also makes the column deterministic, which
matters more than it sounds: shadow_compare.py diffs snapshots to decide whether an automation changed a
to-do, and a tags field whose order depends on how it was read would manufacture phantom updates.

Consumers that treat tags as a set — which is all of them, since that is what tags are — are unaffected.
verify_bulk_equivalence.py compares this field as a set and says so in its output.

OUTPUT CONTRACT. Identical keys and identical values to the original for every to-do. Key ORDER differs,
because NSJSONSerialization does not preserve it and never did — so the two are compared parsed, not as
bytes. scripts/verify_bulk_equivalence.py does that comparison and is the gate on shipping this.

READ ONLY. Every operation here is a `get`.
*)

on run argv
    if (count of argv) < 1 then
        error "List name required as argument"
    end if

    set listName to item 1 of argv

    if listName is not in {"Today", "Inbox", "Anytime", "Upcoming", "Someday", "Logbook", "Trash"} then
        error "Invalid list name. Valid lists: Today, Inbox, Anytime, Upcoming, Someday, Logbook, Trash"
    end if

    return my get_tasks_from_list(listName)
end run


(*
build_parent_map(listName) -- todo id -> {list, list_type, project_id, project_title, area_id, area_name}

Two passes, in this order, because the second must win: a to-do belonging to a project INSIDE an area is
reported by the original reader as belonging to the PROJECT, with the area carried along. Areas are walked
first so direct-in-area to-dos are recorded, then projects overwrite any to-do they own.

A to-do in NEITHER — an Inbox item, typically — gets no entry, and the caller fills in the same empty
strings the original produced.

ONLY THE PARENTS THIS LIST ACTUALLY USES ARE WALKED. The first working version rebuilt the whole database's
parentage on every call: 67 projects x 2 events, every time. It fixed Anytime (80.5s -> 6.8s) and made the
SMALL lists worse — Today went 1.8s -> 4.4s — which is a poor trade to leave in place when the small lists
are the ones a human waits on.

`id of project of to dos of list L` drops the missing values and so cannot be zipped against the id column
(see the notes at the top). But as a SET — "which projects appear in this list at all" — it is exactly
right, and that is all this needs. Today touches about six projects, not sixty-seven.
*)
on build_parent_map(listName)
    set m to current application's NSMutableDictionary's dictionary()

    tell application "Things3"
        -- Name tables. Four events total, regardless of list size, and they spare a round trip per parent
        -- later: an id resolved here never has to be asked for its name.
        set areaIds to {}
        set areaNames to {}
        try
            set areaIds to id of areas
            set areaNames to name of areas
        on error errMsg
            log "build_parent_map: areas unreadable: " & errMsg
        end try

        set projIds to {}
        set projNames to {}
        try
            set projIds to id of projects
            set projNames to name of projects
        on error errMsg
            log "build_parent_map: project list unreadable: " & errMsg
        end try

        -- Which parents appear in THIS list. One event each. Both forms drop `missing value`, which is
        -- harmless here and useless anywhere else.
        --
        -- If either probe fails, fall back to walking everything. Slower, never wrong — and the fallback is
        -- LOGGED, because a silent fallback that merely looks slow is how a real breakage hides for weeks.
        set wantProj to {}
        try
            set wantProj to my dedupe(id of project of to dos of list listName)
        on error errMsg
            log "build_parent_map: present-project probe failed (" & errMsg & ") — walking all projects"
            set wantProj to projIds
        end try

        set wantArea to {}
        try
            set wantArea to my dedupe(id of area of to dos of list listName)
        on error errMsg
            log "build_parent_map: present-area probe failed (" & errMsg & ") — walking all areas"
            set wantArea to areaIds
        end try

        -- PASS 1: to-dos living DIRECTLY in an area, with no project between them and it.
        repeat with aidRef in wantArea
            set aid to contents of aidRef
            set aname to my lookup_name(aid, areaIds, areaNames)
            try
                set directIds to id of to dos of area id aid
                repeat with tidRef in directIds
                    set d to current application's NSMutableDictionary's dictionary()
                    d's setValue:aname forKey:"list"
                    d's setValue:"area" forKey:"list_type"
                    d's setValue:"" forKey:"project_id"
                    d's setValue:"" forKey:"project_title"
                    d's setValue:aid forKey:"area_id"
                    d's setValue:aname forKey:"area_name"
                    m's setObject:d forKey:(contents of tidRef)
                end repeat
            on error errMsg
                -- An unreadable area must stay visible, not become silently equivalent to an empty one. Its
                -- to-dos resolve with blank parent fields, which shows in the output rather than appearing
                -- confidently correct.
                log "build_parent_map: area " & aid & " to dos unreadable: " & errMsg
            end try
        end repeat

        -- PASS 2: the projects this list touches, and the to-dos they own.
        repeat with pidRef in wantProj
            set pid to contents of pidRef
            set pname to my lookup_name(pid, projIds, projNames)

            -- One event. It ERRORS rather than returning missing value when a project has no area, which is
            -- why this is wrapped rather than tested. The bulk form `id of area of projects` would be one
            -- event for all of them and drops the arealess ones, so it cannot be aligned.
            set aid to ""
            try
                set aid to id of area of project id pid
            on error
                set aid to ""
            end try
            set aname to ""
            if aid is not "" then set aname to my lookup_name(aid, areaIds, areaNames)

            try
                set kidIds to id of to dos of project id pid
            on error errMsg
                log "build_parent_map: project " & pid & " to dos unreadable: " & errMsg
                set kidIds to {}
            end try

            repeat with tidRef in kidIds
                set d to current application's NSMutableDictionary's dictionary()
                d's setValue:pname forKey:"list"
                d's setValue:"project" forKey:"list_type"
                d's setValue:pid forKey:"project_id"
                d's setValue:pname forKey:"project_title"
                d's setValue:aid forKey:"area_id"
                d's setValue:aname forKey:"area_name"
                m's setObject:d forKey:(contents of tidRef)
            end repeat
        end repeat
    end tell

    return m
end build_parent_map


(* Distinct values, order preserved, via a dictionary so this stays linear rather than quadratic on Anytime. *)
on dedupe(theList)
    set seen to current application's NSMutableDictionary's dictionary()
    set out to {}
    repeat with xRef in theList
        set x to contents of xRef
        if x is not missing value and x is not "" then
            if (seen's objectForKey:x) is missing value then
                seen's setObject:"1" forKey:x
                set end of out to x
            end if
        end if
    end repeat
    return out
end dedupe


(* Name for an id, from the parallel id/name columns fetched once up front. No Apple Event. *)
on lookup_name(theId, ids, names)
    repeat with i from 1 to count of ids
        if item i of ids is theId then return item i of names
    end repeat
    return ""
end lookup_name


on get_tasks_from_list(listName)
    set parentMap to my build_parent_map(listName)

    tell application "Things3"
        try
            -- SEVEN EVENTS, whatever the list size. This is the whole point of the rewrite.
            set theList to list listName
            set idL to id of to dos of theList
            set n to count of idL
            if n is 0 then return "[]"

            set nameL to name of to dos of theList
            set notesL to notes of to dos of theList
            set dueL to due date of to dos of theList
            set actL to activation date of to dos of theList
            set statL to status of to dos of theList
            set tagL to tag names of to dos of theList

            -- A short column means Things3 disagreed with itself between two gets — a to-do was created or
            -- removed mid-read. Refusing is right: a row built from misaligned columns would attribute one
            -- to-do's title to another to-do's id, and nothing downstream could detect it.
            if (count of nameL) is not n or (count of notesL) is not n or (count of dueL) is not n ¬
                or (count of actL) is not n or (count of statL) is not n or (count of tagL) is not n then
                error "list changed while being read (column lengths disagree) — retry"
            end if

            set todoArray to current application's NSMutableArray's array()

            repeat with i from 1 to n
                set theDict to current application's NSMutableDictionary's dictionary()
                set tid to item i of idL

                theDict's setValue:tid forKey:"id"
                theDict's setValue:(item i of nameL) forKey:"title"

                set v to item i of notesL
                if v is missing value then
                    theDict's setValue:"" forKey:"notes"
                else
                    theDict's setValue:v forKey:"notes"
                end if

                set v to item i of dueL
                if v is missing value then
                    theDict's setValue:"" forKey:"due_date"
                else
                    theDict's setValue:(v as string) forKey:"due_date"
                end if

                set v to item i of statL
                if v is completed then
                    theDict's setValue:"completed" forKey:"status"
                else if v is canceled then
                    theDict's setValue:"canceled" forKey:"status"
                else
                    theDict's setValue:"open" forKey:"status"
                end if

                set v to item i of actL
                if v is missing value then
                    theDict's setValue:"" forKey:"when_date"
                else
                    theDict's setValue:(v as string) forKey:"when_date"
                end if

                -- SORTED. See the TAG ORDER note at the top of this file: the order Things hands back is an
                -- artifact of which access path you used, so this pins it instead of inheriting it.
                set tagStr to item i of tagL
                if tagStr is missing value or tagStr is "" then
                    theDict's setValue:"" forKey:"tags"
                else
                    set AppleScript's text item delimiters to ", "
                    set parts to text items of tagStr
                    set AppleScript's text item delimiters to ""
                    set sortedTags to (current application's NSArray's arrayWithArray:parts)'s ¬
                        sortedArrayUsingSelector:"localizedCaseInsensitiveCompare:"
                    theDict's setValue:((sortedTags's componentsJoinedByString:", ") as text) forKey:"tags"
                end if

                set p to (parentMap's objectForKey:tid)
                if p is missing value then
                    theDict's setValue:"" forKey:"list"
                    theDict's setValue:"" forKey:"list_type"
                    theDict's setValue:"" forKey:"project_id"
                    theDict's setValue:"" forKey:"project_title"
                    theDict's setValue:"" forKey:"area_id"
                    theDict's setValue:"" forKey:"area_name"
                else
                    repeat with k in {"list", "list_type", "project_id", "project_title", "area_id", "area_name"}
                        theDict's setValue:(p's objectForKey:(contents of k)) forKey:(contents of k)
                    end repeat
                end if

                todoArray's addObject:theDict
            end repeat

            return my array_to_json(todoArray)
        on error errMsg
            return "{\"error\": \"" & errMsg & "\"}"
        end try
    end tell
end get_tasks_from_list


on array_to_json(todoArray)
    set {jsonData, theError} to current application's NSJSONSerialization's dataWithJSONObject:todoArray options:0 |error|:(reference)

    if jsonData is missing value then
        error (theError's localizedDescription() as text)
    end if

    set jsonString to current application's NSString's alloc()'s initWithData:jsonData encoding:(current application's NSUTF8StringEncoding)

    return jsonString as text
end array_to_json
