from pathlib import Path

import customtkinter as ctk
import threading
import ollama
import re

PROJECT_DIR = Path(__file__).resolve().parent

from database import (
    initialize_database,
    save_memory,
    get_memories,
    delete_memory,
    update_memory,
    save_context,
    get_recent_context,
    clear_old_context,
    get_companion_settings,
)

from web_search import (
    search_web,
    format_results,
)


# ============================================================
# SETTINGS
# ============================================================

MODEL = "llama3.2:3b"

initialize_database()
clear_old_context(7)

conversation = []


# ============================================================
# EMOTION DETECTION
# ============================================================

def detect_emotion(text):

    text = text.lower()

    emotions = {

        "happy": [
            "happy", "glad", "great", "awesome",
            "wonderful", "yay", "feeling good"
        ],

        "excited": [
            "excited", "so excited", "can't wait",
            "cant wait", "looking forward"
        ],

        "sad": [
            "sad", "upset", "unhappy", "lonely",
            "heartbroken", "feeling down",
            "feel bad", "depressed"
        ],

        "angry": [
            "angry", "mad", "furious",
            "pissed", "hate this"
        ],

        "frustrated": [
            "frustrated", "frustrating",
            "annoying", "ugh"
        ],

        "worried": [
            "worried", "worry", "nervous",
            "anxious", "scared", "afraid",
            "concerned"
        ],

        "confused": [
            "confused", "don't understand",
            "dont understand"
        ],

        "tired": [
            "tired", "exhausted",
            "sleepy", "worn out"
        ],

        "proud": [
            "proud", "i did it",
            "finally did it"
        ],

        "relieved": [
            "relieved", "thank god",
            "what a relief"
        ]
    }

    for emotion, words in emotions.items():

        for word in words:

            if word in text:
                return emotion

    return None


# ============================================================
# PERSONAL MESSAGE DETECTOR
# ============================================================

def is_personal_message(text):

    text = text.lower()

    patterns = [

        r"\bi\b",
        r"\bme\b",
        r"\bmy\b",
        r"\bmine\b",
        r"\bmyself\b",

        r"\bi'm\b",
        r"\bim\b",
        r"\bi am\b",

        r"\bi've\b",
        r"\bive\b",
        r"\bi have\b",

        r"\bi like\b",
        r"\bi love\b",
        r"\bi hate\b",
        r"\bi enjoy\b",
        r"\bi prefer\b",

        r"\bi want\b",
        r"\bi need\b",
        r"\bi hope\b",
        r"\bi wish\b",

        r"\bi think\b",
        r"\bi believe\b",
        r"\bi feel\b",
        r"\bi remember\b",

        r"\bi used to\b",
        r"\bwhen i was\b",
        r"\bwhen i was younger\b",
        r"\bwhen i was a kid\b",
        r"\bgrowing up\b",

        r"\bmy life\b",
        r"\bmy past\b",
        r"\bmy future\b",
        r"\bmy story\b",

        r"\bmy goal\b",
        r"\bmy dream\b",
        r"\bmy plan\b",

        r"\bmy family\b",
        r"\bmy parents\b",
        r"\bmy mother\b",
        r"\bmy father\b",
        r"\bmy mom\b",
        r"\bmy dad\b",
        r"\bmy brother\b",
        r"\bmy sister\b",

        r"\bmy friend\b",
        r"\bmy friends\b",

        r"\bmy school\b",
        r"\bmy college\b",
        r"\bmy education\b",

        r"\bmy job\b",
        r"\bmy work\b",
        r"\bmy career\b",

        r"\bmy hobby\b",
        r"\bmy hobbies\b",
        r"\bmy interests\b",

        r"\bmy personality\b",
        r"\bmy behavior\b",
        r"\bmy behaviour\b",
        r"\bmy habits\b"
    ]

    return any(
        re.search(pattern, text)
        for pattern in patterns
    )


# ============================================================
# CLEAN MEMORY
# ============================================================

def clean_memory(text):

    text = text.strip()

    text = re.sub(
        r"^(memory|new|update)\s*:\s*",
        "",
        text,
        flags=re.IGNORECASE
    )

    text = text.strip("\"' ")

    if text.upper() in {
        "NONE",
        "N/A",
        "NULL",
        "NO MEMORY"
    }:
        return None

    if len(text) < 5:
        return None

    return text


