**English** | [Русский](README.ru.md)

# Day 12 — Assistant Personalization

Day 12 adds user personalization on top of the three memory layers from Day 11. The user no longer has to repeat the preferred language, level of detail, style, response format, and constraints: the active profile is automatically attached to every prompt.

## User profiles

Each JSON file in `config/profiles/` defines:

| Field | Purpose |
|---|---|
| `id` | Stable profile identifier |
| `name`, `role` | User identity and role |
| `language` | Response language |
| `detail_level` | Expected answer depth |
| `style` | Communication preferences |
| `response_format` | Output structure rules |
| `constraints` | User-specific restrictions |

Bublik's identity lives separately in `config/assistant.json`, so assistant configuration is not mixed with user preferences.

Two deliberately different profiles are included:

- `cheburator` requests concise, conclusion-first answers and short lists;
- `scientist` requests detailed sections, comparisons, uncertainty, and risk analysis.

## Profiles and memory

A profile is selected when a dialogue is created, and its `profile_id` is stored in `conversations`. Both conversation history and personalization are therefore restored after a restart.

| Data | Scope |
|---|---|
| Short-term messages | Current dialogue |
| Working memory | Current dialogue and task |
| Long-term decisions and knowledge | All dialogues of one profile |
| Preferences | Selected user profile |

Long-term records are scoped by `profile_id`, preventing one user's decisions from entering another user's context. A profile can be changed with `/profile PROFILE_ID` only while the dialogue and its working memory are empty.

## Every request

`MemoryPromptBuilder` constructs the prompt in this fixed order:

```text
assistant identity + invariants
user profile: language + detail + style + format + constraints
long-term memory for the selected profile
working memory for the current dialogue
last 6 short-term messages
current user request
```

The profile is loaded inside `get_context_preview()`, which runs before every `process()` call. The `/context` command shows the exact prompt before it is sent to Groq.

## Run

```bash
pip install -r requirements.txt
python day-12-personalization/main.py
```

Day 11 commands remain available. Day 12 adds:

- `/profile` — show the active profile;
- `/profile PROFILE_ID` — change the profile of an empty dialogue;
- `/context` — verify that personalization is included;
- `/dialogs` — create another dialogue with another profile.

## Verification

Run 12 local tests without API calls:

```bash
python -m unittest discover -s day-12-personalization -p "test_*.py" -v
```

They verify different profiles, automatic profile injection into every request, persistence, profile-scoped long-term memory, safe profile switching, and all inherited Day 11 memory/state-machine behavior.

To compare real responses for the same question and working memory:

```bash
python day-12-personalization/experiment.py
```

Cheburator's answer should be short and conclusion-first. Doctor Lyra's answer should be more detailed, structured, and risk-aware, even though neither request repeats those preferences.

## Result

Bublik is now a personalized agent. The selected profile persists with the dialogue, affects every response automatically, and remains isolated from other profiles while the explicit three-layer memory model continues to work.
