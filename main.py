import os
import sys
import time
from dotenv import load_dotenv
from proto.graph import build_graph

def main():
    # Load environment variables from .env
    load_dotenv()
    
    # Build the LangGraph
    app = build_graph()
    
    # Configuration
    watch_mode = "--watch" in sys.argv
    interval = 10 # Check every 10 seconds in watch mode
    pid = os.getpid()
    
    print("\n=======================================================")
    print(f"  🤖 AI Email Assistant — Prototype (PID: {pid})")
    print("=======================================================\n")

    def run_once():
        # Initial state for each run
        initial_state = {
            "email": None,
            "intent": "",
            "processed_content": "",
            "cal_link": "",
            "meet_link": "",
            "reply_body": "",
            "status": ""
        }
        
        try:
            # Invoke the graph
            app.invoke(initial_state)
        except Exception as e:
            print(f"❌ Error during execution: {e}")

    if watch_mode:
        print(f"📡 Watch mode active: polling every {interval}s...")
        try:
            while True:
                run_once()
                # Optional: print a separator for the next poll
                time.sleep(interval)
        except KeyboardInterrupt:
            print("\n👋 Assistant stopped.")
    else:
        run_once()
        print("\n-------------------------------------------------------")
        print("  ✅ Run complete.")
        print("-------------------------------------------------------\n")

if __name__ == "__main__":
    main()