# ============================================================
# MEMORY ANALYZER
# ============================================================

def analyze_memory(user_text, memories):

    existing = ""

    for row in memories:

        memory_id = row[0]
        memory = row[1]
        category = row[2]

        existing += (
            f"ID {memory_id} "
            f"[{category}]: "
            f"{memory}\n"
        )

    prompt = f"""
You are the long-term memory manager
for a personal AI companion.

USER MESSAGE:
{user_text}

EXISTING MEMORIES:
{existing if existing else "NONE"}

Your job is to decide whether this message
contains meaningful information about the USER.

REMEMBER meaningful information about:

- personality
- behavior
- preferences
- likes
- dislikes
- hobbies
- interests
- goals
- dreams
- education
- career
- family
- friends
- relationships
- important people
- childhood
- important life experiences
- life stories
- current circumstances
- future plans

DO NOT remember:

- normal questions
- random facts
- ordinary greetings
- simple jokes
- temporary conversation
- things about the AI
- information that clearly has no future value

If the user tells a meaningful story about their life,
remember the important meaning of the story,
not every tiny detail.

If an existing memory has changed,
UPDATE the old memory instead of creating a duplicate.

People change over time.

For example:

"I used to play games every day."

followed later by:

"I don't play games much anymore."

means the newer information should replace
or update the older information.

If the user says:

"I might learn Italian."

remember that they are considering it,
not that they definitely do it.

Categories:

general
personality
behavior
preference
interest
hobby
goal
dream
education
career
family
friend
relationship
life
past
present
future

Return ONLY ONE command:

NEW: <category> | <memory>

OR

UPDATE: <numeric ID> | <category> | <memory>

OR

NONE

Never explain.
"""

    try:

        response = ollama.chat(
            model=MODEL,
            messages=[
                {
                    "role": "system",
                    "content": prompt
                }
            ]
        )

        return response["message"]["content"].strip()

    except Exception:

        return "NONE"


# ============================================================
# APPLY MEMORY COMMAND
# ============================================================

def apply_memory_command(result, memories):

    if not result:
        return 0, 0

    result = result.strip()

    # --------------------------------------------------------
    # NEW
    # --------------------------------------------------------

    match = re.match(
        r"^NEW\s*:\s*([^|]+)\|\s*(.+)$",
        result,
        flags=re.IGNORECASE
    )

    if match:

        category = (
            match.group(1)
            .strip()
            .lower()
        )

        memory = clean_memory(
            match.group(2)
        )

        if not memory:
            return 0, 0

        valid_categories = {
            "general",
            "personality",
            "behavior",
            "preference",
            "interest",
            "hobby",
            "goal",
            "dream",
            "education",
            "career",
            "family",
            "friend",
            "relationship",
            "life",
            "past",
            "present",
            "future"
        }

        if category not in valid_categories:
            category = "general"

        for row in memories:

            if (
                row[1].strip().lower()
                == memory.strip().lower()
            ):
                return 0, 0

        save_memory(
            memory,
            category
        )

        return 1, 0

    # --------------------------------------------------------
    # UPDATE
    # --------------------------------------------------------

    match = re.match(
        r"^UPDATE\s*:\s*(\d+)\s*\|\s*([^|]+)\|\s*(.+)$",
        result,
        flags=re.IGNORECASE
    )

    if match:

        memory_id = int(
            match.group(1)
        )

        category = (
            match.group(2)
            .strip()
            .lower()
        )

        memory = clean_memory(
            match.group(3)
        )

        if not memory:
            return 0, 0

        valid_id = any(
            row[0] == memory_id
            for row in memories
        )

        if not valid_id:
            return 0, 0

        update_memory(
            memory_id,
            memory,
            category
        )

        return 0, 1

    return 0, 0


# ============================================================
# WEB SEARCH DECISION
# ============================================================

