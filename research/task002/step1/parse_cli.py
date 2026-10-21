"""Split logs/04_cli.log into per-command JSON blobs -> step1/logs/cli_json/<n>.json"""
import json,re,os,sys
src=sys.argv[1]; out=sys.argv[2]; os.makedirs(out,exist_ok=True)
txt=open(src).read(); blocks=re.split(r"\n=+\n\$ codegraph ",txt)[1:]
for i,b in enumerate(blocks):
    cmd,body=b.split("\n",1); body=body.rsplit("\n[exit=",1)[0]
    try: j=json.loads(body[body.index("{"):]) ; json.dump({"cmd":"codegraph "+cmd,"out":j},open(f"{out}/{i:02d}.json","w"),indent=1); print(i,"json",cmd)
    except Exception as e: print(i,"text",cmd)
