"""
main.py — Entry point for the AI Email Coordination Assistant prototype.

Run:
    python main.py           # process latest unread email once
    python main.py --watch   # poll every 60 seconds
"""
import os
import sys
import time
from dotenv import load_dotenv

load_dotenv()

from proto.graph import build_graph


def run_once():
    """Build and invoke the LangGraph agent once."""
    print("\n" + "="*55)
    print("  🤖 AI Email Coordination Assistant — Prototype")
    print("="*55)

    app = build_graph()
    initial_state = {
        "email": None,
        "intent": "",
        "processed_content": "",
        "reply_body": "",
        "status": "",
    }

    final_state = app.invoke(initial_state)

    print("\n" + "-"*55)
    print(f"  ✅ Run complete. Status: {final_state['status'].upper()}")
    if final_state.get("intent"):
        print(f"  📌 Intent detected: {final_state['intent']}")
    print("-"*55 + "\n")

    return final_state


def main():
    watch_mode = "--watch" in sys.argv

    if watch_mode:
        interval = int(os.getenv("POLL_INTERVAL_SECONDS", 60))
        print(f"👁️  Watch mode: polling every {interval}s. Press Ctrl+C to stop.\n")
        try:
            while True:
                run_once()
                print(f"⏳ Waiting {interval}s for next check...")
                time.sleep(interval)
        except KeyboardInterrupt:
            print("\n🛑 Agent stopped.")
    else:
        run_once()


if __name__ == "__main__":
    main()
