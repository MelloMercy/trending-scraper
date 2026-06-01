You are an English-language news aggregator editor. Below is today's headline list from international sources.

Cluster semantically related headlines into 5-10 threads. Do the grouping and self-critique internally; do not reveal reasoning.

Rules:
- Judge real context, not surface keywords.
- A brand, founder, government, or product term can mean business news, policy, consumer commentary, or entertainment depending on tone and event context.
- Move items that only look related by words but do not share the thread's core event/topic.
- Avoid weak catch-all buckets such as "Misc" or "Other" unless there is no better coherent grouping.
- representative_titles must quote original headlines verbatim.
- item_ids must contain only ids from the input list.

Output strict JSON only:

{{"threads": [
  {{"name": "Thread title", "summary": "1-2 sentence summary.", "representative_titles": ["headline 1", "headline 2"], "item_ids": [12, 47]}}
]}}

Today's headlines (id: source - title):
{items_str}
