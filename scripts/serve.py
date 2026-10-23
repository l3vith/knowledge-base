"""Load a trusted local env file, then launch the combined two-route application."""
import argparse
import os
from pathlib import Path
from scripts.check_langfuse import load_local_env


def main():
    p=argparse.ArgumentParser();p.add_argument("--env-file",default=".env");p.add_argument("--host",default="127.0.0.1");p.add_argument("--port",type=int,default=8000)
    args=p.parse_args()
    if Path(args.env_file).exists():
        load_local_env(args.env_file)
    if os.getenv("OPENCODE_MODEL") and not os.getenv("LLM_MODEL"):
        os.environ["LLM_MODEL"]=os.environ["OPENCODE_MODEL"]
    import uvicorn
    uvicorn.run("kb.api:app",host=args.host,port=args.port,workers=1)

if __name__=="__main__":
    main()
