import resource, subprocess, sys, time
t=time.time(); rc=subprocess.call(["bash","-c",sys.argv[1]])
r=resource.getrusage(resource.RUSAGE_CHILDREN)
print(f"MEASURE rc={rc} wall_s={time.time()-t:.1f} user_s={r.ru_utime:.1f} sys_s={r.ru_stime:.1f} peak_rss_mb={r.ru_maxrss/1024:.0f}", flush=True)
sys.exit(rc)