def should_search_web(user_text):

    text = user_text.lower().strip()

    # Explicit requests to search
    explicit = [
        "search the internet",
        "search online",
        "search the web",
        "look it up",
        "look this up",
        "google this",
        "find online",
        "find me online",
        "check online",
        "check the internet"
    ]

    if any(
        phrase in text
        for phrase in explicit
    ):
        return True

    # Current-information indicators
    current_words = [
        "latest",
        "newest",
        "today",
        "tonight",
        "tomorrow",
        "currently",
        "right now",
        "this week",
        "this month",
        "2026",
        "price",
        "cost",
        "release date",
        "released",
        "available now",
        "stock",
        "weather",
        "news"
    ]

    if any(
        word in text
        for word in current_words
    ):
        return True

    # Requests for external research
    research_patterns = [
        "where can i buy",
        "where can i get",
        "where can i apply",
        "find me",
        "recommend me",
        "what are the best",
        "compare",
        "reviews of",
        "is there a",
        "are there any",
        "what happened",
        "who won",
        "who is currently",
        "how much does"
    ]

    if any(
        phrase in text
        for phrase in research_patterns
    ):
        return True

    return False


# ============================================================
# WEB SEARCH
# ============================================================

def perform_web_search(query):

    try:

        response = search_web(
            query,
            max_results=5
        )

        return format_results(
            response
        )

    except Exception as e:

        return (
            "Web search failed: "
            + str(e)
        )


# ============================================================
# MAIN APPLICATION
# ============================================================

