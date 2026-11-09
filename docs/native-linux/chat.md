# Chat in the terminal

## Start

Open a terminal and paste:

```bash
cd /home/phatkitty/Projects/Marionette
./scripts/native-linux/chat.sh
```

Two log terminals open: **Connections and requests** and **Model processing**. In the chat terminal, wait for the `>` prompt, then type your message and press **Enter**.

Your prompt and typed input are neon green (`#39FF14`), status information and her reasoning are white, and her final answers are pink. Blank lines separate input, replies, and turns. Colors reset when chat exits; plain-output terminals remain uncolored. The chat transcript retains terminal color codes, while diagnostic logs keep their existing readable format.

## While chatting

- **Exit:** type `/exit`, or press **Ctrl+D** at an empty chat prompt.
- **Start fresh:** type `/clear`, or exit and launch again.

The local server is local to this computer and stops when the chat process exits. Its temporary address appears in the connections-and-requests log.

No setup report is generated or sent to her. She cannot open files or read logs herself.

Each session saves three matching files in `data/conversations/`:

- `…-chat.txt`: your messages, her reasoning, and her final answers.
- `…-server.txt`: connections and requests, shown in its own terminal.
- `…-model.txt`: model processing, shown in its own terminal.

After replies, the client checks space for the next turn. When needed, it leaves out oldest complete exchanges and prepares the shortened history while you read or type. Preparation and removed-exchange counts appear in the diagnostic logs, without interrupting the chat display. Older messages remain in the saved transcript but are no longer visible to her.

The total context is 65,536 tokens, including a 2,048-token next-message allowance and a 32,768-token combined thinking-and-answer allowance. Sending before preparation finishes, or sending a larger message, can still cause a wait. The client checks every actual message; oversized input is rejected without truncating it. There is no separate thinking cap: reasoning and the answer share the allowance, so reasoning can use it up before an answer appears. A notice appears if generation reaches its allowance. Thinking can increase the wait before the final answer; only final answers are kept in conversation history, while reasoning remains in the logs.

Only `/clear` and `/exit` are supported commands. Ctrl+C also exits. No file attachments, tools, summaries, or saved-memory loading are implemented.

Past logs stay there, but she starts fresh each launch. Logs remain local and are excluded from GitHub.

Unknown entries, warnings, and errors appear in both diagnostic files with the same event number. Original timestamps are retained. Long entries are wrapped into readable blocks; terminal control codes are shown as escaped text without being discarded. There is no new raw debug file; older logs remain untouched.

Closing either log window does not stop chat or recording. After chat exits, press **Enter** in each log window to close it. Restarting chat does not erase past logs.

## If setup is missing

From the same project folder, run:

```bash
python scripts/native-linux/setup.py
./scripts/native-linux/chat.sh
```

Setup needs internet access to download missing files. You do not need to run it before every chat.

For installation details and advanced settings, see [Setup](setup.md).
