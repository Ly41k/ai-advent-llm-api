"""Original owned documentation worker with the explicitly frozen research selector."""
import bublik_developer.agent_worker as worker
from selection_policy import search
worker.search=search
if __name__=='__main__':raise SystemExit(worker.main())
