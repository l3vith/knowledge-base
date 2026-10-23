"""Upgrade an existing collection's source metadata without LLM/embedding calls."""
import argparse
import json
from kb.config import get_settings
from kb.ingest.enrich import enrich_collection


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--collection',required=True)
    parser.add_argument('--source-dir',help='Optional original PDF directory for bookmarks, labels and links; identity checked')
    args=parser.parse_args()
    print(json.dumps(enrich_collection(args.collection,get_settings(),args.source_dir),indent=2))


if __name__=='__main__':main()
