"""Isolated memory prompt texts (xagent-memory-saas overlay).

All memory-related prompt wording lives in this one file so upstream syncs,
edits and migrations only touch here. Consumption points:

- core/agent/context/execution.py   -> MEMORY_PERSISTENCE_GUIDE
- core/agent/pattern/auto/auto.py   -> AUTO_MEMORY_RULE, AUTO_DURABLE_RULE,
                                        AUTO_DURABLE_FACTS_SCHEMA_DESCRIPTION
- core/agent/context/memory_tool.py -> STORE/SEARCH/UPDATE/DELETE/DELIVER/
                                        CHECK_INBOX _DESCRIPTION

Keep these texts English-only and limited to memory discipline: no product
copy, no CLI tutorials, no repetition of tool schemas.
"""

MEMORY_PERSISTENCE_GUIDE = (
"Memory persistence:\n"
"Use the memory tools for knowledge that should outlive this task. "
"Store one durable fact per call — a stable user preference or "
"correction, a non-obvious mistake and how you fixed it, a reusable "
"lesson about this domain or its tools, or a lasting business or "
"project fact (a client or project name, an identifier, a budget, a "
"deadline, a decision, a constraint) — written as a self-contained "
"statement. Never merge several facts into one entry: each entry is "
"retrieved on its own, so a later search for any one of them must "
"find it. Do not store routine task completions, transient chatter, "
"the answer you just produced, widely known facts, secrets or "
"credentials. Before the final answer, re-read the conversation: "
"every durable fact the user stated and that is not yet stored must "
"be stored now; storing never needs the user's permission.\n"
"Recall by writing one complete sentence about what you need, naming "
"the fact, person, decision or period you are after — retrieval is "
"semantic, so a full sentence finds more than a pile of keywords. If "
"nothing returns, rephrase the same need once and search again. Each "
"hit sits in a tree: follow up with a sentence built from the hit's "
"own subject to reach its parent, children and siblings.\n"
"Respect ownership: a retrieved memory may carry an owner_user_id. "
"When it is not the user you are answering for, say whose fact it is, "
"never restate one person's fact under another person's name, and "
"report several people's facts separately.\n"
"Correct in place: when the user corrects a fact, search_memory for "
"the old statement and update_memory it — storing the corrected "
"sentence beside the old one leaves two rows that disagree. When the "
"user asks you to forget, drop, reset or re-record something, search "
"and delete_memory or update it in the same turn; never claim a "
"stored memory cannot be removed.\n"
"Hand a fact, decision or instruction to a teammate with "
"deliver_memory, addressed by username, external id or agent name; "
"pass relevant memory ids or keywords in attach so the source text "
"travels with it. Call check_inbox when an instruction may have been "
"handed to you from another agent or user; it returns only unread "
"deliveries and marks them read. A [to:<recipient>] marker at the "
"very start of store_memory content is a delivery address — copy it "
"verbatim. [share:dept], [share:company] or [share:dept:<id>] writes "
"to the shared layer instead of your own memory.\n"
"Report writes honestly: when store_memory or deliver_memory returns "
"success false, stored false or an error, the fact is NOT recorded. "
"Retry once in a form that can succeed (for a 409 append-only "
"conflict, store it as a new memory); if the retry also fails, say "
"plainly that the fact was not saved and why. Never imply a write "
"succeeded on the strength of a failed tool result. Never store a "
"fragment ending in an ellipsis; re-derive the complete fact from the "
"conversation or leave it out."
)

AUTO_MEMORY_RULE = (
"If the latest user message asks to remember, store, forget, or "
"update personal information or preferences for future tasks, "
"choose react so the memory tools can persist the change; never "
"claim via final_answer that something was remembered, because "
"final_answer cannot store anything. Likewise, if the user asks "
"what they previously told you or what you remember about them "
"and the retrieved context does not already contain the answer, "
"choose react and search_memory before concluding that nothing "
"was recorded. "
)

