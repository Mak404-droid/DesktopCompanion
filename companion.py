import ollama

MODEL = "llama3.2:3b"

print("=================================")
print("     AI DESKTOP COMPANION")
print("=================================")
print("Type 'exit' to quit.\n")

messages = [
    {
        "role": "system",
        "content": (
            "You are a helpful desktop AI companion. "
            "Be friendly, concise, and conversational. "
            "Remember the conversation during this session."
        ),
    }
]

while True:
    user_input = input("You: ")

    if user_input.lower() in {"exit", "quit"}:
        print("Goodbye!")
        break

    messages.append({
        "role": "user",
        "content": user_input
    })

    try:
        response = ollama.chat(
            model=MODEL,
            messages=messages
        )

        reply = response["message"]["content"]

        print(f"Companion: {reply}\n")

        messages.append({
            "role": "assistant",
            "content": reply
        })

    except Exception as e:
        print(f"Error: {e}")