class DesktopCompanion(ctk.CTk):

    def __init__(self):

        super().__init__()

        self.title(
            "AI Desktop Companion"
        )

        self.geometry(
            "900x720"
        )

        self.minsize(
            650,
            500
        )

        self.setup_ui()

    # ========================================================
    # UI
    # ========================================================

    def setup_ui(self):

        header = ctk.CTkFrame(
            self,
            corner_radius=0
        )

        header.pack(
            fill="x"
        )

        title = ctk.CTkLabel(
            header,
            text="AI Desktop Companion",
            font=(
                "Segoe UI",
                22,
                "bold"
            )
        )

        title.pack(
            side="left",
            padx=20,
            pady=15
        )

        self.status = ctk.CTkLabel(
            header,
            text="● Ready",
            font=(
                "Segoe UI",
                13
            )
        )

        self.status.pack(
            side="right",
            padx=20
        )

        self.chat = ctk.CTkTextbox(
            self,
            font=(
                "Segoe UI",
                15
            ),
            wrap="word",
            corner_radius=12
        )

        self.chat.pack(
            fill="both",
            expand=True,
            padx=20,
            pady=15
        )

        self.chat.configure(
            state="disabled"
        )

        bottom = ctk.CTkFrame(
            self,
            fg_color="transparent"
        )

        bottom.pack(
            fill="x",
            padx=20,
            pady=(0, 20)
        )

        self.entry = ctk.CTkEntry(
            bottom,
            placeholder_text="Talk to your companion...",
            font=(
                "Segoe UI",
                14
            ),
            height=45
        )

        self.entry.pack(
            side="left",
            fill="x",
            expand=True,
            padx=(0, 10)
        )

        self.send_button = ctk.CTkButton(
            bottom,
            text="Send",
            width=100,
            height=45,
            command=self.send_message
        )

        self.send_button.pack(
            side="right"
        )

        self.entry.bind(
            "<Return>",
            lambda event: self.send_message()
        )

        self.add_message(
            "Companion\n"
            "Hey! I'm ready. 😎"
        )

        self.entry.focus()

    # ========================================================
    # DISPLAY
    # ========================================================

    def add_message(self, text):

        self.chat.configure(
            state="normal"
        )

        self.chat.insert(
            "end",
            text + "\n\n"
        )

        self.chat.configure(
            state="disabled"
        )

        self.chat.see(
            "end"
        )

    # ========================================================
    # SEND
    # ========================================================

    def send_message(self):

        user_text = (
            self.entry
            .get()
            .strip()
        )

        if not user_text:
            return

        self.entry.delete(
            0,
            "end"
        )

        # ----------------------------------------------------
        # MEMORIES
        # ----------------------------------------------------

        if user_text.lower() == "/memories":

            self.show_memories()

            return

        # ----------------------------------------------------
        # FORGET
        # ----------------------------------------------------

        if user_text.lower().startswith(
            "/forget "
        ):

            try:

                memory_id = int(
                    user_text[8:].strip()
                )

                if delete_memory(
                    memory_id
                ):

                    self.add_message(
                        f"🗑️ Memory {memory_id} forgotten."
                    )

                else:

                    self.add_message(
                        "Memory not found."
                    )

            except ValueError:

                self.add_message(
                    "Use: /forget <memory number>"
                )

            return

        # ----------------------------------------------------
        # MANUAL MEMORY
        # ----------------------------------------------------

        if user_text.lower().startswith(
            "/remember "
        ):

            memory = (
                user_text[10:]
                .strip()
            )

            if memory:

                memory_id = save_memory(
                    memory,
                    "general"
                )

                self.add_message(
                    f"🧠 Saved memory #{memory_id}\n"
                    f"{memory}"
                )

            return

        # ----------------------------------------------------
        # NORMAL MESSAGE
        # ----------------------------------------------------

        self.add_message(
            f"You\n{user_text}"
        )

        conversation.append(
            {
                "role": "user",
                "content": user_text
            }
        )

        self.send_button.configure(
            state="disabled"
        )

        self.entry.configure(
            state="disabled"
        )

        self.status.configure(
            text="● Thinking..."
        )

        threading.Thread(
            target=self.process_message,
            args=(user_text,),
            daemon=True
        ).start()

    # ========================================================
    # PROCESS
    # ========================================================

    def process_message(self, user_text):

        try:

            memories = get_memories()

            recent = get_recent_context(
                30
            )

            settings = get_companion_settings()

            personality = settings.get(
                "personality",
                "friendly, curious, playful, warm, natural and emotionally aware"
            )

            relationship_style = settings.get(
                "relationship_style",
                "consistent, caring, curious and conversational without being intrusive"
            )

            # ------------------------------------------------
            # EMOTION
            # ------------------------------------------------

            current_emotion = detect_emotion(
                user_text
            )

            # ------------------------------------------------
            # SAVE RECENT EVENT
            # ------------------------------------------------

            save_context(
                user_text,
                current_emotion
            )

            # ------------------------------------------------
            # RECENT CONTEXT
            # ------------------------------------------------

            recent_text = ""

            for row in reversed(recent):

                message = row[1]
                emotion = row[2]
                created_at = row[3]

                recent_text += (
                    f"{created_at}: "
                    f"{message}"
                )

                if emotion:

                    recent_text += (
                        f" [emotion: {emotion}]"
                    )

                recent_text += "\n"

            # ------------------------------------------------
            # LONG-TERM MEMORY
            # ------------------------------------------------

            memory_text = ""

            for row in memories:

                memory_id = row[0]
                memory = row[1]
                category = row[2]

                memory_text += (
                    f"ID {memory_id} "
                    f"[{category}]: "
                    f"{memory}\n"
                )

            # ------------------------------------------------
            # WEB SEARCH
            # ------------------------------------------------

            web_information = ""

            if should_search_web(
                user_text
            ):

                self.after(
                    0,
                    lambda:
                    self.status.configure(
                        text="● Searching the web..."
                    )
                )

                web_information = (
                    perform_web_search(
                        user_text
                    )
                )

            # ------------------------------------------------
            # SYSTEM PROMPT
            # ------------------------------------------------

            system_prompt = f"""
You are a personal AI desktop companion.

============================================================
YOUR PERSONALITY
============================================================

You are:

- friendly
- curious
- warm
- playful when appropriate
- emotionally aware
- helpful
- natural
- conversational

Do not sound like a generic customer-service chatbot.

============================================================
IMPORTANT
============================================================

You are an AI.

Do not pretend to be a human or claim
to have physical experiences.

But communicate naturally and warmly.

============================================================
USER'S LONG-TERM MEMORY
============================================================

{memory_text if memory_text else "No long-term memories yet."}

Use these memories when relevant.

Never invent memories.

Do not mention the database or memory system
unless the user asks about it.

============================================================
RECENT EVENTS
============================================================

{recent_text if recent_text else "No recent events available."}

Use recent events to understand continuity.

Do not treat every recent message as a permanent fact.

============================================================
CURRENT EMOTION
============================================================

{current_emotion if current_emotion else "unknown"}

If the user seems sad, upset, lonely,
frustrated, worried or disappointed:

- acknowledge it naturally
- be supportive
- don't dismiss the feeling
- don't immediately lecture
- if appropriate, try gently cheering them up
- offer something useful or enjoyable
- give them the choice to talk or be distracted

If they don't want to talk,
respect that.

============================================================
EMOTIONAL CONTINUITY
============================================================

Notice changes in mood.

If the user was excited yesterday
and sad today, you may mention the change.

Example:

"You sounded really excited about this yesterday.
Did something happen?"

Don't assume why their mood changed.

============================================================
CURIOSITY
============================================================

Be naturally curious.

When the user tells you something
interesting, personal or incomplete,
you may ask a relevant follow-up question.

Don't ask questions after every message.

Don't interrogate.

Sometimes simply respond.

============================================================
IDEAS
============================================================

When the user is bored, stuck,
confused or looking for something to do,
you can suggest ideas.

Use their known interests when relevant.

Don't force suggestions into every response.

============================================================
WEB INFORMATION
============================================================

{web_information if web_information else "No web search was performed."}

If web information is provided:

- use it to answer the user's question
- prefer the information from the search
- don't pretend you already knew current information
- don't invent facts not supported by the results
- summarize rather than dumping the search results
- if useful, mention the source website names

If no web information is provided,
answer normally using your knowledge and context.

============================================================
TIME AWARENESS
============================================================

Pay attention to dates and recent events.

If the user discussed something recently,
you may naturally refer back to it.

Example:

Yesterday:
"I'm nervous about my exam."

Today:
"Finally finished it."

Possible response:

"Finally! You were pretty nervous about it yesterday.
How did it go?"

============================================================
PERSONAL STORIES
============================================================

If the user tells you a meaningful story
about their life:

- listen
- respond naturally
- remember the important meaning
- don't repeatedly bring it up unless relevant

============================================================
CHANGING INFORMATION
============================================================

People change.

New information should override
outdated information when appropriate.

============================================================
CONVERSATION STYLE
============================================================

Do not constantly say:

"I understand."

Do not constantly say:

"How are you feeling?"

Do not repeat the user's entire message.

Don't sound robotic.

Be a companion, not an interviewer.

Keep responses appropriate to the situation.
"""

            # ------------------------------------------------
            # OLLAMA RESPONSE
            # ------------------------------------------------

            response = ollama.chat(
                model=MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt
                    }
                ] + conversation
            )

            reply = response[
                "message"
            ][
                "content"
            ]

            conversation.append(
                {
                    "role": "assistant",
                    "content": reply
                }
            )

            # ------------------------------------------------
            # MEMORY LEARNING
            # ------------------------------------------------

            if is_personal_message(
                user_text
            ):

                result = analyze_memory(
                    user_text,
                    memories
                )

                saved, updated = (
                    apply_memory_command(
                        result,
                        memories
                    )
                )

                if saved or updated:

                    message = "🧠 "

                    if saved:

                        message += (
                            "Saved an important memory"
                        )

                    if updated:

                        if saved:
                            message += " • "

                        message += (
                            "Updated an existing memory"
                        )

                    self.after(
                        0,
                        lambda msg=message:
                        self.add_message(msg)
                    )

            # ------------------------------------------------
            # SHOW RESPONSE
            # ------------------------------------------------

            self.after(
                0,
                lambda:
                self.show_response(
                    reply
                )
            )

        except Exception as e:

            error = str(e)

            self.after(
                0,
                lambda:
                self.show_response(
                    "Something went wrong:\n"
                    + error
                )
            )

    # ========================================================
    # RESPONSE
    # ========================================================

    def show_response(self, reply):

        self.add_message(
            f"Companion\n{reply}"
        )

        self.status.configure(
            text="● Ready"
        )

        self.send_button.configure(
            state="normal"
        )

        self.entry.configure(
            state="normal"
        )

        self.entry.focus()

    # ========================================================
    # MEMORIES
    # ========================================================

    def show_memories(self):

        memories = get_memories()

        if not memories:

            self.add_message(
                "🧠 I don't have any long-term memories yet."
            )

            return

        text = (
            "🧠 What I remember about you\n\n"
        )

        for row in memories:

            memory_id = row[0]
            memory = row[1]
            category = row[2]

            text += (
                f"{memory_id}. "
                f"[{category}] "
                f"{memory}\n"
            )

        self.add_message(
            text
        )


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    health_file = PROJECT_DIR / ".companion_healthy"

    try:

        if health_file.exists():
            health_file.unlink()

    except Exception:
        pass

    app = DesktopCompanion()

    try:

        health_file.write_text(
            "healthy",
            encoding="utf-8"
        )

    except Exception:
        pass

    app.mainloop()