AUTO_DURABLE_RULE = (
"Independently of the action, list in durable_facts every stable "
"fact from this conversation that future tasks should remember "
"(client or project names, identifiers, budgets, deadlines, "
"schedules, owners and reporting lines, decisions and their "
"reasons, lasting preferences, corrections stated as the new "
"value), each as a self-contained statement. Emit one entry per "
"fact: a turn that names a deadline, an owner and an amount yields "
"three entries, never one combined sentence and never a partial "
"selection, because each entry is stored separately and anything "
"you omit is forgotten. When unsure whether something is durable, "
"include it. Only pure small talk with no such content yields an "
"empty array; the answer text itself is never a durable fact. "
)

AUTO_DURABLE_FACTS_SCHEMA_DESCRIPTION = (
"Stable facts from this conversation that future "
"tasks should remember, each a self-contained "
"statement (client or project names, identifiers, "
"budgets, deadlines, decisions, lasting "
"preferences). Enumerate every distinct durable "
"fact as its own entry; never merge or omit, "
"because each entry is stored separately and an "
"omitted fact is lost. Use an empty array when "
"nothing is durable; never include transient chat, "
"the final answer itself, or secrets, credentials "
"and personal data that is not meant to persist."
)

STORE_MEMORY_DESCRIPTION = """Store one durable memory for future tasks.

Store a stable user preference or correction, a non-obvious failure and its
fix, a reusable strategy or domain insight, or a lasting business or project
fact (a client or project name, an identifier, a budget, a deadline, a
decision).

Call this once per fact: when one message states a deadline, an owner and an
amount, issue three calls, because each entry is retrieved on its own and a
combined entry makes its parts unfindable.

Do NOT store routine task completions, generic tool usage, common facts,
transient chatter, secrets or credentials. Write the content as a
self-contained statement understandable without this conversation.

If a similar memory already exists, the write is merged into it or attached
under it rather than dropped; read the result. stored false or an error means
nothing was saved: retry a 409 append-only conflict once as a new memory and,
if that also fails, tell the user the fact was not saved instead of implying
it was.

If the content opens with a [to:<recipient>] delivery marker, copy it verbatim
at the very start. Opening it with [share:dept], [share:company] or
[share:dept:<id>] writes to the shared layer instead of your own memory. The
result reports space_kind and space_id: the shared space written to, or null
when the note stayed in your own memory."""

SEARCH_MEMORY_DESCRIPTION = (
"Search stored memories from previous tasks. Retrieval is semantic: "
"write the query as one complete sentence stating what you are looking "
"for — a person, a date, an amount, a place, a decision — because it "
"matches meaning, not exact words. Facts from one message are stored "
"as separate lines, so search each fact you need on its own. If a "
"query returns nothing, rephrase the same need in a different "
"sentence once before concluding the fact was never stored. Each "
"result sits in a tree: after a hit, follow up with a sentence built "
"from that hit's own subject to reach its parent, children and "
"siblings. Results include each memory's id, which update_memory and "
"delete_memory take."
)

UPDATE_MEMORY_DESCRIPTION = (
"Replace the content of a stored memory. Use this when a memory turns "
"out to be outdated or contradicts what you observe now. Find the "
"memory's id with search_memory first."
)

DELETE_MEMORY_DESCRIPTION = (
"Permanently delete a stored memory. Use this when a memory is "
"plainly wrong or harmful and cannot be fixed by update_memory, and "
"whenever the user explicitly asks you to forget, drop or remove "
"something you stored. Find the memory's id with search_memory first."
)

DELIVER_MEMORY_DESCRIPTION = (
"Hand a note to a teammate's own memory instead of keeping it in "
"yours: the recipient's agents retrieve it as if they had stored it "
"themselves. Use it to pass a fact, decision or instruction to the "
"agent or user who will act on it, addressed by username, external id "
"or agent name. It lands in their inbox (read back with check_inbox), "
"is rate-limited per recipient, and never exposes who else is copied. "
"For your own durable facts use store_memory instead."
)

CHECK_INBOX_DESCRIPTION = (
"Read the notes teammates have delivered to you — things other "
"agents or users handed over for you to act on. Use this when the "
"user asks what you were told, when a task refers to a handover, or "
"before acting on an instruction that did not come from this "
"conversation. Returns the newest deliveries first, each with its "
"content, sender and time. Facts stored by your own past tasks are "
"found with search_memory instead."
)
